"""R90/R91 (Phase 7l) — THE COUSIN HUNT: the winner's family + the reducers.

Phase 7l hunts the family of ``f_rev_gap3072`` (Session 5.0's first paying body:
7.48x, but 1/20 cross-pair). These tests pin, without a tape:

* the deterministic GRIDS — the relatives (one lever at a time), the frequency
  push, and the one-gene anatomy — each a valid static-gate body;
* the winner BODY reproduces Session 5.0's gene vector (gap 3072, z(40)|1.5,
  rsi gene band) and its ablation toggles flip exactly one lever;
* the pure REDUCERS — ``width_of_zone`` (band vs needle) and ``frequency_cliff``
  (where the multiple drops below the bar) — so the AGENTS.md verdict is
  reproducible without a tape.
"""

from __future__ import annotations

import pytest

from app.core import law
from app.pyramid.author import author2 as a2
from app.pyramid.author import grammar as g
from app.pyramid.sandbox import static_gate
from tools import author_session_6 as s6


# ---------------------------------------------------------------------------
# The grids.
# ---------------------------------------------------------------------------
def test_relatives_plan_is_the_deliberate_family_grid():
    plan = s6.relatives_plan()
    assert len(plan) >= 30  # ~40 bodies; a few levers share a value
    for name, prog, over in plan:
        assert prog.concept.startswith("cousin:")
        assert static_gate.check_source(g.emit_python(prog)).ok
        assert isinstance(over, dict)


def test_frequency_push_plan_spans_smaller_gaps_and_a_session_filter():
    plan = s6.frequency_push_plan()
    assert len(plan) == len(s6.PUSH_GAPS) * len(s6.PUSH_SESSIONS)
    for name, prog, _ in plan:
        assert static_gate.check_source(g.emit_python(prog)).ok


def test_anatomy_plan_is_one_lever_at_a_time():
    plan = s6.anatomy_plan()
    assert plan[0][0] == "w_winner"
    names = [n for n, _, _ in plan]
    assert {"w_no_gap", "w_z_off", "w_rsi_off", "w_gap2048"} <= set(names)
    for _, prog, _ in plan:
        assert static_gate.check_source(g.emit_python(prog)).ok


# ---------------------------------------------------------------------------
# The winner body + its ablation levers.
# ---------------------------------------------------------------------------
def _kinds(tree) -> list[str]:
    out = [tree.kind]
    for c in tree.children:
        out.extend(_kinds(c))
    return out


def test_winner_body_reproduces_the_session_5_gene_vector():
    prog = s6._body(concept="anatomy:winner")
    assert prog.long.kind == "min_gap_bars" and int(prog.long.params[0]) == s6.WINNER_GAP
    assert prog.long.children[0].kind == "and"
    assert "zscore" in _kinds(prog.long) and "rsi" in _kinds(prog.long)


def test_gap_lever_moves_only_the_spacing():
    a = s6._body(gap=2048, concept="a")
    b = s6._body(gap=4096, concept="b")
    # the event half is identical; only the gap param differs
    assert _kinds(a.long) == _kinds(b.long)
    assert int(a.long.params[0]) == 2048 and int(b.long.params[0]) == 4096
    assert a.long.children == b.long.children


def test_z_off_removes_the_stretch_gate():
    assert "zscore" in _kinds(s6._body(z_on=True, concept="a").long)
    assert "zscore" not in _kinds(s6._body(z_on=False, concept="b").long)


def test_rsi_off_removes_the_momentum_gate():
    assert "rsi" in _kinds(s6._body(rsi_on=True, concept="a").long)
    assert "rsi" not in _kinds(s6._body(rsi_on=False, concept="b").long)


def test_direction_filter_silences_one_side():
    long_only = s6._body(direction="long", concept="l")
    short_only = s6._body(direction="short", concept="s")
    # the short tree of a long-only body ANDs an always-false gate (ATR < -1).
    assert short_only.short.kind == "min_gap_bars"
    assert long_only.long.kind == "min_gap_bars"


# ---------------------------------------------------------------------------
# The pure reducers.
# ---------------------------------------------------------------------------
def test_width_of_zone_reports_a_needle():
    pts = [
        {"name": "a", "paid_multiple": 0.5, "gross_r": 1, "gap": 2048,
         "entries_per_month": 1.0},
        {"name": "b", "paid_multiple": 7.5, "gross_r": 20, "gap": 3072,
         "entries_per_month": 0.18},
    ]
    w = s6.width_of_zone(pts, law.FRICTION_MULTIPLE)
    assert w["n_crossers"] == 1 and w["verdict"] == "needle"
    assert w["gap_span"] == [3072, 3072]


def test_width_of_zone_reports_a_band():
    pts = [
        {"name": f"g{g}", "paid_multiple": 4.0, "gross_r": 20, "gap": g,
         "entries_per_month": 0.2}
        for g in (2048, 3072, 4096)
    ]
    w = s6.width_of_zone(pts, law.FRICTION_MULTIPLE)
    assert w["verdict"] == "band" and w["gap_span"] == [2048, 4096]


def test_width_of_zone_ignores_non_positive_gross():
    pts = [{"name": "x", "paid_multiple": 9.0, "gross_r": -1, "gap": 3072,
            "entries_per_month": 0.2}]
    assert s6.width_of_zone(pts, law.FRICTION_MULTIPLE)["n_crossers"] == 0


def test_frequency_cliff_finds_the_highest_clearing_frequency():
    pts = [
        {"name": "fast", "entries_per_month": 5.0, "paid_multiple": 0.4},
        {"name": "mid", "entries_per_month": 1.0, "paid_multiple": 3.2},
        {"name": "slow", "entries_per_month": 0.1, "paid_multiple": 7.0},
    ]
    c = s6.frequency_cliff(pts, law.FRICTION_MULTIPLE)
    assert c["highest_clearing_epm"] == 1.0
    assert c["first_below"]["name"] == "fast"  # highest frequency, below bar
    assert c["best"]["name"] == "slow"
    assert c["last_positive"]["name"] == "fast"


def test_frequency_cliff_reports_no_clearing_body():
    pts = [{"name": "a", "entries_per_month": 3.0, "paid_multiple": 0.1}]
    c = s6.frequency_cliff(pts, law.FRICTION_MULTIPLE)
    assert c["highest_clearing_epm"] is None
    assert c["first_below"]["name"] == "a"
    assert c["last_positive"]["name"] == "a"  # 0.1 > 0


def test_carrier_overrides_are_one_gene():
    base = s6._carrier().to_dict()
    rr3 = s6._carrier(target_rr=3.0).to_dict()
    diffs = [k for k in base if base[k] != rr3[k]]
    assert diffs == ["target_rr"]
