"""THE SEARCH — the Author's bounded, budget-capped loop (Phase 4b, R33).

The Author grows a population of grammar programs, JUDGES each through the full
cage (R31 static gate -> R30 sandbox / determinism / R32 causality / honest
engine), keeps the survivors, and evolves them by mutation and crossover.

R33 — BUDGET CAP. Exploration consumes a bounded number of EVALUATIONS (one
judge = one evaluation). When the cap is reached the loop stops and reports
``partial=True``; it can never run unbounded. This is the same honest unit the
avant-garde budget uses (R25).

DETERMINISM. A seeded run is byte-for-byte reproducible: the RNG seed and the
population are the only inputs, and a judge is deterministic. The result digest
carries a stable signature sample.

PURITY. No I/O at import. The loop's only I/O is the judge (sandbox) and the
optional ledger/registry, passed in by the caller. Build Mode: bounded loops
only — never a server, scheduler, or unbounded loop.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.pyramid.author import grammar as g
from app.pyramid.author import registry as registry_mod
from app.pyramid.author import synth as sy
from app.quant.genome import FAMILIES

__all__ = ["AuthorConfig", "AuthorCandidate", "AuthorResult", "run_author",
           "AUTHORED_FAMILY_COUNT"]

# The 45th family: the 44 broadcast families plus the attended ``generated_body``.
# Declared here as the single arithmetic truth (never re-derived by hand).
AUTHORED_FAMILY_COUNT = len(FAMILIES) + 1


@dataclass(frozen=True)
class AuthorConfig:
    """Everything an Author run needs to be reproducible and bounded."""

    pairs: tuple[str, ...]
    population: int = 12
    generations: int = 2
    elite: int = 4
    seed: int = 0
    # R33 — hard cap on evaluations (one judge == one evaluation).
    evaluation_budget: int = 200
    mutation_rate: float = 0.6
    # M15 rows to judge over, and the per-body sandbox timeout.
    rows: int = 3000
    timeout: float = 8.0
    # When True, only NET-POSITIVE survivors are kept (R21 doctrine applied here).
    require_net_positive: bool = True
    # R35 (Phase 5) — CROSS-PAIR validation: a survivor must also be net-positive
    # on at least this many Constellation pairs (closes the 4b single-pair
    # weakness). 1 disables the extra check.
    min_cross_pairs: int = 1

    def signature(self) -> str:
        payload = (
            f"pairs={sorted(self.pairs)};pop={self.population};gen={self.generations};"
            f"elite={self.elite};seed={self.seed};mut={self.mutation_rate};"
            f"rows={self.rows};pos={self.require_net_positive};"
            f"xpairs={self.min_cross_pairs}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class AuthorCandidate:
    """One judged body: its program, its emitted source, and its verdict."""

    program: g.Program
    source: str
    body_id: str
    pair: str
    alive: bool
    causes: list[str]
    performance: dict | None
    generation: int
    # R35 — how many Constellation pairs the body was net-positive on (evidence).
    cross_pairs_positive: int = 0

    def to_dict(self) -> dict:
        return {
            "body_id": self.body_id,
            "concept": self.program.concept,
            "pair": self.pair,
            "alive": self.alive,
            "causes": list(self.causes),
            "performance": self.performance,
            "generation": self.generation,
            "cross_pairs_positive": int(self.cross_pairs_positive),
        }


@dataclass
class AuthorResult:
    """The full record of an Author run."""

    config_hash: str
    seed: int
    evaluations: int
    partial: bool
    populations: dict[int, list[AuthorCandidate]]
    survivors: list[AuthorCandidate]
    by_cause: dict[str, int]
    best: AuthorCandidate | None
    concept_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "config_hash": self.config_hash,
            "seed": self.seed,
            "evaluations": self.evaluations,
            "partial": self.partial,
            "populations": {str(k): [c.to_dict() for c in v]
                            for k, v in self.populations.items()},
            "survivors": [c.to_dict() for c in self.survivors],
            "survivor_signatures": [c.body_id for c in self.survivors],
            "by_cause": dict(self.by_cause),
            "best": self.best.to_dict() if self.best else None,
        }


def _judge(program: g.Program, source: str, m15: pd.DataFrame, pair: str, pip: float,
           cfg: AuthorConfig):
    from app.pyramid.sandbox import judge_body
    from app.pyramid.sandbox.runner import SandboxConfig

    return judge_body(
        source, m15, pair, pip, {"family": "trend_pullback"},
        config=SandboxConfig(timeout=cfg.timeout),
        program=program,   # R35 — shadow-equivalence gate on grammar bodies
    )


def _cross_pairs_positive(program, frames, pips, cfg, *, exclude_pair) -> int:
    """R35 — count Constellation pairs where the body is net-positive (native).

    Uses the shadow evaluation (the verified-causal reference) and the honest
    engine, so the count is the SAME judgement a full cage run would reach for a
    grammar body (R35 equivalence, gate 3). Bounded to the pairs in the run.
    """
    from app.pyramid.author import shadow as shadow_mod
    from app.quant import evaluator as ev
    from app.quant import frames as fr
    from app.quant.genome import StrategyGenome

    geometry = StrategyGenome.from_dict({"family": "trend_pullback"})
    count = 0
    for pair in sorted(frames):
        try:
            F = fr.build_frames(frames[pair], pair, pips[pair])
            sh = shadow_mod.evaluate_tree(program, F.exec, {"family": "trend_pullback"})
            rep = ev.evaluate(
                geometry, {pair: F}, ev.EvaluationConfig(),
                signals_by_pair={pair: (sh.long, sh.short, {})},
            )
        except Exception:
            continue
        if float(rep.metrics.net_r) > 0.0:
            count += 1
    return count


def run_author(
    universe: dict[str, pd.DataFrame],
    config: AuthorConfig,
    *,
    ledger=None,
) -> AuthorResult:
    """Run the Author over ``universe`` (pair -> validated M15 frame).

    Deterministic under ``seed``; bounded by ``evaluation_budget`` (R33).
    """
    from app.core.pairs import PAIR_PIP

    rng = np.random.default_rng(config.seed)
    frames = {}
    for pair in config.pairs:
        if pair not in universe:
            continue
        obj = universe[pair]
        m15 = getattr(obj, "m15", obj)  # accept a Frames or a bare M15 frame
        frames[pair] = m15.iloc[-config.rows:].reset_index(drop=True) if config.rows else m15
    if not frames:
        raise ValueError("author run has no usable pairs (fail-closed)")

    pairs_sorted = tuple(sorted(frames))
    pips = {p: PAIR_PIP[p] for p in pairs_sorted}

    # gen 0 — a fresh random population.
    population = [sy.random_body(rng, concept=f"gen0_{i}") for i in range(config.population)]

    evaluations = 0
    partial = False
    by_cause: dict[str, int] = {}
    populations: dict[int, list[AuthorCandidate]] = {}
    survivors: list[AuthorCandidate] = []
    best: AuthorCandidate | None = None

    for gen in range(config.generations):
        gen_candidates: list[AuthorCandidate] = []
        for i, program in enumerate(population):
            if evaluations >= config.evaluation_budget:
                partial = True
                break
            source = g.emit_python(program)
            pair = pairs_sorted[(gen + i) % len(pairs_sorted)]
            bid = registry_mod.body_hash(source)
            if ledger is not None:
                ledger.birth(source, concept=program.concept, origin="generated")
            # R34 — persist the generated body on disk (source survives the process).
            registry_mod.store(source, concept=program.concept, parent=None)
            verdict = _judge(program, source, frames[pair], pair, pips[pair], config)
            evaluations += 1
            if ledger is not None:
                ledger.verdict(bid, verdict)
            perf = verdict.performance
            alive = verdict.alive
            if alive and config.require_net_positive:
                alive = bool(perf and perf.get("net_r", 0.0) > 0.0)
            cross = 0
            if alive and config.min_cross_pairs > 1:
                cross = _cross_pairs_positive(program, frames, pips, config,
                                              exclude_pair=pair)
                if cross < config.min_cross_pairs:
                    alive = False
            caus = list(verdict.causes) if not verdict.alive else (
                [] if alive else (["cross_pair"] if config.min_cross_pairs > 1
                                  and cross < config.min_cross_pairs else ["friction"])
            )
            if not alive:
                for c in (caus or ["unknown"]):
                    by_cause[c] = by_cause.get(c, 0) + 1
            cand = AuthorCandidate(
                program=program, source=source, body_id=bid, pair=pair,
                alive=alive, causes=caus, performance=perf, generation=gen,
                cross_pairs_positive=cross,
            )
            gen_candidates.append(cand)
            if alive:
                survivors.append(cand)
                if best is None or (perf or {}).get("net_r", 0.0) > \
                        (best.performance or {}).get("net_r", 0.0):
                    best = cand
        populations[gen] = gen_candidates
        if partial:
            break
        if gen + 1 >= config.generations:
            break

        # Evolve: keep the strongest, refill by mutation/crossover of the elite.
        ranked = sorted(
            gen_candidates,
            key=lambda c: (0 if c.alive else 1, -((c.performance or {}).get("net_r", 0.0))),
        )
        elite = [c.program for c in ranked[: max(1, config.elite)]]
        next_pop: list[g.Program] = list(elite)
        while len(next_pop) < config.population:
            if rng.random() < config.mutation_rate or len(elite) < 2:
                parent = elite[int(rng.integers(0, len(elite)))]
                child = sy.mutate_body(parent, rng)
            else:
                a = elite[int(rng.integers(0, len(elite)))]
                b = elite[int(rng.integers(0, len(elite)))]
                child = sy.crossover_body(a, b, rng)
            next_pop.append(child)
        population = next_pop

    concept_counts: dict[str, int] = {}
    for cands in populations.values():
        for c in cands:
            concept_counts[c.program.concept] = concept_counts.get(c.program.concept, 0) + 1

    return AuthorResult(
        config_hash=config.signature(), seed=config.seed,
        evaluations=evaluations, partial=partial, populations=populations,
        survivors=survivors, by_cause=by_cause, best=best,
        concept_counts=concept_counts,
    )
