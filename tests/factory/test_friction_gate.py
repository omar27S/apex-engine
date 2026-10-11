"""R85 — the gross-to-friction gate + R86 — the mirror-window rule (Phase 7i).

Two new laws from the Baptism's lesson (tape-window artifacts): a candidate must
pay its friction 3x over, and "survivor" means the FULL tape, never a short tail.
"""

from __future__ import annotations

import math

import pytest

from app.core import law
from app.factory import staircase as st


# --- R85 sealed constant -----------------------------------------------------
def test_friction_multiple_is_sealed_at_three():
    assert law.FRICTION_MULTIPLE == 3.0


# --- R85 the verdict ---------------------------------------------------------
def test_gate_passes_a_gross_rich_friction_poor_body():
    # gross 100, friction 20 -> multiple 5.0 >= 3.0
    v = law.gross_to_friction_verdict(100.0, 80.0)
    assert v.ok and v.multiple == pytest.approx(5.0)
    assert v.friction_r == pytest.approx(20.0)


def test_gate_rejects_a_gross_rich_friction_dominated_body():
    # the friday_fade shape: gross positive, friction eats it whole
    v = law.gross_to_friction_verdict(1022.0, -2840.0)
    assert not v.ok
    assert v.multiple < law.FRICTION_MULTIPLE
    assert "below" in v.reason or "<" in v.reason


def test_gate_rejects_non_positive_gross():
    v = law.gross_to_friction_verdict(-5.0, -5.0)
    assert not v.ok and "non-positive gross" in v.reason


def test_gate_rejects_zero_friction_un_invoiced():
    # a diagnostic gross run (friction 0) carries no evidence -> refused
    v = law.gross_to_friction_verdict(50.0, 50.0)
    assert not v.ok and "zero friction" in v.reason


def test_gate_boundary_is_inclusive_at_exactly_the_multiple():
    # gross 60, friction 20 -> multiple exactly 3.0 -> passes (>=)
    assert law.gross_to_friction_verdict(60.0, 40.0).ok
    # gross 59.99, friction 20 -> 2.9995 < 3.0 -> rejected
    assert not law.gross_to_friction_verdict(59.99, 39.99).ok


# --- R85 in the staircase ----------------------------------------------------
def _evals():
    return {"screen": lambda g, s: True, "era": lambda g, s: True,
            "gauntlet": lambda g, s: True}


def test_staircase_rejects_a_friction_poor_body_at_round_one():
    pool = ["rich", "poor"]
    calls = {"screen": [], "era": []}

    def screen(g, spec):
        calls["screen"].append(g)
        return True

    def era(g, spec):
        calls["era"].append(g)
        return True

    def gate(g):
        if g == "poor":
            # gross 1000, friction 3000 -> multiple 0.33 -> reject
            return st.FrictionGate(gross_r=1000.0, friction_r=3000.0)
        # gross 1000, friction 100 -> multiple 10 -> pass
        return st.FrictionGate(gross_r=1000.0, friction_r=100.0)

    ev = {"screen": screen, "era": era, "gauntlet": era}
    res = st.screen(pool, ev, friction_gate=gate)
    # the poor body never reached even the cheap screen
    assert "poor" not in calls["screen"]
    assert "poor" not in calls["era"]
    assert res.survivors == ["rich"]
    assert res.friction_rejected == 1
    assert any("friction" in k for k in res.friction_reasons)


def test_staircase_gate_is_reported_not_silent():
    res = st.screen(["a"], _evals(),
                    friction_gate=lambda g: st.FrictionGate(gross_r=1.0, friction_r=100.0))
    d = res.to_dict()
    assert d["friction_gate"]["rejected"] == 1
    assert d["friction_gate"]["multiple"] == law.FRICTION_MULTIPLE
    assert d["friction_gate"]["reasons"]  # an explanation, never a silent kill


def test_staircase_gate_none_means_do_not_block():
    # a gate that returns None (no data) never blocks
    res = st.screen(["a", "b"], _evals(), friction_gate=lambda g: None)
    assert res.survivors == ["a", "b"] and res.friction_rejected == 0


def test_staircase_without_gate_is_unchanged():
    res = st.screen(["a", "b"], _evals())
    assert res.survivors == ["a", "b"] and res.friction_rejected == 0


def test_property_friction_poor_bodies_are_all_culled_before_round_two():
    """Property — whichever body has gross < 3x friction never reaches round 2."""
    poor = [("poor", float(i), float(i) + 10 * i) for i in (100, 500, 900)]
    rich = [("rich", 1000.0, 100.0)]
    pool = [name for name, _, _ in poor] + [name for name, _, _ in rich]
    gate_map = {name: st.FrictionGate(gross_r=g, friction_r=f) for name, g, f in poor + rich}
    calls2 = []

    def era(g, spec):
        calls2.append(g)
        return True

    res = st.screen(pool, {"screen": lambda g, s: True, "era": era, "gauntlet": era},
                    friction_gate=lambda g: gate_map[g])
    assert res.survivors == ["rich"]
    assert set(calls2) == {"rich"}   # every round-2 call is the survivor only
    assert res.friction_rejected == len(poor)


# --- R86 mirror-window rule --------------------------------------------------
def test_short_window_rows_default_is_the_legacy_tail():
    assert law.MIRROR_SHORT_WINDOW_ROWS == 20000


def test_mirror_verdict_defines_survivor_as_full_tape_positive():
    v = law.mirror_window_verdict(full_positive=True, short_positive=False)
    assert v["survivor"] is True and v["window_artifact"] is False


def test_mirror_verdict_flags_a_window_artifact():
    # the friday_fade shape: alive on the short tail, dead on the full tape
    v = law.mirror_window_verdict(full_positive=False, short_positive=True)
    assert v["survivor"] is False
    assert v["window_artifact"] is True
    assert v["full_tape_positive"] is False and v["short_window_positive"] is True
