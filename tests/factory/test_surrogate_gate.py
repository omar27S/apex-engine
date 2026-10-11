"""R79 — THE SURROGATE GATE (pre-screen only; never a verdict)."""

from __future__ import annotations

import numpy as np
import pytest

from app.factory import surrogate as s


def _toy_data(n=400, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.random((n, len(s.FEATURE_NAMES)))
    # A learnable signal: net_r rises with feature 0 and family_bucket.
    y = 2.0 * X[:, 0] + X[:, 8] - 1.0 + 0.05 * rng.standard_normal(n)
    return X, y


def test_constants_sealed():
    assert s.MAX_SKIP_FRACTION == 0.30
    assert s.RETRAIN_PERIOD_NIGHTS == 7
    assert len(s.FEATURE_NAMES) == 11


def test_tree_learns_a_monotone_signal():
    X, y = _toy_data()
    tree = s.RegressionTree(max_depth=3).fit(X, y)
    pred = tree.predict(X)
    baseline = np.full_like(y, y.mean())
    assert ((pred - y) ** 2).mean() < ((baseline - y) ** 2).mean() * 0.8


def test_surrogate_reduces_error_and_is_deterministic():
    X, y = _toy_data()
    m1 = s.Surrogate(n_estimators=40, seed=0).fit(X, y)
    p1 = m1.predict(X)
    m2 = s.Surrogate(n_estimators=40, seed=0).fit(X, y)
    p2 = m2.predict(X)
    assert np.array_equal(p1, p2)
    assert ((p1 - y) ** 2).mean() < ((y - y.mean()) ** 2).mean()


def test_unfitted_predict_refused():
    with pytest.raises(s.SurrogateError):
        s.Surrogate().predict(np.zeros((2, len(s.FEATURE_NAMES))))


def test_skip_bound_holds_and_never_skips_at_or_above_floor():
    pred = np.array([0.0] * 60 + [1.0] * 40, dtype=float)
    mask = s.skip_mask(pred, floor=0.5)
    k = int(np.ceil(s.MAX_SKIP_FRACTION * 100))
    assert mask.sum() == k == 30
    assert not mask[60:].any()
    assert mask[:60].sum() == 30
    assert mask[:30].all()


def test_skip_bound_holds_at_small_n():
    pred = np.array([0.0, 0.1, 0.2], dtype=float)
    mask = s.skip_mask(pred, floor=0.5)
    assert mask.sum() == int(np.ceil(0.30 * 3)) == 1


def test_no_skips_when_none_below_floor():
    pred = np.array([0.9, 0.95, 1.0], dtype=float)
    assert s.skip_mask(pred, floor=0.5).sum() == 0


def test_should_retrain_weekly():
    assert s.should_retrain(None, 5) is True
    assert s.should_retrain(0, 6) is False
    assert s.should_retrain(0, 7) is True
    assert s.should_retrain(10, 16) is False
    assert s.should_retrain(10, 17) is True


def test_surrogate_excluded_from_identity():
    m = s.Surrogate().fit(*_toy_data(n=50))
    assert m.identity_token() == ""


def test_flight_record_bounds_and_stats():
    rec = s.flight_record(fitted=True, n_candidates=100, skipped=30,
                          hits=27, misses=3)
    assert rec["skip_rate"] == pytest.approx(0.30)
    assert rec["skip_bound"] == 0.30
    assert rec["hit_rate"] == pytest.approx(0.9)
    assert rec["in_identity"] is False
    none = s.flight_record(fitted=False, n_candidates=100, skipped=0,
                           hits=0, misses=0)
    assert none["skip_rate"] == 0.0 and none["hit_rate"] is None


def test_matrix_from_rows_is_deterministic():
    from app.pyramid.outcome_corpus import OutcomeRow, features_from

    rows = [OutcomeRow(features=features_from(family="breakout", trades=50),
                       net_r=(0.1 if i % 2 else -0.1), family="breakout")
            for i in range(8)]
    X1, y1 = s.matrix_from_rows(rows)
    X2, y2 = s.matrix_from_rows(rows)
    assert np.array_equal(X1, X2) and np.array_equal(y1, y2)
    assert X1.shape == (8, len(s.FEATURE_NAMES))
