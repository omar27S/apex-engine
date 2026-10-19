"""THE CONTINUOUS STREAMS — from a nightly batch to a breathing day (Part Two).

The civilization no longer lives once a night. On the VM it runs STREAMS, each with
its own cadence, all feeding the shared state so that at ANY moment someone is
thinking, seeing, inventing or evolving:

* item 6  MICRO-EVOLUTION  — hourly micro-tournaments (pop 20-40, 1 gen, rotating
            seed, 2-3 pairs); survivors feed the shared pool IMMEDIATELY.
* item 7  SEEING STREAM    — the hawk writes to a SHARED SENSOR BUFFER every 5
            minutes (ticks, DOM, spreads); patrol rotates every 2 hours.
* item 8  THINKING STREAM  — reflect slots hourly (rotating agents); dreams run
            IMMEDIATELY after significant events; the belief ledger updates live.
* item 9  INVENTION STREAM — Author micro-sessions every 2 hours; the playground is
            always open; the Market of Ideas funds and bursts in real time.

This module is the DATA + the SCHEDULE (pure at import, Scar #6): it derives, from a
timestamp, WHICH stream is due and with WHAT seed, and it appends the day's real
activity to a bounded log. It never reads the wall clock itself and never performs
I/O — the daemon on the VM supplies the time and runs the work.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.civilization import rotation

__all__ = [
    "ACTIVITY_KINDS",
    "activity_log",
    "record_activity",
    "sensor_buffer",
    "append_reading",
    "micro_tournament_plan",
    "due_streams",
    "stream_report",
]

# The four living acts (they feed the collective pulse) plus plain work.
ACTIVITY_KINDS: tuple[str, ...] = ("thought", "vision", "spontaneous", "invention",
                                   "work")


def activity_log(state: dict) -> list[dict]:
    """The day's real activity log (bounded to the most recent 2000 rows)."""
    return state.setdefault("activity", [])


def record_activity(state: dict, *, kind: str, agent: str, what: str,
                    spontaneous: bool = False, ts: str = "") -> dict:
    """Append one living act to the log (the pulse's source). Fail-closed on kind."""
    if kind not in ACTIVITY_KINDS:
        raise ValueError(f"unknown activity kind {kind!r}; known: {ACTIVITY_KINDS}")
    row = {"ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "kind": kind, "agent": str(agent), "what": str(what),
           "spontaneous": bool(spontaneous)}
    log = activity_log(state)
    log.append(row)
    del log[:-2000]
    return row


# --- item 7: the SHARED SENSOR BUFFER --------------------------------------

SENSOR_BUFFER_MAX: int = 288  # 24h at one reading every 5 minutes


def sensor_buffer(state: dict) -> list[dict]:
    """The shared sensor buffer: the hawk's recent readings, consulted by all."""
    return state.setdefault("sensor_buffer", [])


def append_reading(state: dict, *, pair: str, ticks: float | None,
                   dom: list | None = None, spreads: dict | None = None,
                   ts: str = "") -> dict:
    """The hawk appends one reading (every 5 min) to the shared buffer.

    Honest: an unmeasured tick is carried as ``None`` (never a fabricated number).
    The buffer is bounded (the last 24h), so the state never grows forever.
    """
    row = {"ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "pair": str(pair),
           "ticks": ticks if isinstance(ticks, (int, float)) else None,
           "dom": list(dom or []), "spreads": dict(spreads or {})}
    buf = sensor_buffer(state)
    buf.append(row)
    del buf[:-SENSOR_BUFFER_MAX]
    return row


# --- item 6: the MICRO-EVOLUTION plan --------------------------------------


def micro_tournament_plan(*, dispatch_ts: str, slot: int = 0,
                          population: int = 30, pairs: int = 3) -> dict:
    """One micro-tournament's plan: a ROTATING seed from the dispatch timestamp.

    Bounded (pop 20-40, 1 generation, 2-3 pairs) and honest: the seed rotates with
    the dispatch, so two hours never draw the same tournament.
    """
    pop = max(20, min(40, int(population)))
    n_pairs = max(2, min(3, int(pairs)))
    seed = rotation.micro_seed(dispatch_ts=dispatch_ts, slot=slot)
    return {
        "kind": "micro_tournament", "dispatch_ts": str(dispatch_ts),
        "seed": seed, "population": pop, "generations": 1, "pairs": n_pairs,
        "reading": (f"micro-torneo: pop {pop}, 1 gen, {n_pairs} coppie, "
                    f"seme {seed} (dal dispatch {dispatch_ts})"),
    }


# --- the STREAM SCHEDULE ---------------------------------------------------


def _hour(ts: str) -> tuple[int, int] | None:
    v = str(ts or "").strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.hour, dt.minute


def due_streams(ts: str, *, phase: dict | None = None) -> dict:
    """Which streams are DUE at this timestamp (the VM's rhythm).

    * micro-evolution: every hour (on the hour);
    * thinking (reflect): every hour, offset to :30;
    * invention (author): every 2 hours (even hours);
    * patrol: every 2 hours (even hours) — doubled in alert/peak phases;
    * sensor reading: every 5 minutes.

    Honest: no parseable timestamp -> nothing is due (the schedule is unmeasured).
    """
    hm = _hour(ts)
    if hm is None:
        return {"ts": ts, "due": [], "measured": False,
                "reading": "orologio non misurato (timestamp assente)"}
    hour, minute = hm
    due: list[str] = []
    if minute < 5:
        due.append("micro_evolution")
    if 30 <= minute < 35:
        due.append("thinking")
    if hour % 2 == 0 and minute < 5:
        due.append("invention")
        due.append("patrol")
    due.append("sensor_reading")  # every 5 minutes: the hawk always appends
    patrol_mult = (phase or {}).get("patrol_mult", 1.0)
    return {"ts": str(ts), "hour": hour, "minute": minute, "due": due,
            "patrol_mult": patrol_mult, "measured": True,
            "reading": ("stream dovuti: " + (", ".join(due) if due else "nessuno"))}


def stream_report(state: dict, *, ts: str = "") -> dict:
    """The streams' health: the activity log size, the buffer depth, the schedule."""
    act = state.get("activity") or []
    buf = state.get("sensor_buffer") or []
    return {
        "activity_rows": len(act),
        "sensor_rows": len(buf),
        "due": due_streams(ts).get("due") if ts else None,
        "reading": (f"stream: {len(act)} atti registrati, "
                    f"{len(buf)} letture nel buffer condiviso"),
    }
