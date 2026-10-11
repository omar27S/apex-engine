"""AUTHOR-BODY AUDIT — concentration, regime dependence, and the sample bar.

The Baptism directive asks three blunt questions of an authored survivor: is its
edge one lucky year, is it one regime, and does the sample actually support a
promotion claim. This module holds the PURE helpers; the heavy sandbox/evaluate
work lives in ``tools/baptism_audit.py``.

No I/O, no services, deterministic.
"""

from __future__ import annotations

import datetime as _dt
import math

import numpy as np

from app.quant.fitness import WILSON_Z

__all__ = [
    "year_of",
    "per_year_summary",
    "concentration_share",
    "atr_percentile_of_entries",
    "by_volatility_bucket",
    "wilson_upper_bound",
    "required_sample_for_lb",
]

_SEASON_SECONDS = 365.25 * 86400.0


def year_of(entry_ts) -> int:
    """The UTC calendar year of a bar timestamp (epoch seconds)."""
    return int(_dt.datetime.fromtimestamp(int(entry_ts), _dt.timezone.utc).year)


def per_year_summary(trades) -> dict[int, dict]:
    """Group a trade stream by UTC calendar year -> honest per-year metrics."""
    by: dict[int, list] = {}
    for t in trades:
        rs = float(t.r_multiple if getattr(t, "net_r", None) is None else t.net_r)
        by.setdefault(year_of(t.entry_ts), []).append(rs)
    out: dict[int, dict] = {}
    for year, rs in sorted(by.items()):
        wins = sum(1 for r in rs if r > 0)
        out[year] = {
            "trades": len(rs),
            "wins": wins,
            "win_rate": (wins / len(rs)) if rs else 0.0,
            "net_r": float(sum(rs)),
            "positive": float(sum(rs)) > 0.0,
        }
    return out


def concentration_share(per_year: dict[int, dict], *, positive_only: bool = True) -> float:
    """The share of the total net_r carried by the single best year.

    A body whose whole net_r comes from one year (share near 1.0) has an edge that
    is NOT broad. Uses only the positive years' sum in the denominator when
    ``positive_only`` — the honest "of the money it made, how much was one year".
    """
    values = [v["net_r"] for v in per_year.values()]
    if positive_only:
        denom = sum(v for v in values if v > 0)
        top = max([v for v in values if v > 0], default=0.0)
    else:
        denom = sum(abs(v) for v in values)
        top = max((abs(v) for v in values), default=0.0)
    if denom <= 0:
        return 0.0
    return float(top / denom)


def atr_percentile_of_entries(F, trades, *, window: int = 200) -> list[float]:
    """Causal ATR rank (0..1) at each trade's entry bar on frame ``F``."""
    from app.quant.indicators import rolling_percentile_rank

    atr = np.asarray(F.atr, dtype="float64")
    rank = rolling_percentile_rank(atr, window=min(window, max(2, len(atr))))
    out = []
    for t in trades:
        i = int(t.entry_index)
        v = float(rank[i]) if 0 <= i < len(rank) else np.nan
        out.append(v if np.isfinite(v) else 1.0)
    return out


def by_volatility_bucket(trades, percentiles, *, edges=(0.33, 0.66)) -> dict[str, dict]:
    """Bucket trades by the entry-time ATR percentile (low / mid / high vol)."""
    labels = ["low_vol", "mid_vol", "high_vol"]
    acc: dict[str, list] = {lab: [] for lab in labels}
    for t, p in zip(trades, percentiles):
        r = float(t.r_multiple if getattr(t, "net_r", None) is None else t.net_r)
        if p <= edges[0]:
            acc["low_vol"].append(r)
        elif p <= edges[1]:
            acc["mid_vol"].append(r)
        else:
            acc["high_vol"].append(r)
    out = {}
    for lab, rs in acc.items():
        wins = sum(1 for r in rs if r > 0)
        out[lab] = {
            "trades": len(rs), "wins": wins,
            "win_rate": (wins / len(rs)) if rs else 0.0,
            "net_r": float(sum(rs)),
        }
    return out


def wilson_upper_bound(wins: int, trades: int, z: float = WILSON_Z) -> float:
    """Wilson score interval UPPER bound of the binomial proportion."""
    n = int(trades)
    if n <= 0:
        return 0.0
    p = int(wins) / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return float(min(1.0, (centre + margin) / denom))


def required_sample_for_lb(target_lb: float, win_rate: float,
                           *, cap: int = 100_000) -> int:
    """Smallest integer trade count whose Wilson LB reaches ``target_lb``.

    Given an observed win rate, more trades tighten the interval toward the point
    estimate; if the win rate is below the target, NO sample ever clears it and the
    function returns -1 (the honest "impossible at this rate"). Uses the SAME
    Wilson bound the fitness ranks on, so the answer is the promotion bar's own
    arithmetic.
    """
    from app.quant.fitness import wilson_lower_bound

    p = float(win_rate)
    if p <= 0:
        return -1
    lo, hi = 1, int(cap)
    if wilson_lower_bound(int(round(p * hi)), hi) < target_lb:
        return -1
    while lo < hi:
        mid = (lo + hi) // 2
        if wilson_lower_bound(int(round(p * mid)), mid) >= target_lb:
            hi = mid
        else:
            lo = mid + 1
    return int(lo)
