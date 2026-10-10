"""PHASE 2.2a — THE FIRST SIX CLASSICAL FAMILIES.

Each family is a pure function ``(genome, ctx) -> (long_mask, short_mask)`` over
the EXECUTION (H1) frame, built ONLY from ``indicators.py`` / ``levels.py``
primitives. No I/O, no state, strictly causal (registered in the future-leak
detector). Warmup is implicit in the primitives: a ``NaN`` input yields a False
comparison, so a family stays silent until its indicators are meaningful.

The dispatcher owns the shared gate stack; these functions emit the *raw* family
signal and nothing more.
"""

from __future__ import annotations

import numpy as np

from app.quant import indicators as ind

__all__ = [
    "trend_pullback",
    "mean_reversion",
    "breakout",
    "macd_momentum",
    "keltner_expansion",
    "rsi_reversal",
]


def _prev(values: np.ndarray) -> np.ndarray:
    """The previous bar's value (``NaN`` at index 0). Strictly causal."""
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


def trend_pullback(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """Pull back to the fast EMA while trading on the right side of the slow EMA.

    Trend: ``close > slow EMA`` (long) / ``close < slow`` (short). Pullback: the
    bar's extreme touches the fast EMA. Confirmation: a directional candle and
    an RSI that has not run to the opposite extreme (``<= pullback_rsi`` long,
    ``>= 100 - pullback_rsi`` short).
    """
    open_, high, low, close = _ohlc(ctx)
    fast = ind.ema(close, genome.ema_fast)
    slow = ind.ema(close, genome.ema_slow)
    r = ind.rsi(close, genome.rsi_period)
    long = (close > slow) & (low <= fast) & (close > open_) & (r <= genome.pullback_rsi)
    short = (close < slow) & (high >= fast) & (close < open_) & (r >= 100.0 - genome.pullback_rsi)
    return long, short


def mean_reversion(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """Close beyond a Bollinger band + RSI extreme + a reversal candle."""
    open_, high, low, close = _ohlc(ctx)
    mid, upper, lower = ind.bollinger(close, genome.bb_period, genome.bb_std)
    r = ind.rsi(close, genome.rsi_period)
    long = (close < lower) & (r <= genome.rsi_oversold) & (close > open_)
    short = (close > upper) & (r >= genome.rsi_overbought) & (close < open_)
    return long, short


def breakout(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """Close beyond the shifted Donchian channel with ATR expansion."""
    open_, high, low, close = _ohlc(ctx)
    upper, lower = ind.donchian(high, low, genome.target_lookback, shift=1)
    atr = ind.atr(high, low, close, genome.atr_period)
    atr_ref = ind.sma(atr, max(genome.atr_period, 2) * 2)
    expanding = atr > atr_ref
    long = (close > upper) & expanding & (close > open_)
    short = (close < lower) & expanding & (close < open_)
    return long, short


def macd_momentum(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """MACD histogram sign flip with price on the right side of the fast EMA."""
    open_, high, low, close = _ohlc(ctx)
    _, _, hist = ind.macd(close, genome.macd_fast, genome.macd_slow, genome.macd_signal)
    prev_hist = _prev(hist)
    fast = ind.ema(close, genome.ema_fast)
    long = (hist > 0) & (prev_hist <= 0) & (close > fast)
    short = (hist < 0) & (prev_hist >= 0) & (close < fast)
    return long, short


def keltner_expansion(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """Close beyond a Keltner band with a directional candle."""
    open_, high, low, close = _ohlc(ctx)
    _, upper, lower = ind.keltner(
        high, low, close, genome.keltner_period, genome.atr_period, genome.keltner_mult
    )
    long = (close > upper) & (close > open_)
    short = (close < lower) & (close < open_)
    return long, short


def rsi_reversal(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """RSI crosses back out of an extreme zone."""
    _, _, _, close = _ohlc(ctx)
    r = ind.rsi(close, genome.rsi_period)
    prev_r = _prev(r)
    long = (prev_r <= genome.rsi_oversold) & (r > genome.rsi_oversold)
    short = (prev_r >= genome.rsi_overbought) & (r < genome.rsi_overbought)
    return long, short
