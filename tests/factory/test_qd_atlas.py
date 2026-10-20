"""THE ATLAS'S PROOFS -- the behavioral map measured, not narrated."""
from __future__ import annotations

import json

import pytest

from app.factory import qd


def _entry(**over):
    base = {"signature": "sig-a", "family": "trend_pullback",
            "wilson_lb": 0.50, "net_r": 12.0, "trades": 40,
            "behavior": None,
            "genome": {"family": "trend_pullback"}}
    base.update(over)
    # the behavior is always MEASURED from the entry's own numbers (an
    # override of trades/held/share moves the niche -- the test never
    # hand-plants a stale descriptor)
    base["behavior"] = qd.descriptor(
        trades=base["trades"],
        avg_bars_held=over.get("avg_bars_held", 20.0),
        long_share=over.get("long_share", 0.5))
    return base


class TestDescriptor:
    def test_three_axes_measured(self):
        d = qd.descriptor(trades=50, avg_bars_held=10.0, long_share=0.7)
        assert d["activity"] == "active"
        assert d["horizon"] == "mid"
        assert d["direction"] == "long-leaning"
        assert 0 <= qd.niche_id(d) < qd.NICHES

    def test_couch_has_no_behavior(self):
        assert qd.descriptor(trades=0, avg_bars_held=0.0, long_share=0.5) is None

    def test_garbage_is_refused_not_guessed(self):
        assert qd.descriptor(trades=10, avg_bars_held=float("nan"),
                             long_share=0.5) is None
        assert qd.descriptor(trades=10, avg_bars_held=5.0,
                             long_share=1.5) is None
        assert qd.niche_id(None) is None
        assert qd.niche_id({}) is None
        assert qd.niche_name(None) == ""

    def test_thirty_six_niches_distinct(self):
        ids = set()
        for a, t in (("sparse", 5), ("low", 20), ("active", 50), ("hyper", 100)):
            for h, held in (("sniper", 4.0), ("mid", 20.0), ("marathon", 50.0)):
                for s, share in (("short", 0.2), ("balanced", 0.5), ("long", 0.8)):
                    d = qd.descriptor(trades=t, avg_bars_held=held,
                                      long_share=share)
                    assert d is not None
                    ids.add(qd.niche_id(d))
        assert len(ids) == qd.NICHES == 36


class TestArchive:
    def test_mapelites_rule_empty_then_better(self):
        atlas = qd.QDArchive()
        assert atlas.offer(_entry()) is True          # the niche is empty
        assert atlas.offer(_entry(signature="sig-b", wilson_lb=0.40)) is False
        assert atlas.offer(_entry(signature="sig-c", wilson_lb=0.60)) is True
        cell = list(atlas.cells.values())[0]
        assert cell["signature"] == "sig-c"           # the best Wilson owns the niche

    def test_tiebreak_net_r_then_trades(self):
        atlas = qd.QDArchive()
        atlas.offer(_entry(wilson_lb=0.50, net_r=10.0, trades=40))
        assert atlas.offer(_entry(signature="tie-net", wilson_lb=0.50,
                                  net_r=20.0, trades=40)) is True
        assert atlas.offer(_entry(signature="tie-net-trades", wilson_lb=0.50,
                                  net_r=20.0, trades=60)) is True

    def test_ghost_and_couch_refused(self):
        atlas = qd.QDArchive()
        assert atlas.offer({"family": "x", "wilson_lb": 0.5}) is False        # no behavior
        assert atlas.offer(_entry(wilson_lb=None)) is False                    # ghost
        assert atlas.offer(_entry(wilson_lb=float("nan"))) is False            # NaN ghost
        assert atlas.offer("not-a-dict") is False
        assert atlas.coverage() == 0.0

    def test_different_behaviors_different_niches(self):
        atlas = qd.QDArchive()
        atlas.offer(_entry())  # active/mid/balanced
        atlas.offer(_entry(signature="sniper", trades=50, avg_bars_held=4.0,
                           wilson_lb=0.30))
        atlas.offer(_entry(signature="marathon-short", trades=100,
                           avg_bars_held=90.0, long_share=0.1, wilson_lb=0.35))
        assert atlas.coverage() == pytest.approx(3.0 / 36.0)
        assert len(atlas.occupied()) == 3
        assert atlas.occupied()[0]["signature"] == "sig-a"  # best Wilson first
        names = {r["niche_name"] for r in atlas.occupied()}
        assert names == {"active/mid/balanced", "active/sniper/balanced",
                         "hyper/marathon/short-leaning"}

    def test_diversity_pool_capped_best_first(self):
        atlas = qd.QDArchive()
        # five DIFFERENT niches, five different measures: the pool draws the
        # map's best, capped, best-first -- coverage without ignoring quality
        shapes = ((50, 4.0, 0.5, 0.44), (50, 20.0, 0.5, 0.51),
                  (50, 90.0, 0.5, 0.40), (100, 20.0, 0.2, 0.47),
                  (20, 4.0, 0.8, 0.45))
        for i, (t, held, share, w) in enumerate(shapes):
            atlas.offer(_entry(signature=f"sig-{i}", trades=t,
                               avg_bars_held=held, long_share=share,
                               wilson_lb=w))
        assert atlas.coverage() == pytest.approx(5.0 / 36.0)
        pool = atlas.diversity_pool(3)
        assert len(pool) == 3
        assert pool[0]["wilson_lb"] == pytest.approx(0.51)
        assert pool[0]["wilson_lb"] >= pool[1]["wilson_lb"] >= pool[-1]["wilson_lb"]
        assert atlas.diversity_pool(0) == []

    def test_persistence_roundtrip_and_fail_open(self, tmp_path):
        atlas = qd.QDArchive()
        atlas.offer(_entry())
        path = tmp_path / "factory_qd_test.json"
        assert qd.save_archive(atlas, path)
        loaded = qd.load_archive(path)
        assert loaded.coverage() == atlas.coverage()
        assert list(loaded.cells.values())[0]["signature"] == "sig-a"
        # torn / absent files are a fresh map, never a crash
        assert qd.load_archive(tmp_path / "absent.json").coverage() == 0.0
        torn = tmp_path / "torn.json"
        torn.write_text("{not json")
        assert qd.load_archive(torn).coverage() == 0.0

    def test_serialized_form_is_json_plain(self):
        atlas = qd.QDArchive()
        atlas.offer(_entry())
        blob = json.dumps(atlas.to_dict())
        assert json.loads(blob)["niches_total"] == qd.NICHES


class TestPublicationGate:
    """THE PUBLICATION GATE (the D3 lesson, applied at the atlas's birth).

    The first live round caught it: a factory test island (``test``,
    ``revolution``) left ``factory_qd_test.json`` beside the real memories in
    the working tree -- one heartbeat away from being committed as state. The
    gate: the atlas and the calibration are PUBLISHED for the real islands
    (heart/turbo/vault) only; a test island evolves in memory and dies with
    its run.
    """

    def test_a_test_island_publishes_nothing(self, tmp_path, monkeypatch):
        import numpy as np
        import pandas as pd
        from app.core.pairs import PAIR_PIP
        from app.quant import frames as fr
        from app.factory.factory import FactoryConfig, run_factory
        from app.factory.islands import ISLAND_WHEEL

        rng = np.random.default_rng(7)
        rows = 400
        steps = rng.normal(0, 0.0008, rows)
        close = 1.1000 + np.cumsum(steps)
        open_ = np.r_[close[0], close[:-1]]
        high = np.maximum(open_, close) + rng.uniform(0.0001, 0.0012, rows)
        low = np.minimum(open_, close) - rng.uniform(0.0001, 0.0012, rows)
        ts = 1546380000 + np.arange(rows) * 900
        tape = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low,
                             "close": close, "volume": np.full(rows, 300.0)})
        universe = {"EURUSD": fr.build_frames(tape, "EURUSD", PAIR_PIP["EURUSD"])}

        monkeypatch.chdir(tmp_path)  # belt and braces: nothing lands anywhere
        config = FactoryConfig(pairs=("EURUSD",), population=8, generations=1,
                               elite=3, min_trades=1, seed=3, polish=False,
                               cma=False, staircase=False,
                               ensemble_quota=0.0, screen_pair="EURUSD",
                               island="test")
        assert "test" not in ISLAND_WHEEL  # the premise: a test island is not real
        report = run_factory(universe, config)
        # the evolution RAN (the atlas applied, in memory) but PUBLISHED nothing:
        # the qd block says so, and no memory file landed anywhere near the tree
        assert report["qd"]["applied"] is True
        assert report["qd"]["published"] is False
        assert "zcognition" in report  # the cognition rode the report (Faculty 6)
        assert not (tmp_path / "factory_qd_test.json").exists()
        assert not (tmp_path / "factory_calibration_test.json").exists()
        assert not (tmp_path / "factory_champions_test.json").exists()
