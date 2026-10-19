"""THE FOUNDING CHARTER — the governing document's executable half.

The verbatim CEO charter lives at the TOP of ``APEX/AGENTS.md``; this package is
its executable counterpart. It encodes the parts of the charter that must be
COMPUTED, not narrated:

* **THE 8% LIVE LAW** (``charter.deployable_fraction``) — the account's live
  drawdown ceiling is 8%, enforced by ACCOUNT SCALING, never by limiting research.
  The state measures realized DD honestly and reports the deployable fraction; its
  standing job is to make measured DD FALL, which enlarges the fraction.
* **THE INVIOLABLE LAWS** (``charter.INVIOLABLE_LAWS``) — the ten fixed things,
  referenced from the single source of truth ``app.core.law`` (never re-declared).

"DD is DATA, not a cage": the drawdown cage is LIFTED FOR RESEARCH. Nothing here
optimises against a sealed number; this module only measures and reports.

Pure at import (Scar #6): no I/O, no services, no loops.
"""

from __future__ import annotations

from app.core import law

__all__ = [
    "LIVE_DD_CEILING_PCT",
    "INVIOLABLE_LAWS",
    "deployable_fraction",
    "dd_trend",
    "measured_dd_report",
]

# The CEO's live account drawdown ceiling. A POLICY constant (the charter), not a
# research constraint — it never enters a search; it only scales deployed capital.
LIVE_DD_CEILING_PCT: float = 8.0

# THE INVIOLABLE LAWS (never in discussion). Each is a (number, name, source) where
# source is the law.py symbol that IS the law — this table NEVER re-declares a
# value, it names it (Scar #2).
INVIOLABLE_LAWS: tuple[tuple[int, str, str], ...] = (
    (1, "Titanium Floor: 1% minimum risk per trade, forever", "TITANIUM_FLOOR_PCT"),
    (2, "RR minimum 1:2.5 (ambition climbs, evidence-gated)", "MIN_TARGET_RR"),
    (3, "VNSB stops 0.8-1.8x ATR (self-scaling per instrument)", "VNSB_ATR_MULT_MIN"),
    (4, "Parachute at +2.5R locks to +0.5R", "PARACHUTE_TRIGGER_RR"),
    (5, "Human execution only (state proposes, CEO executes)", "HUMAN_EXECUTION_ONLY"),
    (6, "Forex only (now 30 pairs)", "is_tradable_pair"),
    (7, "Funded accounts: stealth, no EA, no webhooks", "FUNDED_STEALTH_MODE"),
    (8, "WebHook 1-click: personal account only", "HUMAN_EXECUTION_ONLY"),
    (9, "Macro radar read-only", "MACRO_RADAR_SYMBOLS"),
    (10, "Absolute honesty: pessimistic fills, honest metrics", "PESSIMISTIC_FILL"),
)


def deployable_fraction(measured_dd_r: float, *,
                        ceiling_pct: float = LIVE_DD_CEILING_PCT) -> float:
    """The fraction of intended capital the CEO may deploy for the current DD.

    The 8% LIVE LAW: capital deployed = ceiling / measured DD. Because 1R == the
    1% Titanium Floor, DD in R is DD in percent, so ``fraction = 8 / DD``. A DD at
    or below the ceiling is fully deployable (fraction 1.0, capped). A non-positive
    or non-finite DD is refused (fail-closed) — a deployable fraction computed off
    a missing number could over-lever the account, the one error the charter can
    never make.
    """
    dd = float(measured_dd_r)
    if dd != dd or dd in (float("inf"), float("-inf")) or dd <= 0.0:
        raise ValueError(f"measured_dd_r must be finite and positive, got {measured_dd_r!r} "
                         "(fail-closed: never over-lever on a missing number)")
    if ceiling_pct <= 0.0:
        raise ValueError(f"ceiling_pct must be positive, got {ceiling_pct!r} (fail-closed)")
    return round(min(1.0, ceiling_pct / dd), 6)


def dd_trend(realized_dd_r: float, prior_dd_r: float | None) -> dict:
    """The direction of DD: the state's standing job is to make it FALL."""
    if prior_dd_r is None:
        return {"direction": "unknown", "delta_r": None}
    delta = round(float(realized_dd_r) - float(prior_dd_r), 4)
    return {"direction": "falling" if delta < 0 else "rising" if delta > 0 else "flat",
            "delta_r": delta}


def measured_dd_report(realized_dd_r: float, *, prior_dd_r: float | None = None,
                       ceiling_pct: float = LIVE_DD_CEILING_PCT) -> dict:
    """The measured-DD report that rides in EVERY nightly summary (charter act 6).

    Reports realized DD honestly, the implied deployable fraction, and the trend —
    so the CEO always sees how much capital the current state could command, and
    whether the answer is growing.
    """
    frac = deployable_fraction(realized_dd_r, ceiling_pct=ceiling_pct)
    return {
        "realized_dd_r": round(float(realized_dd_r), 4),
        "live_ceiling_pct": ceiling_pct,
        "implied_deployable_fraction": frac,
        "implied_deployable_pct": round(frac * 100.0, 2),
        "dd_trend": dd_trend(realized_dd_r, prior_dd_r),
        "note": ("DD is DATA, not a cage: research is unlimited; the CEO scales the "
                 "DEPLOYED fraction to hold the account's live DD at <= 8%."),
    }
