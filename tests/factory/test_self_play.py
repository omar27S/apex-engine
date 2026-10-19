"""SELF-PLAY (Mega Phase 2, Section C) -- sparring, adversaries, the ladder.

Friction contract: make ``sparring`` always name a winner (even on a draw) and the
draw test FAILS; drop the demotion rule and the ladder test FAILS.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.data import load_parquet
from app.factory import self_play as sp
from app.quant import frames as fr
from app.quant import seeds

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "history"


@pytest.fixture(scope="module")
def universe():
    fp = DATA_DIR / "EURUSD_M15.parquet"
    if not fp.exists():
        pytest.skip("real history not present")
    F = fr.build_frames(load_parquet(str(fp)).tail(6000).reset_index(drop=True),
                        "EURUSD", 0.0001)
    return {"EURUSD": F}


def test_opposite_bias_requires_full_opposition():
    assert sp.opposite_bias(1, -1) is True
    assert sp.opposite_bias(1, 1) is False
    assert sp.opposite_bias(0, -1) is False
    assert sp.opposite_bias(None, -1) is False


def test_ladder_tier_reads_the_survival_record():
    assert sp.ladder_tier({})["tier"] == "Bronze"
    assert sp.ladder_tier({"tournaments_survived": 3, "net_r": 5.0})["tier"] == "Platinum"
    assert sp.ladder_tier({"passed_gauntlet": True})["tier"] == "Diamond"


def test_three_losses_demote():
    r = sp.ladder_tier({"tournaments_survived": 3, "net_r": 5.0,
                        "consecutive_self_play_losses": 3})
    assert r["demoted"] is True and r["tier"] == "Gold"


def test_sparring_on_real_tape_names_a_winner_or_a_draw(universe):
    a = seeds.seed_for("breakout")
    b = seeds.seed_for("mean_reversion")
    res = sp.sparring(a, b, universe)
    assert res["ok"] is True
    assert "winner" in res
    if res.get("draw"):
        assert res["winner"] is None


def test_sparring_is_honest_without_a_tape():
    a = seeds.seed_for("breakout")
    b = seeds.seed_for("mean_reversion")
    res = sp.sparring(a, b, {})
    assert res["ok"] is False and res["winner"] is None


def test_adversarial_mutation_flips_the_bias():
    champion = seeds.seed_for("breakout")
    res = sp.adversarial_mutation(champion, rng=__import__("random").Random(1))
    adv = res["adversary"]
    assert adv.signature() != champion.signature()


def test_self_play_block_is_honest_when_empty():
    blk = sp.self_play_block([], universe={})
    assert blk["measured"] is False and blk["rounds"] == []
