"""R95-R99 (Phase 7m revised) — THE VOLUME ENGINE: the volume law reducers.

R92 sets a first-class portfolio constraint: a SUSTAINED minimum of 5 executed,
DISTINCT trades per week, inside a sealed max-drawdown cage. These tests pin the
pure reducers of the volume engine WITHOUT a tape:

* the PORTFOLIO MATH (both cases) — the per-pair frequency 5/week demands;
* the OVERLAP GUARD — same-pair same-day collapses to ONE casello (distinct
  volume only), and the collapse neither inflates volume nor the P&L;
* the SUSTAINABILITY WINDOW — the rolling 12-month trades/week and the DIRECTION
  of the worst-window statistic;
* the UTILITY CURVE — frequency capped at the law, net floored at zero, DD
  linearly penalized.
"""

from __future__ import annotations

import numpy as np

from tools import volume_engine_v3 as v


# ---------------------------------------------------------------------------
# (1) THE PORTFOLIO MATH
# ---------------------------------------------------------------------------
def test_single_strategy_spreads_the_law_over_fifteen_pairs():
    m = v.portfolio_math()["single_strategy"]
    assert m["pairs"] == 15
    assert m["required_entries_per_week_per_pair"] == round(5.0 / 15, 4)
    # 1/3 per week ~= 1.444 per month per pair
    assert m["required_entries_per_month_per_pair"] == round(
        (5.0 / 15) * (52.0 / 12.0), 4)


def test_multi_strategy_spreads_the_law_over_45_snipers():
    m = v.portfolio_math()["multi_strategy"]
    assert m["max_snipers"] == 45 and m["max_families_per_pair"] == 3
    assert m["required_entries_per_week_per_sniper"] == round(5.0 / 45, 4)
    assert m["required_entries_per_month_per_pair"] == round(
        (5.0 / 45) * 3 * (52.0 / 12.0), 4)


# ---------------------------------------------------------------------------
# (2) THE FREQUENCY LADDER
# ---------------------------------------------------------------------------
def test_ladder_stays_in_the_vnsb_top_half():
    plan = v.ladder_plan("rsi_only")
    assert plan, "the ladder must be non-empty"
    for _name, prog, over, gap in plan:
        assert v.VNSB_TOP_HALF[0] <= over["sl_atr_mult"] <= v.VNSB_TOP_HALF[1]
        assert gap in v.LADDER_GAPS
        assert prog.concept.startswith("ladder:")


def test_ladder_is_deterministic():
    assert v.ladder_plan("rsi_only") == v.ladder_plan("rsi_only")


# ---------------------------------------------------------------------------
# (3) THE OVERLAP GUARD
# ---------------------------------------------------------------------------
class _T:
    def __init__(self, ts, r):
        self.entry_ts = ts
        self.net_r = r


class _M:
    def __init__(self, trades, net_r):
        self.trades = trades
        self.net_r = net_r


def _arm(pair, name, day_r_pairs):
    """Build a fake Arm: day_r_pairs = [(day_index, net_r), ...]."""
    trades = [_T(d * 86400, r) for d, r in day_r_pairs]
    return v.Arm(name, pair, trades, _M(trades, sum(r for _, r in day_r_pairs)),
                 sorted({d for d, _ in day_r_pairs}), None, 1.5)


def test_same_pair_same_day_collapses_to_one_casello():
    a = _arm("EURUSD", "A", [(10, 1.0), (11, 2.0)])
    b = _arm("EURUSD", "B", [(10, 3.0), (12, 4.0)])
    arms = [a, b]
    caselli = v.distinct_day_caselli(arms)
    # days 10, 11, 12 -> three distinct caselli, NOT four trades
    assert caselli == {("EURUSD", 10), ("EURUSD", 11), ("EURUSD", 12)}


def test_overlap_matrix_reports_the_shared_fraction():
    a = _arm("EURUSD", "A", [(10, 1.0), (11, 2.0)])
    b = _arm("EURUSD", "B", [(10, 3.0), (12, 4.0)])
    ov = v.overlap_matrix([a, b])
    row = ov["per_pair"]["EURUSD"][0]
    assert row["shared_days"] == 1
    assert row["overlap_of_smaller"] == round(1 / 2, 4)
    assert ov["max_overlap_of_smaller"] == round(1 / 2, 4)


def test_different_pairs_never_overlap():
    a = _arm("EURUSD", "A", [(10, 1.0)])
    b = _arm("GBPUSD", "B", [(10, 3.0)])
    ov = v.overlap_matrix([a, b])
    assert ov["max_overlap_of_smaller"] == 0.0


def test_casello_collapse_averages_the_pnl_not_sums_it():
    a = _arm("EURUSD", "A", [(10, 2.0)])
    b = _arm("EURUSD", "B", [(10, 4.0)])
    series = v.distinct_casello_series([a, b])
    assert len(series) == 1
    assert series[0][1] == 3.0  # mean(2, 4), not 6


def test_realized_portfolio_uses_the_distinct_series():
    a = _arm("EURUSD", "A", [(10, 1.0), (20, -3.0)])
    dd = v.realized_portfolio([a])
    assert dd["distinct_caselli"] == 2
    assert dd["max_drawdown_r"] == 3.0     # peak 1 -> trough -2
    assert dd["net_r"] == -2.0
    assert dd["within_seal"] is True


def test_realized_portfolio_breaches_the_seal():
    # 40R of drawdown breaches the WIDENED 30R seal (was 15R before Phase 7n-2).
    a = _arm("EURUSD", "A", [(i, -1.0) for i in range(40)])
    dd = v.realized_portfolio([a])
    assert dd["max_drawdown_r"] == 40.0
    assert dd["within_seal"] is False


def test_twenty_r_drawdown_fits_inside_the_widened_seal():
    a = _arm("EURUSD", "A", [(i, -1.0) for i in range(20)])
    dd = v.realized_portfolio([a])
    assert dd["max_drawdown_r"] == 20.0
    assert dd["within_seal"] is True


# ---------------------------------------------------------------------------
# (4) THE SUSTAINABILITY WINDOW
# ---------------------------------------------------------------------------
def test_short_tape_is_a_single_window():
    r = v.rolling_week_windows([0, 7, 14])
    assert r["n_windows"] == 1
    assert r["worst_window_trades_per_week"] == r["mean_window_trades_per_week"]


def test_worst_window_is_no_greater_than_the_mean():
    days = sorted(set(range(0, 3000, 4)))
    r = v.rolling_week_windows(days)
    assert r["n_windows"] > 1
    assert r["worst_window_trades_per_week"] <= r["mean_window_trades_per_week"]


def test_worst_window_finds_the_drought():
    # 60 weeks dense (every 2 days), then a 60-week drought (nothing), then dense.
    dense1 = list(range(0, 420, 2))
    dense2 = list(range(840, 1260, 2))
    r = v.rolling_week_windows(sorted(dense1 + dense2))
    # a full 12-month window inside the drought must read near zero
    assert r["worst_window_trades_per_week"] < 1.0
    assert r["mean_window_trades_per_week"] > r["worst_window_trades_per_week"]


# ---------------------------------------------------------------------------
# (5) THE DRAWDOWN SEAL
# ---------------------------------------------------------------------------
def test_drawdown_seal_is_thirty_r_after_the_ceo_widening():
    # R97 was WIDENED 15R -> 30R by the CEO (Phase 7n-2 ruling).
    assert v.DRAWDOWN_SEAL_R == 30.0
    assert v.DRAWDOWN_SEAL_HISTORY == (15.0, 30.0)
    assert v.TITANIUM_FLOOR_PCT == 1.0  # eternal law


# ---------------------------------------------------------------------------
# (7) THE UTILITY CURVE
# ---------------------------------------------------------------------------
def test_utility_caps_frequency_at_the_law():
    u5 = v.utility(5.0, 0.0, 0.0)
    u9 = v.utility(9.0, 0.0, 0.0)
    assert u5["utility"] == u9["utility"] == 5.0     # satiety: the law is a floor
    assert u9["freq_term"] == 5.0


def test_utility_penalizes_drawdown_linearly():
    u = v.utility(5.0, 10.0, 4.0)
    assert u["freq_term"] == 5.0
    assert u["net_term"] == round(0.05 * 10.0, 4)
    assert u["dd_term"] == round(0.30 * 4.0, 4)
    assert u["utility"] == round(5.0 + 0.5 - 1.2, 4)


def test_utility_gives_no_credit_for_a_losing_net():
    u = v.utility(2.0, -100.0, 0.0)
    assert u["net_term"] == 0.0
    assert u["law_shortfall"] == 3.0


def test_frontier_curve_reports_the_highest_clearing_epm():
    pts = [
        {"name": "a", "entries_per_month": 0.2, "gate_ok": True},
        {"name": "b", "entries_per_month": 0.4, "gate_ok": True},
        {"name": "c", "entries_per_month": 0.9, "gate_ok": False},
    ]
    f = v.frontier_curve(pts)
    assert f["highest_clearing_epm"] == 0.4
    assert f["n_crossers"] == 2


def test_frontier_curve_handles_an_empty_clearing_set():
    f = v.frontier_curve([{"name": "x", "entries_per_month": 0.9, "gate_ok": False}])
    assert f["highest_clearing_epm"] is None and f["n_crossers"] == 0


# ---------------------------------------------------------------------------
# assembly selectors
# ---------------------------------------------------------------------------
def _mk_arm(pair, name, net_r, days, epm):
    trades = [_T(d * 86400, net_r / max(1, len(days))) for d in days]
    m = _M(trades, net_r)
    return v.Arm(name, pair, trades, m, sorted(days), None, 1.5, epm=epm)


def test_max_volume_selector_prefers_the_densest_arm():
    densest = _mk_arm("EURUSD", "dense", 1.0, [1, 2, 3, 4], 0.9)
    richest = _mk_arm("EURUSD", "rich", 99.0, [10, 20], 0.2)
    arms = v.select_max_volume_assembly({"EURUSD": [densest, richest]},
                                        families_per_pair=1)
    assert [a.name for a in arms] == ["dense"]


def test_net_selector_prefers_the_richest_arm():
    densest = _mk_arm("EURUSD", "dense", 1.0, [1, 2, 3, 4], 0.9)
    richest = _mk_arm("EURUSD", "rich", 99.0, [10, 20], 0.2)
    arms = v.select_assembly({"EURUSD": [densest, richest]}, families_per_pair=1)
    assert [a.name for a in arms] == ["rich"]


def test_max_volume_selector_caps_families_per_pair():
    arms_in = [_mk_arm("EURUSD", f"a{i}", 1.0, [i * 40, i * 40 + 1], 0.5)
               for i in range(6)]
    picked = v.select_max_volume_assembly({"EURUSD": arms_in}, families_per_pair=3)
    assert len(picked) <= 3
