"""THE IDLENESS GUARDIAN — l'idleness e peccato mortale (Part Three, the pressure).

FREEDOM WITHOUT PRESSURE IS DECAY. The civilization's agents are free to think and
act whenever they want (the Freedom Doctrine); this module makes sure that freedom
is not spent in idleness. It is the HUNTER.

It watches every agent's real activity — hours since the last thought, the last
vision, the last contribution, the last SPONTANEOUS act — and:

* flags an agent idle beyond its TIER's threshold LIVE in the state, as
  ``dormiente`` (sleeping), visible to all: shame in the open, not a private note;
* counts down to RETIREMENT (the survival law, harder now): a newborn is idle at
  most 5 days, a veteran 14, a King 30 — even kings must produce;
* feeds the TRIBUNAL: the idleness pattern of a candidate is evidence.

Honest-measurement (the CEO's principle): an agent with NO recorded activity is
NEVER assumed idle or active — with no clock it is ``non misurato`` (None), never a
fabricated number. The thresholds are DATA; the caller passes the agent's real
``last_*`` stamps and the current time.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "TIER_IDLE_DAYS",
    "tier_of",
    "idle_days",
    "idleness_of",
    "idleness_report",
    "retirement_due",
]

# The survival law (Part Three, item 12): idle beyond the tier's threshold and the
# agent is retired. Newborn 5 days, veteran 14, King 30 (even kings produce).
TIER_IDLE_DAYS: dict[str, int] = {
    "newborn": 5,
    "veteran": 14,
    "king": 30,
}

# The activities that count as LIVING (a vision and a spontaneous act count too).
_ACTIVITY_FIELDS: tuple[str, ...] = ("last_thought", "last_vision",
                                     "last_contribution", "last_spontaneous")


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    v = str(ts).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tier_of(agent: dict) -> str:
    """An agent's tier from its record: a King by ``is_king``, else by its age.

    Newborn (young) -> veteran (older) -> king. Age is measured in
    ``generations`` when present, else in ``lived_cycles``; an agent with neither
    is a newborn (the safe, gentler default — never an instant retirement).
    """
    if agent.get("is_king") or str(agent.get("role", "")).startswith("king"):
        return "king"
    age = agent.get("generations", agent.get("lived_cycles", 0)) or 0
    try:
        age = int(age)
    except (TypeError, ValueError):
        age = 0
    return "veteran" if age >= 5 else "newborn"


def idle_days(agent: dict, *, now: datetime) -> float | None:
    """Days since the agent's MOST RECENT activity, or ``None`` if unmeasured.

    An agent with no recorded activity stamp has no honest idleness reading — the
    guardian says so (None) rather than inventing one.
    """
    stamps = [_parse(agent.get(f)) for f in _ACTIVITY_FIELDS]
    stamps = [s for s in stamps if s is not None]
    if not stamps:
        return None
    last = max(stamps)
    return round((now - last).total_seconds() / 86400.0, 3)


def idleness_of(agent: dict, *, now: datetime) -> dict:
    """One agent's idleness verdict: tier, idle days, dormiente flag, countdown."""
    tier = tier_of(agent)
    threshold = TIER_IDLE_DAYS[tier]
    days = idle_days(agent, now=now)
    if days is None:
        return {"agent": agent.get("signature"), "tier": tier, "idle_days": None,
                "threshold_days": threshold, "dormiente": None,
                "days_to_retirement": None,
                "reading": f"{agent.get('signature')}: inattivita' non misurata "
                           f"(nessuna attivita' registrata)"}
    dormiente = days > threshold
    countdown = round(max(0.0, threshold - days), 3)
    return {
        "agent": agent.get("signature"), "tier": tier, "idle_days": days,
        "threshold_days": threshold, "dormiente": dormiente,
        "days_to_retirement": countdown,
        "reading": (f"{agent.get('signature')}: DORMIENTE da {days}g "
                    f"(soglia {threshold}g, {countdown}g al pensionamento)"
                    if dormiente else
                    f"{agent.get('signature')}: vivo ({days}g dall'ultima attivita')"),
    }


def idleness_report(population: list[dict], *, now: datetime) -> dict:
    """The whole population's idleness: the dormienti named, and the count.

    The state carries this LIVE: every sleeping agent is named, with its countdown
    to retirement, so the shame is public and the pressure is structural.
    """
    rows = [idleness_of(a, now=now) for a in (population or [])]
    dormienti = [r for r in rows if r.get("dormiente")]
    unmeasured = [r for r in rows if r.get("idle_days") is None]
    return {
        "rows": rows,
        "dormienti": dormienti,
        "n_dormienti": len(dormienti),
        "n_unmeasured": len(unmeasured),
        "reading": (f"{len(dormienti)} dormiente/i su {len(rows)} agenti"
                    + (f" ({len(unmeasured)} non misurati)" if unmeasured else "")
                    + ("; il Guardian caccia l'ozio" if dormienti
                       else "; nessuno dorme")),
    }


def retirement_due(population: list[dict], *, now: datetime) -> list[dict]:
    """The agents whose idleness exceeds their tier threshold (retirement due).

    Returned as ``{signature, tier, idle_days, threshold_days}`` rows the tribunal
    can rule on. An unmeasured agent is NEVER listed (never retire on a guess).
    """
    due: list[dict] = []
    for a in (population or []):
        v = idleness_of(a, now=now)
        if v.get("dormiente"):
            due.append({"signature": v["agent"], "tier": v["tier"],
                        "idle_days": v["idle_days"],
                        "threshold_days": v["threshold_days"]})
    return due
