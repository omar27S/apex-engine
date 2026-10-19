"""R93/R94 (Phase 7m) — THE CHAMPION CANDIDATE: c_long + the champion reducers.

Phase 7m promotes Session 6.0's ``c_long`` (net-positive on ALL SEVEN majors under
local adaptation) to champion-candidate status and builds the dossier the Council
needs. These tests pin, WITHOUT a tape:

* the candidate BODY is long-only (its short leg is structurally impossible) and
  reproduces the winner's gene vector (z(40) | 1.5, rsi gene band, gap window);
* the local-adaptation gap set is the deliberate ``(2048, 3072, 4096)`` grid;
* the pure reducers — ``bootstrap_distribution`` (the tail-luck test),
  ``classify_year`` (vol / trend / range) — are deterministic and honest;
* the RAMS cage path is ADDITIVE: ``rams_evaluate`` accepts ``cage_masks`` and the
  sealed genome dispatch is byte-for-byte unchanged when it is ``None``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.quant.rams import report as rams
from app.pyramid.author import grammar as g
from app.pyramid.sandbox import static_gate
from tools import champion_session_7 as s7


def _kinds(tree) -> list[str]:
    out = [tree.kind]
    for c in tree.children:
        out.extend(_kinds(c))
    return out


# ---------------------------------------------------------------------------
# The candidate body.
# ---------------------------------------------------------------------------
def test_candidate_body_is_static_gate_clean():
    for gap in s7.LOCAL_GAPS:
        src = g.emit_python(s7.candidate_body(gap))
        assert static_gate.check_source(src).ok


def test_candidate_body_is_long_only():
    prog = s7.candidate_body(3072)
    # the short tree ANDs an always-false gate (ATR < -1) — structurally dead.
    assert prog.long.kind == "min_gap_bars"
    assert prog.short.kind == "min_gap_bars"
    assert "atr" in _kinds(prog.short)


def test_candidate_body_reproduces_the_winner_gene_vector():
    prog = s7.candidate_body(3072)
    assert int(prog.long.params[0]) == 3072
    kinds = _kinds(prog.long)
    assert "zscore" in kinds and "rsi" in kinds


def test_local_gap_grid_is_deliberate():
    assert s7.LOCAL_GAPS == (2048, 3072, 4096)


def test_gap_lever_moves_only_the_spacing():
    a = s7.candidate_body(2048)
    b = s7.candidate_body(4096)
    assert _kinds(a.long) == _kinds(b.long)
    assert int(a.long.params[0]) == 2048 and int(b.long.params[0]) == 4096


# ---------------------------------------------------------------------------
# The pure reducers.
# ---------------------------------------------------------------------------
def test_bootstrap_distribution_is_deterministic():
    rs = [1.0, -1.0, 2.0, -0.5, 3.0]
    a = s7.bootstrap_distribution(rs, horizon_trades=100, draws=200, seed=7)
    b = s7.bootstrap_distribution(rs, horizon_trades=100, draws=200, seed=7)
    assert a == b
    assert 0.0 <= a["p_positive"] <= 1.0
    assert a["p05"] <= a["median"] <= a["p95"]


def test_bootstrap_of_a_losing_stream_is_negative():
    rs = [-1.0, -0.5, -2.0]
    d = s7.bootstrap_distribution(rs, horizon_trades=50, draws=300, seed=1)
    assert d["mean"] < 0 and d["p_positive"] == 0.0


def test_bootstrap_empty_is_safe():
    d = s7.bootstrap_distribution([], horizon_trades=10)
    assert d["n"] == 0 and d["p_positive"] == 0.0


def test_classify_year_labels_a_violent_year_as_vol():
    rng = np.random.default_rng(3)
    close = 1.0 + np.cumsum(rng.normal(0, 0.002, 2000))
    frame = pd.DataFrame({"close": close})
    lbl = s7.classify_year(frame, vol_hi=0.0005, er_trend=1.0, er_range=0.0)
    assert lbl["regime"] == "vol" and lbl["vol"] >= 0.0005


def test_classify_year_labels_a_clean_trend_as_trend():
    close = np.linspace(1.0, 1.5, 2000)  # a straight line: ER == 1.0
    frame = pd.DataFrame({"close": close})
    lbl = s7.classify_year(frame, vol_hi=1.0, er_trend=0.5, er_range=0.2)
    assert lbl["regime"] == "trend" and lbl["er"] == 1.0


def test_classify_year_labels_a_flat_year_as_range():
    close = 1.0 + np.tile([0.0, 1e-5], 1000)  # oscillates in place: ER ~ 0
    frame = pd.DataFrame({"close": close})
    lbl = s7.classify_year(frame, vol_hi=1.0, er_trend=0.5, er_range=0.2)
    assert lbl["regime"] == "range"


# ---------------------------------------------------------------------------
# The RAMS cage path is additive (R93): the sealed dispatch is untouched.
# ---------------------------------------------------------------------------
def test_rams_evaluate_accepts_cage_masks_keyword():
    import inspect
    sig = inspect.signature(rams.rams_evaluate)
    assert "cage_masks" in sig.parameters
    assert inspect.signature(rams.gauntlet_row).parameters["cage_masks"].default is None
    assert (inspect.signature(rams.survivability_verdict_multi)
            .parameters["cage_masks"].default is None)


def test_cage_masks_none_leaves_the_call_path_unchanged():
    # The mask plumbing is a pure pass-through: when no masks are supplied the
    # evaluator receives an empty ``signals_by_pair`` (the sealed dispatch runs).
    from app.quant import evaluator as ev
    captured = {}
    real = ev.evaluate

    def spy(genome, frames, config=None, **kw):
        captured["signals_by_pair"] = kw.get("signals_by_pair")
        raise RuntimeError("stop here")

    import pytest
    ev.evaluate = spy
    try:
        with pytest.raises(RuntimeError):
            rams.rams_evaluate(_genome(), _tiny_universe())
    finally:
        ev.evaluate = real
    assert captured["signals_by_pair"] == {}


def _genome():
    from app.quant.genome import StrategyGenome
    return StrategyGenome()


def _tiny_universe():
    from app.quant import frames as fr
    m15 = pd.DataFrame({
        "ts": np.arange(0, 600, 60, dtype="int64"),
        "open": np.linspace(1.0, 1.1, 10),
        "high": np.linspace(1.001, 1.101, 10),
        "low": np.linspace(0.999, 1.099, 10),
        "close": np.linspace(1.0, 1.1, 10),
        "volume": np.full(10, 100.0),
    })
    return {"EURUSD": fr.build_frames(m15, "EURUSD", 0.0001)}
