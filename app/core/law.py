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
