"""SMC / ICT PRIMITIVES — the shared structural vocabulary.

Pure, causal, and built ONLY from ``indicators.py`` / ``levels.py`` primitives
(no duplicated math). These are the shared building blocks the Phase 2.2b
families consume; the dispatcher owns the gate stack.

Every product is registered in the future-leak detector.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import NamedTuple

import numpy as np
import pandas as pd

from app.quant import indicators as ind

__all__ = [
    "bos_choch",
    "premium_discount",
    "fvg_mask",
    "liquidity_pool",
    "displacement",
    "order_block",
    "killzone_mask",
    "recent",
    "SmcStructure",
    "build_structure",
    "clear_structure_cache",
]


def _n(values) -> np.ndarray:
    return np.asarray(values, dtype="float64")


def recent(mask: np.ndarray, lookback: int) -> np.ndarray:
    """True at ``i`` when ``mask`` fired at any ``j`` in ``(i-lookback, i]``.

    The public trailing-window primitive: a setup whose stages occupy different
    bars (sweep then reclaim, break then retrace) is expressed by OR-ing the
    earlier stage over its lookback. Strictly causal (the window ends at ``i``);
    vectorized with a prefix sum.
    """
    n = len(mask)
    out = np.zeros(n, dtype=bool)
    if lookback < 1 or n == 0:
        return out
    idx = np.arange(n)
    prefix = np.concatenate([[0], np.cumsum(mask.astype(np.int64))])
    lo = np.maximum(idx - lookback + 1, 0)
    out = (prefix[idx + 1] - prefix[lo]) > 0
    return out


# ---------------------------------------------------------------------------
# Break of structure / change of character.
# ---------------------------------------------------------------------------
def bos_choch(pivot_high, pivot_low, close, slow_ema):
    """BOS (continuation) and CHOCH (reversal) breaks of the last confirmed pivot.

    ``pivot_high``/``pivot_low`` are the forward-filled last confirmed swing
    levels (from :func:`indicators.confirmed_pivots`); ``slow_ema`` defines the
    prevailing leg (price above = up-leg). Returns ``(bos_long, bos_short,
    choch_long, choch_short)``.

    * BOS long  = close breaks the last pivot HIGH while the leg is already up.
    * BOS short = close breaks the last pivot LOW while the leg is already down.
    * CHOCH long/short = the same break AGAINST the prevailing leg (reversal).

    NaN pivots/EMA yield False (fail-closed).
    """
    ph, pl, c, ema = _n(pivot_high), _n(pivot_low), _n(close), _n(slow_ema)
    finite = np.isfinite(ph) & np.isfinite(pl) & np.isfinite(c) & np.isfinite(ema)
    up_break = finite & (c > ph)
    down_break = finite & (c < pl)
    up_leg = ema < c
    bos_long = up_break & up_leg
    bos_short = down_break & ~up_leg & finite
    choch_long = up_break & ~up_leg & finite
    choch_short = down_break & up_leg
    return bos_long, bos_short, choch_long, choch_short


# ---------------------------------------------------------------------------
# Premium / discount dealing range.
# ---------------------------------------------------------------------------
def premium_discount(pivot_high, pivot_low, close):
    """Dealing-range halves. Returns ``(premium, discount)`` boolean masks.

    The range is ``[last confirmed pivot low, last confirmed pivot high]``
    (forward-filled); ``mid`` is its midpoint. Premium = close above mid,
    discount = close below mid. NaN range yields False (fail-closed).
    """
    ph, pl, c = _n(pivot_high), _n(pivot_low), _n(close)
    finite = np.isfinite(ph) & np.isfinite(pl) & np.isfinite(c) & (ph > pl)
    mid = (ph + pl) / 2.0
    premium = finite & (c > mid)
    discount = finite & (c < mid)
    return premium, discount


# ---------------------------------------------------------------------------
# Fair value gaps.
# ---------------------------------------------------------------------------
def fvg_mask(high, low, lookback: int):
    """Fair-value gaps, restricted to the trailing ``lookback`` bars.

    An FVG exists at ``t`` when ``low[t] > high[t-2]`` (bullish, gap spans
    ``[high[t-2], low[t]]``) or ``high[t] < low[t-2]`` (bearish). Returns
    ``(bull_recent, bear_recent)`` — True at ``t`` when such a gap fired in
    ``(t-lookback, t]``. Strictly causal: the comparison uses only ``t`` and
    ``t-2``, and the "recent" window ends at ``t``.
    """
    h, l = _n(high), _n(low)
    n = len(h)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    if n >= 3:
        bull[2:] = l[2:] > h[:-2]
        bear[2:] = h[2:] < l[:-2]
    return recent(bull, lookback), recent(bear, lookback)


# ---------------------------------------------------------------------------
# Liquidity pools (equal highs / lows).
# ---------------------------------------------------------------------------
def liquidity_pool(high, low, pip: float, window: int = 40, tol_pips: float = 1.0):
    """Prior equal-highs / equal-lows pool levels (delegates to indicators).

    Returns ``(eq_high_level, eq_low_level, eq_high_count, eq_low_count)``.
    """
    return ind.equal_highs_lows_pool(high, low, pip, window, tol_pips)


# ---------------------------------------------------------------------------
# Displacement.
# ---------------------------------------------------------------------------
def displacement(open_, close, atr, mult: float):
    """A candle whose body exceeds ``mult * ATR`` — institutional participation.

    NaN ATR yields False (fail-closed).
    """
    o, c, a = _n(open_), _n(close), _n(atr)
    with np.errstate(invalid="ignore"):
        return np.isfinite(a) & (a > 0) & (np.abs(c - o) > mult * a)


# ---------------------------------------------------------------------------
# Order blocks.
# ---------------------------------------------------------------------------
class SmcStructure(NamedTuple):
    """The per-bar SMC reading, precomputed once for all SMC families."""

    pivot_high: np.ndarray
    pivot_low: np.ndarray
    bos_long: np.ndarray
    bos_short: np.ndarray
    choch_long: np.ndarray
    choch_short: np.ndarray
    premium: np.ndarray
    discount: np.ndarray
    fvg_bull: np.ndarray
    fvg_bear: np.ndarray
    fvg_bull_level: np.ndarray
    fvg_bear_level: np.ndarray
    eq_high: np.ndarray
    eq_low: np.ndarray
    eq_high_count: np.ndarray
    eq_low_count: np.ndarray
    displacement_up: np.ndarray
    displacement_down: np.ndarray
    ob_low: np.ndarray
    ob_high: np.ndarray
    ob_bull_active: np.ndarray
    ob_bear_active: np.ndarray
    atr: np.ndarray
    atr_rank: np.ndarray
    killzone: np.ndarray


def order_block(open_, close, high, low, lookback: int, displacement_mask):
    """Far edge of the last opposite candle before each displacement leg.

    A bullish displacement (``displacement_mask`` and ``close > open``) is
    preceded by the last bearish candle; that candle's LOW is the bullish order
    block (support). A bearish displacement uses the last bullish candle's HIGH
    (resistance). Returns ``(ob_low, ob_high, bull_active, bear_active)``:
    the two forward-filled edges and whether the block was created within the
    trailing ``lookback`` bars (still "fresh"). Strictly causal.
    """
    o, c, h, l = _n(open_), _n(close), _n(high), _n(low)
    disp = np.asarray(displacement_mask, dtype=bool)
    n = len(c)
    ob_low = np.full(n, np.nan)
    ob_high = np.full(n, np.nan)
    bull_new = np.zeros(n, dtype=bool)
    bear_new = np.zeros(n, dtype=bool)
    last_bear_low = np.nan
    last_bull_high = np.nan
    for i in range(n):
        if c[i] < o[i]:
            last_bear_low = l[i]
        elif c[i] > o[i]:
            last_bull_high = h[i]
        if disp[i] and np.isfinite(last_bear_low):
            ob_low[i] = last_bear_low
            bull_new[i] = True
        if disp[i] and c[i] < o[i] and np.isfinite(last_bull_high):
            ob_high[i] = last_bull_high
            bear_new[i] = True
    return _ffill(ob_low), _ffill(ob_high), recent(bull_new, lookback), recent(bear_new, lookback)


def _ffill(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype="float64")
    finite = np.isfinite(values)
    if not finite.any():
        return values.copy()
    idx = np.where(finite, np.arange(len(values)), 0)
    np.maximum.accumulate(idx, out=idx)
    out = values[idx]
    out[: int(np.argmax(finite))] = np.nan
    return out


# ---------------------------------------------------------------------------
# ICT killzones.
# ---------------------------------------------------------------------------
def killzone_mask(ts) -> np.ndarray:
    """ICT killzone bars in UTC: NY AM (15:00) and NY PM (19:00).

    DST is NOT modelled — the mandate fixes these UTC hours (W5 from Phase 2.1).
    A bar is labelled by its right-edge timestamp; hour is taken in UTC.
    """
    hour = pd.to_datetime(np.asarray(ts), unit="s", utc=True).hour.to_numpy()
    return ((hour >= 15) & (hour < 16)) | ((hour >= 19) & (hour < 20))


# ---------------------------------------------------------------------------
# One precomputed structure for all SMC families (built once, then read-only).
# ---------------------------------------------------------------------------
# Bounded identity cache. The key is ``(pair, id(frames), *genes)`` and the entry
# holds a STRONG reference to the frames object, so its id cannot be recycled
# while the entry lives and a stale structure can never be served (the identity is
# re-checked on hit). Pair is part of the key so two pairs that happen to share a
# frame object never share a structure. LRU-bounded.
_STRUCTURE_CACHE: "OrderedDict[tuple, tuple[object, SmcStructure]]" = OrderedDict()
_STRUCTURE_CACHE_MAX = 16


def build_structure(genome, ctx) -> SmcStructure:
    """Compute every SMC primitive ONCE from the genome's genes.

    Pure with respect to ``ctx``: a function of the (immutable) execution frame,
    the pair, and the genes that shape the structure. Results are memoized per
    (pair, frame identity, gene tuple) so a census (many families over one frame)
    pays the cost once. :func:`clear_structure_cache` empties it.
    """
    genes = (
        int(getattr(genome, "atr_period", 14)),
        int(getattr(genome, "ema_slow", 21)),
        int(getattr(genome, "smc_pivot_strength", 2)),
        int(getattr(genome, "smc_pool_window", 40)),
        float(getattr(genome, "smc_pool_tol_pips", 1.0)),
        int(getattr(genome, "smc_fvg_lookback", 20)),
        int(getattr(genome, "smc_ob_lookback", 20)),
        float(getattr(genome, "smc_displacement_atr", 1.0)),
    )
    key = (ctx.pair, id(ctx.frames), *genes)
    entry = _STRUCTURE_CACHE.get(key)
    if entry is not None and entry[0] is ctx.frames:
        _STRUCTURE_CACHE.move_to_end(key)
        return entry[1]
    result = _build_structure(genome, ctx)
    _STRUCTURE_CACHE[key] = (ctx.frames, result)
    _STRUCTURE_CACHE.move_to_end(key)
    while len(_STRUCTURE_CACHE) > _STRUCTURE_CACHE_MAX:
        _STRUCTURE_CACHE.popitem(last=False)
    return result


def clear_structure_cache() -> None:
    """Empty the explicit SMC structure cache."""
    _STRUCTURE_CACHE.clear()


def _build_structure(genome, ctx) -> SmcStructure:
    ex = ctx.frames.exec
    o = ex["open"].to_numpy(dtype="float64")
    h = ex["high"].to_numpy(dtype="float64")
    l = ex["low"].to_numpy(dtype="float64")
    c = ex["close"].to_numpy(dtype="float64")
    ts = ex["ts"].to_numpy()
    pip = ctx.pip

    atr = ind.atr(h, l, c, int(getattr(genome, "atr_period", 14)))
    slow_ema = ind.ema(c, int(getattr(genome, "ema_slow", 21)))
    ph, pl = ind.confirmed_pivots(h, l, int(getattr(genome, "smc_pivot_strength", 2)))
    bos_long, bos_short, choch_long, choch_short = bos_choch(ph, pl, c, slow_ema)
    premium, discount = premium_discount(ph, pl, c)

    fvg_bull, fvg_bear = fvg_mask(h, l, int(getattr(genome, "smc_fvg_lookback", 20)))
    # FVG edge levels (unmitigated, forward-filled) via the levels primitive.
    from app.quant import levels as lv

    fvl = lv.fvg_levels(h, l)
    fvg_bull_level, fvg_bear_level = fvl.swing_low, fvl.swing_high

    eq_high, eq_low, eq_hc, eq_lc = liquidity_pool(
        h, l, pip,
        int(getattr(genome, "smc_pool_window", 40)),
        float(getattr(genome, "smc_pool_tol_pips", 1.0)),
    )

    disp = displacement(o, c, atr, float(getattr(genome, "smc_displacement_atr", 1.0)))
    displacement_up = disp & (c > o)
    displacement_down = disp & (c < o)
    ob_low, ob_high, ob_bull_active, ob_bear_active = order_block(
        o, c, h, l, int(getattr(genome, "smc_ob_lookback", 20)), disp
    )

    atr_rank = ind.rolling_percentile_rank(atr, 500)
    killzone = killzone_mask(ts)

    return SmcStructure(
        pivot_high=ph, pivot_low=pl,
        bos_long=bos_long, bos_short=bos_short,
        choch_long=choch_long, choch_short=choch_short,
        premium=premium, discount=discount,
        fvg_bull=fvg_bull, fvg_bear=fvg_bear,
        fvg_bull_level=fvg_bull_level, fvg_bear_level=fvg_bear_level,
        eq_high=eq_high, eq_low=eq_low,
        eq_high_count=eq_hc, eq_low_count=eq_lc,
        displacement_up=displacement_up, displacement_down=displacement_down,
        ob_low=ob_low, ob_high=ob_high,
        ob_bull_active=ob_bull_active, ob_bear_active=ob_bear_active,
        atr=atr, atr_rank=atr_rank, killzone=killzone,
    )
