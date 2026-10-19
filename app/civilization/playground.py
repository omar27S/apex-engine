"""THE PLAYGROUND — Vygotsky's play (the One Brain, Part Three, item 2).

Queue slots for PLAY: agents try roles WITHOUT risk — a trend-follower pretending to
be a contrarian for a session, an agent building a deliberately crazy theory to see
what breaks it, two agents swapping strategies for a night. Play findings flow to
the Market of Ideas. The playground is the source of novelty that pure optimization
never finds.

Pure at import (Scar #6): it produces work items and a report over the caller's
data. No I/O, no clock, no RNG.
"""

from __future__ import annotations

__all__ = [
    "PLAY_SHAPES",
    "play_item",
    "playground_slots",
    "play_report",
]

# The named play shapes: role-swaps and deliberate provocation. Each carries the
# WHY of the play (what novelty it is fishing for).
PLAY_SHAPES: tuple[dict, ...] = (
    {"shape": "role_swap", "why": "an agent tries the opposite role for a night "
     "— the friction reveals what pure optimization cannot"},
    {"shape": "crazy_theory", "why": "build a deliberately absurd theory to see "
     "what breaks it — falsification as play"},
    {"shape": "strategy_swap", "why": "two agents swap strategies for a night — "
     "cross-pollination of method"},
)


def play_item(*, agent: str, shape: str, ts: str = "") -> dict:
    """One PLAY work item (no capital at risk). Raises on an unknown shape."""
    known = {s["shape"] for s in PLAY_SHAPES}
    if shape not in known:
        raise ValueError(f"unknown play shape {shape!r}; known: {sorted(known)}")
    why = next(s["why"] for s in PLAY_SHAPES if s["shape"] == shape)
    return {"kind": "play", "what": f"{agent}: {shape}", "why": why,
            "agent": str(agent), "shape": shape, "ts": ts, "risk": 0.0}


def playground_slots(agents: list[str], *, max_slots: int = 2, ts: str = "") -> list[dict]:
    """Offer a bounded number of play slots, round-robin over the play shapes.

    Bounded (the machine still has real work) and honest: with no agents there is no
    play. The slot count never exceeds ``max_slots``.
    """
    out: list[dict] = []
    for i, agent in enumerate(agents):
        if len(out) >= max_slots:
            break
        shape = PLAY_SHAPES[i % len(PLAY_SHAPES)]["shape"]
        out.append(play_item(agent=agent, shape=shape, ts=ts))
    return out


def play_report(items: list[dict]) -> dict:
    """A compact reading of the night's play (what was tried, and why)."""
    by_shape: dict[str, int] = {}
    for it in items:
        by_shape[it.get("shape", "?")] = by_shape.get(it.get("shape", "?"), 0) + 1
    if not items:
        return {"played": 0, "by_shape": {}, "reading": "nessun gioco stanotte"}
    return {"played": len(items), "by_shape": dict(sorted(by_shape.items())),
            "reading": f"{len(items)} gioco/i: {dict(sorted(by_shape.items()))}"}
