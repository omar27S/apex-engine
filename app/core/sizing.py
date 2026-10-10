"""HONEST SIZING — the Titanium Floor is a floor, not a target.

``position_size_lots`` computes the number of lots for a trade under the law:
risk a fixed percentage of equity, expressed in lots. Because the Titanium
Floor is a *floor*, the chosen size must risk **at least** the intended amount —
rounding DOWN below it is illegal. So we pick the smallest ``lot_step`` multiple
whose actual risk is ``>=`` the intended risk. If that minimum already overshoots
by more than ``max_drift`` (the account is too small for this stop at the floor
risk), the trade is rejected.

Fail-closed: a missing or non-positive pip value, non-positive inputs, or a
malformed step returns a reject with a reason string — never an exception.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.law import TITANIUM_FLOOR_PCT


@dataclass(frozen=True)
class SizeResult:
    ok: bool
    lots: float | None
    actual_risk: float | None
    intended_risk: float | None
    drift_ratio: float | None
    reason: str


def _bad(reason: str, intended: float | None = None) -> SizeResult:
    return SizeResult(False, None, None, intended, None, reason)


def position_size_lots(
    equity: float | None,
    risk_pct: float | None,
    sl_pips: float | None,
    pip_value_per_lot: float | None,
    *,
    lot_step: float = 0.01,
    max_drift: float = 1.25,
) -> SizeResult:
    """Size a position under the Titanium Floor and lot-step granularity."""
    if equity is None or risk_pct is None or sl_pips is None:
        return _bad("missing input — fail closed")
    if pip_value_per_lot is None or pip_value_per_lot <= 0:
        return _bad("no pip value — fail closed")
    if equity <= 0 or risk_pct <= 0 or sl_pips <= 0:
        return _bad("non-positive input — fail closed")
    if lot_step <= 0 or max_drift < 1.0:
        return _bad("invalid sizing parameter — fail closed")

    intended_risk = equity * risk_pct / 100.0
    risk_per_lot = sl_pips * pip_value_per_lot  # money risked per 1.0 lot
    if risk_per_lot <= 0:
        return _bad("non-positive risk per lot — fail closed", intended_risk)

    raw_lots = intended_risk / risk_per_lot
    # Smallest lot_step multiple whose actual risk is >= intended (floor).
    steps = math.ceil(raw_lots / lot_step - 1e-9)
    lots = steps * lot_step
    if lots <= 0:
        return _bad("zero lots cannot meet the floor — fail closed", intended_risk)

    actual_risk = lots * risk_per_lot
    drift_ratio = actual_risk / intended_risk
    if drift_ratio > max_drift:
        return SizeResult(
            False,
            None,
            None,
            intended_risk,
            None,
            "account too small for this stop at the floor risk",
        )
    return SizeResult(
        True,
        round(lots, 10),
        actual_risk,
        intended_risk,
        drift_ratio,
        "sized at or above the titanium floor",
    )


def floor_risk_pct(risk_pct: float | None) -> float | None:
    """Return ``risk_pct`` if it meets the Titanium Floor, else ``None``.

    Convenience guard for callers; the floor itself stays in the Law.
    """
    if risk_pct is None or risk_pct < TITANIUM_FLOOR_PCT:
        return None
    return risk_pct
