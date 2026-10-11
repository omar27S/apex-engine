"""THE CONSTITUTION — the Ten Eternal Laws of APEX.

This module is the single source of truth for every sealed constant and every
fail-closed gate. No other module may re-declare these constants.

Account currency is USD. Build Mode: this module is inert — pure functions only,
no I/O at import time, no services, no side effects.

Dependency direction (no circular imports): ``pairs`` imports ``law``. Therefore
``law`` must not import ``pairs`` at module load. ``is_tradable_pair`` resolves
the Constellation lazily, inside the function body, only when no universe is
supplied by the caller.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple

# ---------------------------------------------------------------------------
# The Ten Eternal Laws (sealed constants).
# ---------------------------------------------------------------------------
TITANIUM_FLOOR_PCT = 1.0  # minimum risk per trade (below = reject)
MIN_TARGET_RR = 2.5  # minimum reward:risk, no upper ceiling
VNSB_ATR_MULT_MIN = 0.8  # stop band, in ATR(14) M15 multiples
VNSB_ATR_MULT_MAX = 1.8
PARACHUTE_TRIGGER_RR = 2.5  # at this touch the stop locks...
PARACHUTE_LOCK_RR = 0.5  # ...to +0.5R, forever
HUMAN_EXECUTION_ONLY = True  # machine advises, CEO executes
FUNDED_STEALTH_MODE = True  # funded accounts: no EA, no webhooks
MACRO_RADAR_SYMBOLS = ("DXY", "WTI", "US10Y", "VIX")  # read-only sensors
PESSIMISTIC_FILL = True  # backtest books the worst intrabar case

# R11 — MUTE-DEF DOCTRINE. The census raw-fire floor below which a family is
# called MUTE on a pair. A single sealed source so the threshold can never drift
# between the census tool and any later audit. A family with raw signals at or
# above this floor whose every signal is gated away at all three profiles is
# GATED-DEAD (a computed condition), never silently dropped.
MUTE_RAW_THRESHOLD = 50

# R85 — THE GROSS-TO-FRICTION GATE (Phase 7i). A candidate must earn its own
# friction many times over before it is worth expensive rounds. The gate runs at
# STAIRCASE ROUND 1 (the cheap screen) and requires the GROSS edge to clear the
# conservative friction multiple:
#
#     gross_r >= FRICTION_MULTIPLE * |friction_r|,   friction_r = gross_r - net_r
#
# FRICTION_MULTIPLE is sealed at 3.0 — three times the friction is the margin a
# candidate must plausibly pay. It is a floor on EVIDENCE, not a promise of edge.
FRICTION_MULTIPLE = 3.0


class GrossFrictionVerdict(NamedTuple):
    """R85 — the gross-to-friction ruling (``ok`` is the only actionable field)."""

    ok: bool
    gross_r: float
    friction_r: float
    multiple: float  # gross_r / |friction_r| (inf when friction is zero)
    reason: str


def gross_to_friction_verdict(gross_r: float, net_r: float) -> GrossFrictionVerdict:
    """R85 — approve iff ``gross_r >= FRICTION_MULTIPLE * |friction_r|``.

    ``friction_r = gross_r - net_r`` is the cost the market charged (>= 0 in the
    honest, cost-on path). Fail-closed:

    * a non-positive gross edge is rejected (nothing to pay friction with);
    * zero friction (a diagnostic gross run, or a frictionless slice) is rejected,
      because the gate must not pass on an un-invoiced evaluation — with no
      friction it carries no evidence that the edge survives it.

    A gross-rich, friction-poor body (gross 1000, net -2000) is therefore rejected
    at round 1, before it can cost minutes in the expensive rounds.
    """
    g = float(gross_r)
    n = float(net_r)
    friction = g - n
    if g <= 0.0:
        return GrossFrictionVerdict(False, g, friction, 0.0,
                                    "non-positive gross edge — nothing to pay friction with")
    if friction <= 0.0:
        return GrossFrictionVerdict(False, g, friction, float("inf"),
                                    "zero friction recorded — un-invoiced evaluation refused")
    multiple = g / friction
    if multiple < FRICTION_MULTIPLE:
        return GrossFrictionVerdict(
            False, g, friction, multiple,
            f"gross/friction {multiple:.2f} < sealed multiple {FRICTION_MULTIPLE:g}")
    return GrossFrictionVerdict(
        True, g, friction, multiple,
        f"gross/friction {multiple:.2f} >= sealed multiple {FRICTION_MULTIPLE:g}")


def friction_breakdown(gross_r: float, net_r: float) -> dict:
    """R85 (Phase 7j) — the gate's arithmetic, stated per body so the search can
    SEE how far a candidate sits from the bar.

    ``paid_multiple`` is the gross/friction ratio the body ACTUALLY paid
    (``gross_r / |friction_r|``; ``inf`` when friction is zero). ``breakeven_ratio``
    is the gross edge needed per unit of friction to clear the sealed multiple
    (always ``FRICTION_MULTIPLE``) — the bar itself. ``distance`` is
    ``paid_multiple - FRICTION_MULTIPLE`` (negative = short of the bar; positive =
    clears it). ``gap_to_bar_r`` is the extra gross R the body would need ON THIS
    FRICTION to reach the bar (0 when it already clears; ``inf`` when nonsensical).
    Reports only — the ruling is :func:`gross_to_friction_verdict`.
    """
    g = float(gross_r)
    n = float(net_r)
    friction = g - n
    v = gross_to_friction_verdict(g, n)
    paid = v.multiple
    if friction > 0.0 and g > 0.0:
        distance = paid - FRICTION_MULTIPLE
        gap_r = max(0.0, FRICTION_MULTIPLE * friction - g)
    else:
        distance = float("-inf") if g <= 0.0 else float("inf")
        gap_r = float("inf")
    return {
        "gross_r": round(g, 4),
        "net_r": round(n, 4),
        "friction_r": round(friction, 4),
        "paid_multiple": (None if paid == float("inf") else round(paid, 4)),
        "breakeven_ratio": FRICTION_MULTIPLE,
        "distance_from_bar": (None if distance in (float("inf"), float("-inf"))
                              else round(distance, 4)),
        "gap_to_bar_r": (None if gap_r == float("inf") else round(gap_r, 4)),
        "gate_ok": bool(v.ok),
        "reason": v.reason,
    }


# R86 — THE MIRROR-WINDOW RULE (Phase 7i). Every evaluation report that carries a
# verdict carries BOTH windows: the SHORT-WINDOW diagnostic (the last
# MIRROR_SHORT_WINDOW_ROWS M15 bars — the ~20k tail the author sessions once used)
# and the FULL-TAPE verdict. "Survivor" is defined ONLY as full-tape-positive; the
# short window exists so a tape-window artifact (a body alive on the tail, dead on
# the full tape — e.g. the Baptism's friday_fade) can never be mistaken for an edge.
MIRROR_SHORT_WINDOW_ROWS = 20000


def mirror_window_verdict(full_positive: bool, short_positive: bool) -> dict:
    """R86 — label a body's two windows; FULL-TAPE decides "survivor", not the tail.

    Returns a plain dict so any report can embed it. ``survivor`` is True iff the
    FULL tape is positive. ``window_artifact`` is True when the short diagnostic is
    positive but the full tape is not — the exact failure mode R85/R86 exist to catch.
    """
    return {
        "full_tape_positive": bool(full_positive),
        "short_window_positive": bool(short_positive),
        "survivor": bool(full_positive),
        "window_artifact": bool(short_positive and not full_positive),
        "definition": "survivor == full-tape-positive (R86)",
    }



# ---------------------------------------------------------------------------
# Verdicts (plain data carriers; ``ok`` is the only field a caller may act on).
# ---------------------------------------------------------------------------
class Verdict(NamedTuple):
    ok: bool
    reason: str


class VnsbVerdict(NamedTuple):
    ok: bool
    multiplier: float | None
    reason: str


class RrVerdict(NamedTuple):
    ok: bool
    ratio: float | None
    reason: str


class TitaniumVerdict(NamedTuple):
    ok: bool
    reason: str


class LawViolation(ValueError):
    """Raised when a caller supplies levels that violate the Constitution.

    A bad lock is a bug in the caller, not a trade to book — this is an
    invariant breach, not a rejectable market condition.
    """


def _normalize_direction(direction: str) -> str | None:
    """Return canonical ``"long"``/``"short"`` or ``None`` if unknown."""
    if not isinstance(direction, str):
        return None
    d = direction.strip().lower()
    if d in ("long", "buy"):
        return "long"
    if d in ("short", "sell"):
        return "short"
    return None


# ---------------------------------------------------------------------------
# Pair gate.
# ---------------------------------------------------------------------------
def normalize_pair(symbol: str) -> str | None:
    """Return the canonical 6-letter pair code, or ``None`` if not canonical.

    Strips broker suffixes (everything from the first ``"."``), uppercases, and
    accepts only alphabetic 6-letter codes. It does NOT check tradability — that
    is the job of :func:`is_tradable_pair`.
    """
    if not isinstance(symbol, str):
        return None
    canonical = symbol.strip().upper().split(".", 1)[0]
    if len(canonical) != 6 or not canonical.isalpha():
        return None
    return canonical


def is_tradable_pair(symbol: str, universe: Iterable[str] | None = None) -> bool:
    """THE hard gate: is ``symbol`` a tradable Constellation pair?

    Fail-closed: a symbol that does not normalize cleanly is rejected. When
    ``universe`` is ``None`` the Constellation is resolved lazily from
    ``app.core.pairs`` (see module docstring); an empty/unavailable universe
    rejects everything.
    """
    canonical = normalize_pair(symbol)
    if canonical is None:
        return False
    if universe is None:
        from app.core.pairs import CONSTELLATION_PAIRS  # lazy: see module docstring

        universe = CONSTELLATION_PAIRS
    return canonical in universe


# ---------------------------------------------------------------------------
# VNSB stop-band gate.
# ---------------------------------------------------------------------------
def vnsb_verdict(sl_pips: float | None, atr_pips: float | None) -> VnsbVerdict:
    """Judge a stop distance against the ATR(14) M15 band.

    ``multiplier = sl_pips / atr_pips`` must fall within
    ``[VNSB_ATR_MULT_MIN, VNSB_ATR_MULT_MAX]`` (inclusive). Fail-closed: a
    missing or non-positive ATR rejects with the sealed reason string.
    """
    if atr_pips is None or atr_pips <= 0:
        return VnsbVerdict(False, None, "no ATR reading — fail closed")
    if sl_pips is None or sl_pips <= 0:
        return VnsbVerdict(False, None, "no stop distance — fail closed")
    multiplier = sl_pips / atr_pips
    if multiplier < VNSB_ATR_MULT_MIN:
        return VnsbVerdict(False, multiplier, "stop band below VNSB minimum")
    if multiplier > VNSB_ATR_MULT_MAX:
        return VnsbVerdict(False, multiplier, "stop band above VNSB maximum")
    return VnsbVerdict(True, multiplier, "within VNSB band")


# ---------------------------------------------------------------------------
# Reward:risk gate.
# ---------------------------------------------------------------------------
def rr_verdict(tp_distance: float | None, sl_distance: float | None) -> RrVerdict:
    """Approve iff ``tp_distance / sl_distance >= MIN_TARGET_RR``.

    Distances are positive magnitudes. Fail-closed on missing or non-positive
    inputs.
    """
    if sl_distance is None or sl_distance <= 0:
        return RrVerdict(False, None, "no stop distance — fail closed")
    if tp_distance is None or tp_distance <= 0:
        return RrVerdict(False, None, "no target distance — fail closed")
    ratio = tp_distance / sl_distance
    if ratio < MIN_TARGET_RR:
        return RrVerdict(False, ratio, "reward:risk below minimum")
    return RrVerdict(True, ratio, "reward:risk acceptable")


# ---------------------------------------------------------------------------
# Titanium floor gate.
# ---------------------------------------------------------------------------
def titanium_verdict(risk_pct: float | None) -> TitaniumVerdict:
    """Approve iff risk per trade is at least ``TITANIUM_FLOOR_PCT`` percent."""
    if risk_pct is None:
        return TitaniumVerdict(False, "no risk figure — fail closed")
    if risk_pct < TITANIUM_FLOOR_PCT:
        return TitaniumVerdict(False, "risk below titanium floor")
    return TitaniumVerdict(True, "risk at or above titanium floor")


# ---------------------------------------------------------------------------
# Parachute gate.
# ---------------------------------------------------------------------------
def parachute_levels(
    entry: float, stop: float, direction: str
) -> tuple[float | None, float | None]:
    """Return ``(trigger_price, locked_stop_price)`` for the parachute.

    Long:  trigger = entry + 2.5R, lock = entry + 0.5R.
    Short: trigger = entry - 2.5R, lock = entry - 0.5R, where R = |entry-stop|.

    Fail-closed: unknown direction or non-positive risk returns ``(None, None)``.
    """
    d = _normalize_direction(direction)
    if d is None:
        return (None, None)
    if entry is None or stop is None:
        return (None, None)
    risk = abs(entry - stop)
    if risk <= 0:
        return (None, None)
    if d == "long":
        return (entry + PARACHUTE_TRIGGER_RR * risk, entry + PARACHUTE_LOCK_RR * risk)
    return (entry - PARACHUTE_TRIGGER_RR * risk, entry - PARACHUTE_LOCK_RR * risk)


def effective_stop(
    direction: str,
    entry: float | None,
    trailing_candidate: float | None,
    locked_stop: float | None,
) -> float | None:
    """Clamp a trailing stop so it never violates the parachute lock.

    The lock MUST already be on the profitable side of ``entry``: long requires
    ``locked_stop >= entry``, short requires ``locked_stop <= entry``. A lock on
    the losing side is a caller bug, so this raises :class:`LawViolation` with the
    offending values rather than silently returning a stop that would risk more
    than the parachute allows.

    Long:  ``max(trailing_candidate, locked_stop)``.
    Short: ``min(trailing_candidate, locked_stop)``.

    Fail-closed: unknown direction or any missing input (entry, candidate, lock)
    returns ``None``.
    """
    d = _normalize_direction(direction)
    if d is None:
        return None
    if entry is None or trailing_candidate is None or locked_stop is None:
        return None
    if d == "long":
        if locked_stop < entry:
            raise LawViolation(
                f"long locked_stop {locked_stop} is not at/above entry {entry}"
            )
        return max(trailing_candidate, locked_stop)
    if locked_stop > entry:
        raise LawViolation(
            f"short locked_stop {locked_stop} is not at/below entry {entry}"
        )
    return min(trailing_candidate, locked_stop)
