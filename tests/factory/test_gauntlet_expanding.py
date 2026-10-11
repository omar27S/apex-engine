"""R77 — THE EXPANDING GAUNTLET (the moving unseen exam)."""

from __future__ import annotations

from itertools import combinations

import pytest

from app.factory import gauntlet as g


def test_pool_is_32_sealed_seeds_disjoint_from_seen():
    assert len(g.UNSEEN_POOL) == 32
    assert len(set(g.UNSEEN_POOL)) == 32
    # The seen selection seeds (0,1,2) must never be in the unseen exam pool.
    assert not (set((0, 1, 2)) & set(g.UNSEEN_POOL))
    assert g.DRAWS_PER_VERDICT == 3
    assert g.ROLLING_WINDOW == 20


def test_pool_digest_is_stable():
    assert g.pool_digest() == g.pool_digest(g.UNSEEN_POOL)
    assert len(g.pool_digest()) == 64


def test_draw_is_distinct_and_sorted():
    for i in range(50):
        seeds = g.draw_seeds(i)
        assert len(seeds) == 3
        assert len(set(seeds)) == 3
        assert list(seeds) == sorted(seeds)
        assert all(s in g.UNSEEN_POOL for s in seeds)


def test_draw_is_deterministic():
    assert g.draw_seeds(0) == g.draw_seeds(0)
    assert g.draw_schedule(5) == g.draw_schedule(5)


def test_no_triple_repeats_in_rolling_window():
    """The R77 invariant: over a long run, no drawn triple repeats within 20."""
    draws = [g.draw_seeds(i) for i in range(20000)]
    assert g.rolling_window_ok(draws, window=g.ROLLING_WINDOW)


def test_draw_visits_every_triple_before_repeating():
    combos = list(combinations(g.UNSEEN_POOL, g.DRAWS_PER_VERDICT))
    cycle = [g.draw_seeds(i) for i in range(len(combos))]
    assert len(set(cycle)) == len(combos)  # a true permutation of the subsets
    # One past the cycle is the start again.
    assert g.draw_seeds(len(combos)) == g.draw_seeds(0)


def test_draw_record_carries_the_exam_identity():
    rec = g.draw_record(3)
    assert rec["verdict_index"] == 3
    assert rec["seeds"] == list(g.draw_seeds(3))
    assert rec["pool_size"] == 32
    assert rec["draws_per_verdict"] == 3
    assert len(rec["pool_digest"]) == 64


def test_negative_index_refused():
    with pytest.raises(ValueError):
        g.draw_seeds(-1)


def test_too_small_pool_refused():
    with pytest.raises(ValueError):
        g.draw_seeds(0, pool=(1, 2))


def test_duplicate_pool_refused():
    with pytest.raises(ValueError):
        g.draw_seeds(0, pool=(1, 1, 2))


def test_resume_safety_only_the_index_matters():
    # A resumed run draws the SAME exam for the same ledger index.
    assert g.draw_seeds(7) == g.draw_seeds(7)
    sched = g.draw_schedule(10, start=5)
    assert sched == [g.draw_seeds(5 + i) for i in range(10)]
