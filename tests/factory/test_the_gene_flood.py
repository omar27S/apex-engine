"""R143 -- THE GENE FLOOD: a desert does not heal one immigrant at a time.

The measured collapse (every island one-blood, every night, Ne 0.48..0.82,
incest 105-142/216, learning acceleration -171%) was met by R127's brake with
FOUR founders a generation -- a spice against a desert. These tests pin the
flood's law: the streak (a persistent blood measurement, not a mood), the wave
(a bounded share of the population, family-spread), the forced-family draw
(genes inside the law, family the caller's), and the artifact that carries the
streak across runs. The red lines are pinned too: the wave never touches the
population count, the pairs, or any sizing rule -- founders replace children
exactly as the drip's immigrants always have.
"""

from __future__ import annotations

import math

import numpy as np

from app.factory import genealogist as gene
from app.quant import breeding


def _rng(seed: int = 7) -> np.random.Generator:
    return np.random.default_rng(seed)


# ---------------------------------------------------------------------------
# the streak -- a measurement, not a mood
# ---------------------------------------------------------------------------

def test_the_streak_rises_while_the_blood_is_one_family():
    assert gene.blood_streak(0, 0.60) == 1
    assert gene.blood_streak(1, 0.60) == 2
    assert gene.blood_streak(2, 0.60) == 3


def test_the_streak_resets_the_moment_the_blood_diversifies():
    assert gene.blood_streak(5, 0.49) == 0   # concentrating is not one-blood
    assert gene.blood_streak(5, 0.10) == 0   # diverse
    assert gene.blood_streak(5, 0.00) == 0


# ---------------------------------------------------------------------------
# the wave -- a drip, then a bounded flood
# ---------------------------------------------------------------------------

def test_no_streak_no_founders():
    assert gene.flood_wave(0, 240) == 0
    assert gene.flood_wave(-1, 240) == 0
    assert gene.flood_wave(1, 0) == 0


def test_the_drip_stays_a_spice():
    """Streaks of one or two get exactly R127's four founders, no more."""
    assert gene.flood_wave(1, 240) == gene.BRAKE_IMMIGRANTS
    assert gene.flood_wave(2, 240) == gene.BRAKE_IMMIGRANTS


def test_the_streak_opens_the_wave():
    """At FLOOD_STAGNATION the drip becomes a wave: a 15% share of the pool."""
    wave = gene.flood_wave(gene.FLOOD_STAGNATION, 240)
    assert wave == math.ceil(gene.FLOOD_MAX_SHARE * 240)
    assert wave > gene.BRAKE_IMMIGRANTS


def test_the_wave_is_bounded_however_long_the_desert():
    """A hundred-generation streak never buys more than the ceiling."""
    for streak in (gene.FLOOD_STAGNATION, 10, 99):
        assert gene.flood_wave(streak, 240) <= math.ceil(
            gene.FLOOD_MAX_SHARE * 240)


def test_the_wave_never_takes_the_majority():
    """The red line: bred children + elites always keep the majority of the
    pool, at any population the factory runs."""
    for pop in (60, 120, 240, 720):
        wave = gene.flood_wave(99, pop)
        assert 2 * wave < pop


# ---------------------------------------------------------------------------
# the spread -- a wave of one family would be a new monoculture
# ---------------------------------------------------------------------------

def test_a_small_wave_touches_every_family_once():
    table = [f"fam_{i}" for i in range(44)]
    wave = gene.spread_families(36, table, _rng())
    assert len(wave) == 36
    assert len(set(wave)) == 36          # 36 founders over 44 families: all distinct
    assert set(wave) <= set(table)


def test_a_big_wave_is_evenly_spread():
    table = [f"fam_{i}" for i in range(10)]
    wave = gene.spread_families(60, table, _rng())
    assert len(wave) == 60
    counts = {f: wave.count(f) for f in set(wave)}
    assert set(counts.values()) == {6}   # exactly even
    assert max(counts.values()) <= math.ceil(60 / 10)


def test_the_spread_refuses_empty_tables():
    assert gene.spread_families(10, [], _rng()) == []
    assert gene.spread_families(0, ["a"], _rng()) == []
    assert gene.spread_families(5, ["", "  "], _rng()) == []


def test_the_spreads_rotation_is_not_alphabetical_law():
    """The offset is drawn: the wave is a rotated slice of the sorted table --
    each seed picks a different window, every window is all-distinct families."""
    table = [f"fam_{i:02d}" for i in range(20)]
    for seed in (1, 2, 3):
        w = gene.spread_families(8, table, _rng(seed))
        assert len(w) == 8 and len(set(w)) == 8      # a small wave: all distinct
        assert set(w) <= set(table)                  # nothing invented
        # the wave is 8 CONSECUTIVE families of the rotated sorted table
        start = table.index(w[0])
        expected = [table[(start + i) % len(table)] for i in range(8)]
        assert w == expected
    firsts = {gene.spread_families(8, table, _rng(s))[0] for s in range(20)}
    assert len(firsts) > 1               # the start rotates, it is not fixed


# ---------------------------------------------------------------------------
# the forced-family founder -- genes inside the law, family the caller's
# ---------------------------------------------------------------------------

def test_a_forced_family_genome_is_drawn_inside_the_law():
    rng = _rng()
    for _ in range(8):
        g = breeding.random_genome(rng, family="mean_reversion")
        assert g.family == "mean_reversion"
        assert g.target_rr >= 2.5          # the Constitution's floor holds


def test_the_family_parameter_leaves_the_weighted_draw_untouched():
    """family=None is the classic draw: a family from the table, genes in law."""
    rng = _rng()
    table = set(breeding.eligible_families())
    for _ in range(8):
        g = breeding.random_genome(rng)
        assert g.family in table
        assert g.target_rr >= 2.5


def test_the_eligible_table_is_the_draws_own():
    """The flood does not invent families: it spreads across what the weighted
    draw itself samples; the concrete table forbids the ensemble family."""
    table = breeding.eligible_families()
    assert len(table) >= 20
    assert "mean_reversion" in table
    concrete = breeding.eligible_families(concrete=True)
    assert breeding.ENSEMBLE_FAMILY not in concrete


# ---------------------------------------------------------------------------
# the artifact -- the streak crosses runs
# ---------------------------------------------------------------------------

def test_the_artifact_carries_the_streak():
    book = gene.BloodBook(island="test")
    a = gene.artifact(island="test", blood_map={}, births=[], book=book,
                      brake={"applied": True}, brake_streak=3)
    assert a["brake_streak"] == 3
    b = gene.artifact(island="test", blood_map={}, births=[], book=book)
    assert b["brake_streak"] == 0
