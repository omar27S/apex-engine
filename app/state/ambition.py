"""THE AMBITION CURVE — the state's reward:risk roadmap.

Charter act 4. The inviolable RR floor is 1:2.5. Ambition climbs toward 1:6, 1:30+
— but each step is unlocked ONLY by evidence: the bar rises with proof, never with
hope. This module makes that rule executable: a rung is ``unlocked`` iff the
evidence clears its bar.

Pure at import (Scar #6): no I/O, no services.
"""

from __future__ import annotations

from app.core import law

__all__ = [
    "AMBITION_CURVE",
    "RR_FLOOR",
    "unlocked_rung",
    "ambition_status",
]

# The sealed floor — read from the single source of truth, never re-declared.
RR_FLOOR: float = law.MIN_TARGET_RR  # 2.5

# The rungs. ``unlock`` names the evidence bar: (min_survivors, min_net_r,
# require_dd_not_rising). The floor rung is ALWAYS unlocked (it is the law).
AMBITION_CURVE: tuple[dict, ...] = (
    {"rung": 0, "target_rr": 2.5, "label": "the floor (the law)",
     "unlock": None},
    {"rung": 1, "target_rr": 4.0, "label": "modest ambition",
     "unlock": {"min_survivors": 1, "min_net_r": 0.0, "require_dd_not_rising": True}},
    {"rung": 2, "target_rr": 6.0, "label": "the stated ambition (1:6)",
     "unlock": {"min_survivors": 3, "min_net_r": 50.0, "require_dd_not_rising": True}},
    {"rung": 3, "target_rr": 12.0, "label": "stretch",
     "unlock": {"min_survivors": 5, "min_net_r": 200.0, "require_dd_not_rising": True}},
    {"rung": 4, "target_rr": 30.0, "label": "the 1:30 horizon",
     "unlock": {"min_survivors": 8, "min_net_r": 600.0, "require_dd_not_rising": True}},
    {"rung": 5, "target_rr": 60.0, "label": "beyond — never seen",
     "unlock": {"min_survivors": 12, "min_net_r": 1500.0, "require_dd_not_rising": True}},
)


def _rung_clears(rung: dict, evidence: dict) -> bool:
    bar = rung["unlock"]
    if bar is None:
        return True  # the floor is the law — always unlocked
    if int(evidence.get("survivors", 0)) < bar["min_survivors"]:
        return False
    if float(evidence.get("net_r", 0.0)) < bar["min_net_r"]:
        return False
    if bar["require_dd_not_rising"] and evidence.get("dd_trend") == "rising":
        return False
    return True


def unlocked_rung(evidence: dict) -> dict:
    """The highest rung whose evidence bar is cleared (at least the floor)."""
    best = AMBITION_CURVE[0]
    for rung in AMBITION_CURVE:
        if _rung_clears(rung, evidence):
            best = rung
        else:
            break  # rungs are monotone: stop at the first unmet bar
    return best


def ambition_status(evidence: dict) -> dict:
    """The ambition curve's status: current rung, the target, and the next bar.

    The bar rises with PROOF: an unmet rung stays locked no matter how much hope
    is applied. Reports exactly what evidence the next rung needs.
    """
    cur = unlocked_rung(evidence)
    nxt = next((r for r in AMBITION_CURVE if r["rung"] == cur["rung"] + 1), None)
    return {
        "rr_floor": RR_FLOOR,
        "current_rung": cur["rung"],
        "current_target_rr": cur["target_rr"],
        "current_label": cur["label"],
        "next_rung": ({"rung": nxt["rung"], "target_rr": nxt["target_rr"],
                       "requires": nxt["unlock"]} if nxt else None),
        "evidence": {"survivors": int(evidence.get("survivors", 0)),
                     "net_r": float(evidence.get("net_r", 0.0)),
                     "dd_trend": evidence.get("dd_trend", "unknown")},
        "reading": (f"target {cur['target_rr']}:1 (rung {cur['rung']}); "
                    + (f"next {nxt['target_rr']}:1 needs {nxt['unlock']}"
                       if nxt else "top of the curve")),
    }
