"""THE INDICATOR LIBRARY — pure, vectorized, strictly causal math.

Every function here is a pure transformer: numpy arrays in, numpy arrays out.
No I/O, no state, no services. Warmup is explicit — an indicator returns ``NaN``
until it has enough history to be meaningful, and ``NaN`` is never silently
filled. Causality is absolute: ``out[i]`` depends only on inputs at indices
``<= i`` (see ``tests/quant/test_causality.py``, the standing future-leak
detector, which mutates every bar after ``t`` and demands ``out[0..t]`` is
bit-for-bit unchanged).

Conventions
-----------
- Prices are passed as separate ``high``/``low``/``close`` arrays (already
  validated by ``app.core.data``). Timestamps are int64 epoch seconds UTC.
- Wilder-smoothed indicators (RSI, ATR, ADX) seed with the simple mean of the
  first ``period`` observations, then recurse with ``alpha = 1/period``.
- ``donchian`` and the level helpers are *shifted*: a window labelled at ``i``
  contains only bars strictly before ``i - (shift-1)``, so a breakout compares
  today's bar against a past extreme, never today's.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "ema",
    "sma",
    "rsi",
    "atr",
    "adx",
    "macd",
    "bollinger",
    "donchian",
    "keltner",
    "hurst",
    "confirmed_pivots",
    "session_masks",
    "session_vwap",
    "zscore",
    "opening_range",
    "equal_highs_lows_pool",
    "prior_day_session_range",
    "rolling_percentile_rank",
    "SESSION_DEFS",
]

# Session windows in UTC hours, half-open [start, end). Documented, fixed.
SESSION_DEFS: dict[str, tuple[int, int]] = {
    "asia": (0, 8),
    "london": (7, 16),
    "newyork": (12, 21),
}


def _arr(values) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def _wilder_auto(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder smoothing that discovers its own first finite index.

    Seeds at the ``period``-th finite observation with the mean of the first
    ``period`` finite values, then recurses. Positions before the seed, and gaps
    where the input is non-finite, are ``NaN``. Strictly causal.
    """
    n = len(values)
    out = np.full(n, np.nan)
    finite = np.flatnonzero(np.isfinite(values))
    if period <= 0 or finite.size < period:
        return out
    seed = int(finite[period - 1])
    out[seed] = float(np.mean(values[finite[:period]]))
    alpha = 1.0 / period
    for i in range(seed + 1, n):
        if np.isfinite(values[i]):
            out[i] = out[i - 1] + alpha * (values[i] - out[i - 1])
        else:
            out[i] = out[i - 1]
    return out


# ---------------------------------------------------------------------------
# Moving averages and oscillators.
# ---------------------------------------------------------------------------
def sma(values, period: int) -> np.ndarray:
    """Simple moving average. ``NaN`` for the first ``period-1`` bars."""
    x = _arr(values)
    out = np.full(x.shape, np.nan)
    if period <= 0 or len(x) < period:
        return out
    kernel = np.ones(period) / period
    valid = np.convolve(x, kernel, mode="valid")
    out[period - 1 :] = valid
    return out


def ema(values, period: int) -> np.ndarray:
    """Exponential moving average, SMA-seeded.

    ``EMA[period-1]`` is the SMA of the first ``period`` values; thereafter
    ``EMA[i] = alpha*x[i] + (1-alpha)*EMA[i-1]`` with ``alpha = 2/(period+1)``.
    ``NaN`` before the seed. Strictly causal.
    """
    x = _arr(values)
    n = len(x)
    out = np.full(n, np.nan)
    if period <= 0 or n < period:
        return out
    alpha = 2.0 / (period + 1.0)
    out[period - 1] = float(np.mean(x[:period]))
    for i in range(period, n):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    return out


def rsi(values, period: int = 14) -> np.ndarray:
    """Wilder RSI over ``period``.

    ``NaN`` until index ``period`` (needs ``period`` price changes). When the
    average loss is zero the RSI is ``100``; when both averages are zero it is
    ``50`` (a flat market has no direction). Strictly causal.
    """
    x = _arr(values)
    n = len(x)
    out = np.full(n, np.nan)
    if period <= 0 or n <= period:
        return out
    delta = np.full(n, np.nan)
    delta[1:] = x[1:] - x[:-1]
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    gain[0] = np.nan
    loss[0] = np.nan
    avg_gain = _wilder_auto(gain, period)
    avg_loss = _wilder_auto(loss, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        rs = avg_gain / avg_loss
        rsi_vals = 100.0 - 100.0 / (1.0 + rs)
    flat = (avg_gain == 0.0) & (avg_loss == 0.0)
    zero_loss = (avg_loss == 0.0) & (avg_gain > 0.0)
    rsi_vals = np.where(flat, 50.0, rsi_vals)
    rsi_vals = np.where(zero_loss, 100.0, rsi_vals)
    return rsi_vals


def atr(high, low, close, period: int = 14) -> np.ndarray:
    """Wilder Average True Range.

    ``TR[i] = max(high-low, |high-prev_close|, |low-prev_close|)``; index 0 has
    no prior close so its TR is undefined. ``NaN`` until index ``period``.
    Strictly causal.
    """
    h, low_a, c = _arr(high), _arr(low), _arr(close)
    n = len(c)
    out = np.full(n, np.nan)
    if period <= 0 or n <= period:
        return out
    prev_close = np.full(n, np.nan)
    prev_close[1:] = c[:-1]
    tr = np.maximum(
        h - low_a,
        np.maximum(np.abs(h - prev_close), np.abs(low_a - prev_close)),
    )
    tr[0] = np.nan
    return _wilder_auto(tr, period)


def adx(high, low, close, period: int = 14) -> np.ndarray:
    """Wilder Average Directional Index.

    Directional movement and TR are Wilder-smoothed, converted to ``+DI`` /
    ``-DI``, then ``DX`` is Wilder-smoothed once more into ``ADX``. ``NaN`` until
    index ``2*period - 1`` (both Wilder seeds must land). Strictly causal.
    """
    h, low_a, c = _arr(high), _arr(low), _arr(close)
    n = len(c)
    out = np.full(n, np.nan)
    if period <= 0 or n < 2 * period + 1:
        return out
    up = np.full(n, np.nan)
    down = np.full(n, np.nan)
    up[1:] = h[1:] - h[:-1]
    down[1:] = low_a[:-1] - low_a[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm[0] = np.nan
    minus_dm[0] = np.nan
    prev_close = np.full(n, np.nan)
    prev_close[1:] = c[:-1]
    tr = np.maximum(
        h - low_a,
        np.maximum(np.abs(h - prev_close), np.abs(low_a - prev_close)),
    )
    tr[0] = np.nan
    sm_tr = _wilder_auto(tr, period)
    sm_plus = _wilder_auto(plus_dm, period)
    sm_minus = _wilder_auto(minus_dm, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = 100.0 * sm_plus / sm_tr
        minus_di = 100.0 * sm_minus / sm_tr
        di_sum = plus_di + minus_di
        dx = 100.0 * np.abs(plus_di - minus_di) / di_sum
    dx = np.where(di_sum == 0.0, 0.0, dx)
    dx[~np.isfinite(sm_tr)] = np.nan
    return _wilder_auto(dx, period)


# ---------------------------------------------------------------------------
# Bands and channels.
# ---------------------------------------------------------------------------
def macd(values, fast: int = 12, slow: int = 26, signal: int = 9
         ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD. Returns ``(macd_line, signal_line, histogram)``.

    ``macd = ema(fast) - ema(slow)``; ``signal = ema(macd, signal)``;
    ``histogram = macd - signal``. ``NaN`` during warmup. Strictly causal.
    """
    x = _arr(values)
    macd_line = ema(x, fast) - ema(x, slow)
    signal_line = _wilder_auto(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(values, period: int = 20, num_std: float = 2.0
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger bands. Returns ``(middle, upper, lower)``.

    Middle is the SMA; the band width is ``num_std`` population standard
    deviations of the same window. ``NaN`` for the first ``period-1`` bars.
    """
    x = _arr(values)
    n = len(x)
    middle = sma(x, period)
    width = np.full(n, np.nan)
    if period > 0 and n >= period:
        windows = np.lib.stride_tricks.sliding_window_view(x, period)
        std = windows.std(axis=1, ddof=0)
        width[period - 1 :] = std * num_std
    return middle, middle + width, middle - width


def donchian(high, low, period: int = 20, shift: int = 1
             ) -> tuple[np.ndarray, np.ndarray]:
    """Shifted Donchian channel. Returns ``(upper, lower)``.

    ``upper[i]`` is the max high and ``lower[i]`` the min low over the window
    ending at ``i - shift`` (inclusive), i.e. bars
    ``[i - shift - period + 1, i - shift]``. With the default ``shift=1`` the
    current bar is excluded, so a breakout compares against past extremes only.
    ``NaN`` until a full window exists. Strictly causal.
    """
    h, low_a = _arr(high), _arr(low)
    n = len(h)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    if period <= 0 or shift < 0 or n < period + shift:
        return upper, lower
    hh = np.lib.stride_tricks.sliding_window_view(h, period).max(axis=1)
    ll = np.lib.stride_tricks.sliding_window_view(low_a, period).min(axis=1)
    # hh[k] covers [k, k+period-1]; we want coverage ending at i-shift.
    end = np.arange(period - 1, n) + shift
    valid = end < n
    upper[period - 1 + shift :] = hh[valid]
    lower[period - 1 + shift :] = ll[valid]
    return upper, lower


def keltner(high, low, close, period: int = 20, atr_period: int = 14,
            mult: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keltner channel. Returns ``(middle, upper, lower)``.

    Middle is ``ema(close, period)``; bands are ``mult * atr(atr_period)``.
    ``NaN`` until both legs are ready. Strictly causal.
    """
    c = _arr(close)
    middle = ema(c, period)
    band = mult * atr(high, low, close, atr_period)
    return middle, middle + band, middle - band


# ---------------------------------------------------------------------------
# Hurst exponent (rescaled range).
# ---------------------------------------------------------------------------
def hurst(values, window: int = 100, min_lag: int = 2, max_lag: int = 20
          ) -> np.ndarray:
    """Sliding-window Hurst exponent via rescaled range (R/S).

    For each window of ``window`` bars ending at ``i`` the series is split into
    chunks of size ``lag``; ``(R/S)_lag`` is the mean over chunks of
    (range of mean-adjusted cumulative deviations) / (chunk std). The exponent
    is the least-squares slope of ``log(R/S)`` against ``log(lag)`` over the
    integer lags in ``[min_lag, max_lag]`` that fit the window. ``NaN`` until a
    full window exists. ``out[i]`` uses only bars ``<= i`` — strictly causal.

    HONESTY CAVEAT: this classic R/S estimator carries the Anis–Lloyd upward
    bias — iid noise reads ~0.7, not 0.5, at typical windows. Use it as an
    *ordering* signal (trending > random > mean-reverting), not as an absolute
    fractal dimension. A bias-corrected estimator is deferred to a later phase.

    Memory note: the windowed view is O(n*window); call on the frame you need
    rather than all 193k bars at once if memory is tight.
    """
    x = _arr(values)
    n = len(x)
    out = np.full(n, np.nan)
    if window < 2 or n < window:
        return out
    lags = [lag for lag in range(min_lag, max_lag + 1) if lag <= window // 2]
    if len(lags) < 2:
        return out
    windows = np.lib.stride_tricks.sliding_window_view(x, window)
    log_lags = np.log(lags)
    rs_stack = np.empty((len(lags), windows.shape[0]), dtype=np.float64)
    for k, lag in enumerate(lags):
        chunks = (window // lag) * lag
        blocks = windows[:, :chunks].reshape(windows.shape[0], -1, lag)
        means = blocks.mean(axis=2, keepdims=True)
        deviations = np.cumsum(blocks - means, axis=2)
        ranges = deviations.max(axis=2) - deviations.min(axis=2)
        stds = blocks.std(axis=2, ddof=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            rs = ranges / stds
        finite = np.isfinite(rs)
        chunk_counts = finite.sum(axis=1)
        sums = np.where(finite, rs, 0.0).sum(axis=1)
        safe = np.where(chunk_counts > 0, chunk_counts, 1)
        rs_stack[k] = np.where(chunk_counts > 0, sums / safe, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        log_rs = np.log(rs_stack)
    lm = log_lags[:, None]
    valid = np.isfinite(log_rs)
    counts = valid.sum(axis=0)
    counts_safe = np.where(counts > 0, counts, 1)
    mean_lag_row = np.where(valid, lm, 0.0).sum(axis=0) / counts_safe
    mean_rs_col = np.where(valid, log_rs, 0.0).sum(axis=0) / counts_safe
    cov = np.where(valid, (lm - mean_lag_row) * (log_rs - mean_rs_col), 0.0).sum(axis=0)
    var = np.where(valid, (lm - mean_lag_row) ** 2, 0.0).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = cov / var
    slope[counts < 2] = np.nan
    out[window - 1 :] = slope
    return out


# ---------------------------------------------------------------------------
# Confirmed pivots.
# ---------------------------------------------------------------------------
def confirmed_pivots(high, low, strength: int = 2
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Last *confirmed* swing level per bar. Returns ``(pivot_high, pivot_low)``.

    A bar ``j`` is a pivot high when its high is strictly the greatest within
    ``[j-strength, j+strength]``. That fact is unknowable until ``j+strength``,
    so the level becomes visible exactly at index ``j+strength`` and is
    forward-filled thereafter. ``NaN`` until the first confirmation. Strictly
    causal by construction (the look-ahead in identification is delayed by
    ``strength`` before it is ever emitted).
    """
    h, low_a = _arr(high), _arr(low)
    n = len(h)
    pivot_high = np.full(n, np.nan)
    pivot_low = np.full(n, np.nan)
    if strength < 1 or n < 2 * strength + 1:
        return pivot_high, pivot_low

    def _is_pivot(series: np.ndarray, want_max: bool) -> np.ndarray:
        flags = np.zeros(n, dtype=bool)
        for j in range(strength, n - strength):
            window = series[j - strength : j + strength + 1]
            center = series[j]
            if want_max:
                if center == window.max() and center > series[j - 1] and center > series[j + 1]:
                    flags[j] = True
            else:
                if center == window.min() and center < series[j - 1] and center < series[j + 1]:
                    flags[j] = True
        return flags

    raw_high = np.where(_is_pivot(h, True), h, np.nan)
    raw_low = np.where(_is_pivot(low_a, False), low_a, np.nan)
    confirmed_high = np.full(n, np.nan)
    confirmed_low = np.full(n, np.nan)
    confirmed_high[strength:] = raw_high[:-strength]
    confirmed_low[strength:] = raw_low[:-strength]
    pivot_high = _ffill(confirmed_high)
    pivot_low = _ffill(confirmed_low)
    return pivot_high, pivot_low


def _ffill(values: np.ndarray) -> np.ndarray:
    """Forward-fill ``NaN`` with the last finite value (causal).

    Leading ``NaN`` (before the first finite value) stay ``NaN``.
    """
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(values)
    if not finite.any():
        return values.copy()
    idx = np.where(finite, np.arange(len(values)), 0)
    np.maximum.accumulate(idx, out=idx)
    out = values[idx]
    out[: int(np.argmax(finite))] = np.nan
    return out


# ---------------------------------------------------------------------------
# Sessions (UTC).
# ---------------------------------------------------------------------------
def _datetime_index(ts) -> pd.DatetimeIndex:
    return pd.to_datetime(np.asarray(ts), unit="s", utc=True)


def session_masks(ts) -> dict[str, np.ndarray]:
    """Boolean UTC session masks for each bar.

    Keys are the names in :data:`SESSION_DEFS` plus ``london_newyork`` (their
    overlap). A bar is labelled by its right-edge timestamp. Trivially causal.
    """
    moment = _datetime_index(ts)
    hour = moment.hour.to_numpy()
    masks: dict[str, np.ndarray] = {}
    for name, (start, end) in SESSION_DEFS.items():
        masks[name] = (hour >= start) & (hour < end)
    ln_start = max(SESSION_DEFS["london"][0], SESSION_DEFS["newyork"][0])
    ln_end = min(SESSION_DEFS["london"][1], SESSION_DEFS["newyork"][1])
    masks["london_newyork"] = (hour >= ln_start) & (hour < ln_end)
    return masks


def session_vwap(high, low, close, volume, ts) -> np.ndarray:
    """Session VWAP with a daily (UTC) reset.

    Typical price ``(h+l+c)/3`` weighted by volume, cumulated within each UTC
    calendar day. ``NaN`` where a day's cumulative volume is zero. Strictly
    causal (each day only ever accumulates forward).
    """
    h, low_a, c, vol = _arr(high), _arr(low), _arr(close), _arr(volume)
    moment = _datetime_index(ts)
    day = moment.floor("D")
    typical = (h + low_a + c) / 3.0
    frame = pd.DataFrame({"day": day, "pv": typical * vol, "vol": vol})
    cum_pv = frame.groupby("day")["pv"].cumsum().to_numpy()
    cum_vol = frame.groupby("day")["vol"].cumsum().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap = cum_pv / cum_vol
    vwap[cum_vol == 0.0] = np.nan
    return vwap


def opening_range(high, low, ts, minutes: int = 30, start_hour: int = 0
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Opening-range extremes and a readiness mask.

    ``(or_high, or_low, ready)``. For each UTC day the opening range is the
    extreme over ``[start_hour, start_hour + minutes)``. The extremes are only
    emitted at and after the window closes (``ready`` is True there); during the
    window they are ``NaN``/False, so a bar inside the range cannot see its own
    future. Persist for the rest of the day; the first day may be incomplete.
    """
    h, low_a = _arr(high), _arr(low)
    n = len(h)
    moment = _datetime_index(ts)
    day = moment.floor("D")
    minute_of_day = (moment.hour * 60 + moment.minute).to_numpy()
    start_min = start_hour * 60
    end_min = start_min + minutes
    in_window = (minute_of_day >= start_min) & (minute_of_day < end_min)

    frame = pd.DataFrame({"day": day, "in_win": in_window, "h": h, "lo": low_a})
    win = frame[frame["in_win"]]
    day_high = win.groupby("day")["h"].max()
    day_low = win.groupby("day")["lo"].min()

    or_high = frame["day"].map(day_high).to_numpy(dtype=np.float64)
    or_low = frame["day"].map(day_low).to_numpy(dtype=np.float64)
    ready = (minute_of_day >= end_min) & np.isfinite(or_high)
    or_high = np.where(ready, or_high, np.nan)
    or_low = np.where(ready, or_low, np.nan)
    return or_high, or_low, ready


# ---------------------------------------------------------------------------
# Statistical helpers.
# ---------------------------------------------------------------------------
def zscore(values, period: int = 20) -> np.ndarray:
    """Rolling z-score against the SMA and population std of ``period`` bars.

    ``NaN`` for the first ``period-1`` bars, and wherever the window std is
    zero (a constant window has no defined z). Strictly causal.
    """
    x = _arr(values)
    n = len(x)
    out = np.full(n, np.nan)
    mean = sma(x, period)
    if period > 0 and n >= period:
        windows = np.lib.stride_tricks.sliding_window_view(x, period)
        std = windows.std(axis=1, ddof=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (x[period - 1 :] - mean[period - 1 :]) / std
        z[std == 0.0] = np.nan
        out[period - 1 :] = z
    return out


def equal_highs_lows_pool(high, low, pip: float, window: int = 40,
                          tol_pips: float = 1.0
                          ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Equal-highs / equal-lows liquidity pools.

    Returns ``(eq_high_level, eq_low_level, eq_high_count, eq_low_count)``.
    Within the prior ``window`` bars (shifted by one, so the current bar is not
    part of its own pool) we ask whether at least two highs (lows) sit within
    ``tol_pips * pip`` of the window extreme; the level is that extreme and the
    count is how many bars make the pool, else ``NaN``/``0``. Strictly causal.
    """
    h, low_a = _arr(high), _arr(low)
    n = len(h)
    eq_high = np.full(n, np.nan)
    eq_low = np.full(n, np.nan)
    eq_high_count = np.zeros(n, dtype=np.int64)
    eq_low_count = np.zeros(n, dtype=np.int64)
    if window < 2 or n < window + 1 or pip <= 0 or tol_pips < 0:
        return eq_high, eq_low, eq_high_count, eq_low_count
    tol = tol_pips * pip
    hh = np.lib.stride_tricks.sliding_window_view(h, window).max(axis=1)
    ll = np.lib.stride_tricks.sliding_window_view(low_a, window).min(axis=1)
    # window [i-window, i-1] -> computed at left index k=i-window.
    for i in range(window, n):
        k = i - window
        hi = hh[k]
        lo = ll[k]
        c_hi = int(np.count_nonzero(h[k : k + window] >= hi - tol))
        c_lo = int(np.count_nonzero(low_a[k : k + window] <= lo + tol))
        if c_hi >= 2:
            eq_high[i] = hi
            eq_high_count[i] = c_hi
        if c_lo >= 2:
            eq_low[i] = lo
            eq_low_count[i] = c_lo
    return eq_high, eq_low, eq_high_count, eq_low_count


def rolling_percentile_rank(values, window: int = 500) -> np.ndarray:
    """Percentile rank of each bar within its own trailing window (0..1).

    ``rank[i]`` is the fraction of ``values[i-window+1 .. i]`` at or below
    ``values[i]`` (self-inclusive). Strictly causal. A NaN in the window or a
    window shorter than ``window`` yields NaN. This is the single self-relative
    rank used by the regime/activation gates and by the family layer — the R2
    doctrine (a Hurst/ATR style reading is used by percentile, never absolute).
    """
    x = _arr(values)
    n = len(x)
    out = np.full(n, np.nan)
    if window < 2 or n < window:
        return out
    windows = np.lib.stride_tricks.sliding_window_view(x, window)
    last = windows[:, -1:]
    with np.errstate(invalid="ignore"):
        ranks = np.nanmean((windows <= last).astype("float64"), axis=1)
    finite = np.isfinite(windows).all(axis=1)
    out[window - 1 :] = np.where(finite, ranks, np.nan)
    return out


def prior_day_session_range(high, low, ts, start_hour: int = 0
                            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Previous UTC day's session high, low, and range, held into today.

    ``(prior_high, prior_low, prior_range)``. Each bar carries the *completed
    previous* day's extremes; the first day is ``NaN``. Strictly causal.
    """
    h, low_a = _arr(high), _arr(low)
    moment = _datetime_index(ts)
    day = moment.floor("D")
    frame = pd.DataFrame({"day": day, "h": h, "lo": low_a})
    agg = frame.groupby("day").agg(high=("h", "max"), low=("lo", "min"))
    agg["range"] = agg["high"] - agg["low"]
    shifted = agg.shift(1)
    prior_high = frame["day"].map(shifted["high"]).to_numpy(dtype=np.float64)
    prior_low = frame["day"].map(shifted["low"]).to_numpy(dtype=np.float64)
    prior_range = frame["day"].map(shifted["range"]).to_numpy(dtype=np.float64)
    return prior_high, prior_low, prior_range
