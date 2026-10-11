"""THE GENOME — the DNA a strategy is bred from.

This module holds the DNA *dataclass only*. Indicator math lives in
``indicators``, structure in ``levels``; signal logic arrives in Phase 2.2. No
3,000-line monolith, no signal code here.

THE LAW INSIDE THE BOUNDS. ``target_rr`` is a mutable gene, but its mutation
space is ``[law.MIN_TARGET_RR, 8.0]``. The genetic algorithm physically cannot
breed a target below the 1:2.5 floor — the Constitution is encoded in the bounds
table, not merely enforced after the fact. Every mutable numeric gene appears in
:data:`GENE_BOUNDS` exactly once.

FAMILIES is the closed set of signal families. It includes ``"ensemble"`` and
deliberately excludes machine-learning families (``ml_*``); learned models are a
later phase and must not be smuggled in as a "family".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, replace
from typing import NamedTuple

from app.core import law

# ---------------------------------------------------------------------------
# Signal families — closed, unique.
# ---------------------------------------------------------------------------
FAMILIES: tuple[str, ...] = (
    "trend_pullback",
    "mean_reversion",
    "breakout",
    "macd_momentum",
    "keltner_expansion",
    "rsi_reversal",
    "wyckoff_spring",
    "order_block",
    "volume_delta",
    "ob_atr_rank",
    "cointegration_statarb",
    "liq_sweep_ote",
    "choch_fvg",
    "bos_premium_discount",
    "fvg_momentum",
    "silver_bullet",
    "asian_range_sweep",
    "eqhl_tap",
    "judas_swing",
    "ict_2022_model",
    "dealing_range",
    "turtle_soup",
    "bb_keltner_squeeze",
    "rsi_divergence",
    "vwap_reversion",
    "keltner_pullback",
    "zscore_reversion",
    "hurst_regime",
    "atr_squeeze_breakout",
    "london_orb",
    "ny_orb",
    "vcp_breakout",
    "momentum_ignition",
    "pin_bar",
    "engulfing_liquidity",
    "hikkake",
    "fib_confluence",
    "harmonic_proxy",
    "mtf_divergence",
    "volume_profile_v",
    "fib_ote_confluence",
    "hurst_reversion_filtered",
    "time_based_reversal",
    "ensemble",
)

# Families that reason about relative value rather than a single series.
RELATIVE_VALUE_FAMILIES: frozenset[str] = frozenset({"cointegration_statarb"})

# Families whose members are themselves strategies (lineage composes).
ENSEMBLE_FAMILY = "ensemble"

# R15 — SEALED ENSEMBLE FLOOR. An ensemble is a quorum over at least this many
# concrete members; the 2-member degenerate (where any quorum short of unanimity
# is ambiguous) is extinct. One declaration, consumed by the breeding draw,
# the mutation shrink floor, and the seed builder. Quorum is clamped to [2, n].
ENSEMBLE_MIN_MEMBERS = 3


# ---------------------------------------------------------------------------
# Gene bounds. (name, low, high, is_int) for every mutable numeric gene.
# ---------------------------------------------------------------------------
class GeneBound(NamedTuple):
    name: str
    low: float
    high: float
    is_int: bool


GENE_BOUNDS: tuple[GeneBound, ...] = (
    # trend / momentum
    GeneBound("ema_fast", 3, 50, True),
    GeneBound("ema_slow", 10, 200, True),
    GeneBound("adx_period", 7, 30, True),
    GeneBound("adx_min", 0.0, 50.0, False),
    GeneBound("macd_fast", 5, 20, True),
    GeneBound("macd_slow", 15, 60, True),
    GeneBound("macd_signal", 3, 20, True),
    GeneBound("momentum_lookback", 2, 50, True),
    GeneBound("pullback_rsi", 5.0, 80.0, False),  # long pullback RSI ceiling
    # oscillators / bands
    GeneBound("rsi_period", 5, 30, True),
    GeneBound("rsi_oversold", 0.0, 50.0, False),
    GeneBound("rsi_overbought", 50.0, 100.0, False),
    GeneBound("bb_period", 10, 50, True),
    GeneBound("bb_std", 1.0, 4.0, False),
    GeneBound("keltner_period", 10, 50, True),
    GeneBound("keltner_mult", 1.0, 4.0, False),
    GeneBound("atr_period", 7, 30, True),
    GeneBound("hurst_window", 50, 300, True),
    GeneBound("zscore_period", 5, 60, True),
    # risk geometry
    GeneBound("sl_lookback", 5, 100, True),
    GeneBound("sl_buffer_pips", 0.0, 50.0, False),
    # The stop-distance multiplier, in ATR(14) M15 units. Its mutation space IS
    # the VNSB band (law.VNSB_ATR_MULT_MIN..MAX), so the GA cannot breed a stop
    # the Constitution would reject for being off-band — THE LAW, inside the bounds.
    GeneBound("sl_atr_mult", law.VNSB_ATR_MULT_MIN, law.VNSB_ATR_MULT_MAX, False),
    GeneBound("target_lookback", 5, 100, True),
    GeneBound("target_rr", law.MIN_TARGET_RR, 8.0, False),  # THE LAW, inside the bounds
    GeneBound("trail_start_rr", 0.0, 5.0, False),
    GeneBound("trail_atr_mult", 0.1, 5.0, False),
    GeneBound("max_bars_hold", 4, 500, True),
    GeneBound("cooldown_bars", 0, 100, True),
    # regime / confluence / alignment (Phase 2.2a gate stack)
    # R84 (Phase 7h) — the ATR floor was calibrated DOWN from 50.0. On the M15 tapes
    # a normal bar is ~2-11 pips of ATR (p90 <= ~18 pips across the majors); a floor
    # drawn uniformly up to 50 pips rejects ~90% of random genomes as "no trades".
    # 20 pips keeps the gate meaningful (it still rejects genuinely quiet bars) while
    # admitting the tradeable range. The old value remains the honest counterfactual.
    GeneBound("min_atr_pips", 0.0, 20.0, False),
    GeneBound("max_spread_pips", 0.1, 10.0, False),
    GeneBound("session_id", 0, 3, True),
    GeneBound("trend_align", 0, 2, True),        # 0=off, 1=with D1 trend, 2=against
    GeneBound("require_h1_align", 0, 1, True),   # 1=H1 must agree with H4 structure
    GeneBound("min_confluence", 0, 3, True),     # independent confirmations required
    # institutional seeds
    GeneBound("seed_win_rate", 0.0, 1.0, False),
    GeneBound("seed_payoff", 0.0, 10.0, False),
    GeneBound("seed_sample", 0, 100000, True),
    # ensemble
    GeneBound("ensemble_size", 2, 20, True),
    GeneBound("ensemble_window", 50, 2000, True),
    GeneBound("ensemble_min_votes", 1, 20, True),
    # regime activation
    GeneBound("regime_hurst_min", 0.0, 1.0, False),
    GeneBound("regime_adx_min", 0.0, 50.0, False),
    GeneBound("regime_atr_rank_min", 0.0, 1.0, False),
    # SMC / ICT structure (Phase 2.2b)
    GeneBound("smc_pivot_strength", 1, 5, True),
    GeneBound("smc_range_lookback", 5, 200, True),
    GeneBound("smc_pool_window", 5, 200, True),
    GeneBound("smc_pool_tol_pips", 0.5, 20.0, False),
    GeneBound("smc_fvg_lookback", 5, 200, True),
    GeneBound("smc_displacement_atr", 0.5, 5.0, False),
    GeneBound("smc_spring_depth_atr", 0.1, 3.0, False),
    GeneBound("smc_sweep_depth_atr", 0.1, 3.0, False),
    GeneBound("smc_ote_low", 0.5, 0.9, False),
    GeneBound("smc_ote_high", 0.7, 1.0, False),
    GeneBound("smc_ob_lookback", 3, 100, True),
    GeneBound("smc_momentum_atr", 0.5, 5.0, False),
    GeneBound("smc_atr_rank_min", 0.0, 1.0, False),
    GeneBound("smc_turtle_lookback", 5, 200, True),
    # statistical arbitrage (Phase 2.2b)
    GeneBound("statarb_window", 20, 1000, True),
    GeneBound("statarb_z", 0.5, 5.0, False),
    # volatility / statistical families (Phase 2.2c)
    GeneBound("squeeze_rank", 0.0, 1.0, False),     # ATR/vol contraction percentile
    GeneBound("expansion_atr", 0.5, 5.0, False),    # body > expansion_atr * ATR
    GeneBound("vcp_lookback", 20, 200, True),
    GeneBound("vcp_contractions", 2, 5, True),
    GeneBound("ignition_vol_mult", 1.0, 10.0, False),
    GeneBound("pullback_frac", 0.2, 0.8, False),
    GeneBound("orb_minutes", 15, 180, True),
    GeneBound("vwap_std_mult", 0.5, 5.0, False),
    GeneBound("zscore_entry", 0.5, 5.0, False),
    GeneBound("hurst_trend_min", 0.5, 1.0, False),   # HIGH Hurst percentile
    GeneBound("hurst_revert_max", 0.0, 0.5, False),  # LOW Hurst percentile
    GeneBound("volume_spike_mult", 1.0, 10.0, False),
    # pattern / confluence families (Phase 2.2c)
    GeneBound("pin_ratio", 1.0, 6.0, False),         # wick >= pin_ratio * body
    GeneBound("fib_low", 0.2, 0.7, False),
    GeneBound("fib_high", 0.5, 0.95, False),
    GeneBound("harmonic_tolerance", 0.01, 0.2, False),
    GeneBound("mtf_window", 4, 100, True),
    GeneBound("london_hours", 1, 6, True),
    GeneBound("hikkake_lookback", 2, 50, True),
    # The structural-level source the strategy derives stop/target geometry from.
    # Interval id into evaluator.LEVEL_SOURCES (clamped to the registry size).
    GeneBound("level_source_id", 0, 4, True),
)

GENE_BOUNDS_BY_NAME: dict[str, GeneBound] = {b.name: b for b in GENE_BOUNDS}


def clamp_gene(name: str, value) -> float:
    """Clamp ``value`` into the sealed bounds for ``name`` (int if the bound is)."""
    bound = GENE_BOUNDS_BY_NAME[name]
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = bound.low
    if number != number:  # NaN -> reject to the floor, never a magic pass-through
        number = bound.low
    number = min(max(number, bound.low), bound.high)
    if bound.is_int:
        return int(round(number))
    return number


# ---------------------------------------------------------------------------
# The genome.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StrategyGenome:
    """The DNA of one strategy. Groups follow the breeding axes."""

    family: str = "trend_pullback"

    # trend / momentum
    ema_fast: int = 9
    ema_slow: int = 21
    adx_period: int = 14
    adx_min: float = 18.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    momentum_lookback: int = 10
    pullback_rsi: float = 55.0

    # oscillators / bands
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    bb_period: int = 20
    bb_std: float = 2.0
    keltner_period: int = 20
    keltner_mult: float = 2.0
    atr_period: int = 14
    hurst_window: int = 100
    zscore_period: int = 20

    # risk geometry
    sl_lookback: int = 20
    sl_buffer_pips: float = 2.0
    sl_atr_mult: float = 1.2   # stop distance in ATR multiples (VNSB band)
    target_lookback: int = 20
    target_rr: float = 3.0
    trail_start_rr: float = 1.0
    trail_atr_mult: float = 1.0
    max_bars_hold: int = 96
    cooldown_bars: int = 4
    level_source_id: int = 0    # interval id into evaluator.LEVEL_SOURCES

    # regime / confluence filters
    min_atr_pips: float = 1.0
    max_spread_pips: float = 3.0
    session_id: int = 0
    trend_align: int = 1        # require the D1 trend to agree with the trade
    require_h1_align: int = 1   # require H1 to agree with the H4 structure
    min_confluence: int = 1     # independent confirmations required

    # institutional seed genes
    seed_win_rate: float = 0.5
    seed_payoff: float = 2.5
    seed_sample: int = 100

    # ensemble genes
    ensemble_size: int = 5
    ensemble_window: int = 500
    ensemble_min_votes: int = 3
    ensemble_members: tuple[dict, ...] = ()
    # R58 (Phase 7c) — member provenance: "elite" (drawn from the previous
    # generation's top-ranked singles) or "random" (exploration share). This is
    # METADATA for the survival table (elite | random), not a signal gene: it does
    # not enter the signature (two ensembles with identical members are identical
    # regardless of how those members were sourced).
    ensemble_source: str = "random"

    # regime activation genes
    regime_hurst_min: float = 0.5
    regime_adx_min: float = 20.0
    regime_atr_rank_min: float = 0.3

    # SMC / ICT structure genes (Phase 2.2b)
    smc_pivot_strength: int = 2
    smc_range_lookback: int = 100
    smc_pool_window: int = 40
    smc_pool_tol_pips: float = 1.0
    smc_fvg_lookback: int = 20
    smc_displacement_atr: float = 1.0
    smc_spring_depth_atr: float = 0.3
    smc_sweep_depth_atr: float = 0.3
    smc_ote_low: float = 0.705
    smc_ote_high: float = 0.79
    smc_ob_lookback: int = 20
    smc_momentum_atr: float = 1.0
    smc_atr_rank_min: float = 0.5
    smc_turtle_lookback: int = 20

    # statistical arbitrage genes (Phase 2.2b)
    statarb_partner: str = ""
    statarb_window: int = 100
    statarb_z: float = 2.0

    # volatility / statistical family genes (Phase 2.2c)
    squeeze_rank: float = 0.2
    expansion_atr: float = 1.0
    vcp_lookback: int = 60
    vcp_contractions: int = 2
    ignition_vol_mult: float = 2.0
    pullback_frac: float = 0.5
    orb_minutes: int = 30
    vwap_std_mult: float = 2.0
    zscore_entry: float = 2.0
    hurst_trend_min: float = 0.6
    hurst_revert_max: float = 0.4
    volume_spike_mult: float = 2.0

    # pattern / confluence family genes (Phase 2.2c)
    pin_ratio: float = 2.0
    fib_low: float = 0.382
    fib_high: float = 0.786
    harmonic_tolerance: float = 0.05
    mtf_window: int = 12
    london_hours: int = 3
    hikkake_lookback: int = 6

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family {self.family!r}")

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> dict:
        """Plain-dict form; ensemble members are nested dicts."""
        out: dict = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "ensemble_members":
                out[f.name] = [dict(m) for m in value]
            else:
                out[f.name] = value
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyGenome":
        """Build a genome, ignoring unknown keys and clamping out-of-bounds genes."""
        known = {f.name for f in fields(cls)}
        kwargs: dict = {}
        for key, value in dict(data or {}).items():
            if key not in known:
                continue  # unknown keys ignored safely
            if key == "ensemble_members":
                kwargs[key] = tuple(dict(m) for m in (value or ()))
            elif key == "family":
                kwargs[key] = value if value in FAMILIES else "trend_pullback"
            elif key == "ensemble_source":
                kwargs[key] = value if value in ("elite", "random") else "random"
            elif key in GENE_BOUNDS_BY_NAME:
                kwargs[key] = clamp_gene(key, value)
            else:
                kwargs[key] = value
        return cls(**kwargs)

    # -- lineage ------------------------------------------------------------
    def signature(self) -> str:
        """A stable, compact lineage id.

        Deterministic over the family + every gene; ensembles additionally fold
        in their members' signatures so two different member sets never collide.
        """
        payload = {"family": self.family}
        for f in fields(self):
            if f.name in ("ensemble_members", "ensemble_source"):
                continue  # R58: members fold in below; source is provenance, not DNA
            payload[f.name] = getattr(self, f.name)
        if self.ensemble_members:
            member_sigs = sorted(
                StrategyGenome.from_dict(m).signature() for m in self.ensemble_members
            )
            payload["ensemble_member_signatures"] = member_sigs
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]

    # -- convenience --------------------------------------------------------
    def with_genes(self, **changes) -> "StrategyGenome":
        """A copy with clamped gene overrides (unknown names raise)."""
        for key in changes:
            if key not in GENE_BOUNDS_BY_NAME and key not in ("family", "ensemble_members"):
                raise KeyError(f"not a gene: {key}")
            if key in GENE_BOUNDS_BY_NAME:
                changes[key] = clamp_gene(key, changes[key])
        return replace(self, **changes)
