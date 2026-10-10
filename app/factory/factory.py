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
* R68 islands     — a champion migration export.

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
from dataclasses import dataclass, field

import numpy as np

from app.core.pairs import PAIR_PIP
from app.quant import breeding
from app.quant import costs
from app.quant import evaluator as ev
from app.quant import fitness as fitness_mod
from app.quant.genome import StrategyGenome
from app.factory import eda as eda_mod
from app.factory import entropy as entropy_mod
from app.factory import islands as islands_mod
from app.factory import polish as polish_mod
from app.factory import realms as realms_mod
from app.factory import result_memory as rm_mod
from app.factory import slices as slices_mod
from app.factory import staircase as staircase_mod

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

    def signature(self) -> str:
        blob = json.dumps(
            {
                "pairs": sorted(self.pairs), "population": self.population,
                "generations": self.generations, "elite": self.elite,
                "min_trades": self.min_trades, "seed": self.seed,
                "ensemble_quota": self.ensemble_quota, "n_slices": self.n_slices,
                "slice_salt": self.slice_salt, "polish": self.polish,
                "cma": self.cma, "staircase": self.staircase,
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


def run_factory(universe, config: FactoryConfig, *,
                clock=time.monotonic) -> dict:
    """Run the factory's bounded reproductive loop and return the honest report."""
    start = clock()
    pairs = tuple(sorted(p for p in config.pairs if p in universe))
    if not pairs:
        raise ValueError("no pairs from the config are in the universe (fail-closed)")
    rng = np.random.default_rng(config.seed)
    memory = rm_mod.ResultMemory()
    evaluator = _Evaluator(universe, config.min_trades, memory)
    eda_mem = eda_mod.GeneMemory()
    staircase = _make_staircase(pairs, config.screen_pair, evaluator)

    slice_set = slices_mod.make_slices(
        pairs, min(config.n_slices, len(pairs)), config.seed, config.slice_salt)

    cheap_pairs = (config.screen_pair,) if config.screen_pair else (pairs[0],)

    def _new_genome():
        return breeding.random_genome(rng, ensemble_quota=config.ensemble_quota)

    # --- generation 0: random + Lamarckian polish (R71c) -------------------
    population: list[StrategyGenome] = []
    polish_deltas: list[dict] = []
    for _ in range(config.population):
        g = _new_genome()
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

    # R69 — screen the whole pool cheaply before the full evaluation.
    if config.staircase:
        scr = staircase_mod.screen(population, staircase)
        screened = scr.survivors
        staircase_ledger = scr.to_dict()
        staircase_ledger["screened_out_before_full_eval"] = (
            len(population) - len(screened))
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
        n_child = max(0, config.population - len(elites))
        for i in range(n_child):
            if i % 2 == 1 and len(elites) >= 2:
                a, b = elites[int(rng.integers(len(elites)))], \
                    elites[int(rng.integers(len(elites)))]
                child = breeding.crossover_genome(a, b, rng)
            else:
                parent = elites[int(rng.integers(len(elites)))]
                child = breeding.mutate_genome(parent, rng, rate=rate)
            # R71a — draw a few genes from the survivors' distribution.
            genes = child.to_dict()
            moved = False
            for gene in ("sl_atr_mult", "target_rr", "min_confluence"):
                if rng.random() < 0.5:
                    drawn = eda_mem.sample_gene(child.family, gene, rng)
                    if drawn is not None:
                        genes[gene] = drawn
                        moved = True
            children.append(StrategyGenome.from_dict(genes) if moved else child)
        scored = _evaluate_pool(children)

    # --- R73 realms + R71b CMA-ES on the finalists -------------------------
    final_scored = sorted(scored, key=lambda t: _rank_key(t[1]), reverse=True)
    leaderboard = []
    for g, f in final_scored:
        row = g.to_dict()
        row.update({
            "signature": g.signature(), "family": g.family,
            "wilson_lb": round(float(f.wilson_lb), 4),
            "net_r": round(float(f.net_r), 4), "trades": int(f.trades),
        })
        leaderboard.append(row)

    realm_census = realms_mod.census(leaderboard)
    champions = realms_mod.distinct_realm_champions(
        leaderboard, seats=7)

    cma_rows: list[dict] = []
    if config.cma and leaderboard:
        for row in leaderboard[:min(5, len(leaderboard))]:
            g = StrategyGenome.from_dict(row)
            cma_rows.append(_cma_refine(g, evaluator, cheap_pairs, config))

    # R68 — export this island's champions as a migration (empty => no export,
    # reported honestly rather than fabricated).
    if champions:
        migration = islands_mod.build_migration(
            config.island, config.generations,
            [{"genome": StrategyGenome.from_dict(r).to_dict(),
              "family": r["family"], "wilson_lb": r["wilson_lb"],
              "net_r": r["net_r"]}
             for r in champions],
        ).to_dict()
    else:
        migration = {"exported": False,
                     "reason": "no realm champion cleared the rank floor"}

    wall = clock() - start
    # Honest machine-work: EVERY evaluation performed (polish + screen + full +
    # CMA), which is exactly the result memory's miss count. ``genomes_scored``
    # is the narrower count of population members that reached a full evaluation.
    mem_stats = memory.stats()
    return {
        "phase": 7,
        "kind": "factory_run",
        "config_hash": config.signature(),
        "seed": config.seed,
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
        "result_memory": memory.stats(),
        "eda_memory": {"families_learned": len(eda_mem.snapshot()),
                       "snapshot": eda_mem.snapshot()},
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
             "wilson_lb": r.get("wilson_lb"), "net_r": r.get("net_r")}
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
