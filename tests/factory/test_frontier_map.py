"""R88/R89 (Phase 7k) — THE FRONTIER MAP: the gross-edge grammar + the curve.

Phase 7k makes the Session 4.0 gradient EXPLICIT as a reference curve, and adds
the grammar the curve needed to exist. These tests pin:

* the three R89 gross-edge primitives (typing, bounds, emission, causality);
* the deterministic frontier GRID (2 events x the spacing ladder = 20 bodies),
  each a valid static-gate body;
* the frequency/curve REDUCER (``frontier_curve``): sorting, monotonicity, and
  the 3x crossing test — pure, so the AGENTS.md reference curve is reproducible
  without a tape.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core import law
from app.pyramid.author import author2 as a2
from app.pyramid.author import grammar as g
from app.pyramid.sandbox import static_gate
from tools import author_session_5 as s5


# ---------------------------------------------------------------------------
# Grammar: the three R89 gross-edge primitives.
# ---------------------------------------------------------------------------
def test_gross_edge_nodes_are_registered_primitives():
    for k in ("vol_displacement", "pullback_depth", "session_boundary_reversal"):
        assert k in g.PRIMITIVE_KINDS


def test_hunt_bodies_are_valid_and_pass_the_static_gate():
    hyps = a2.hunt_hypotheses()
    assert len(hyps) == 9
    for h in hyps:
        assert h.program.long.type == g.BOOL and h.program.short.type == g.BOOL
        assert static_gate.check_source(g.emit_python(h.program)).ok


def test_vol_displacement_rejects_out_of_range_window():
    g.node("vol_displacement", (96,))  # legal
    with pytest.raises(g.GrammarError):
        g.node("vol_displacement", (3,))  # below the multi-day floor


def test_pullback_depth_rejects_out_of_range_window():
    g.node("pullback_depth", (48,))  # legal
    with pytest.raises(g.GrammarError):
        g.node("pullback_depth", (2,))


def test_session_boundary_reversal_bounds_and_singleton_child():
    child = g.node("zscore", (40,))
    g.node("session_boundary_reversal", (2.0,), (child,))  # legal
    with pytest.raises(g.GrammarError):
        g.node("session_boundary_reversal", (5.0,), (child,))  # fade out of range
    with pytest.raises(g.GrammarError):
        g.node("session_boundary_reversal", (2.0,), ())  # needs a child


def test_min_gap_bars_now_reaches_the_rare_regime():
    g.node("min_gap_bars", (4096,), (g.node("day_of_week", (1,)),))  # legal (R89)


# ---------------------------------------------------------------------------
# Semantics + causality of the new helpers.
# ---------------------------------------------------------------------------
def _helpers() -> dict:
    ns: dict = {}
    exec(compile(g.preamble_helpers(), "<frontier_preamble>", "exec"), ns)
    return ns


def _tape(n=800, vol=0.3, seed=11):
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, vol, n))
    high = close + np.abs(rng.normal(0.0, vol / 2, n))
    low = close - np.abs(rng.normal(0.0, vol / 2, n))
    return high, low, close


def test_vol_displacement_is_signed_and_atr_scaled():
    ns = _helpers()
    high, low, close = _tape()
    disp = ns["_vol_displacement"](close, high, low, 96)
    finite = disp[np.isfinite(disp)]
    assert finite.size
    # an up-trending tape (positive drift here) leans positive; magnitudes are
    # ATR-scaled, i.e. of order a few, not raw pips.
    assert abs(np.nanmedian(finite)) <= 20.0


def test_pullback_depth_is_in_unit_interval():
    ns = _helpers()
    high, low, close = _tape()
    d = ns["_pullback_depth"](high, low, close, 48)
    finite = d[np.isfinite(d)]
    assert finite.size and finite.min() >= 0.0 and finite.max() <= 1.0


def test_session_boundary_reversal_fires_only_on_boundary_hours():
    ns = _helpers()
    # hourly-ish ts across two days; z-score forced above threshold
    ts = np.arange(0, 200) * 3600
    front = np.full(ts.size, 3.0)
    mask = ns["_session_boundary_reversal"](ts, front, 2.0)
    hours = (ts % 86400) // 3600
    assert mask.any()
    assert set(np.unique(hours[mask])).issubset({0, 8, 16, 21})
    # below threshold -> nothing
    assert not ns["_session_boundary_reversal"](ts, np.full(ts.size, 1.0), 2.0).any()


@pytest.mark.parametrize("mode", ["scale", "zero", "shuffle"])
@pytest.mark.parametrize("t", [300, 600, 1100])
def test_gross_edge_nodes_never_leak_the_future(mode, t):
    rng = np.random.default_rng(999)
    n = 1400
    high, low, close = _tape(n=n, vol=0.3, seed=5)
    ts = (1_700_000_000 + np.arange(n) * 900).astype("int64")
    ns = _helpers()
    z = ns["_zscore"](close, 40)
    base = (
        np.asarray(ns["_vol_displacement"](close, high, low, 96), dtype=float),
        np.asarray(ns["_pullback_depth"](high, low, close, 48), dtype=float),
        np.asarray(ns["_session_boundary_reversal"](ts, z, 2.0), dtype=bool),
    )
    h2, l2, c2, t2, z2 = high.copy(), low.copy(), close.copy(), ts.copy(), z.copy()
    seg = slice(t + 1, n)
    if mode == "scale":
        h2[seg] = h2[seg] * 3.0 + 1000.0
        l2[seg] = l2[seg] * 3.0 + 1000.0
        c2[seg] = c2[seg] * 3.0 + 1000.0
        z2[seg] = z2[seg] * 3.0
    elif mode == "zero":
        h2[seg] = 0.0
        l2[seg] = 0.0
        c2[seg] = 0.0
        z2[seg] = 0.0
    else:
        h2[seg] = rng.permutation(h2[seg])
        l2[seg] = rng.permutation(l2[seg])
        c2[seg] = rng.permutation(c2[seg])
        z2[seg] = rng.permutation(z2[seg])
    mut = (
        np.asarray(ns["_vol_displacement"](c2, h2, l2, 96), dtype=float),
        np.asarray(ns["_pullback_depth"](h2, l2, c2, 48), dtype=float),
        np.asarray(ns["_session_boundary_reversal"](t2, z2, 2.0), dtype=bool),
    )
    for b, m in zip(base, mut):
        assert np.array_equal(b[: t + 1], m[: t + 1], equal_nan=True), (
            f"gross-edge node leaked future at t={t} mode={mode!r}")


# ---------------------------------------------------------------------------
# The frontier GRID.
# ---------------------------------------------------------------------------
def test_frontier_plan_is_the_full_grid():
    plan = s5.frontier_plan()
    assert len(plan) == len(s5.BASE_EVENTS) * len(s5.SPACING_LADDER)
    assert len(plan) == 20
    for name, concept, prog in plan:
        assert concept == f"frontier:{name}"
        assert static_gate.check_source(g.emit_python(prog)).ok


def test_frontier_curve_is_monotone_on_a_synthetic_frontier():
    pts = [
        {"entries_per_month": 10.0, "paid_multiple": 0.1, "gross_r": 5, "net_r": -5,
         "concept": "a"},
        {"entries_per_month": 1.0, "paid_multiple": 0.7, "gross_r": 20, "net_r": -8,
         "concept": "b"},
        {"entries_per_month": 0.1, "paid_multiple": 3.5, "gross_r": 100, "net_r": 70,
         "concept": "c"},
    ]
    c = s5.frontier_curve(pts)
    assert [p["concept"] for p in c["points"]] == ["a", "b", "c"]  # descending freq
    assert c["crosses_bar"] is True
    assert c["best_paid_multiple"] == 3.5
    assert c["monotone_steps"]["decreasing"] == 0
    assert c["bar"] == law.FRICTION_MULTIPLE


def test_frontier_curve_reports_no_cross_when_below_bar():
    pts = [{"entries_per_month": f, "paid_multiple": 0.5, "gross_r": 1, "net_r": -1,
            "concept": str(f)} for f in (5.0, 1.0, 0.2)]
    c = s5.frontier_curve(pts)
    assert c["crosses_bar"] is False
    assert c["crossed_points"] == []


def test_entries_per_month_is_a_frequency():
    # one year of M15 tape, 12 round-1 trades -> ~1/month
    one_year = 365.0 * 86400.0
    assert s5.entries_per_month(12, one_year) == pytest.approx(1.0, abs=0.05)
    assert s5.entries_per_month(5, 0.0) is None
