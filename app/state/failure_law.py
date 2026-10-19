"""E2 -- THE FAILURE LAW: every failure MUST change behaviour.

First Amendment, doctrine E2. A failure that is only RECORDED is a state bug: the
state paid for a lesson and learned nothing. This law makes the consequence
structural -- every registered failure must name the AUTONOMOUS behavioural change
it triggered. A failure whose change is missing or unknown is a BUG: flagged,
counted, and repaired.

The night report shows the three numbers the doctrine names:

    failures registered / failures that changed behaviour / bugs found

Pure at import (Scar #6): the response table is data; the functions reduce the
events the caller registers.
"""

from __future__ import annotations

__all__ = [
    "FAILURE_RESPONSES",
    "FailureEvent",
    "register_failure",
    "is_bug",
    "failure_law_report",
]

# The closed set of failure kinds and the AUTONOMOUS behavioural change each MUST
# trigger. A kind absent from this table has no mandated response, so registering
# it is a BUG until the response is written (fail-closed: the law is not optional).
#
# Cure 6 — the REAL death causes the tournament actually produces (death_ledger's
# CAUSES) are reconciled here, so E2 stops reporting phantom bugs. A cause that is
# the intended outcome of a mechanism (a death by the rank floor, a clean
# retirement) names "recorded, no response needed" -- an honest response, not a
# blank.
FAILURE_RESPONSES: dict[str, str] = {
    "zero_trades": "widen the entry gate's gradient by one notch (the drought rule)",
    "net_negative": "exile the genome and down-weight its family's draw",
    "unseen_death": "add the killing seed to the gauntlet rotation (R46)",
    "veto_false_negative": "retrain the veto on the fresh losers (R27)",
    "capacity_stall": "re-derive the guardian rhythm from the measured resource (E2)",
    "manifest_mismatch": "refuse to ignite and re-acquire the tape (R49)",
    # --- the real death causes (Cure 6, reconciled with death_ledger.CAUSES) ---
    "early_stop": "tighten the streak-kill so the losers stop before the tape pays "
                  "for them (the early-stop rule did its job)",
    "tournament_floor": "the rank floor exiled the genome by data; down-weight its "
                        "family's next draw so the search spends elsewhere",
    "apoptosis": "retire the weak with an autopsy and refill the seat with a "
                 "child of the King (E4) — recorded, no further response needed",
    "retirement": "record the legacy and refill the seat (E4) — the intended "
                  "outcome of the cycle of the weak, no further response needed",
    "tribunal": "the tribunal condemned the family by survivability data; retire "
                "its members and reallocate the draw",
    "friction": "the genome's net R <= 0 after costs — exile it and down-weight "
                "its family (R21 friction exile)",
    "zero_survivors": "no finalist survived the unseen gauntlet: widen the gauntlet "
                      "pool draw and re-examine the breeding (R77)",
    "single_book": "hold the dual-book schedule (no widening)",
}


class FailureEvent(dict):
    """One registered failure, as a plain dict (JSON-serializable as-is)."""

    __slots__ = ()


def register_failure(kind: str, *, detail: str = "", signature: str = "",
                     behavior_change: str | None = None) -> FailureEvent:
    """Register a failure and attach the autonomous behavioural change it triggers.

    The change defaults to the mandated response for ``kind`` (``FAILURE_RESPONSES``).
    A caller may pass an explicit ``behavior_change`` to record a richer response.
    An unknown ``kind`` with no explicit change is recorded with ``behavior_change``
    empty -- and therefore flagged as a BUG by :func:`is_bug`.
    """
    change = behavior_change if behavior_change is not None else FAILURE_RESPONSES.get(kind, "")
    return FailureEvent(
        kind=str(kind),
        detail=str(detail),
        signature=str(signature),
        behavior_change=str(change),
    )


def is_bug(event: dict) -> bool:
    """A failure is a STATE BUG iff it names no behavioural change (E2)."""
    return not str(event.get("behavior_change", "")).strip()


def failure_law_report(events: list[dict]) -> dict:
    """The Failure Law's night report: registered / changed / bugs found.

    Every registered failure either CHANGED behaviour or is a bug. The bugs are
    listed in full -- a bug is not hidden in a count, it is named so it can be
    repaired.
    """
    registered = len(events)
    bugs = [e for e in events if is_bug(e)]
    changed = registered - len(bugs)
    return {
        "doctrine": "E2 the Failure Law: every failure must change behaviour",
        "failures_registered": registered,
        "failures_that_changed_behaviour": changed,
        "bugs_found": len(bugs),
        "bugs": [{"kind": e.get("kind"), "detail": e.get("detail")} for e in bugs],
        "changed": [{"kind": e.get("kind"), "behavior_change": e.get("behavior_change")}
                    for e in events if not is_bug(e)],
        "reading": (f"{registered} registered, {changed} changed behaviour, "
                    f"{len(bugs)} bug(s)"
                    + ("" if not bugs else f": {[e.get('kind') for e in bugs]}")),
    }
