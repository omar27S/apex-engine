"""R79 — THE SURROGATE GATE (the cheap pre-screen).

Evaluating a genome on the real staircase is expensive. A cheap SURROGATE learns
the result-memory corpus (genome features + family + realm + prior results) and
pre-screens: candidates the surrogate predicts FAR BELOW the staircase floor are
SKIPPED from the expensive rounds — bounded to at most :data:`MAX_SKIP_FRACTION`
(30%) of a batch. It changes only EVALUATION ORDER, never a verdict: the surrogate
is structurally incapable of touching sizing, crowns, or deaths (it is never on
those code paths and exports no such function).

Honesty rules, enforced here:

* the model is a small deterministic gradient-boosted regression tree (squared
  loss) — no third-party dependency, reproducible under ``seed``;
* skipping is only allowed when a fit EXISTS and the predicted value is below the
  floor; with no model, NOTHING is skipped (fail-open to full evaluation);
* every report carries the skip-rate and the hit/miss audit (a hit is a skipped
  candidate that was in fact below the floor; a miss is one wrongly skipped);
* the surrogate is EXCLUDED from run identity: it never enters a config signature
  (determinism preserved). ``identity_token`` is empty for that reason.

Retraining is WEEKLY (the corpus grows nightly); :func:`should_retrain` is a pure
scheduling check, not a hidden timer.

Pure at import; no I/O. Build Mode: pure arithmetic over matrices.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "MAX_SKIP_FRACTION",
    "RETRAIN_PERIOD_NIGHTS",
    "FEATURE_NAMES",
    "SurrogateError",
    "RegressionTree",
    "Surrogate",
    "skip_mask",
    "should_retrain",
    "matrix_from_rows",
    "flight_record",
]

MAX_SKIP_FRACTION: float = 0.30
RETRAIN_PERIOD_NIGHTS: int = 7

# Genome features + family + realm + prior results (the directive's feature set).
# The first eight are the canonical outcome-corpus features; ``family_bucket`` and
# ``realm_bucket`` add the categorical identity; ``prior_net_r`` is the candidate's
# last known result (0.0 when unknown).
FEATURE_NAMES: tuple[str, ...] = (
    "aos", "domain_agreement", "session", "regime_percentile", "trust",
    "funnel_stage", "density_class", "spread_state",
    "family_bucket", "realm_bucket", "prior_net_r",
)


class SurrogateError(ValueError):
    """A surrogate request was refused (fail-closed)."""


class RegressionTree:
    """A depth-limited regression tree over squared loss (the boosting base)."""

    def __init__(self, max_depth: int = 2) -> None:
        if max_depth < 1:
            raise SurrogateError("max_depth must be >= 1 (fail-closed)")
        self.max_depth = int(max_depth)
        self.root: dict | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RegressionTree":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim != 2 or y.ndim != 1 or X.shape[0] != y.shape[0]:
            raise SurrogateError("X (n,f) and y (n,) must agree (fail-closed)")
        if X.shape[0] == 0:
            raise SurrogateError("cannot fit a tree on zero rows (fail-closed)")
        self.root = self._grow(X, y, depth=0)
        return self

    def _grow(self, X: np.ndarray, y: np.ndarray, depth: int) -> dict:
        node = {"value": float(y.mean()), "feature": None, "threshold": None,
                "left": None, "right": None}
        if depth >= self.max_depth or X.shape[0] < 2 or float(y.std()) == 0.0:
            return node
        best = None  # (sse, feature, threshold, left_idx, right_idx)
        n_features = X.shape[1]
        for f in range(n_features):
            col = X[:, f]
            uniq = np.unique(col)
            if uniq.size < 2:
                continue
            # Try midpoints between consecutive distinct values.
            thresholds = (uniq[:-1] + uniq[1:]) / 2.0
            for t in thresholds:
                left = col <= t
                nl = int(left.sum())
                if nl == 0 or nl == X.shape[0]:
                    continue
                yl, yr = y[left], y[~left]
                sse = float(((yl - yl.mean()) ** 2).sum()
                            + ((yr - yr.mean()) ** 2).sum())
                if best is None or sse < best[0] - 1e-12:
                    best = (sse, f, float(t), left)
        if best is None:
            return node
        _, f, t, left = best
        node["feature"] = int(f)
        node["threshold"] = float(t)
        node["left"] = self._grow(X[left], y[left], depth + 1)
        node["right"] = self._grow(X[~left], y[~left], depth + 1)
        return node

    def predict_one(self, row: np.ndarray) -> float:
        node = self.root
        while node and node["feature"] is not None:
            node = node["left"] if row[node["feature"]] <= node["threshold"] \
                else node["right"]
        return float(node["value"]) if node else 0.0

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return np.array([self.predict_one(r) for r in X], dtype=float)


class Surrogate:
    """A gradient-boosted regression surrogate (deterministic under ``seed``)."""

    def __init__(self, *, n_estimators: int = 30, learning_rate: float = 0.1,
                 max_depth: int = 2, seed: int = 0) -> None:
        if n_estimators < 1:
            raise SurrogateError("n_estimators must be >= 1 (fail-closed)")
        self.n_estimators = int(n_estimators)
        self.learning_rate = float(learning_rate)
        self.max_depth = int(max_depth)
        self.seed = int(seed)
        self.base_: float = 0.0
        self.trees_: list[RegressionTree] = []
        self.fitted_: bool = False

    def fit(self, X, y) -> "Surrogate":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.shape[0] != y.shape[0] or X.shape[0] == 0:
            raise SurrogateError("X and y must be non-empty and agree (fail-closed)")
        self.base_ = float(y.mean())
        pred = np.full(y.shape, self.base_, dtype=float)
        self.trees_ = []
        for _ in range(self.n_estimators):
            residual = y - pred
            tree = RegressionTree(max_depth=self.max_depth).fit(X, residual)
            self.trees_.append(tree)
            pred = pred + self.learning_rate * tree.predict(X)
        self.fitted_ = True
        return self

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if not self.fitted_:
            raise SurrogateError("the surrogate is not fitted (fail-closed)")
        pred = np.full(X.shape[0], self.base_, dtype=float)
        for tree in self.trees_:
            pred = pred + self.learning_rate * tree.predict(X)
        return pred

    def identity_token(self) -> str:
        """R79 — the surrogate is EXCLUDED from run identity: always empty."""
        return ""


def skip_mask(predicted, floor: float, *,
              max_skip_fraction: float = MAX_SKIP_FRACTION) -> np.ndarray:
    """Which candidates are skipped (predicted far below ``floor``), bounded.

    Skips are chosen as the ``k`` LOWEST-predicted candidates below ``floor``,
    where ``k <= ceil(max_skip_fraction * n)``. A candidate at or above the floor is
    NEVER skipped. Returns a boolean array (True = skip).
    """
    if not (0.0 <= max_skip_fraction < 1.0):
        raise SurrogateError("max_skip_fraction must be in [0,1) (fail-closed)")
    pred = np.asarray(predicted, dtype=float)
    n = pred.shape[0]
    mask = np.zeros(n, dtype=bool)
    if n == 0:
        return mask
    below = np.where(pred < float(floor))[0]
    if below.size == 0:
        return mask
    k = int(np.ceil(max_skip_fraction * n))
    if k <= 0:
        return mask
    order = below[np.argsort(pred[below], kind="stable")]
    chosen = order[:k]
    mask[chosen] = True
    return mask


def should_retrain(last_train_night: int | None, current_night: int,
                   *, period: int = RETRAIN_PERIOD_NIGHTS) -> bool:
    """R79 — weekly retrain check (pure scheduling, no hidden timer)."""
    if period < 1:
        raise SurrogateError("retrain period must be >= 1 (fail-closed)")
    if last_train_night is None:
        return True
    return (int(current_night) - int(last_train_night)) >= period


def matrix_from_rows(rows, *, realm_of=None, prior_net_r_of=None) -> tuple:
    """Build ``(X, y)`` from outcome-corpus rows for the surrogate.

    ``rows`` are :class:`app.pyramid.outcome_corpus.OutcomeRow` (they carry
    ``features`` and ``net_r``). ``realm_of`` / ``prior_net_r_of`` are optional
    callables adding the realm bucket and the prior result. Deterministic.
    """
    from app.pyramid.outcome_corpus import family_bucket

    X: list[list[float]] = []
    y: list[float] = []
    for r in rows:
        vec = [float(x) for x in r.features.vector()]
        fam = str(getattr(r, "family", ""))
        realm = ""
        if realm_of is not None:
            try:
                realm = str(realm_of(r))
            except Exception:
                realm = ""
        prior = 0.0
        if prior_net_r_of is not None:
            try:
                prior = float(prior_net_r_of(r))
            except Exception:
                prior = 0.0
        # realm_bucket: a stable [0,1] bucket over a fixed realm vocabulary.
        realm_bucket = _realm_bucket(realm)
        X.append(vec + [family_bucket(fam), realm_bucket, prior])
        y.append(float(getattr(r, "net_r", 0.0)))
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


_REALM_ORDER = sorted((
    "trend", "reversion", "breakout", "momentum", "volatility", "smc",
    "pattern", "confluence", "statistical", "ensemble", "mixed",
))


def _realm_bucket(realm: str) -> float:
    n = len(_REALM_ORDER)
    if n <= 1 or realm not in _REALM_ORDER:
        return 0.5
    return _REALM_ORDER.index(realm) / (n - 1)


def flight_record(*, fitted: bool, n_candidates: int, skipped: int,
                  hits: int, misses: int) -> dict:
    """R79 — the per-report audit row: skip-rate and the hit/miss stats.

    A HIT is a skipped candidate that was in fact below the floor (the skip was
    right); a MISS is a skipped candidate that was at/above the floor (a wrong
    skip). With no fitted model, ``fitted=False`` and zero skips.
    """
    n = int(n_candidates)
    return {
        "surrogate_fitted": bool(fitted),
        "candidates": n,
        "skipped": int(skipped),
        "skip_rate": (int(skipped) / n) if n else 0.0,
        "skip_bound": MAX_SKIP_FRACTION,
        "hits": int(hits),
        "misses": int(misses),
        "hit_rate": (int(hits) / int(skipped)) if skipped else None,
        "in_identity": False,   # R79 — excluded from run identity
    }
