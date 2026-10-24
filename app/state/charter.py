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
    "EVIDENCE_HALF_LIFE_NIGHTS",
    "INVIOLABLE_LAWS",
    "evidence_weight",
    "witnessed_fraction",
    "deployable_fraction",
    "dd_trend",
    "measured_dd_report",
]

# The CEO's live account drawdown ceiling. A POLICY constant (the charter), not a
# research constraint — it never enters a search; it only scales deployed capital.
LIVE_DD_CEILING_PCT: float = 8.0

# R142 — THE HONEST WITNESS: the nights of realized evidence at which the witness
# vouches for HALF of the raw fraction. One quiet night must not vouch for the
# whole account; a season of realized nights can (a Wilson-flavoured shrinkage
# applied to CAPITAL, not to research — the cage stays lifted for research).
EVIDENCE_HALF_LIFE_NIGHTS: int = 10


def evidence_weight(evidence_nights: int) -> float:
    """How much of the raw fraction the EVIDENCE can vouch for (0.0 .. 1.0).

    ``w = nights / (nights + EVIDENCE_HALF_LIFE_NIGHTS)``: with the half-life at
    10 realized nights, one night vouches for 1/11 (~9%), ten for 1/2, forty for
    4/5. A negative count is refused (fail-closed); ZERO realized nights vouch
    for NOTHING (0.0) — an unmeasured season never cosigns capital.
    """
    n = int(evidence_nights)
    if n < 0:
        raise ValueError(f"evidence_nights must be >= 0, got {evidence_nights!r} "
                         "(fail-closed: never vouch on a negative season)")
    return n / (n + EVIDENCE_HALF_LIFE_NIGHTS)


def witnessed_fraction(raw_fraction: float, *, evidence_nights: int) -> float:
    """The fraction the EVIDENCE can vouch for: raw x weight, honestly shrunk.

    The raw law (``8 / DD``, capped at 1.0) answers "what WOULD the charter allow";
    the witnessed fraction answers "what can tonight's EVIDENCE actually stand
    behind". Thin evidence shrinks toward zero; a season approaches the raw law.
    """
    return round(min(1.0, float(raw_fraction)) * evidence_weight(evidence_nights), 6)

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
                        ceiling_pct: float = LIVE_DD_CEILING_PCT,
                        evidence_nights: int | None = None) -> float:
    """The fraction of intended capital the CEO may deploy for the current DD.

    The 8% LIVE LAW: capital deployed = ceiling / measured DD. Because 1R == the
    1% Titanium Floor, DD in R is DD in percent, so ``fraction = 8 / DD``. A DD at
    or below the ceiling is fully deployable (fraction 1.0, capped). A non-positive
    or non-finite DD is refused (fail-closed) — a deployable fraction computed off
    a missing number could over-lever the account, the one error the charter can
    never make.

    R142 — ``evidence_nights`` (optional): when given, the fraction is WITNESSED —
    shrunk by how many realized nights stand behind the number (see
    :func:`evidence_weight`). ``None`` keeps the raw law untouched (the legacy
    callers and the tests that pin the law itself).
    """
    dd = float(measured_dd_r)
    if dd != dd or dd in (float("inf"), float("-inf")) or dd <= 0.0:
        raise ValueError(f"measured_dd_r must be finite and positive, got {measured_dd_r!r} "
                         "(fail-closed: never over-lever on a missing number)")
    if ceiling_pct <= 0.0:
        raise ValueError(f"ceiling_pct must be positive, got {ceiling_pct!r} (fail-closed)")
    raw = round(min(1.0, ceiling_pct / dd), 6)
    if evidence_nights is None:
        return raw
    return witnessed_fraction(raw, evidence_nights=evidence_nights)


def headline_deployable(block: dict) -> dict:
    """R154 — THE WITNESSED HEADLINE: which deployable fraction the CEO reads.

    A LIVE crown (orders dispatched) certifies the implied fraction — the
    raw law applied to a realized DD. A PAPER crown (no order ever
    dispatched) cannot certify its own safety: the headline is the
    WITNESSED fraction, what the realized nights can actually vouch for.
    The Dragon's first denuncia of 2026-10-24, amputated mid-sentence by
    the token limit, was exactly this: "witnessed 28.57%, implied 100% —
    that 71.4% is not a safety margin, it is INFLATION". Zero measured
    stays zero measured: the evidence grows with nights, never with the
    absence of dispatch.

    R155 — THE LIVE CROWN: when the crown carries its live measurements
    (``live_resolved`` judged dispatches and the ``live_dd_r`` the tape
    measured), the 8% law applies to the LIVE DD — the tape is the judge,
    the research curve a hypothesis — witnessed by the count of judged
    dispatches. A dispatch born with nothing judged yet keeps the paper
    witness; a legacy crown (dispatch counted, measurements absent) keeps
    the implied reading it was given: committed bytes never change voice.
    """
    block = block or {}
    crown = block.get("crown") or {}
    if (crown.get("dispatched_trades") or 0) > 0:
        if "live_resolved" in crown:
            # R155 — the crown carries its live measurements: the law
            # follows the tape, never the research curve's desire.
            live_dd = crown.get("live_dd_r")
            resolved = crown.get("live_resolved") or 0
            if (isinstance(live_dd, (int, float)) and live_dd >= 0
                    and live_dd == live_dd and live_dd != float("inf")
                    and int(resolved) > 0):
                try:
                    raw = (deployable_fraction(float(live_dd))
                           if float(live_dd) > 0.0 else 1.0)
                except ValueError:
                    raw = None
                if raw is not None:
                    frac = witnessed_fraction(raw, evidence_nights=int(resolved))
                    return {"headline_deployable_pct": round(frac * 100.0, 2),
                            "headline_deployable_basis": (
                                "live dispatch (the 8% law on the LIVE measured "
                                f"DD {float(live_dd):.2f}R over {int(resolved)} "
                                "judged dispatches; the tape is the judge, the "
                                "research curve a hypothesis)")}
            if int(resolved or 0) == 0:
                # dispatch is born, nothing judged on the tape yet: the paper
                # witness still speaks (the realized nights remain the best
                # evidence the house has).
                if block.get("witnessed_deployable_pct") is not None:
                    return {"headline_deployable_pct":
                            block["witnessed_deployable_pct"],
                            "headline_deployable_basis": (
                                "witnessed (dispatch is born but nothing judged "
                                "on the tape yet; the realized nights remain the "
                                "best evidence)")}
                return {"headline_deployable_pct":
                        block.get("implied_deployable_pct"),
                        "headline_deployable_basis": (
                            "implied (dispatch is born, nothing judged yet, and "
                            "no witness nights behind the number)")}
        # legacy live shape (dispatch counted, no live measurements carried):
        # the committed bytes keep the reading they were given.
        return {"headline_deployable_pct": block.get("implied_deployable_pct"),
                "headline_deployable_basis": "implied (the live crown dispatches)"}
    if block.get("witnessed_deployable_pct") is not None:
        return {"headline_deployable_pct": block.get("witnessed_deployable_pct"),
                "headline_deployable_basis": (
                    "witnessed (the crown is paper: no order ever dispatched; "
                    "the evidence stands behind what it can vouch for, never "
                    "the raw law)")}
    return {"headline_deployable_pct": block.get("implied_deployable_pct"),
            "headline_deployable_basis": (
                "implied (no witness nights behind the number yet)")}


def dd_trend(realized_dd_r: float, prior_dd_r: float | None) -> dict:
    """The direction of DD: the state's standing job is to make it FALL."""
    if prior_dd_r is None:
        return {"direction": "unknown", "delta_r": None}
    delta = round(float(realized_dd_r) - float(prior_dd_r), 4)
    return {"direction": "falling" if delta < 0 else "rising" if delta > 0 else "flat",
            "delta_r": delta}


def measured_dd_report(realized_dd_r: float, *, prior_dd_r: float | None = None,
                       ceiling_pct: float = LIVE_DD_CEILING_PCT,
                       evidence_nights: int | None = None) -> dict:
    """The measured-DD report that rides in EVERY nightly summary (charter act 6).

    Reports realized DD honestly, the implied deployable fraction, and the trend —
    so the CEO always sees how much capital the current state could command, and
    whether the answer is growing.

    R142 — THE HONEST WITNESS: with ``evidence_nights`` the report ALSO carries the
    WITNESSED fraction — the raw law shrunk by how many realized nights stand
    behind the number. One quiet night must never vouch for the whole account;
    the implied (raw) fraction stays for continuity, the witnessed one is what
    the evidence can actually stand behind.
    """
    frac = deployable_fraction(realized_dd_r, ceiling_pct=ceiling_pct)
    out = {
        "realized_dd_r": round(float(realized_dd_r), 4),
        "live_ceiling_pct": ceiling_pct,
        "implied_deployable_fraction": frac,
        "implied_deployable_pct": round(frac * 100.0, 2),
        "dd_trend": dd_trend(realized_dd_r, prior_dd_r),
        "note": ("DD is DATA, not a cage: research is unlimited; the CEO scales the "
                 "DEPLOYED fraction to hold the account's live DD at <= 8%."),
    }
    if evidence_nights is not None:
        w = evidence_weight(evidence_nights)
        wf = round(frac * w, 6)
        out["evidence_nights"] = int(evidence_nights)
        out["evidence_weight"] = round(w, 4)
        out["witnessed_deployable_fraction"] = wf
        out["witnessed_deployable_pct"] = round(wf * 100.0, 2)
        out["note"] += (f" The WITNESSED fraction ({wf * 100.0:.2f}%) is what "
                        f"{int(evidence_nights)} realized night(s) of evidence "
                        f"can vouch for; a season approaches the raw law.")
    return out
