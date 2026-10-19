"""THE VOLUME LAW — distinct executed trades/week at the 15 operational pairs.

CEO ruling (Founding Charter, binding): 5 distinct executed trades/week minimum
over the worst rolling 12-month window, at the 15 operational pairs. The interim
honest state of 2-3/week is ACCEPTED while the search works — the law is the
target, not a fiction.

"Distinct" is the economic unit: same-pair same-DAY signals collapse to ONE trade
(the R92 overlap guard), so a day with two pairs counts as two, and a day with two
signals on one pair counts as one. This module reduces a list of executed
``(pair, entry_ts)`` entries to that honest count and reports the worst window.

The report is DATA, never a cage: it measures and reports; it never fabricates a
flattering number. Fewer than one full window of history is reported honestly as a
single window, not padded.

Pure at import (Scar #6): the reductions take entries; there is no I/O.
"""

from __future__ import annotations

from bisect import bisect_left

__all__ = [
    "VOLUME_LAW_PER_WEEK",
    "INTERIM_ACCEPTED_LOW",
    "INTERIM_ACCEPTED_HIGH",
    "distinct_caselli",
    "rolling_week_windows",
    "volume_law_status",
]

# R92 — the sealed minimum distinct trades/week, and the interim band the CEO
# accepts while the search works.
VOLUME_LAW_PER_WEEK: float = 5.0
INTERIM_ACCEPTED_LOW: float = 2.0
INTERIM_ACCEPTED_HIGH: float = 3.0

_SECONDS_PER_DAY = 86400


def distinct_caselli(entries) -> list[tuple[str, int]]:
    """Collapse ``(pair, entry_ts)`` entries to the distinct ``(pair, day)`` set.

    One economic trade per pair per day (the R92 overlap guard). Returns a sorted
    list so downstream windowing is deterministic.
    """
    caselli: set[tuple[str, int]] = set()
    for pair, ts in entries:
        try:
            day = int(int(ts) // _SECONDS_PER_DAY)
        except (TypeError, ValueError):
            continue
        caselli.add((str(pair), day))
    return sorted(caselli)


def rolling_week_windows(day_indices, *, window_days: int = 365,
                         step_days: int = 7) -> dict:
    """Distinct-casello trades/week over every rolling 12-month window.

    ``day_indices`` is one integer day-index per distinct casello. Returns the
    worst (driest) window, the mean, and how many windows were seen.
    """
    weeks = window_days / 7.0
    days = sorted(int(d) for d in day_indices)
    if not days:
        return {"worst_window_trades_per_week": 0.0,
                "mean_window_trades_per_week": 0.0, "n_windows": 0,
                "window_weeks": weeks, "n_caselli": 0}
    start, end = days[0], days[-1]
    if (end - start) < window_days:
        per_week = len(days) / weeks
        return {"worst_window_trades_per_week": round(per_week, 4),
                "mean_window_trades_per_week": round(per_week, 4),
                "n_windows": 1, "window_weeks": weeks, "n_caselli": len(days)}
    rates: list[float] = []
    a = start
    while a + window_days <= end:
        b = a + window_days
        n = bisect_left(days, b) - bisect_left(days, a)
        rates.append(n / weeks)
        a += step_days
    return {
        "worst_window_trades_per_week": round(min(rates), 4),
        "mean_window_trades_per_week": round(sum(rates) / len(rates), 4),
        "n_windows": len(rates), "window_weeks": weeks, "n_caselli": len(days),
    }


def volume_law_status(entries, *, window_days: int = 365,
                      law_per_week: float = VOLUME_LAW_PER_WEEK) -> dict:
    """The volume-law status the nightly STATE REPORT carries (charter act 5).

    ``entries`` is an iterable of ``(pair, entry_ts)`` executed trades at the 15
    operational pairs. Reports the worst rolling-12-month trades/week and whether
    the law is met, interim-accepted, or short.
    """
    caselli = distinct_caselli(entries)
    pairs = sorted({p for p, _ in caselli})
    win = rolling_week_windows([d for _, d in caselli], window_days=window_days)
    worst = win["worst_window_trades_per_week"]
    if not caselli:
        state = "no trades measured"
    elif worst >= law_per_week:
        state = "LAW MET"
    elif INTERIM_ACCEPTED_LOW <= worst <= INTERIM_ACCEPTED_HIGH:
        state = "interim-accepted (search in progress)"
    elif worst > INTERIM_ACCEPTED_HIGH:
        state = "below law, above interim"
    else:
        state = "below interim"
    return {
        "law_trades_per_week": law_per_week,
        "interim_band": [INTERIM_ACCEPTED_LOW, INTERIM_ACCEPTED_HIGH],
        "n_caselli": len(caselli),
        "n_pairs": len(pairs),
        "pairs": pairs,
        "worst_window_trades_per_week": worst,
        "mean_window_trades_per_week": win["mean_window_trades_per_week"],
        "n_windows": win["n_windows"],
        "law_met": worst >= law_per_week,
        "status": state,
        "reading": (f"volume: worst 12-mo window {worst}/wk at {len(pairs)} pair(s) "
                    f"({state})"),
    }
