"""THE RUNNER WATCHDOG -- a dead Heart must never look like a quiet night.

R76's heartbeat watches the NIGHT on GitHub Actions. Nothing watched the
self-hosted runners themselves: ``apex-heart`` and ``apex-turbo`` could go
offline and the machine would look peaceful. This module is the missing watch.

It reads the runners' live status (``online``/``offline`` + ``busy``) and renders
ONE verdict the night report can carry:

  * ``healthy`` -- every expected runner is online,
  * ``degraded`` -- an expected runner is offline (the Heart cannot beat),
  * ``busy``    -- an expected runner is online but mid-job (not a fault).

An expected runner that is MISSING entirely (not registered) is ``degraded``: a
name the deployment promises but GitHub does not list is a real fault.

Pure at import (Scar #6): the verdict is a reduction of the caller's status list.
"""

from __future__ import annotations

__all__ = [
    "EXPECTED_RUNNERS",
    "runner_verdict",
    "runner_watchdog_report",
]

# The two runners the ignition script promises by name (one per repo).
EXPECTED_RUNNERS: tuple[str, ...] = ("apex-heart", "apex-turbo")


def _index(runners) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in runners or []:
        name = str(r.get("name", "")).strip()
        if not name:
            continue
        out[name] = {
            "name": name,
            "status": str(r.get("status", "")).lower(),
            "busy": bool(r.get("busy", False)),
            "labels": [str(x) for x in (r.get("labels") or [])],
        }
    return out


def runner_verdict(runners, *, expected=EXPECTED_RUNNERS, measured: bool = True) -> dict:
    """Reduce the live runner list into a verdict over the EXPECTED names.

    ``measured=False`` means the status could not be read at all (an API refusal,
    a missing token): the verdict is ``unmeasured`` and NEVER alerts -- a number
    the state does not have must not raise an alarm.
    """
    idx = _index(runners)
    if not measured:
        return {
            "status": "unmeasured", "alert": False,
            "expected": list(expected), "online": [], "busy": [],
            "offline": [], "missing": [], "faults": [],
            "reading": "runners: unmeasured (status not read -- no alarm raised)",
        }
    missing: list[str] = []
    offline: list[str] = []
    busy: list[str] = []
    online: list[str] = []
    for name in expected:
        r = idx.get(name)
        if r is None:
            missing.append(name)
        elif r["status"] != "online":
            offline.append(name)
        elif r["busy"]:
            busy.append(name)
        else:
            online.append(name)

    if missing or offline:
        status = "degraded"
    elif busy:
        status = "busy"
    else:
        status = "healthy"

    faults = [f"missing: {n}" for n in missing] + [f"offline: {n}" for n in offline]
    return {
        "status": status,
        "alert": status == "degraded",
        "expected": list(expected),
        "online": online,
        "busy": busy,
        "offline": offline,
        "missing": missing,
        "faults": faults,
        "reading": (
            f"runners: {status} -- online {online or '[]'}"
            + (f"; busy {busy}" if busy else "")
            + (f"; FAULTS {faults}" if faults else "")),
    }


def runner_watchdog_report(runners, *, expected=EXPECTED_RUNNERS,
                           measured: bool = True) -> dict:
    """The nightly reading: the two runners' liveness, ready for the report."""
    v = runner_verdict(runners, expected=expected, measured=measured)
    v["all"] = _index(runners)
    return v
