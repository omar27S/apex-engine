"""R72 — ADAPTIVE ENTROPY.

Population diversity is measured every generation in SIGNATURE space: the
Shannon entropy of the signature distribution, normalized to [0, 1] by the
population size. Mutation rates then auto-scale:

* LOW diversity (a converged, clone-y population) -> AGGRESSIVE exploration;
* HIGH diversity (a healthy, spread population) -> REFINEMENT.

This is a pure control law: given an entropy reading it returns the mutation
rate to use. It never fabricates diversity — the entropy is computed from the
real signatures the caller hands in.

Pure at import; deterministic.
"""

from __future__ import annotations

import math
from collections import Counter

__all__ = [
    "normalized_entropy",
    "adaptive_mutation_rate",
    "EntropyReading",
    "LOW_DIVERSITY",
    "HIGH_DIVERSITY",
]

# Thresholds on NORMALIZED entropy. Below LOW the population is dangerously
# cloned; above HIGH it is healthy.
LOW_DIVERSITY = 0.45
HIGH_DIVERSITY = 0.75

# Mutation-rate envelope (the sealed breeding rate is 0.25; these bound the
# adaptive excursion well inside a sane range).
RATE_MIN = 0.10
RATE_BASE = 0.25
RATE_MAX = 0.60


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def normalized_entropy(signatures: list[str]) -> float:
    """Shannon entropy of the signature distribution, normalized to [0, 1].

    0.0 = every genome identical; 1.0 = every genome unique. An empty or
    single-genome population is 0.0 (no diversity — the honest reading).
    """
    n = len(signatures)
    if n <= 1:
        return 0.0
    counts = Counter(signatures)
    entropy = 0.0
    for c in counts.values():
        p = c / n
        entropy -= p * math.log(p)
    max_entropy = math.log(n)  # uniform over n distinct signatures
    if max_entropy <= 0:
        return 0.0
    return _clamp01(entropy / max_entropy)


def adaptive_mutation_rate(
    signatures: list[str],
    *,
    low: float = LOW_DIVERSITY,
    high: float = HIGH_DIVERSITY,
    rate_min: float = RATE_MIN,
    rate_base: float = RATE_BASE,
    rate_max: float = RATE_MAX,
) -> float:
    """Map a live entropy reading to a mutation rate (R72).

    Below ``low`` -> linearly up toward ``rate_max``; above ``high`` -> linearly
    down toward ``rate_min``; in between -> the base rate. Monotone DECREASING in
    entropy (more diversity => less mutation).
    """
    if not (0.0 <= low < high <= 1.0):
        raise ValueError(f"need 0 <= low < high <= 1, got low={low} high={high}")
    if not (0.0 < rate_min <= rate_base <= rate_max):
        raise ValueError("need 0 < rate_min <= rate_base <= rate_max")
    h = normalized_entropy(signatures)
    if h >= high:
        return rate_min
    if h <= low:
        return rate_max
    # Piecewise-linear, anchored at the band midpoint where the base rate holds.
    mid = (low + high) / 2.0
    if h < mid:
        t = (h - low) / (mid - low)          # 0 at low, 1 at mid
        return rate_max - t * (rate_max - rate_base)
    t = (h - mid) / (high - mid)             # 0 at mid, 1 at high
    return rate_base - t * (rate_base - rate_min)


class EntropyReading:
    """A named reading for the audit: entropy in, rate out, plus the band."""

    __slots__ = ("entropy", "rate", "band")

    def __init__(self, signatures: list[str]) -> None:
        self.entropy = normalized_entropy(signatures)
        self.rate = adaptive_mutation_rate(signatures)
        if self.entropy <= LOW_DIVERSITY:
            self.band = "explore"
        elif self.entropy >= HIGH_DIVERSITY:
            self.band = "refine"
        else:
            self.band = "balanced"

    def to_dict(self) -> dict:
        return {"entropy": round(self.entropy, 4), "mutation_rate": round(self.rate, 4),
                "band": self.band}
