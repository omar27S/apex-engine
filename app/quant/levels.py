"""STRUCTURAL LEVELS — the geometry a strategy reasons about.

Each source returns a :class:`LevelSet`: four same-length arrays
``(swing_low, swing_high, tgt_high, tgt_low)``. ``swing_low``/``swing_high`` are
the reference edges of the structure; ``tgt_high``/``tgt_low`` are the measured-
move projections beyond them (edge +/- the structure's own spread). All are
``NaN`` where the structure does not exist yet.

Every function is strictly causal: windows are shifted so a level at index ``i``
is built only from bars ``<= i`` (see ``tests/quant/test_causality.py``).
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from app.quant import indicators

__all__ = [
    "LevelSet",
    "swing_levels",
    "donchian_levels",
    "equal_hl_levels",
    "fvg_levels",
    "round_levels",
]

DEFAULT_ROUND_STEP_PIPS = 50


class LevelSet(NamedTuple):
    """The four level arrays a strategy consumes, plus the source label."""

    swing_low: np.ndarray
    swing_high: np.ndarray
    tgt_high: np.ndarray
    tgt_low: np.ndarray
    source: str


def _ffill(values: np.ndarray) -> np.ndarray:
    """Forward-fill ``NaN`` with the last finite value (causal; leading stays NaN)."""
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(values)
    if not finite.any():
        return values.copy()
    idx = np.where(finite, np.arange(len(values)), 0)
    np.maximum.accumulate(idx, out=idx)
    out = values[idx]
    out[: int(np.argmax(finite))] = np.nan
    return out


def _levels(swing_low, swing_high, source: str) -> LevelSet:
    """Build a :class:`LevelSet`, projecting targets by the level spread."""
    low = np.asarray(swing_low, dtype=np.float64)
    high = np.asarray(swing_high, dtype=np.float64)
    spread = high - low
    return LevelSet(low, high, high + spread, low - spread, source)


def swing_levels(high, low, lookback: int = 20) -> LevelSet:
    """Prior rolling swing extreme (shifted one bar).

    ``swing_high`` is the max high and ``swing_low`` the min low over the
    ``lookback`` bars strictly before ``i``. ``NaN`` until a full window exists.
    """
    upper, lower = indicators.donchian(high, low, lookback, shift=1)
    return _levels(lower, upper, "swing")


def donchian_levels(high, low, period: int = 20) -> LevelSet:
    """Donchian channel (shifted one bar) as the structural edges."""
    upper, lower = indicators.donchian(high, low, period, shift=1)
    return _levels(lower, upper, "donchian")


def equal_hl_levels(high, low, pip: float, window: int = 40,
                    tol_pips: float = 1.0) -> LevelSet:
    """Equal-highs / equal-lows liquidity pools over a doubled window.

    Uses a ``2*window`` detection window and projects targets by the pool
    window's own range. ``NaN`` where no pool exists. Strictly causal (the pool
    window is shifted by one bar).
    """
    eq_high, eq_low, _, _ = indicators.equal_highs_lows_pool(
        high, low, pip, window=2 * window, tol_pips=tol_pips
    )
    upper, lower = indicators.donchian(high, low, 2 * window, shift=1)
    swing_high = np.where(np.isfinite(eq_high), eq_high, np.nan)
    swing_low = np.where(np.isfinite(eq_low), eq_low, np.nan)
    spread = np.where(
        np.isfinite(swing_high) & np.isfinite(swing_low),
        swing_high - swing_low,
        upper - lower,
    )
    tgt_high = swing_high + spread
    tgt_low = swing_low - spread
    return LevelSet(swing_low, swing_high, tgt_high, tgt_low, "equal_hl")


def fvg_levels(high, low, min_gap: float = 0.0) -> LevelSet:
    """Fair-value-gap edges, causal, forward-filled to the latest gap.

    A bullish FVG at bar ``i`` exists when ``high[i-2] < low[i]``: the gap spans
    ``[high[i-2], low[i]]``. A bearish FVG exists when ``low[i-2] > high[i]``:
    the gap spans ``[high[i], low[i-2]]``. The most recent qualifying gap's
    lower/upper edges are carried forward. Only bars ``i`` and ``i-2`` are used,
    so the reference is visible exactly at ``i``. ``NaN`` before the first gap.
    """
    h = np.asarray(high, dtype=np.float64)
    low_a = np.asarray(low, dtype=np.float64)
    n = len(h)
    bottom = np.full(n, np.nan)
    top = np.full(n, np.nan)
    if n >= 3:
        bull = (h[:-2] < low_a[2:]) & ((low_a[2:] - h[:-2]) > min_gap)
        bear = (low_a[:-2] > h[2:]) & ((low_a[:-2] - h[2:]) > min_gap)
        index = np.arange(2, n)
        gap_bottom = np.where(bull, h[:-2], np.where(bear, h[2:], np.nan))
        gap_top = np.where(bull, low_a[2:], np.where(bear, low_a[:-2], np.nan))
        bottom[index] = gap_bottom
        top[index] = gap_top
    return _levels(_ffill(bottom), _ffill(top), "fvg")


def round_levels(close, pip: float, step_pips: int = DEFAULT_ROUND_STEP_PIPS
                 ) -> LevelSet:
    """Psychological round-number grid scaled by pip size.

    ``grid = step_pips * pip``. The nearest grid line at/above price is
    ``swing_high`` and the nearest at/below is ``swing_low``; targets are the
    next lines outward. Computed from the bar's own close — strictly causal.
    ``NaN`` if ``pip <= 0`` or ``step_pips <= 0``.
    """
    c = np.asarray(close, dtype=np.float64)
    n = len(c)
    if pip <= 0 or step_pips <= 0:
        return LevelSet(
            np.full(n, np.nan), np.full(n, np.nan),
            np.full(n, np.nan), np.full(n, np.nan), "round",
        )
    grid = step_pips * pip
    scaled = c / grid
    above = np.ceil(scaled - 1e-9) * grid
    below = np.floor(scaled + 1e-9) * grid
    return LevelSet(below, above, above + grid, below - grid, "round")
