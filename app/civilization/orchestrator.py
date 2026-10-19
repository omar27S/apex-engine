"""THE ORCHESTRATOR — the VM as the civilization's NERVOUS SYSTEM (Part Two, item 10).

The VM runs many streams (the Council, the body, the hawk's eye, the micro-evolution
tournaments, the thinking/invention streams). One master service coordinates them:

* it reads each stream's LAST TICK (a heartbeat file the stream refreshes) and
  reports the VITAL SIGNS — every stream's name, its age, and whether it is ALIVE;
* a stream silent beyond :data:`STALL_SECONDS` (1 hour) is a STALL: the orchestrator
  logs it loudly and advises a RESTART (the caller restarts the unit; the pure
  functions here never call systemctl themselves);
* it reports the REBOOT ARMOR: whether the system came back within
  :data:`RECOVERY_TARGET_S` (60 seconds) after a boot.

Honest-measurement (the CEO's principle): a stream with NO recorded tick is
``non misurato`` — never assumed alive, never assumed dead. The caller supplies the
ticks (the wall clock is passed in), so the logic is deterministic and testable.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "STALL_SECONDS",
    "RECOVERY_TARGET_S",
    "STREAMS",
    "stream_age_s",
    "vital_signs",
    "stalls",
    "recovery_within_armor",
    "orchestrator_report",
]

# A stream silent this long is stalled (Part Two, item 10: "stall > 1 hour").
STALL_SECONDS: int = 3600
# The reboot armor: full recovery must land inside this window (item 10: "< 60s").
RECOVERY_TARGET_S: int = 60

# The streams the orchestrator watches (name -> the human reading).
STREAMS: dict[str, str] = {
    "council": "the perpetual Council (deliberation + standby)",
    "queue": "the body (the infinite work queue)",
    "hawk_eye": "the hawk's eye (the live market sense)",
    "micro_evolution": "the hourly micro-tournament stream",
    "thinking": "the hourly reflect slots",
    "invention": "the author micro-sessions",
    "sensor_buffer": "the shared sensor buffer",
}


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


def stream_age_s(stream: dict, *, now: datetime) -> float | None:
    """Seconds since a stream's last tick, or ``None`` when unmeasured."""
    last = _parse(stream.get("last_tick"))
    if last is None:
        return None
    return max(0.0, (now - last).total_seconds())


def vital_signs(streams: dict[str, dict], *, now: datetime,
                stall_seconds: int = STALL_SECONDS) -> dict:
    """The VITAL SIGNS: every stream's age, alive/stalled/unmeasured, honestly."""
    rows: list[dict] = []
    for name in STREAMS:
        s = (streams or {}).get(name) or {}
        age = stream_age_s(s, now=now)
        if age is None:
            state = "non misurato"
        elif age > stall_seconds:
            state = "stalled"
        else:
            state = "alive"
        rows.append({"stream": name, "what": STREAMS[name],
                     "last_tick": s.get("last_tick"), "age_s": age,
                     "state": state, "restart": state == "stalled"})
    alive = sum(1 for r in rows if r["state"] == "alive")
    stalled = sum(1 for r in rows if r["state"] == "stalled")
    unmeasured = sum(1 for r in rows if r["state"] == "non misurato")
    return {
        "rows": rows, "alive": alive, "stalled": stalled,
        "unmeasured": unmeasured, "n": len(rows),
        "reading": (f"segni vitali: {alive}/{len(rows)} vivi, {stalled} fermi"
                    + (f", {unmeasured} non misurati" if unmeasured else "")),
    }


def stalls(streams: dict[str, dict], *, now: datetime,
           stall_seconds: int = STALL_SECONDS) -> list[dict]:
    """The stalled streams (to restart), never an unmeasured one."""
    return [r for r in vital_signs(streams, now=now,
                                   stall_seconds=stall_seconds)["rows"]
            if r["state"] == "stalled"]


def recovery_within_armor(*, boot_ts: str, ready_ts: str,
                          target_s: int = RECOVERY_TARGET_S) -> dict:
    """The reboot armor reading: did the system recover inside the target window?

    Honest: an unparseable timestamp -> unmeasured (None), never a pass.
    """
    b, r = _parse(boot_ts), _parse(ready_ts)
    if b is None or r is None:
        return {"recovery_s": None, "within_target": None,
                "reading": "recupero non misurato (timestamp assente)"}
    secs = round((r - b).total_seconds(), 3)
    within = secs <= target_s
    return {"recovery_s": secs, "within_target": within,
            "reading": (f"armatura di riavvio: recupero in {secs}s "
                        + ("(dentro i 60s)" if within else "(FUORI i 60s)"))}


def orchestrator_report(streams: dict[str, dict], *, now: datetime,
                        boot_ts: str = "", ready_ts: str = "") -> dict:
    """The master reading: vital signs + the stalls to restart + the reboot armor."""
    vs = vital_signs(streams, now=now)
    st = [r for r in vs["rows"] if r["state"] == "stalled"]
    armor = (recovery_within_armor(boot_ts=boot_ts, ready_ts=ready_ts)
             if boot_ts and ready_ts else None)
    return {
        "vital_signs": vs,
        "stalls": st,
        "restart_advised": [r["stream"] for r in st],
        "reboot_armor": armor,
        "reading": (vs["reading"] + (f"; {len(st)} stream da riavviare" if st
                                     else "; nessun fermo")),
    }
