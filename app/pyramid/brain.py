"""THE BRAIN WIRING — genome + report + frames -> Oracle AOS -> Veto gate (3.2).

This module is the connective tissue between the honest evaluator and the two new
brains. It does three things, purely:

1. :func:`build_context` assembles an :class:`OracleContext` from a genome, its
   evaluation report, and its frames. Every value is knowable at the signal's
   closed bar; the trade OUTCOME is deliberately excluded (that is the veto's
   label set, kept separate).
2. :func:`veto_features` assembles the veto's feature vector from the SAME context.
3. :func:`run_brain` scores a pool of candidate genomes (all survivors), fits the
   veto on their honest NET outcomes, and returns the AOS distribution, the veto
   gate, and the self-audit.

Build Mode: pure functions. No I/O, no services. The caller passes a universe of
already-sliced frames; this module never loads files.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace as _dc_replace

import numpy as np

from app.core import law
from app.pyramid import roster as roster_mod
from app.pyramid import outcome_corpus as corpus_mod
from app.pyramid.oracle import OracleContext, OracleVerdict, score as oracle_score
from app.pyramid.veto import (
    DEFAULT_VETO_THRESHOLD,
    VetoAudit,
    VetoFeatures,
    VetoModel,
)
from app.quant import evaluator as ev
from app.quant.genome import StrategyGenome

__all__ = [
    "BrainReport",
    "build_context",
    "veto_features",
    "run_brain",
]


def _last_finite(arr) -> float | None:
    a = np.asarray(arr, dtype="float64")
    finite = a[np.isfinite(a)]
    return float(finite[-1]) if finite.size else None


def _market_features(F, index: int = -1) -> dict:
    """Causal market features at execution row ``index`` (default: the last closed
    bar). Every series is truncated to ``index`` inclusive so no future bar is read.
    """
    out: dict = {}
    end = None if index == -1 else index + 1
    atr_pips = np.asarray(F.atr_pips, dtype="float64")
    if end is not None:
        atr_pips = atr_pips[:end]
    out["atr_pips"] = _last_finite(atr_pips)
    fast = _last_finite(np.asarray(F.structure_ema_fast)[:end] if end is not None else F.structure_ema_fast)
    slow = _last_finite(np.asarray(F.structure_ema_slow)[:end] if end is not None else F.structure_ema_slow)
    out["structure_ema_fast"] = fast
    out["structure_ema_slow"] = slow
    if fast is not None and slow not in (None, 0.0):
        out["structure_slope"] = float(np.tanh((fast - slow) / abs(slow)))
    # momentum: close vs a short lookback, normalized by range
    closes = np.asarray(F.exec["close"], dtype="float64")
    if end is not None:
        closes = closes[:end]
    if closes.size >= 6:
        look = closes[-6:]
        hi, lo = float(np.max(look)), float(np.min(look))
        if hi > lo:
            out["momentum_pct"] = float(np.tanh((closes[-1] - closes[-6]) / (hi - lo)))
    # atr expansion ratio vs its own recent mean
    atr = np.asarray(F.atr, dtype="float64")
    if end is not None:
        atr = atr[:end]
    finite = atr[np.isfinite(atr)]
    if finite.size >= 20:
        cur = float(finite[-1])
        mean = float(np.mean(finite[-20:]))
        if mean > 0:
            out["atr_ratio"] = cur / mean
    # regime percentile: rank of current ATR over the finite window
    if finite.size >= 20:
        window = finite[-200:]
        out["regime_percentile"] = float(np.mean(window <= finite[-1]))
    # range position on the last 50 exec bars
    if closes.size >= 50:
        win = closes[-50:]
        hi, lo = float(np.max(win)), float(np.min(win))
        out["range_pos"] = (closes[-1] - lo) / (hi - lo) if hi > lo else 0.5
    # last M15 body ratio (native base, up to ``index``)
    m = F.m15 if end is None else F.m15.iloc[:end]
    if len(m) >= 1:
        o = float(m["open"].iloc[-1]); h = float(m["high"].iloc[-1])
        l = float(m["low"].iloc[-1]); c = float(m["close"].iloc[-1])
        rng = h - l
        out["body_ratio"] = abs(c - o) / rng if rng > 0 else 0.0
    return out


def _aggregate_market_features(frames_by_pair: dict, index: int = -1) -> dict:
    """Mean of each causal market scalar across the universe's pairs (DEBT-016).

    Scalar keys are averaged over pairs that produced a finite value; a key with no
    reading anywhere is ``None``. The sign-like keys (``htf_agrees`` is handled
    separately) are averages of continuous features only.
    """
    per = [_market_features(F, index=index) for F in frames_by_pair.values() if F is not None]
    if not per:
        return {}
    keys = set().union(*(p.keys() for p in per))
    out: dict = {}
    for k in keys:
        vals = [p[k] for p in per if p.get(k) is not None]
        out[k] = (sum(vals) / len(vals)) if vals else None
    return out


def build_context(
    genome: StrategyGenome,
    report,
    frames_by_pair: dict,
    *,
    trust: float = 0.0,
    domain_trust: dict[str, float] | None = None,
    seated_domains: set[str] | None = None,
    covered_pairs: set[str] | None = None,
    rotation_step: int = 0,
    trades: int | None = None,
    min_trades: int = 30,
    index: int = -1,
    net_r_override: float | None = None,
    win_rate_override: float | None = None,
) -> OracleContext:
    """Assemble an :class:`OracleContext` for one genome from its honest report.

    ``index`` selects the execution row for the causally-truncated market snapshot
    (default -1 = end of frame). ``net_r_override``/``win_rate_override`` let the
    R27 per-trade school build a context at one trade's entry bar.
    """
    domain = roster_mod.domain_of(genome.family)
    funnel = dict(getattr(report, "funnel", {}) or {})
    raw = sum(v.get("long", 0) + v.get("short", 0) for v in [funnel.get("family_raw", {})])
    final = sum(v.get("long", 0) + v.get("short", 0) for v in [funnel.get("final", {})])

    # DEBT-016: aggregate the causal market snapshot across ALL pairs in the
    # universe instead of reading the first pair alone. Each scalar is the mean of
    # the finite per-pair values; a scalar with no pair reading stays None. With a
    # single pair this is exactly the old snapshot (backward compatible).
    market = _aggregate_market_features(frames_by_pair, index)
    pair = sorted(frames_by_pair)[0] if frames_by_pair else ""

    tr = trades if trades is not None else int(getattr(report.metrics, "trades", 0))
    net_r = (float(getattr(report.metrics, "net_r", 0.0))
             if net_r_override is None else float(net_r_override))
    win_rate = (float(getattr(report.metrics, "win_rate", 0.0))
                if win_rate_override is None else float(win_rate_override))
    _ = net_r  # kept for clarity: net_r is not a context feature (no label leak)
    dtrust = dict(domain_trust or {})
    seated = set(seated_domains or ())
    covered = set(covered_pairs or ())

    # domain and priest votes: the domain's mean trust mapped to [0,1]
    dv = 0.5 + 0.5 * (dtrust.get(domain, 0.0) / (1.0 + abs(dtrust.get(domain, 0.0))))
    return OracleContext(
        pair=pair, family=genome.family, domain=domain, is_long=True,
        structure_ema_fast=market.get("structure_ema_fast"),
        structure_ema_slow=market.get("structure_ema_slow"),
        structure_slope=market.get("structure_slope"),
        momentum_pct=market.get("momentum_pct"),
        atr_pips=market.get("atr_pips"),
        min_atr_pips=float(genome.min_atr_pips),
        atr_ratio=market.get("atr_ratio"),
        regime_percentile=market.get("regime_percentile"),
        session_id=int(genome.session_id),
        range_pos=market.get("range_pos"),
        body_ratio=market.get("body_ratio"),
        htf_agrees=(market.get("structure_ema_fast") is not None
                    and market.get("structure_ema_slow") is not None
                    and market["structure_ema_fast"] > market["structure_ema_slow"]),
        domain_vote=dv,
        priest_vote=0.5 + 0.5 * (dtrust.get(domain, 0.0) / (1.0 + abs(dtrust.get(domain, 0.0)))),
        family_density=float(min(1.0, tr / 200.0)),
        funnel_raw=int(raw),
        funnel_final=int(final),
        signal_rate=float(min(1.0, tr / 500.0)),
        warmup_ok=True,
        sl_atr_mult=float(genome.sl_atr_mult),
        atr_mult_min=float(law.VNSB_ATR_MULT_MIN),
        atr_mult_max=float(law.VNSB_ATR_MULT_MAX),
        target_rr=float(genome.target_rr),
        min_rr=float(law.MIN_TARGET_RR),
        spread_pips=None,
        max_spread_pips=float(genome.max_spread_pips),
        cost_r=None,
        risk=None,
        risk_pct=float(law.TITANIUM_FLOOR_PCT),
        titanium_floor_pct=float(law.TITANIUM_FLOOR_PCT),
        payoff=float(genome.target_rr),
        max_bars_hold=int(genome.max_bars_hold),
        parachute_armed=None,
        trust=float(trust),
        trust_spread=None,
        trades=int(tr),
        min_trades=int(min_trades),
        prize=float(win_rate),
        priest_seated=domain in seated if seated else None,
        pair_covered=pair in covered if covered else None,
        rotation_step=int(rotation_step),
    )


def veto_features(ctx: OracleContext, aos: float = 0.5) -> VetoFeatures:
    """The veto's feature vector, derived from the same Oracle context (no extras)."""
    agree = 0.0
    if ctx.domain_vote is not None and ctx.priest_vote is not None:
        agree = 1.0 if (ctx.domain_vote >= 0.5) == (ctx.priest_vote >= 0.5) else 0.0
    funnel_stage = 0.5
    if ctx.funnel_raw and ctx.funnel_final is not None and ctx.funnel_raw > 0:
        funnel_stage = min(1.0, ctx.funnel_final / ctx.funnel_raw)
    session = 0.5 if ctx.session_id is None else min(1.0, int(ctx.session_id) / 3.0)
    return VetoFeatures(
        aos=aos,
        domain_agreement=agree,
        session=session,
        regime_percentile=ctx.regime_percentile if ctx.regime_percentile is not None else 0.5,
        trust=(
            0.5 + 0.5 * (ctx.trust / (1.0 + abs(ctx.trust)))
            if ctx.trust is not None else 0.5
        ),
        funnel_stage=funnel_stage,
        density_class=ctx.family_density if ctx.family_density is not None else 0.5,
        spread_state=0.5,
    )


@dataclass
class BrainReport:
    """The brain layer's output: AOS distribution, contexts, veto audit, calibration."""

    scored: int
    aos_values: list[float]
    aos_mean: float
    aos_min: float
    aos_max: float
    missing_total: int
    verdicts: list[dict]
    veto: dict
    veto_audit: dict
    calibration: dict = field(default_factory=dict)
    curriculum: dict = field(default_factory=dict)
    veto_school: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scored": self.scored,
            "aos_mean": self.aos_mean,
            "aos_min": self.aos_min,
            "aos_max": self.aos_max,
            "missing_total": self.missing_total,
            "verdicts": self.verdicts,
            "veto": self.veto,
            "veto_audit": self.veto_audit,
            "calibration": self.calibration,
            "curriculum": self.curriculum,
            "veto_school": self.veto_school,
            "uncalibrated": bool(self.calibration.get("uncalibrated", True)),
        }


def _per_trade_school_rows(
    contexts, reports, *, domain_trust, seated_domains, covered_pairs,
    rotation_step, universe,
) -> list[tuple[VetoFeatures, int]]:
    """R27 tier-2 school: one labelled row per HONEST per-trade NET-R outcome.

    For every trade the engine booked on a real genome, build a causally-truncated
    oracle context at that trade's ENTRY bar (market features up to and including
    ``entry_index``) and label it by the trade's stamped NET R. This gives the veto
    a school of SIGNALS that actually contains losers — the DEBT-014 correction.
    """
    rows: list[tuple[VetoFeatures, int]] = []
    for g, _ctx, aos, _nw in contexts:
        report = reports.get(g.signature())
        if report is None:
            continue
        for pair, prep in getattr(report, "per_pair", {}).items():
            F = universe.get(pair)
            if F is None or not getattr(prep, "trades", None):
                continue
            for t in prep.trades:
                net = t.net_r if t.net_r is not None else t.r_multiple
                ctx = build_context(
                    g, report, {pair: F},
                    domain_trust=domain_trust, seated_domains=seated_domains,
                    covered_pairs=covered_pairs, rotation_step=rotation_step,
                    index=int(t.entry_index),
                )
                vf = veto_features(ctx, aos=aos)
                rows.append((vf, 1 if float(net) > 0.0 else 0))
    return rows


def run_brain(
    genomes: list[StrategyGenome],
    universe: dict,
    *,
    eval_cfg=None,
    trust_scores: dict[str, float] | None = None,
    domain_trust: dict[str, float] | None = None,
    seated_domains: set[str] | None = None,
    covered_pairs: set[str] | None = None,
    rotation_step: int = 0,
    min_trades: int = 30,
    veto_threshold: float = DEFAULT_VETO_THRESHOLD,
    corpus_paths=None,
    ram_corpus_paths=None,
) -> "tuple[BrainReport, VetoModel]":
    """Score every genome through the Oracle, then fit + apply the veto.

    Each genome is re-evaluated on the (already sliced) universe to obtain an
    honest report (R17). The Oracle scores its context.

    R27 (veto school): when ``corpus_paths`` is given (the historical outcome
    files under ``data/history``), the veto trains on ALL historical outcomes —
    winners AND losers — instead of the survivor pool alone. This is the DEBT-014
    correction. Without it the veto trains on the current pool only (legacy
    behavior, kept for callers that pass an explicit pool).

    R28 (calibration): the AOS reliability table is always computed over the
    training rows and carried in the report; ``uncalibrated`` is True until every
    bin is trustworthy. While uncalibrated, god-tier AOS is quarantined.
    """
    trust_scores = dict(trust_scores or {})
    eval_cfg = eval_cfg or ev.EvaluationConfig()
    verdicts: list[dict] = []
    contexts: list[tuple[StrategyGenome, OracleContext, float, bool]] = []
    reports: dict[str, object] = {}
    aos_values: list[float] = []
    missing_total = 0

    for g in genomes:
        report = ev.evaluate(g, universe, eval_cfg)
        ctx = build_context(
            g, report, universe,
            trust=float(trust_scores.get(g.signature(), 0.0)),
            domain_trust=domain_trust,
            seated_domains=seated_domains,
            covered_pairs=covered_pairs,
            rotation_step=rotation_step,
            min_trades=min_trades,
        )
        verd: OracleVerdict = oracle_score(
            ctx, domain_trust=domain_trust, seated_domains=seated_domains
        )
        net_win = float(report.metrics.net_r) > 0.0
        aos_values.append(verd.aos)
        missing_total += len(verd.acolyte_missing)
        verdicts.append({
            "signature": g.signature(), "family": g.family, "domain": ctx.domain,
            "aos": verd.aos, "net_r": float(report.metrics.net_r),
            "trades": int(report.metrics.trades),
            "acolyte_missing": list(verd.acolyte_missing),
        })
        contexts.append((g, ctx, verd.aos, net_win))
        reports[g.signature()] = report

    # Fit the veto on a three-tier school (R27). The veto is a yes/no gate over
    # SIGNALS, so its honest school is labelled SIGNALS — not genomes.
    #   Tier 1  corpus:   historical genome-level outcomes (winners AND losers).
    #   Tier 2  per-trade: the honest judge's own per-trade NET-R labels, each row
    #           a causally-truncated context at that trade's entry bar. This is the
    #           real R27 school: the veto sees signals, and losers among them.
    #   Tier 3  pool:     the legacy survivor pool (kept as a last resort).
    model = VetoModel(threshold=veto_threshold)
    fit_rows: list[tuple[VetoFeatures, int]] = []
    curriculum: dict = {}
    if corpus_paths:
        corpus = corpus_mod.load_corpus(corpus_paths)
        # R37 — clean-only training: the veto learns on the CLEAN era; RAMS-era
        # rows are evidence (with a feature-drift report), never training rows.
        ram_corpus = (corpus_mod.load_corpus(ram_corpus_paths)
                      if ram_corpus_paths else [])
        ram_corpus = [_dc_replace(r, era=corpus_mod.RAM_ERA)
                      for r in ram_corpus]
        clean_corpus = corpus_mod.rows_with_era(corpus, corpus_mod.CLEAN_ERA)
        # Legacy corpus files carry no era stamp -> treat them as CLEAN (era 0).
        if not clean_corpus:
            clean_corpus = list(corpus)
        school = {"source": "corpus",
                  **corpus_mod.summarize(clean_corpus).to_dict()}
        curriculum = {
            "eras": corpus_mod.era_counts(clean_corpus + ram_corpus),
            "clean_rows": len(clean_corpus),
            "rams_rows": len(ram_corpus),
            "trained_on": "clean",
            "drift": (corpus_mod.feature_drift(clean_corpus, ram_corpus)
                      if ram_corpus else {}),
        }
        corpus_rows = [(r.features, r.label) for r in clean_corpus]
        calibration = corpus_mod.calibration_table(clean_corpus)
    else:
        corpus_rows = []
        school = {"source": "pool"}
        calibration = {}

    # R27 tier-2 school (per-trade NET-R labels) is built only in the corpus (R27)
    # path. Without ``corpus_paths`` the legacy pool-only behavior is preserved
    # exactly (Phase 3.2 callers keep fitting one row per genome).
    per_trade_rows = (
        _per_trade_school_rows(
            contexts, reports,
            domain_trust=domain_trust, seated_domains=seated_domains,
            covered_pairs=covered_pairs, rotation_step=rotation_step, universe=universe,
        )
        if corpus_paths else []
    )
    if per_trade_rows:
        fit_rows = corpus_rows + per_trade_rows
        school["per_trade_rows"] = len(per_trade_rows)
        school["per_trade_negatives"] = sum(1 for _f, y in per_trade_rows if y == 0)
    elif corpus_rows:
        fit_rows = corpus_rows
    else:
        for _g, ctx, aos, net_win in contexts:
            fit_rows.append((veto_features(ctx, aos=aos), 1 if net_win else 0))
        school["source"] = "pool"
    school["feature_rows"] = len(fit_rows)
    school["negatives_seen"] = sum(1 for _f, y in fit_rows if y == 0)
    school["positives_seen"] = sum(1 for _f, y in fit_rows if y == 1)
    model.fit(fit_rows)

    # R28: attach the structural quarantine decision to every verdict. A god-tier
    # AOS while uncalibrated is REPORTED, never actionable.
    god_tier_quarantined = 0
    for row in verdicts:
        q = corpus_mod.quarantine_decision(row["aos"], calibration)
        row["quarantine"] = q
        if q["quarantined"]:
            god_tier_quarantined += 1
    school["god_tier_quarantined"] = god_tier_quarantined

    audit = VetoAudit(threshold=veto_threshold)
    by_sig = {row["signature"]: row for row in verdicts}
    for g, ctx, aos, net_win in contexts:
        f = veto_features(ctx, aos=aos)
        vetoed = model.vetoes(f)
        audit.observe(vetoed=vetoed, net_win=net_win,
                      family=g.family, domain=ctx.domain)
        row = by_sig.get(g.signature())
        if row is not None:
            row["vetoed"] = vetoed
            row["p_net_win"] = model.probability(f)

    aos_values_sorted = sorted(aos_values)
    report_obj = BrainReport(
        scored=len(aos_values),
        aos_values=aos_values_sorted,
        aos_mean=(sum(aos_values) / len(aos_values)) if aos_values else 0.0,
        aos_min=(aos_values_sorted[0] if aos_values_sorted else 0.0),
        aos_max=(aos_values_sorted[-1] if aos_values_sorted else 0.0),
        missing_total=missing_total,
        verdicts=verdicts,
        veto=model.to_dict(),
        veto_audit=audit.to_dict(),
        calibration=calibration,
        curriculum=curriculum,
        veto_school=school,
    )
    return report_obj, model
