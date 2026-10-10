"""R71b — THE CMA-ES REFINER.

Every finalist is parameter-refined by a bounded CMA-ES pass before the crown
verdict — no finalist faces the unseen gauntlet untrained, and a good genome is
not lost to a bad coordinate.

CMA-ES (Covariance Matrix Adaptation Evolution Strategy) is the strongest
derivative-free continuous optimizer known: it adapts a multivariate normal
search distribution (mean + full covariance) to the objective's local geometry,
using ranked updates and cumulative step-size control. Gradient-free, which is
mandatory here — the fitness landscape is a black box of discrete simulation.

This is a SELF-CONTAINED, dependency-free (numpy only) implementation over a
BOUNDED numeric vector. The caller maps a genome to a vector of mutable numeric
genes, supplies an objective, and maps the refined vector back — the bounds (the
Constitution's gene bounds) are enforced by clamping inside :func:`refine`, so a
refined gene can never leave its sealed space.

Bounded, deterministic under a seed, and honest: it returns the ACTUAL best
objective achieved and the improvement delta, never a fabricated gain.

Pure at import; no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["CMAConfig", "CMAResult", "refine"]


@dataclass(frozen=True)
class CMAConfig:
    """Bounded CMA-ES parameters (all sealed here)."""

    population: int = 16          # lambda (>= 2)
    generations: int = 30         # bounded pass, never a long search
    sigma0_frac: float = 0.15     # initial step, fraction of each bound span
    seed: int = 0

    def __post_init__(self):
        if self.population < 2:
            raise ValueError("CMA population must be >= 2")
        if self.generations < 1:
            raise ValueError("CMA generations must be >= 1")
        if not (0.0 < self.sigma0_frac <= 1.0):
            raise ValueError("sigma0_frac must be in (0, 1]")


@dataclass
class CMAResult:
    """The honest record of one refinement pass."""

    best_x: np.ndarray
    best_value: float
    start_value: float
    improvements: int          # candidates that beat the start
    evaluations: int
    generations: int

    @property
    def delta(self) -> float:
        return float(self.best_value - self.start_value)

    def to_dict(self) -> dict:
        return {
            "start_value": round(float(self.start_value), 6),
            "best_value": round(float(self.best_value), 6),
            "delta": round(self.delta, 6),
            "improvements": int(self.improvements),
            "evaluations": int(self.evaluations),
            "generations": int(self.generations),
            "best_x": [round(float(v), 6) for v in np.asarray(self.best_x)],
        }


def _weights(mu: int) -> np.ndarray:
    raw = np.array([np.log(mu + 0.5) - np.log(i + 1) for i in range(mu)])
    return raw / raw.sum()


def refine(
    x0,
    objective,
    low,
    high,
    config: CMAConfig | None = None,
) -> CMAResult:
    """Refine ``x0`` toward a higher ``objective``, clamped to ``[low, high]``.

    ``objective`` maps a 1-D array to a scalar (higher is better). ``low``/``high``
    are the per-dimension sealed bounds — every candidate and the final result are
    clamped into them, so the Constitution is never violated by the refiner.

    The best point ever visited is returned (elitist), and ``start_value`` is the
    objective at ``x0`` so the caller sees the true delta. If nothing improves,
    ``best_x`` equals ``x0`` and ``delta`` is 0.0 — the honest outcome.
    """
    cfg = config or CMAConfig()
    x0 = np.asarray(x0, dtype="float64").copy()
    low = np.asarray(low, dtype="float64")
    high = np.asarray(high, dtype="float64")
    if x0.shape != low.shape or low.shape != high.shape:
        raise ValueError("x0, low, high must share a shape")
    n = x0.size
    rng = np.random.default_rng(cfg.seed)

    def clip(x):
        return np.minimum(np.maximum(x, low), high)

    start_value = float(objective(clip(x0)))
    mean = clip(x0)
    sigma = float(cfg.sigma0_frac) * (high - low)
    sigma = np.where(sigma <= 0, 1e-9, sigma)
    C = np.eye(n)
    pc = np.zeros(n)
    ps = np.zeros(n)

    mu = cfg.population // 2
    weights = _weights(mu)
    mueff = 1.0 / np.sum(weights ** 2)
    cc = 4.0 / (n + 4.0)
    cs = (mueff + 2.0) / (n + mueff + 5.0)
    c1 = 2.0 / ((n + 1.3) ** 2 + mueff)
    cmu = min(1.0 - c1, 2.0 * (mueff - 2.0 + 1.0 / mueff) / ((n + 2.0) ** 2 + mueff))
    damps = 1.0 + 2.0 * max(0.0, np.sqrt((mueff - 1.0) / (n + 1.0)) - 1.0) + cs
    chi_n = np.sqrt(n) * (1.0 - 1.0 / (4.0 * n) + 1.0 / (21.0 * n * n))

    best_x = clip(x0)
    best_value = start_value
    improvements = 0
    evaluations = 1

    for it in range(cfg.generations):
        try:
            L = np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            C = np.eye(n)
            L = np.eye(n)
        z = rng.standard_normal((cfg.population, n))
        y = z @ L.T
        candidates = clip(mean + sigma * y)
        values = np.array([float(objective(c)) for c in candidates])
        evaluations += cfg.population

        idx = np.argsort(values)[::-1]  # descending: best first
        if values[idx[0]] > best_value:
            best_value = float(values[idx[0]])
            best_x = candidates[idx[0]].copy()
        improvements += int(np.sum(values > start_value))

        # Recombine the top-mu.
        xsel = candidates[idx[:mu]]
        old_mean = mean.copy()
        mean = np.sum(weights[:, None] * xsel, axis=0)

        y_w = (mean - old_mean) / sigma
        # Cumulative step-size path.
        ps = (1 - cs) * ps + np.sqrt(cs * (2 - cs) * mueff) * np.linalg.solve(L, y_w)
        norm_ps = np.linalg.norm(ps)
        chi_n_gen = chi_n * np.sqrt(1 - (1 - cs) ** (2 * (it + 1)))
        hsig = norm_ps / chi_n_gen < (1.4 + 2.0 / (n + 1.0))
        pc = (1 - cc) * pc + (1.0 if hsig else 0.0) * np.sqrt(cc * (2 - cc) * mueff) * y_w

        # Covariance update (rank-one + rank-mu).
        artmp = (xsel - old_mean) / sigma
        C = ((1 - c1 - cmu) * C
             + c1 * (np.outer(pc, pc) + (0.0 if hsig else cc * (2 - cc)) * C)
             + cmu * (artmp.T @ (weights[:, None] * artmp)))
        C = (C + C.T) / 2.0        # keep it symmetric
        sigma = sigma * np.exp((cs / damps) * (norm_ps / chi_n - 1.0))
        sigma = np.where(sigma <= 0, 1e-12, sigma)
        mean = clip(mean)

    return CMAResult(best_x=best_x, best_value=best_value, start_value=start_value,
                     improvements=improvements, evaluations=evaluations,
                     generations=cfg.generations)
