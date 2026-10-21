"""THE GENEALOGIST'S TRIBUNAL (R126/R127) -- blood, census, brake.

Every law here is a pure-arithmetic proof: the book's ancestry rules, the
census's collision probability, the verdict's fixed thresholds, the brake's
bounded honesty.  No factory run is needed (the integration law lives in
the workflow suite); these are the organ's own nerves.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.factory import genealogist as gen


# ---------------------------------------------------------------------------
# the book's ancestry laws
# ---------------------------------------------------------------------------
def test_a_random_newborn_is_its_own_founder():
    book = gen.BloodBook()
    book.record_founder("A")
    assert book.blood_of("A") == frozenset({"A"})
    assert book.founders_seen == 1


def test_a_mutated_child_inherits_the_parents_blood_unchanged():
    book = gen.BloodBook()
    book.record_founder("A")
    blood = book.record_child("a1", ("A",))
    assert blood == frozenset({"A"})
    assert book.blood_of("a1") == frozenset({"A"})


def test_a_crossover_child_carries_the_union_of_both_parents():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    blood = book.record_child("ab", ("A", "B"))
    assert blood == frozenset({"A", "B"})


def test_union_blood_flows_down_generations():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    book.record_child("ab", ("A", "B"))
    blood = book.record_child("ab1", ("ab",))
    assert blood == frozenset({"A", "B"})


def test_an_unseen_parent_becomes_a_founder_honestly():
    """A parent absent from the book starts its own line NOW -- ancestry is
    never invented for the past (no fabricated grandfathers)."""
    book = gen.BloodBook()
    blood = book.record_child("c", ("OLD",))
    assert blood == frozenset({"OLD"})
    assert book.founders_seen == 1


def test_a_first_sighting_in_the_book_is_empty_not_a_guess():
    book = gen.BloodBook()
    assert book.blood_of("GHOST") == frozenset()
    assert not book.is_known("GHOST")


def test_record_child_with_no_parents_is_its_own_founder():
    book = gen.BloodBook()
    blood = book.record_child("fresh", ())
    assert blood == frozenset({"fresh"})


# ---------------------------------------------------------------------------
# the census arithmetic
# ---------------------------------------------------------------------------
def _toy_pool():
    """10 bodies: 6 carry only founder A, 4 carry only founder B."""
    return {
        "b1": frozenset({"A"}), "b2": frozenset({"A"}), "b3": frozenset({"A"}),
        "b4": frozenset({"A"}), "b5": frozenset({"A"}), "b6": frozenset({"A"}),
        "b7": frozenset({"B"}), "b8": frozenset({"B"}),
        "b9": frozenset({"B"}), "b10": frozenset({"B"}),
    }


def test_census_counts_the_share_of_every_founder():
    cns = gen.census(_toy_pool())
    assert cns == {"A": pytest.approx(0.6), "B": pytest.approx(0.4)}


def test_herfindahl_is_the_collision_probability():
    # 0.6^2 + 0.4^2 = 0.52 -- the chance two random bodies share a founder
    assert gen.herfindahl(gen.census(_toy_pool())) == pytest.approx(0.52)


def test_effective_population_is_one_over_h():
    assert gen.effective_population(0.52) == pytest.approx(1.0 / 0.52)


def test_effective_population_of_zero_is_infinite():
    assert gen.effective_population(0.0) == float("inf")


def test_census_shares_sum_above_one_when_children_carry_two_lines():
    """A crossover child counts for both grandfathers -- the arithmetic of
    ancestry, not a bug (2 bodies, 3 founders carried: 3 x 0.5 = 1.5)."""
    pool = {"ab": frozenset({"A", "B"}), "c": frozenset({"C"})}
    cns = gen.census(pool)
    assert sum(cns.values()) == pytest.approx(1.5)


def test_census_on_an_empty_pool_is_empty():
    assert gen.census({}) == {}


# ---------------------------------------------------------------------------
# the verdict's fixed thresholds
# ---------------------------------------------------------------------------
def test_the_verdict_thresholds_are_declared_and_fixed():
    assert gen.VERDICT_THRESHOLDS == {"concentrating": 0.25, "one_blood": 0.50}


def test_verdict_reads_the_three_skies():
    assert gen.verdict(0.10) == "diverse"
    assert gen.verdict(0.25) == "concentrating"
    assert gen.verdict(0.49) == "concentrating"
    assert gen.verdict(0.50) == "one-blood"
    assert gen.verdict(1.00) == "one-blood"


# ---------------------------------------------------------------------------
# the incest measurement
# ---------------------------------------------------------------------------
def test_sibling_matings_counts_pairs_sharing_a_founder():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    book.record_child("a1", ("A",))
    book.record_child("a2", ("A",))
    book.record_child("b1", ("B",))
    shared, total = gen.sibling_matings([("a1", "a2"), ("a1", "b1")], book)
    assert (shared, total) == (1, 2)


def test_disjoint_blood_is_not_sibling_mating():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    book.record_child("a1", ("A",))
    book.record_child("b1", ("B",))
    shared, total = gen.sibling_matings([("a1", "b1")], book)
    assert (shared, total) == (0, 1)


# ---------------------------------------------------------------------------
# R127 -- the consanguineity brake
# ---------------------------------------------------------------------------
def test_the_brake_prefers_unrelated_blood():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    book.record_child("a1", ("A",))
    book.record_child("a2", ("A",))
    book.record_child("b1", ("B",))
    rng = np.random.default_rng(7)
    # the siblings are first in the pool; the stranger must still win
    for _ in range(20):
        mate, avoided = gen.choose_mate(["a1", "a2", "b1"], "a1", book, rng)
        if avoided:
            assert mate == "b1"
            break
    else:
        pytest.fail("the brake never found the stranger in 20 seeded tries")


def test_the_brake_falls_through_when_every_candidate_is_family():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_child("a1", ("A",))
    book.record_child("a2", ("A",))
    rng = np.random.default_rng(3)
    mate, avoided = gen.choose_mate(["a1", "a2"], "a1", book, rng)
    assert mate in ("a1", "a2")
    assert avoided is False  # honest fall-through, never an invented stranger


def test_the_brake_on_an_empty_candidate_list_is_a_no_op():
    book = gen.BloodBook()
    rng = np.random.default_rng(1)
    mate, avoided = gen.choose_mate([], "solo", book, rng)
    assert (mate, avoided) == ("solo", False)


def test_the_brake_never_mates_a_body_with_itself_when_avoided():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    book.record_child("a1", ("A",))
    book.record_child("b1", ("B",))
    rng = np.random.default_rng(11)
    for _ in range(30):
        mate, avoided = gen.choose_mate(["a1", "b1"], "a1", book, rng)
        if avoided:
            assert mate != "a1"


# ---------------------------------------------------------------------------
# persistence: the book survives shifts, pruned by construction
# ---------------------------------------------------------------------------
def test_the_book_round_trips_through_disk(tmp_path: Path):
    book = gen.BloodBook(island="heart")
    book.record_founder("A")
    book.record_child("ab", ("A", "B"))
    p = tmp_path / "factory_blood_heart.json"
    assert book.save(p)
    loaded = gen.BloodBook.load(p, island="heart")
    assert loaded.island == "heart"
    assert loaded.blood_of("ab") == frozenset({"A", "B"})
    assert loaded.founders_seen == 2


def test_a_torn_book_is_a_fresh_start_never_a_crash(tmp_path: Path):
    p = tmp_path / "torn.json"
    p.write_text("{not json")
    book = gen.BloodBook.load(p)
    assert book.blood == {}
    assert book.is_known("anything") is False


def test_prune_keeps_only_the_living(tmp_path: Path):
    book = gen.BloodBook()
    for f in ("A", "B", "C"):
        book.record_founder(f)
    book.record_child("ab", ("A", "B"))
    book.record_child("cx", ("C",))
    book.prune_to({"ab", "A", "B"})  # C and cx are gone
    assert book.is_known("ab")
    assert book.is_known("A")
    assert not book.is_known("cx")
    assert not book.is_known("C")  # a founder nobody carries is memory freed


# ---------------------------------------------------------------------------
# the artifact
# ---------------------------------------------------------------------------
def test_the_artifact_speaks_the_whole_census():
    book = gen.BloodBook()
    book.record_founder("A")
    book.record_founder("B")
    book.record_child("a1", ("A",))
    book.record_child("b1", ("B",))
    births = [gen.Birth(child="a1", op="mutate", parents=("A",)),
              gen.Birth(child="b1", op="mutate", parents=("B",)),
              gen.Birth(child="ab", op="crossover", parents=("a1", "b1"))]
    art = gen.artifact(island="heart",
                       blood_map={"a1": book.blood_of("a1"),
                                  "b1": book.blood_of("b1"),
                                  "ab": book.blood_of("ab")},
                       births=births, book=book, ts=1.0)
    assert art["island"] == "heart"
    assert art["schema"] == gen.BLOOD_SCHEMA
    assert art["bodies"] == 3
    assert art["verdict"] in ("diverse", "concentrating", "one-blood")
    assert art["crossovers"] == 1
    assert art["census_top"][0]["founder"] in ("A", "B")
    assert "il sangue" in art["reading"]


def test_the_artifact_on_an_empty_pool_is_honest_not_invented():
    art = gen.artifact(island="turbo", blood_map={}, births=[],
                       book=gen.BloodBook(), ts=1.0)
    assert art["bodies"] == 0
    assert art["effective_population"] is None


def test_the_artifact_carries_the_brakes_counters():
    art = gen.artifact(island="vault", blood_map={},
                       births=[], book=gen.BloodBook(),
                       brake={"applied": True, "sibling_mates_avoided": 7,
                              "immigrants": 2})
    assert art["brake"]["sibling_mates_avoided"] == 7
    assert art["brake"]["immigrants"] == 2
