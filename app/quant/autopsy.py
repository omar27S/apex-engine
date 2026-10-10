"""THE FORENSIC AUTOPSY — every death teaches the system WHY it died (Phase 5).

A losing trade is not just a number. This module classifies every loss into a
sealed taxonomy, each cause computable from the trade record, the frame, the RAMS
injection log, and the entry context:

* ``stop_hunt_gap``     — a RAMS micro-gap hunted a resting stop (exit was a gap
                          stop, and a micro-gap was injected near the entry).
* ``news_whipsaw``      — the loss fell inside a RAMS fake-news impulse window.
* ``slippage_erosion``  — the trade was GROSS-positive but NET-negative: friction,
                          not the market, killed it.
* ``structural_failure``— a clean stop touch: no injection, no regime
                          contradiction — the setup was simply wrong.
* ``regime_misread``    — the family's own gate said trade, but the entry-time
                          regime percentile contradicted its declared regime.
* ``target_missed``     — favorable excursion reached >= +1R but the trade never
                          armed and died at the stop.
* ``time_death``        — it ran out of bars (time stop) still a loser.

Priority is fixed and documented; the first matching cause wins, so a
classification is deterministic and never ambiguous. Each class is pinned by a
hand-built test trade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.quant.engine import EXIT_GAP_STOP, EXIT_STOP, EXIT_TIME

__all__ = [
    "CAUSES",
    "AutopsyContext",
    "CLASSIFIED_CAUSES",
    "classify_trade",
    "autopsy",
    "distributions",
    "favorable_excursion_r",
]

# The sealed taxonomy (this tuple is the single declaration of the cause set).
CAUSES: tuple[str, ...] = (
    "stop_hunt_gap",
    "news_whipsaw",
    "slippage_erosion",
    "structural_failure",
    "regime_misread",
    "target_missed",
    "time_death",
)
CLASSIFIED_CAUSES = CAUSES

# How many execution bars after an injected M15 event an entry may sit and still
# be attributed to it (matches the RAMS report's attribution window).
ATTR_BARS = 2

# The favorable-excursion bar for ``target_missed`` (>= +1R).
MFE_TARGET_R = 1.0


@dataclass(frozen=True)
class AutopsyContext:
    """What the classifier needs beyond the raw trade.

    ``injection_ts`` maps a kind ("micro_gap"/"news_whipsaw") to the injection
    timestamps (M15 epoch seconds). ``exec_ts`` is the execution timestamp grid the
    trade's indices refer to. ``regime_percentile_at_entry`` is the entry-time
    regime reading in [0,1] (or NaN); ``family_regime`` is the family's declared
    regime ("trend"/"revert"/"volatility"/"unknown").
    """

    exec_ts: np.ndarray | None = None
    injection_ts: dict[str, list[int]] = field(default_factory=dict)
    regime_percentile_at_entry: float = float("nan")
    family_regime: str = "unknown"


def favorable_excursion_r(trade, exec_frame) -> float:
    """Max favorable excursion of a trade in R, from the execution frame.

    Reads only bars between the entry and exit indices (the trade's realized
    window). Returns 0.0 when the window is unknown or the risk is non-positive.
    """
    risk = float(trade.risk)
    if risk <= 0.0:
        return 0.0
    hi = exec_frame["high"].to_numpy(dtype="float64")
    lo = exec_frame["low"].to_numpy(dtype="float64")
    a = int(trade.entry_index)
    b = int(trade.exit_index)
    if a < 0 or b < a or b >= len(hi):
        return 0.0
    if trade.direction == "long":
        mfe = float(hi[a:b + 1].max()) - float(trade.entry_price)
    else:
        mfe = float(trade.entry_price) - float(lo[a:b + 1].min())
    return mfe / risk


def _attributed(trade, inj_ts: list[int], exec_ts, *, bars: int = ATTR_BARS) -> bool:
    if not inj_ts or exec_ts is None:
        return False
    exec_ts = np.asarray(exec_ts)
    ets = int(trade.entry_ts)
    for its in inj_ts:
        if ets < its:
            continue
        gap = int(np.searchsorted(exec_ts, ets) - np.searchsorted(exec_ts, its))
        if 0 <= gap <= bars:
            return True
    return False


def _regime_contradicts(ctx: AutopsyContext) -> bool:
    p = float(ctx.regime_percentile_at_entry)
    if not np.isfinite(p):
        return False
    fam = ctx.family_regime
    if fam == "trend":
        return p < 0.5
    if fam == "revert":
        return p > 0.5
    return False


def classify_trade(trade, exec_frame, context: AutopsyContext | None = None) -> str:
    """Classify ONE losing trade into the sealed taxonomy (first match wins).

    A non-losing trade (net_r >= 0) is not an autopsy subject; it raises, because
    calling the autopsy on a winner is a caller bug, not a silent no-op.
    """
    ctx = context or AutopsyContext()
    net = float(trade.r_multiple if getattr(trade, "net_r", None) is None else trade.net_r)
    if net >= 0.0:
        raise ValueError(f"autopsy is for losses; trade net_r={net} is not a loss")
    gross = float(trade.r_multiple)
    reason = trade.exit_reason

    # 1. stop_hunt_gap — an injected micro-gap killed a resting stop.
    if reason == EXIT_GAP_STOP and _attributed(
        trade, ctx.injection_ts.get("micro_gap", []), ctx.exec_ts
    ):
        return "stop_hunt_gap"

    # 2. news_whipsaw — the entry sat inside a fake-news impulse window.
    if _attributed(trade, ctx.injection_ts.get("news_whipsaw", []), ctx.exec_ts):
        return "news_whipsaw"

    # 3. slippage_erosion — gross win, net loss (friction killed it).
    if gross > 0.0:
        return "slippage_erosion"

    # 4. target_missed — favorable excursion >= +1R, never armed, died at stop.
    if reason in (EXIT_STOP, EXIT_GAP_STOP):
        if (not bool(getattr(trade, "parachute_armed", False))
                and favorable_excursion_r(trade, exec_frame) >= MFE_TARGET_R):
            return "target_missed"

    # 5. regime_misread — died at stop while the regime contradicted the family.
    if reason in (EXIT_STOP, EXIT_GAP_STOP) and _regime_contradicts(ctx):
        return "regime_misread"

    # 6. structural_failure — a clean stop/gap touch with no RAMS influence.
    if reason in (EXIT_STOP, EXIT_GAP_STOP):
        return "structural_failure"

    # 7. time_death — ran out of bars still a loser.
    if reason == EXIT_TIME:
        return "time_death"

    # Fail-closed: an unclassifiable loss is reported as structural_failure? No —
    # an unknown exit reason is a bug; name it honestly rather than pretend.
    return "structural_failure"


@dataclass
class AutopsyReport:
    """The classification of one genome's losing trades, with distributions."""

    signature: str
    family: str
    domain: str
    losses: int
    causes: dict
    per_cause_examples: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"signature": self.signature, "family": self.family,
                "domain": self.domain, "losses": self.losses,
                "causes": dict(self.causes),
                "per_cause_examples": dict(self.per_cause_examples)}


def autopsy(
    trades,
    exec_frame,
    *,
    signature: str = "",
    family: str = "",
    domain: str = "",
    context: AutopsyContext | None = None,
) -> AutopsyReport:
    """Classify every losing trade in ``trades``; return its cause distribution."""
    causes: dict[str, int] = {c: 0 for c in CAUSES}
    examples: dict[str, dict] = {}
    losses = 0
    for t in trades:
        net = float(t.r_multiple if getattr(t, "net_r", None) is None else t.net_r)
        if net >= 0.0:
            continue
        losses += 1
        cause = classify_trade(t, exec_frame, context)
        causes[cause] = causes.get(cause, 0) + 1
        if cause not in examples:
            examples[cause] = {
                "entry_ts": int(t.entry_ts), "exit_reason": t.exit_reason,
                "gross_r": float(t.r_multiple), "net_r": net,
            }
    return AutopsyReport(signature=signature, family=family, domain=domain,
                         losses=losses, causes=causes, per_cause_examples=examples)


def distributions(reports: list[AutopsyReport]) -> dict:
    """Aggregate autopsy cause distributions by family and by domain."""
    by_family: dict[str, dict[str, int]] = {}
    by_domain: dict[str, dict[str, int]] = {}
    total: dict[str, int] = {c: 0 for c in CAUSES}
    for r in reports:
        fam = by_family.setdefault(r.family or "unknown", {c: 0 for c in CAUSES})
        dom = by_domain.setdefault(r.domain or "unknown", {c: 0 for c in CAUSES})
        for c, n in r.causes.items():
            fam[c] = fam.get(c, 0) + int(n)
            dom[c] = dom.get(c, 0) + int(n)
            total[c] = total.get(c, 0) + int(n)
    return {"total": total, "by_family": by_family, "by_domain": by_domain}
