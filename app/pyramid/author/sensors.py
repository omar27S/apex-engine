"""READ-ONLY CROSS-INSTRUMENT SENSORS (Phase 7h, R82; Law 9).

The grammar's cross-instrument nodes (``dxy_proxy`` / ``dxy_ret`` / ``dxy_corr`` /
``dxy_lag_align``) read a single scalar series, ``DXY_``, injected as a CAUSAL
column on the execution frame. This module BUILDS that series from the majors —
no new data, no external feed, exactly the rate oracle's per-currency convention.

THE PROXY. For each USD major we form a per-bar USD-strength value consistent with
:mod:`app.core.rate_oracle`:

    USD-quoted major (EURUSD, GBPUSD, AUDUSD, NZDUSD): usd = 1 / close
    USD-base   major (USDJPY, USDCHF, USDCAD):          usd = close

So a firmer dollar lifts every major's value. Each series is normalised to its own
first bar (removing price scale / pip differences), averaged across the majors
present, and scaled by 100. The result is a nominal, causal dollar index.

CAUSAL ALIGNMENT. The proxy is mapped onto the traded pair's execution bars with a
BACKWARD merge-asof (the last major bar at or before each execution ``ts``) — the
closed-bar law. Mutating the traded pair's future bars cannot move the proxy at any
earlier ``ts``, because the proxy is built entirely from the (unmutated) majors.

PURITY. No I/O at import; every function is pure and deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.constellation import MAJOR_PAIRS

__all__ = ["USD_BASE_MAJORS", "USD_QUOTE_MAJORS", "MAJOR_USD_SIGN", "dxy_proxy_series"]

USD_QUOTE_MAJORS: tuple[str, ...] = tuple(p for p in MAJOR_PAIRS if p[3:] == "USD")
USD_BASE_MAJORS: tuple[str, ...] = tuple(p for p in MAJOR_PAIRS if p[:3] == "USD")

# +1 when a rising price means a firmer dollar (USD-base), -1 otherwise.
MAJOR_USD_SIGN: dict[str, int] = {
    **{p: -1 for p in USD_QUOTE_MAJORS},
    **{p: +1 for p in USD_BASE_MAJORS},
}


def dxy_proxy_series(target_ts, major_frames: dict) -> np.ndarray:
    """Return the causal USD-index proxy aligned to ``target_ts``.

    ``major_frames`` maps a major pair code to a validated M15 frame with ``ts``
    and ``close``. Only majors classified by :data:`MAJOR_USD_SIGN` are used; a
    missing or malformed major is simply omitted. When no usable major exists, the
    result is all-NaN (the cross nodes stay inert rather than inventing a value).
    """
    target_ts = np.asarray(target_ts, dtype="int64")
    out = np.full(target_ts.shape, np.nan, dtype="float64")
    if target_ts.size == 0 or not major_frames:
        return out

    levels: list[pd.Series] = []
    for pair, sign in MAJOR_USD_SIGN.items():
        frame = major_frames.get(pair)
        if frame is None or len(frame) == 0:
            continue
        if "ts" not in frame.columns or "close" not in frame.columns:
            continue
        ts = frame["ts"].to_numpy(dtype="int64")
        close = frame["close"].to_numpy(dtype="float64")
        # per-bar USD strength, signed, then normalised to the first finite bar
        usd = np.where(sign > 0, close, np.divide(1.0, close, where=close != 0,
                                                  out=np.full_like(close, np.nan)))
        finite = np.isfinite(usd) & (usd > 0)
        if not finite.any():
            continue
        base = usd[finite][0]
        norm = np.where(finite, usd / base, np.nan)
        levels.append(pd.Series(norm, index=ts, name=pair))

    if not levels:
        return out

    # Backward as-of join: each target ts takes the LAST major bar at/before it.
    proxy = pd.concat(levels, axis=1).sort_index()
    proxy = proxy[~proxy.index.duplicated(keep="last")]
    mean = proxy.mean(axis=1, skipna=True) * 100.0
    mean = mean.dropna()
    if mean.empty:
        return out
    src = pd.DataFrame({"ts": mean.index.to_numpy(dtype="int64"),
                        "dxy": mean.to_numpy(dtype="float64")}).sort_values("ts")
    tgt = pd.DataFrame({"ts": target_ts, "_ord": np.arange(target_ts.size)})
    tgt = tgt.sort_values("ts")
    merged = pd.merge_asof(tgt, src, on="ts", direction="backward")
    merged = merged.sort_values("_ord")
    return merged["dxy"].to_numpy(dtype="float64")
