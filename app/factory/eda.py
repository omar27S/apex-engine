"""R71a — BAYES-GENE MEMORY (EDA-lite).

The dead teach, the living guide. Per family, per gene, we keep a RUNNING
DISTRIBUTION of the values the SURVIVORS carried. Breeding then draws a NEW gene
from the survivors' distribution (a fitted normal, clamped into the sealed
bounds) instead of the uniform prior. A gene with no surviving observations
returns ``None`` — the caller falls back to the uniform draw, fail-closed
(ScaR #1: never invent a distribution from nothing).

This is "EDA-lite": an Estimation-of-Distribution pass that biases exploration
toward the region the survivors occupy, without abandoning the bounds or the law.

Deterministic under the caller's rng. Pure at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.quant.genome import GENE_BOUNDS_BY_NAME

__all__ = ["GeneMemory", "MIN_OBSERVATIONS"]

# Below this many survivor observations a gene's distribution is noise; fall back
# to the uniform prior rather than fit a normal to one point.
MIN_OBSERVATIONS = 3

# The fitted std is floored to a fraction of the bound span so the memory never
# collapses to a point (which would forbid exploration).
_MIN_SPAN_FRACTION = 0.05


@dataclass
class GeneMemory:
    """Running per-(family, gene) summary of surviving gene values."""

    # family -> gene -> list of observed values (kept raw so the fit is honest;
    # the populations here are hundreds, not millions, so raw storage is cheap).
    _obs: dict[str, dict[str, list[float]]] = field(default_factory=dict)

    def observe(self, survivors) -> None:
        """Fold a generation's survivors into the memory (int/float genes only)."""
        for g in survivors:
            family = getattr(g, "family", None)
            if not family:
                continue
            fam = self._obs.setdefault(family, {})
            for name in GENE_BOUNDS_BY_NAME:
                fam.setdefault(name, [])
                try:
                    value = float(getattr(g, name))
                except (TypeError, ValueError, AttributeError):
                    continue
                if value != value:  # NaN never enters memory
                    continue
                fam[name].append(value)

    def count(self, family: str, gene: str) -> int:
        return len(self._obs.get(family, {}).get(gene, ()))

    def mean_std(self, family: str, gene: str) -> tuple[float, float] | None:
        """Fitted (mean, std) for a gene, or None if under-observed (fail-closed)."""
        values = self._obs.get(family, {}).get(gene, ())
        if len(values) < MIN_OBSERVATIONS:
            return None
        arr = np.asarray(values, dtype="float64")
        bound = GENE_BOUNDS_BY_NAME[gene]
        span = float(bound.high) - float(bound.low)
        std = float(arr.std())
        floor = _MIN_SPAN_FRACTION * span
        return float(arr.mean()), max(std, floor)

    def sample_gene(self, family: str, gene: str, rng: np.random.Generator):
        """Draw a new gene value from the survivors' distribution, or None.

        The draw is clamped into the sealed bounds (THE LAW, inside the bounds).
        Returns ``None`` when the gene is under-observed so the caller may use the
        uniform prior.
        """
        fit = self.mean_std(family, gene)
        if fit is None:
            return None
        mean, std = fit
        value = float(rng.normal(mean, std))
        from app.quant.genome import clamp_gene
        return clamp_gene(gene, value)

    def snapshot(self) -> dict:
        """A compact, serialisable summary for the audit."""
        out: dict = {}
        for family, genes in sorted(self._obs.items()):
            fam: dict = {}
            for gene, values in sorted(genes.items()):
                if len(values) < MIN_OBSERVATIONS:
                    continue
                fit = self.mean_std(family, gene)
                if fit is None:
                    continue
                fam[gene] = {"n": len(values), "mean": round(fit[0], 4),
                             "std": round(fit[1], 4)}
            if fam:
                out[family] = fam
        return out
