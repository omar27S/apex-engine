"""LAW 5 (Physical Might) -- THE DEAD-HOUR SWEEP (harvest everything).

The Terms Guardian watches the month's free GitHub minutes. If the month is
under-consumed by day 20, it schedules catch-up bursts (private quota) so the free
minutes are HARVESTED, not expired unused. Every free minute a platform offers is
either used or consciously declined -- never wasted by neglect.

Pure at import (Scar #6): a reduction over the minute readings the caller hands it.
A missing reading sets no plan (never assume); the sweep only ever proposes, it
never fabricates consumption.
"""

from __future__ import annotations

import math

__all__ = [
    "SWEEP_DAY",
    "CATCHUP_TRIGGER_PCT",
    "sweep_status",
    "catchup_plan",
]

SWEEP_DAY: int = 20           # from day 20 the month is swept
CATCHUP_TRIGGER_PCT: float = 70.0   # under this share of the elapsed pace -> sweep


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def sweep_status(*, minutes_used=None, monthly_budget=None, day_of_month=None,
                 days_in_month=30) -> dict:
    """The month's honest minute reading: consumed vs quota, and the elapsed pace.

    The pace is the share of the budget the month SHOULD have consumed by now
    (``day_of_month / days_in_month``). Under-consumption is measured against it.
    """
    used = _num(minutes_used)
    budget = _num(monthly_budget)
    day = _num(day_of_month)
    total = _num(days_in_month)
    if used is None or budget is None or budget <= 0 or day is None or total is None or total <= 0:
        return {"measured": False, "reading": "dead-hour sweep unmeasured "
                "(no minute reading) -- nothing to harvest yet"}

    share = round(used / budget * 100.0, 1)
    expected = round(day / total * 100.0, 1)
    behind = round(max(0.0, (day / total) * budget - used), 1)
    return {
        "measured": True,
        "minutes_used": used,
        "monthly_budget": budget,
        "share_pct": share,
        "elapsed_pct": expected,
        "behind_min": behind,
        "reading": (f"{used:g}/{budget:g} min used ({share:g}%), "
                    f"month {expected:g}% elapsed, {behind:g} min behind"),
    }


def catchup_plan(*, minutes_used=None, monthly_budget=None, day_of_month=None,
                 days_in_month=30, minutes_per_burst=45) -> dict:
    """Plan catch-up bursts when the month is under-consumed on/after ``SWEEP_DAY``.

    Returns the number of bursts to schedule (bounded by the remaining budget) so
    the free minutes are harvested before they expire. Before ``SWEEP_DAY`` the plan
    is empty -- the month is still filling naturally.
    """
    st = sweep_status(minutes_used=minutes_used, monthly_budget=monthly_budget,
                      day_of_month=day_of_month, days_in_month=days_in_month)
    if not st.get("measured"):
        return {"schedule": False, "bursts": 0, "reading": st["reading"]}
    if day_of_month < SWEEP_DAY:
        return {"schedule": False, "bursts": 0, "status": st,
                "reading": f"before day {SWEEP_DAY}: the month is still filling naturally"}
    if st["share_pct"] >= CATCHUP_TRIGGER_PCT:
        return {"schedule": False, "bursts": 0, "status": st,
                "reading": f"consumed {st['share_pct']:g}% >= {CATCHUP_TRIGGER_PCT:g}% "
                           f"trigger: nothing to harvest"}
    remaining = max(0.0, st["monthly_budget"] - st["minutes_used"])
    bursts = int(remaining // max(1.0, minutes_per_burst))
    return {
        "schedule": bursts > 0, "bursts": bursts, "status": st,
        "minutes_per_burst": minutes_per_burst,
        "reading": (f"UNDER-CONSUMED {st['share_pct']:g}% < {CATCHUP_TRIGGER_PCT:g}%: "
                    f"schedule {bursts} catch-up burst(s) to harvest {remaining:g} free min"),
    }
