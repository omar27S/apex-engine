"""THE COGNITION'S PROOFS -- the faculties measured, not narrated."""
from __future__ import annotations

import json

import pytest

from app.factory import zcognition as zc


class TestFaculties:
    def test_six_faculties_with_guards(self):
        assert len(zc.FACULTIES) == 6
        for f in zc.FACULTIES:
            assert f["id"] and f["name"] and f["text"] and f["guard"]

    def test_slice_agreement_independence(self):
        # wins on every slice: full independence
        assert zc.slice_agreement([1.0, 2.0, 0.5]) == pytest.approx(1.0)
        # wins on one of three
        assert zc.slice_agreement([1.0, -0.5, -0.5]) == pytest.approx(1.0 / 3.0)
        # empty is unmeasured, NEVER zero
        assert zc.slice_agreement([]) is None
        assert zc.slice_agreement(None) is None
        # NaN rows are dropped, the rest still measured
        assert zc.slice_agreement([float("nan"), 1.0, -1.0]) == pytest.approx(0.5)


class TestCalibrationLedger:
    def test_record_is_idempotent_per_shift(self):
        cal = zc.CalibrationLedger()
        assert cal.record(shift_id="s1", signature="A", verdict="confirmed",
                          wilson_lb=0.5)
        assert not cal.record(shift_id="s1", signature="A", verdict="couch",
                              wilson_lb=0.5)  # a shift files its word once
        assert len(cal.rows) == 1

    def test_confirmed_that_stays_agrees(self):
        cal = zc.CalibrationLedger()
        cal.record(shift_id="s1", signature="A", verdict="confirmed",
                   wilson_lb=0.55)
        graded = cal.score(signature="A", wilson_lb=0.60, ranked=True)
        assert graded == 1
        assert cal.rows[0]["agreed"] is True

    def test_confirmed_that_collapses_disagrees(self):
        cal = zc.CalibrationLedger()
        cal.record(shift_id="s1", signature="A", verdict="confirmed",
                   wilson_lb=0.55)
        cal.score(signature="A", wilson_lb=-1.0, ranked=False)
        assert cal.rows[0]["agreed"] is False

    def test_couch_that_wakes_disagrees(self):
        cal = zc.CalibrationLedger()
        cal.record(shift_id="s1", signature="B", verdict="couch", wilson_lb=0.0)
        cal.score(signature="B", wilson_lb=0.44, ranked=True)
        assert cal.rows[0]["agreed"] is False  # the couch woke: the label was wrong
        cal2 = zc.CalibrationLedger()
        cal2.record(shift_id="s1", signature="C", verdict="couch", wilson_lb=0.0)
        cal2.score(signature="C", wilson_lb=0.0, ranked=False)
        assert cal2.rows[0]["agreed"] is True   # the couch stayed: the label held

    def test_ungraded_signature_scores_zero_honestly(self):
        cal = zc.CalibrationLedger()
        assert cal.score(signature="never-filed", wilson_lb=0.5, ranked=True) == 0

    def test_accuracy_counts_only_graded(self):
        cal = zc.CalibrationLedger()
        cal.record(shift_id="s1", signature="A", verdict="confirmed", wilson_lb=0.5)
        cal.record(shift_id="s1", signature="B", verdict="confirmed", wilson_lb=0.5)
        cal.record(shift_id="s1", signature="C", verdict="couch", wilson_lb=0.0)
        cal.score(signature="A", wilson_lb=0.6, ranked=True)    # agreed
        cal.score(signature="B", wilson_lb=-2.0, ranked=False)  # disagreed
        acc = cal.accuracy()
        assert acc["filed"] == 3
        assert acc["graded"] == 2
        assert acc["agreed"] == 1
        assert acc["hit_rate"] == pytest.approx(0.5)
        assert cal.ungraded() and cal.ungraded()[0]["signature"] == "C"

    def test_bounded_memory(self):
        cal = zc.CalibrationLedger(max_rows=10)
        for i in range(30):
            cal.record(shift_id=f"s{i}", signature=f"sig-{i}",
                       verdict="confirmed", wilson_lb=0.5)
        assert len(cal.rows) == 10

    def test_persistence_roundtrip_fail_open(self, tmp_path):
        cal = zc.CalibrationLedger()
        cal.record(shift_id="s1", signature="A", verdict="confirmed",
                   wilson_lb=0.5)
        path = tmp_path / "factory_calibration_test.json"
        assert zc.save_calibration(cal, path)
        loaded = zc.load_calibration(path)
        assert loaded.rows[0]["signature"] == "A"
        assert zc.load_calibration(tmp_path / "absent.json").rows == []
        torn = tmp_path / "torn.json"
        torn.write_text("{oops")
        assert zc.load_calibration(torn).rows == []


class TestBlock:
    def test_zcognition_block_honest_arithmetic(self):
        blk = zc.zcognition_block(
            qd_coverage=0.25,
            calibration={"filed": 4, "graded": 2, "agreed": 2, "disagreed": 0,
                         "hit_rate": 1.0},
            slice_agreements=[1.0, 0.6667, None],
            champions=[{"signature": "A", "slice_agreement": 1.0}])
        assert blk["faculties"] == 6
        assert blk["qd_coverage"] == pytest.approx(0.25)
        assert blk["calibration"]["hit_rate"] == 1.0
        assert blk["slice_agreement"]["measured"] == 2
        assert blk["slice_agreement"]["unmeasured"] == 1
        assert blk["slice_agreement"]["mean"] == pytest.approx(0.83335, abs=1e-4)
        assert blk["slice_agreement"]["perfect"] == 1
        assert blk["champions"][0]["signature"] == "A"

    def test_empty_block_never_invents(self):
        blk = zc.zcognition_block()
        assert blk["qd_coverage"] is None
        assert blk["slice_agreement"]["mean"] is None
        assert blk["calibration"]["hit_rate"] is None


class TestDnaV2:
    def test_the_seal_covers_laws_and_faculties(self):
        from app.factory import dna
        assert dna.DNA_VERSION == 2
        assert dna.seal() == "dna=v2"
        assert len(dna.LAWS) == 12
        assert len(dna.FACULTIES) == 6
        t = dna.transcribe()
        assert t == {"version": 2, "laws": 12, "faculties": 6,
                     "seal": "dna=v2", "champions_refused": 0}

    def test_honest_champions_unchanged_law_3(self):
        from app.factory import dna
        keep, refused = dna.honest_champions([
            {"genome": {"family": "x"}, "wilson_lb": 0.0},   # measured 0.0: honest
            {"genome": {"family": "y"}},                     # ghost: refused
            {"genome": {"family": "z"}, "wilson_lb": None},  # ghost: refused
        ])
        assert len(keep) == 1 and refused == 2
