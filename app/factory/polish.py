"""R71c — MEMETIC LAMARCKIAN POLISH.

Every newborn genome gets ONE cheap local-search polish BEFORE its first
evaluation: a bounded descent over a small set of numeric genes, scored by the
caller's objective. The polished genes are WRITTEN BACK into the genome
(Lamarck: what the search learned during an individual's life is inherited by
its genome), so an offspring starts where its parent's polish left off.

The polish is:
* BOUNDED — a capped number of coordinate nudges, never a long search;
* CLAMPED — every nudge is clamped into the sealed gene bounds (THE LAW);
* HONEST — it reports the true improvement delta and never claims a gain it did
  not achieve. If no nudge improves, the genome is returned unchanged.

The caller supplies the mutable-gene list and the objective, so this module has
no opinion about which genes matter — it operates on whatever bounded vector the
caller names. Pure at import; deterministic under the caller's rng.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from app.quant.genome import GENE_BOUNDS_BY_NAME, StrategyGenome, clamp_gene

__all__ = ["PolishConfig", "PolishResult", "polish_genome"]

# The default genes the polish touches: the risk geometry, whose local shape
# most directly moves the win/loss balance and whose bounds are tight and sane.
# Kept SMALL (R71c demands a *cheap* polish: a handful of EVALUATIONS, not a search).
DEFAULT_POLISH_GENES: tuple[str, ...] = (
    "sl_atr_mult", "target_rr", "min_atr_pips", "min_confluence",
)


@dataclass(frozen=True)
class PolishConfig:
    """Bounded polish parameters (sealed here)."""

    genes: tuple[str, ...] = DEFAULT_POLISH_GENES
    steps: int = 3              # coordinate descent passes (cheap by decree)
    step_frac: float = 0.10     # initial nudge, fraction of the bound span
    shrink: float = 0.5         # per-pass step shrink
    seed: int = 0

    def __post_init__(self):
        if self.steps < 1:
            raise ValueError("polish steps must be >= 1")
        if not (0.0 < self.step_frac <= 1.0):
            raise ValueError("step_frac must be in (0, 1]")
        if not (0.0 < self.shrink < 1.0):
            raise ValueError("shrink must be in (0, 1)")
        unknown = [g for g in self.genes if g not in GENE_BOUNDS_BY_NAME]
        if unknown:
            raise ValueError(f"polish genes are not mutable genes: {unknown}")


@dataclass
class PolishResult:
    """The honest record of one polish."""

    genome: StrategyGenome
    start_value: float
    best_value: float
    accepted: int
    evaluations: int

    @property
    def delta(self) -> float:
        return float(self.best_value - self.start_value)

    def to_dict(self) -> dict:
        return {"start_value": round(float(self.start_value), 6),
                "best_value": round(float(self.best_value), 6),
                "delta": round(self.delta, 6),
                "accepted": int(self.accepted),
                "evaluations": int(self.evaluations)}


def polish_genome(
    genome: StrategyGenome,
    objective,
    config: PolishConfig | None = None,
) -> PolishResult:
    """Return a polished genome (Lamarckian) plus its honest delta.

    ``objective`` maps a :class:`StrategyGenome` to a scalar (higher is better).
    Only the configured bounded genes are nudged; the polished values are written
    back with :func:`app.quant.genome.clamp_gene`, so no nudge can leave the law.
    """
    cfg = config or PolishConfig()
    rng = np.random.default_rng(cfg.seed)
    current = genome
    start_value = float(objective(current))
    best_value = start_value
    evaluations = 1
    accepted = 0
    step = cfg.step_frac

    for _ in range(cfg.steps):
        for gene in cfg.genes:
            bound = GENE_BOUNDS_BY_NAME[gene]
            span = float(bound.high) - float(bound.low)
            if span <= 0:
                continue
            base = float(getattr(current, gene))
            for direction in (+1.0, -1.0):
                candidate_value = clamp_gene(gene, base + direction * step * span)
                if candidate_value == base:
                    continue  # clamped back to the same value: no move
                candidate = replace(current, **{gene: candidate_value})
                evaluations += 1
                value = float(objective(candidate))
                if value > best_value:
                    best_value = value
                    current = candidate
                    base = candidate_value
                    accepted += 1
        step *= cfg.shrink

    return PolishResult(genome=current, start_value=start_value,
                        best_value=best_value, accepted=accepted,
                        evaluations=evaluations)
