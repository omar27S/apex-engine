"""R80 — THE PARETO FRONT (domination math + corner coverage)."""

from __future__ import annotations

import pytest

from app.factory import pareto as p


def _row(sig, lb, worst, resil, trades, realm=""):
    return {"signature": sig, "adv_net_lb": lb, "worst_seed_exposure": worst,
            "autopsy_resilience": resil, "trade_count": trades, "realm": realm}


def test_domination_math():
    assert p.dominates((1.0, 1.0), (0.0, 1.0)) is True
    assert p.dominates((1.0, 1.0), (1.0, 1.0)) is False     # equal is not dominate
    assert p.dominates((0.0, 1.0), (1.0, 0.0)) is False     # trade-off
    assert p.dominates((1.0, 1.0, 1.0), (1.0, 1.0, 0.0)) is True
    with pytest.raises(p.ParetoError):
        p.dominates((1.0,), (1.0, 0.0))


def test_front_excludes_dominated_points():
    rows = [
        _row("A", 1.0, 1.0, 1.0, 100),
        _row("B", 0.5, 0.5, 0.5, 50),   # dominated by A
        _row("C", 0.0, 2.0, 1.0, 200),  # trades off with A
    ]
    front = p.pareto_front(rows)
    sigs = {rows[i]["signature"] for i in front}
    assert sigs == {"A", "C"}
    assert 1 not in front


def test_missing_objective_refused():
    rows = [{"signature": "X", "adv_net_lb": 1.0}]
    with pytest.raises(p.ParetoError):
        p.pareto_front(rows)


def test_nonfinite_objective_refused():
    rows = [_row("A", float("nan"), 1.0, 1.0, 10)]
    with pytest.raises(p.ParetoError):
        p.pareto_front(rows)


def test_aliases_accept_row_shapes():
    rows = [{"signature": "A", "wilson_lb": 0.4, "worst_seed_net_r": -1.0,
             "resilience": 0.9, "trades": 30}]
    assert p.value_of(rows[0], "adv_net_lb") == 0.4
    assert p.value_of(rows[0], "worst_seed_exposure") == -1.0
    assert p.value_of(rows[0], "autopsy_resilience") == 0.9
    assert p.value_of(rows[0], "trade_count") == 30


def test_corners_occupied_and_representatives_are_front():
    rows = [
        _row("A", 1.0, 0.0, 0.5, 50),
        _row("B", 0.0, 1.0, 0.5, 50),
        _row("C", 0.5, 0.5, 1.0, 50),
        _row("D", 0.5, 0.5, 0.5, 500),
        _row("Z", 0.1, 0.1, 0.1, 10),
    ]
    front = p.pareto_front(rows)
    assert 4 not in front
    info = p.front_corners(rows, front=front)
    assert info["corners_total"] == 16
    assert info["occupied"] >= 2
    for rep in info["representatives"]:
        assert rep["row_index"] in front


def test_single_point_front_occupies_one_corner():
    rows = [_row("A", 1.0, 1.0, 1.0, 100)]
    info = p.front_corners(rows)
    assert info["occupied"] == 1


def test_select_elites_come_from_the_front_and_are_distinct():
    rows = [
        _row("A", 1.0, 0.0, 0.5, 50, realm="trend"),
        _row("B", 0.0, 1.0, 0.5, 50, realm="range"),
        _row("C", 0.5, 0.5, 1.0, 50, realm="vol"),
        _row("D", 0.5, 0.5, 0.5, 500, realm="mom"),
        _row("Z", 0.0, 0.0, 0.0, 1, realm="dead"),
    ]
    res = p.select_elites(rows, elites=3)
    assert len(res["selected"]) == 3
    assert len(set(res["selected"])) == 3
    assert 4 not in res["selected"]
    assert res["front_size"] == 4


def test_select_elites_preserves_realm_diversity_when_possible():
    rows = [
        _row("A", 1.0, 0.5, 0.5, 50, realm="trend"),
        _row("B", 0.0, 1.0, 0.5, 50, realm="range"),
        _row("C", 0.5, 0.0, 1.0, 50, realm="vol"),
    ]
    res = p.select_elites(rows, elites=3)
    assert set(res["realms"]) == {"trend", "range", "vol"}


def test_council_seats_distinct_realms_and_corners():
    rows = [
        _row("A", 1.0, 0.0, 0.5, 50, realm="trend"),
        _row("B", 0.0, 1.0, 0.5, 50, realm="range"),
        _row("C", 0.5, 0.5, 1.0, 50, realm="vol"),
        _row("D", 0.5, 0.5, 0.5, 500, realm="mom"),
        _row("A2", 1.0, 0.0, 0.5, 50, realm="trend"),
    ]
    res = p.council_seats(rows, seats=7)
    realms = res["realms_used"]
    assert len(realms) == len(set(realms))
    assert res["seats_filled"] <= 7
    assert res["corners_used"] >= 1
    sigs = [s["signature"] for s in res["seats"]]
    assert len(sigs) == len(set(sigs))


def test_council_seats_empty_front_is_honest():
    res = p.council_seats([], seats=7)
    assert res["seats_filled"] == 0
    assert res["realms_used"] == []
