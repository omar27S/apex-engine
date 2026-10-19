"""E9 -- THE ORCHESTRA: a consensus of experts, never one master.

First Amendment, doctrine E9. The strategy that proposes trades is never ONE. It is
an emergent combination of many strong experts and winning strategies collaborating
on every single trade: the sniper proposes, the meteorologist confirms the regime,
the orderflow reader watches the flow, the sage recalls the episodes, the veto brain
can refuse. No single master -- a consensus of experts. Collective wisdom beats
solo genius.

This module composes those experts into ONE graded proposal. Two rules are
structural:

* THE VETO CAN REFUSE. A refusing veto brain forces the proposal to ``refuse``
  regardless of the other voices -- the one expert with a hard stop keeps it.
* THE DECISION IS GRADED, NEVER BINARY (E5). The consensus is a curve over the
  weighted voices; the size is scaled by the consensus score, never snapped to a
  hard yes/no.

The experts are APEX mechanisms: the ensemble sniper, the regime classifier, the
world-radar orderflow proxy (E7), the episodic sage (E6), the meta-label veto.
Pure at import (Scar #6).
"""

from __future__ import annotations

import math

__all__ = [
    "EXPERTS",
    "orchestra_consensus",
    "orchestra_report",
]

# The expert voices, each with a role. The veto is special (see below).
EXPERTS: tuple[dict, ...] = (
    {"name": "sniper", "role": "propose", "weight": 0.35},
    {"name": "meteorologist", "role": "confirm regime", "weight": 0.20},
    {"name": "orderflow_reader", "role": "watch flow", "weight": 0.15},
    {"name": "sage", "role": "recall episodes", "weight": 0.15},
    {"name": "veto", "role": "refuse", "weight": 0.15},
)

# The consensus score above which the orchestra proposes a trade (a curve, not a
# wall -- the score still scales the size).
PROPOSE_FLOOR: float = 0.5


def _voice(value, *, name: str) -> float:
    if value is None:
        raise ValueError(f"voice {name!r} is missing (fail-closed)")
    v = float(value)
    if not math.isfinite(v) or not (0.0 <= v <= 1.0):
        raise ValueError(f"voice {name!r} must be in [0, 1], got {value!r} (fail-closed)")
    return v


def orchestra_consensus(voices: dict[str, float], *, veto_refuses: bool = False) -> dict:
    """Combine the expert voices into one graded proposal (E9).

    ``voices`` maps expert name -> a graded reading in [0, 1] (a strength, not a
    bit). ``veto_refuses`` is the veto brain's hard stop: if True the orchestra
    REFUSES, whatever the other voices say. Otherwise the consensus is the
    weight-normalised mean of the voices and the size is scaled by it -- a graded
    decision, never a binary one.
    """
    weighted = 0.0
    total_w = 0.0
    detail: list[dict] = []
    for expert in EXPERTS:
        name = expert["name"]
        w = float(expert["weight"])
        if name in voices:
            v = _voice(voices[name], name=name)
            weighted += w * v
            total_w += w
            detail.append({"expert": name, "role": expert["role"], "voice": v,
                           "weight": w})
    if total_w == 0.0:
        return {"decision": "refuse", "consensus": None, "size_fraction": 0.0,
                "reason": "no expert voiced a reading (fail-closed)",
                "voices": detail, "reading": "no voices -- refuse"}
    consensus = round(weighted / total_w, 6)

    if veto_refuses:
        return {"decision": "refuse", "consensus": consensus, "size_fraction": 0.0,
                "reason": "the veto brain refuses (E9: the veto keeps its hard stop)",
                "voices": detail,
                "reading": f"consensus {consensus:.3f} but the veto refuses"}
    decision = "propose" if consensus >= PROPOSE_FLOOR else "abstain"
    # The size is the graded consensus itself (E5): no snap to a hard 0/1.
    size = round(consensus, 6) if decision == "propose" else 0.0
    return {
        "decision": decision,
        "consensus": consensus,
        "size_fraction": size,
        "reason": f"consensus {consensus:.3f} vs floor {PROPOSE_FLOOR}",
        "voices": detail,
        "reading": f"{decision} at consensus {consensus:.3f} (size {size:.3f})",
    }


def orchestra_report(voices: dict[str, float] | None = None, *,
                     veto_refuses: bool = False) -> dict:
    """The Orchestra's standing report (E9)."""
    if voices is None:
        return {
            "doctrine": "E9 the Orchestra: a consensus of experts, never one master",
            "experts": [e["name"] for e in EXPERTS],
            "n_experts": len(EXPERTS),
            "propose_floor": PROPOSE_FLOOR,
            "reading": f"{len(EXPERTS)} expert voices; the veto can refuse",
        }
    c = orchestra_consensus(voices, veto_refuses=veto_refuses)
    return {
        "doctrine": "E9 the Orchestra: a consensus of experts, never one master",
        "experts": [e["name"] for e in EXPERTS],
        "consensus": c,
        "reading": c["reading"],
    }
