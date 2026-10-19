"""THE COLLECTIVE PULSE — the civilization's heartbeat, and its ENGAGEMENT (Part Three).

THE LIVING RATE. A civilization that breathes produces, every hour: thoughts,
visions, spontaneous acts, inventions. This module reduces the day's REAL activity
log into that rate, and its trend against the prior day. A falling pulse is the
Guardians' ALARM ("la civilta' sta addormentandosi") and the Council must answer it
with corrective pressure.

THE ENGAGEMENT METRIC (item 13, the ultimate health number): the ratio of VOLUNTARY
work to ASSIGNED work. A civilization that WANTS to work (high voluntary share) is
in FLOW STATE; one that only works when told is not free, merely obedient.

Honest-measurement: a rate over an empty log is ``0.0`` with ``measured=False`` (the
system did not live, or did not log); an unmeasured axis is never dressed up as
health. The BALANCE LAW reads pulse and engagement together and proposes a bounded
corrective (more pressure when too passive, deeper reflection when too frantic) —
advice to the Guardians, never a command.
"""

from __future__ import annotations

__all__ = [
    "PULSE_KINDS",
    "collective_pulse",
    "pulse_trend",
    "engagement",
    "balance_law",
]

# The four living acts counted in the pulse (Part Three, item 12).
PULSE_KINDS: tuple[str, ...] = ("thought", "vision", "spontaneous", "invention")

# A pulse this far BELOW the prior day raises the alarm (a real fall, not noise).
PULSE_ALARM_DROP: float = 0.35


def _count_by_kind(activity: list[dict], kind: str) -> int:
    return sum(1 for a in (activity or []) if a.get("kind") == kind)


def collective_pulse(activity: list[dict], *, hours: float = 24.0) -> dict:
    """The LIVING RATE over ``hours``: thoughts/visions/spontaneous/inventions per hour.

    ``activity`` is the day's real log of ``{kind, agent, ts, ...}`` rows. The
    per-hour rate divides by ``hours``; with no hours (or no activity) the rate is an
    honest zero and ``measured`` is False.
    """
    h = float(hours) if hours and hours > 0 else 0.0
    counts = {k: _count_by_kind(activity, k) for k in PULSE_KINDS}
    total = sum(counts.values())
    measured = h > 0 and total > 0
    rate = round(total / h, 3) if h > 0 else 0.0
    per_hour = {k: (round(counts[k] / h, 3) if h > 0 else 0.0) for k in PULSE_KINDS}
    return {
        "counts": counts,
        "total": total,
        "hours": round(h, 2),
        "rate_per_hour": rate,
        "per_hour": per_hour,
        "measured": measured,
        "reading": (f"polso {rate}/h su {round(h, 1)}h "
                    f"(pensieri {counts['thought']}, visioni {counts['vision']}, "
                    f"atti spontanei {counts['spontaneous']}, invenzioni "
                    f"{counts['invention']})" if measured
                    else "polso non misurato (nessuna attivita' registrata)"),
    }


def pulse_trend(today: dict, prior: dict | None) -> dict:
    """The pulse's trend vs the prior day, with the Guardians' alarm when it falls.

    Honest: no prior reading -> no trend (``None``), never a fabricated comparison.
    """
    t = (today or {}).get("rate_per_hour")
    p = (prior or {}).get("rate_per_hour") if prior else None
    if t is None or p is None or not (today or {}).get("measured"):
        return {"delta": None, "direction": None, "alarm": False,
                "reading": "trend del polso non misurato (manca il giorno prima)"}
    delta = round(float(t) - float(p), 3)
    if p > 0:
        pct = round(delta / float(p), 4)
    else:
        pct = None
    alarm = bool(p > 0 and pct is not None and pct < -PULSE_ALARM_DROP)
    direction = "rising" if delta > 0 else ("falling" if delta < 0 else "flat")
    return {
        "delta": delta, "pct": pct, "direction": direction, "alarm": alarm,
        "reading": (f"polso {direction} ({delta:+g}/h"
                    + (f", {pct:+.0%}" if pct is not None else "") + ")"
                    + (" -- ALLARME: la civilta' sta addormentandosi" if alarm else "")),
    }


def engagement(activity: list[dict]) -> dict:
    """The voluntary/assigned ratio — the Guardians' ultimate health number.

    ``voluntary`` counts spontaneous acts; ``assigned`` counts the rest of the
    produced work. With no work at all the ratio is ``None`` (unmeasured), never a
    flattering default. Flow state is a HIGH voluntary share: the civilization WANTS
    to work.
    """
    acts = [a for a in (activity or []) if a.get("kind") in PULSE_KINDS
            or a.get("kind") == "work"]
    voluntary = sum(1 for a in acts if a.get("spontaneous"))
    total = len(acts)
    assigned = total - voluntary
    ratio = round(voluntary / total, 4) if total else None
    return {
        "voluntary": voluntary, "assigned": assigned, "total": total,
        "ratio": ratio,
        "reading": (f"engagement {ratio:.0%} volontario ({voluntary}/{total})"
                    if ratio is not None else "engagement non misurato"),
    }


def balance_law(*, pulse: dict, engagement_reading: dict) -> dict:
    """THE BALANCE LAW (item 13): freedom is the SPACE, pressure is the REASON.

    Reads the pulse and the engagement together and proposes a bounded corrective:

    * too passive (low voluntary share, measured) -> PRESSURE UP (new challenges,
      provocations, territory);
    * too frantic (very high pulse with a low voluntary share is noise) -> RHYTHM
      DOWN (more flow slots, deeper reflection);
    * otherwise FLOW STATE stands.

    Returns advice as data (``pressure`` / ``rhythm`` deltas), never a command.
    """
    ratio = (engagement_reading or {}).get("ratio")
    rate = (pulse or {}).get("rate_per_hour")
    if ratio is None:
        return {"state": "non misurato", "pressure_delta": 0, "rhythm_delta": 0,
                "reading": "bilanciamento non misurato (engagement assente)"}
    if ratio < 0.15:
        return {"state": "troppo passivi", "pressure_delta": 1, "rhythm_delta": 0,
                "reading": ("popolazione troppo passiva: la pressione sale "
                            "(nuove sfide, provocazioni del Consiglio)")}
    if ratio >= 0.15 and isinstance(rate, (int, float)) and rate > 60.0:
        return {"state": "troppo frenetici", "pressure_delta": 0, "rhythm_delta": 1,
                "reading": ("attivita' frenetica: il ritmo rallenta, lo spazio del "
                            "flow si allarga (liberta' che diventa riflessione)")}
    return {"state": "flow", "pressure_delta": 0, "rhythm_delta": 0,
            "reading": ("STATO DI FLOW: alta liberta' e alta pressione -- la "
                        "civilta' VUOLE lavorare")}
