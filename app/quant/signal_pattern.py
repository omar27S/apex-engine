"""PHASE 2.2c — THE NINE PATTERN / CONFLUENCE FAMILIES.

Pure ``(genome, ctx) -> (long_mask, short_mask)`` over the EXECUTION (H1) frame,
built from ``indicators`` / ``levels`` / ``smc`` primitives. Strictly causal,
registered in the future-leak detector. The dispatcher owns the shared gate
stack; these emit the raw family signal only.

"Confirmed pivot" here ALWAYS means :func:`indicators.confirmed_pivots`, whose
level is only visible ``strength`` bars after the swing — a pivot a family acts
on can never have been known earlier than the tape allowed.
"""

from __future__ import annotations

import numpy as np

from app.quant import indicators as ind
from app.quant import smc
from app.quant.smc import recent

__all__ = [
    "pin_bar",
    "engulfing_liquidity",
    "hikkake",
    "fib_confluence",
    "harmonic_proxy",
    "rsi_divergence",
    "mtf_divergence",
    "fib_ote_confluence",
    "time_based_reversal",
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


# ---------------------------------------------------------------------------
# 1. Rejection wick at a confirmed pivot.
# ---------------------------------------------------------------------------
def pin_bar(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    s = smc.build_structure(genome, ctx)
    body = np.maximum(np.abs(c - o), 1e-12)
    rng = np.maximum(h - l, 1e-12)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l
    ratio = float(genome.pin_ratio)
    # Long: a long lower wick, rejecting a confirmed pivot low (near it).
    at_low = np.isfinite(s.pivot_low) & (l <= s.pivot_low + 0.25 * rng)
    at_high = np.isfinite(s.pivot_high) & (h >= s.pivot_high - 0.25 * rng)
    long = at_low & (lower_wick >= ratio * body)
    short = at_high & (upper_wick >= ratio * body)
    return long, short


# ---------------------------------------------------------------------------
# 2. Engulfing right after a pool sweep + reclaim.
# ---------------------------------------------------------------------------
def engulfing_liquidity(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    s = smc.build_structure(genome, ctx)
    po, pc = _prev(o), _prev(c)
    bull_engulf = (c > o) & (pc < po) & (c >= np.maximum(po, pc)) & (o <= np.minimum(po, pc))
    bear_engulf = (c < o) & (pc > po) & (c <= np.minimum(po, pc)) & (o >= np.maximum(po, pc))
    look = int(genome.smc_ob_lookback)
    depth = float(genome.smc_sweep_depth_atr)
    finite = np.isfinite(s.eq_low) & np.isfinite(s.eq_high) & np.isfinite(s.atr)
    swept_low = finite & (l <= s.eq_low - depth * s.atr) & (c > s.eq_low)
    swept_high = finite & (h >= s.eq_high + depth * s.atr) & (c < s.eq_high)
    long = recent(swept_low, look) & bull_engulf
    short = recent(swept_high, look) & bear_engulf
    return long, short


# ---------------------------------------------------------------------------
# 3. Hikkake: inside bar, false breakout, reversal.
# ---------------------------------------------------------------------------
def hikkake(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    look = int(genome.hikkake_lookback)
    ph, pl = _prev(h), _prev(l)
    inside = (h <= ph) & (l >= pl)
    inside = _hold(inside, look)  # an inside bar within the trailing window
    prev_h = _shift_max(h, look)
    prev_l = _shift_min(l, look)
    # False break beyond the inside bar's range, then a close back inside.
    trapped_low = inside & (l < prev_l) & (c > prev_l)
    trapped_high = inside & (h > prev_h) & (c < prev_h)
    long = trapped_low & (c > o)
    short = trapped_high & (c < o)
    return long, short


def _hold(mask: np.ndarray, lookback: int) -> np.ndarray:
    return recent(np.asarray(mask, bool), lookback)


def _shift_max(values: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=np.float64)
    if k <= 0 or k >= len(values):
        return out
    win = np.lib.stride_tricks.sliding_window_view(values, k)
    m = win.max(axis=1)
    out[k:] = m[: len(values) - k]
    return out


def _shift_min(values: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=np.float64)
    if k <= 0 or k >= len(values):
        return out
    win = np.lib.stride_tricks.sliding_window_view(values, k)
    m = win.min(axis=1)
    out[k:] = m[: len(values) - k]
    return out


# ---------------------------------------------------------------------------
# 4. Close in the fib band of the confirmed leg + trend candle.
# ---------------------------------------------------------------------------
def fib_confluence(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    s = smc.build_structure(genome, ctx)
    leg = s.pivot_high - s.pivot_low
    finite = np.isfinite(leg) & (leg > 0)
    low_f = float(genome.fib_low)
    high_f = float(genome.fib_high)
    if low_f > high_f:
        low_f, high_f = high_f, low_f
    band_lo = s.pivot_low + low_f * leg
    band_hi = s.pivot_low + high_f * leg
    in_band = finite & (c >= band_lo) & (c <= band_hi)
    long = in_band & (c > o)
    short = in_band & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 5. XABCD on confirmed pivots, D-point in 0.618..0.786 of XA.
# ---------------------------------------------------------------------------
def harmonic_proxy(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    s = smc.build_structure(genome, ctx)
    # With only the last confirmed pivot pair, the "X->A" leg is the dealing
    # range and D is the current bar's retracement. Long when price retraces to
    # 0.618..0.786 of an up-leg (discount into support) and prints a bull candle.
    leg = s.pivot_high - s.pivot_low
    finite = np.isfinite(leg) & (leg > 0)
    tol = float(genome.harmonic_tolerance)
    lo_d = 0.618 - tol
    hi_d = 0.786 + tol
    retr_up = (s.pivot_high - c) / np.where(leg != 0, leg, np.nan)
    in_zone = finite & (retr_up >= lo_d) & (retr_up <= hi_d)
    long = in_zone & (c > o)
    short = in_zone & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 6. RSI divergence: a new pivot low on higher RSI (confirmed at the pivot).
# ---------------------------------------------------------------------------
def rsi_divergence(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    r = ind.rsi(c, int(genome.rsi_period))
    s = smc.build_structure(genome, ctx)
    # A new CONFIRMED pivot low that prints below the previous confirmed pivot
    # low while the RSI AT CONFIRMATION is higher than at the previous one. Both
    # pivot levels are already confirmation-delayed (visible only after
    # ``strength`` bars), so no swing is read before the tape allowed it.
    bull_div = _divergence(s.pivot_low, r, want_bull=True)
    bear_div = _divergence(s.pivot_high, r, want_bull=False)
    look = int(genome.smc_ob_lookback)
    long = recent(bull_div, look) & (c > o)
    short = recent(bear_div, look) & (c < o)
    return long, short


def _divergence(levels: np.ndarray, rsi: np.ndarray, want_bull: bool) -> np.ndarray:
    """Pivot-vs-previous-pivot price/RSI divergence at confirmation bars.

    At bar ``i`` where a new pivot level becomes current, compare its level and
    its confirmation-bar RSI to the PREVIOUS distinct pivot. Bullish (``want_bull``):
    lower price low on higher RSI. Bearish: higher price high on lower RSI.
    """
    n = len(levels)
    out = np.zeros(n, dtype=bool)
    cur_level = np.nan
    prev = None  # the previous distinct (level, rsi_at_confirmation)
    for i in range(n):
        level = levels[i]
        if not np.isfinite(level):
            continue
        if np.isfinite(cur_level) and level == cur_level:
            continue  # still the same (forward-filled) pivot
        if prev is not None and np.isfinite(rsi[i]):
            prev_level, prev_rsi = prev
            if want_bull:
                out[i] = (level < prev_level) and (rsi[i] > prev_rsi)
            else:
                out[i] = (level > prev_level) and (rsi[i] < prev_rsi)
        if np.isfinite(rsi[i]):
            prev = (level, rsi[i])
        cur_level = level
    return out


# ---------------------------------------------------------------------------
# 7. Exec-TF RSI divergence + H4 MACD flip within a recent window (closed only).
# ---------------------------------------------------------------------------
def mtf_divergence(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    r = ind.rsi(c, int(genome.rsi_period))
    s = smc.build_structure(genome, ctx)
    # Execution-TF RSI divergence at confirmed pivots.
    bull_div = _divergence(s.pivot_low, r, want_bull=True)
    bear_div = _divergence(s.pivot_high, r, want_bull=False)
    # H4 MACD is computed on the STRUCTURE (H4) frame, then aligned closed-only
    # so no execution bar reads an H4 bar that has not closed.
    _, _, s_hist = ind.macd(
        ctx.frames.structure["close"].to_numpy(), int(genome.macd_fast),
        int(genome.macd_slow), int(genome.macd_signal),
    )
    h4_hist = _align(ctx, s_hist)
    h4_prev = _prev(h4_hist)
    flip_up = np.isfinite(h4_hist) & np.isfinite(h4_prev) & (h4_hist > 0) & (h4_prev <= 0)
    flip_dn = np.isfinite(h4_hist) & np.isfinite(h4_prev) & (h4_hist < 0) & (h4_prev >= 0)
    look = int(genome.mtf_window)
    # Both the divergence and the H4 flip must have happened in the recent
    # window; the entry candle confirms direction.
    long = recent(bull_div, look) & recent(flip_up, look) & (c > o)
    short = recent(bear_div, look) & recent(flip_dn, look) & (c < o)
    return long, short


def _align(ctx, htf_values: np.ndarray) -> np.ndarray:
    from app.quant import frames as fr

    struct = ctx.frames.structure
    return fr.align_htf(
        ctx.frames.exec["ts"], struct["ts"],
        fr.TF_MINUTES[fr.STRUCTURE_TF], htf_values,
    )


# ---------------------------------------------------------------------------
# 8. H4 0.618 level overlapping the execution OTE band with a recent FVG.
# ---------------------------------------------------------------------------
def fib_ote_confluence(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    s = smc.build_structure(genome, ctx)
    leg = s.pivot_high - s.pivot_low
    finite = np.isfinite(leg) & (leg > 0)
    # Execution OTE band.
    ote_lo = s.pivot_low + float(genome.smc_ote_low) * leg
    ote_hi = s.pivot_low + float(genome.smc_ote_high) * leg
    in_ote = finite & (c >= ote_lo) & (c <= ote_hi)
    # H4 0.618 of the H4 dealing range, aligned closed-only.
    sh, sl = ctx.frames.structure["high"].to_numpy(), ctx.frames.structure["low"].to_numpy()
    h4_lo = _align(ctx, sl)
    h4_hi = _align(ctx, sh)
    h4_leg = h4_hi - h4_lo
    h4_618 = h4_lo + 0.618 * h4_leg
    near_618 = np.isfinite(h4_618) & (np.abs(c - h4_618) <= 0.25 * np.abs(h4_leg))
    long = in_ote & near_618 & s.fvg_bull & (c > o)
    short = in_ote & near_618 & s.fvg_bear & (c < o)
    return long, short


# ---------------------------------------------------------------------------
# 9. Sweep of London's first N-hour extreme, engulfing reversal.
# ---------------------------------------------------------------------------
def time_based_reversal(genome, ctx):
    o, h, l, c = _ohlc(ctx)
    ts = ctx.frames.exec["ts"].to_numpy()
    hours = int(genome.london_hours)
    hi, lo, ready = _london_early_extreme(ts, h, l, hours)
    finite = ready & np.isfinite(hi) & np.isfinite(lo)
    po, pc = _prev(o), _prev(c)
    bull_engulf = (c > o) & (pc < po) & (c >= np.maximum(po, pc)) & (o <= np.minimum(po, pc))
    bear_engulf = (c < o) & (pc > po) & (c <= np.minimum(po, pc)) & (o >= np.maximum(po, pc))
    long = finite & (l <= lo) & (c > lo) & bull_engulf
    short = finite & (h >= hi) & (c < hi) & bear_engulf
    return long, short


def _london_early_extreme(ts, high, low, hours: int):
    """First ``hours`` London (07:00 UTC) extremes, held for the rest of the day.

    Causal: the extreme is only emitted once its window has closed.
    """
    import pandas as pd

    moment = pd.to_datetime(np.asarray(ts), unit="s", utc=True)
    day = moment.floor("D")
    minute_of_day = (moment.hour * 60 + moment.minute).to_numpy()
    start = 7 * 60
    end = start + hours * 60
    in_win = (minute_of_day >= start) & (minute_of_day < end)
    frame = pd.DataFrame({"day": day, "in_win": in_win, "h": np.asarray(high),
                          "lo": np.asarray(low)})
    win = frame[frame["in_win"]]
    dh = win.groupby("day")["h"].max()
    dl = win.groupby("day")["lo"].min()
    hi = frame["day"].map(dh).to_numpy(dtype=np.float64)
    lo = frame["day"].map(dl).to_numpy(dtype=np.float64)
    ready = (minute_of_day >= end) & np.isfinite(hi)
    return np.where(ready, hi, np.nan), np.where(ready, lo, np.nan), ready
