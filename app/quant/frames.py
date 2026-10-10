"""FRAMES & ALIGNMENT — the multi-timeframe triad the switchboard reads.

From the native M15 base we build the mandate triad by causal resample:

  EXECUTION = H1   (signals are generated here)
  STRUCTURE = H4   (trend alignment)
  TREND     = D1   (higher-timeframe context)

All resampling is right-closed / right-labeled on epoch boundaries (see
``app.core.data.resample``), so a higher-timeframe bar labeled at ``T`` contains
only base bars that closed in ``(T - duration, T]``. ``align_htf`` then maps a
higher-timeframe series onto execution bars using the LAST CLOSED higher bar
only (``htf_right_edge + htf_duration <= exec_ts``). A higher bar whose period
is still open at the execution time is invisible — this is the closed-bar law.

EXECUTION-H1 / ATR-M15 LAW LETTER. ATR(14) is defined on the NATIVE M15 series
(the Constitution's VNSB band is M15-defined). It is computed there and causally
aligned up to execution bars (the last closed M15 ATR at each H1 bar open), so
``frames.atr_pips`` is always an M15 ATR even though execution is H1.

Every frame product is registered in the future-leak detector; mutating M15 bars
after ``t`` must not change any aligned output at or before ``t``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core import data as data_mod

TF_MINUTES: dict[str, int] = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
EXECUTION_TF = "H1"
STRUCTURE_TF = "H4"
TREND_TF = "D1"
ATR_PERIOD = 14

__all__ = [
    "Frames",
    "TF_MINUTES",
    "EXECUTION_TF",
    "STRUCTURE_TF",
    "TREND_TF",
    "ATR_PERIOD",
    "build_frames",
    "align_htf",
    "m15_atr_aligned",
    "cached_frames",
    "clear_cache",
]


def _as_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Copy the canonical columns into a plain float/int frame."""
    out = df[["ts", "open", "high", "low", "close", "volume"]].copy()
    out["ts"] = out["ts"].astype("int64")
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = out[col].astype("float64")
    return out


def align_htf(exec_ts, htf_ts, htf_minutes: int, values) -> np.ndarray:
    """Map a higher-timeframe series onto execution bars, last-closed-only.

    For each execution timestamp ``t`` we take the higher bar with the greatest
    right edge ``T`` such that ``T + htf_minutes*60 <= t`` — i.e. a higher bar
    that has fully *completed* by ``t``. An execution bar earlier than the first
    fully-closed higher bar gets ``NaN``. Strictly causal.
    """
    exec_ts = np.asarray(exec_ts, dtype="int64")
    htf_ts = np.asarray(htf_ts, dtype="int64")
    values = np.asarray(values, dtype="float64")
    out = np.full(exec_ts.shape, np.nan, dtype="float64")
    if htf_ts.size == 0:
        return out
    # closed_by[k] = right edge T_k + duration; strictly increasing because
    # htf_ts is strictly increasing.
    closed_by = htf_ts + np.int64(htf_minutes) * np.int64(60)
    pos = np.searchsorted(closed_by, exec_ts, side="right") - 1
    valid = pos >= 0
    out[valid] = values[pos[valid]]
    return out


def m15_atr_aligned(base_ts, base_atr, exec_ts) -> np.ndarray:
    """Align the native M15 ATR up to execution bars (last closed M15 ATR).

    Each M15 value is treated as known at its own right edge; an execution bar
    reads the last M15 ATR whose right edge is at or before it. Strictly causal.
    """
    return align_htf(exec_ts, base_ts, 0, base_atr)


@dataclass(frozen=True)
class Frames:
    """The aligned timeframe triad plus the law-letter M15 ATR and the pip size.

    ``exec_*`` arrays are all the same length (one entry per H1 bar). ``pip``
    converts an ATR price distance into pips for the VNSB gate.
    """

    pair: str
    pip: float
    exec: pd.DataFrame
    structure: pd.DataFrame
    trend: pd.DataFrame
    m15: pd.DataFrame
    atr: np.ndarray
    atr_pips: np.ndarray
    structure_close: np.ndarray
    structure_ema_fast: np.ndarray
    structure_ema_slow: np.ndarray
    trend_close: np.ndarray
    trend_ema_fast: np.ndarray
    trend_ema_slow: np.ndarray

    def __len__(self) -> int:
        return len(self.exec)


def build_frames(m15: pd.DataFrame, pair: str, pip: float) -> Frames:
    """Build the aligned triad from a native M15 frame. Pure.

    ``m15`` must be a validated canonical frame. ``pair``/``pip`` are carried
    through for downstream gates and pip conversion.
    """
    from app.quant import indicators  # local import keeps the import graph flat

    base = _as_frame(m15)
    exec_df = data_mod.resample(base, EXECUTION_TF)
    struct_df = data_mod.resample(base, STRUCTURE_TF)
    trend_df = data_mod.resample(base, TREND_TF)

    # Native M15 ATR (the law's letter), aligned up to execution bars.
    base_atr = indicators.atr(
        base["high"].to_numpy(), base["low"].to_numpy(), base["close"].to_numpy(), ATR_PERIOD
    )
    atr = m15_atr_aligned(base["ts"].to_numpy(), base_atr, exec_df["ts"].to_numpy())

    def _ema(df, period):
        return indicators.ema(df["close"].to_numpy(), period)

    struct_close = align_htf(
        exec_df["ts"], struct_df["ts"], TF_MINUTES[STRUCTURE_TF], struct_df["close"].to_numpy()
    )
    trend_close = align_htf(
        exec_df["ts"], trend_df["ts"], TF_MINUTES[TREND_TF], trend_df["close"].to_numpy()
    )
    # EMAs are computed on the higher frames themselves, then aligned closed-only.
    struct_ema_fast = align_htf(
        exec_df["ts"], struct_df["ts"], TF_MINUTES[STRUCTURE_TF], _ema(struct_df, 21)
    )
    struct_ema_slow = align_htf(
        exec_df["ts"], struct_df["ts"], TF_MINUTES[STRUCTURE_TF], _ema(struct_df, 50)
    )
    trend_ema_fast = align_htf(
        exec_df["ts"], trend_df["ts"], TF_MINUTES[TREND_TF], _ema(trend_df, 10)
    )
    trend_ema_slow = align_htf(
        exec_df["ts"], trend_df["ts"], TF_MINUTES[TREND_TF], _ema(trend_df, 30)
    )

    with np.errstate(invalid="ignore", divide="ignore"):
        atr_pips = atr / pip if pip > 0 else np.full(atr.shape, np.nan)

    return Frames(
        pair=pair,
        pip=pip,
        exec=exec_df,
        structure=struct_df,
        trend=trend_df,
        m15=base,
        atr=atr,
        atr_pips=atr_pips,
        structure_close=struct_close,
        structure_ema_fast=struct_ema_fast,
        structure_ema_slow=struct_ema_slow,
        trend_close=trend_close,
        trend_ema_fast=trend_ema_fast,
        trend_ema_slow=trend_ema_slow,
    )


# ---------------------------------------------------------------------------
# Optional explicit cache — never implicit global state.
# ---------------------------------------------------------------------------
_CACHE: dict[tuple, Frames] = {}


def cached_frames(m15: pd.DataFrame, pair: str, pip: float, key: tuple | None = None) -> Frames:
    """Return a cached :class:`Frames` for ``key``, building it once.

    The cache is opt-in: callers pass a stable ``key``. It is module-level but
    explicit — :func:`clear_cache` empties it, and nothing depends on it being
    warm. Purity of :func:`build_frames` is unaffected.
    """
    cache_key = key if key is not None else (pair, float(pip), int(len(m15)))
    if cache_key not in _CACHE:
        _CACHE[cache_key] = build_frames(m15, pair, pip)
    return _CACHE[cache_key]


def clear_cache() -> None:
    """Empty the explicit frames cache."""
    _CACHE.clear()
