"""R13 — SINGLE HEALTH DEFINITION. One sealed classifier for every family.

Phase 2.3a left two divergent local flags: the census's ``mute_raw``/
``structurally_muted`` and the tribunal's GATED-ZERO detector. They disagreed by
one count on ``hurst_reversion_filtered`` / CADJPY (raw=49), so a reviewer could
read "fine" from one artifact and "thin" from the other. R13 deletes both: the
census and the tribunal consume :func:`family_health` ONLY.

The classification, in order (the order IS the doctrine):

1. ``THIN``      — ``raw < law.MUTE_RAW_THRESHOLD``. Not enough evidence to say
   anything about the family on this tape; a thin family is never called dead.
2. ``GATED-DEAD``— enough raw signals, but every active gate profile removes all
   of them. The gates, not the tape, are the bottleneck.
3. ``HEALTHY``   — otherwise.

``gated_by_profile`` maps a profile name to its final (post-gate) signal count.
Only profiles where the gate stack is ACTIVE are passed (the census sends
``trend``/``counter``, not the gates-off baseline); an empty map means "no gate
profile applies", so a non-thin family is HEALTHY.

Pure, no I/O, no services. ``law`` is the single source of the threshold (Scar #2).
"""

from __future__ import annotations

from typing import Mapping

from app.core import law

__all__ = ["THIN", "GATED_DEAD", "HEALTHY", "STATES", "family_health"]

THIN = "THIN"
GATED_DEAD = "GATED_DEAD"
HEALTHY = "HEALTHY"
STATES: frozenset[str] = frozenset({THIN, GATED_DEAD, HEALTHY})


def family_health(raw: int, gated_by_profile: Mapping[str, int]) -> dict:
    """Classify a family's health on one tape (R13).

    ``raw`` is the family's raw signal count (gates off). ``gated_by_profile``
    maps each ACTIVE gate profile to its final signal count after gating.

    Returns ``{"state": one of STATES, "raw": int, "gated": {profile: int}}``.
    """
    raw = int(raw)
    gated = {str(k): int(v) for k, v in dict(gated_by_profile or {}).items()}
    if raw < law.MUTE_RAW_THRESHOLD:
        state = THIN
    elif gated and all(v == 0 for v in gated.values()):
        state = GATED_DEAD
    else:
        state = HEALTHY
    return {"state": state, "raw": raw, "gated": gated}
