"""PHASE 7p — THE INVENTION + THE EXPANSION (pure function tests)."""

from __future__ import annotations

from tools import expansion_7p as x
from tools import invention_7p as inv


# ---------------------------------------------------------------------------
# ROAD 1 — the invention
# ---------------------------------------------------------------------------
def _sweep(family, sl, mean_epm, gross, net, paid):
    return {"family": family, "sl": sl, "mean_epm": mean_epm,
            "pooled": {"gross_r": gross, "net_r": net}, "paid_multiple": paid}


def test_failure_autopsy_separates_before_and_at_spread():
    rows = [
        _sweep("london_orb", 1.4, 15.0, -577.0, -2684.0, 0.0),   # before-spread
        _sweep("breakout", 1.4, 7.9, 26.0, -884.0, 0.03),        # at-spread
        _sweep("winner", 1.8, 0.2, 69.0, 60.0, 7.9),             # survivor
    ]
    a = inv.failure_autopsy(rows)
    assert a[0]["loses"] == "before-spread"
    assert a[1]["loses"] == "at-spread"
    assert a[2]["loses"] == "survivor"


def test_autopsy_summary_counts_each_shape():
    rows = inv.failure_autopsy([
        _sweep("london_orb", 1.4, 15.0, -577.0, -2684.0, 0.0),
        _sweep("ny_orb", 1.4, 9.6, -410.0, -1646.0, 0.0),
        _sweep("breakout", 1.4, 7.9, 26.0, -884.0, 0.03),
    ])
    s = inv.autopsy_summary(rows)
    assert s["n_rows"] == 3 and s["before_spread"] == 2 and s["at_spread"] == 1
    assert set(s["before_spread_families"]) == {"london_orb", "ny_orb"}
    assert s["at_spread_families"] == ["breakout"]


def test_rare_anatomy_states_the_patience_arithmetic():
    r = inv.rare_anatomy(17.99, 7.9, 384)
    assert r["paid_multiple"] == 7.9 and r["holding_bars"] == 384
    assert "friction" in r["why"]


def test_zscore_edge_picks_the_best_dense_gross_edge():
    rows = [_sweep("zscore_reversion", 1.4, 5.6, 223.0, -413.0, 0.35),
            _sweep("zscore_reversion", 1.8, 3.4, 216.0, -163.0, 0.57)]
    z = inv.zscore_edge(rows)
    assert z["sl"] == 1.8 and z["paid_multiple"] == 0.57


def test_novelty_plan_is_sixty_bodies():
    plan = inv.novelty_plan()
    assert len(plan) == 60
    names = [p["name"] for p in plan]
    assert len(set(names)) == 60
    # the patience wrappers are present
    assert any("quiet" in p["wrapper"] for p in plan)
    assert any("gap" in p["wrapper"] for p in plan)


def test_invention_frontier_needs_both_density_and_pay():
    pts = [
        {"name": "dense_only", "entries_per_month": 5.0, "gate_ok": False},
        {"name": "pay_only", "entries_per_month": 0.2, "gate_ok": True},
        {"name": "both", "entries_per_month": 0.8, "gate_ok": True},
    ]
    f = inv.invention_frontier(pts)
    assert f["n_dense_and_paying"] == 1
    assert f["dense_and_paying_names"] == ["both"]
    assert f["verdict"] == "INVENTED"


def test_invention_frontier_seals_the_negative_verdict():
    pts = [{"name": "x", "entries_per_month": 9.0, "gate_ok": False}]
    f = inv.invention_frontier(pts)
    assert f["n_dense_and_paying"] == 0
    assert "does not exist" in f["verdict"]


# ---------------------------------------------------------------------------
# ROAD 2 — the expansion
# ---------------------------------------------------------------------------
def test_roster_study_ranks_tighter_spreads_higher():
    r = x.roster_study()
    assert r["need"] == x.TARGET_PAIRS - x.CURRENT_ROSTER
    ranked = r["ranked"]
    # the top candidate must be a tight-spread primary
    assert ranked[0]["tier"] == "primary"
    assert ranked[0]["score"] >= ranked[-1]["score"]


def test_roster_covers_enough_candidates_for_the_target():
    r = x.roster_study()
    assert r["n_candidates"] >= r["need"]


def test_acquisition_plan_sizes_the_new_tapes():
    r = x.roster_study()
    a = x.acquisition_plan(r)
    assert a["release_tag"] == "market-data-v2"
    assert a["n_tapes"] == r["need"]
    assert a["est_mb"] > 0 and a["est_time_minutes"] > 0
    assert "sha256" in a["manifest_plan"].lower() or "SHA-256" in a["manifest_plan"]


def test_expand_cadence_grows_the_pair_count():
    day_lists = {
        "EURUSD": [0, 30, 60, 90],
        "GBPUSD": [10, 40, 70, 100],
    }
    out = x.expand_cadence(day_lists, current=2, target=5)
    assert len(out) == 5
    assert out["EURUSD"] == [0, 30, 60, 90]


def test_simulate_expansion_scales_with_pair_count():
    day_lists = {
        "A": sorted(range(0, 500, 20)),
        "B": sorted(range(7, 500, 25)),
    }
    small = x.simulate_expansion(day_lists, target=2)
    big = x.simulate_expansion(day_lists, target=8)
    # more pairs => more distinct trades/week in the worst window
    assert big["worst_window_trades_per_week"] > small["worst_window_trades_per_week"]


def test_expansion_curve_is_monotone_in_target_over_a_flat_source():
    day_lists = {"A": sorted(range(0, 800, 30))}
    curve = x.expansion_curve(day_lists, targets=(1, 2, 4, 8))
    worsts = [c["worst_window_trades_per_week"] for c in curve]
    assert worsts == sorted(worsts)


def test_expansion_verdict_reports_the_gap():
    day_lists = {"A": sorted(range(0, 400, 40))}
    rep = {"expansion_at_target": x.simulate_expansion(day_lists, target=20),
           "current_multi_strategy": {"worst_window_trades_per_week": 2.65}}
    v = x._expansion_verdict(rep)
    assert "expanded_worst" in v and "reading" in v
    assert v["expanded_worst"] >= 0.0
