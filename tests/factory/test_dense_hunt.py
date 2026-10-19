"""PHASE 7n-2 — the DENSE HUNT (pure function tests, no real working tree)."""

from __future__ import annotations

from tools import dense_hunt_7n2 as d
from tools import volume_engine_v3 as ve


# --- the plans -------------------------------------------------------------
def test_sweep_plan_is_ten_families_by_three_stops():
    plan = d.sweep_plan()
    assert len(plan) == 30
    fams = {name.split(":")[1] for name, *_ in plan}
    assert len(fams) == 10
    assert fams == set(d.DENSE_FAMILIES)
    assert {sl for _, _, sl, _ in plan} == {1.4, 1.6, 1.8}


def test_sweep_plan_stays_in_the_vnsb_top_half():
    for _, _, sl, _ in d.sweep_plan():
        assert d.WIDE_SL_MIN <= sl <= d.WIDE_SL_MAX


def test_hybrid_plan_is_five_families_by_three_stops():
    plan = d.hybrid_plan()
    assert len(plan) == 15
    assert {name.split(":")[1] for name, *_ in plan} == set(d.HYBRID_FAMILIES)


def test_hybrids_carry_patient_exits_and_sweeps_do_not():
    for _, _, _, kw in d.hybrid_plan():
        assert kw["max_bars_hold"] == d.PATIENT_EXIT["max_bars_hold"] >= 300
        assert kw["target_rr"] >= 5.0
    for _, _, _, kw in d.sweep_plan():
        assert kw == {}


# --- the dense bar ---------------------------------------------------------
def _row(name, family, sl, mean_epm, net_r, paid):
    return {"name": name, "family": family, "sl": sl, "mean_epm": mean_epm,
            "pooled": {"net_r": net_r}, "paid_multiple": paid}


def test_dense_elite_requires_density_and_friction_and_profit():
    rows = [
        _row("a", "breakout", 1.4, 0.8, 50.0, 4.0),    # clears all three
        _row("b", "breakout", 1.6, 0.4, 50.0, 4.0),    # too sparse
        _row("c", "breakout", 1.8, 0.8, 50.0, 2.9),    # friction short
        _row("e", "breakout", 1.8, 0.8, -1.0, 4.0),    # losing
    ]
    elite = d.dense_elite(rows)
    assert [e["name"] for e in elite] == ["a"]


def test_dense_elite_is_empty_when_nothing_clears():
    rows = [_row("x", "london_orb", 1.4, 15.0, -2684.0, 0.0)]
    assert d.dense_elite(rows) == []


# --- the rulings -----------------------------------------------------------
def test_dense_hunt_reads_the_widened_thirty_r_seal():
    # The CEO widened R97 to 30R in this phase.
    assert ve.DRAWDOWN_SEAL_R == 30.0
    assert ve.TITANIUM_FLOOR_PCT == 1.0


def test_the_dense_bar_constants_are_sealed():
    assert d.EPM_FLOOR == 0.5
    assert d.FRICTION_BAR == 3.0
    assert d.MAJORS == ("EURUSD", "GBPUSD", "USDJPY", "USDCHF",
                        "AUDUSD", "USDCAD", "NZDUSD")
