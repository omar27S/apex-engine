"""THE INSTITUTIONAL SEEDS — one curated genome per family (47 total).

Each seed is hand-parameterized to its family's concept (the Phase-2.2-era seed
style) and carries GATE DIVERSITY: a counter-trend/reversion seed explicitly sets
``trend_align=0``, a trend seed sets ``trend_align=1``, and so on. The seed set is
the fixed origin of the lineage universe — the reference DNA the breeding loom is
seeded from.

The ensemble seed's members are deliberately DIVERSE families (no two identical),
with an explicit quorum (R3). As of Mega Phase 2 (Section D) the three ML families
(``ml_gradient_boosting``, ``ml_lstm_pattern``, ``ml_bayesian_regime``) each carry
a seed too, so the learned models enter the tournament like any other family.

Every seed is validated by ``tests/quant/test_seeds.py``: it must fire at least one
RAW signal on the real EURUSD tape under a permissive gate probe, round-trip
through ``from_dict``, and have a stable signature.

Build Mode: pure data + pure builders; no I/O at import.
"""

from __future__ import annotations

from app.quant.genome import ENSEMBLE_FAMILY, FAMILIES, StrategyGenome

__all__ = ["SEED_SPECS", "build_seeds", "seed_for", "seed_signatures"]

# Base gates for a seed: the shared gates OPEN (a seed is a raw probe of its
# concept), and the seven per-family gate genes set explicitly per seed for
# diversity. ``trend_align`` is the headline axis: 0 = counter-trend/reversion.
_PERMISSIVE_GATES = dict(
    session_id=0,
    min_atr_pips=0.0,
    regime_adx_min=0.0,
    regime_atr_rank_min=0.0,
    regime_hurst_min=0.0,
    min_confluence=0,
    require_h1_align=0,
)

# family -> concept genes + gate choices. ``trend_align`` is set on every entry to
# make the diversity explicit (0 = counter-trend, 1 = with-trend).
SEED_SPECS: dict[str, dict] = {
    # --- classic trend / momentum (with-trend) ---
    "trend_pullback": dict(trend_align=1, ema_fast=13, ema_slow=34, pullback_rsi=55.0),
    "mean_reversion": dict(trend_align=0, bb_period=20, bb_std=2.0, rsi_oversold=30.0, rsi_overbought=70.0),
    "breakout": dict(trend_align=1, target_lookback=20, min_atr_pips=0.0),
    "macd_momentum": dict(trend_align=1, macd_fast=12, macd_slow=26, macd_signal=9),
    "keltner_expansion": dict(trend_align=1, keltner_period=20, keltner_mult=2.0, atr_period=14),
    "rsi_reversal": dict(trend_align=0, rsi_period=14, rsi_oversold=30.0, rsi_overbought=70.0),
    # --- SMC / ICT (sequence) ---
    "wyckoff_spring": dict(trend_align=0, smc_spring_depth_atr=0.3, smc_pivot_strength=2),
    "order_block": dict(trend_align=1, smc_ob_lookback=20, smc_displacement_atr=1.0),
    "volume_delta": dict(trend_align=1, volume_spike_mult=2.0),
    "ob_atr_rank": dict(trend_align=1, smc_atr_rank_min=0.5, smc_ob_lookback=20),
    "cointegration_statarb": dict(trend_align=0, statarb_window=100, statarb_z=2.0),
    "liq_sweep_ote": dict(trend_align=0, smc_ote_low=0.705, smc_ote_high=0.79, smc_sweep_depth_atr=0.3),
    "choch_fvg": dict(trend_align=0, smc_fvg_lookback=20, smc_pivot_strength=2),
    "bos_premium_discount": dict(trend_align=1, smc_range_lookback=100, smc_pivot_strength=2),
    "fvg_momentum": dict(trend_align=1, smc_fvg_lookback=20, smc_momentum_atr=1.0),
    "silver_bullet": dict(trend_align=1, smc_fvg_lookback=20, smc_displacement_atr=1.0),
    "asian_range_sweep": dict(trend_align=0, smc_pool_window=40, smc_pool_tol_pips=1.0),
    "eqhl_tap": dict(trend_align=0, smc_pool_window=40, smc_pool_tol_pips=1.0),
    "judas_swing": dict(trend_align=0, smc_sweep_depth_atr=0.3, smc_range_lookback=100),
    "ict_2022_model": dict(trend_align=0, smc_fvg_lookback=20, smc_pivot_strength=2),
    "dealing_range": dict(trend_align=0, smc_range_lookback=100, smc_pivot_strength=2),
    "turtle_soup": dict(trend_align=0, smc_turtle_lookback=20, smc_pivot_strength=2),
    # --- statistical / volatility ---
    "bb_keltner_squeeze": dict(trend_align=1, squeeze_rank=0.2, bb_period=20, keltner_period=20),
    "rsi_divergence": dict(trend_align=0, rsi_period=14, smc_pivot_strength=2),
    "vwap_reversion": dict(trend_align=0, vwap_std_mult=2.0),
    "keltner_pullback": dict(trend_align=1, keltner_period=20, keltner_mult=2.0),
    "zscore_reversion": dict(trend_align=0, zscore_period=20, zscore_entry=2.0),
    "hurst_regime": dict(trend_align=0, hurst_window=100, hurst_trend_min=0.6, hurst_revert_max=0.4),
    "atr_squeeze_breakout": dict(trend_align=1, squeeze_rank=0.2, expansion_atr=1.0),
    "london_orb": dict(trend_align=1, orb_minutes=30, london_hours=3),
    "ny_orb": dict(trend_align=1, orb_minutes=30),
    "vcp_breakout": dict(trend_align=1, vcp_lookback=60, vcp_contractions=2),
    "momentum_ignition": dict(trend_align=1, ignition_vol_mult=2.0),
    # --- pattern / confluence ---
    "pin_bar": dict(trend_align=0, pin_ratio=2.0, smc_pivot_strength=2),
    "engulfing_liquidity": dict(trend_align=0, smc_pool_window=40, smc_pool_tol_pips=1.0),
    "hikkake": dict(trend_align=0, hikkake_lookback=6),
    "fib_confluence": dict(trend_align=0, fib_low=0.382, fib_high=0.786, smc_pivot_strength=2),
    "harmonic_proxy": dict(trend_align=0, harmonic_tolerance=0.05, smc_pivot_strength=2),
    "mtf_divergence": dict(trend_align=0, mtf_window=12, rsi_period=14),
    "volume_profile_v": dict(trend_align=1, volume_spike_mult=2.0),
    "fib_ote_confluence": dict(trend_align=0, smc_ote_low=0.705, smc_ote_high=0.79, fib_low=0.618, fib_high=0.786),
    "hurst_reversion_filtered": dict(trend_align=0, hurst_window=100, hurst_revert_max=0.4, adx_min=18.0),
    "time_based_reversal": dict(trend_align=0, london_hours=3),
    # --- ensemble: diverse concrete members, explicit quorum (R3) ---
    "ensemble": dict(
        trend_align=0,
        ensemble_window=500,
        ensemble_min_votes=3,
        ensemble_members=(
            StrategyGenome(family="breakout").to_dict(),
            StrategyGenome(family="mean_reversion").to_dict(),
            StrategyGenome(family="macd_momentum").to_dict(),
            StrategyGenome(family="rsi_reversal").to_dict(),
            StrategyGenome(family="trend_pullback").to_dict(),
        ),
    ),
    # --- machine learning (Mega Phase 2, Section D): lightweight learned models ---
    "ml_gradient_boosting": dict(trend_align=0, ml_horizon=4, ml_confidence=0.55, ml_decay=0.9),
    "ml_lstm_pattern": dict(trend_align=0, ml_horizon=4, ml_confidence=0.55, ml_decay=0.9),
    "ml_bayesian_regime": dict(trend_align=0, ml_horizon=4, ml_confidence=0.6, ml_decay=0.95),
}


def _seed_dict(family: str) -> dict:
    spec = dict(_PERMISSIVE_GATES)
    spec.update(SEED_SPECS.get(family, {}))
    spec["family"] = family
    return spec


def build_seeds() -> dict[str, StrategyGenome]:
    """The 44 curated seeds, keyed by family."""
    return {family: StrategyGenome.from_dict(_seed_dict(family)) for family in FAMILIES}


def seed_for(family: str) -> StrategyGenome:
    """The curated seed for ``family`` (raises on an unknown family)."""
    if family not in FAMILIES:
        raise KeyError(f"no seed for unknown family {family!r}")
    return StrategyGenome.from_dict(_seed_dict(family))


def seed_signatures() -> dict[str, str]:
    """``family -> signature`` for the whole seed set."""
    return {f: g.signature() for f, g in build_seeds().items()}
