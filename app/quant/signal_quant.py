"""PHASE 2.2c — THE TWELVE STATISTICAL / VOLATILITY FAMILIES.

Each family is a pure ``(genome, ctx) -> (long_mask, short_mask)`` over the
EXECUTION (H1) frame, built only from ``indicators`` / ``levels`` / ``smc``
primitives. Strictly causal, registered in the future-leak detector. The
dispatcher owns the shared gate stack; these emit the raw family signal only.

R2 DOCTRINE: every Hurst reading used here is a rolling PERCENTILE (via
``indicators.rolling_percentile_rank``), never an absolute R/S threshold.
"""

from __future__ import annotations

import numpy as np

from app.quant import indicators as ind
from app.quant import smc
from app.quant.smc import recent

__all__ = [
    "bb_keltner_squeeze",
    "atr_squeeze_breakout",
    "vcp_breakout",
    "momentum_ignition",
    "london_orb",
    "ny_orb",
    "vwap_reversion",
    "zscore_reversion",
    "hurst_regime",
    "hurst_reversion_filtered",
    "keltner_pullback",
    "volume_profile_v",
]


def _prev(values: np.ndarray) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=np.float64)
    out[1:] = values[:-1]
    return out


def _ohlc(ctx):
    ex = ctx.frames.exec
    return (
        ex["open"].to_numpy(dtype="float64"),
        ex["high"].to_numpy(dtype="float64"),
        ex["low"].to_numpy(dtype="float64"),
        ex["close"].to_numpy(dtype="float64"),
    )


def _volume(ctx) -> np.ndarray:
    return ctx.frames.exec["volume"].to_numpy(dtype="float64")


def _body(o, c):
    return np.abs(c - o)


def _squeeze_rank(genome) -> float:
    return float(getattr(genome, "squeeze_rank", 0.2))


# ---------------------------------------------------------------------------
# 1. Bollinger-inside-Keltner squeeze, then band break with EMA bias.
# ---------------------------------------------------------------------------
def bb_keltner_squeeze(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    _, bb_up, bb_lo = ind.bollinger(c, int(genome.bb_period), float(genome.bb_std))
    _, kc_up, kc_lo = ind.keltner(
        h, l, c, int(genome.keltner_period), int(genome.atr_period), float(genome.keltner_mult)
    )
    bias = ind.ema(c, int(genome.ema_fast))
    finite = np.isfinite(bb_up) & np.isfinite(kc_up)
    squeeze = finite & (bb_up < kc_up) & (bb_lo > kc_lo)
    was_squeezed = recent(squeeze, int(genome.bb_period))
    long = was_squeezed & (c > bb_up) & (c > bias) & (c > o)
    short = was_squeezed & (c < bb_lo) & (c < bias) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 2. ATR lower-tail contraction, then the first expansion candle.
# ---------------------------------------------------------------------------
def atr_squeeze_breakout(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    atr = ind.atr(h, l, c, int(genome.atr_period))
    rank = ind.rolling_percentile_rank(atr, 500)
    contracted = np.isfinite(rank) & (rank <= _squeeze_rank(genome))
    prev_atr = _prev(atr)
    expanding = np.isfinite(atr) & np.isfinite(prev_atr) & (atr > prev_atr)
    strong = _body(o, c) > float(genome.expansion_atr) * np.where(np.isfinite(atr), atr, np.nan)
    was = recent(contracted, int(genome.bb_period))
    up_n, lo_n = ind.donchian(h, l, int(genome.target_lookback), shift=1)
    long = was & expanding & strong & (c > o) & (c > up_n)
    short = was & expanding & strong & (c < o) & (c < lo_n)
    return long, short


# ---------------------------------------------------------------------------
# 3. Nested volatility contraction, then band break.
# ---------------------------------------------------------------------------
def vcp_breakout(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    mid, up, lo = ind.bollinger(c, int(genome.bb_period), float(genome.bb_std))
    width = (up - lo) / np.where(c != 0, c, np.nan)
    look = int(genome.vcp_lookback)
    rank = ind.rolling_percentile_rank(width, look)
    contracted = np.isfinite(rank) & (rank <= _squeeze_rank(genome))
    older = _shift(width, look)
    narrowing = np.isfinite(width) & np.isfinite(older) & (width < older)
    nested = contracted & narrowing
    was = recent(nested, int(genome.bb_period))
    long = was & (c > up) & (c > o)
    short = was & (c < lo) & (c < o)
    return long, short


def _shift(values: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=np.float64)
    if k < len(values):
        out[k:] = values[:-k] if k > 0 else values
    return out


# ---------------------------------------------------------------------------
# 4. Volume ignition impulse, entry on the ~50% pullback to the impulse edge.
# ---------------------------------------------------------------------------
def momentum_ignition(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    v = _volume(ctx)
    atr = ind.atr(h, l, c, int(genome.atr_period))
    vol_ma = ind.sma(v, max(int(genome.bb_period), 2))
    spike = np.isfinite(vol_ma) & (vol_ma > 0) & (v > float(genome.ignition_vol_mult) * vol_ma)
    strong = _body(o, c) > float(genome.expansion_atr) * np.where(np.isfinite(atr), atr, np.nan)
    ign_up = spike & strong & (c > o)
    ign_dn = spike & strong & (c < o)
    # The impulse edge is the ignition bar's own open (the base of the move).
    ign_up_loc = np.where(ign_up, o, np.nan)
    ign_dn_loc = np.where(ign_dn, o, np.nan)
    up_edge = _ffill(ign_up_loc)
    dn_edge = _ffill(ign_dn_loc)
    look = int(genome.smc_ob_lookback)
    frac = float(genome.pullback_frac)
    # The ENTRY bar must be a pullback AFTER the impulse: the edge is a level set
    # by a prior ignition bar, and the entry bar itself is not that bar (on the
    # ignition bar the low always touches its own open, so without this the
    # "pullback" would be vacuously true).
    long = (recent(ign_up, look) & ~ign_up & (l <= up_edge + frac * (h - l))
            & (c > up_edge) & (c > o))
    short = (recent(ign_dn, look) & ~ign_dn & (h >= dn_edge - frac * (h - l))
             & (c < dn_edge) & (c < o))
    return long, short


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
# 5/6. Opening-range breakout + retest (London 07:00 / New York 13:00 UTC).
# ---------------------------------------------------------------------------
def _orb(genome, ctx, start_hour: int):
    o, h, l, c = _ohlc(ctx)
    ts = ctx.frames.exec["ts"].to_numpy()
    or_high, or_low, ready = ind.opening_range(
        h, l, ts, minutes=int(genome.orb_minutes), start_hour=start_hour
    )
    finite = ready & np.isfinite(or_high) & np.isfinite(or_low)
    look = int(genome.smc_ob_lookback)
    broke_up = finite & (c > or_high)
    broke_dn = finite & (c < or_low)
    long = recent(broke_up, look) & finite & (l <= or_high) & (c > or_high) & (c > o)
    short = recent(broke_dn, look) & finite & (h >= or_low) & (c < or_low) & (c < o)
    return long, short


def london_orb(genome, ctx):
    """Break + retest of the completed London opening range (07:00 UTC)."""
    return _orb(genome, ctx, 7)


def ny_orb(genome, ctx):
    """Break + retest of the completed New York opening range (13:00 UTC)."""
    return _orb(genome, ctx, 13)


# ---------------------------------------------------------------------------
# 7. Session-VWAP deviation, reversal candle.
# ---------------------------------------------------------------------------
def vwap_reversion(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    v = _volume(ctx)
    ts = ctx.frames.exec["ts"].to_numpy()
    vwap = ind.session_vwap(h, l, c, v, ts)
    dev = c - vwap
    z = ind.zscore(dev, int(genome.zscore_period))
    thr = float(genome.vwap_std_mult)
    long = np.isfinite(z) & (z <= -thr) & (c > o)
    short = np.isfinite(z) & (z >= thr) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 8. Rolling z-score beyond an entry band, reversal candle.
# ---------------------------------------------------------------------------
def zscore_reversion(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    z = ind.zscore(c, int(genome.zscore_period))
    thr = float(genome.zscore_entry)
    long = np.isfinite(z) & (z <= -thr) & (c > o)
    short = np.isfinite(z) & (z >= thr) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 9. Hurst-regime switch: follow in HIGH percentile, revert in LOW.
# ---------------------------------------------------------------------------
def hurst_regime(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    raw = ind.hurst(c, int(genome.hurst_window))
    rank = ind.rolling_percentile_rank(raw, 500)
    high = np.isfinite(rank) & (rank >= float(genome.hurst_trend_min))
    low = np.isfinite(rank) & (rank <= float(genome.hurst_revert_max))
    fast = ind.ema(c, int(genome.ema_fast))
    slow = ind.ema(c, int(genome.ema_slow))
    _, bb_up, bb_lo = ind.bollinger(c, int(genome.bb_period), float(genome.bb_std))
    # Trend-follow in high-Hurst tape.
    trend_long = high & (c > fast) & (fast > slow) & (c > o)
    trend_short = high & (c < fast) & (fast < slow) & (c < o)
    # Mean-revert in low-Hurst tape.
    rev_long = low & (c < bb_lo) & (c > o)
    rev_short = low & (c > bb_up) & (c < o)
    return trend_long | rev_long, trend_short | rev_short


# ---------------------------------------------------------------------------
# 10. Reversion only in LOW Hurst percentile AND low ADX.
# ---------------------------------------------------------------------------
def hurst_reversion_filtered(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    raw = ind.hurst(c, int(genome.hurst_window))
    rank = ind.rolling_percentile_rank(raw, 500)
    low = np.isfinite(rank) & (rank <= float(genome.hurst_revert_max))
    adx = ind.adx(h, l, c, int(genome.adx_period))
    quiet = np.isfinite(adx) & (adx < float(genome.adx_min))
    _, bb_up, bb_lo = ind.bollinger(c, int(genome.bb_period), float(genome.bb_std))
    long = low & quiet & (c < bb_lo) & (c > o)
    short = low & quiet & (c > bb_up) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 11. Keltner band break, pullback to the EMA, resume.
# ---------------------------------------------------------------------------
def keltner_pullback(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    mid, up, lo = ind.keltner(
        h, l, c, int(genome.keltner_period), int(genome.atr_period), float(genome.keltner_mult)
    )
    look = int(genome.smc_ob_lookback)
    broke_up = (c > up) & (c > o)
    broke_dn = (c < lo) & (c < o)
    # The entry is the RESUME bar AFTER the breakout, never the breakout bar
    # itself (on the breakout bar the low routinely pierces the mid-band, so the
    # pullback would be vacuously true).
    long = recent(broke_up, look) & ~broke_up & (l <= mid) & (c > mid) & (c > o)
    short = recent(broke_dn, look) & ~broke_dn & (h >= mid) & (c < mid) & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 12. Volume drop then spike at the killzone open, displacement direction.
# ---------------------------------------------------------------------------
def volume_profile_v(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    v = _volume(ctx)
    ts = ctx.frames.exec["ts"].to_numpy()
    kz = smc.killzone_mask(ts)
    vol_ma = ind.sma(v, max(int(genome.bb_period), 2))
    drop = np.isfinite(vol_ma) & (v < vol_ma)
    spike = np.isfinite(vol_ma) & (vol_ma > 0) & (v > float(genome.volume_spike_mult) * vol_ma)
    atr = ind.atr(h, l, c, int(genome.atr_period))
    disp = smc.displacement(o, c, atr, float(genome.smc_displacement_atr))
    look = int(genome.smc_ob_lookback)
    long = kz & recent(drop, look) & spike & disp & (c > o)
    short = kz & recent(drop, look) & spike & disp & (c < o)
    return long, short
