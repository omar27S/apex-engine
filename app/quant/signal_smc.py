"""PHASE 2.2b — THE FIFTEEN SMC / ICT FAMILIES.

Each family is a pure function ``(genome, ctx) -> (long_mask, short_mask)`` over
the EXECUTION (H1) frame, consuming :mod:`app.quant.smc` primitives (themselves
built from ``indicators`` / ``levels``). Strictly causal, registered in the
future-leak detector. The dispatcher owns the shared gate stack; these emit the
raw family signal only.

Shared structure (pivots, BOS/CHOCH, FVG, pools, order blocks, ATR rank) is
computed once per dispatch via :func:`smc.build_structure`.
"""

from __future__ import annotations

import numpy as np

from app.quant import indicators as ind
from app.quant import smc

__all__ = [
    "wyckoff_spring",
    "order_block",
    "volume_delta",
    "ob_atr_rank",
    "liq_sweep_ote",
    "choch_fvg",
    "bos_premium_discount",
    "fvg_momentum",
    "silver_bullet",
    "asian_range_sweep",
    "eqhl_tap",
    "judas_swing",
    "ict_2022_model",
    "dealing_range",
    "turtle_soup",
]


def _ohlc(ctx):
    ex = ctx.frames.exec
    return (
        ex["open"].to_numpy(dtype="float64"),
        ex["high"].to_numpy(dtype="float64"),
        ex["low"].to_numpy(dtype="float64"),
        ex["close"].to_numpy(dtype="float64"),
    )


def recent(mask, lookback):
    return smc.recent(np.asarray(mask, bool), int(lookback))


def _structure(genome, ctx):
    return smc.build_structure(genome, ctx)


# ---------------------------------------------------------------------------
# 1. Wyckoff spring / upthrust.
# ---------------------------------------------------------------------------
def wyckoff_spring(genome, ctx):
    """False break of range support (spring) / resistance (upthrust)."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    lower, upper = ind.donchian(h, l, int(genome.smc_range_lookback), shift=1)
    depth = float(genome.smc_spring_depth_atr)
    finite = np.isfinite(lower) & np.isfinite(upper) & np.isfinite(s.atr)
    long = finite & (l <= lower - depth * s.atr) & (c > lower) & (c > o)
    short = finite & (h >= upper + depth * s.atr) & (c < upper) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 2. Order block entry.
# ---------------------------------------------------------------------------
def order_block(genome, ctx):
    """Retracement into the last opposite-candle edge after a displacement."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    finite = np.isfinite(s.ob_low) & np.isfinite(s.ob_high)
    long = finite & s.ob_bull_active & (l <= s.ob_low) & (c > s.ob_low) & (c > o)
    short = finite & s.ob_bear_active & (h >= s.ob_high) & (c < s.ob_high) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 3. Volume delta (price/volume divergence).
# ---------------------------------------------------------------------------
def volume_delta(genome, ctx):
    """New price extreme on fading volume — accumulation/distribution."""
    o, h, l, c = _ohlc(ctx)
    vol = ctx.frames.exec["volume"].to_numpy(dtype="float64")
    look = int(genome.smc_range_lookback)
    lo_n, hi_n = ind.donchian(l, h, look, shift=1)  # lower of lows / upper of highs
    vol_ma = ind.sma(vol, max(look // 2, 2))
    fading = np.isfinite(vol_ma) & (vol < vol_ma)
    long = np.isfinite(lo_n) & fading & (l <= lo_n) & (c > o)
    short = np.isfinite(hi_n) & fading & (h >= hi_n) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 4. Order block in an ATR-ranked expansion.
# ---------------------------------------------------------------------------
def ob_atr_rank(genome, ctx):
    """Order block gated on ATR percentile rank and a > 1.5xATR displacement."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    rank_ok = np.isfinite(s.atr_rank) & (s.atr_rank >= float(genome.smc_atr_rank_min))
    wide = np.isfinite(s.atr) & ((h - l) > 1.5 * s.atr)
    finite = np.isfinite(s.ob_low) & np.isfinite(s.ob_high)
    long = finite & s.ob_bull_active & rank_ok & wide & (l <= s.ob_low) & (c > s.ob_low) & (c > o)
    short = finite & s.ob_bear_active & rank_ok & wide & (h >= s.ob_high) & (c < s.ob_high) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 5. Liquidity sweep into the OTE band near a FVG.
# ---------------------------------------------------------------------------
def liq_sweep_ote(genome, ctx):
    """Sweep of the prior equal-low/high pool, reclaim, inside the OTE band + FVG.

    The setup is a SEQUENCE: the sweep-and-reclaim happens within the trailing
    lookback, then price retraces into the OTE band with a fresh FVG. Same-bar
    conjunction is impossible by construction (a reclaim sits near the pool, the
    OTE band sits deep in the retracement), so the two stages use ``recent``.
    """
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    depth = float(genome.smc_sweep_depth_atr)
    look = int(genome.smc_range_lookback)
    finite = np.isfinite(s.eq_low) & np.isfinite(s.eq_high) & np.isfinite(s.atr)
    leg = s.pivot_high - s.pivot_low
    ote_lo = s.pivot_low + float(genome.smc_ote_low) * leg
    ote_hi = s.pivot_low + float(genome.smc_ote_high) * leg
    in_ote_long = np.isfinite(leg) & (c >= ote_lo) & (c <= ote_hi)
    setup_long = finite & (l <= s.eq_low - depth * s.atr) & (c > s.eq_low)
    long = recent(setup_long, look) & in_ote_long & s.fvg_bull & (c > o)
    # Short mirror: sweep equal highs, retrace into the premium OTE band.
    ote_lo_s = s.pivot_high - float(genome.smc_ote_high) * leg
    ote_hi_s = s.pivot_high - float(genome.smc_ote_low) * leg
    in_ote_short = np.isfinite(leg) & (c >= ote_lo_s) & (c <= ote_hi_s)
    setup_short = finite & (h >= s.eq_high + depth * s.atr) & (c < s.eq_high)
    short = recent(setup_short, look) & in_ote_short & s.fvg_bear & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 6. CHOCH + FVG retracement.
# ---------------------------------------------------------------------------
def choch_fvg(genome, ctx):
    """CHOCH against the prevailing leg, entry on a FVG retracement."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    long = s.choch_long & s.fvg_bull & np.isfinite(s.fvg_bull_level) & (l <= s.fvg_bull_level) & (c > o)
    short = s.choch_short & s.fvg_bear & np.isfinite(s.fvg_bear_level) & (h >= s.fvg_bear_level) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 7. BOS at a premium/discount extreme.
# ---------------------------------------------------------------------------
def bos_premium_discount(genome, ctx):
    """A recent BOS with the leg, entered on the retracement to its extreme half.

    The BOS closes beyond the pivot (premium for longs, discount for shorts), then
    price pulls back into the opposite half within the trailing window — so the
    two conditions occupy different bars and use ``recent`` for the break.
    """
    s = _structure(genome, ctx)
    look = int(genome.smc_range_lookback)
    return recent(s.bos_long, look) & s.discount, recent(s.bos_short, look) & s.premium


# ---------------------------------------------------------------------------
# 8. FVG tap with a momentum candle.
# ---------------------------------------------------------------------------
def fvg_momentum(genome, ctx):
    """Tap of an unmitigated FVG confirmed by a body > momentum_atr x ATR."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    body = np.abs(c - o)
    strong = np.isfinite(s.atr) & (s.atr > 0) & (body > float(genome.smc_momentum_atr) * s.atr)
    long = s.fvg_bull & np.isfinite(s.fvg_bull_level) & (l <= s.fvg_bull_level) & strong & (c > o)
    short = s.fvg_bear & np.isfinite(s.fvg_bear_level) & (h >= s.fvg_bear_level) & strong & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 9. Silver bullet (NY killzone only).
# ---------------------------------------------------------------------------
def silver_bullet(genome, ctx):
    """FVG tap inside the NY killzone mask only."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    long = s.killzone & s.fvg_bull & np.isfinite(s.fvg_bull_level) & (l <= s.fvg_bull_level) & (c > o)
    short = s.killzone & s.fvg_bear & np.isfinite(s.fvg_bear_level) & (h >= s.fvg_bear_level) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 10. Asian range sweep.
# ---------------------------------------------------------------------------
def asian_range_sweep(genome, ctx):
    """Sweep of the prior day's session extreme, then reclaim on close."""
    o, h, l, c = _ohlc(ctx)
    ts = ctx.frames.exec["ts"].to_numpy()
    prior_high, prior_low, _ = ind.prior_day_session_range(h, l, ts)
    finite = np.isfinite(prior_high) & np.isfinite(prior_low)
    long = finite & (l <= prior_low) & (c > prior_low) & (c > o)
    short = finite & (h >= prior_high) & (c < prior_high) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 11. Equal-highs/lows pool tap then reclaim.
# ---------------------------------------------------------------------------
def eqhl_tap(genome, ctx):
    """Break of an equal-highs/lows pool then reversal (reclaim on close)."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    finite = np.isfinite(s.eq_low) & np.isfinite(s.eq_high)
    long = finite & (l <= s.eq_low) & (c > s.eq_low) & (c > o)
    short = finite & (h >= s.eq_high) & (c < s.eq_high) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 12. Judas swing (London false move + CHOCH).
# ---------------------------------------------------------------------------
def judas_swing(genome, ctx):
    """London-session false sweep of a pool followed by a CHOCH reversal."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    ts = ctx.frames.exec["ts"].to_numpy()
    london = ind.session_masks(ts)["london"]
    finite = np.isfinite(s.eq_low) & np.isfinite(s.eq_high) & np.isfinite(s.atr)
    depth = float(genome.smc_sweep_depth_atr)
    look = int(genome.smc_range_lookback)
    # The false sweep and the CHOCH reversal need not share a bar: the sweep is a
    # London false move, and the reversal is confirmed within the trailing window
    # after it. Both stages are looked back over, so the sequence reads across
    # bars rather than demanding an impossible same-bar conjunction.
    swept_low = finite & (l <= s.eq_low - depth * s.atr)
    swept_high = finite & (h >= s.eq_high + depth * s.atr)
    long = london & recent(swept_low, look) & recent(s.choch_long, look) & (c > o)
    short = london & recent(swept_high, look) & recent(s.choch_short, look) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 13. ICT 2022 model.
# ---------------------------------------------------------------------------
def ict_2022_model(genome, ctx):
    """Draw on liquidity (prior Donchian extreme) + displacement + FVG entry."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    lower, upper = ind.donchian(h, l, int(genome.smc_turtle_lookback), shift=1)
    finite = np.isfinite(lower) & np.isfinite(upper)
    long = finite & (l <= lower) & s.displacement_up & s.fvg_bull & (c > o)
    short = finite & (h >= upper) & s.displacement_down & s.fvg_bear & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 14. Dealing range extremes + BOS confirmation.
# ---------------------------------------------------------------------------
def dealing_range(genome, ctx):
    """Entry only in the outer premium/discount extreme with BOS confirmation."""
    o, h, l, c = _ohlc(ctx)
    s = _structure(genome, ctx)
    leg = s.pivot_high - s.pivot_low
    finite = np.isfinite(leg) & (leg > 0)
    look = int(genome.smc_range_lookback)
    deep_discount = finite & (c <= s.pivot_low + 0.25 * leg)
    deep_premium = finite & (c >= s.pivot_high - 0.25 * leg)
    broke_up = recent(s.bos_long | s.choch_long, look)
    broke_down = recent(s.bos_short | s.choch_short, look)
    long = deep_discount & broke_up & (c > o)
    short = deep_premium & broke_down & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 15. Turtle soup (false break of an N-bar extreme).
# ---------------------------------------------------------------------------
def turtle_soup(genome, ctx):
    """False breakout of the N-bar extreme that closes back inside."""
    o, h, l, c = _ohlc(ctx)
    lower, upper = ind.donchian(h, l, int(genome.smc_turtle_lookback), shift=1)
    finite = np.isfinite(lower) & np.isfinite(upper)
    long = finite & (l < lower) & (c > lower) & (c > o)
    short = finite & (h > upper) & (c < upper) & (c < o)
    return long, short
