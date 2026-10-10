"""THE RATE ORACLE — the constellation pays for its own rates.

The seven majors carry every quote currency of the fifteen-pair Constellation,
so APEX never needs an external FX feed:

    USD-quoted majors (EURUSD, GBPUSD, AUDUSD, NZDUSD): rate(BASE) = price
    USD-base  majors (USDJPY, USDCHF, USDCAD):          rate(QUOTE) = 1 / price
    USD:                                                1.0

Fail-closed doctrine: a malformed or missing major simply omits that currency
from the result. Downstream, ``tick_value.pip_value_per_lot`` then returns
``None`` for any pair needing it, and the trade is rejected. No magic defaults,
no imputation, no caches.

Pure: no I/O, no side effects, deterministic.
"""

from __future__ import annotations

from math import isfinite
from typing import Mapping

import pandas as pd

from app.core.constellation import MAJOR_PAIRS
from app.core.law import normalize_pair

ACCOUNT_CURRENCY = "USD"

# Which side of USD a major sits on is COMPUTED from the pair code, never a table:
#   starts with USD -> USD is base  (price == base units per USD, so rate = 1/price)
#   ends   with USD -> USD is quote (price == USD per base unit, so rate = price)
ORACLE_MAJORS: tuple[str, ...] = tuple(
    p for p in MAJOR_PAIRS if p[:3] == ACCOUNT_CURRENCY or p[3:] == ACCOUNT_CURRENCY
)
USD_BASE_MAJORS: tuple[str, ...] = tuple(p for p in ORACLE_MAJORS if p[:3] == "USD")
USD_QUOTE_MAJORS: tuple[str, ...] = tuple(p for p in ORACLE_MAJORS if p[3:] == "USD")


class RateOracleStalenessError(ValueError):
    """Raised when major frames are too far apart in time to price a cross."""


def _positive_finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number <= 0:
        return None
    return number


def build_usd_rates(major_prices: Mapping[str, float]) -> dict[str, float]:
    """Return USD rates for every currency the supplied majors can cover.

    Keys are canonical pair codes or broker-suffixed symbols; values are prices.
    Malformed keys, non-finite prices, and absent majors are skipped, not
    defaulted. The account currency ``USD`` is always present at 1.0.
    """
    rates: dict[str, float] = {ACCOUNT_CURRENCY: 1.0}
    if not major_prices:
        return rates

    for raw_symbol, raw_price in major_prices.items():
        pair = normalize_pair(raw_symbol)
        if pair is None:
            continue
        price = _positive_finite(raw_price)
        if price is None:
            continue
        if pair in USD_QUOTE_MAJORS:
            rates[pair[:3]] = price
        elif pair in USD_BASE_MAJORS:
            rates[pair[3:]] = 1.0 / price
    return rates


def rates_from_frames(
    frames: Mapping[str, pd.DataFrame],
    max_spread_seconds: int | None = None,
) -> dict[str, float]:
    """Build USD rates from each major's LAST CLOSED bar close.

    Frames are expected to be validated, causal (right-edge labeled) frames; the
    last row is therefore the last completed bar. Empty or malformed frames are
    skipped (the corresponding currency is simply omitted). Pure — the caller
    does the loading.

    Staleness guard: mixing rates read at different times silently distorts a
    cross's pip value. When ``max_spread_seconds`` is given, every usable frame
    must carry an integer ``ts`` column and the spread between the newest and
    oldest usable last-bar timestamp must not exceed it, else
    :class:`RateOracleStalenessError` is raised. Frames without a usable ``ts``
    are omitted from the check (and from the rate map only if their price is
    unusable). No defaults, no clamping.
    """
    if max_spread_seconds is not None and max_spread_seconds < 0:
        raise ValueError("max_spread_seconds must be non-negative")

    major_prices: dict[str, float] = {}
    timestamps: list[int] = []
    for raw_symbol, frame in frames.items():
        if frame is None or len(frame) == 0 or "close" not in frame.columns:
            continue
        major_prices[raw_symbol] = frame["close"].iloc[-1]
        if "ts" in frame.columns:
            ts_value = frame["ts"].iloc[-1]
            try:
                timestamps.append(int(ts_value))
            except (TypeError, ValueError):
                continue

    if max_spread_seconds is not None and len(timestamps) > 1:
        spread = max(timestamps) - min(timestamps)
        if spread > max_spread_seconds:
            raise RateOracleStalenessError(
                f"major frames span {spread}s, exceeding max_spread_seconds="
                f"{max_spread_seconds}s"
            )

    return build_usd_rates(major_prices)
