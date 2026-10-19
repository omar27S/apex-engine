"""LAW OF LIFE 5 — THE MARKET OF IDEAS (the economy of thought).

Ideas compete for ATTENTION: every agent holds a reputation budget (earned by past
contributions). Investing attention in an idea = backing it. Ideas with many
backers get burst resources; ideas with none starve and die. This is natural
selection applied to THOUGHTS — the civilization's collective judgment emerges
from many small bets, not one ruler's whim.

Pure at import (Scar #6): reputations and ideas are data; the functions reduce.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "START_REPUTATION",
    "REPLENISH_BASE",
    "REPLENISH_MIN",
    "REPLENISH_MAX",
    "back",
    "reputation_delta",
    "settle",
    "starved",
    "funded",
    "replenishment",
    "replenish",
    "attention_ranking",
    "market_digest",
]

# Every agent starts with one unit of attention to spend.
START_REPUTATION: float = 1.0
# A minimum attention weight for a single back; keeps the ledger readable.
MIN_BACK: float = 0.05

# THE PER-CYCLE REPLENISHMENT (LAW 5, Cure 1). Every agent receives a base
# attention allowance each Council cycle so nobody starves to zero permanently --
# but performance MODULATES it: an agent whose ideas paid back earns more, one
# whose ideas lost earns the bare floor. The allowance is bounded so the economy
# stays scarce (attention is earned, never printed without limit).
REPLENISH_BASE: float = 0.50
REPLENISH_MIN: float = 0.25
REPLENISH_MAX: float = 1.00


class InsufficientReputation(ValueError):
    """An agent tried to back an idea with attention it does not have."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def back(reputations: dict[str, float], idea: dict, *, agent: str,
         weight: float = 0.25, ts: str = "") -> dict:
    """An agent invests attention (weight) in an idea — a bet on its promise.

    The bet is bounded by the agent's reputation (fail-closed: no backing with
    attention you do not hold). Each bet is recorded on the idea with its WHY.
    """
    w = float(weight)
    if not (w >= MIN_BACK):
        raise ValueError(f"back weight must be >= {MIN_BACK}, got {weight!r}")
    held = float(reputations.get(agent, 0.0))
    if w > held + 1e-9:
        raise InsufficientReputation(
            f"{agent} holds {held:.3f} reputation, cannot back with {w:.3f}")
    reputations[agent] = round(held - w, 6)
    idea.setdefault("backers", []).append(
        {"agent": agent, "weight": round(w, 6), "ts": ts or _now()})
    idea["attention"] = round(idea.get("attention", 0.0) + w, 6)
    return idea


def reputation_delta(*, realized_value: float, attention: float) -> float:
    """Reputation earned when an idea SETTLES: value delivered, honestly scaled.

    A backer is rewarded in proportion to the idea's realized value and to how
    much attention they put in — nothing for an idea that delivered nothing.
    """
    v = float(realized_value)
    a = float(attention)
    if v != v or a != a:
        raise ValueError("settle inputs must be finite (fail-closed)")
    if v <= 0.0 or a <= 0.0:
        return 0.0
    return round(v * a, 6)


def settle(reputations: dict[str, float], idea: dict, *, realized_value: float,
           ts: str = "") -> dict:
    """Settle an idea: pay each backer reputation from its realized value."""
    value = float(realized_value)
    pays: list[dict] = []
    for b in idea.get("backers", []):
        gain = reputation_delta(realized_value=value, attention=b["weight"])
        reputations[b["agent"]] = round(
            reputations.get(b["agent"], 0.0) + gain, 6)
        pays.append({"agent": b["agent"], "reputation_gained": gain})
    idea["status"] = "settled"
    idea["realized_value"] = value
    idea["settled_ts"] = ts or _now()
    idea["payouts"] = pays
    return idea


def replenishment(*, earned: float = 0.0, lost: float = 0.0,
                  base: float = REPLENISH_BASE) -> float:
    """The per-cycle attention allowance, MODULATED by an agent's performance.

    An agent starts from ``base``; reputation EARNED from settled ideas (the payoff
    of the bets that paid) raises it, reputation LOST to ideas that delivered
    nothing lowers it. The result is clamped to ``[REPLENISH_MIN, REPLENISH_MAX]``:
    even a consistently losing agent keeps the floor (nobody starves to zero), and
    even the best cannot print attention without bound (the market stays scarce).
    """
    e = float(earned)
    l = float(lost)
    if e != e or l != l:
        raise ValueError("replenishment inputs must be finite (fail-closed)")
    raw = float(base) + e - l
    return round(max(REPLENISH_MIN, min(REPLENISH_MAX, raw)), 6)


def replenish(reputations: dict[str, float], *, agents: list[str],
              earned: dict[str, float] | None = None,
              lost: dict[str, float] | None = None,
              base: float = REPLENISH_BASE) -> dict[str, float]:
    """Grant every agent its per-cycle allowance (LAW 5, Cure 1).

    Every named agent receives ``replenishment(earned, lost)`` on top of whatever
    attention it still holds. This is what keeps the Market of Ideas ALIVE: the
    agents who lost their stake backing a dead idea are refilled and can bet again,
    while the agents whose ideas paid back are refilled more. Returns the granted
    amounts (for the audit trail).
    """
    earned = earned or {}
    lost = lost or {}
    granted: dict[str, float] = {}
    for a in agents:
        grant = replenishment(earned=earned.get(a, 0.0), lost=lost.get(a, 0.0),
                              base=base)
        reputations[a] = round(float(reputations.get(a, 0.0)) + grant, 6)
        granted[a] = grant
    return granted


def starved(idea: dict, *, floor: float = 0.1) -> bool:
    """An idea with too little attention STARVES (no backers, no resources)."""
    return float(idea.get("attention", 0.0)) < floor and not idea.get("backers")


def funded(idea: dict, *, threshold: float = 0.5) -> bool:
    """An idea with enough collective attention earns burst resources."""
    return float(idea.get("attention", 0.0)) >= threshold


def attention_ranking(ideas: list[dict]) -> list[dict]:
    """Ideas ranked by collective attention — the market's price signal."""
    return sorted(ideas, key=lambda i: (-float(i.get("attention", 0.0)),
                                        str(i.get("idea", ""))))


def market_digest(ideas: list[dict], reputations: dict[str, float]) -> dict:
    """A compact reading of the market: funded, starved, top ideas, reputation."""
    funded_ideas = [i for i in ideas if funded(i)]
    starved_ideas = [i for i in ideas if starved(i)]
    top = attention_ranking(ideas)[:3]
    return {
        "ideas": len(ideas),
        "funded": len(funded_ideas),
        "starved": len(starved_ideas),
        "top": [{"idea": t.get("idea"), "attention": t.get("attention", 0.0)}
                for t in top],
        "reputation": dict(sorted(reputations.items())),
        "reading": (f"{len(ideas)} idea(s): {len(funded_ideas)} funded, "
                    f"{len(starved_ideas)} starved"),
    }
