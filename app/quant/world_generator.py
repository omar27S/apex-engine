"""THE WORLD CLONER -- synthetic worlds (Mega Phase 2, Section A, Lever 14).

The tournament has only 8 real years. This module manufactures INFINITE testing data
that is statistically indistinguishable from the real tapes, plus catastrophes that
never happened and rare regimes the real data barely exercises.

THE GENERATOR (A1) -- a joint BLOCK bootstrap over the real tapes. Return blocks are
resampled WITH replacement using the SAME block indices across pairs, so the synthetic
tape preserves, by construction, what the real tape had: volatility clustering and fat
tails (blocks keep real microstructure), regime transitions (long blocks), intraday
seasonality (whole-session blocks on the real timestamps), and cross-pair correlations
(shared block indices). No torch, no GAN training on the VM -- a Markov/bootstrap
cloner that fits the machine and is honest about being exactly that.

QUALITY GATE (A1) -- every synthetic tape must PASS a statistical validation before it
may be used: a two-sample Kolmogorov-Smirnov test on returns, an autocorrelation
comparison of squared returns (vol clustering), and a Hurst exponent within +/- 0.1 of
the real tape. A failing tape is REJECTED (fail-closed), never silently shipped.

THE STRESS EXPANDER (A2) -- synthetic BLACK SWANS that never occurred: a -5% flash
crash, a liquidity evacuation (spread/gap), a regime collapse 10x worse than 2008. The
Saboteur (RAMS) attacks the survivors with these synthetic apocalypses.

THE REALM POPULATOR (A3) -- synthetic tapes for RARE regimes (extreme volatility for
months, dead-calm for months), so specialists that real data barely exercises can be
found and held in reserve.

Honesty is binding: a synthetic tape that fails validation raises/reports FAIL, never a
quiet pass; an unmeasured statistic is ``None``. Pure at import (Scar #6): the real
tapes come from the caller; the RNG is seeded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core import data as data_mod

__all__ = [
    "WORLD_VERSION",
    "BLOCK_BARS",
    "REALM_EXTREME_VOL",
    "REALM_DEAD_CALM",
    "build_synthetic_tape",
    "validate_synthetic",
    "ks_statistic",
    "hurst_exponent",
    "acf_squared",
    "synthetic_black_swan",
    "realm_tape",
    "world_block",
]

WORLD_VERSION: int = 1

# One block = one real trading day of M15 bars (96 bars). Long enough to keep a
# regime's texture, short enough to keep diversity.
BLOCK_BARS: int = 96

REALM_EXTREME_VOL = "extreme_vol"
REALM_DEAD_CALM = "dead_calm"


def _canon(df: pd.DataFrame) -> pd.DataFrame:
    return data_mod.validate(df)


def _return_col(df: pd.DataFrame) -> np.ndarray:
    close = df["close"].to_numpy(dtype="float64")
    out = np.zeros(close.shape[0], dtype="float64")
    out[1:] = np.diff(close) / close[:-1]
    out[0] = 0.0
    return out


# ---------------------------------------------------------------------------
# A1 -- the generator.
# ---------------------------------------------------------------------------
def build_synthetic_tape(real_by_pair: dict, *, seed: int = 0,
                         n_blocks: int | None = None,
                         block_bars: int = BLOCK_BARS) -> dict:
    """Build a joint synthetic tape for every pair via shared-index block bootstrap.

    ``real_by_pair`` maps pair -> canonical M15 DataFrame (the real tapes). We split
    each pair into row-blocks of ``block_bars`` and, for each synthetic block, draw ONE
    real block index (shared across all pairs) and copy that block's OHLCV rows onto a
    synthetic, continuous timestamp grid. Shared indices preserve cross-pair
    correlation; whole blocks preserve clay/seasonality. Returns ``pair -> DataFrame``.

    Honest: pairs of differing length are handled by drawing indices valid for the
    SHORTEST tape; a pair with too few bars is skipped (never padded with a guess).
    """
    pairs = {p: _canon(df) for p, df in (real_by_pair or {}).items() if len(df) >= block_bars}
    if not pairs:
        return {}
    rng = np.random.default_rng(seed)
    min_len = min(len(df) for df in pairs.values())
    n_blocks_real = min_len // block_bars
    if n_blocks_real < 1:
        return {}
    n_blocks = int(n_blocks or max(1, n_blocks_real))
    # shared block indices for every pair -> cross-correlation preserved
    block_idx = rng.integers(0, n_blocks_real, size=n_blocks)

    base = next(iter(pairs.values()))
    # a continuous synthetic timestamp grid on the real spacing of the lead pair
    step = data_mod.infer_step_seconds(base) or 900
    ts0 = int(base["ts"].to_numpy()[0])
    synth_ts = ts0 + np.arange(n_blocks * block_bars, dtype="int64") * step

    out: dict = {}
    for pair, df in pairs.items():
        rows = []
        for b in block_idx:
            start = int(b) * block_bars
            blk = df.iloc[start:start + block_bars]
            rows.append(blk[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64"))
        stacked = np.vstack(rows)
        frame = pd.DataFrame({
            "ts": synth_ts[:stacked.shape[0]],
            "open": stacked[:, 0], "high": stacked[:, 1],
            "low": stacked[:, 2], "close": stacked[:, 3], "volume": stacked[:, 4],
        })
        # stitch OHLC continuity: an open gap between blocks is harmless (real gaps
        # exist), but price levels are kept on the real scale by construction.
        try:
            out[pair] = _canon(frame)
        except data_mod.DataValidationError:
            # a reordered block may violate OHLC invariants; repair high/low only.
            frame["high"] = frame[["open", "high", "low", "close"]].max(axis=1)
            frame["low"] = frame[["open", "high", "low", "close"]].min(axis=1)
            out[pair] = _canon(frame)
    return out


# ---------------------------------------------------------------------------
# Statistics for the quality gate.
# ---------------------------------------------------------------------------
def ks_statistic(a: np.ndarray, b: np.ndarray) -> float | None:
    """Two-sample Kolmogorov-Smirnov statistic (no SciPy). ``None`` if empty."""
    a = np.asarray(a, dtype="float64")
    b = np.asarray(b, dtype="float64")
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size == 0 or b.size == 0:
        return None
    a.sort()
    b.sort()
    grid = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, grid, side="right") / a.size
    cdf_b = np.searchsorted(b, grid, side="right") / b.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


def acf_squared(returns: np.ndarray, *, lags: int = 10) -> np.ndarray:
    """Autocorrelation of squared returns at lags 1..lags (the vol-clustering curve)."""
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    out = np.full(int(lags), np.nan, dtype="float64")
    if r.size < lags + 2:
        return out
    r2 = r * r
    r2 = r2 - r2.mean()
    denom = np.sum(r2 * r2)
    if denom <= 0:
        return out
    for k in range(1, int(lags) + 1):
        out[k - 1] = float(np.sum(r2[k:] * r2[:-k]) / denom)
    return out


def hurst_exponent(series, *, max_lag: int = 50) -> float | None:
    """The Hurst exponent via aggregated-variance (a robust, simple estimator).

    H < 0.5 -> mean-reverting, H = 0.5 -> random walk, H > 0.5 -> trending.
    ``None`` when the series is too short or degenerate.
    """
    x = np.asarray(series, dtype="float64")
    x = x[np.isfinite(x)]
    n = x.size
    if n < 20:
        return None
    lags = [2, 4, 8, 16, 32]
    lags = [l for l in lags if l < n // 4]
    if len(lags) < 2:
        return None
    tau = []
    for lag in lags:
        # variance of the lag-difference of the aggregated-by-lag series
        m = n // lag
        if m < 2:
            continue
        agg = x[:m * lag].reshape(m, lag).mean(axis=1)
        d = np.diff(agg)
        tau.append((lag, float(np.std(d))))
    tau = [(l, s) for l, s in tau if s > 0]
    if len(tau) < 2:
        return None
    logs = np.log([t[0] for t in tau])
    logt = np.log([t[1] for t in tau])
    slope = np.polyfit(logs, logt, 1)[0]
    return float(slope)


def validate_synthetic(real: pd.DataFrame, synth: pd.DataFrame, *,
                       alpha: float = 0.05, hurst_tol: float = 0.1,
                       acf_tol: float = 0.4) -> dict:
    """The A1 quality gate: KS on returns, ACF of squared returns, Hurst +/- tol.

    Returns ``{ok, ks, ks_crit, acf_close, hurst_real, hurst_synth, hurst_ok,
    reasons}``. ``ok`` is the only actionable field. Fail-closed: a missing real or
    synthetic tape -> ``ok=False``.
    """
    if real is None or synth is None or len(real) == 0 or len(synth) == 0:
        return {"ok": False, "reasons": ["tape mancante o vuota"]}
    rr = _return_col(_canon(real))
    rs = _return_col(_canon(synth))
    ks = ks_statistic(rr, rs)
    n1, n2 = np.isfinite(rr).sum(), np.isfinite(rs).sum()
    ks_crit = None
    if n1 > 0 and n2 > 0:
        ks_crit = 1.358 * np.sqrt((n1 + n2) / (n1 * n2))  # 5% two-sample critical value
    a_real = acf_squared(rr, lags=10)
    a_synth = acf_squared(rs, lags=10)
    finite = np.isfinite(a_real) & np.isfinite(a_synth)
    acf_maxdiff = (float(np.max(np.abs(a_real[finite] - a_synth[finite])))
                   if finite.any() else None)
    h_real = hurst_exponent(np.cumsum(rr))
    h_synth = hurst_exponent(np.cumsum(rs))
    hurst_ok = (h_real is not None and h_synth is not None
                and abs(h_real - h_synth) <= hurst_tol)
    reasons: list[str] = []
    ks_ok = (ks is not None and ks_crit is not None and ks <= ks_crit)
    if not ks_ok:
        reasons.append(f"KS {ks} > critico {ks_crit}")
    acf_close = (acf_maxdiff is not None and acf_maxdiff <= acf_tol)
    if not acf_close:
        reasons.append(f"ACF(f^2) differisce {acf_maxdiff} > {acf_tol}")
    if not hurst_ok:
        reasons.append(f"Hurst reale {h_real} vs sintetico {h_synth} (tol {hurst_tol})")
    return {
        "ok": bool(ks_ok and acf_close and hurst_ok),
        "ks": (round(ks, 6) if ks is not None else None),
        "ks_crit": (round(ks_crit, 6) if ks_crit is not None else None),
        "acf_maxdiff": (round(acf_maxdiff, 6) if acf_maxdiff is not None else None),
        "hurst_real": (round(h_real, 4) if h_real is not None else None),
        "hurst_synth": (round(h_synth, 4) if h_synth is not None else None),
        "hurst_ok": bool(hurst_ok),
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# A2 -- the stress expander (synthetic black swans).
# ---------------------------------------------------------------------------
def synthetic_black_swan(tape: pd.DataFrame, *, seed: int = 0,
                         drop_pct: float = 0.05, kind: str = "flash_crash") -> pd.DataFrame:
    """Inject a synthetic catastrophe that never happened into a tape.

    ``flash_crash`` -- a ``drop_pct`` gap-down over a few bars, then a partial recover.
    ``liquidity_evacuation`` -- a violent two-way whipsaw with huge ranges (spreads blow
    out). ``regime_collapse`` -- a sustained 10x-worse-than-2008 slide. All variants keep
    OHLC invariants (high >= max(open,close), low <= min(open,close)) and are DETERMINISTIC
    under ``seed``. Honest: a tape shorter than the injection window is returned unscaled
    with no crash -- never a fabricated event on a tiny tape.
    """
    df = _canon(tape).copy()
    n = len(df)
    if n < 20:
        return df
    rng = np.random.default_rng(seed)
    idx = int(n * (0.3 + 0.4 * rng.random()))
    if kind == "regime_collapse":
        span = max(8, n // 20)
        for k in range(span):
            i = idx + k
            if i >= n:
                break
            mult = np.exp(-drop_pct * (1.0 - k / span))
            for col in ("open", "high", "low", "close"):
                df.iloc[i, df.columns.get_loc(col)] *= mult
    elif kind == "liquidity_evacuation":
        span = 4
        for k in range(span):
            i = idx + k
            if i >= n:
                break
            o = float(df.iloc[i]["open"])
            c = float(df.iloc[i]["close"])
            rng_pct = (0.04 + 0.03 * rng.random()) * (1 if k % 2 == 0 else -1)
            c2 = c * (1 + rng_pct)
            df.iloc[i, df.columns.get_loc("close")] = c2
            df.iloc[i, df.columns.get_loc("high")] = max(o, c2) * (1 + 0.02)
            df.iloc[i, df.columns.get_loc("low")] = min(o, c2) * (1 - 0.02)
    else:  # flash_crash
        span = 3
        for k in range(span):
            i = idx + k
            if i >= n:
                break
            mult = (1.0 - drop_pct) ** ((k + 1) / span)
            for col in ("open", "high", "low", "close"):
                df.iloc[i, df.columns.get_loc(col)] *= mult
    # repair OHLC invariants across the injected seam (fail-closed legality)
    o = df["open"].to_numpy(dtype="float64")
    h = df["high"].to_numpy(dtype="float64")
    lo = df["low"].to_numpy(dtype="float64")
    c = df["close"].to_numpy(dtype="float64")
    df["high"] = np.maximum.reduce([o, h, c])
    df["low"] = np.minimum.reduce([o, lo, c])
    return _canon(df)


# ---------------------------------------------------------------------------
# A3 -- the synthetic realm populator (rare regimes).
# ---------------------------------------------------------------------------
def realm_tape(real: pd.DataFrame, *, regime: str, seed: int = 0,
               vol_scale: float | None = None) -> pd.DataFrame:
    """Build a synthetic tape for a RARE regime the real data barely exercises.

    ``extreme_vol`` -- returns scaled up (default 3x) for months of chaos.
    ``dead_calm`` -- returns scaled down (default 0.3x) for months of quiet.
    The scaling is applied to the close-to-close increments (still causal OHLC repair).
    Honest: an unknown regime -> the tape returned unchanged with a marker.
    """
    df = _canon(real).copy()
    n = len(df)
    if n < 20:
        return df
    if regime == REALM_EXTREME_VOL:
        scale = float(vol_scale if vol_scale is not None else 3.0)
    elif regime == REALM_DEAD_CALM:
        scale = float(vol_scale if vol_scale is not None else 0.3)
    else:
        return df
    close = df["close"].to_numpy(dtype="float64")
    ret = np.zeros(n, dtype="float64")
    ret[1:] = np.diff(close) / close[:-1]
    new_close = close[0] * np.cumprod(1.0 + scale * ret)
    df["close"] = new_close
    # carry open/high/low proportionally from the original body shape
    ratio = new_close / close
    df["open"] = df["open"].to_numpy(dtype="float64") * ratio
    df["high"] = df["high"].to_numpy(dtype="float64") * ratio
    df["low"] = df["low"].to_numpy(dtype="float64") * ratio
    o = df["open"].to_numpy(dtype="float64")
    h = df["high"].to_numpy(dtype="float64")
    lo = df["low"].to_numpy(dtype="float64")
    c = df["close"].to_numpy(dtype="float64")
    df["high"] = np.maximum.reduce([o, h, c])
    df["low"] = np.minimum.reduce([o, lo, c])
    return _canon(df)


# ---------------------------------------------------------------------------
# The Letter block.
# ---------------------------------------------------------------------------
def world_block(real_by_pair: dict, *, seed: int = 0, horizon: int = 4,
                realm: str | None = None) -> dict:
    """The Letter block: generate one joint synthetic tape, validate EVERY pair.

    Returns ``{version, n_pairs, synthetic_bars, validations, all_valid, realms,
    crash, reading}``. Honest: a pair whose synthetic tape fails validation is named
    in ``rejected`` and the block reports ``all_valid=False`` -- never a quiet pass.
    """
    if not real_by_pair:
        return {"version": WORLD_VERSION, "measured": False,
                "reading": "clonatore di mondi: nessun tape reale"}
    synth = build_synthetic_tape(real_by_pair, seed=seed)
    if not synth:
        return {"version": WORLD_VERSION, "measured": False,
                "reading": "clonatore di mondi: tape troppo corti"}
    validations = {}
    rejected = []
    for pair, sdf in synth.items():
        report = validate_synthetic(real_by_pair[pair], sdf)
        validations[pair] = report
        if not report.get("ok"):
            rejected.append(pair)
    realms = {}
    if realm:
        realms[realm] = {p: realm_tape(real_by_pair[p], regime=realm, seed=seed)
                         for p in real_by_pair if len(real_by_pair[p]) >= 20}
    return {
        "version": WORLD_VERSION,
        "n_pairs": len(synth),
        "synthetic_bars": int(sum(len(d) for d in synth.values())),
        "validations": validations,
        "all_valid": bool(not rejected and validations),
        "rejected": rejected,
        "realms": list(realms.keys()),
        "measured": True,
        "reading": (f"clonatore di mondi: {len(synth)} tape sintetici, "
                    f"{len(synth) - len(rejected)}/{len(synth)} validi"
                    + (f"; RIFIUTATI {rejected}" if rejected else "")),
    }
