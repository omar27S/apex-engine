"""THE TOURNAMENT — reality judges the DNA.

The first real evolutionary run. Genomes compete on real history; the Phase-1
honest engine supplies the trades; the R13 health classifier and the fitness
Wilson lower bound do the judging; deaths are recorded; and the champions must
survive the walk-forward test.

Shape of a run (per :func:`run`):

1. **Gen 0** — the 44 institutional seeds, then weighted random draws, then R12
   vault immigration, normalized to ``population``.
2. **Each generation** — evaluate every genome on the TRAIN slice; rank by
   :func:`fitness.fitness`; record deaths; keep ``elite``; breed the rest
   (crossover among elite-weighted parents + mutation) and re-seed the tail from
   the vault (R12). Life and death inside the tournament follow plain fitness —
   only CHAMPION promotion pays the R16 lottery tax.
3. **Checkpoint** — after every generation, the full state (population, RNG
   bit-generator state, generation index, results) is written to
   ``.tournament_state.json`` so :func:`run` can resume byte-identically.
4. **Time-box** — at ``max_wallclock_seconds`` the loop stops gracefully between
   genomes, marks the run ``partial``, and reports honestly.
5. **Walk-forward** — the top ``top_n_test`` train survivors are evaluated on the
   TEST slice. THE OUTFIT-EXPOSURE REPORT lists every train hero whose test
   Wilson LB falls below the promotion bar (or whose test net_r is negative):
   "train heroes, test zeros". It is the conscience of the tournament.

Determinism: same seed, same frames -> same leaderboard (hash-compared in tests).
Pure module: no I/O at import; files are touched only when a caller runs with a
checkpoint or ledger path.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from app.core import law
from app.quant import breeding, costs, fitness, statarb, vault
from app.quant import cost_report, death_ledger, evaluator
from app.quant.evaluator import (
    EvaluationConfig,
    evaluate,
    evaluate_adversarial,
    evaluate_dual,
)
from app.quant.frames import Frames
from app.quant.genome import ENSEMBLE_FAMILY, FAMILIES, StrategyGenome

__all__ = [
    "TournamentConfig",
    "GenerationResult",
    "OutfitExposure",
    "TournamentResult",
    "run",
    "load_checkpoint",
    "DUAL_SELECTION_DIGEST",
    "dual_selection_manifest",
    "RAMS_SEED_SCHEDULE",
    "seed_schedule_digest",
    "DEFAULT_ENSEMBLE_QUOTA",
    "ensemble_manifest",
    "ensemble_manifest_digest",
    "ensemble_survival_table",
    "ENSEMBLE_SURVIVAL_COLUMNS",
    "ensemble_verdict",
]

CHECKPOINT_PATH = "data/history/.tournament_state.json"

# R55 — the fixed columns of the ensemble survival table (emitted on every run).
# R58 (Phase 7c) — ``member_source`` splits the ensemble arm into ELITE (members
# drawn from the previous generation's top singles) and RANDOM (the exploration
# share). The single arm carries ``None`` (no members to source).
ENSEMBLE_SURVIVAL_COLUMNS: tuple[str, ...] = (
    "arm", "member_source", "trials", "ranked", "survivors", "unseen_pass_rate",
)

# The three arms the table reports: elite ensembles, random ensembles, singles.
SURVIVAL_ARMS: tuple[str, ...] = ("ensemble_elite", "ensemble_random", "single")


def survival_arm(genome) -> str:
    """R58 — the survival-table arm a genome belongs to (elite|random|single)."""
    if getattr(genome, "family", None) != ENSEMBLE_FAMILY:
        return "single"
    source = getattr(genome, "ensemble_source", "random")
    return "ensemble_elite" if source == "elite" else "ensemble_random"


def _member_source_of(arm: str) -> str | None:
    if arm == "ensemble_elite":
        return "elite"
    if arm == "ensemble_random":
        return "random"
    return None


def ensemble_survival_table(trials_by_arm: dict, survivors_by_arm: dict,
                            ranked_by_arm: dict | None = None,
                            gauntlet_by_arm: dict | None = None,
                            arms: tuple[str, ...] = SURVIVAL_ARMS) -> list[dict]:
    """R55/R58 — the ensemble-vs-single survival table, honest even when singles win.

    One row per arm (``ensemble_elite``, ``ensemble_random``, ``single``), each
    carrying its ``member_source`` (elite | random | null). ``unseen_pass_rate`` is
    the fraction of that arm's finalists that passed the unseen majority gauntlet
    (``None`` when the arm had no finalists — never a fabricated zero). The table
    is DATA, not a verdict: if singles outsurvive ensembles, the numbers say so.
    """
    ranked_by_arm = ranked_by_arm or {}
    gauntlet_by_arm = gauntlet_by_arm or {}
    rows: list[dict] = []
    for arm in arms:
        trials = int(trials_by_arm.get(arm, 0))
        ranked = int(ranked_by_arm.get(arm, 0))
        survivors = int(survivors_by_arm.get(arm, 0))
        g = gauntlet_by_arm.get(arm)
        if g is None:
            rate = None
        else:
            tested = int(g.get("tested", 0))
            passed = int(g.get("passed", 0))
            rate = (passed / tested) if tested else None
        rows.append({
            "arm": arm,
            "member_source": _member_source_of(arm),
            "trials": trials,
            "ranked": ranked,
            "survivors": survivors,
            "unseen_pass_rate": rate,
        })
    return rows


# DEBT-040 — R58 (elite soup) graduation: the hypothesis, adjudicated from data.
# The claim: ensembling from the elite pool beats single strategies. The verdict is
# read from the survival history (survivor rate per arm), never from plausibility.
VERDICT_MIN_TRIALS: int = 30


def ensemble_verdict(nights: list[list[dict]]) -> dict:
    """DEBT-040 — adjudicate R58 (elite soup) from the REAL survival history.

    Aggregates each arm's ``survivors``/``trials`` across every night and compares
    the ELITE survivor rate against the SINGLE survivor rate. The claim "elite soup
    beats singles" is ``supported`` when the elite rate is at least the single rate,
    ``refuted`` when it is below it, and ``inconclusive`` when an arm never reached
    ``VERDICT_MIN_TRIALS`` (never a fabricated verdict).
    """
    agg: dict[str, dict] = {}
    for night in (nights or []):
        for row in (night or []):
            arm = row.get("arm")
            if arm not in SURVIVAL_ARMS:
                continue
            a = agg.setdefault(arm, {"trials": 0, "survivors": 0})
            a["trials"] += int(row.get("trials") or 0)
            a["survivors"] += int(row.get("survivors") or 0)
    if not agg:
        return {"verdict": "inconclusive", "elite_rate": None, "single_rate": None,
                "elite_trials": 0, "single_trials": 0,
                "reading": "R58 (zuppa d'elite): nessuna storia -- inconcludente"}
    el = agg.get("ensemble_elite", {"trials": 0, "survivors": 0})
    sg = agg.get("single", {"trials": 0, "survivors": 0})
    if el["trials"] < VERDICT_MIN_TRIALS or sg["trials"] < VERDICT_MIN_TRIALS:
        return {"verdict": "inconclusive", "elite_rate": None, "single_rate": None,
                "elite_trials": el["trials"], "single_trials": sg["trials"],
                "reading": (f"R58 (zuppa d'elite): troppi pochi trial "
                            f"(elite {el['trials']}, single {sg['trials']}) -- inconcludente")}
    er = el["survivors"] / el["trials"]
    sr = sg["survivors"] / sg["trials"]
    verdict = "supported" if er >= sr else "refuted"
    return {"verdict": verdict, "elite_rate": round(er, 5), "single_rate": round(sr, 5),
            "elite_trials": el["trials"], "single_trials": sg["trials"],
            "reading": (f"R58 (zuppa d'elite): {'CONFERMATA' if verdict == 'supported' else 'REFUTATA'}"
                        f" -- elite sopravvive {er:.2%}, single {sr:.2%} "
                        f"({el['trials']} vs {sg['trials']} trial)")}

# R39 (Phase 6a) — DUAL SELECTION. The manifest names every parameter that shapes
# the dual world; its digest is hash-pinned in tests/quant/test_tournament.py. A
# change to dual selection is a DELIBERATE commit (edit the values, recompute the
# digest, update the pin in the same commit).
# R42 (Phase 6b) — THE ROTATING ENEMY. The adversarial seed ROTATES per
# generation: generation g faces ``schedule[g % len(schedule)]``. The sealed
# default schedule cycles all three seeds once. The three-seed majority verdict
# remains the CROWN gate for finalists (R40) — rotation is the SELECTION
# pressure, the verdict is the PROMOTION law.
RAMS_SEED_SCHEDULE = (0, 1, 2)


def dual_selection_manifest() -> dict:
    """R39+R42+R43 — the sealed description of dual selection (one declaration).

    R39 dual selection (clean diagnostic vs adversarial ranking), R42 seed
    rotation (the enemy changes face every generation), R43 clean demotion
    (in-generation ranking is ADVERSARIAL ONLY; clean is evaluated for the elite
    set alone). The digest is hash-pinned in tests/quant/test_tournament_dual.py;
    changing any value is a DELIBERATE commit (edit, recompute, update the pin).
    """
    return {
        "dual_selection": True,
        "primary_rank": "adversarial_wilson_lb",
        "clean": "elite_diagnostic",
        "clean_elite_eval": True,
        "rotation": "per_generation",
        "rams_seed_schedule": list(RAMS_SEED_SCHEDULE),
        "tiebreak": ["adversarial_wilson_lb", "autopsy_resilience", "net_r", "drawdown"],
        "billing": "adversarial_all + clean_elite",
        "adversarial_floor_death": "rams_floor",
    }


def _digest_manifest(manifest: dict) -> str:
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, default=str).encode()
    ).hexdigest()


DUAL_SELECTION_DIGEST = _digest_manifest(dual_selection_manifest())


def seed_schedule_digest(schedule: tuple[int, ...] = RAMS_SEED_SCHEDULE) -> str:
    """R42 — the pinned digest of the rotation schedule (R18 style)."""
    return _digest_manifest({"rotation": "per_generation", "schedule": list(schedule)})


# R55 (Phase 7b) — THE ENSEMBLE THESIS. Ensembles get a guaranteed population
# share, members are DISTINCT BY FAMILY, elite ensembles evolve member-by-member,
# and every tournament emits the ensemble-vs-single survival table. The manifest
# names every parameter that shapes the ensemble pressure; its digest is
# hash-pinned in tests/quant/test_tournament.py. A change is a DELIBERATE commit
# (edit the values, recompute the digest, update the pin in the same commit).
DEFAULT_ENSEMBLE_QUOTA = 0.25


def ensemble_manifest(quota: float = DEFAULT_ENSEMBLE_QUOTA,
                      elite_soup: bool = True) -> dict:
    """R55/R58 — the sealed description of the ensemble thesis (one declaration)."""
    return {
        "ensemble_quota": float(quota),
        "min_quota": 0.25,                       # the directive's floor
        "member_diversity": "distinct_family",
        "member_evolution": "single_member_per_child",
        "quorum": "evolvable_gene_r3",
        "member_source": "elite_soup" if elite_soup else "random",
        "exploration_share": 0.10,               # R58 — random-member exploration
        "survival_table": ["trials", "ranked", "survivors", "gauntlet_pass_rate",
                           "member_source"],
    }


def ensemble_manifest_digest(quota: float = DEFAULT_ENSEMBLE_QUOTA,
                             elite_soup: bool = True) -> str:
    return _digest_manifest(ensemble_manifest(quota, elite_soup))



@dataclass(frozen=True)
class TournamentConfig:
    """Everything a run needs to be reproducible and bounded."""

    pairs: tuple[str, ...]
    population: int = 120
    generations: int = 4
    elite: int = 20
    vault_fraction: float = 0.05
    min_trades: int = 30
    streak_kill: int = 8
    train_frac: float = 0.7
    seed: int = 0
    max_wallclock_seconds: float = 900.0
    top_n_test: int = 10
    mutation_rate: float = 0.25
    checkpoint_path: str | None = None
    death_ledger_path: str | None = None
    # R17/R18: costs are ON by default (None = the sealed model). ``use_costs=False``
    # is the DIAGNOSTIC gross mode ONLY — its leaderboard must never be ranked.
    cost_model_hash: str | None = None
    use_costs: bool = True
    # R39 (Phase 6a) — DUAL SELECTION. When True, every genome is judged on BOTH
    # the clean tape and the RAMS adversarial tape; the leaderboard ranks on the
    # ADVERSARIAL Wilson LB, clean metrics ride along as diagnostics, and an
    # adversarial-floor death is recorded with cause "rams_floor".
    dual_selection: bool = True
    # R42 (Phase 6b) — THE ROTATING ENEMY. The adversarial seed of generation g is
    # ``adversarial_seed_schedule[g % len]``; the schedule is part of run identity
    # and its digest is pinned (R18 style). Rotation is SELECTION pressure only —
    # the finalist crown still needs the R40 three-seed majority verdict.
    adversarial_seed_schedule: tuple[int, ...] = RAMS_SEED_SCHEDULE
    # R43 (Phase 6b) — CLEAN DEMOTION. Within generations the population ranks on
    # the ADVERSARIAL world ONLY. The clean world is evaluated solely for the ELITE
    # set post-selection: the clean world is billed exactly ``elite x generations``
    # times per run (its rows feed the veto school's clean-era corpus + diagnostics).
    clean_elite_eval: bool = True
    # R47 (Phase 6c) — UNATTENDED BODIES BAN. An unattended run (a cloud/night-shift
    # run with no human present) may NOT admit the ATTENDED-ONLY ``generated_body``
    # family. Fail-closed at ``run`` start; the two colliding is a ValueError.
    unattended: bool = False
    # R55 (Phase 7b) — THE ENSEMBLE THESIS. A guaranteed share of the population is
    # forced onto the ensemble family (>= 0.25 by the directive), members are
    # distinct by family, elite ensembles evolve member-by-member, and the run
    # emits the ensemble-vs-single survival table. Part of run identity.
    ensemble_quota: float = DEFAULT_ENSEMBLE_QUOTA
    # R58 (Phase 7c) — THE ELITE SOUP. When True, the quota-share ensembles draw
    # their members from the previous generation's top-ranked SINGLES (10%
    # exploration stays random). False reproduces the Phase 7b random-member thesis.
    # Part of run identity (it changes what the ensembles ARE).
    elite_soup: bool = True
    # R59 (Phase 7c) — THE MEMBER VOTE CACHE. When True, a member's signals are
    # computed once per (member, pair, world seed, slice) and reused. A pure
    # PERFORMANCE flag (no effect on results); kept out of run identity.
    vote_cache: bool = True

    def signature(self) -> str:
        """Identity of a run for checkpoint compatibility.

        Stop conditions (time-box) and I/O paths are NOT part of identity: a run
        killed by the clock, or one whose generation budget is extended on resume,
        must still find its checkpoint. Everything that shapes the population and
        the breeding (pairs, size, elite, seed, rates, min_trades) IS identity.
        The dual-selection flag, its seed ROTATION schedule (R42) and the clean
        demotion flag (R43) are ALL identity — they change the ranking world.
        """
        payload = asdict(self)
        for stop_condition in (
            "max_wallclock_seconds", "generations",
            "checkpoint_path", "death_ledger_path",
            "vote_cache",  # R59 — a pure performance flag, not run identity
        ):
            payload.pop(stop_condition, None)
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class GenerationResult:
    """One generation's honest ledger."""

    generation: int
    evaluated: int
    ranked: int
    unranked: int
    best_signature: str
    best_family: str
    best_wilson_lb: float
    best_net_r: float
    deaths: dict
    trials: int
    adversarial_seed: int = 0  # R42 — the enemy face this generation faced


@dataclass
class OutfitExposure:
    """"Train hero, test zero": a champion that did not survive reality."""

    signature: str
    family: str
    train_wilson_lb: float
    train_net_r: float
    train_trades: int
    test_wilson_lb: float
    test_net_r: float
    test_trades: int
    reason: str


@dataclass
class TournamentResult:
    """The full record of a run (persisted verbatim to JSON by the tool)."""

    config_hash: str
    config: dict
    seed: int
    generations: list[GenerationResult]
    leaderboard: list[dict]          # top-N train survivors (ranked keys inside)
    test_leaderboard: list[dict]     # same heroes, judged on the TEST slice
    outfit_exposure: list[OutfitExposure]
    death_summary: dict
    trials: int
    partial: bool
    wallclock_seconds: float
    population_hashes: dict          # gen -> sha1 of the ordered population
    stopped_reason: str
    cost_model_hash: str = "diagnostic_gross"
    diagnostic: bool = False         # True => gross mode, NOT FOR RANKING (R17)
    final_population: list[dict] = field(default_factory=list)  # R19 era comparison
    # Phase 3.1 — the surviving population's DNA (serialized), so the pyramid can
    # muster Soldiers from the very genomes the honest judge passed. Ordered as
    # ``final_population`` (ranked, best first).
    final_population_genomes: list[dict] = field(default_factory=list)
    # R21 — the NET-POSITIVE survivors alone (the only genomes eligible for the
    # pyramid's ranks). ``survivor_population`` are their rows, ``survivor_genomes``
    # their DNA. A genome on ``final_population`` with net_r <= 0 is EXILED, not a
    # soldier; mustering it would contradict R21.
    survivor_population: list[dict] = field(default_factory=list)
    survivor_genomes: list[dict] = field(default_factory=list)
    # R39 (Phase 6a) — DUAL SELECTION. ``dual_selection`` is True when the
    # leaderboard was ranked on the adversarial world (clean metrics are then
    # diagnostics). ``dual_selection_digest`` pins the sealed dual manifest.
    dual_selection: bool = False
    dual_selection_digest: str = ""
    # R55 (Phase 7b) — THE ENSEMBLE SURVIVAL TABLE. Ensembles vs singles: trials,
    # ranked rows, survivors, and the unseen-gauntlet pass rate. Emitted by EVERY
    # run and persisted in the certificate; the table says the truth even when
    # singles outsurvive ensembles.
    ensemble_survival: list[dict] = field(default_factory=list)
    ensemble_quota: float = DEFAULT_ENSEMBLE_QUOTA
    # R58 (Phase 7c) — the elite-soup thesis flag (part of run identity).
    elite_soup: bool = True
    # R59 (Phase 7c) — the member vote cache's honest arithmetic for this run
    # (hits/misses/size/hit_rate). Pure performance telemetry; not identity.
    vote_cache_stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["outfit_exposure"] = [asdict(o) for o in self.outfit_exposure]
        return d


# ---------------------------------------------------------------------------
# Population helpers.
# ---------------------------------------------------------------------------
def _population_hash(population: list[StrategyGenome]) -> str:
    blob = json.dumps([g.signature() for g in population], sort_keys=False)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def _normalize(
    population: list[StrategyGenome], size: int, rng, *, ensemble_quota: float = 0.0
) -> list[StrategyGenome]:
    """Trim or pad to exactly ``size`` (padding is fresh random DNA, quota-aware)."""
    pop = list(population[:size])
    while len(pop) < size:
        pop.append(breeding.random_genome(rng, ensemble_quota=ensemble_quota))
    return pop


def _gen0(config: TournamentConfig, rng) -> list[StrategyGenome]:
    """44 seeds, then weighted draws (ensemble-quota-aware), then vault (R12)."""
    from app.quant.seeds import build_seeds

    seeds = list(build_seeds().values())
    pop: list[StrategyGenome] = list(seeds[: config.population])
    while len(pop) < config.population:
        pop.append(breeding.random_genome(
            rng, ensemble_quota=config.ensemble_quota))
    pop = _normalize(pop, config.population, rng,
                     ensemble_quota=config.ensemble_quota)
    return _apply_vault(pop, config, rng)


def _apply_vault(population: list[StrategyGenome], config: TournamentConfig, rng):
    """Replace the population tail with R12 immigrants.

    The slot count is delegated to :func:`vault.immigration_quota` so R12's 5%
    floor and the "at least one per non-empty population" rule live in ONE place;
    ``config.vault_fraction`` only overrides the fraction when it differs.
    """
    size = len(population)
    if size == 0:
        return []
    if abs(config.vault_fraction - vault.IMMIGRATION_FRACTION) < 1e-12:
        quota = vault.immigration_quota(size)
    else:
        quota = max(1, int(round(size * config.vault_fraction)))
    keep = size - quota
    immigrants = [
        breeding.random_genome(rng, ensemble_quota=config.ensemble_quota)
        for _ in range(quota)
    ]
    return list(population[:keep]) + immigrants


def _elite_parents(elites: list[StrategyGenome], rng) -> tuple[StrategyGenome, StrategyGenome]:
    """Two parents drawn from the elite, biased toward the front (better rank)."""
    n = len(elites)
    weights = np.linspace(n, 1.0, n)  # front (rank 1) weighs most
    weights = weights / weights.sum()
    idx = rng.choice(n, size=2, replace=True, p=weights)
    return elites[int(idx[0])], elites[int(idx[1])]


def _breed_children(
    elites: list[StrategyGenome], count: int, config: TournamentConfig, rng
) -> list[StrategyGenome]:
    """Crossover + mutate, reserving a quota share of fresh ENSEMBLE draws (R55).

    A child of an elite ENSEMBLE is evolved at MEMBER level (one member mutates,
    lineage preserved) instead of being crossed wholesale — the elite's winning
    core rides into the next generation.

    R58 (Phase 7c) — the quota-share ensembles draw their members from the ELITE
    SOUP (the previous generation's top-ranked SINGLES), with a 10% exploration
    share left to random draws. The thesis is five independent ELITE voters.
    """
    n_ensemble = 0
    if count > 0 and config.ensemble_quota > 0.0:
        n_ensemble = int(round(count * min(1.0, config.ensemble_quota)))
    n_cross = count - n_ensemble

    children: list[StrategyGenome] = []
    for _ in range(n_cross):
        if len(elites) >= 2:
            a, b = _elite_parents(elites, rng)
            child = breeding.crossover_genome(a, b, rng)
        else:
            child = breeding.random_genome(rng)
        if child.family == breeding.ENSEMBLE_FAMILY:
            # R55 — member-level evolution beat: one member moves, the rest survive.
            child = breeding.evolve_ensemble_member(
                child, rng, rate=config.mutation_rate)
        else:
            child = breeding.mutate_genome(child, rng, rate=config.mutation_rate)
        children.append(child)

    # R55/R58 — the guaranteed ensemble share. Members come from the ELITE SOUP
    # (R58) with a 10% exploration share; the source is recorded on the genome so
    # the survival table can split elite vs random ensembles honestly.
    soup = breeding.elite_soup_pool(elites) if config.elite_soup else []
    for _ in range(n_ensemble):
        child = _ensemble_from_soup(soup, config, rng)
        child = breeding.mutate_genome(child, rng, rate=config.mutation_rate)
        children.append(child)
    return children


def _ensemble_from_soup(soup, config: TournamentConfig, rng) -> StrategyGenome:
    """R58 — a fresh ensemble genome whose members come from the elite soup."""
    size = int(rng.integers(
        breeding.ENSEMBLE_MIN_MEMBERS, breeding.ENSEMBLE_MAX_MEMBERS + 1))
    members, source = breeding.elite_soup_members(soup, rng, size=size)
    genes = {b.name: breeding._draw_gene(rng, breeding.ENSEMBLE_FAMILY, b.name)
             for b in breeding.GENE_BOUNDS}
    genes = breeding._repair_coherence(genes, breeding.ENSEMBLE_FAMILY)
    genes["family"] = breeding.ENSEMBLE_FAMILY
    genes["ensemble_members"] = members
    genes["ensemble_size"] = breeding.clamp_gene("ensemble_size", len(members))
    genes["ensemble_min_votes"] = breeding._ensemble_quorum(rng, len(members))
    genes["ensemble_source"] = source
    return StrategyGenome.from_dict(genes)


def _adversarial_cfg(eval_cfg, rams_cfg):
    """The R39 adversarial evaluation config from a clean config + RAMS config.

    Identical gate stack (streak_kill/trail/enforce_min_atr), the SEALED selection
    book, and the R36 spread multiplier. Shared by the in-generation ranking and the
    R43 clean-demotion path so both rank on the SAME adversarial world.
    """
    return EvaluationConfig(
        streak_kill=eval_cfg.streak_kill,
        trail=eval_cfg.trail,
        enforce_min_atr=eval_cfg.enforce_min_atr,
        cost_model=(costs.SELECTION_COST_MODEL if eval_cfg.cost_model is not None else None),
        adversarial_spread_mult=rams_cfg.spread_multiplier,
    )


def _eval_clean(genome, universe, eval_cfg, vote_cache=None):
    """Evaluate ``genome`` on the CLEAN world (R43 elite-only diagnostic)."""
    statarb_clean = None
    if genome.family in {"cointegration_statarb"}:
        statarb_clean = statarb.statarb_z_map(genome, universe)
    return evaluate(genome, universe, eval_cfg, statarb_z_by_pair=statarb_clean,
                    vote_cache=vote_cache, world_seed=0)


def _evaluate_in_universe(genome, universe: dict, eval_cfg, *, adversarial: tuple | None = None,
                          rams_config=None, dual: bool = False):
    """Evaluate ``genome`` on ``universe``, supplying statarb z ONLY for the
    relative-value family (whose ``statarb_window`` is genome-specific). Every
    other family pays zero cost for a cross-pair z it will never read.

    R39 — when ``dual`` and ``adversarial`` (a precomputed ``(adv_frames, logs)``)
    are supplied, returns a :class:`DualEvaluationReport` (clean + adversarial);
    otherwise returns a plain :class:`EvaluationReport` (clean only).

    The caller is responsible for threading the adversarial config (spread
    multiplier) and the R36 slippage via ``rams_config``.
    """
    from app.quant.rams.config import DEFAULT_RAMS

    adv_frames, adv_logs = (adversarial if adversarial else (None, None))
    statarb_clean = None
    if genome.family in {"cointegration_statarb"}:
        statarb_clean = statarb.statarb_z_map(genome, universe)
    statarb_adv = None
    if adv_frames is not None and genome.family in {"cointegration_statarb"}:
        statarb_adv = statarb.statarb_z_map(genome, adv_frames)

    if dual:
        from app.quant import costs as _costs

        rc = rams_config if rams_config is not None else DEFAULT_RAMS
        adv_cfg = EvaluationConfig(
            streak_kill=eval_cfg.streak_kill,
            trail=eval_cfg.trail,
            enforce_min_atr=eval_cfg.enforce_min_atr,
            cost_model=_costs.SELECTION_COST_MODEL if eval_cfg.cost_model is not None else None,
            adversarial_spread_mult=rc.spread_multiplier,
        )
        return evaluate_dual(
            genome, universe, eval_cfg, adv_frames, adv_cfg,
            adversarial_logs=adv_logs,
            statarb_z_by_pair=statarb_clean,
            statarb_z_by_pair_adv=statarb_adv,
            rams_config=(rc if eval_cfg.cost_model is not None else None),
        )
    return evaluate(genome, universe, eval_cfg, statarb_z_by_pair=statarb_clean)


# ---------------------------------------------------------------------------
# Checkpointing.
# ---------------------------------------------------------------------------
def _save_checkpoint(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, default=str))
    tmp.replace(target)  # atomic replace: a crash never leaves a torn checkpoint


def load_checkpoint(path: str) -> dict | None:
    """Read a checkpoint; returns ``None`` if absent or unreadable (fail-open load)."""
    target = Path(path)
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text())
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# The run.
# ---------------------------------------------------------------------------
def run(
    config: TournamentConfig,
    train_frames: dict[str, Frames],
    test_frames: dict[str, Frames] | None = None,
    *,
    resume: bool = True,
    clock=time.monotonic,
) -> TournamentResult:
    """Run (or resume) a tournament. See the module docstring for the shape.

    ``clock`` is injectable so the time-box can be tested deterministically.
    """
    start = clock()
    config_hash = config.signature()
    # R47 (Phase 6c) — UNATTENDED BODIES BAN. Fail-closed BEFORE any work: an
    # unattended run may never admit the ATTENDED-ONLY generated_body family.
    from app.quant.signals import assert_attended_ok
    assert_attended_ok(bool(config.unattended), FAMILIES)
    rng = np.random.default_rng(config.seed)
    cost_model = costs.DEFAULT_COST_MODEL if config.use_costs else None
    if config.use_costs:
        # R18: a run records WHICH sealed cost model judged it; an eval model that
        # differs from the caller's pinned hash is a loud mismatch, never silent.
        active_hash = costs.manifest_digest(cost_model)
        if config.cost_model_hash is not None and config.cost_model_hash != active_hash:
            raise ValueError(
                f"cost model hash mismatch: config pins {config.cost_model_hash} "
                f"but the sealed model digests to {active_hash}"
            )
    else:
        active_hash = "diagnostic_gross"
    eval_cfg = EvaluationConfig(streak_kill=config.streak_kill, cost_model=cost_model)

    # R39/R42/R43 (Phase 6a/6b) — DUAL SELECTION + THE ROTATING ENEMY.
    # The adversarial tape is wounded PER SEED, ONCE per run (the adversary is
    # deterministic under its seed), then cached. Generation g faces
    # ``schedule[g % len]`` (R42): the enemy changes face every round. Under R43
    # (clean demotion) the clean world is NOT evaluated in-generation — it is
    # billed for the elite set alone, post-selection.
    dual = bool(config.dual_selection)
    schedule = tuple(int(s) for s in (config.adversarial_seed_schedule or ()))
    if dual and not schedule:
        raise ValueError(
            "dual_selection needs a non-empty adversarial_seed_schedule (fail-closed)"
        )
    rams_cfg = None
    _adv_cache: dict[int, tuple] = {}
    if dual:
        from app.quant.rams.config import DEFAULT_RAMS
        from app.quant.rams.report import adversarial_frames as _rams_wound

        rams_cfg = DEFAULT_RAMS

        def _wounded(seed: int):
            """Wound-and-cache the adversarial world for a rotation seed (R42)."""
            if seed not in _adv_cache:
                _adv_cache[seed] = _rams_wound(train_frames, rams_cfg, seed=seed)
            return _adv_cache[seed]

    population: list[StrategyGenome] | None = None
    generations: list[GenerationResult] = []
    population_hashes: dict[str, str] = {}
    trials = 0
    start_gen = 0
    partial = False
    stopped_reason = "completed"
    all_deaths: list[dict] = []
    schedule_pos = 0  # R42 — the rotation position (generations already completed)
    # R55/R58 — per-arm tallies. ``trials`` counts every genome evaluated; ``ranked``
    # counts the rows that cleared the fitness floor. Three arms: elite ensembles,
    # random ensembles, and singles (see ``survival_arm``).
    arm_trials = {a: 0 for a in SURVIVAL_ARMS}
    arm_ranked = {a: 0 for a in SURVIVAL_ARMS}
    # R59 (Phase 7c) — the member vote cache, one per run (member votes are reused
    # across every ensemble containing that member). Disabled by ``config.vote_cache``.
    vote_cache = None
    if config.vote_cache:
        from app.quant.vote_cache import MemberVoteCache
        vote_cache = MemberVoteCache()

    ckpt = load_checkpoint(config.checkpoint_path) if (resume and config.checkpoint_path) else None
    if ckpt and ckpt.get("config_hash") == config_hash and ckpt.get("seed") == config.seed:
        population = [StrategyGenome.from_dict(g) for g in ckpt["population"]]
        rng.bit_generator.state = ckpt["rng_state"]
        trials = int(ckpt["trials"])
        start_gen = int(ckpt["generation"]) + 1
        generations = [GenerationResult(**g) for g in ckpt["generations"]]
        population_hashes = dict(ckpt["population_hashes"])
        all_deaths = list(ckpt.get("deaths", []))
        # R42 — restore the rotation position so a resumed run faces the SAME seed
        # on the SAME generation (identity includes the schedule position).
        schedule_pos = int(ckpt.get("schedule_pos", start_gen))
        # R55/R58 — restore the per-arm tallies so a resumed run's survival table is
        # byte-identical to the uninterrupted run (they accumulate across gens).
        arm_trials = {a: int(ckpt.get("arm_trials", {}).get(a, 0))
                      for a in SURVIVAL_ARMS}
        arm_ranked = {a: int(ckpt.get("arm_ranked", {}).get(a, 0))
                      for a in SURVIVAL_ARMS}

    if population is None:
        population = _gen0(config, rng)
        population_hashes["0"] = _population_hash(population)

    def _judge_one(genome, adv_rep, adv_seed, adv_universe=None, adv_logs=None):
        """R43 — rank on the ADVERSARIAL world ONLY; clean is elite-only.

        Returns ``(fit_report, adversarial_report)``. The adversarial report is the
        one the rotation produced for THIS generation; the clean world is not
        touched here (see the elite pass below).
        """
        fixable = None
        if eval_cfg.cost_model is not None and adv_universe is not None:
            fixable, _ = evaluator.adversarial_fixable_deaths(
                genome, adv_rep, adv_universe, adv_logs)
        result = fitness.fitness(adv_rep.metrics, config.min_trades, fixable_deaths=fixable)
        return result, adv_rep

    for gi in range(start_gen, config.generations):
        gen = gi
        # R42 — the ROTATING ENEMY: generation ``gen`` faces this seed.
        adv_seed = schedule[gen % len(schedule)]
        if dual:
            adversarial, adv_logs = _wounded(adv_seed)
        else:
            adversarial, adv_logs = None, None
        if clock() - start >= config.max_wallclock_seconds:
            partial = True
            stopped_reason = f"time-box at gen {gen}"
            break

        evaluated = 0
        judged: list[tuple[StrategyGenome, object, object]] = []
        judged_adv: dict[str, object] = {}
        per_gen_deaths: dict[str, int] = {}
        for genome in population:
            if clock() - start >= config.max_wallclock_seconds:
                partial = True
                stopped_reason = f"time-box mid-gen {gen} after {evaluated} genomes"
                break
            if dual:
                adv_rep = evaluate_adversarial(
                    genome, adversarial, _adversarial_cfg(eval_cfg, rams_cfg),
                    statarb_z_by_pair_adv=(
                        statarb.statarb_z_map(genome, adversarial)
                        if genome.family == "cointegration_statarb" else None),
                    rams_config=(rams_cfg if eval_cfg.cost_model is not None else None),
                    vote_cache=vote_cache, world_seed=int(adv_seed),
                )
            else:
                adv_rep = None
            # R43 — the clean world is NOT evaluated in-generation (elite-only).
            result, adv_rep = _judge_one(
                genome, adv_rep if dual else _eval_clean(genome, train_frames, eval_cfg, vote_cache),
                adv_seed, adversarial if dual else None, adv_logs if dual else None)
            judged.append((genome, adv_rep, result))
            sig = genome.signature()
            if dual:
                judged_adv[sig] = adv_rep
            # R55/R58 — per-arm tallies (elite ensemble vs random ensemble vs single).
            arm = survival_arm(genome)
            arm_trials[arm] += 1
            if result.ranked:
                arm_ranked[arm] += 1
            evaluated += 1
            trials += 1

        if not judged:
            break

        # Rank the ranked; unranked have no key and are never sorted as if they had.
        ranked_pairs = [(g, r, f) for (g, r, f) in judged if f.ranked]
        ranked_pairs.sort(key=lambda t: t[2].key())
        elite_ranked = ranked_pairs[: config.elite]

        # R43 — CLEAN DEMOTION. The clean world is billed for the ELITE set alone,
        # AFTER selection, as a diagnostic + the veto school's clean-era rows.
        clean_by_sig: dict[str, object] = {}
        if dual and config.clean_elite_eval:
            for g, _r, _f in elite_ranked:
                clean_by_sig[g.signature()] = _eval_clean(g, train_frames, eval_cfg, vote_cache)

        fine = []
        for g, r, f in ranked_pairs:
            sig = g.signature()
            adv_rep = judged_adv.get(sig)
            row = {
                "signature": sig,
                "family": g.family,
                "wilson_lb": f.wilson_lb,
                "win_rate": f.win_rate,
                "net_r": f.net_r,
                "gross_r": f.gross_r,  # DIAGNOSTIC ONLY (R17)
                "max_drawdown_r": f.max_drawdown_r,
                "trades": f.trades,
                "autopsy_resilience": f.autopsy_resilience,  # R39 tiebreak
                "adversarial_seed": int(adv_seed),  # R42 — the face it faced
            }
            if dual and sig in clean_by_sig:
                # R39/R43 — the clean world rides along as a DIAGNOSTIC for elites.
                cm = clean_by_sig[sig].metrics
                row.update({
                    "clean_wilson_lb": fitness.wilson_lower_bound(cm.wins, cm.trades),
                    "clean_net_r": float(cm.net_r),
                    "clean_win_rate": float(cm.win_rate),
                    "clean_trades": int(cm.trades),
                    "fixable_deaths": int(getattr(adv_rep, "autopsy_fixable", 0) or 0),
                    "diagnostic_clean": True,
                })
            fine.append(row)

        unranked = len(judged) - len(ranked_pairs)
        elite_ranked = ranked_pairs[: config.elite]

        # Deaths: unranked -> tournament_floor; a streak-killed ranked genome ->
        # early_stop; a ranked-but-not-elite genome -> apoptosis. Under R43 the
        # in-generation ranking IS the adversarial world, so a genome cannot be a
        # "clean-tape hero" HERE (clean is elite-only): the R39 ``rams_floor`` cause
        # is reserved for the finalist gauntlet (a rotation survivor that fails the
        # three-seed majority verdict) and is named by the run tool, not the loop.
        elite_sigs = {g.signature() for g, _, _ in elite_ranked}
        streaks = {g.signature(): r.streak_kills for g, r, _ in judged}
        for g, r, f in judged:
            sig = g.signature()
            if sig in elite_sigs:
                continue  # survives this generation
            if not f.ranked:
                cause = "tournament_floor"
            elif streaks.get(sig, 0) > 0:
                cause = "early_stop"
            else:
                cause = "apoptosis"
            per_gen_deaths[cause] = per_gen_deaths.get(cause, 0) + 1
            entry = {
                "signature": sig, "family": g.family, "generation": gen,
                "cause": cause, "detail": f.reason,
                "adversarial_seed": int(adv_seed),  # R42 — the face it faced
            }
            all_deaths.append(entry)
            if config.death_ledger_path:
                death_ledger.record(
                    sig, g.family, gen, cause, detail=f.reason,
                    path=config.death_ledger_path,
                )

        best = fine[0] if fine else {
            "signature": "", "family": "", "wilson_lb": 0.0, "net_r": 0.0,
        }
        generations.append(
            GenerationResult(
                generation=gen,
                evaluated=evaluated,
                ranked=len(ranked_pairs),
                unranked=unranked,
                best_signature=best["signature"],
                best_family=best["family"],
                best_wilson_lb=best["wilson_lb"],
                best_net_r=best["net_r"],
                deaths=per_gen_deaths,
                trials=trials,
                adversarial_seed=int(adv_seed),  # R42 — rotation record
            )
        )

        if partial:
            break

        # Breed the next generation from the elite, then vault-immigrate.
        elites = [g for g, _, _ in elite_ranked]
        n_children = max(0, config.population - len(elites))
        children = _breed_children(elites, n_children, config, rng)
        population = _normalize(list(elites) + children, config.population, rng,
                                ensemble_quota=config.ensemble_quota)
        population = _apply_vault(population, config, rng)
        population_hashes[str(gen + 1)] = _population_hash(population)

        if config.checkpoint_path:
            _save_checkpoint(
                config.checkpoint_path,
                {
                    "config_hash": config_hash,
                    "seed": config.seed,
                    "generation": gen,
                    "population": [g.to_dict() for g in population],
                    "rng_state": rng.bit_generator.state,
                    "trials": trials,
                    "generations": [asdict(g) for g in generations],
                    "population_hashes": population_hashes,
                    "deaths": all_deaths,
                    "schedule_pos": gen + 1,  # R42 — the rotation position after gen
                    "arm_trials": arm_trials,  # R55 — per-arm tallies
                    "arm_ranked": arm_ranked,
                },
            )

    # Final leaderboard: the surviving population, ranked on the ADVERSARIAL world
    # (R39/R43) at the FINAL rotation seed (R42) — the face of the last round.
    final_seed = schedule[(config.generations - 1) % len(schedule)] if (dual and schedule) else 0
    final_adversarial = _wounded(final_seed) if dual else (None, None)
    final_judged: list[tuple[StrategyGenome, object, object]] = []
    for genome in population or []:
        if dual:
            adv_rep = evaluate_adversarial(
                genome, final_adversarial[0], _adversarial_cfg(eval_cfg, rams_cfg),
                statarb_z_by_pair_adv=(
                    statarb.statarb_z_map(genome, final_adversarial[0])
                    if genome.family == "cointegration_statarb" else None),
                rams_config=(rams_cfg if eval_cfg.cost_model is not None else None),
                vote_cache=vote_cache, world_seed=int(final_seed),
            )
            result, adv_rep = _judge_one(
                genome, adv_rep, final_seed, final_adversarial[0], final_adversarial[1])
        else:
            clean_rep = _eval_clean(genome, train_frames, eval_cfg, vote_cache)
            result, adv_rep = _judge_one(genome, clean_rep, final_seed)
        final_judged.append((genome, adv_rep, result))
    final_ranked = [(g, r, f) for (g, r, f) in final_judged if f.ranked]
    final_ranked.sort(key=lambda t: t[2].key())

    # R43 — clean evaluation for the final ELITE set alone (diagnostics only; the
    # other surviving rows stay adversarial-only).
    final_clean: dict[str, object] = {}
    if dual and config.clean_elite_eval:
        for g, _r, _f in final_ranked[: config.elite]:
            final_clean[g.signature()] = _eval_clean(g, train_frames, eval_cfg, vote_cache)

    def _row(g, f) -> dict:
        sig = g.signature()
        row = {
            "signature": sig, "family": g.family,
            "kinship": cost_report.kinship_key(g),  # R23 coarse lineage id
            "wilson_lb": f.wilson_lb, "win_rate": f.win_rate, "net_r": f.net_r,
            "gross_r": f.gross_r,  # DIAGNOSTIC ONLY (R17)
            "max_drawdown_r": f.max_drawdown_r, "trades": f.trades,
            "autopsy_resilience": f.autopsy_resilience,  # R39 tiebreak
            # THE FULL FEEDING — the fields the Letter's table reads, carried on every
            # row so the report → statistics → Letter chain never drops a measured
            # number (profit factor, the per-trade expectancy, the realized DD).
            "profit_factor": f.profit_factor,
            "expectancy_r": (round(f.net_r / f.trades, 4) if f.trades else None),
            "measured_dd_r": f.max_drawdown_r,
            "gross_profit_r": f.gross_profit_r,
            "gross_loss_r": f.gross_loss_r,
            "wins": f.wins,
            "losses": max(0, f.trades - f.wins),
            # R85 — THE GROSS-TO-FRICTION GATE's own arithmetic, carried per row so
            # the Letter's "Frizione media (x)" reads the REAL paid multiple (the
            # gross edge per unit of friction), never a fabricated number.
            "friction_breakdown": law.friction_breakdown(f.gross_r, f.net_r),
            # The reward:risk the genome actually TRADES (the law's floor is 2.5).
            # Carried so the bulletin's RR can read a real R:R, never net-R/trade.
            "target_rr": getattr(g, "target_rr", None),
        }
        if dual:
            clean = final_clean.get(sig)
            if clean is not None:
                cm = clean.metrics
                row.update({
                    "clean_wilson_lb": fitness.wilson_lower_bound(cm.wins, cm.trades),
                    "clean_net_r": float(cm.net_r),
                    "clean_win_rate": float(cm.win_rate),
                    "clean_trades": int(cm.trades),
                    "diagnostic_clean": True,
                })
        return row

    # R21 — NEGATIVE-NET EXILE. The bar was always the gate; now it is also the
    # floor. Any ranked genome whose FINAL net_r <= 0 is exiled from the
    # leaderboard into the death ledger (cause "friction"), regardless of rank.
    # The leaderboard holds only net-positive genomes.
    alive = [(g, r, f) for (g, r, f) in final_ranked if f.net_r > 0.0]
    exiled = [(g, r, f) for (g, r, f) in final_ranked if f.net_r <= 0.0]
    for g, r, f in exiled:
        entry = {
            "signature": g.signature(), "family": g.family, "generation": -1,
            "cause": "friction",
            "detail": f"final net_r {f.net_r:.4f} <= 0 (R21 exile)",
        }
        all_deaths.append(entry)
        if config.death_ledger_path:
            death_ledger.record(
                g.signature(), g.family, -1, "friction",
                detail=entry["detail"], path=config.death_ledger_path,
            )

    leaderboard = [_row(g, f) for g, _, f in alive[: config.top_n_test]]
    # The full surviving population, for the R19 era/vs-era comparison.
    final_population = [_row(g, f) for g, _, f in final_ranked]
    # The surviving DNA, in the same order — the pyramid musters Soldiers from it.
    final_population_genomes = [g.to_dict() for g, _, _ in final_ranked]
    # R21 — the NET-POSITIVE survivors alone: the only genomes a rank may hold.
    survivor_population = [_row(g, f) for g, _, f in alive]
    survivor_genomes = [g.to_dict() for g, _, _ in alive]

    # Walk-forward: the train heroes face the test slice.
    test_leaderboard: list[dict] = []
    exposure: list[OutfitExposure] = []
    if test_frames:
        bar = fitness.promotion_bar(trials)
        # R21: the walk-forward crown goes to the NET-POSITIVE survivors only. A
        # genome the friction exiled cannot be a champion, however high it ranked.
        for (g, train_rep, train_fit) in alive[: config.top_n_test]:
            test_rep = _evaluate_in_universe(g, test_frames, eval_cfg)
            test_fit = fitness.fitness(test_rep.metrics, config.min_trades)
            test_leaderboard.append(
                {
                    "signature": g.signature(), "family": g.family,
                    "test_wilson_lb": test_fit.wilson_lb, "test_net_r": test_fit.net_r,
                    "test_gross_r": test_fit.gross_r,  # DIAGNOSTIC ONLY (R17)
                    "test_trades": test_fit.trades, "test_ranked": test_fit.ranked,
                }
            )
            below = test_fit.wilson_lb < bar
            negative = test_fit.net_r < 0
            if below or negative:
                reasons = []
                if below:
                    reasons.append(f"test LB {test_fit.wilson_lb:.3f} < bar {bar:.3f}")
                if negative:
                    reasons.append(f"test net_r {test_fit.net_r:.2f} < 0")
                exposure.append(
                    OutfitExposure(
                        signature=g.signature(), family=g.family,
                        train_wilson_lb=train_fit.wilson_lb, train_net_r=train_fit.net_r,
                        train_trades=train_fit.trades,
                        test_wilson_lb=test_fit.wilson_lb, test_net_r=test_fit.net_r,
                        test_trades=test_fit.trades,
                        reason="; ".join(reasons),
                    )
                )

    # R55/R58 — elite/random ensemble vs single survivors in the final ranked
    # population. The final pass re-judges the survivors, so its votes land in the
    # same R59 cache (a member shared with the in-generation pass is already warm).
    arm_survivors = {a: 0 for a in SURVIVAL_ARMS}
    for g, _r, f in final_ranked:
        if f.net_r > 0.0:  # R21 — only net-positive rows are true survivors
            arm_survivors[survival_arm(g)] += 1
    ensemble_survival = ensemble_survival_table(
        arm_trials, arm_survivors, ranked_by_arm=arm_ranked)

    return TournamentResult(
        config_hash=config_hash,
        config=asdict(config),
        seed=config.seed,
        generations=generations,
        leaderboard=leaderboard,
        test_leaderboard=test_leaderboard,
        outfit_exposure=exposure,
        death_summary=death_ledger.summarize(all_deaths),
        final_population=final_population,
        final_population_genomes=final_population_genomes,
        survivor_population=survivor_population,
        survivor_genomes=survivor_genomes,
        trials=trials,
        partial=partial,
        wallclock_seconds=clock() - start,
        population_hashes=population_hashes,
        stopped_reason=stopped_reason,
        cost_model_hash=active_hash,
        diagnostic=not config.use_costs,
        dual_selection=dual,
        dual_selection_digest=(DUAL_SELECTION_DIGEST if dual else ""),
        ensemble_survival=ensemble_survival,
        ensemble_quota=float(config.ensemble_quota),
        elite_soup=bool(config.elite_soup),
        vote_cache_stats=(vote_cache.stats() if vote_cache is not None else {}),
    )
