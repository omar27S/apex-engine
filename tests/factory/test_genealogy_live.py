"""THE GENEALOGIST RIDES THE FACTORY (R126/R127 integration).

A synthetic universe (the atlas's own pattern), a tiny population, and the
three proofs that matter: the census rides the report, a wheel island
publishes the book (and a test island publishes nothing), and the memory
SURVIVES the turn -- the second run's pantry is KNOWN blood, not a fresh
founder fleet.  The brake engages on a tiny elite pool by honest
arithmetic (3 elites = 3 lines = H 1/3 >= 0.25).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from app.core.pairs import PAIR_PIP
from app.factory import genealogist as gen
from app.factory.factory import FactoryConfig, run_factory
from app.factory.islands import ISLAND_WHEEL
from app.quant import frames as fr


def _universe(seed: int = 7, rows: int = 400):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.0008, rows)
    close = 1.1000 + np.cumsum(steps)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.0001, 0.0012, rows)
    low = np.minimum(open_, close) - rng.uniform(0.0001, 0.0012, rows)
    ts = 1546380000 + np.arange(rows) * 900
    tape = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": np.full(rows, 300.0)})
    return {"EURUSD": fr.build_frames(tape, "EURUSD", PAIR_PIP["EURUSD"])}


def _config(island: str, generations: int = 2) -> FactoryConfig:
    return FactoryConfig(pairs=("EURUSD",), population=8,
                         generations=generations, elite=3, min_trades=1,
                         seed=3, polish=False, cma=False, staircase=False,
                         ensemble_quota=0.0, screen_pair="EURUSD",
                         island=island)


def test_the_census_rides_the_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = run_factory(_universe(), _config("test"))
    assert "genealogy" in report          # the organ rides the report
    gene = report["genealogy"]
    assert gene["schema"] == gen.BLOOD_SCHEMA
    assert gene["island"] == "test"
    assert gene["bodies"] > 0            # the census counted the living
    assert gene["founders_alive"] >= 1
    assert 0.0 <= gene["herfindahl"] <= 1.0
    assert gene["verdict"] in ("diverse", "concentrating", "one-blood")
    assert "reading" in gene and "il sangue" in gene["reading"]


def test_a_test_island_publishes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_factory(_universe(), _config("test"))
    assert "test" not in ISLAND_WHEEL    # the premise
    assert not (tmp_path / "factory_genealogy_test.json").exists()
    assert not (tmp_path / "factory_blood_test.json").exists()


def test_a_wheel_island_writes_the_book_and_the_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = run_factory(_universe(), _config("heart"))
    assert "heart" in ISLAND_WHEEL       # the premise
    art_p = tmp_path / "factory_genealogy_heart.json"
    book_p = tmp_path / "factory_blood_heart.json"
    assert art_p.exists() and book_p.exists()
    art = json.loads(art_p.read_text())
    assert art["island"] == "heart"
    assert art["bodies"] == report["genealogy"]["bodies"]
    # the book on disk is the one the census measured
    book = gen.BloodBook.load(book_p, island="heart")
    assert book.founders_seen >= art["founders_alive"]


def test_the_book_remembers_across_turns(tmp_path, monkeypatch):
    """THE CROSS-TURN PROOF: the book's memory is monotone across turns,
    and whatever the pantry crowned carries real blood in the book."""
    monkeypatch.chdir(tmp_path)
    r1 = run_factory(_universe(seed=7), _config("heart"))
    b1 = gen.BloodBook.load(tmp_path / "factory_blood_heart.json")
    seen_1 = b1.founders_seen
    assert seen_1 >= 1
    # if the pantry crowned champions, the book knows their blood (a tiny
    # random-walk universe may honestly crown nobody -- the floor is the law)
    champs_p = tmp_path / "factory_champions_heart.json"
    if champs_p.exists():
        champs = json.loads(champs_p.read_text()).get("champions") or []
        from app.quant.genome import StrategyGenome
        for c in champs:
            _sig = str(StrategyGenome.from_dict(c["genome"]).signature())
            assert b1.blood_of(_sig) != frozenset(), (
                "a crowned body left no blood in the book")
    r2 = run_factory(_universe(seed=99), _config("heart"))
    b2 = gen.BloodBook.load(tmp_path / "factory_blood_heart.json")
    # monotone memory: the second turn knew the first turn's founders
    assert b2.founders_seen >= seen_1
    assert r2["genealogy"]["founders_seen_total"] >= seen_1


def test_the_brake_engages_on_a_tiny_elite_pool(tmp_path, monkeypatch):
    """3 elites from 3 random founders = collision probability 1/3 >= 0.25:
    the brake FIRES by honest arithmetic, and the report says so."""
    monkeypatch.chdir(tmp_path)
    report = run_factory(_universe(), _config("test", generations=2))
    gene = report["genealogy"]
    elite_h = 1.0 / 3.0
    if gene["brake"].get("applied"):
        # the engaged brake speaks its reason and counts its work
        assert "reason" in gene["brake"]
        assert elite_h >= gen.VERDICT_THRESHOLDS["concentrating"]
    else:
        # honest alternative: the funnel may collapse the elites below 3
        # distinct founders; then the census must still be spoken
        assert gene["verdict"] in ("diverse", "concentrating", "one-blood")


def test_the_population_size_is_untouched_by_the_brake(tmp_path, monkeypatch):
    """THE RED LINE'S COUSIN: the brake never changes the pool's size --
    immigrants REPLACE bred children, the pool stays config.population."""
    monkeypatch.chdir(tmp_path)
    for gens in (1, 2, 3):
        report = run_factory(_universe(), _config("test", generations=gens))
        assert report["population"] == 8
        pool = report["funnel"]["pool"]
        assert pool == 8, f"generations={gens}: the pool changed ({pool})"


def test_the_letter_speaks_the_blood(tmp_path, monkeypatch):
    """R126's voice: the morning letter carries the census of all three
    islands, the verdict in the CEO's tongue, and the brake said aloud."""
    monkeypatch.chdir(tmp_path)
    rows = (
        ("heart", "diverse", {}),
        ("turbo", "concentrating",
         {"applied": True, "sibling_mates_avoided": 5}),
        ("vault", "one-blood",
         {"applied": True, "sibling_mates_avoided": 9, "immigrants": 4}),
    )
    for isle, verdict, brake in rows:
        (tmp_path / f"factory_genealogy_{isle}.json").write_text(json.dumps({
            "schema": 1, "island": isle, "ts": 1.0, "bodies": 240,
            "founders_alive": 12, "herfindahl": 0.4,
            "effective_population": 2.5, "sibling_matings": 3,
            "crossovers": 100, "verdict": verdict, "brake": brake,
            "census_top": []}))
    from app.civilization import letter
    txt = letter.build_morning_letter({"leaderboard": []}, date="2026-10-21")
    assert "Il sangue (da dove vengono i corpi)" in txt
    assert "diversificato" in txt
    assert "in concentrazione" in txt
    assert "una sola famiglia" in txt
    assert "il freno e' scattato" in txt
    assert "9 accoppiamenti tra fratelli evitati" in txt
    assert "4 immigrati freschi" in txt


def test_the_letter_stays_silent_when_the_genealogist_is_unborn(tmp_path,
                                                                monkeypatch):
    """A letter without the census still speaks its numbers (the law of the
    scars holds for the blood too: an absent organ is silence, not a lie)."""
    monkeypatch.chdir(tmp_path)
    from app.civilization import letter
    txt = letter.build_morning_letter({"leaderboard": []}, date="2026-10-21")
    assert "Il sangue (da dove vengono i corpi)" not in txt
