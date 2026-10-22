"""THE FACTORY ORCHESTRATOR — the twelve levers, wired into one search.

This is the scale layer's reproductive loop. It is a NEW module (Scar #4: new
behaviour gets new tests; no prior test is touched). It does not replace the
sealed dual tournament used for the crown; it is the factory that produces and
breeds candidates at scale, and it emits EVERY lever's number so the audit can
show each one working:

* R69 staircase   — entered/passed per rung (seconds, not minutes, for the dead);
* R70 result mem  — reuse ratio (hits / total);
* R71a EDA memory — per-family fitted distributions (the dead teach);
* R71b CMA-ES     — refinement delta per finalist;
* R71c polish     — Lamarckian gain written back per newborn;
* R72 entropy     — per-generation entropy + adaptive mutation rate;
* R73 realms      — occupied realms + the kings census;
* R66 ledger      — one honest record per job;
* R67 slices      — the deterministic slice-set (parallel-safe);
* R68 islands     — a champion migration export;
* R91 pantry      — the island's champions re-enter generation 0;
* R99 diaspora    — the OTHER islands' best feed this island too (one gene pool);
* R100 probation  — every champion is re-measured on the most recent window
                     before the pantry remembers it (labels, never erasures);
* R103 atlas      — the behavioral atlas (quality-diversity): 36 measured
                     niches keep their own elite, and the map's best feed
                     generation 0 beside the pantry (diversity is preparation
                     for the regime that has not arrived);
* R104 cognition  — the Director's faculties as instruments: slice
                     agreement (independence of evidence) measured for every
                     champion, and the calibration ledger grading the
                     probation's own predictions (a label is a prediction).

Fail-closed throughout (Scar #1): no ATR/rate is invented; a genome with no
results is unranked, never promoted. Deterministic under ``(config.seed,
config.slice_set)``.

Pure at import; no I/O. Build Mode: a bounded batch, no server, no loop beyond
population x generations.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np

from app.core.pairs import PAIR_PIP
from app.quant import breeding
from app.quant import costs
from app.quant import evaluator as ev
from app.quant import fitness as fitness_mod
from app.quant import tribunal
from app.quant.genome import GENE_BOUNDS, GENE_BOUNDS_BY_NAME, StrategyGenome
from app.factory import dna as dna_mod
from app.factory import eda as eda_mod
from app.factory import entropy as entropy_mod
from app.factory import islands as islands_mod
from app.factory import polish as polish_mod
from app.factory import qd as qd_mod
from app.factory import realms as realms_mod
from app.factory import result_memory as rm_mod
from app.factory import slices as slices_mod
from app.factory import staircase as staircase_mod
from app.factory import zcognition as zcog_mod
from app.factory import genealogist as gene_mod

__all__ = ["FactoryConfig", "run_factory"]


@dataclass(frozen=True)
class FactoryConfig:
    """Everything a factory run needs to be reproducible and bounded."""

    pairs: tuple[str, ...]
    population: int = 240
    generations: int = 3
    elite: int = 40
    min_trades: int = 30
    seed: int = 0
    rotate_seed: bool = False
    ensemble_quota: float = 0.25
    n_slices: int = 3
    slice_salt: str = ""
    polish: bool = True
    cma: bool = True
    cma_generations: int = 20
    cma_population: int = 12
    staircase: bool = True
    # The stairstep's cheap pair for round 1 (must be in the universe).
    screen_pair: str = ""
    island: str = "heart"
    # THE DRAGON'S DIRECTED MUTATIONS (the dominant intelligence guides evolution):
    # a tuple of ``{family, gene, direction, reason}`` hypotheses that nudge the
    # surviving genomes toward a chosen bound. Empty -> blind evolution as before.
    directed: tuple = ()
    # DEBT-060 — THE REGIME GATING (the Watchtower's reconfiguration, honoured).
    # A map ``pair -> {"paused": [family_group,...], "active": [family_group,...]}``
    # read from the civilization state's ``regime.gating``. A family in a pair's
    # PAUSED set loses its population slots on that pair; a family in the ACTIVE set
    # is PRIORITISED. Empty (or a pair with no entry) -> no gating, as before, so the
    # factory is byte-identical when the Watchtower has not reconfigured anything.
    regime_gating: dict = field(default_factory=dict)
    # JUMP 7 — the multi-layer quota: the share of the population that draws a
    # coordination stack (strategic D1 + tactical H4 above the execution M15).
    layers_quota: float = 0.0
    # R96 — THE NINE SEATS: how many distinct-realm champions each shift sets
    # aside for the pantry and the migration. Fewer occupied realms yield
    # fewer champions (empty seats stay empty; no placeholder, R20/R21 spirit).
    champion_seats: int = 9
    # R97 — THE LIVING FUNNEL: the share of the pool round one lets THROUGH to
    # the full judgement (the top graded ``keep`` bodies; life first, merit in
    # the full rounds). 1.0 = everything passes round one. Measured need: the
    # absolute round-one bar (30+ trades on the cheap pair AND gross >= 3x
    # friction) killed 240/240 random bodies for days -- extinction, not
    # selection; an extinct pool cannot breed.
    screen_survival: float = 0.6
    # R103 — THE BEHAVIORAL ATLAS: quality-diversity beside the pantry. The
    # atlas offers only RANKED bodies (measured behavior, never couches),
    # keeps one elite per behavioral niche (activity x horizon x direction),
    # and injects its best into generation 0 (``qd_injection`` of the
    # population, capped, dedup'd, gated like every other door).
    qd: bool = True
    qd_injection: float = 0.125
    qd_top: int = 60
    # R104 — THE COGNITION INSTRUMENTS: slice agreement for every champion
    # and the calibration ledger grading the probation's own predictions.
    calibration: bool = True
    # R106 — THE COUCH KING'S TERM LIMIT: a champion that couches on the recent
    # window for ``couch_bench_streak`` consecutive shifts has earned a BENCH
    # rest -- it is not injected (its slots go to fresh hunters), its genome is
    # PRESERVED in the pantry's bench with re-trial rights (a cooldown that
    # halves-free over shifts, doubling each failed re-trial, capped). The
    # pantry keeps every label (R100: labels, never erasures); the door simply
    # stops crowning a king that does not hunt in the reigning regime.
    couch_bench_streak: int = 3
    couch_cooldown_base: int = 4
    couch_cooldown_cap: int = 24
    bench_max: int = 12

    def signature(self) -> str:
        blob = json.dumps(
            {
                "pairs": sorted(self.pairs), "population": self.population,
                "generations": self.generations, "elite": self.elite,
                "min_trades": self.min_trades, "seed": self.seed,
                "ensemble_quota": self.ensemble_quota, "n_slices": self.n_slices,
                "slice_salt": self.slice_salt, "polish": self.polish,
                "cma": self.cma, "staircase": self.staircase,
                "layers_quota": self.layers_quota,
                "champion_seats": self.champion_seats,
                "screen_survival": self.screen_survival,
                "qd": self.qd,
                "qd_injection": self.qd_injection,
                "qd_top": self.qd_top,
                "calibration": self.calibration,
                "couch_bench_streak": self.couch_bench_streak,
                "couch_cooldown_base": self.couch_cooldown_base,
                "couch_cooldown_cap": self.couch_cooldown_cap,
                "bench_max": self.bench_max,
                "regime_gating": self.regime_gating,
            },
            sort_keys=True, default=str,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


class _Evaluator:
    """A result-memory-backed evaluator (R70) over a pair universe."""

    def __init__(self, universe, min_trades, memory: rm_mod.ResultMemory,
                 world_seed: int = 0):
        self.universe = universe
        self.min_trades = int(min_trades)
        self.memory = memory
        self.world_seed = int(world_seed)
        self.cfg = ev.EvaluationConfig(cost_model=costs.SELECTION_COST_MODEL)

    def report(self, genome: StrategyGenome, pairs):
        sub = {p: self.universe[p] for p in pairs if p in self.universe}
        if not sub:
            raise ValueError("no pairs to evaluate — fail-closed")
        slice_id = ",".join(sorted(sub))
        key = rm_mod.result_key(genome.signature(), self.world_seed, slice_id)

        def compute():
            return ev.evaluate(genome, sub, self.cfg, world_seed=self.world_seed)

        return self.memory.get_or_compute(key, compute)

    def fit(self, genome: StrategyGenome, pairs):
        rep = self.report(genome, pairs)
        return fitness_mod.fitness(rep.metrics, self.min_trades)


def _rank_key(fit) -> tuple[float, float]:
    return (float(fit.wilson_lb), float(fit.net_r))


def _recency_rank(entry: dict) -> tuple[int, tuple[int, float], float]:
    """R100+R107 -- the order a pantry champion re-enters generation 0 in.

    A champion CONFIRMED on the recent window (the closest thing to tomorrow)
    rides first; a probationer follows; an unjudged entry (an old pantry, a
    hand-made one) rides last, never refused -- the label is read from the
    pantry, never assumed. R107 -- WITHIN each class the INDEPENDENCE of the
    evidence now orders the door: a body that wins on every deterministic
    slice rides before an equal Wilson that rode one (Faculty 4: belief
    follows evidence, and independence is part of the evidence); an
    unmeasured agreement rides last within its class, honestly, and the
    measured wilson breaks what agreement leaves tied.
    """
    verdict = str((entry.get("recency") or {}).get("verdict") or "")
    order = {"confirmed": 0, "probation": 1}.get(verdict, 2)
    try:
        wilson = float(entry.get("wilson_lb") or 0.0)
    except (TypeError, ValueError):
        wilson = 0.0
    if not wilson == wilson:  # NaN guard: an unmeasured score rides last
        wilson, order = 0.0, 2
    sa = entry.get("slice_agreement")
    try:
        sa_val = float(sa)
    except (TypeError, ValueError):
        sa_val = float("nan")
    if sa_val == sa_val:  # measured independence leads; unmeasured trails
        sa_key = (0, -sa_val)
    else:
        sa_key = (1, 0.0)
    return (order, sa_key, -wilson)


def _couch_backoff(streak: int, config: "FactoryConfig") -> int:
    """R106 -- the bench's cooldown: exponential in the streak, capped.

    streak 3 -> base (4 shifts); each couch beyond the trigger doubles it
    (8, 16, ...), the cap bounds the exile so a king is never forgotten
    forever. The numbers are policy, not physics: they live in the config,
    sealed by its signature.
    """
    trigger = max(1, int(config.couch_bench_streak))
    n = max(0, int(streak) - trigger)
    base = max(1, int(config.couch_cooldown_base))
    return int(min(base * (2 ** n), max(base, int(config.couch_cooldown_cap))))


def _evolve_bench(old_bench: list, champions: list,
                  config: "FactoryConfig") -> list:
    """R106 -- the bench's honest bookkeeping between shifts.

    * an OLD bench king that is among tonight's champions won its re-trial
      (or was re-crowned): it leaves the bench, a full citizen again;
    * an old king still resting ticks its cooldown DOWN one shift;
    * an old king whose re-trial ran (cooldown hit 0 last shift) and did NOT
      make tonight's champions couches again: its streak grows and the
      doubled cooldown is honest arithmetic on that streak;
    * tonight's chronic couches (streak >= trigger) join the bench with
      their genome preserved -- memory, never exile;
    * the bench is capped (the deepest streaks ride; the rest are spoken in
      the report's overflow count, never silently erased).
    """
    out: list[dict] = []
    tonight = {str(c.get("signature") or "") for c in champions}
    for b in (old_bench or []):
        if not isinstance(b, dict):
            continue
        sig = str(b.get("signature") or "")
        if sig and sig in tonight:
            continue  # it hunted again: the bench closes its file
        cd = int(b.get("cooldown") or 0)
        if cd > 0:
            out.append({**b, "cooldown": cd - 1})
        else:
            streak = int(b.get("couch_streak") or 0) + 1
            out.append({**b, "couch_streak": streak,
                        "cooldown": _couch_backoff(streak, config)})
    for c in champions:
        rec = c.get("recency") or {}
        if str(rec.get("verdict") or "") != "couch":
            continue
        streak = int(rec.get("couch_streak") or 0)
        if streak < max(1, int(config.couch_bench_streak)):
            continue
        sig = str(c.get("signature") or "")
        if any(str(x.get("signature") or "") == sig for x in out):
            continue
        try:
            genome = StrategyGenome.from_dict(c).to_dict()
        except Exception:
            continue  # a body that cannot be read cannot be remembered
        out.append({"genome": genome, "family": c.get("family"),
                    "signature": sig, "wilson_lb": c.get("wilson_lb"),
                    "net_r": c.get("net_r"), "couch_streak": streak,
                    "cooldown": _couch_backoff(streak, config)})
    out.sort(key=lambda b: -int(b.get("couch_streak") or 0))
    return out[:max(0, int(config.bench_max))]


def _make_staircase(pairs, screen_pair, evaluator: _Evaluator):
    """Build the R69 evaluators. Round 1 is the cheap pair; round 3 is all pairs."""
    cheap = (screen_pair,) if screen_pair else (sorted(pairs)[0],)
    full = tuple(sorted(pairs))

    def screen(genome, spec):
        return evaluator.fit(genome, cheap).ranked

    def era(genome, spec):
        return evaluator.fit(genome, full).ranked

    def gauntlet(genome, spec):
        return evaluator.fit(genome, full).ranked

    return {"screen": screen, "era": era, "gauntlet": gauntlet}


def _directed_index(directed) -> dict:
    """Map ``(family, gene) -> direction`` from the Dragon's hypotheses (last wins)."""
    idx: dict = {}
    for h in directed or ():
        if not isinstance(h, dict):
            continue
        fam = str(h.get("family") or "").strip()
        gene = str(h.get("gene") or "").strip()
        direction = str(h.get("direction") or "").strip().lower()
        if fam and gene in GENE_BOUNDS_BY_NAME and direction in ("up", "down"):
            idx[(fam, gene)] = direction
    return idx


def _directed_genes(genome: StrategyGenome, idx: dict):
    """The genome's genes nudged per the Dragon's directed hypotheses.

    A nudge moves the gene 30% of the way from its current value toward the bound
    named by ``direction`` (``up`` -> high, ``down`` -> low), clamped INSIDE the
    family's effective bound -- a directed mutation is a step in a chosen
    direction, never a teleport, and the law is never broken. Returns ``(genes,
    n)`` where ``n`` is the number of genes actually nudged; an absent directive
    yields ``n=0`` (the caller leaves the genome untouched, honest).
    """
    fam = genome.family
    genes = {b.name: getattr(genome, b.name) for b in GENE_BOUNDS}
    n = 0
    for (hfam, gene), direction in idx.items():
        if hfam != fam:
            continue
        low, high, is_int = tribunal.effective_bounds(fam, gene)
        cur = float(genes[gene])
        target = high if direction == "up" else low
        moved = cur + 0.30 * (target - cur)
        moved = min(max(moved, low), high)
        genes[gene] = int(round(moved)) if is_int else float(moved)
        n += 1
    return genes, n


# --- DEBT-060: the factory HONOURS the regime gating -----------------------

# The soft boost for an ACTIVE family group: with this probability a draw outside the
# active set is redrawn (a priority, not a hard block -- a paused group is the only
# hard exclusion). Named so the report and the draw can never drift apart.
ACTIVE_BOOST = 0.5


def _group_of(family: str) -> str:
    """The coarse family group a genome's family belongs to (the gating's key).

    Reuses ``app.factory.realms`` (single source of truth, Scar #2): the
    Watchtower's gating names FAMILY GROUPS (trend/momentum/...), the same partition
    the realm census uses. An unknown family reports ``unknown`` (never a guess).
    """
    return realms_mod.family_group(str(family))


def _paused_groups(config: FactoryConfig) -> set[str]:
    """The family groups PAUSED across every gated pair (the union)."""
    out: set[str] = set()
    for _pair, g in (config.regime_gating or {}).items():
        for grp in ((g or {}).get("paused") or []):
            out.add(str(grp))
    return out


def _active_groups(config: FactoryConfig) -> set[str]:
    """The family groups BOOSTED across every gated pair (the union)."""
    out: set[str] = set()
    for _pair, g in (config.regime_gating or {}).items():
        for grp in ((g or {}).get("active") or []):
            out.add(str(grp))
    return out


def _draw_gated(config: FactoryConfig, rng, *, concrete: bool):
    """Draw a genome whose family respects the regime gating (DEBT-060).

    Paused groups are REJECTED and redrawn (bounded retries, then a best-effort draw
    -- never an infinite loop); active groups are drawn FIRST with probability
    ``ACTIVE_BOOST``. Honest: with no gating this is exactly the ungated draw, so the
    classic path is byte-identical (the retry never fires).
    """
    paused = _paused_groups(config)
    active = _active_groups(config)
    if not paused and not active:
        return breeding.random_genome(
            rng, concrete=concrete, ensemble_quota=config.ensemble_quota,
            layers_quota=config.layers_quota)
    for _ in range(20):
        g = breeding.random_genome(
            rng, concrete=concrete, ensemble_quota=config.ensemble_quota,
            layers_quota=config.layers_quota)
        grp = _group_of(g.family)
        if grp in paused:
            continue  # paused on some pair -- redraw
        if active and grp not in active and rng.random() < ACTIVE_BOOST:
            continue  # prioritise active groups (a soft boost, not a hard block)
        return g
    return breeding.random_genome(
        rng, concrete=concrete, ensemble_quota=config.ensemble_quota,
        layers_quota=config.layers_quota)


def _gating_block(config: FactoryConfig, population) -> dict:
    """The honest gating report: paused/active groups + the population's respect."""
    paused = _paused_groups(config)
    active = _active_groups(config)
    if not config.regime_gating:
        return {"applied": False, "paused": [], "active": [],
                "n_paused_offered": 0, "n_active_offered": 0, "pairs": 0,
                "reading": "nessun gating di regime (la torre non ha riconfigurato)"}
    offered = [g for g in population]
    n_paused = sum(1 for g in offered if _group_of(g.family) in paused)
    n_active = sum(1 for g in offered if _group_of(g.family) in active)
    return {
        "applied": True, "paused": sorted(paused), "active": sorted(active),
        "pairs": len(config.regime_gating),
        "n_paused_offered": n_paused, "n_active_offered": n_active,
        "n_population": len(offered),
        "reading": (f"il gating del regime e' onorato: {n_paused} genomi di gruppi "
                    f"in pausa su {len(offered)} (gruppi attivi prioritizzati: "
                    f"{sorted(active)})"),
    }


def _live_weather(*, path: str = "hyperfeed.json",
                   now_epoch: float | None = None) -> dict:
    """R115 -- IL METEO: the live sky this shift evolved under.

    The factory evolves on taped history; from today it also RECORDS the
    weather the live market wore while it worked (the wire's snapshot, read
    honestly): the FX majors' median measured motion, the fear gauge's own
    motion, and a coarse label from FIXED, DECLARED thresholds -- never a
    learned guess. The weather is OBSERVED, never obeyed: no selection rule
    reads it yet (that is a future law, and it will need days of this
    evidence first). A sleeping wire (a CI runner with a stale committed
    snapshot) is declared sleeping -- the meteo never invents a sky.
    """
    # The declared thresholds (pips/min median across the FX majors that
    # have a measured motion; bp/min for the BTC fear gauge).
    wind_min, storm_min = 0.40, 1.50
    quiet_max, tense_max = 3.0, 10.0
    try:
        snap = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        snap = None
    if not isinstance(snap, dict) or not isinstance(snap.get("ts"), (int, float)):
        return {"state": "absent", "label": None,
                "reading": "il filo non ha scritto: nessun cielo dichiarato"}
    now = float(now_epoch if now_epoch is not None else time.time())
    age_s = max(0.0, now - float(snap["ts"]))
    alive = float(snap.get("alive_s") or 900)
    if age_s > alive:
        return {"state": "sleeping", "snapshot_age_s": round(age_s, 1),
                "label": None,
                "reading": f"il filo dorme ({age_s/60.0:.0f} min): meteo sospeso"}
    syms = snap.get("symbols") or {}
    fx_motions = []
    for s in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"):
        m = (syms.get(s) or {}).get("motion")
        if isinstance(m, dict) and isinstance(m.get("displacement_per_min"), (int, float)):
            fx_motions.append(float(m["displacement_per_min"]))
    fx_med = (sorted(fx_motions)[len(fx_motions) // 2]
              if fx_motions else None)
    label = None
    if fx_med is not None:
        label = ("calm" if fx_med < wind_min else
                 "storm" if fx_med >= storm_min else "wind")
    btc_m = ((syms.get("BTCUSDT") or {}).get("motion") or {}).get("displacement_per_min")
    fear = None
    if isinstance(btc_m, (int, float)):
        fear = {"btc_bp_per_min": round(float(btc_m), 3),
                "label": ("quiet" if btc_m < quiet_max else
                          "panicking" if btc_m >= tense_max else "tense")}
    counts = snap.get("counts") or {}
    return {
        "state": "live", "snapshot_age_s": round(age_s, 1),
        "fx_median_pips_per_min": (round(fx_med, 3) if fx_med is not None else None),
        "label": label,
        "fear": fear,
        "symbols_moving": counts.get("symbols_moving"),
        "cross_updates": counts.get("cross_updates"),
        "thresholds": {"fx_wind_min": wind_min, "fx_storm_min": storm_min,
                        "fear_tense_max": tense_max},
        "reading": (f"meteo: {label} "
                    f"(FX mediana {fx_med:.2f} pip/min su {len(fx_motions)} misurati)"
                    if fx_med is not None else
                    "meteo: nessun major con moto misurato (filo giovane)"),
    }


def run_factory(universe, config: FactoryConfig, *,
                clock=time.monotonic, probation_universe=None) -> dict:
    """Run the factory's bounded reproductive loop and return the honest report.

    ``probation_universe`` (R100, optional) is a SECOND pair->Frames map over
    the most recent window: every pantry champion is re-measured on it and
    labelled (confirmed / probation / couch / unmeasured) -- the label rides
    with the champion into the pantry and orders its next re-entry. ``None``
    means no probation this shift (honest ``unmeasured``, never a guess).
    """
    start = clock()
    pairs = tuple(sorted(p for p in config.pairs if p in universe))
    if not pairs:
        raise ValueError("no pairs from the config are in the universe (fail-closed)")
    # R92 -- THE ROTATING SEED: a fixed seed redrew the SAME evolution every
    # shift (four identical ledger rows during the flatline). When the config
    # opts in, the seed rotates with the ledger's length: deterministic PER
    # SHIFT (each shift is exactly reproducible from its recorded seed, in the
    # ledger note), never repeated across shifts.
    shift_seed = config.seed
    if config.rotate_seed:
        try:
            _ll = Path("factory_ledger.jsonl")
            _n = sum(1 for _ in _ll.open()) if _ll.exists() else 0
        except OSError:
            _n = 0
        shift_seed = (config.seed + 7919 * (_n + 1)) % (1 << 30)
    rng = np.random.default_rng(shift_seed)
    if not (0.0 < float(config.screen_survival) <= 1.0):
        raise ValueError(
            "screen_survival must be in (0, 1] — the funnel keeps at least one "
            "living body and never more than the whole pool (fail-closed)")
    memory = rm_mod.ResultMemory()
    evaluator = _Evaluator(universe, config.min_trades, memory)
    eda_mem = eda_mod.GeneMemory()
    staircase = _make_staircase(pairs, config.screen_pair, evaluator)

    slice_set = slices_mod.make_slices(
        pairs, min(config.n_slices, len(pairs)), shift_seed, config.slice_salt)

    cheap_pairs = (config.screen_pair,) if config.screen_pair else (pairs[0],)

    def _new_genome():
        return _draw_gated(config, rng, concrete=False)

    # --- generation 0: random + Lamarckian polish (R71c) -------------------
    population: list[StrategyGenome] = []
    # R126 -- THE GENEALOGIST'S BLOOD BOOK: the island's persistent memory of
    # parentage.  Every entry into generation 0 (pantry, bench, diaspora,
    # atlas, random) is SIGHTED in the book: a known signature carries its
    # blood forward, a first sighting is a founder (ancestry is never
    # invented for the past).  The book is pruned on save to the living --
    # memory, not a cemetery.  Fail-open: a torn book is a fresh start.
    _blood_path = Path(f"factory_blood_{config.island}.json")
    _book = gene_mod.BloodBook.load(_blood_path, island=config.island)
    _births: list[gene_mod.Birth] = []
    _brake = {"applied": False, "sibling_mates_avoided": 0,
              "immigrants": 0, "reason": "il sangue era diversificato"}
    # R143 -- THE GENE FLOOD's SEED: the one-blood streak is a PERSISTENT blood
    # measurement.  The previous run's genealogy artifact carries where the
    # collapse stood; a torn, absent, or pre-flood artifact is a fresh streak
    # (fail-open: an invented collapse would flood on a lie, so it never is).
    # The measured collapse (every island one-blood, every night) does not
    # restart with every run -- and neither does its cure's escalation.
    _one_blood_streak = 0
    try:
        _prev_gene = json.loads(
            Path(f"factory_genealogy_{config.island}.json").read_text())
        _one_blood_streak = int(_prev_gene.get("brake_streak") or 0)
    except Exception:
        _one_blood_streak = 0
    _one_blood_streak = max(0, _one_blood_streak)

    def _flood_families(config) -> list[str]:
        """R143 -- the flood's table: every family the weighted draw itself
        would consider, minus the groups the regime gating has paused.  A
        founder the tournament would not judge is not a founder, it is noise.
        No config gating -> the full eligible table (the honest default)."""
        try:
            paused = _paused_groups(config)
        except Exception:
            paused = set()
        return [f for f in breeding.eligible_families()
                if _group_of(f) not in (paused or set())]

    def _sight(g, op: str = "seed", parents: tuple = ()) -> None:
        sig = str(g.signature())
        if not _book.is_known(sig):
            if parents:
                _book.record_child(sig, parents)
            else:
                _book.record_founder(sig)
        _births.append(gene_mod.Birth(child=sig, op=op, parents=parents))
    # R91 -- THE PERSISTENT CHAMPIONS: this island's previous champions re-enter
    # generation 0 (re-evaluated on TONIGHT's slices -- the result memory makes
    # their re-scoring nearly free). Evolution ACCUMULATES instead of restarting
    # blind every shift (the identical-ledger flatline fix). Fail-open: a
    # missing/corrupt file simply means a fresh random start, as before.
    champions_refused = 0
    gated_own = 0
    # R106 -- the bench's honest counters (spoken in every report)
    couch_benched = 0
    bench_retrials = 0
    bench_waiting = 0
    couch_gated = 0
    _couch_prior: dict[str, int] = {}
    _bench_old: list = []
    # DEBT-060 -- THE WATCHTOWER'S WORD AT THE INJECTION DOOR TOO: a family the
    # state has PAUSED loses its slots, and the pantry's memory may not reopen
    # a closed door -- not this island's own champions (R91), not a foreigner's
    # best (R99). Refused and counted, never swallowed: the gating is the
    # living state's word, and the living state wins (Law 9).
    _paused = _paused_groups(config)

    def _gated_out(entry) -> bool:
        group = realms_mod.family_group(str(entry.get("family") or ""))
        return group in _paused

    try:
        _cf = Path(f"factory_champions_{config.island}.json")
        _mig = json.loads(_cf.read_text()) if _cf.exists() else {}
        _pool = (_mig.get("migrants") or _mig.get("champions") or [])
        _bench_old = _mig.get("bench") or []
        if not isinstance(_bench_old, list):
            _bench_old = []
        # THE DIRECTOR'S DNA (Law 3) -- the honest injection: a champion must
        # CARRY A MEASURE to re-enter generation 0. A measured 0.0 is honest
        # (re-scored, under the rank floor); an absent/NaN score is a ghost --
        # refused and counted, never silently dropped.
        _pool, champions_refused = dna_mod.honest_champions(_pool)
        _ungated = []
        for m in _pool:
            if _gated_out(m):
                gated_own += 1
                continue
            _ungated.append(m)
        _pool = _ungated
        # R100 -- THE RECENCY PROBATION'S ORDER: a champion confirmed on the
        # recent window re-enters FIRST (the label is read, never assumed; an
        # unjudged pantry ranks by measure alone, honest and backward-safe).
        # R107 -- within each class the INDEPENDENCE of the evidence orders
        # the door (slice agreement before Wilson; unmeasured trails).
        _pool.sort(key=_recency_rank)
        # R106 -- THE COUCH KING'S TERM LIMIT: a chronic couch (a king that
        # has couches on the recent window for `couch_bench_streak`
        # consecutive shifts) sits this shift OUT -- its slot goes to a fresh
        # hunter. The pantry's bench keeps its genome and its streak; a
        # benched king earns a re-trial when its cooldown expires (below).
        # Honest counters, never silent drops.
        _couch_prior: dict[str, int] = {}
        _hunters = []
        for m in _pool:
            _rec = m.get("recency") or {}
            _sig = str(m.get("signature") or "")
            _streak = int(_rec.get("couch_streak") or 0)
            if _sig:
                _couch_prior[_sig] = _streak
            if (str(_rec.get("verdict") or "") == "couch"
                    and _streak >= max(1, int(config.couch_bench_streak))):
                couch_benched += 1
                continue
            _hunters.append(m)
        _pool = _hunters
        champions_in = [StrategyGenome.from_dict(m["genome"])
                        for m in _pool if m.get("genome")]
        for _cg in champions_in:
            _sight(_cg, op="pantry")
        # R106 -- THE RE-TRIAL DOOR: a benched king whose cooldown has
        # expired re-enters generation 0 for ONE shift -- if it hunts again
        # it is a full citizen (streak reset); if it couches again it is
        # re-benched with a doubled cooldown. The bench is memory, not
        # exile (the pantry never erases; the door only rests). The bench
        # faces the SAME Law 3 as the pantry: a ghost (no genome, no
        # measured score) never rides a re-trial -- refused and counted.
        _bench_valid, _bench_refused = dna_mod.honest_champions(_bench_old)
        couch_gated += _bench_refused
        for _b in _bench_valid:
            if bench_retrials >= max(0, int(config.bench_max)):
                break
            if not _b.get("genome"):
                continue
            if int(_b.get("cooldown") or 0) > 0:
                bench_waiting += 1
                continue
            if _gated_out(_b):
                couch_gated += 1
                continue
            _bg = StrategyGenome.from_dict(_b["genome"])
            _bsig = str(_b.get("signature") or "")
            if _bsig:
                _couch_prior[_bsig] = int(_b.get("couch_streak") or 0)
            champions_in.append(_bg)
            _sight(_bg, op="bench")
            bench_retrials += 1
    except (OSError, ValueError, TypeError, KeyError):
        champions_in = []
    champions_injected = 0
    champions_in = champions_in[:max(0, config.population // 4)]
    # R99 -- THE DIASPORA: the other islands' pantries feed this island's
    # generation 0 too (best-first, honest-validated, dedup by signature).
    # Three tribes that never trade genes are three SMALL searches wearing
    # one architecture's clothes; one gene pool of 240 x 3 is the search the
    # Boss was promised. Bounded: at most population//8 foreigners ride
    # beside the island's own pop//4 -- the diaspora is a spice, not a
    # takeover. Fail-open: a broken foreign pantry never starves the shift.
    diaspora_injected = 0
    diaspora_refused = 0
    diaspora_gated = 0
    diaspora_couch_refused = 0
    diaspora_sources: dict[str, int] = {}
    try:
        _foreign_cap = max(0, config.population // 8)
        _seen = {str(g.signature()) for g in champions_in}
        for _other in islands_mod.ISLAND_WHEEL:
            if _other == config.island or diaspora_injected >= _foreign_cap:
                continue
            _pf = Path(f"factory_champions_{_other}.json")
            if not _pf.exists():
                continue
            _pm = json.loads(_pf.read_text())
            _fp, _ref = dna_mod.honest_champions(
                _pm.get("migrants") or _pm.get("champions") or [])
            diaspora_refused += _ref
            # R106 -- THE DIASPORA DOES NOT SPREAD COUCHES: a foreign body whose
            # own pantry labels it a couch on ITS recent window is refused at
            # THIS door too (counted, never hidden) -- the diaspora carries
            # hunters, not reputations earned in a regime that has passed.
            _kept = []
            for m in _fp:
                if str((m.get("recency") or {}).get("verdict") or "") == "couch":
                    diaspora_couch_refused += 1
                    continue
                _kept.append(m)
            _fp = _kept
            _fp.sort(key=_recency_rank)
            for m in _fp:
                if diaspora_injected >= _foreign_cap:
                    break
                if not m.get("genome") or _gated_out(m):
                    diaspora_gated += 1
                    continue
                _g = StrategyGenome.from_dict(m["genome"])
                _sig = str(_g.signature())
                if _sig in _seen:
                    continue  # no island doubles its population with a clone
                _seen.add(_sig)
                champions_in.append(_g)
                _sight(_g, op="diaspora")
                diaspora_injected += 1
                diaspora_sources[_other] = diaspora_sources.get(_other, 0) + 1
    except (OSError, ValueError, TypeError, KeyError):
        pass  # the diaspora is a passenger, never a gate
    # R103 -- THE ATLAS'S SEED: the behavioral map's best ride generation 0
    # beside the pantry's champions and the diaspora's foreigners. The map is
    # the evolution's DIVERSITY memory: one elite per measured behavior, so
    # a regime shift never finds the pool made of one kind of hunter. The
    # same laws as every other door: honest (a cell cannot exist without a
    # measured wilson), dedup'd by signature, gated by the Watchtower's
    # word, capped (a spice, not a takeover). Fail-open: a torn atlas is a
    # fresh random start, never a crash.
    qd_injected = 0
    qd_gated = 0
    qd_dupes = 0
    if config.qd:
        try:
            _seen_qd = {str(g.signature()) for g in champions_in}
            _atlas_seed = qd_mod.load_archive(
                f"factory_qd_{config.island}.json")
            _cap = max(0, int(round(config.population * float(config.qd_injection))))
            for _e in _atlas_seed.diversity_pool(_cap):
                _g_dict = _e.get("genome")
                if not isinstance(_g_dict, dict):
                    continue
                _sig = str(_e.get("signature") or "")
                if not _sig or _sig in _seen_qd:
                    qd_dupes += 1
                    continue
                if _gated_out(_e):
                    qd_gated += 1
                    continue
                champions_in.append(StrategyGenome.from_dict(_g_dict))
                _seen_qd.add(_sig)
                _sight(champions_in[-1], op="atlas")
                qd_injected += 1
        except (OSError, ValueError, TypeError, KeyError):
            pass  # the atlas is a passenger, never a gate
    polish_deltas: list[dict] = []
    # THE DRAGON'S DIRECTED MUTATIONS: the committed hypotheses, indexed by family
    # and gene. An empty directive set is a no-op (blind evolution, as before).
    directed_idx = _directed_index(config.directed)
    directed_stats = {"nudged": 0, "genes": sorted(
        {f"{f}:{g}" for (f, g) in directed_idx})}
    for _ in range(config.population):
        if champions_in:
            # R91 -- a champion enters generation 0 unpolished (it arrives
            # already refined) and is re-scored honestly on tonight's slices.
            population.append(champions_in.pop(0))
            champions_injected += 1
            continue
        g = _new_genome()
        _sight(g, op="random")
        if config.polish:
            def objective(cand):
                # The polish is a CHEAP local search: the screen pair only.
                return evaluator.fit(cand, cheap_pairs).wilson_lb
            pr = polish_mod.polish_genome(g, objective,
                                          polish_mod.PolishConfig(seed=int(rng.integers(1 << 30))))
            if pr.delta > 0:
                g = pr.genome
            polish_deltas.append(pr.to_dict())
        population.append(g)

    # R69/R97 — screen the whole pool: round one keeps the living variety, the
    # full rounds judge the merit.
    funnel_block = {"applied": False, "survival": config.screen_survival,
                    "keep": 0, "pool": len(population)}
    if config.staircase:
        # R97 — THE LIVING FUNNEL. Round one grades the pool on the CHEAP pair
        # with life first: (trades, wilson_lb, net_r) — a body that never trades
        # sinks to the bottom, a living body rises regardless of its merit; the
        # merit is NOT judged here. The top ``keep`` pass. The R85 friction gate
        # moves to round two (the "era"), where the invoice is FULL (all pairs)
        # and the result memory makes the re-read free -- the sealed 3x law is
        # unchanged, only its seat in the funnel moves: judging 240 random
        # bodies on a cheap single-pair invoice killed the evolution for days.
        def _friction_gate_full(genome):
            m = evaluator.report(genome, pairs).metrics
            if m.trades <= 0:
                return None
            return staircase_mod.FrictionGate(gross_r=m.gross_r,
                                              friction_r=m.gross_r - m.net_r)

        def _graded(genome):
            fit = evaluator.fit(genome, cheap_pairs)
            return (int(fit.trades), float(fit.wilson_lb), float(fit.net_r))

        keep = max(1, int(round(len(population) * float(config.screen_survival))))
        scr = staircase_mod.screen(
            population, staircase, friction_gate=_friction_gate_full,
            gate_round=1, relative={"keep": keep, "graded": _graded})
        screened = scr.survivors
        staircase_ledger = scr.to_dict()
        staircase_ledger["screened_out_before_full_eval"] = (
            len(population) - len(screened))
        funnel_block.update({"applied": True, "keep": keep})
    else:
        screened = population
        staircase_ledger = {"rounds_run": 0, "survivors": len(population)}

    generations: list[dict] = []
    entropy_trend: list[dict] = []
    trials = 0

    def _evaluate_pool(pool):
        nonlocal trials
        scored = []
        for g in pool:
            fit = evaluator.fit(g, pairs)
            trials += 1
            scored.append((g, fit))
        scored.sort(key=lambda t: _rank_key(t[1]), reverse=True)
        return scored

    # --- the sealed first full evaluation (post-screen) --------------------
    scored = _evaluate_pool(screened)

    for gen in range(config.generations):
        # R72 — read the live diversity of the ranked population.
        sigs = [g.signature() for g, _ in scored]
        reading = entropy_mod.EntropyReading(sigs)
        rate = reading.rate
        entropy_trend.append({"generation": gen, **reading.to_dict(),
                              "population": len(sigs)})

        ranked = [(g, f) for g, f in scored if f.ranked]
        if not ranked:
            generations.append({
                "generation": gen, "evaluated": len(scored), "ranked": 0,
                "best_family": "", "best_wilson_lb": 0.0, "best_net_r": 0.0,
                "entropy": reading.entropy, "mutation_rate": rate,
            })
            break

        # R71a — the survivors teach: fold them into the gene memory.
        eda_mem.observe([g for g, _ in ranked])

        elites = [g for g, _ in ranked[:config.elite]]
        record = {
            "generation": gen,
            "evaluated": len(scored),
            "ranked": len(ranked),
            "best_family": ranked[0][0].family,
            "best_wilson_lb": round(float(ranked[0][1].wilson_lb), 4),
            "best_net_r": round(float(ranked[0][1].net_r), 4),
            "entropy": reading.entropy, "mutation_rate": rate,
        }
        generations.append(record)

        if gen == config.generations - 1:
            break

        # --- breed the next generation (EDA-biased + adaptive rate) --------
        children: list[StrategyGenome] = list(elites)
        for _eg in elites:
            _sight(_eg, op="elite")
        # R127 -- THE CONSANGUINEITY BRAKE: measure the elites' blood BEFORE
        # breeding.  When it concentrates the crossover prefers DISJOINT
        # mates (bounded tries, honest fall-through); under one-blood a few
        # fresh immigrants ride the children (they REPLACE as many bred
        # children -- the population never changes, the pairs never change,
        # every sizing rule untouched: only the CHOICE OF MATES widens).
        _elite_blood = {str(g.signature()): _book.blood_of(str(g.signature()))
                        for g in elites}
        _elite_h = gene_mod.herfindahl(gene_mod.census(_elite_blood))
        _brake_on = _elite_h >= gene_mod.VERDICT_THRESHOLDS["concentrating"]
        # R143 -- THE GENE FLOOD: the streak is the measurement that escalates.
        # A one-blood night gets the drip (4 founders, exactly as R127); a
        # one-blood STREAK (persistent across runs -- the collapse the letter
        # has measured every night for weeks) gets the WAVE: a bounded share of
        # the children as family-spread fresh founders.  The population never
        # changes, the pairs never change, every sizing rule untouched: only
        # the WIDTH of the new blood grows, and it recedes the moment the
        # census says the blood is diverse again.
        _one_blood_streak = gene_mod.blood_streak(_one_blood_streak, _elite_h)
        _immigrants_n = gene_mod.flood_wave(_one_blood_streak, config.population)
        _flood = (_one_blood_streak >= gene_mod.FLOOD_STAGNATION)
        if _brake_on:
            _brake["applied"] = True
            _brake["reason"] = (
                "il sangue degli elite si concentra (H="
                f"{_elite_h:.3f}): i partner preferiti hanno sangue diverso")
        if _immigrants_n:
            _brake["immigrants"] = _immigrants_n
            _brake["reason"] = (f"one-blood (H={_elite_h:.3f}) da "
                                f"{_one_blood_streak} generazioni: "
                                f"{_immigrants_n} immigrati freschi entrano "
                                "nella generazione")
        if _flood:
            _brake["flood"] = True
            _brake["flood_streak"] = _one_blood_streak
            _brake["reason"] = (f"L'ONDATA DI SANGUE NUOVO (H={_elite_h:.3f}, "
                                f"{_one_blood_streak} generazioni di "
                                f"one-blood): {_immigrants_n} fondatori "
                                "freschi sparsi su tutte le famiglie entrano "
                                "nella generazione")
        n_child = max(0, config.population - len(elites) - _immigrants_n)
        for i in range(n_child):
            if i % 2 == 1 and len(elites) >= 2:
                a = elites[int(rng.integers(len(elites)))]
                if _brake_on:
                    _asig = str(a.signature())
                    _msig, _avd = gene_mod.choose_mate(
                        [str(g.signature()) for g in elites], _asig, _book, rng)
                    b = next(g for g in elites if str(g.signature()) == _msig)
                    if _avd:
                        _brake["sibling_mates_avoided"] += 1
                else:
                    b = elites[int(rng.integers(len(elites)))]
                child = breeding.crossover_genome(a, b, rng)
                _book.record_child(str(child.signature()),
                                   (str(a.signature()), str(b.signature())))
                _births.append(gene_mod.Birth(
                    child=str(child.signature()), op="crossover",
                    parents=(str(a.signature()), str(b.signature()))))
            else:
                parent = elites[int(rng.integers(len(elites)))]
                child = breeding.mutate_genome(parent, rng, rate=rate)
                _book.record_child(str(child.signature()),
                                   (str(parent.signature()),))
                _births.append(gene_mod.Birth(
                    child=str(child.signature()), op="mutate",
                    parents=(str(parent.signature()),)))
            # R71a — draw a few genes from the survivors' distribution.
            genes = child.to_dict()
            moved = False
            for gene in ("sl_atr_mult", "target_rr", "min_confluence"):
                if rng.random() < 0.5:
                    drawn = eda_mem.sample_gene(child.family, gene, rng)
                    if drawn is not None:
                        genes[gene] = drawn
                        moved = True
            # THE DRAGON'S DIRECTED MUTATIONS: nudge the child's genes toward the
            # bound the dominant intelligence named (no directive -> no change).
            d_genes, d_n = _directed_genes(child, directed_idx)
            if d_n:
                for k in d_genes:
                    genes[k] = d_genes[k]
                moved = True
                directed_stats["nudged"] += d_n
            children.append(StrategyGenome.from_dict(genes) if moved else child)
            _csig = str(children[-1].signature())
            if not _book.is_known(_csig):
                # an EDA/directed REBUILD is a new signature born of `child`
                _book.record_child(_csig, (str(child.signature()),))
                _births.append(gene_mod.Birth(
                    child=_csig, op="rebuild",
                    parents=(str(child.signature()),)))
        # R127 -- the fresh immigrants ride BESIDE the bred children (they
        # replaced their slots in n_child, so the pool stays exactly
        # config.population).  A newborn immigrant is its own founder.
        # R143 -- in a FLOOD the wave is FAMILY-SPREAD: every family the table
        # would judge gets its founders (a wave drawn from one family would be
        # a new monoculture, not a cure).  In the drip the draw stays exactly
        # as R127 drew it (weighted, gated, byte-identical).
        if _flood:
            _wave = gene_mod.spread_families(
                _immigrants_n, _flood_families(config), rng)
            for _fam in _wave:
                _ig = breeding.random_genome(rng, family=_fam)
                _sight(_ig, op="immigrant")
                children.append(_ig)
        else:
            for _ in range(_immigrants_n):
                _ig = _new_genome()
                _sight(_ig, op="immigrant")
                children.append(_ig)
        scored = _evaluate_pool(children)

    # --- R73 realms + R71b CMA-ES on the finalists -------------------------
    final_scored = sorted(scored, key=lambda t: _rank_key(t[1]), reverse=True)
    leaderboard = []
    for g, f in final_scored:
        row = g.to_dict()
        row.update({
            "signature": g.signature(), "family": g.family,
            "ranked": bool(f.ranked),
            "wilson_lb": round(float(f.wilson_lb), 4),
            "net_r": round(float(f.net_r), 4), "trades": int(f.trades),
        })
        leaderboard.append(row)

    # R97 — A COUCH IS NEVER A CHAMPION: only bodies with enough evidence
    # (min_trades on the full universe) sit in realms, hold thrones or enter
    # the pantry. The old leaderboard let a no-trade body (wilson 0.0, net 0.0)
    # outrank every honest loser and be crowned -- the pantry held seven couches
    # for days. The couch is not "worst"; it is UNKNOWN (the doctrine's own
    # words), and the unknown is never crowned. The full leaderboard stays in
    # the report (diagnostic, couches visible and counted); the CENSUS and the
    # SEATS see only the measured.
    ranked_rows = [r for r in leaderboard if r.get("ranked")]
    realm_census = realms_mod.census(ranked_rows)
    champions = realms_mod.distinct_realm_champions(
        ranked_rows, seats=config.champion_seats)

    # R100 -- THE RECENCY PROBATION (the fire every champion faces before the
    # pantry remembers it): the champion was SELECTED on the full book; the
    # probation re-measures it on the MOST RECENT window -- the closest thing
    # to tomorrow morning. A champion that only fits the distant past is
    # LABELLED, never erased (the label is the medicine, and the next shift's
    # injection reads it). A fresh result memory keeps the probation's reads
    # from ever colliding with the selection's own (the key would be blind to
    # the window -- the house learned this the honest way).
    probation_block = {"applied": False, "confirmed": 0, "probation": 0,
                       "couch": 0, "unmeasured": 0,
                       "policy": "the most recent window, fresh memory; "
                                 "labels, never erasures"}
    if probation_universe and champions:
        _prob_eval = _Evaluator(probation_universe, config.min_trades,
                                rm_mod.ResultMemory())
        for _ch in champions:
            try:
                _rep = _prob_eval.report(
                    StrategyGenome.from_dict(_ch), pairs)
                _fit = fitness_mod.fitness(_rep.metrics, config.min_trades)
                _trades = int(_fit.trades)
                _wilson = float(_fit.wilson_lb)
                if _trades >= 5 and _wilson >= 0.20:
                    _verdict = "confirmed"
                elif _trades >= 1:
                    _verdict = "probation"
                else:
                    _verdict = "couch"  # measured: no life in the window
                # R106 -- THE STREAK IS MEMORY: a couch tonight rides the
                # pantry's prior streak (its own label of last shift, or a
                # bench re-trial's); a hunter resets it to zero. The streak
                # is the bench's trigger, and it is honest arithmetic on
                # measured labels, never a guess.
                _psig = str(_ch.get("signature") or "")
                _streak = (int(_couch_prior.get(_psig, 0)) + 1
                           if _verdict == "couch" else 0)
                _ch["recency"] = {"wilson_lb": round(_wilson, 4),
                                   "net_r": round(float(_fit.net_r), 4),
                                   "trades": _trades, "verdict": _verdict,
                                   "couch_streak": _streak}
            except Exception:  # a failed re-read is unmeasured, never a guess
                _verdict = "unmeasured"
                _ch["recency"] = {"verdict": _verdict}
            probation_block[_verdict] = probation_block.get(_verdict, 0) + 1
        probation_block["applied"] = True

    # R104 -- THE COGNITION INSTRUMENTS (the Director's faculties, applied):
    # (a) SLICE AGREEMENT -- every champion is re-read on each deterministic
    #     slice of the universe: the fraction of slices on which the body
    #     was net profitable. Two equal Wilsons are not equal evidence when
    #     one wins everywhere and the other rides a single slice (Faculty 4:
    #     belief follows evidence, and INDEPENDENCE is part of the evidence).
    #     Unmeasured is None, never a 0.0 (the couch lesson, applied to
    #     independence itself).
    for _ch in champions:
        _ch["slice_agreement"] = None
        try:
            _slice_rs = []
            _cg = StrategyGenome.from_dict(_ch)
            for _s in slice_set:
                _slice_rs.append(float(evaluator.fit(_cg, _s.pairs).net_r))
            _ch["slice_agreement"] = zcog_mod.slice_agreement(_slice_rs)
        except Exception:
            _ch["slice_agreement"] = None  # a failed read is unmeasured, never a guess

    # (b) THE CALIBRATION LEDGER (Faculty 6): the previous shifts' probation
    #     labels are graded against tonight's measurements, and tonight's
    #     labels are filed for the next shift to grade. A label is a
    #     prediction; the ledger keeps the score; the organism stops lying
    #     by accident. Fail-open both ways: the instrument is a passenger.
    calibration_block = {"applied": False, "accuracy": None, "graded": 0,
                         "published": False,
                         "policy": "a label is a prediction; the next shift grades it"}
    # THE PUBLICATION GATE (the D3 lesson, applied at birth): the memory files
    # are published for the REAL islands only (heart/turbo/vault). A test
    # island evolves in memory and dies with its run -- its map may never
    # land in the working tree (the wound this gate closes was caught on the
    # first live round: factory_qd_test.json and _revolution.json appeared
    # beside the real memories, one VM death away from being committed).
    _publish = config.island in islands_mod.ISLAND_WHEEL
    if config.calibration:
        try:
            _cal = zcog_mod.load_calibration(
                f"factory_calibration_{config.island}.json")
            for _ch in champions:
                try:
                    calibration_block["graded"] += _cal.score(
                        signature=str(_ch.get("signature") or ""),
                        wilson_lb=float(_ch.get("wilson_lb") or 0.0),
                        ranked=bool(_ch.get("ranked")))
                except Exception:
                    pass
            for _ch in champions:
                _verdict = (_ch.get("recency") or {}).get("verdict")
                if _verdict:
                    _cal.record(shift_id=f"seed={shift_seed}",
                                signature=str(_ch.get("signature") or ""),
                                verdict=_verdict,
                                wilson_lb=float(_ch.get("wilson_lb") or 0.0),
                                family=str(_ch.get("family") or ""))
            if _publish:
                zcog_mod.save_calibration(
                    _cal, f"factory_calibration_{config.island}.json")
            calibration_block["applied"] = True
            calibration_block["published"] = bool(_publish)
            calibration_block["accuracy"] = _cal.accuracy()
        except (OSError, ValueError, TypeError, KeyError):
            pass

    # R103 -- THE ATLAS GROWS: every RANKED body with a measured behavior is
    # offered to its niche (the couch has no behavior; the unranked carry too
    # little evidence to map). The offer is the MAP-ELITES rule: a niche
    # keeps the best Wilson lower bound it has ever seen. The atlas file
    # rides the heart's commit beside the pantry (the R101 doctrine, one
    # memory more). The per-row report read is a result-memory hit (the key
    # is the full-universe one the leaderboard already wrote) -- the atlas
    # costs nothing the evolution has not already paid.
    qd_block = {"applied": False, "niches_total": qd_mod.NICHES,
                "occupied": 0, "coverage": 0.0, "offered": 0, "entered": 0,
                "published": False,
                "policy": "one elite per measured behavior (activity x horizon "
                          "x direction); MAP-Elites over 36 niches"}
    if config.qd:
        try:
            _atlas = qd_mod.load_archive(f"factory_qd_{config.island}.json")
            _offers = []
            for _row in ranked_rows[:max(0, int(config.qd_top))]:
                try:
                    _rg = StrategyGenome.from_dict(_row)
                    _m = evaluator.report(_rg, pairs).metrics
                    _side_total = int(_m.long_trades) + int(_m.short_trades)
                    # the direction axis needs the engine's own census: only
                    # when at least half the trades declared a side is the
                    # share measured (else the body is direction-unknown --
                    # not offered, never a guessed leaning)
                    _share = (float(_m.long_trades) / float(_side_total)
                              if _side_total >= max(1, int(_m.trades) // 2)
                              else None)
                    _desc = qd_mod.descriptor(
                        trades=_m.trades, avg_bars_held=_m.avg_bars_held,
                        long_share=_share)
                    if _desc is None:
                        continue
                    _offers.append({
                        "signature": _row.get("signature"),
                        "family": _row.get("family"),
                        "wilson_lb": float(_row.get("wilson_lb") or 0.0),
                        "net_r": float(_row.get("net_r") or 0.0),
                        "trades": int(_m.trades),
                        "behavior": _desc, "genome": _row,
                        "slice_agreement": _row.get("slice_agreement"),
                    })
                except Exception:
                    continue
            _entered = _atlas.offer_many(_offers)
            if _publish:
                qd_mod.save_archive(_atlas, f"factory_qd_{config.island}.json")
            qd_block.update({
                "applied": True, "offered": len(_offers), "entered": _entered,
                "occupied": len(_atlas.cells),
                "coverage": round(_atlas.coverage(), 4),
                "published": bool(_publish),
            })
        except (OSError, ValueError, TypeError, KeyError):
            pass

    cma_rows: list[dict] = []
    if config.cma and leaderboard:
        for row in leaderboard[:min(5, len(leaderboard))]:
            g = StrategyGenome.from_dict(row)
            cma_rows.append(_cma_refine(g, evaluator, cheap_pairs, config))

    # R68 — export this island's champions as a migration (empty => no export,
    # reported honestly rather than fabricated). R106 -- THE EXPORT CARRIES
    # HUNTERS ONLY: a champion the probation labels a couch on the recent
    # window does not ride to the other islands (their door refuses it too,
    # belt over braces); the honest reason is spoken when nobody rides.
    _pantry_rows = [{"genome": StrategyGenome.from_dict(r).to_dict(),
                     "family": r["family"], "wilson_lb": r["wilson_lb"],
                     "net_r": r["net_r"],
                     "slice_agreement": r.get("slice_agreement"),
                     "recency": r.get("recency")}
                    for r in champions]
    _hunters = [row for row in _pantry_rows
                if str(((row.get("recency") or {}).get("verdict"))
                       or "") != "couch"]
    if _hunters:
        migration = islands_mod.build_migration(
            config.island, config.generations, _hunters).to_dict()
    elif champions:
        migration = {"exported": False,
                     "reason": "every champion is a couch on the recent "
                               "window -- the diaspora does not spread "
                               "couches (R106)"}
    else:
        migration = {"exported": False,
                     "reason": "no ranked body cleared the floor this shift "
                               "(R97: the couch is never crowned)"}

    # R97 — the honest funnel report: what round one kept, how many couches
    # rode the pool, how many bodies carried real evidence to the end.
    funnel_block.update({
        "pool": len(population),
        "no_trade_final": sum(1 for r in leaderboard if int(r.get("trades") or 0) == 0),
        "ranked_final": len(ranked_rows),
        "gate_round": "era",
        "graded_key": "(trades, wilson_lb, net_r) on the cheap pair — life first",
    })

    # R91 -- persist this shift's champions for the NEXT shift's generation 0
    # (the evolution's memory; committed like the ledger it grows beside).
    # R106 -- THE BENCH RIDES THE PANTRY FILE: the pantry keeps ALL of
    # tonight's champions (the island's own memory, labels and all) PLUS the
    # bench (benched kings with their streak and cooldown -- memory, never
    # exile). The digest seals the champions exactly as before (a reader
    # that never knew the bench is never surprised).
    if champions or _bench_old:
        _bench_final: list = []
        try:
            _bench_final = _evolve_bench(_bench_old, champions, config)
            _pantry = {
                "schema": islands_mod.MIGRATION_SCHEMA,
                "source_island": config.island,
                "generation": int(config.generations),
                "champions": _pantry_rows,
                "digest": islands_mod._digest(
                    config.island, int(config.generations), _pantry_rows),
                "bench": _bench_final,
                "exported": {"hunters": len(_hunters),
                             "couches": len(_pantry_rows) - len(_hunters)},
            }
            Path(f"factory_champions_{config.island}.json").write_text(
                json.dumps(_pantry, indent=2, default=str))
        except (OSError, TypeError, ValueError):
            pass
    else:
        _bench_final = []

    # R126 -- THE GENEALOGIST'S SPOKEN CENSUS: the final pool's blood (the
    # last generation's living bodies -- the survivors of the funnel), the
    # collision probability, the effective population, the verdict.  The
    # book is pruned to the living (pool + champions + bench + atlas
    # futures) and saved; the artifact rides beside the pantry (guardian
    # check #16).  Fail-open: a book that cannot save never stops the shift.
    _final_blood = {str(g.signature()): _book.blood_of(str(g.signature()))
                    for g, _f in final_scored}
    _gene_block = gene_mod.artifact(
        island=config.island, blood_map=_final_blood, births=_births,
        book=_book, brake=_brake, brake_streak=_one_blood_streak)
    try:
        _alive = set(_final_blood)
        _alive |= {str(StrategyGenome.from_dict(r["genome"]).signature())
                   for r in _pantry_rows if r.get("genome")}
        _alive |= {str(m.get("signature") or "") for m in _bench_old}
        _book.prune_to({s for s in _alive if s})
        if _publish:
            _book.save(_blood_path)
            Path(f"factory_genealogy_{config.island}.json").write_text(
                json.dumps(_gene_block, indent=1, default=str))
    except (OSError, ValueError, TypeError, KeyError):
        pass  # the census was already spoken; the memory is a passenger

    wall = clock() - start
    # Honest machine-work: EVERY evaluation performed (polish + screen + full +
    # CMA), which is exactly the result memory's miss count. ``genomes_scored``
    # is the narrower count of population members that reached a full evaluation.
    mem_stats = memory.stats()
    return {
        "phase": 7,
        "kind": "factory_run",
        "config_hash": config.signature(),
        "seed": shift_seed,
        "champions_injected": champions_injected,
        "diaspora": {"injected": diaspora_injected,
                     "sources": diaspora_sources,
                     "refused": diaspora_refused,
                     "gated": diaspora_gated + gated_own,
                     "couch_refused": diaspora_couch_refused,
                     "policy": "cross-island best-first, cap population//8 "
                               "(R99: three tribes, one gene pool); the "
                               "Watchtower's paused families never re-enter; "
                               "a couch never rides (R106)"},
        "probation": probation_block,
        "couch_law": {"benched_own": couch_benched,
                      "bench_retrials": bench_retrials,
                      "bench_waiting": bench_waiting,
                      "bench_gated": couch_gated,
                      "bench_size": len(_bench_final),
                      "diaspora_couch_refused": diaspora_couch_refused,
                      "exported_hunters": len(_hunters),
                      "exported_couches": len(_pantry_rows) - len(_hunters),
                      "policy": "a chronic couch (streak >= trigger) rests on "
                                "the bench with re-trial rights; the pantry "
                                "never erases; the diaspora spreads hunters "
                                "only (R106)"},
        "dna": dna_mod.transcribe(champions_refused=champions_refused),
        "weather": _live_weather(),   # R115: the sky it evolved under, observed
        "genealogy": _gene_block,     # R126: the blood it carries, spoken
        "zcognition": zcog_mod.zcognition_block(
            qd_coverage=qd_block.get("coverage"),
            calibration=calibration_block.get("accuracy"),
            slice_agreements=[c.get("slice_agreement") for c in champions],
            champions=champions),
        "qd": {**qd_block, "injected": qd_injected, "gated": qd_gated,
               "dupes": qd_dupes},
        "island": config.island,
        "pairs": list(pairs),
        "population": config.population,
        "generations_config": config.generations,
        "wallclock_seconds": round(wall, 3),
        "trials": int(mem_stats["misses"]),
        "genomes_scored": len(leaderboard) + sum(
            g["evaluated"] for g in generations),
        "slices": {
            "slice_set_digest": slices_mod.fuse_certificate_summary(
                slice_set, {s.index: [] for s in slice_set}, [])["slice_set_digest"],
            "slices": [s.to_dict() for s in slice_set],
        },
        "staircase": staircase_ledger,
        "funnel": funnel_block,
        "result_memory": memory.stats(),
        "eda_memory": {"families_learned": len(eda_mem.snapshot()),
                       "snapshot": eda_mem.snapshot()},
        "directed": {**directed_stats,
                     "n_directives": len(directed_idx)},
        "regime_gating": _gating_block(config, population),
        "polish": {
            "newborns": len(polish_deltas),
            "improved": sum(1 for d in polish_deltas if d["delta"] > 0),
            "total_delta": round(sum(d["delta"] for d in polish_deltas), 6),
            "last": polish_deltas[-1] if polish_deltas else {},
        },
        "cma": {"refined": len(cma_rows), "rows": cma_rows},
        "entropy_trend": entropy_trend,
        "realms": realm_census,
        "champions": [
            {"signature": r.get("signature"), "family": r.get("family"),
             "wilson_lb": r.get("wilson_lb"), "net_r": r.get("net_r"),
             "slice_agreement": r.get("slice_agreement"),
             "recency": (r.get("recency") or {}).get("verdict")}
            for r in champions
        ],
        "leaderboard_top": [
            {"signature": r["signature"], "family": r["family"],
             "wilson_lb": r["wilson_lb"], "net_r": r["net_r"],
             "trades": r["trades"]}
            for r in leaderboard[:10]
        ],
        "migration": migration,
        "generations": generations,
    }


def _cma_refine(genome, evaluator, pairs, config) -> dict:
    """R71b — one bounded CMA-ES pass over the risk-geometry genes."""
    from app.factory.cma import CMAConfig, refine
    from app.quant.genome import GENE_BOUNDS_BY_NAME

    genes = ("sl_atr_mult", "target_rr", "trail_start_rr", "trail_atr_mult",
             "min_atr_pips", "max_spread_pips", "min_confluence")
    x0 = np.array([float(getattr(genome, g)) for g in genes])
    low = np.array([GENE_BOUNDS_BY_NAME[g].low for g in genes])
    high = np.array([GENE_BOUNDS_BY_NAME[g].high for g in genes])

    def objective(x):
        cand = genome
        for g, v in zip(genes, x):
            cand = cand.with_genes(**{g: float(v)})
        return evaluator.fit(cand, pairs).wilson_lb

    res = refine(x0, objective, low, high,
                 CMAConfig(population=config.cma_population,
                           generations=config.cma_generations,
                           seed=config.seed))
    out = res.to_dict()
    out["signature"] = genome.signature()
    out["family"] = genome.family
    return out
