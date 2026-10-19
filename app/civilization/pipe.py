"""THE PIPE -- the VM-to-GitHub conduit, rebuilt so NOTHING leaks (Part Three).

The VM's brain and GitHub were two half-blind mirrors. This module makes ONE pipe:

  * THE UNIFIED STATE ARTIFACT (``apex_state.json``) -- refreshed after EVERY cycle,
    carrying the VM's vital signs: machine hours, queue depth, the falcon's summary,
    the Dragon's latest thought, the Sage's latest note, body utilization, and the
    day's tournament/survivor counts. GitHub ALWAYS has the VM's current vitals;
  * THE HEARTBEAT CONTRACT -- a push older than :data:`HEARTBEAT_MAX_MINUTES` means
    the VM's heartbeat is MISSING; the Letter says so LOUDLY and the GitHub backup
    fires (never silently wrong numbers);
  * THE DUAL LETTER -- the Letter is generated ON THE VM (where the data lives) and
    pushed complete; GitHub's fallback is explicitly labelled "backup letter -- VM
    silent" so the CEO always knows which voice he is reading.

Honest-measurement is the whole point: a "0 hours, 0 ticks" Letter over a LIVE VM is
a leak. If the VM is alive its numbers are in the artifact; if they are missing the
artifact SAYS the VM is silent rather than printing a false zero.

Pure at import (Scar #6): the artifact builder and the heartbeat check are reductions
over the state + a timestamp; the git plumbing lives in the tool.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "PIPE_VERSION",
    "HEARTBEAT_MAX_MINUTES",
    "STATE_ARTIFACT",
    "VM_SILENT_LABEL",
    "apex_state_artifact",
    "heartbeat_status",
    "heartbeat_missing",
    "commit_discipline",
    "dual_letter_label",
    "pipe_block",
]

PIPE_VERSION: int = 1

# The heartbeat contract: no push from the VM in this many minutes is a MISS.
HEARTBEAT_MAX_MINUTES: int = 90

# The unified artifact's filename (committed with every cycle's push).
STATE_ARTIFACT: str = "apex_state.json"

# The label GitHub's fallback Letter carries when the VM is silent.
VM_SILENT_LABEL: str = "backup letter -- VM silent"


def _parse(ts: str) -> datetime | None:
    v = str(ts or "").strip().replace("Z", "+00:00")
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def apex_state_artifact(state: dict, *, ts: str = "", day: str = "") -> dict:
    """Build the UNIFIED STATE ARTIFACT -- the VM's vital signs in one file.

    Every axis is read from the state honestly: an absent axis is ``None`` (never a
    fabricated zero). The artifact is what EVERY push carries, so GitHub always holds
    the VM's current numbers.

    The artifact also carries THE HEARTBEAT: the VM's last push timestamp and its
    fresh/stale reading, so any reader can tell whether the VM is alive without a
    second file. It carries the FLOW block too (what is due now, the day's tournaments
    and their TRIALS), so the artifact PROVES the micro executed.
    """
    st = state or {}
    body = st.get("body") or {}
    machine = st.get("machine_body") or {}
    queue = st.get("queue") or {}
    report = st.get("night_report") or st.get("report") or {}

    def _num(d: dict, *keys):
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)):
                return v
        return None

    def _queue_depth(q: dict, s: dict):
        d = _num(q, "depth", "open") if q else None
        if d is not None:
            return d
        # The committed checkpoint carries the OPEN jobs as a ``queue`` LIST (the
        # journal is separate); its length is the honest depth. An absent list is
        # unmeasured (None), never a fabricated 0.
        if q and isinstance(q.get("queue"), list):
            return len(q["queue"])
        return _num(s, "queue_depth")

    def _first(d: dict, *keys):
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)):
                return v
        return None

    # A measured 0.0 is a real reading (an idle machine is 0% busy), so coalesce on
    # ``None`` explicitly -- an ``or`` would discard a legitimate zero.
    machine_hours = _first(st, "machine_hours", "uptime_hours")
    if machine_hours is None:
        machine_hours = _first(body, "hours_worked")
    body_util = _first(body, "utilization", "util_pct")
    if body_util is None:
        body_util = _first(machine, "utilization")

    tournaments = _num(report, "tournaments", "tournament_count")
    if tournaments is None:
        tournaments = _num(st, "tournaments_today")
    survivors = _num(report, "survivors", "survivor_count")
    if survivors is None:
        # The night report's real survivor count (``survivor_population``; a list in
        # some reports). Without this the tube printed "sopravvissuti None" even while
        # four strategies had survived the gauntlet, because only ``survivors_pooled``
        # (never written) was read. A real, present count -- never a fabricated one.
        sv = report.get("survivor_population", report.get("survivor_genomes"))
        if isinstance(sv, list):
            survivors = len(sv)
        else:
            survivors = _num(report, "survivor_population")
    if survivors is None:
        survivors = _num(st, "survivors_today")

    artifact_ts = ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pipe_state = st.get("pipe") or {}
    last_push_ts = str(pipe_state.get("last_push_ts", "") or "")
    heartbeat = heartbeat_status(last_push_ts=last_push_ts, now_ts=artifact_ts)

    # THE FLOW BLOCK: the river's logbook, reduced for the artifact. Imported lazily to
    # keep the pipe free of a cycle-time import (flow imports rotation only).
    try:
        from app.civilization import flow as _flow
        flow_block = _flow.flow_report(st, ts=artifact_ts)
    except Exception:  # noqa: BLE001 -- the artifact must never fail on the flow
        flow_block = None

    # The river's logbook PROVES the day's tournaments even when the report block is
    # absent (the hourly pipe runs against a state with no night_report): fall back to
    # the flow's own count of REAL dispatches, never a fabricated number.
    if tournaments is None and isinstance(flow_block, dict):
        tournaments = (flow_block.get("today") or {}).get("total")
    if survivors is None:
        survivors = _num(st, "survivors_pooled")

    return {
        "ts": artifact_ts,
        "day": day or "",
        # The vitals are read under BOTH the artifact's canonical names and the
        # tools' native ones (the body reports ``hours_worked``/``util_pct``, the
        # queue checkpoint a ``queue`` list): without the fallbacks the tube printed
        # an empty None even after the body had really measured the machine.
        "machine_hours": machine_hours,
        "queue_depth": _queue_depth(queue, st),
        "body_utilization": body_util,
        "falcon": (st.get("falcon_summary")
                   or (st.get("falcon") or {}).get("summary")),
        "dragon_thought": (st.get("dragon") or {}).get("thought"),
        "sage_note": ((st.get("sage") or {}).get("ceo_notes") or [None])[-1],
        "tournaments_today": tournaments,
        "survivors_today": survivors,
        "last_push_ts": last_push_ts or None,
        "heartbeat": heartbeat,
        "flow": flow_block,
        # THE FIRST ASCENSION (Jumps 4, 3, 6): the present-moment blocks -- the regime
        # map (what skin the system wears), the forward-test (what the present judges),
        # and the stress-test (the portfolio's live vulnerability). Honest: an absent
        # block stays None (never a fabricated reading).
        "regime": st.get("regime_summary"),
        "forward_test": st.get("forward_test_summary"),
        "stress_test": st.get("stress_test_summary"),
    }


def heartbeat_status(*, last_push_ts: str, now_ts: str,
                     max_minutes: int = HEARTBEAT_MAX_MINUTES) -> dict:
    """The heartbeat reading: is the VM's last push fresh, stale, or unmeasured?

    Honest: an unparseable timestamp is ``non misurato`` (never assumed alive).
    """
    last, now = _parse(last_push_ts), _parse(now_ts)
    if last is None or now is None:
        return {"age_minutes": None, "missing": None, "measured": False,
                "reading": "battito non misurato (timestamp assente)"}
    age = max(0.0, (now - last).total_seconds() / 60.0)
    missing = age > max_minutes
    return {"age_minutes": round(age, 1), "missing": missing, "measured": True,
            "reading": (f"battito del VM: {age:.0f} min fa"
                        + (" -- BATTITO ASSENTE, indago" if missing else " (regolare)"))}


def heartbeat_missing(*, last_push_ts: str, now_ts: str,
                      max_minutes: int = HEARTBEAT_MAX_MINUTES) -> bool:
    """True only when a MEASURED heartbeat is stale (never on an unmeasured one)."""
    st = heartbeat_status(last_push_ts=last_push_ts, now_ts=now_ts,
                          max_minutes=max_minutes)
    return st["missing"] is True


def commit_discipline(*, rebase: bool = True, retries: int = 3) -> dict:
    """The commit discipline the VM's push follows (--rebase + bounded retries).

    The ledger conflicts are resolved by the merge logic already built; the pipe
    never jams and never force-pushes over the CEO's work.
    """
    return {"rebase": bool(rebase), "retries": max(0, int(retries)),
            "force_push": False,
            "reading": (f"disciplina di commit: --rebase, {int(retries)} tentativi, "
                        "mai force-push")}


def dual_letter_label(*, vm_silent: bool) -> dict:
    """The DUAL LETTER label: the VM's voice, or GitHub's labelled backup.

    When the VM is silent GitHub may generate the Letter, but it is LABELLED so the
    CEO always knows which voice he reads.
    """
    return {"vm_generated": not vm_silent,
            "label": (VM_SILENT_LABEL if vm_silent else "lettera del VM"),
            "reading": (VM_SILENT_LABEL if vm_silent else "lettera generata sul VM")}


def pipe_block(state: dict, *, last_push_ts: str = "", now_ts: str = "",
               day: str = "") -> dict:
    """The pipe's block for the Letter: the artifact's vitals + the heartbeat."""
    art = apex_state_artifact(state, ts=now_ts, day=day)
    hb = heartbeat_status(last_push_ts=last_push_ts, now_ts=now_ts)
    return {"artifact": art, "heartbeat": hb,
            "reading": (hb["reading"] + f"; ultimo stato: "
                        f"{art['ts']}")}
