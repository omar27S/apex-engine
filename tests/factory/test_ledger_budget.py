"""Tests for R66 (factory ledger) and R75 (turbo budget law)."""

from __future__ import annotations

import json

import pytest

from app.factory import budget as budget_mod
from app.factory import ledger as ledger_mod
from app.factory.budget import TurboBudget, TurboBudgetExceeded
from app.factory.ledger import FactoryRecord, LedgerError


# --- R66 ledger ------------------------------------------------------------

def test_record_validated_refuses_missing_field():
    rec = FactoryRecord(date="2026-10-10", machine="heart", job="",
                        trials=1, machine_seconds=1.0)
    with pytest.raises(LedgerError):
        rec.validated()


def test_record_refuses_unknown_machine():
    rec = FactoryRecord(date="2026-10-10", machine="laptop", job="x",
                        trials=1, machine_seconds=1.0)
    with pytest.raises(LedgerError):
        rec.validated()


def test_record_refuses_negative_and_nonfinite():
    with pytest.raises(LedgerError):
        FactoryRecord(date="2026-10-10", machine="heart", job="x", trials=1,
                      machine_seconds=-1.0).validated()
    with pytest.raises(LedgerError):
        FactoryRecord(date="2026-10-10", machine="heart", job="x", trials=1,
                      machine_seconds=float("nan")).validated()


def test_record_refuses_bad_date():
    with pytest.raises(LedgerError):
        FactoryRecord(date="10/10/2026", machine="heart", job="x", trials=1,
                      machine_seconds=1.0).validated()


def test_append_load_roundtrip_and_aggregate(tmp_path):
    path = tmp_path / "l.jsonl"
    ledger_mod.append([], FactoryRecord(date="2026-10-10", machine="heart",
                                        job="factory-shift", trials=100,
                                        machine_seconds=3600.0,
                                        cache_hits=10, cache_misses=90,
                                        realms_occupied=3), path)
    ledger_mod.append([], FactoryRecord(date="2026-10-10", machine="turbo",
                                        job="burst", trials=240,
                                        machine_seconds=7200.0,
                                        cache_hits=5, cache_misses=235,
                                        realms_occupied=7), path)
    ledger_mod.append([], FactoryRecord(date="2026-10-11", machine="vault",
                                        job="fuse", trials=0,
                                        machine_seconds=60.0), path)
    records = ledger_mod.load(path)
    assert len(records) == 3
    assert ledger_mod.total_trials(records) == 340
    agg = ledger_mod.aggregate_daily(records)
    assert agg["2026-10-10"]["trials"] == 340
    assert agg["2026-10-10"]["jobs"] == 2
    assert agg["2026-10-10"]["realms_occupied_max"] == 7
    assert agg["2026-10-10"]["machines"] == {"heart": 1, "turbo": 1}
    assert agg["2026-10-11"]["trials"] == 0


def test_load_skips_malformed_lines(tmp_path):
    path = tmp_path / "l.jsonl"
    path.write_text('{"date":"2026-10-10","machine":"heart","job":"x",'
                    '"trials":1,"machine_seconds":1.0}\n'
                    'not json\n'
                    '{"date":"2026-10-10","machine":"heart"}\n')
    records = ledger_mod.load(path)
    assert len(records) == 1


def test_render_last_days_is_bounded_and_labelled(tmp_path):
    path = tmp_path / "l.jsonl"
    for day in range(1, 6):
        ledger_mod.append([], FactoryRecord(
            date=f"2026-10-0{day}", machine="heart", job="j", trials=day,
            machine_seconds=100.0), path)
    text = ledger_mod.render_last_days(ledger_mod.load(path), days=3)
    assert "last 3 day(s)" in text
    assert "TOTAL" in text
    assert "2026-10-05" in text and "2026-10-03" in text
    assert "2026-10-01" not in text


def test_render_empty_is_honest():
    assert "no records yet" in ledger_mod.render_last_days([], days=7)


# --- DEBT-034: the derating factor, MEASURED not guessed -------------------

def _rec(trials: int, seconds: float) -> FactoryRecord:
    return FactoryRecord(date="2026-10-10", machine="heart", job="j",
                         trials=trials, machine_seconds=seconds)


def test_measured_derating_needs_two_timed_runs_and_is_honest_otherwise():
    # a single run cannot separate throughput from overhead -> None, never a guess.
    one = ledger_mod.measured_derating([_rec(100, 60.0)])
    assert one["factor"] is None and one["n"] == 1
    assert "non misurato" in one["reading"]
    assert ledger_mod.measured_derating([])["factor"] is None


def test_measured_derating_is_median_over_best_throughput():
    # best throughput = 100 trials/min (200 trials in 120 s); the median run is
    # 50 trials/min -> derating 0.5 (the overhead penalty, measured).
    recs = [_rec(200, 120.0), _rec(100, 120.0), _rec(100, 120.0)]
    d = ledger_mod.measured_derating(recs)
    assert d["best_trials_per_min"] == pytest.approx(100.0)
    assert d["median_trials_per_min"] == pytest.approx(50.0)
    assert d["factor"] == pytest.approx(0.5)
    assert "derating misurato" in d["reading"]


def test_a_perfectly_steady_machine_derates_to_one():
    d = ledger_mod.measured_derating([_rec(100, 60.0), _rec(100, 60.0)])
    assert d["factor"] == pytest.approx(1.0)


def test_render_carries_the_measured_derating(tmp_path):
    path = tmp_path / "l.jsonl"
    for t, s in ((200, 120.0), (100, 120.0), (100, 120.0)):
        ledger_mod.append([], _rec(t, s), path)
    text = ledger_mod.render_last_days(ledger_mod.load(path), days=3)
    assert "DERATING" in text and "0.5" in text


# --- R75 turbo budget ------------------------------------------------------

def test_budget_sealed_values():
    b = budget_mod.TURBO_BUDGET
    assert b.max_bursts_per_day == 3
    assert b.max_burst_seconds == 7200
    assert b.max_concurrent_jobs == 20


def test_budget_digest_is_stable_and_pinned():
    d1 = budget_mod.budget_manifest_digest()
    assert d1 == budget_mod.budget_manifest_digest(TurboBudget())
    assert len(d1) == 64


@pytest.mark.parametrize("kwargs", [
    {"bursts_today": 3, "requested_seconds": 60, "concurrency": 3},
    {"bursts_today": 0, "requested_seconds": 7201, "concurrency": 3},
    {"bursts_today": 0, "requested_seconds": 60, "concurrency": 21},
])
def test_check_burst_refuses_over_bounds(kwargs):
    with pytest.raises(TurboBudgetExceeded):
        budget_mod.check_burst(**kwargs)


def test_check_burst_allows_within_bounds():
    budget_mod.check_burst(bursts_today=0, requested_seconds=7200, concurrency=20)


def test_backoff_halves_every_bound():
    b = budget_mod.backoff()
    assert b.max_bursts_per_day == 1          # max(1, 3//2)
    assert b.max_burst_seconds == 3600
    assert b.max_concurrent_jobs == 10
