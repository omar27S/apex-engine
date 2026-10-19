"""THE CIRCADIAN RHYTHM — the breath of the living day (Part Five, item 16).

The civilization does not run at a flat rate; it BREATHES with the market's day:

* ASIAN calm     -- flow, light reflection, patrol thin;
* LONDON alert   -- micro-tournaments up, patrol doubles, the Council cycles faster;
* NY peak        -- full engagement: invention at maximum, simulation density highest;
* EVENING        -- consolidation: dreams, revisions, archival.

The Guardians may EXTEND or SHORTEN a phase based on the market's real behaviour, so
this module exposes the phase as a bounded, overridable reading rather than a fixed
clock. Honest: with no timestamp the phase is ``non misurato`` (None) — never a
fabricated "peak".

Pure at import (Scar #6): a reduction over an hour-of-day integer.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "PHASES",
    "CIRCADIAN_BY_PHASE",
    "phase_of_hour",
    "phase_at",
    "circadian_reading",
    "council_interval_s",
]

# The four phases, as (name, start_hour_utc, end_hour_utc) in the day (end exclusive;
# the evening wraps to the next day). Boundaries are the classic FX sessions.
PHASES: tuple[tuple[str, int, int], ...] = (
    ("asian_calm", 0, 7),        # Tokyo calm, light reflection
    ("london_alert", 7, 13),     # London open: the day wakes
    ("ny_peak", 13, 20),         # London/NY overlap: the peak
    ("evening_consolidation", 20, 24),  # close, consolidate, archive
)

# Per-phase rhythm: how the streams turn with the day. ``patrol_mult`` doubles the
# patrol in the alert/peak hours; ``council_interval_s`` is the Council's cycle.
CIRCADIAN_BY_PHASE: dict[str, dict] = {
    "asian_calm": {"flow": "light reflection", "patrol_mult": 0.5,
                   "micro_mult": 0.5, "invention_mult": 0.5,
                   "council_interval_s": 3600, "simulation_density": "low"},
    "london_alert": {"flow": "alert", "patrol_mult": 2.0, "micro_mult": 1.0,
                     "invention_mult": 1.0, "council_interval_s": 900,
                     "simulation_density": "medium"},
    "ny_peak": {"flow": "full engagement", "patrol_mult": 2.0, "micro_mult": 1.0,
                "invention_mult": 1.0, "council_interval_s": 900,
                "simulation_density": "highest"},
    "evening_consolidation": {"flow": "consolidation", "patrol_mult": 0.5,
                              "micro_mult": 0.5, "invention_mult": 0.5,
                              "council_interval_s": 1800, "simulation_density": "low"},
}


def phase_of_hour(hour: int) -> str:
    """The phase name for an hour of day (UTC), fail-closed outside 0..23."""
    h = int(hour)
    if not 0 <= h <= 23:
        raise ValueError(f"hour must be 0..23, got {hour!r}")
    for name, start, end in PHASES:
        if start <= h < end:
            return name
    return "evening_consolidation"  # 23 -> evening (defensive; unreachable above)


def phase_at(ts: str) -> str | None:
    """The phase at an ISO-8601 timestamp, or ``None`` when unmeasured (no ts)."""
    if not str(ts or "").strip():
        return None
    v = str(ts).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return phase_of_hour(dt.astimezone(timezone.utc).hour)


def circadian_reading(ts: str, *, override: str | None = None) -> dict:
    """The day's phase reading. ``override`` lets the Guardians bend the rhythm.

    Honest: no timestamp and no override -> the phase is unmeasured (None).
    """
    name = override if override in CIRCADIAN_BY_PHASE else phase_at(ts)
    if name is None:
        return {"phase": None, "measured": False,
                "reading": "ritmo circadiano non misurato (nessuna ora)"}
    cfg = dict(CIRCADIAN_BY_PHASE[name])
    cfg["phase"] = name
    cfg["measured"] = True
    cfg["overridden"] = bool(override)
    cfg["reading"] = (f"fase {name}: {cfg['flow']}, "
                      f"pattuglia x{cfg['patrol_mult']}, "
                      f"ciclo Consiglio {cfg['council_interval_s']}s, "
                      f"simulazioni {cfg['simulation_density']}")
    return cfg


def council_interval_s(ts: str, *, override: str | None = None) -> int | None:
    """The Council's deliberation interval for the day's phase (the rhythm)."""
    return circadian_reading(ts, override=override).get("council_interval_s")
