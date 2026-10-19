"""THE ADAPTIVE RHYTHM -- the cadence bends to what the machine measured.

R61 fixed the Heart's beat at every 3 hours. That is a ceiling chosen without
measurement. The three Guardians measure the real machine, account budget and
terms rate; this module turns their readings into the rhythm the Heart SHOULD run
at, honestly bounded:

  * the machine's own max safe cadence sets the floor interval (a hotter, busier
    box is asked less often; a cold idle box may be asked a little more),
  * the account's remaining free minutes set an interval that cannot overrun the
    quota,
  * the terms rate can only ever SLOW the beat, never speed it past the machine.

The result is always clamped to ``[MIN_INTERVAL_S, MAX_INTERVAL_S]``: the rhythm
adapts, but never below the safe floor nor above the watchdog's patience.

Never assumed: an unmeasured Guardian contributes no constraint (that axis does
not bind this night). With nothing measured, the rhythm is the original 3 hours.

Pure at import (Scar #6).
"""

from __future__ import annotations

import math

__all__ = [
    "MIN_INTERVAL_S",
    "MAX_INTERVAL_S",
    "BASE_INTERVAL_S",
    "adaptive_interval_s",
    "adaptive_rhythm_report",
]

BASE_INTERVAL_S: int = 3 * 3600      # R61 -- the unmeasured default (3 hours)
MIN_INTERVAL_S: int = 3600           # never faster than hourly (no busy loop)
MAX_INTERVAL_S: int = 24 * 3600      # never slower than daily (no silent death)


def _seconds_or_none(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def adaptive_interval_s(*, machine_safe_interval_s=None,
                        account_remaining_min=None,
                        account_minutes_per_run=None,
                        terms_min_interval_s=None) -> dict:
    """Fold the measured Guardian readings into one interval, with its reasons.

    Each constraint is optional; an unmeasured axis is listed under
    ``unmeasured`` and does not bind. The chosen interval is the MAXIMUM of the
    binding floors (the slowest requirement wins), clamped to the safe range.
    """
    reasons: list[str] = []
    unmeasured: list[str] = []
    candidates: list[float] = []

    ms = _seconds_or_none(machine_safe_interval_s)
    if ms is None:
        unmeasured.append("machine")
    else:
        candidates.append(ms)
        reasons.append(f"machine floor {int(ms)}s")

    rem = _seconds_or_none(account_remaining_min)
    per = _seconds_or_none(account_minutes_per_run)
    if rem is None or per is None:
        unmeasured.append("account")
    else:
        # The remaining minutes can fund `beats_left` runs; to make them last a
        # full day the beat must be no faster than the day divided by the beats
        # affordable. This is a FLOOR on the interval (a slower beat is allowed).
        beats_left = max(rem / per, 1.0)
        interval = (24 * 3600.0) / beats_left
        candidates.append(interval)
        reasons.append(f"account budget floor {int(interval)}s "
                       f"({beats_left:.1f} beats/day affordable)")

    ts = _seconds_or_none(terms_min_interval_s)
    if ts is None:
        unmeasured.append("terms")
    else:
        candidates.append(ts)
        reasons.append(f"terms floor {int(ts)}s")

    raw = max(candidates) if candidates else float(BASE_INTERVAL_S)
    chosen = int(min(max(raw, MIN_INTERVAL_S), MAX_INTERVAL_S))
    clamped = "as-measured" if chosen == int(raw) else (
        "floor" if raw < MIN_INTERVAL_S else "ceiling")
    return {
        "interval_s": chosen,
        "raw_interval_s": int(raw),
        "clamped": clamped,
        "reasons": reasons,
        "unmeasured": unmeasured,
        "binding": bool(candidates),
    }


def adaptive_rhythm_report(**kwargs) -> dict:
    """The nightly reading: the interval the Heart should beat at, and why."""
    d = adaptive_interval_s(**kwargs)
    hours, rem_s = divmod(d["interval_s"], 3600)
    minutes = rem_s // 60
    pretty = f"{hours}h" + (f" {minutes}m" if minutes else "")
    d["reading"] = (
        f"rhythm: every {pretty} "
        f"({'; '.join(d['reasons']) or 'no measured constraint -- 3h default'};"
        f" {d['clamped']})")
    return d
