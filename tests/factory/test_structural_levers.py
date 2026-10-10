"""Tests for R67 (slices), R68 (islands), R69 (staircase), R70 (result memory)."""

from __future__ import annotations

import pytest

from app.factory import islands as islands_mod
from app.factory import result_memory as rm_mod
from app.factory import slices as slices_mod
from app.factory import staircase as staircase_mod
from app.factory.islands import MigrationError
from app.factory.slices import SliceError
from app.factory.staircase import StaircaseError, RoundSpec


PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "EURGBP", "AUDJPY", "CADJPY"]


# --- R67 slices ------------------------------------------------------------

def test_partition_is_balanced_disjoint_and_canonical():
    groups = slices_mod.partition_pairs(PAIRS, 3)
    flat = [p for g in groups for p in g]
    assert len(groups) == 3
    assert sorted(flat) == sorted(PAIRS)          # disjoint + complete
    assert all(len(g) == 2 for g in groups)       # balanced


def test_partition_is_deterministic_under_order():
    a = slices_mod.partition_pairs(["USDJPY", "EURUSD", "GBPUSD"], 2)
    b = slices_mod.partition_pairs(["EURUSD", "GBPUSD", "USDJPY"], 2)
    assert a == b


def test_partition_fail_closed_when_more_slices_than_pairs():
    with pytest.raises(SliceError):
        slices_mod.partition_pairs(["EURUSD", "GBPUSD"], 3)
    with pytest.raises(SliceError):
        slices_mod.partition_pairs(PAIRS, 0)


def test_slice_seed_is_deterministic_and_distinct():
    s = slices_mod.make_slices(PAIRS, 3, base_seed=7, salt="burst")
    assert [x.seed for x in s] == [x.seed for x in
                                   slices_mod.make_slices(PAIRS, 3, 7, "burst")]
    assert len({x.seed for x in s}) == 3          # distinct per slice
    assert s[0].seed != slices_mod.make_slices(PAIRS, 3, 8, "burst")[0].seed


def test_fuse_dedups_by_signature_keeping_best_and_ranks():
    rows = {
        0: [{"signature": "a", "wilson_lb": 0.3, "net_r": 1.0},
            {"signature": "b", "wilson_lb": 0.5, "net_r": 2.0}],
        1: [{"signature": "a", "wilson_lb": 0.4, "net_r": 1.5}],  # 'a' better here
    }
    fused = slices_mod.fuse_leaderboards(rows)
    assert len(fused) == 2
    assert fused[0]["signature"] == "b"           # highest lb first
    a = next(r for r in fused if r["signature"] == "a")
    assert a["wilson_lb"] == 0.4                   # best occurrence kept


def test_fuse_certificate_summary_is_deterministic():
    s = slices_mod.make_slices(PAIRS, 3, 0, "x")
    rows = {x.index: [] for x in s}
    a = slices_mod.fuse_certificate_summary(s, rows, [])
    b = slices_mod.fuse_certificate_summary(s, rows, [])
    assert a["slice_set_digest"] == b["slice_set_digest"]


# --- R68 islands -----------------------------------------------------------

def test_migration_roundtrip_and_digest():
    champs = [{"genome": {"family": "trend_pullback"}, "family": "trend_pullback",
               "wilson_lb": 0.4, "net_r": 2.0}]
    m = islands_mod.build_migration("heart", 3, champs)
    payload = m.to_dict()
    back = islands_mod.verify_migration(payload)
    assert back.source_island == "heart"
    assert back.digest == m.digest


def test_migration_refuses_empty_and_missing_genome():
    with pytest.raises(MigrationError):
        islands_mod.build_migration("heart", 0, [])
    with pytest.raises(MigrationError):
        islands_mod.build_migration("heart", 0, [{"family": "x"}])


def test_migration_refuses_tampered_payload():
    champs = [{"genome": {"family": "trend_pullback"}}]
    payload = islands_mod.build_migration("heart", 1, champs).to_dict()
    payload["champions"][0]["family"] = "mean_reversion"   # tamper after sealing
    with pytest.raises(MigrationError):
        islands_mod.verify_migration(payload)


def test_merge_migrants_dedups_by_signature():
    from app.quant.genome import StrategyGenome
    local = [StrategyGenome.from_dict({"family": "trend_pullback"})]
    dup = {"genome": local[0].to_dict()}
    new = {"genome": {"family": "mean_reversion"}}
    merged = islands_mod.merge_migrants(local, [dup, new])
    assert len(merged) == 2                        # dup skipped, new added


# --- R69 staircase ---------------------------------------------------------

def test_staircase_is_cheapest_first():
    names = [r.name for r in staircase_mod.STAIRCASE_ROUNDS]
    assert names == ["screen", "era", "gauntlet"]
    assert staircase_mod.STAIRCASE_ROUNDS[0].pairs == 1


def test_staircase_screens_progressively_and_counts_honestly():
    pool = list(range(20))
    calls = {"screen": 0, "era": 0, "gauntlet": 0}

    def screen(g, spec):
        calls["screen"] += 1
        return g % 2 == 0        # 10 survive

    def era(g, spec):
        calls["era"] += 1
        return g % 4 == 0        # 5 survive

    def gauntlet(g, spec):
        calls["gauntlet"] += 1
        return g % 8 == 0        # 2 survive

    res = staircase_mod.screen(pool, {"screen": screen, "era": era,
                                      "gauntlet": gauntlet})
    assert res.entered == {"screen": 20, "era": 10, "gauntlet": 5}
    assert res.passed == {"screen": 10, "era": 5, "gauntlet": 3}
    assert res.survivors == [0, 8, 16]
    assert calls == {"screen": 20, "era": 10, "gauntlet": 5}  # dead never re-run


def test_staircase_fail_closed_on_missing_evaluator():
    with pytest.raises(StaircaseError):
        staircase_mod.screen([1, 2, 3], {"screen": lambda g, s: True})


def test_staircase_stops_when_pool_empties():
    res = staircase_mod.screen([1, 2, 3],
                               {"screen": lambda g, s: False,
                                "era": lambda g, s: True,
                                "gauntlet": lambda g, s: True})
    assert res.rounds_run == 1
    assert res.survivors == []


# --- R70 result memory -----------------------------------------------------

def test_result_memory_hit_miss_and_copy_isolation():
    mem = rm_mod.ResultMemory()
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"rows": [1, 2, 3]}

    key = rm_mod.result_key("sig", 0, "EURUSD")
    a = mem.get_or_compute(key, compute)
    a["rows"].append(999)                          # mutate the returned copy
    b = mem.get_or_compute(key, compute)           # must be a fresh copy
    assert calls["n"] == 1                         # computed once
    assert b["rows"] == [1, 2, 3]
    stats = mem.stats()
    assert stats["hits"] == 1 and stats["misses"] == 1
    assert stats["reuse_ratio"] == 0.5


def test_result_key_changes_with_world_and_slice():
    a = rm_mod.result_key("sig", 0, "EURUSD")
    assert a != rm_mod.result_key("sig", 1, "EURUSD")
    assert a != rm_mod.result_key("sig", 0, "GBPUSD")
    assert a != rm_mod.result_key("other", 0, "EURUSD")
