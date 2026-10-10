"""Tests for R73 (realms), R72 (entropy), R71a/b/c (EDA, CMA-ES, polish)."""

from __future__ import annotations

import numpy as np
import pytest

from app.factory import cma as cma_mod
from app.factory import eda as eda_mod
from app.factory import entropy as entropy_mod
from app.factory import polish as polish_mod
from app.factory import realms as realms_mod
from app.quant.genome import StrategyGenome


# --- R73 realms ------------------------------------------------------------

def test_regime_tag_bands():
    assert realms_mod.regime_tag({"regime_hurst_min": 0.7}) == "trend"
    assert realms_mod.regime_tag({"regime_hurst_min": 0.4}) == "range"
    assert realms_mod.regime_tag({"regime_hurst_min": 0.55}) == "chop"
    assert realms_mod.regime_tag({}) == "chop"            # missing -> honest cell
    assert realms_mod.regime_tag({"regime_hurst_min": float("nan")}) == "chop"


def test_pair_class():
    assert realms_mod.pair_class("USDJPY") == "jpy"
    assert realms_mod.pair_class("EURUSD") == "major"
    assert realms_mod.pair_class("EURGBP") == "cross"
    assert realms_mod.pair_class(None) == "all"


def test_realm_of_refuses_row_without_family():
    with pytest.raises(realms_mod.RealmError):
        realms_mod.realm_of({"signature": "x"})


def test_kings_by_realm_keeps_best_per_cell_and_distinct_champions():
    rows = [
        {"signature": "a", "family": "trend_pullback", "regime_hurst_min": 0.7,
         "wilson_lb": 0.30, "net_r": 1.0},
        {"signature": "b", "family": "breakout", "regime_hurst_min": 0.7,
         "wilson_lb": 0.40, "net_r": 1.0},
        # same realm as 'a' (trend group, trend regime, all pairs) but better
        {"signature": "c", "family": "trend_pullback",
         "regime_hurst_min": 0.7, "wilson_lb": 0.55, "net_r": 1.0},
        {"signature": "d", "family": "mean_reversion", "regime_hurst_min": 0.4,
         "wilson_lb": 0.35, "net_r": 1.0},
    ]
    kings = realms_mod.kings_by_realm(rows)
    assert len(kings) == 3                                 # a/c collapsed
    champs = realms_mod.distinct_realm_champions(rows, seats=7)
    sigs = [c["signature"] for c in champs]
    assert len(sigs) == len(set(sigs)) == 3
    assert "c" in sigs                                     # best in its realm
    assert "a" not in sigs


def test_census_reports_occupancy():
    rows = [
        {"signature": "a", "family": "breakout", "regime_hurst_min": 0.7,
         "wilson_lb": 0.4},
        {"signature": "b", "family": "mean_reversion", "regime_hurst_min": 0.4,
         "wilson_lb": 0.4},
    ]
    c = realms_mod.census(rows)
    assert c["occupied"] == 2
    assert c["total_rows"] == 2
    assert c["by_regime"] == {"range": 1, "trend": 1}


# --- R72 entropy -----------------------------------------------------------

def test_normalized_entropy_bounds():
    assert entropy_mod.normalized_entropy([]) == 0.0
    assert entropy_mod.normalized_entropy(["a"]) == 0.0
    assert entropy_mod.normalized_entropy(["a", "a", "a"]) == 0.0
    assert entropy_mod.normalized_entropy(["a", "b", "c"]) == pytest.approx(1.0)


def test_adaptive_rate_is_monotone_decreasing_in_entropy():
    low = entropy_mod.adaptive_mutation_rate(["a"] * 10)          # entropy 0
    high = entropy_mod.adaptive_mutation_rate(
        [str(i) for i in range(20)])                              # entropy 1
    assert low == entropy_mod.RATE_MAX
    assert high == entropy_mod.RATE_MIN
    assert low > entropy_mod.RATE_BASE > high


def test_entropy_reading_band():
    assert entropy_mod.EntropyReading(["a"] * 5).band == "explore"
    assert entropy_mod.EntropyReading([str(i) for i in range(10)]).band == "refine"


def test_adaptive_rate_rejects_bad_bands():
    with pytest.raises(ValueError):
        entropy_mod.adaptive_mutation_rate(["a"], low=0.8, high=0.2)


# --- R71a EDA --------------------------------------------------------------

def test_eda_returns_none_under_min_observations():
    mem = eda_mod.GeneMemory()
    mem.observe([StrategyGenome.from_dict({"family": "trend_pullback",
                                           "target_rr": 3.0})])
    assert mem.sample_gene("trend_pullback", "target_rr", np.random.default_rng(0)) is None
    assert mem.count("trend_pullback", "target_rr") == 1


def test_eda_draws_from_survivor_distribution_within_bounds():
    mem = eda_mod.GeneMemory()
    survivors = [StrategyGenome.from_dict({"family": "breakout", "target_rr": 3.0 + i * 0.1})
                 for i in range(10)]
    mem.observe(survivors)
    fit = mem.mean_std("breakout", "target_rr")
    assert fit is not None
    mean, std = fit
    assert 3.0 <= mean <= 4.0
    rng = np.random.default_rng(0)
    for _ in range(50):
        drawn = mem.sample_gene("breakout", "target_rr", rng)
        assert drawn is not None
        assert 2.5 <= drawn <= 8.0                       # clamped into the law


def test_eda_underobserved_snapshot_is_empty_and_unknown_family_is_zero():
    mem = eda_mod.GeneMemory()
    mem.observe([StrategyGenome.from_dict({"family": "breakout"})])
    assert mem.snapshot() == {}                      # under-observed: no fit
    assert mem.count("nope", "target_rr") == 0


# --- R71b CMA-ES -----------------------------------------------------------

def test_cma_improves_a_simple_quadratic_and_stays_bounded():
    low = np.array([-5.0, -5.0])
    high = np.array([5.0, 5.0])
    target = np.array([3.0, -2.0])

    def objective(x):
        return -float(np.sum((x - target) ** 2))

    x0 = np.array([0.0, 0.0])
    start = objective(x0)
    res = cma_mod.refine(x0, objective, low, high,
                         cma_mod.CMAConfig(population=16, generations=40, seed=1))
    assert res.start_value == start
    assert res.best_value >= start                      # never worse
    assert np.all(res.best_x >= low) and np.all(res.best_x <= high)
    assert res.evaluations == 1 + 16 * 40


def test_cma_respects_zero_width_bounds():
    low = np.array([1.0])
    high = np.array([1.0])

    def objective(x):
        return -float((x[0] - 1.0) ** 2)

    res = cma_mod.refine(np.array([1.0]), objective, low, high,
                         cma_mod.CMAConfig(population=4, generations=3, seed=0))
    assert res.best_x[0] == 1.0


def test_cma_config_validation():
    with pytest.raises(ValueError):
        cma_mod.CMAConfig(population=1)
    with pytest.raises(ValueError):
        cma_mod.CMAConfig(generations=0)
    with pytest.raises(ValueError):
        cma_mod.CMAConfig(sigma0_frac=0.0)


# --- R71c polish -----------------------------------------------------------

def test_polish_writes_back_and_respects_bounds():
    g = StrategyGenome.from_dict({"family": "trend_pullback", "target_rr": 3.0})

    def objective(cand):
        # reward target_rr closer to 5.0 (bounded by the gene's [2.5, 8.0])
        return -abs(float(cand.target_rr) - 5.0)

    res = polish_mod.polish_genome(g, objective,
                                   polish_mod.PolishConfig(steps=6, seed=0))
    assert res.best_value >= res.start_value
    assert 2.5 <= float(res.genome.target_rr) <= 8.0
    # Lamarck: the returned genome is the improved one (written back)
    assert float(res.genome.target_rr) != 3.0 or res.delta == 0.0


def test_polish_config_rejects_non_gene():
    with pytest.raises(ValueError):
        polish_mod.PolishConfig(genes=("family",))
    with pytest.raises(ValueError):
        polish_mod.PolishConfig(steps=0)


def test_polish_no_improvement_keeps_genome():
    g = StrategyGenome.from_dict({"family": "trend_pullback"})

    def flat(cand):
        return 1.0                                    # nothing to improve

    res = polish_mod.polish_genome(g, flat, polish_mod.PolishConfig(steps=2, seed=0))
    assert res.delta == 0.0
    assert res.genome.signature() == g.signature()
