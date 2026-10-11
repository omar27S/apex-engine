"""THE MEASUREMENT LEDGER (Phase 7g, mandate 6).

Every Phase-7g mechanism must put a NUMBER in the night report: a mechanism that
cannot be measured is a mechanism that is not really running. This module folds
the per-mechanism readings into ONE honest ledger:

* R76 heartbeat status        -> handed in by the caller (the workflow's check);
* R77 gauntlet seeds drawn    -> from :mod:`app.factory.gauntlet`;
* R78 ensemble probation      -> from :mod:`app.factory.probation`;
* R79 surrogate skip/hit rate -> from :mod:`app.factory.surrogate`;
* R80 Pareto front corners    -> from :mod:`app.factory.pareto`.

Nothing here fabricates a number: an unknown reading is carried as ``None`` with
a ``reason``, never as a flattering zero.

Pure at import; no I/O.
"""

from __future__ import annotations

__all__ = ["night_measurements"]


def night_measurements(
    *,
    gauntlet_draw: dict | None = None,
    probation_decision: dict | None = None,
    surrogate_flight: dict | None = None,
    pareto_state: dict | None = None,
    heartbeat_status: str | None = None,
) -> dict:
    """Assemble the measurement ledger from the mechanism readings."""
    drawn = None
    pool = None
    if gauntlet_draw:
        drawn = list(gauntlet_draw.get("seeds", []))
        pool = gauntlet_draw.get("pool_size")

    prob = None
    if probation_decision:
        prob = {
            "state": probation_decision.get("ruling", {}).get("state"),
            "nights_counted": probation_decision.get("nights_counted"),
            "ensemble_ranked_share": probation_decision.get("ensemble_ranked_share"),
            "quota_after": probation_decision.get("ruling", {}).get("quota_after"),
        }

    surro = None
    if surrogate_flight is not None:
        surro = {
            "fitted": surrogate_flight.get("surrogate_fitted"),
            "skip_rate": surrogate_flight.get("skip_rate"),
            "hit_rate": surrogate_flight.get("hit_rate"),
            "skipped": surrogate_flight.get("skipped"),
            "bound": surrogate_flight.get("skip_bound"),
        }

    corners = None
    if pareto_state is not None:
        corners = {
            "occupied": pareto_state.get("occupied"),
            "corners_total": pareto_state.get("corners_total"),
        }

    return {
        "R76_heartbeat": {"status": heartbeat_status} if heartbeat_status else
                        {"status": None, "reason": "heartbeat runs out-of-band"},
        "R77_gauntlet": {"seeds_drawn": drawn, "pool_size": pool,
                         "reason": None if drawn else "fixed exam (R46) ran"},
        "R78_probation": prob or {"state": None,
                                  "reason": "no probation measurement supplied"},
        "R79_surrogate": surro or {"fitted": None,
                                   "reason": "surrogate not run this night"},
        "R80_pareto": corners or {"occupied": None,
                                  "reason": "pareto front not requested"},
    }
