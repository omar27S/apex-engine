"""THE LIVING BLOCK — one reduction that makes a cycle BREATHE (Parts Two-Three).

A single deliberation cycle is a heartbeat; this module turns a day of heartbeats
into LIFE. It records the real acts (a thought per deliberating agent, a vision when
the eyes opened, an invention when a body was forged, a spontaneous act when a free
agent asked for work), then reduces them into the readings the CEO asked for:

* I DORMIENTI   — the Idleness Guardian's live flag (who is sleeping, and the
                  countdown to retirement) over the real activity stamps;
* IL POLSO      — the collective pulse (thoughts/visions/spontaneous/inventions per
                  hour) and its trend against the prior day, with the alarm;
* L'ENGAGEMENT  — the voluntary/assigned ratio (flow state);
* IL BILANCIO   — the Balance Law's advice (more pressure, or deeper reflection);
* IL RITMO      — the circadian phase;
* SEGNI VITALI  — the orchestrator's stream health (unmeasured on CI, honestly).

Honest-measurement: an axis with no data stays ``None`` / "non misurato"; the pulse
over an empty log is an honest zero with ``measured=False``, never a dressed-up
health reading. Pure at import (Scar #6): a reduction over the state + the ts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.civilization import circadian, idleness, orchestrator, pulse, streams

__all__ = [
    "STANDING_AGENTS",
    "agent_activity",
    "touch",
    "record_life",
    "window_rows",
    "living_block",
]

# The standing minds the cycle always deliberates with (the Council of Kings + the
# specialists). The population's signatures join them as agents are born.
STANDING_AGENTS: tuple[str, ...] = ("king-trend", "king-range", "philosopher-1",
                                    "explorer-1", "sniper-1")


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


def agent_activity(state: dict) -> dict:
    """The per-agent activity stamps (the source of the idleness reading)."""
    return state.setdefault("agent_activity", {})


def touch(state: dict, *, agent: str, act: str, ts: str) -> None:
    """Stamp an agent's last ``act`` at ``ts`` (``thought``/``vision``/...)."""
    slot = agent_activity(state).setdefault(str(agent), {})
    slot[f"last_{act}"] = str(ts)
    slot.setdefault("tier_hint", "newborn")


def record_life(state: dict, *, agents: list[str], ts: str, thought_agents=None,
                vision: bool = False, inventions: int = 0,
                spontaneous: int = 0) -> dict:
    """Record the cycle's REAL acts into the activity log + the agent stamps.

    Only acts that actually happened are recorded: a thought for each agent that
    deliberated, a vision only when the eyes opened, an invention only for a body
    forged, a spontaneous act only for a free request accepted. No padding.
    """
    acts = {"thought": 0, "vision": 0, "invention": 0, "spontaneous": 0}
    for a in (thought_agents or agents or []):
        touch(state, agent=a, act="thought", ts=ts)
        streams.record_activity(state, kind="thought", agent=a,
                                what="deliberated in the cycle", ts=ts)
        acts["thought"] += 1
    if vision:
        touch(state, agent="king-trend", act="vision", ts=ts)
        streams.record_activity(state, kind="vision", agent="king-trend",
                                what="the eyes opened on the market", ts=ts)
        acts["vision"] += 1
    for i in range(int(inventions or 0)):
        streams.record_activity(state, kind="invention", agent=f"author-{i + 1}",
                                what="authored a body", ts=ts)
        acts["invention"] += 1
    for i in range(int(spontaneous or 0)):
        touch(state, agent=f"agent-{i + 1}", act="spontaneous", ts=ts)
        streams.record_activity(state, kind="spontaneous", agent=f"agent-{i + 1}",
                                what="acted on its own initiative", spontaneous=True,
                                ts=ts)
        acts["spontaneous"] += 1
    return acts


def window_rows(state: dict, *, ts: str, hours: float = 24.0) -> list[dict]:
    """The activity rows within ``hours`` of ``ts`` (the pulse's window)."""
    now = _parse(ts)
    rows = state.get("activity") or []
    if now is None:
        return list(rows)
    lo = now.timestamp() - hours * 3600.0
    out = []
    for r in rows:
        t = _parse(r.get("ts"))
        if t is not None and t.timestamp() >= lo:
            out.append(r)
    return out


def _agent_rows(state: dict, agents: list[str]) -> list[dict]:
    """The agent records the idleness guardian reads (stamps + a tier hint)."""
    act = agent_activity(state)
    pop = {a.get("signature"): a for a in (state.get("population") or [])}
    names = list(dict.fromkeys(list(agents or []) + list(pop)))
    rows: list[dict] = []
    for n in names:
        slot = dict(act.get(n) or {})
        base = pop.get(n) or {}
        slot.setdefault("signature", n)
        slot.setdefault("is_king", str(n).startswith("king"))
        slot.setdefault("generations", base.get("generations", 0))
        rows.append(slot)
    return rows


def living_block(state: dict, *, agents: list[str], ts: str,
                 vision: bool = False, inventions: int = 0,
                 spontaneous: int = 0, phase_override: str | None = None) -> dict:
    """The full life reduction for the Letter: dormienti, pulse, engagement, rhythm."""
    now = _parse(ts) or datetime.now(timezone.utc)
    rows = _agent_rows(state, agents)
    idle = idleness.idleness_report(rows, now=now)

    today = pulse.collective_pulse(window_rows(state, ts=ts, hours=24.0), hours=24.0)
    history = state.setdefault("pulse_history", {})
    day = str(ts)[:10] if ts else ""
    prior = None
    if day:
        # the prior day's stored pulse (never invented: absent -> no trend)
        keys = sorted(k for k in history if k < day)
        prior = history[keys[-1]] if keys else None
    trend = pulse.pulse_trend(today, prior)
    eng = pulse.engagement(window_rows(state, ts=ts, hours=24.0))
    bal = pulse.balance_law(pulse=today, engagement_reading=eng)
    circ = circadian.circadian_reading(ts, override=phase_override)
    vitals = orchestrator.vital_signs(state.get("streams") or {}, now=now)
    if day:
        history[day] = today

    return {
        "dormienti": idle["dormienti"],
        "n_dormienti": idle["n_dormienti"],
        "idleness": idle,
        "pulse": today,
        "pulse_trend": trend,
        "engagement": eng,
        "balance": bal,
        "circadian": circ,
        "vital_signs": vitals,
        "reading": (f"{idle['reading']}; {today['reading']}; "
                    f"{trend['reading']}; {eng['reading']}"),
    }
