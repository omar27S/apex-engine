"""R97 — THE LIVING FUNNEL + THE COUCH IS NEVER A CHAMPION.

The measured wound (2026-10-20, 160 random bodies on the SELECTION book):
66% never trade on the 5-pair universe, 3% clear the old absolute round-one bar
(30+ trades on ONE cheap pair AND gross >= 3x friction there), and the real
shift that morning killed 240/240 — extinction, not selection; an extinct pool
cannot breed, and the pantry held seven couches (wilson 0.0, net 0.0) for days.

The law under test:
* round one keeps the living variety (top-K graded, LIFE FIRST) — a cost funnel,
  never a verdict;
* the sealed R85 friction gate judges at round two, where the invoice is FULL;
* only RANKED bodies (min_trades on the full universe) sit in realms, hold
  thrones, or enter the pantry — the couch is unknown, and the unknown is never
  crowned;
* the funnel reports itself honestly (keep, couches counted, ranked final).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.factory.factory import FactoryConfig, run_factory
from app.factory import staircase as st


# --- the law is law, and it is signed ----------------------------------------
def test_the_funnel_default_is_law():
    assert FactoryConfig(pairs=("EURUSD",)).screen_survival == 0.6


def test_the_funnel_is_signed():
    a = FactoryConfig(pairs=("EURUSD",), screen_survival=0.6)
    b = FactoryConfig(pairs=("EURUSD",), screen_survival=0.75)
    assert a.signature() != b.signature()


# --- round one keeps the LIVING first ----------------------------------------
def test_round_one_keeps_the_living_first():
    pool = ["couch", "worker", "star", "quiet"]
    graded = {"couch": (0, 0.0, 0.0), "quiet": (0, 0.0, 0.0),
              "worker": (30, 0.2, 1.0), "star": (80, 0.4, 9.0)}
    judged = {"era": []}

    def screen(g, s):
        return True

    def era(g, s):
        judged["era"].append(g)
        return True

    res = st.screen(pool, {"screen": screen, "era": era,
                           "gauntlet": lambda g, s: True},
                    relative={"keep": 2, "graded": lambda g: graded[g]})
    # life first: the two bodies that TRADE rise over the two couches, whatever
    # their merit; the merit is not this round's business.
    assert sorted(res.survivors) == ["star", "worker"]
    d = res.to_dict()
    assert d["relative"]["applied"] is True and d["relative"]["keep"] == 2
    # the survivors were handed onward to the full round (they are judged there).
    assert set(res.survivors) <= set(judged["era"])


def test_the_gate_judges_at_round_two_not_the_portcullis():
    # a living, graded body whose gross cannot pay 3x friction: it must SURVIVE
    # the cheap round (round one judges life, not invoices) and die at the era,
    # where the invoice is full and the sealed gate speaks.
    def gate(g):
        return st.FrictionGate(gross_r=10.0, friction_r=30.0)  # multiple 0.33

    res = st.screen(["alive_poor"],
                    {"screen": lambda g, s: True, "era": lambda g, s: True,
                     "gauntlet": lambda g, s: True},
                    friction_gate=gate, gate_round=1,
                    relative={"keep": 1, "graded": lambda g: (50, 0.3, 2.0)})
    assert res.survivors == []
    assert res.friction_rejected == 1
    d = res.to_dict()
    assert d["gate_round"] == 1 and d["relative"]["applied"] is True


def test_the_old_gate_seat_is_unchanged():
    # R85 compatibility: no relative funnel -> the gate judges at round one,
    # exactly as before the law moved its seat.
    res = st.screen(["poor"],
                    {"screen": lambda g, s: True, "era": lambda g, s: True,
                     "gauntlet": lambda g, s: True},
                    friction_gate=lambda g: st.FrictionGate(gross_r=10.0,
                                                            friction_r=30.0))
    assert res.survivors == [] and res.friction_rejected == 1
    assert res.to_dict()["relative"]["applied"] is False


def test_round_one_with_gate_at_zero_judges_the_kept():
    # relative funnel + gate_round=0: the cut happens first, the gate then
    # judges the KEPT bodies before they spend the expensive rounds.
    def gate(g):
        if g == "kept_rich":
            return st.FrictionGate(gross_r=90.0, friction_r=10.0)  # 9x, passes
        return st.FrictionGate(gross_r=10.0, friction_r=30.0)      # 0.33x, dies

    res = st.screen(["kept_rich", "kept_poor"],
                    {"screen": lambda g, s: True, "era": lambda g, s: True,
                     "gauntlet": lambda g, s: True},
                    friction_gate=gate, gate_round=0,
                    relative={"keep": 2, "graded": lambda g: (10, 0.1, 1.0)})
    assert res.survivors == ["kept_rich"] and res.friction_rejected == 1


# --- the couch is never a champion -------------------------------------------
def _tape(rows, start=1.1000, seed=7):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.0008, rows)
    close = start + np.cumsum(steps)
    open_ = np.r_[close[0], close[:-1]]
    # OHLC honesty (the validator is fail-closed): high/low must bracket the
    # open AND the close of their own row, whatever the drift.
    high = np.maximum(open_, close) + rng.uniform(0.0001, 0.0012, rows)
    low = np.minimum(open_, close) - rng.uniform(0.0001, 0.0012, rows)
    ts = 1546380000 + np.arange(rows) * 900
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": np.full(rows, 300.0)})


def _universe():
    from app.core.pairs import PAIR_PIP
    from app.quant import frames as fr
    return {
        "EURUSD": fr.build_frames(_tape(400), "EURUSD", PAIR_PIP["EURUSD"]),
        "GBPUSD": fr.build_frames(_tape(400, start=1.2500), "GBPUSD",
                                  PAIR_PIP["GBPUSD"]),
    }


def _small_config(**kw) -> FactoryConfig:
    base = dict(pairs=("EURUSD", "GBPUSD"), population=12, generations=1, elite=4,
                min_trades=1, seed=3, polish=False, cma=False, staircase=False,
                ensemble_quota=0.0, screen_pair="EURUSD", island="test")
    base.update(kw)
    return FactoryConfig(**base)


def test_survival_is_validated_fail_closed():
    universe = _universe()
    with pytest.raises(ValueError):
        run_factory(universe, _small_config(staircase=True, screen_survival=0.0))
    with pytest.raises(ValueError):
        run_factory(universe, _small_config(staircase=True, screen_survival=1.5))


def test_a_couch_is_never_a_champion():
    # nobody can reach min_trades=10_000 on a 400-row tape: every body is a
    # couch tonight. The pantry must NOT be written, the realms must stay empty,
    # and no couch may be crowned -- the old leaderboard crowned seven of them.
    pantry = Path("factory_champions_test.json")
    try:
        universe = _universe()
        report = run_factory(universe, _small_config(min_trades=10_000,
                                                     staircase=True))
        assert report["champions"] == []
        assert report["realms"]["occupied"] == 0
        assert report["funnel"]["ranked_final"] == 0
        assert report["migration"]["exported"] is False
        assert "couch" in report["migration"]["reason"]
        assert not pantry.exists()          # nothing crowned, nothing written
    finally:
        if pantry.exists():
            pantry.unlink()


def test_the_funnel_report_is_honest():
    pantry = Path("factory_champions_test.json")
    try:
        universe = _universe()
        report = run_factory(universe, _small_config(staircase=True))
        f = report["funnel"]
        assert f["applied"] is True
        # pool 12, survival 0.6 -> keep 7 (at least one living body, never more
        # than the pool).
        assert f["keep"] == max(1, round(12 * 0.6))
        assert 0 <= f["no_trade_final"] <= f["pool"]
        assert isinstance(f["ranked_final"], int)
        assert report["staircase"]["relative"]["applied"] is True
        assert report["staircase"]["gate_round"] == 1
        assert report["staircase"]["passed"]["screen"] == f["keep"]
    finally:
        if pantry.exists():
            pantry.unlink()
