"""R106 THE COUCH KING'S TERM LIMIT + R107 THE INDEPENDENCE ORDER -- a king
that does not hunt in the reigning regime rests on the bench (memory, never
exile), and the evidence's independence orders the door.

The measured truth this law was born from (2026-10-20, the guardian's first
full day): every champion the heart crowned was labelled COUCH on the recent
window -- 0 trades in the last 2,000 bars, wilson 0.55 on a book dominated
by the distant past. The pantry re-crowned them every shift on old evidence;
the diaspora carried them to the other islands; the evolution's slots went
to kings of a regime that no longer reigns.

Under test:
* the backoff arithmetic (streak -> cooldown, exponential, capped);
* the bench's honest bookkeeping: cooldowns tick down, a re-trial winner
  leaves the bench, a re-trial loser is re-benched with doubled cooldown;
* tonight's chronic couches join the bench with their genome PRESERVED;
* the injection door refuses a chronic couch (counted, never hidden) and
  grants the re-trial when the cooldown expires;
* the diaspora refuses a foreign couch at its own door;
* the export carries hunters only, with the honest reason when nobody rides;
* R107 -- within each verdict class the slice agreement orders the door
  (measured independence first, unmeasured last, wilson breaks the ties).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.factory.factory import (
    FactoryConfig, _couch_backoff, _evolve_bench, _recency_rank, run_factory,
)
from app.factory.islands import build_migration


# --- the generous synthetic ward (the diaspora suite's measured recipe) -----
def _tape(rows, start=1.1000, seed=7, drift=0.001, vol=0.0008):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, vol, rows)
    close = start + np.cumsum(steps)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.0001, 0.0012, rows)
    low = np.minimum(open_, close) - rng.uniform(0.0001, 0.0012, rows)
    ts = 1546380000 + np.arange(rows) * 900
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": np.full(rows, 300.0)})


def _build_universe(seed: int, rows: int = 20000):
    from app.core.pairs import PAIR_PIP
    from app.quant import frames as fr
    return {
        "EURUSD": fr.build_frames(_tape(rows, seed=seed), "EURUSD",
                                  PAIR_PIP["EURUSD"]),
        "GBPUSD": fr.build_frames(_tape(rows, start=1.2500, seed=seed + 1),
                                  "GBPUSD", PAIR_PIP["GBPUSD"]),
    }


@pytest.fixture(scope="module")
def universe():
    return _build_universe(seed=7)


@pytest.fixture(scope="module")
def recent_window():
    """A DIFFERENT tape: the fire is a real re-read, never a mirror."""
    return _build_universe(seed=99)


def _config(**kw) -> FactoryConfig:
    base = dict(pairs=("EURUSD", "GBPUSD"), population=12, generations=1,
                elite=4, min_trades=1, seed=3, polish=False, cma=False,
                staircase=True, ensemble_quota=0.0, screen_pair="EURUSD",
                island="test", qd=False)
    base.update(kw)
    return FactoryConfig(**base)


@pytest.fixture()
def ward(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def real_genome(universe, tmp_path_factory):
    """One real turn's pantry, built once: its champion genomes are honest
    bodies for the crafted entries (a hand-made genome would test nothing)."""
    work = tmp_path_factory.mktemp("couch_law_pantry")
    old = Path.cwd()
    import os
    os.chdir(work)
    try:
        report = run_factory(universe, _config(island="test"), )
        champs = report.get("champions") or []
        rows = []
        pantry = json.loads(Path("factory_champions_test.json").read_text())
        for c in (pantry.get("champions") or []):
            rows.append(c)
        return rows
    finally:
        os.chdir(old)


def _couch_entry(real_genome, *, streak=3, verdict="couch", sig="sig-couch"):
    src = dict(real_genome[0])
    src["recency"] = {"verdict": verdict, "wilson_lb": 0.4,
                      "net_r": 1.0, "trades": 40, "couch_streak": streak}
    src["signature"] = sig
    return src


def _write_pantry(ward: Path, island: str, champions: list[dict],
                  bench: list[dict] | None = None):
    (ward / f"factory_champions_{island}.json").write_text(
        json.dumps({"schema": 1, "source_island": island, "generation": 2,
                    "champions": champions, "digest": "x",
                    "bench": bench or []}, indent=2))


# --- R106: the backoff arithmetic --------------------------------------------
class TestBackoff:
    def test_the_arithmetic_is_exponential_and_capped(self):
        cfg = _config()
        assert _couch_backoff(3, cfg) == 4    # the trigger earns the base
        assert _couch_backoff(4, cfg) == 8    # each couch beyond doubles
        assert _couch_backoff(5, cfg) == 16
        assert _couch_backoff(9, cfg) == 24   # the cap bounds the exile
        assert _couch_backoff(30, cfg) == 24  # never forgotten forever

    def test_the_cap_is_honoured_when_small(self):
        cfg = _config(couch_cooldown_cap=6)
        assert _couch_backoff(3, cfg) == 4
        assert _couch_backoff(4, cfg) == 6
        assert _couch_backoff(9, cfg) == 6


# --- R106: the bench's honest bookkeeping ------------------------------------
class TestBenchEvolution:
    def _cfg(self):
        return _config()

    def test_cooldowns_tick_down(self, real_genome):
        bench = [{"genome": real_genome[0]["genome"], "family": "f",
                  "signature": "s1", "wilson_lb": 0.5, "net_r": 2.0,
                  "couch_streak": 3, "cooldown": 4}]
        out = _evolve_bench(bench, [], self._cfg())
        assert len(out) == 1 and out[0]["cooldown"] == 3

    def test_a_retrial_winner_leaves_the_bench(self, real_genome):
        bench = [{"genome": real_genome[0]["genome"], "family": "f",
                  "signature": "s1", "wilson_lb": 0.5, "net_r": 2.0,
                  "couch_streak": 3, "cooldown": 0}]
        tonight = [{"signature": "s1", "family": "f", "wilson_lb": 0.6,
                    "recency": {"verdict": "confirmed"}}]
        out = _evolve_bench(bench, tonight, self._cfg())
        assert out == []

    def test_a_retrial_loser_is_rebenched_with_doubled_cooldown(self, real_genome):
        bench = [{"genome": real_genome[0]["genome"], "family": "f",
                  "signature": "s1", "wilson_lb": 0.5, "net_r": 2.0,
                  "couch_streak": 3, "cooldown": 0}]
        out = _evolve_bench(bench, [], self._cfg())
        assert out[0]["couch_streak"] == 4 and out[0]["cooldown"] == 8

    def test_tonights_chronic_couch_joins_with_genome_preserved(self, real_genome):
        # a leaderboard row carries its genes at the TOP level (the same
        # shape the champion-seats selection feeds the pantry write); the
        # family must be a REAL one (from_dict falls back to a default on
        # an unknown name -- the house refuses imaginary bloodlines)
        row = {**real_genome[0]["genome"], "signature": "s9",
               "family": real_genome[0]["family"],
               "wilson_lb": 0.55, "net_r": 3.0,
               "recency": {"verdict": "couch", "couch_streak": 3}}
        out = _evolve_bench([], [row], self._cfg())
        assert len(out) == 1
        assert out[0]["signature"] == "s9" and out[0]["cooldown"] == 4
        assert out[0]["genome"] == real_genome[0]["genome"]

    def test_a_fresh_couch_stays_in_the_pantry_not_the_bench(self, real_genome):
        champs = [{"signature": "s2", "family": "f",
                   "genome": real_genome[0]["genome"],
                   "wilson_lb": 0.55, "net_r": 3.0,
                   "recency": {"verdict": "couch", "couch_streak": 1}}]
        out = _evolve_bench([], champs, self._cfg())
        assert out == []  # streak 1 < trigger 3: the king still rides

    def test_the_bench_is_bounded_and_the_deepest_survive(self, real_genome):
        bench = []
        for i in range(20):
            bench.append({"genome": real_genome[0]["genome"], "family": "f",
                          "signature": f"s{i}", "wilson_lb": 0.5,
                          "net_r": 1.0, "couch_streak": 3 + i,
                          "cooldown": 1})
        out = _evolve_bench(bench, [], self._cfg())
        assert len(out) == _config().bench_max
        streaks = [b["couch_streak"] for b in out]
        assert streaks == sorted(streaks, reverse=True)


# --- R106: the door and the diaspora in a real turn -------------------------
class TestTheDoor:
    def test_the_term_limit_refuses_a_chronic_couch(self, ward, universe,
                                                    real_genome):
        _write_pantry(ward, "test", [_couch_entry(real_genome, streak=3)])
        report = run_factory(universe, _config(),
                             probation_universe=None)
        law = report["couch_law"]
        assert law["benched_own"] == 1
        assert law["policy"].startswith("a chronic couch")
        pantry = json.loads(Path("factory_champions_test.json").read_text())
        assert isinstance(pantry.get("bench"), list)

    def test_the_retrial_door_opens_when_cooldown_expires(
            self, ward, universe, real_genome):
        _write_pantry(ward, "test", [],
                      bench=[{"genome": real_genome[0]["genome"],
                              "family": real_genome[0]["family"],
                              "signature": "s-bench", "wilson_lb": 0.5,
                              "net_r": 2.0, "couch_streak": 3,
                              "cooldown": 0}])
        report = run_factory(universe, _config())
        assert report["couch_law"]["bench_retrials"] == 1

    def test_a_resting_king_waits_counted(self, ward, universe, real_genome):
        _write_pantry(ward, "test", [],
                      bench=[{"genome": real_genome[0]["genome"],
                              "family": "f", "signature": "s-bench",
                              "wilson_lb": 0.5, "net_r": 2.0,
                              "couch_streak": 3, "cooldown": 7}])
        report = run_factory(universe, _config())
        assert report["couch_law"]["bench_retrials"] == 0
        assert report["couch_law"]["bench_waiting"] == 1

    def test_the_diaspora_refuses_a_foreign_couch(self, ward, universe,
                                                  real_genome):
        _write_pantry(ward, "turbo", [_couch_entry(real_genome,
                                                   streak=2,
                                                   sig="sig-foreign")])
        report = run_factory(universe, _config(), )
        assert report["diaspora"]["couch_refused"] >= 1
        assert report["diaspora"]["injected"] == 0

    def test_the_export_carries_hunters_only(self, ward, universe,
                                             real_genome, recent_window):
        _write_pantry(ward, "test", [_couch_entry(real_genome, streak=2)])
        report = run_factory(universe, _config(),
                             probation_universe=recent_window)
        pantry = json.loads(Path("factory_champions_test.json").read_text())
        exported = pantry.get("exported") or {}
        assert exported.get("hunters", 0) + exported.get("couches", 0) == \
            len(pantry.get("champions") or [])
        mig = report["migration"]
        if isinstance(mig, dict) and mig.get("champions"):
            for c in mig["champions"]:
                assert str((c.get("recency") or {}).get("verdict")) != "couch"


# --- R107: the independence order --------------------------------------------
class TestTheIndependenceOrder:
    def test_slice_agreement_orders_the_door_within_a_class(self):
        confirmed_hi = {"recency": {"verdict": "confirmed"},
                        "slice_agreement": 1.0, "wilson_lb": 0.30}
        confirmed_lo = {"recency": {"verdict": "confirmed"},
                        "slice_agreement": 0.4, "wilson_lb": 0.90}
        confirmed_unmeasured = {"recency": {"verdict": "confirmed"},
                                "slice_agreement": None, "wilson_lb": 0.95}
        rank = sorted([confirmed_lo, confirmed_unmeasured, confirmed_hi],
                      key=_recency_rank)
        assert [r["wilson_lb"] for r in rank] == [0.30, 0.90, 0.95]
        # the independence wins over the wilson; unmeasured trails the class

    def test_the_label_still_wins_over_everything(self):
        probationer = {"recency": {"verdict": "probation"},
                       "slice_agreement": 1.0, "wilson_lb": 0.99}
        confirmed = {"recency": {"verdict": "confirmed"},
                     "slice_agreement": None, "wilson_lb": 0.10}
        assert _recency_rank(confirmed)[0] < _recency_rank(probationer)[0]

    def test_a_nan_agreement_is_unmeasured_never_a_crash(self):
        r = _recency_rank({"recency": {"verdict": "confirmed"},
                           "slice_agreement": float("nan")})
        assert r[1][0] == 1  # the unmeasured key: last within its class
