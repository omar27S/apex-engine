"""THE KELLY CALCULATOR -- dynamic position sizing (Mega Phase 2, Section I).

The Titanium Floor (1%) is the LAW's MINIMUM risk per trade. Kelly asks a different
question: given the measured edge, what size MAXIMIZES long-run growth? This module
computes that suggestion -- and ONLY that. It never authorizes a trade: the LAW is
1% minimum, the CEO executes, and a Kelly suggestion above 1% is rendered as advice.

The formula (the fractional-Kelly form the directive names):

    f* = (W * R - L) / R          with L = 1 - W

where ``W`` is the win probability and ``R`` the average win/loss ratio (payoff).
``f*`` is the fraction of equity to risk. It is clipped into a sane band so a
mis-measured edge can never suggest a ruinous size, and it is NEVER below the
Titanium Floor (the floor is a floor, not a target).

Honesty is binding (the standing principle): a win probability or payoff that was
not MEASURED yields ``None`` (never an invented suggestion); the anti-ruin guard
reports ``None`` when it has no return distribution to simulate, never a
flattering zero.

Purity: this module is inert at import -- pure math, no I/O, no wall clock.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from app.core.law import TITANIUM_FLOOR_PCT

__all__ = [
    "KELLY_VERSION",
    "KELLY_CAP_PCT",
    "RUIN_THRESHOLD_PCT",
    "DEFAULT_RUIN_DRAWDOWN",
    "KellyResult",
    "kelly_fraction",
    "kelly_suggestion",
    "risk_of_ruin",
    "anti_ruin_guard",
    "kelly_block",
]

KELLY_VERSION: int = 1

# The hard cap on a Kelly SUGGESTION (percent of equity). Full Kelly is famously
# over-aggressive on a noisy edge; half-Kelly is the common industry compromise and
# this cap keeps a mis-measured ``W`` from ever proposing an account-ending size.
KELLY_CAP_PCT: float = 5.0

# The risk-of-ruin threshold (percent). At or above this the Guardians alarm.
RUIN_THRESHOLD_PCT: float = 5.0

# The ruin definition: the account dropping to this fraction of its start before it
# recovers (the directive's "below 50% before recovering").
DEFAULT_RUIN_DRAWDOWN: float = 0.5


@dataclass(frozen=True)
class KellyResult:
    """The Kelly computation, fully stated (``ok`` is the only actionable field)."""

    ok: bool
    win_prob: float | None
    payoff: float | None
    fraction: float | None          # the raw Kelly fraction (equity share, uncapped)
    suggestion_pct: float | None    # the SUGGESTED risk percent (clipped, floored)
    floor_pct: float
    capped: bool                    # True when the raw fraction exceeded the cap
    reason: str


def kelly_fraction(win_prob: float | None, payoff: float | None) -> float | None:
    """The raw Kelly fraction ``f* = (W*R - L) / R`` (``None`` when unmeasured).

    Fail-closed: a missing/non-positive payoff, or a win probability outside
    ``[0, 1]``, yields ``None`` -- never a fabricated size. A negative ``f*`` means
    the edge is absent: the honest reading is "no bet", returned as the raw value
    (the caller clips it to the floor).
    """
    if win_prob is None or payoff is None:
        return None
    try:
        w = float(win_prob)
        r = float(payoff)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= w <= 1.0) or r <= 0.0:
        return None
    loss = 1.0 - w
    return (w * r - loss) / r


def kelly_suggestion(win_prob: float | None, payoff: float | None, *,
                     cap_pct: float = KELLY_CAP_PCT,
                     floor_pct: float = TITANIUM_FLOOR_PCT) -> KellyResult:
    """The Kelly SUGGESTION as a risk percent, clipped to ``[floor, cap]``.

    The Titanium Floor is the MINIMUM: even a Kelly fraction that computes below it
    is raised to the floor (the law's minimum risk). A fraction above the cap is
    clipped to the cap and flagged ``capped``. Honest: an unmeasured input yields
    ``ok=False`` with a reason, never a number.
    """
    frac = kelly_fraction(win_prob, payoff)
    if frac is None:
        return KellyResult(False, win_prob, payoff, None, None, floor_pct, False,
                           "win probability or payoff unmeasured -- fail closed")
    raw_pct = frac * 100.0
    capped = raw_pct > cap_pct
    suggestion = min(max(raw_pct, floor_pct), cap_pct)
    return KellyResult(
        True, float(win_prob), float(payoff), round(frac, 6),
        round(suggestion, 4), float(floor_pct), bool(capped),
        ("Kelly sotto il pavimento -- si usa il minimo di legge 1%"
         if raw_pct < floor_pct else
         f"Kelly suggerisce {suggestion:.2f}% (tetto {cap_pct:.1f}%)"))


def risk_of_ruin(returns_r: list[float] | None, *, risk_pct: float | None = None,
                 ruin_drawdown: float = DEFAULT_RUIN_DRAWDOWN,
                 paths: int = 2000, horizon: int | None = None,
                 seed: int = 0) -> dict:
    """Monte Carlo risk of ruin from a strategy's historical return distribution.

    Each element of ``returns_r`` is one trade's result in R units (a win is its
    payoff, a loss is ``-1``). We resample ``horizon`` trades per path (default: the
    length of the sample) and compute the fraction of equity path that ever touches
    the ruin drawdown. Sizing is applied per trade as ``risk_pct`` percent of the
    CURRENT equity (compounding), so a losing streak shrinks the base.

    Honest: an empty or missing distribution yields ``measured=False`` and a ``None``
    ruin probability -- never a fabricated zero.
    """
    vals = [float(r) for r in (returns_r or []) if isinstance(r, (int, float))]
    if not vals or risk_pct is None or risk_pct <= 0:
        return {"measured": False, "ruin_prob": None, "paths": 0,
                "horizon": 0, "risk_pct": risk_pct,
                "reading": "rischio di rovina non misurato (nessuna distribuzione)"}
    horizon = int(horizon or len(vals))
    rng = random.Random(seed)
    ruin = 0
    for _ in range(int(paths)):
        equity = 1.0
        peak = 1.0
        for _t in range(horizon):
            r = rng.choice(vals)
            # risk_pct of CURRENT equity at stake; a loss of 1R loses that stake,
            # a win of rR gains r times it.
            equity *= (1.0 + (risk_pct / 100.0) * r)
            peak = max(peak, equity)
            if equity <= peak * (1.0 - ruin_drawdown):
                ruin += 1
                break
    prob = ruin / float(paths)
    return {"measured": True, "ruin_prob": round(prob, 5), "paths": int(paths),
            "horizon": horizon, "risk_pct": round(float(risk_pct), 4),
            "ruin_drawdown": ruin_drawdown,
            "reading": f"rischio di rovina {prob:.2%} su {paths} sentieri"}


def anti_ruin_guard(returns_r: list[float] | None, *,
                    risk_pct: float | None = None,
                    threshold_pct: float = RUIN_THRESHOLD_PCT,
                    **kwargs) -> dict:
    """The Guardians' anti-ruin alarm: fire when the ruin probability is too high.

    Returns the risk-of-ruin measurement PLUS ``alarm`` (True when
    ``ruin_prob >= threshold``). Honest: an unmeasured distribution never alarms on
    a fabricated number -- it reports ``alarm=None`` and says so.
    """
    ror = risk_of_ruin(returns_r, risk_pct=risk_pct, **kwargs)
    if not ror.get("measured"):
        return {**ror, "alarm": None, "threshold_pct": threshold_pct}
    alarm = bool(ror["ruin_prob"] >= (threshold_pct / 100.0))
    return {**ror, "alarm": alarm, "threshold_pct": threshold_pct,
            "reading": (f"rischio di rovina {ror['ruin_prob']:.2%} "
                        f"{'>= soglia' if alarm else '< soglia'} "
                        f"{threshold_pct:.1f}%"
                        + (" -- ALLARME: ridurre le posizioni concorrenti" if alarm
                           else ""))}


def kelly_block(state: dict, *, returns_r: list[float] | None = None,
                win_prob: float | None = None, payoff: float | None = None,
                risk_pct: float | None = None) -> dict:
    """The Letter block: the Kelly suggestion + the anti-ruin reading (honest)."""
    sug = kelly_suggestion(win_prob, payoff)
    ror = anti_ruin_guard(returns_r, risk_pct=risk_pct)
    return {
        "version": KELLY_VERSION,
        "suggestion_pct": sug.suggestion_pct,
        "fraction": sug.fraction,
        "capped": sug.capped,
        "floor_pct": sug.floor_pct,
        "risk_of_ruin": ror.get("ruin_prob"),
        "alarm": ror.get("alarm"),
        "measured": bool(sug.ok or ror.get("measured")),
        "reading": (f"Kelly: {sug.suggestion_pct:.2f}% "
                    f"(pavimento di legge {sug.floor_pct:.1f}%)"
                    if sug.ok else "Kelly: non misurato"),
    }
