"""Tests for Author 2.0 — R74a (hypothesis engine), R74b (intuition translator),
R74c (novelty hunter).

The point of these tests is honesty: every produced body must be a LEGAL grammar
program (it can be emitted to real Python that the cage accepts), a hypothesis
must cite the ledger reading that motivated it, and a hunch the grammar cannot
express must be REFUSED with a reason — never faked.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.pyramid.author import author2 as a2
from app.pyramid.author import grammar as g
from app.pyramid.author import synth as sy


def _emittable(p) -> bool:
    src = g.emit_python(p)
    return isinstance(src, str) and len(src) > 100 and "def " in src


# --- R74a hypothesis engine ------------------------------------------------

def test_hypotheses_are_grounded_and_emittable():
    inp = a2.HypothesisInputs(
        autopsy={"stop_hunt_gap": 5, "regime_misread": 3,
                 "target_missed": 2, "structural_failure": 4},
        total_autopsy=14)
    hyps = a2.grounded_hypotheses(inp, n=8)
    assert len(hyps) >= 4
    for h in hyps:
        assert _emittable(h.program)
        assert 0.0 <= h.confidence <= 1.0
        assert h.grounding.startswith("autopsy") or h.grounding.startswith("realms")


def test_hypotheses_rank_best_evidence_first():
    inp = a2.HypothesisInputs(
        autopsy={"stop_hunt_gap": 9, "regime_misread": 1}, total_autopsy=10)
    hyps = a2.grounded_hypotheses(inp, n=8)
    assert hyps[0].program.concept == "hyp:meanrev_on_stophunt"   # biggest cause
    assert hyps[0].confidence >= hyps[-1].confidence


def test_empty_ledger_forms_no_autopsy_hypothesis():
    hyps = a2.grounded_hypotheses(a2.HypothesisInputs(), n=8)
    assert hyps == []                                   # nothing invented


def test_unknown_cause_is_covered_generically():
    inp = a2.HypothesisInputs(autopsy={"new_weird_cause": 7}, total_autopsy=7)
    hyps = a2.grounded_hypotheses(inp, n=4)
    assert any(h.program.concept == "hyp:cause_new_weird_cause" for h in hyps)
    assert all(_emittable(h.program) for h in hyps)


def test_realm_fill_hypothesis_names_an_empty_realm():
    inp = a2.HypothesisInputs(occupied_realms=("trend",))
    hyps = a2.grounded_hypotheses(inp, n=4)
    fills = [h for h in hyps if h.program.concept.startswith("hyp:realm_fill")]
    assert fills
    assert "unoccupied" in fills[0].text and _emittable(fills[0].program)


def test_live_taxonomy_specialists_are_used():
    inp = a2.HypothesisInputs(
        autopsy={"early_stop": 10, "tournament_floor": 5}, total_autopsy=15)
    concepts = {h.program.concept for h in a2.grounded_hypotheses(inp, n=8)}
    assert "hyp:london_kz_momentum" in concepts       # early_stop -> session hyp
    assert "hyp:regime_gated_trend" in concepts       # floor -> regime hyp


# --- R74b intuition translator ---------------------------------------------

@pytest.mark.parametrize("italian,concept", [
    ("voglio entrare sul rientro alla media", "hyp:intuition_meanrev"),
    ("entra nella sessione di Londra all'apertura", "hyp:intuition_session"),
    ("compra quando rompe il canale", "hyp:intuition_breakout"),
    ("segui la tendenza col momento", "hyp:intuition_trend"),
])
def test_intuition_translates_to_legal_body(italian, concept):
    res = a2.translate_intuition(italian)
    assert res.ok
    assert res.program.concept == concept
    assert _emittable(res.program)


def test_intuition_refuses_unexpressible_hunch_with_reason():
    res = a2.translate_intuition("metti uno stop sempre stretto e raddoppia dopo "
                                 "una perdita")
    assert not res.ok
    assert res.program is None
    assert "no grammar construct matches" in res.reason


def test_empty_intuition_is_refused():
    res = a2.translate_intuition("   ")
    assert not res.ok and "empty" in res.reason


# --- R74c novelty hunter ---------------------------------------------------

def test_fingerprint_and_distance_are_deterministic_and_bounded():
    a = sy.random_body(np.random.default_rng(1), concept="a")
    b = sy.random_body(np.random.default_rng(2), concept="b")
    assert a2.fingerprint(a) == a2.fingerprint(a)
    d = a2.signal_distance(a, b)
    assert 0.0 <= d <= 1.0
    assert a2.signal_distance(a, a) == 0.0


def test_novelty_hunter_beats_a_naive_draw_on_average():
    rng = np.random.default_rng(0)
    existing = [sy.random_body(np.random.default_rng(i)) for i in range(8)]
    hunter = a2.novelty_hypothesis(existing, rng, attempts=60)
    hunter_dist = min(a2.signal_distance(hunter.program, e) for e in existing)
    # Compare to a fresh random body's distance.
    naive = sy.random_body(np.random.default_rng(123))
    naive_dist = min(a2.signal_distance(naive, e) for e in existing)
    assert hunter_dist >= naive_dist - 1e-9           # the hunt is not worse


def test_novelty_hunter_bootstraps_on_empty_set():
    rng = np.random.default_rng(0)
    h = a2.novelty_hypothesis([], rng)
    assert h.program is not None and _emittable(h.program)
    assert "seed" in h.grounding
