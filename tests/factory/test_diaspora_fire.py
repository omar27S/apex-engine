"""R99 THE DIASPORA + R100 THE RECENCY PROBATION -- three tribes, one gene
pool; and the fire every champion faces before the pantry remembers it.

The measured truth this law was born from (2026-10-20): three islands bred in
perfect isolation -- the migration lever (R68) EXPORTED champions that no
island ever IMPORTED; and the pantry's champions were selected on the full
20,000-row book without ever facing the most recent window -- the closest
thing to tomorrow morning. A champion that only fits the distant past is the
overfit the Boss's money cannot afford.

The ward is a GENEROUS synthetic tape (20,000 rows with drift): the flat
400-row tape of the funnel tests kills every body at the friction gate or
before a single trade (measured here before a single assertion was written --
66% of random bodies never trade even on the real book). The drifting tape
grows a champion (a keltner_expansion with 200+ trades) so the diaspora has
REAL genes to carry. The universe is built ONCE per module: frames are pure,
and honesty does not need three identical tape builds.

Under test:
* the diaspora injects the OTHER islands' best into generation 0 (best-first,
  honest-validated, dedup by signature, capped at population//8);
* a ghost in a foreign pantry is refused and COUNTED, never swallowed;
* the diaspora is fail-open: a torn foreign pantry never starves the shift;
* the recency probation labels every pantry champion on the recent window
  (confirmed / probation / couch / unmeasured) and the label rides into the
  pantry and the report;
* the injection order reads the label (confirmed first) -- an unjudged pantry
  ranks by measure alone (backward honest);
* without a probation window nothing is invented (applied: False).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.factory.factory import FactoryConfig, run_factory, _recency_rank
from app.factory.islands import ISLAND_WHEEL, build_migration


# --- the generous synthetic ward (measured: champions grow here) ------------
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
    """The selection book: one generous tape, built once (frames are pure)."""
    return _build_universe(seed=7)


@pytest.fixture(scope="module")
def recent_window():
    """The probation window: a different tape -- the fire is a real re-read."""
    return _build_universe(seed=99)


def _config(**kw) -> FactoryConfig:
    base = dict(pairs=("EURUSD", "GBPUSD"), population=12, generations=1,
                elite=4, min_trades=1, seed=3, polish=False, cma=False,
                staircase=True, ensemble_quota=0.0, screen_pair="EURUSD",
                island="test")
    base.update(kw)
    return FactoryConfig(**base)


@pytest.fixture()
def ward(tmp_path, monkeypatch):
    """An isolated working dir: pantries written here are the test's alone."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _pantry_path(island: str) -> Path:
    return Path(f"factory_champions_{island}.json")


def _read_pantry(island: str) -> dict:
    return json.loads(_pantry_path(island).read_text())


def _write_foreign(ward: Path, island: str, entries: list[dict]):
    (ward / f"factory_champions_{island}.json").write_text(
        json.dumps(build_migration(island, 2, entries).to_dict(), indent=2))


def _entry_from(pantry: dict, index: int = 0) -> dict:
    src = (pantry.get("champions") or [])[index]
    return {"genome": src["genome"], "family": src["family"],
            "wilson_lb": src["wilson_lb"], "net_r": src["net_r"]}


@pytest.fixture(scope="module")
def a_real_pantry(universe, tmp_path_factory):
    """One REAL island turn's pantry (built once, copied into each ward)."""
    work = tmp_path_factory.mktemp("real_pantry")
    cwd = Path.cwd()
    os_cwd = cwd
    import os
    os.chdir(work)
    try:
        report = run_factory(universe, _config(island="heart"))
        assert report["champions"], ("the generous tape must grow a champion "
                                     "(measured: keltner, 200+ trades)")
        payload = json.loads(
            (work / "factory_champions_heart.json").read_text())
    finally:
        os.chdir(os_cwd)
    return payload


# --- R99: the diaspora -------------------------------------------------------
def test_an_island_with_NO_neighbours_runs_alone_honestly(ward, universe):
    report = run_factory(universe, _config())
    d = report["diaspora"]
    assert d["injected"] == 0 and d["sources"] == {} and d["refused"] == 0


def test_the_diaspora_feeds_the_foreigners_best_first(ward, universe,
                                                      a_real_pantry):
    _write_foreign(ward, "heart",
                   [_entry_from(a_real_pantry, i)
                    for i in range(len(a_real_pantry["champions"]))])
    report = run_factory(universe, _config(island="test"))
    d = report["diaspora"]
    assert d["injected"] >= 1
    assert "heart" in d["sources"]
    assert sum(d["sources"].values()) == d["injected"]


def test_the_diaspora_is_capped_at_an_eighth(ward, universe, a_real_pantry):
    entries = [_entry_from(a_real_pantry, i)
               for i in range(len(a_real_pantry["champions"]))]
    _write_foreign(ward, "heart", entries)
    _write_foreign(ward, "turbo", entries)
    _write_foreign(ward, "vault", entries)
    report = run_factory(universe, _config(island="test"))
    assert report["diaspora"]["injected"] <= 12 // 8  # population // 8


def test_a_ghost_in_a_foreign_pantry_is_refused_and_counted(ward, universe,
                                                            a_real_pantry):
    entries = [_entry_from(a_real_pantry, 0),
               {"genome": {"phantom": True}, "wilson_lb": None}]  # a ghost
    _write_foreign(ward, "heart", entries)
    report = run_factory(universe, _config(island="test"))
    d = report["diaspora"]
    assert d["refused"] >= 1
    assert d["injected"] <= len(entries) - 1


def test_a_torn_foreign_pantry_never_starves_the_shift(ward, universe):
    Path("factory_champions_heart.json").write_text("{torn")
    report = run_factory(universe, _config(island="test"))
    assert report["diaspora"]["injected"] == 0  # fail-open: the turn ran


def test_the_watchtowers_paused_families_never_re_enter(ward, universe,
                                                        a_real_pantry):
    # DEBT-060 at the injection door: the state pauses the champion's whole
    # group on a pair -- the pantry's memory may not reopen a closed door.
    from app.factory import realms
    entries = [_entry_from(a_real_pantry, i)
               for i in range(len(a_real_pantry["champions"]))]
    _write_foreign(ward, "heart", entries)
    groups = {realms.family_group(e["family"]) for e in entries}
    assert groups, "the real pantry must carry families to pause"
    gating = {"EURUSD": {"paused": [sorted(groups)[0]], "active": []}}
    report = run_factory(universe, _config(island="test",
                                           regime_gating=gating))
    d = report["diaspora"]
    assert d["gated"] >= 1
    assert d["injected"] == 0
    # and the gating report stays honest: nobody paused was OFFERED a slot
    assert report["regime_gating"]["n_paused_offered"] == 0


def test_the_wheel_names_the_archipelago_once():
    # the diaspora and the rotation read ONE canonical tuple
    assert ISLAND_WHEEL == ("heart", "turbo", "vault")


# --- R100: the recency probation --------------------------------------------
def test_the_probation_labels_every_champion(ward, universe, recent_window):
    report = run_factory(universe, _config(),
                         probation_universe=recent_window)
    p = report["probation"]
    n = len(report["champions"])
    # the fire is lit when and only when there are champions to face it
    assert p["applied"] == bool(n)
    assert n >= 1, "the generous tape must crown a champion to face the fire"
    assert (p["confirmed"] + p["probation"] + p["couch"] + p["unmeasured"]
            == n)
    # the label rides into the pantry, and the report carries the verdict
    pantry = _read_pantry("test")
    assert pantry["champions"]
    for entry in pantry["champions"]:
        assert (entry.get("recency") or {}).get("verdict") in (
            "confirmed", "probation", "couch", "unmeasured")
    for row in report["champions"]:
        assert row.get("recency") in ("confirmed", "probation", "couch",
                                      "unmeasured")


def test_without_a_window_nothing_is_invented(ward, universe):
    report = run_factory(universe, _config())  # no probation_universe
    p = report["probation"]
    assert p["applied"] is False
    assert p["confirmed"] == 0 and p["couch"] == 0
    for row in report["champions"]:
        assert row.get("recency") is None  # no label, no guess


def test_the_injection_order_reads_the_label():
    confirmed = {"recency": {"verdict": "confirmed"}}
    probationer = {"recency": {"verdict": "probation"}}
    unjudged = {}
    # within each class the measured wilson leads; across classes the label wins
    rank = sorted([
        {"wilson_lb": 0.60, **probationer},
        {"wilson_lb": 0.30, **confirmed},
        {"wilson_lb": 0.90, **unjudged},
    ], key=_recency_rank)
    assert [r["wilson_lb"] for r in rank] == [0.30, 0.60, 0.90]
    # a ghost score rides last, never crashes the sort
    assert _recency_rank({"wilson_lb": float("nan")})[0] == 2


# --- the report's honesty ----------------------------------------------------
def test_the_diaspora_and_probation_report_their_policy(ward, universe,
                                                        recent_window):
    report = run_factory(universe, _config(),
                         probation_universe=recent_window)
    assert "one gene pool" in report["diaspora"]["policy"]
    assert "labels, never erasures" in report["probation"]["policy"]
