"""THE 45 ACOLYTES — the brute-force layer of the Oracle (Phase 3.2).

Each acolyte is a DETERMINISTIC scorer over ONE signal feature view of a
candidate's :class:`~app.pyramid.oracle.context.OracleContext`. An acolyte is
cheap, PURE, and individually dumb; its power is the vote. The 45 views are
grouped so the four domains get genuine representation:

    MARKET (12)  price geometry, trend, momentum, volatility, regime, sessions
    SIGNAL (12)  domain/priest vote, funnel health, confluence, divergence
    RISK   (8)   stop band, reward:risk, spread, cost burden, law compliance
    CONTEXT (8)  trust, sample size, family/domain identity, R26 rotation
    CHAIN  (5)   higher-order "does the whole vote cohere" views

Every view is ``(ctx) -> float in [0, 1] | None``. A view returns ``None`` ONLY
when a feature it genuinely REQUIRES is absent (e.g. the volatility view needs
ATR): the combiner drops missing views and reports them — never a fabricated
0.5 for a required-but-missing feature. Optional context returns neutral 0.5.

CAUSAL. Views read only values knowable at the signal's closed bar; the context
carries no future bars and no trade outcome (that belongs to the veto's labels).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.pyramid.oracle.context import OracleContext

__all__ = [
    "AcolyteView",
    "ACOLYTE_VIEWS",
    "ACOLYTE_COUNT",
    "GROUPS",
    "score_acolytes",
    "acolyte_names",
    "acolytes_by_group",
]

# 45 is law (Phase 3.2). Not 44, not 46.
ACOLYTE_COUNT: int = 45
GROUPS: tuple[str, ...] = ("market", "signal", "risk", "context", "chain")


@dataclass(frozen=True)
class AcolyteView:
    """One feature view: a name, its group, and a pure ``ctx -> [0,1]|None`` scorer."""

    name: str
    group: str
    fn: Callable[[OracleContext], Optional[float]]

    def score(self, ctx: OracleContext) -> Optional[float]:
        value = self.fn(ctx)
        if value is None:
            return None
        v = float(value)
        if v != v:  # NaN is not a score; treat as missing, never a neutral 0.5
            return None
        return min(1.0, max(0.0, v))


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, float(x)))


# ---------------------------------------------------------------------------
# MARKET views (12)
# ---------------------------------------------------------------------------
def _trend_agreement(ctx):
    if ctx.structure_ema_fast is None or ctx.structure_ema_slow is None:
        return 0.5
    agree = (ctx.structure_ema_fast > ctx.structure_ema_slow) == ctx.is_long
    return 0.8 if agree else 0.25

def _momentum_agreement(ctx):
    if ctx.momentum_pct is None:
        return 0.5
    aligned = ctx.momentum_pct if ctx.is_long else -ctx.momentum_pct
    return _clip01(0.5 + 0.5 * aligned)

def _volatility_state(ctx):
    """REQUIRES ATR — absent ATR is a MISSING view, never a neutral score."""
    if ctx.atr_pips is None:
        return None
    floor = ctx.min_atr_pips if ctx.min_atr_pips is not None else 1.0
    if floor <= 0:
        return _clip01(ctx.atr_pips / (ctx.atr_pips + 1.0))
    return _clip01(0.5 * (ctx.atr_pips / floor))

def _regime_percentile(ctx):
    return 0.5 if ctx.regime_percentile is None else _clip01(ctx.regime_percentile)

def _session_position(ctx):
    if ctx.session_id is None:
        return 0.5
    return {0: 0.45, 1: 0.75, 2: 0.70, 3: 0.40}.get(int(ctx.session_id), 0.5)

def _range_position(ctx):
    if ctx.range_pos is None:
        return 0.5
    p = _clip01(ctx.range_pos)
    return _clip01(1.0 - p if ctx.is_long else p)

def _body_strength(ctx):
    return 0.5 if ctx.body_ratio is None else _clip01(ctx.body_ratio)

def _atr_expansion(ctx):
    return 0.5 if ctx.atr_ratio is None else _clip01(ctx.atr_ratio / 2.0)

def _distance_from_extreme(ctx):
    return 0.5 if ctx.excursion_pct is None else _clip01(ctx.excursion_pct)

def _trend_slope(ctx):
    if ctx.structure_slope is None:
        return 0.5
    aligned = ctx.structure_slope if ctx.is_long else -ctx.structure_slope
    return _clip01(0.5 + 0.5 * aligned)

def _htf_alignment(ctx):
    return 0.5 if ctx.htf_agrees is None else (0.85 if ctx.htf_agrees else 0.20)


# ---------------------------------------------------------------------------
# SIGNAL views (12)
# ---------------------------------------------------------------------------
def _domain_vote_strength(ctx):
    return 0.5 if ctx.domain_vote is None else _clip01(ctx.domain_vote)

def _priest_vote_strength(ctx):
    return 0.5 if ctx.priest_vote is None else _clip01(ctx.priest_vote)

def _family_density(ctx):
    return 0.5 if ctx.family_density is None else _clip01(ctx.family_density)

def _confluence_count(ctx):
    return 0.5 if ctx.confluence is None else _clip01(ctx.confluence / 3.0)

def _funnel_health(ctx):
    if ctx.funnel_raw is None or ctx.funnel_final is None or ctx.funnel_raw <= 0:
        return 0.5
    return _clip01(ctx.funnel_final / ctx.funnel_raw)

def _divergence_present(ctx):
    return 0.5 if ctx.divergence is None else (0.70 if ctx.divergence else 0.35)

def _signal_recency(ctx):
    if ctx.bars_since_signal is None:
        return 0.5
    return _clip01(1.0 / (1.0 + max(0, int(ctx.bars_since_signal))))

def _signal_density(ctx):
    return 0.5 if ctx.signal_rate is None else _clip01(ctx.signal_rate)

def _multi_family_agreement(ctx):
    return 0.5 if ctx.family_agreement is None else _clip01(ctx.family_agreement)

def _side_balance(ctx):
    if ctx.long_share is None:
        return 0.5
    share = _clip01(ctx.long_share)
    return _clip01(share if ctx.is_long else 1.0 - share)

def _warmup_state(ctx):
    return 0.5 if ctx.warmup_ok is None else (0.90 if ctx.warmup_ok else 0.10)

def _activation_state(ctx):
    return 0.5 if ctx.activation_state is None else _clip01(ctx.activation_state)


# ---------------------------------------------------------------------------
# RISK views (8)
# ---------------------------------------------------------------------------
def _stop_band_compliance(ctx):
    if ctx.sl_atr_mult is None or ctx.atr_mult_min is None or ctx.atr_mult_max is None:
        return None
    inside = ctx.atr_mult_min <= ctx.sl_atr_mult <= ctx.atr_mult_max
    return 0.90 if inside else 0.15

def _rr_adequacy(ctx):
    if ctx.target_rr is None or ctx.min_rr is None or ctx.min_rr <= 0:
        return None
    return _clip01(ctx.target_rr / (2.0 * ctx.min_rr))

def _spread_state(ctx):
    if ctx.spread_pips is None or not ctx.max_spread_pips:
        return 0.5
    return _clip01(1.0 - ctx.spread_pips / ctx.max_spread_pips)

def _cost_burden(ctx):
    if ctx.cost_r is None or not ctx.risk or ctx.risk <= 0:
        return 0.5
    return _clip01(1.0 - abs(ctx.cost_r) / ctx.risk)

def _titanium_floor(ctx):
    if ctx.risk_pct is None or not ctx.titanium_floor_pct or ctx.titanium_floor_pct <= 0:
        return 0.5
    return _clip01((ctx.risk_pct / ctx.titanium_floor_pct) / 2.0)

def _payoff_geometry(ctx):
    return 0.5 if ctx.payoff is None else _clip01(ctx.payoff / 5.0)

def _hold_time_sanity(ctx):
    if ctx.max_bars_hold is None:
        return 0.5
    b = int(ctx.max_bars_hold)
    if b < 4:
        return 0.30
    if b > 400:
        return 0.40
    return 0.70

def _parachute_armed(ctx):
    return 0.5 if ctx.parachute_armed is None else (0.80 if ctx.parachute_armed else 0.45)


# ---------------------------------------------------------------------------
# CONTEXT views (8)
# ---------------------------------------------------------------------------
def _trust_level(ctx):
    if ctx.trust is None:
        return 0.5
    return _clip01(0.5 + 0.5 * (ctx.trust / (1.0 + abs(ctx.trust))))

def _trust_spread(ctx):
    return 0.5 if ctx.trust_spread is None else _clip01(1.0 - ctx.trust_spread)

def _sample_adequacy(ctx):
    if ctx.trades is None or not ctx.min_trades or ctx.min_trades <= 0:
        return 0.5
    return _clip01(ctx.trades / (2.0 * ctx.min_trades))

def _prize_match(ctx):
    return 0.5 if ctx.prize is None else _clip01(ctx.prize)

def _domain_match(ctx):
    return 0.5 if ctx.priest_seated is None else (0.80 if ctx.priest_seated else 0.30)

def _general_coverage(ctx):
    return 0.5 if ctx.pair_covered is None else (0.80 if ctx.pair_covered else 0.20)

def _rotation_freshness(ctx):
    if ctx.rotation_step is None:
        return 0.5
    return _clip01(0.5 + 0.4 * ((int(ctx.rotation_step) % 15) / 15.0))

def _family_breadth(ctx):
    return 0.5 if ctx.family_size is None else _clip01(ctx.family_size / 20.0)


# ---------------------------------------------------------------------------
# CHAIN views (5)
# ---------------------------------------------------------------------------
def _raw_final_coherence(ctx):
    if ctx.funnel_raw is None or ctx.funnel_final is None or ctx.funnel_raw <= 0:
        return 0.5
    ratio = ctx.funnel_final / ctx.funnel_raw
    return _clip01(1.0 - abs(ratio - 0.30) / 0.70)

def _domain_priest_align(ctx):
    if ctx.domain_vote is None or ctx.priest_vote is None:
        return 0.5
    agree = (ctx.domain_vote >= 0.5) == (ctx.priest_vote >= 0.5)
    return 0.80 if agree else 0.30

def _geometry_signal_align(ctx):
    if ctx.structure_ema_fast is None or ctx.structure_ema_slow is None:
        return 0.5
    agree = (ctx.structure_ema_fast > ctx.structure_ema_slow) == ctx.is_long
    return 0.75 if agree else 0.35

def _risk_reward_consistency(ctx):
    if ctx.target_rr is None or not ctx.payoff or ctx.payoff <= 0:
        return 0.5
    return _clip01(min(ctx.target_rr, ctx.payoff) / max(ctx.target_rr, ctx.payoff))

def _vote_coherence(ctx):
    vals = [v for v in (ctx.domain_vote, ctx.priest_vote) if v is not None]
    return 0.5 if not vals else _clip01(sum(vals) / len(vals))


def _build_views() -> tuple[AcolyteView, ...]:
    views = (
        AcolyteView("trend_agreement", "market", _trend_agreement),
        AcolyteView("momentum_agreement", "market", _momentum_agreement),
        AcolyteView("volatility_state", "market", _volatility_state),
        AcolyteView("regime_percentile", "market", _regime_percentile),
        AcolyteView("session_position", "market", _session_position),
        AcolyteView("range_position", "market", _range_position),
        AcolyteView("body_strength", "market", _body_strength),
        AcolyteView("atr_expansion", "market", _atr_expansion),
        AcolyteView("distance_from_extreme", "market", _distance_from_extreme),
        AcolyteView("trend_slope", "market", _trend_slope),
        AcolyteView("htf_alignment", "market", _htf_alignment),
        AcolyteView("bar_recency", "market", _signal_recency),
        AcolyteView("domain_vote_strength", "signal", _domain_vote_strength),
        AcolyteView("priest_vote_strength", "signal", _priest_vote_strength),
        AcolyteView("family_density", "signal", _family_density),
        AcolyteView("confluence_count", "signal", _confluence_count),
        AcolyteView("funnel_health", "signal", _funnel_health),
        AcolyteView("divergence_present", "signal", _divergence_present),
        AcolyteView("signal_recency", "signal", _signal_recency),
        AcolyteView("signal_density", "signal", _signal_density),
        AcolyteView("multi_family_agreement", "signal", _multi_family_agreement),
        AcolyteView("side_balance", "signal", _side_balance),
        AcolyteView("warmup_state", "signal", _warmup_state),
        AcolyteView("activation_state", "signal", _activation_state),
        AcolyteView("stop_band_compliance", "risk", _stop_band_compliance),
        AcolyteView("rr_adequacy", "risk", _rr_adequacy),
        AcolyteView("spread_state", "risk", _spread_state),
        AcolyteView("cost_burden", "risk", _cost_burden),
        AcolyteView("titanium_floor", "risk", _titanium_floor),
        AcolyteView("payoff_geometry", "risk", _payoff_geometry),
        AcolyteView("hold_time_sanity", "risk", _hold_time_sanity),
        AcolyteView("parachute_armed", "risk", _parachute_armed),
        AcolyteView("trust_level", "context", _trust_level),
        AcolyteView("trust_spread", "context", _trust_spread),
        AcolyteView("sample_adequacy", "context", _sample_adequacy),
        AcolyteView("prize_match", "context", _prize_match),
        AcolyteView("domain_match", "context", _domain_match),
        AcolyteView("general_coverage", "context", _general_coverage),
        AcolyteView("rotation_freshness", "context", _rotation_freshness),
        AcolyteView("family_breadth", "context", _family_breadth),
        AcolyteView("raw_final_coherence", "chain", _raw_final_coherence),
        AcolyteView("domain_priest_align", "chain", _domain_priest_align),
        AcolyteView("geometry_signal_align", "chain", _geometry_signal_align),
        AcolyteView("risk_reward_consistency", "chain", _risk_reward_consistency),
        AcolyteView("vote_coherence", "chain", _vote_coherence),
    )
    if len(views) != ACOLYTE_COUNT:
        raise ValueError(
            f"the Oracle must field exactly {ACOLYTE_COUNT} acolytes, got "
            f"{len(views)} (fail-closed)"
        )
    names = [v.name for v in views]
    if len(set(names)) != len(names):
        raise ValueError("acolyte view names must be unique (fail-closed)")
    return views


ACOLYTE_VIEWS: tuple[AcolyteView, ...] = _build_views()


def acolyte_names() -> tuple[str, ...]:
    return tuple(v.name for v in ACOLYTE_VIEWS)


def acolytes_by_group(group: str) -> tuple[AcolyteView, ...]:
    return tuple(v for v in ACOLYTE_VIEWS if v.group == group)


def score_acolytes(ctx: OracleContext) -> dict[str, Optional[float]]:
    """Score every acolyte for ``ctx``; ``None`` marks a MISSING (dropped) view."""
    return {v.name: v.score(ctx) for v in ACOLYTE_VIEWS}
