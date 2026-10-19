"""THE DIPLOMAT (Mega Phase 2, Section F) -- the hyper-heuristic decision.

Friction contract: remove the flat->restructure rule and the decision tests FAIL;
fabricate an operator effect with no history and the honesty test FAILS.
"""

from __future__ import annotations

from app.factory import diplomat as dip


def test_population_state_reads_diversity_and_trend():
    pop = [{"family": "breakout", "net_r": 5.0}, {"family": "breakout", "net_r": 4.0}]
    st = dip.population_state(pop, performance_history=[1.0, 1.005, 1.003, 1.004])
    assert st["measured"] is True
    assert st["diversity"] == 0.5
    assert st["trend"] == "flat"


def test_population_state_is_honest_when_empty():
    st = dip.population_state([])
    assert st["measured"] is False and st["diversity"] is None


def test_flat_trend_orders_restructuring():
    st = {"measured": True, "trend": "flat", "diverse": True, "performance": 1.0}
    d = dip.select_operator(st)
    assert "SPECIALIZE" in d["operators"] and "HYBRIDIZE" in d["operators"]


def test_low_diversity_orders_exploration():
    st = {"measured": True, "trend": "rising", "diverse": False, "performance": 2.0}
    d = dip.select_operator(st)
    assert "MUTATE" in d["operators"] or "RANDOM" in d["operators"]


def test_operator_effect_sizes_are_absent_when_unused():
    stats = dip.operator_effect_sizes([])
    assert stats == {}
    stats2 = dip.operator_effect_sizes([{"operators": ["MUTATE"], "delta": 0.5},
                                        {"operators": ["MUTATE"], "delta": -0.1}])
    assert stats2["MUTATE"]["effect"] == round((0.5 - 0.1) / 2, 5)


def test_diplomat_prefers_a_positive_measured_operator():
    # MUTATE has a negative measured effect; DIRECT is positive and should replace it.
    stats = {"MUTATE": {"effect": -0.5, "n": 3}, "DIRECT": {"effect": 0.4, "n": 3},
             "RANDOM": {"effect": 0.1, "n": 2}}
    st = {"measured": True, "trend": "rising", "diverse": False, "performance": 1.0}
    d = dip.select_operator(st, operator_stats=stats)
    assert "MUTATE" not in d["operators"]


def test_diplomat_block_reports_the_decision():
    blk = dip.diplomat_block([{"family": "breakout", "net_r": 3.0}],
                             performance_history=[1.0, 1.0, 1.0, 1.0])
    assert blk["measured"] is True
    assert blk["decision"]["operators"]
    assert "DIPLOMATO" in blk["reading"]
