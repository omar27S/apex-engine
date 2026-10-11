"""R78 — PROBATION EXECUTION (the ensemble quota is ruled by the data)."""

from __future__ import annotations

import pytest

from app.factory import probation as p


def _night(ens_ranked: int, single_ranked: int) -> list[dict]:
    return [
        {"arm": "ensemble_elite", "ranked": ens_ranked},
        {"arm": "ensemble_random", "ranked": 0},
        {"arm": "single", "ranked": single_ranked},
    ]


def test_constants_sealed():
    assert p.PROBATION_MIN_NIGHTS == 10
    assert p.ENSEMBLE_SHARE_FLOOR == 0.05
    assert p.BASE_QUOTA == 0.25
    assert p.PROBATION_QUOTA == 0.10


def test_pending_before_ten_nights():
    tables = [_night(1, 9) for _ in range(9)]
    d = p.decide(tables)
    assert d["nights_counted"] == 9
    assert d["ruling"]["state"] == "probation_pending"
    assert d["ruling"]["quota_after"] is None
    assert d["ruling"]["triggered"] is False


def test_rules_to_probation_when_share_below_floor():
    # 10 nights, every night 0 ensembles ranked out of 10 -> share 0% < 5%.
    tables = [_night(0, 10) for _ in range(10)]
    d = p.decide(tables)
    assert d["nights_counted"] == 10
    assert d["ensemble_ranked_share"] == 0.0
    assert d["ruling"]["state"] == "probation_ruled"
    assert d["ruling"]["triggered"] is True
    assert d["ruling"]["quota_after"] == 0.10
    assert d["ruling"]["quota_before"] == 0.25


def test_quota_unchanged_when_share_at_or_above_floor():
    # 10 nights, 1 ensemble ranked out of 10 -> 10% >= 5%.
    tables = [_night(1, 9) for _ in range(10)]
    d = p.decide(tables)
    assert d["ensemble_ranked_share"] == pytest.approx(0.10)
    assert d["ruling"]["state"] == "probation_ruled"
    assert d["ruling"]["triggered"] is False
    assert d["ruling"]["quota_after"] == 0.25


def test_empty_nights_are_not_counted():
    tables = [_night(0, 10) for _ in range(5)] + [[], _night(0, 0)]
    d = p.decide(tables)
    assert d["nights_counted"] == 5  # the empty nights carry no evidence
    assert d["ruling"]["state"] == "probation_pending"


def test_measure_is_deterministic_and_resume_safe():
    tables = [_night(0, 10) for _ in range(10)]
    assert p.decide(tables) == p.decide(tables)
    assert p.ruling_digest(p.decide(tables)) == p.ruling_digest(p.decide(tables))


def test_ruling_record_carries_the_numbers():
    d = p.decide([_night(0, 10) for _ in range(10)])
    rec = p.ruling_record(d, night="2026-10-12", run_number=7)
    assert rec["kind"] == "ensemble_probation_ruling"
    assert rec["triggered"] is True
    assert rec["nights_counted"] == 10
    assert rec["quota_before"] == 0.25 and rec["quota_after"] == 0.10
    assert rec["reason"]
    assert len(rec["digest"]) == 64


def test_non_list_refused():
    with pytest.raises(p.ProbationError):
        p.measure({"not": "a list"})
