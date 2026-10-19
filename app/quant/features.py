"""THE FEATURE BRIDGE -- one pipeline, many consumers (Mega Phase 2, Section D3).

Raw market data -> engineered features -> the ML families, the Cathedral's Column 7
(evidence) and the Dragon's context. ONE place computes the features, so a learned
model and a hand-crafted strategy read the SAME numbers (no train/serve skew).

Every feature is computed CAUSALLY from the execution frame: a feature at bar ``i``
reads only bars at or before ``i``. The matrix is a fixed, named column set, so the
ML models never disagree about feature order.

Honesty is binding: an absent primitive yields ``NaN`` in that cell (never a 0 that
looks like a measurement). Pure at import (Scar #6): the caller supplies the frames.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "FEATURE_NAMES",
    "feature_matrix",
    "latest_features",
]

# The sealed feature set. Order is part of the contract; ML models index by name.
FEATURE_NAMES: tuple[str, ...] = (
    "ret_1",
    "ret_4",
    "ret_16",
    "atr_pips",
    "ema_spread",
    "close_vs_ema",
    "rsi",
    "bb_pos",
    "range_pos",
    "volume_z",
)


def _rolling_mean(a: np.ndarray, w: int) -> np.ndarray:
    out = np.full(a.shape, np.nan, dtype="float64")
    if w <= 0:
        return out
    c = np.cumsum(np.nan_to_num(a, nan=0.0))
    out[w - 1:] = (c[w - 1:] - np.concatenate([[0.0], c[:-w]])) / w
    out[:w - 1] = np.nan
    return out


def _rolling_std(a: np.ndarray, w: int) -> np.ndarray:
    m = _rolling_mean(a, w)
    m2 = _rolling_mean(a * a, w)
    var = np.clip(m2 - m * m, 0.0, None)
    out = np.sqrt(var)
    out[~np.isfinite(m)] = np.nan
    return out


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    n = close.shape[0]
    out = np.full(n, np.nan, dtype="float64")
    if n < period + 1:
        return out
    diff = np.diff(close)
    gain = np.where(diff > 0, diff, 0.0)
    loss = np.where(diff < 0, -diff, 0.0)
    ag = float(np.mean(gain[:period]))
    al = float(np.mean(loss[:period]))
    for i in range(period, n):
        ag = (ag * (period - 1) + gain[i - 1]) / period
        al = (al * (period - 1) + loss[i - 1]) / period
        if al == 0:
            out[i] = 100.0 if ag > 0 else 50.0
        else:
            rs = ag / al
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def feature_matrix(F, *, ema_fast: int = 9, ema_slow: int = 21,
                   bb_period: int = 20, atr_window: int = 14) -> tuple[np.ndarray, list[str]]:
    """Build the ``(n_bars, n_features)`` causal feature matrix for one pair.

    Returns ``(matrix, names)`` where ``names == FEATURE_NAMES``. Every column is a
    float; unmeasured primitives are ``NaN``.
    """
    ex = F.exec
    close = np.asarray(ex["close"].to_numpy(), dtype="float64")
    high = np.asarray(ex["high"].to_numpy(), dtype="float64")
    low = np.asarray(ex["low"].to_numpy(), dtype="float64")
    vol = np.asarray(ex["volume"].to_numpy(), dtype="float64")
    n = close.shape[0]

    def lag(a, k):
        out = np.full(n, np.nan, dtype="float64")
        if 0 < k < n:
            out[k:] = a[:-k]
        return out

    ret_1 = np.divide(close - lag(close, 1), lag(close, 1),
                      out=np.full(n, np.nan), where=lag(close, 1) != 0)
    ret_4 = np.divide(close - lag(close, 4), lag(close, 4),
                      out=np.full(n, np.nan), where=lag(close, 4) != 0)
    ret_16 = np.divide(close - lag(close, 16), lag(close, 16),
                       out=np.full(n, np.nan), where=lag(close, 16) != 0)

    atr = np.asarray(F.atr, dtype="float64")
    atr_pips = np.asarray(F.atr_pips, dtype="float64")

    ema_f = np.asarray(F.structure_ema_fast, dtype="float64")
    ema_s = np.asarray(F.structure_ema_slow, dtype="float64")
    denom = np.where(np.abs(ema_s) > 0, np.abs(ema_s), np.nan)
    ema_spread = np.divide(ema_f - ema_s, denom)

    close_vs_ema = np.divide(close - ema_f,
                             np.where(np.abs(ema_f) > 0, np.abs(ema_f), np.nan))

    rsi = _rsi(close, 14)

    mid = _rolling_mean(close, bb_period)
    sd = _rolling_std(close, bb_period)
    bb_pos = np.divide(close - mid, 2.0 * sd,
                       out=np.full(n, np.nan), where=np.isfinite(sd) & (sd > 0))

    rh = np.full(n, np.nan, dtype="float64")
    rl = np.full(n, np.nan, dtype="float64")
    for i in range(bb_period - 1, n):
        rh[i] = np.max(high[i - bb_period + 1:i + 1])
        rl[i] = np.min(low[i - bb_period + 1:i + 1])
    rng = np.where((rh - rl) > 0, rh - rl, np.nan)
    range_pos = np.divide(close - rl, rng)

    vmean = _rolling_mean(vol, 20)
    vsd = _rolling_std(vol, 20)
    volume_z = np.divide(vol - vmean, vsd,
                         out=np.full(n, np.nan), where=np.isfinite(vsd) & (vsd > 0))

    cols = [ret_1, ret_4, ret_16, atr_pips, ema_spread, close_vs_ema,
            rsi, bb_pos, range_pos, volume_z]
    mat = np.column_stack(cols).astype("float64")
    # A row whose ATR is unmeasured is unusable by any consumer: keep it NaN-able
    # but never let a zero ATR masquerade as a measured quiet bar.
    mat[~np.isfinite(atr), 3] = np.nan
    return mat, list(FEATURE_NAMES)


def latest_features(F) -> dict:
    """The DICTIONARY of the most recent fully-measured feature row (or ``{}``).

    This is the Dragon's context and the Cathedral Column-7 evidence in one call.
    Honest: a NaN cell is dropped from the dict (the caller sees only measured
    features), and a frame too short yields ``{}``.
    """
    mat, names = feature_matrix(F)
    if mat.shape[0] == 0:
        return {}
    row = mat[-1]
    return {name: float(row[i]) for i, name in enumerate(names)
            if np.isfinite(row[i])}
