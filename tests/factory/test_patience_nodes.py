"""R87 (Phase 7j) — the PATIENCE grammar nodes + the friction arithmetic.

Phase 7i sealed the judgment (R85: pay 3x friction; R86: full tape decides). Phase
7j supplies the missing lever — PATIENCE. These tests pin the new primitives: their
grammar typing/bounds, their emission through the sealed preamble, their CAUSALITY
(no bar after t may move a signal at or before t), and the R85 arithmetic report
that makes a near-miss a visible number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core import law
from app.pyramid.author import author2 as a2
from app.pyramid.author import grammar as g
from app.pyramid.author import shadow as sh
from app.pyramid.author import synth as sy
from app.pyramid.sandbox import static_gate


# ---------------------------------------------------------------------------
# Grammar: typing + bounds + singleton child.
# ---------------------------------------------------------------------------
def _programs():
    return [h.program for h in a2.patience_hypotheses()]


def test_patience_nodes_are_registered_primitives():
    for k in ("n_quiet_bars", "atr_quartile", "min_gap_bars", "bars_since_range"):
        assert k in g.PRIMITIVE_KINDS


def test_patience_bodies_are_valid_and_pass_the_static_gate():
    progs = _programs()
    assert len(progs) >= 8
    for p in progs:
        assert p.long.type == g.BOOL and p.short.type == g.BOOL
        assert static_gate.check_source(g.emit_python(p)).ok


def test_n_quiet_bars_rejects_out_of_range_params():
    g.node("n_quiet_bars", (12, 60, 0.8))  # legal
    with pytest.raises(g.GrammarError):
        g.node("n_quiet_bars", (2, 60, 0.8))      # bars below the floor of 4
    with pytest.raises(g.GrammarError):
        g.node("n_quiet_bars", (12, 60, 5.0))     # quiet out of range


def test_atr_quartile_rejects_out_of_range_bucket():
    g.node("atr_quartile", (120, 0.75))  # legal
    with pytest.raises(g.GrammarError):
        g.node("atr_quartile", (120, 0.2))  # bucket below 0.5
    with pytest.raises(g.GrammarError):
        g.node("atr_quartile", (120, 0.99))  # bucket above 0.95


def test_min_gap_bars_requires_exactly_one_bool_child():
    g.node("min_gap_bars", (20,), (g.node("day_of_week", (4,)),))  # legal
    with pytest.raises(g.GrammarError):
        g.node("min_gap_bars", (20,), ())


def test_synth_draws_the_new_nodes_in_random_bodies():
    seen = set()
    for i in range(400):
        p = sy.random_body(np.random.default_rng(i))
        src = g.emit_python(p)
        assert static_gate.check_source(src).ok
        for k in ("n_quiet_bars", "atr_quartile", "min_gap_bars", "bars_since_range"):
            if k in src:
                seen.add(k)
    assert seen == {"n_quiet_bars", "atr_quartile", "min_gap_bars", "bars_since_range"}


# ---------------------------------------------------------------------------
# Semantics: the helpers behave as their names promise.
# ---------------------------------------------------------------------------
def _helpers() -> dict:
    ns: dict = {}
    exec(compile(g.preamble_helpers(), "<patience_preamble>", "exec"), ns)
    return ns


def _flat_frame(n=600, vol=0.02, seed=7):
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, vol, n))
    high = close + np.abs(rng.normal(0.0, vol / 2, n))
    low = close - np.abs(rng.normal(0.0, vol / 2, n))
    return high, low, close


def test_min_gap_bars_enforces_the_spacing_floor():
    ns = _helpers()
    child = np.ones(100, dtype=bool)
    out = ns["_min_gap_bars"](child, 20)
    idx = np.nonzero(out)[0]
    assert idx.tolist() == [0, 20, 40, 60, 80]
    assert np.all(np.diff(idx) >= 20)


def test_n_quiet_bars_requires_every_recent_bar_calm():
    ns = _helpers()
    high, low, close = _flat_frame()
    # a storm at the end must void the gate for bars following it
    hs = high.copy()
    hs[-1] += 10.0
    quiet = ns["_n_quiet_bars"](hs, low, close, 3, 40, 0.5)
    # the last bar is a storm -> the bar that would look back over it cannot fire
    assert not quiet[-1]


def test_atr_quartile_selects_a_minority_of_bars():
    ns = _helpers()
    high, low, close = _flat_frame(n=2000)
    mask = ns["_atr_quartile"](high, low, close, 160, 0.75)
    frac = float(mask[200:].mean())
    assert 0.10 <= frac <= 0.40  # a real regime gate, not all-or-nothing


def test_bars_since_range_is_a_coiledness_in_unit_interval():
    ns = _helpers()
    high, low, close = _flat_frame(n=1000)
    clock = ns["_bars_since_range"](high, low, close, 48)
    finite = clock[np.isfinite(clock)]
    assert finite.size and finite.min() >= 0.0 and finite.max() <= 1.0


# ---------------------------------------------------------------------------
# Causality: no patience node may read a bar after t (the standing institution).
# ---------------------------------------------------------------------------
def _patience_probe(high, low, close):
    n = len(close)
    ns = _helpers()
    q = ns["_n_quiet_bars"](high, low, close, 12, 60, 0.7)
    a = ns["_atr_quartile"](high, low, close, 120, 0.75)
    mg = ns["_min_gap_bars"](q, 8)
    clk = ns["_bars_since_range"](high, low, close, 48)
    return np.array(q, dtype=bool), np.array(a, dtype=bool), \
        np.array(mg, dtype=bool), np.array(clk, dtype=float)


@pytest.mark.parametrize("mode", ["scale", "zero", "shuffle"])
@pytest.mark.parametrize("t", [300, 600, 900, 1198])
def test_patience_nodes_never_leak_the_future(mode, t):
    rng = np.random.default_rng(12345)
    n = 1200
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.3, n))
    high = close + np.abs(rng.normal(0.0, 0.25, n))
    low = close - np.abs(rng.normal(0.0, 0.25, n))
    base = _patience_probe(high, low, close)

    h2, l2, c2 = high.copy(), low.copy(), close.copy()
    seg = slice(t + 1, n)
    if mode == "scale":
        h2[seg] = h2[seg] * 3.0 + 1000.0
        l2[seg] = l2[seg] * 3.0 + 1000.0
        c2[seg] = c2[seg] * 3.0 + 1000.0
    elif mode == "zero":
        h2[seg] = 0.0
        l2[seg] = 0.0
        c2[seg] = 0.0
    else:
        h2[seg] = rng.permutation(h2[seg])
        l2[seg] = rng.permutation(l2[seg])
        c2[seg] = rng.permutation(c2[seg])
    mut = _patience_probe(h2, l2, c2)

    for k, (b, m) in enumerate(zip(base, mut)):
        if b.dtype == bool:
            assert np.array_equal(b[: t + 1], m[: t + 1]), (
                f"patience output[{k}] leaked future at t={t} mode={mode!r}")
        else:
            assert np.array_equal(b[: t + 1], m[: t + 1], equal_nan=True), (
                f"patience output[{k}] leaked future at t={t} mode={mode!r}")


def test_patience_emitted_body_shadow_equivalent_on_a_frame():
    """The emitted body's masks equal the native shadow — the R35 contract."""
    p = a2.patience_hypotheses()[1].program  # p_vol_realm_trend
    src = g.emit_python(p)
    high, low, close = _flat_frame(n=500)
    frame = pd.DataFrame({
        "open": close, "high": high, "low": low, "close": close,
        "volume": np.full(close.size, 1000.0),
        "ts": (1_700_000_000 + np.arange(close.size) * 900).astype("int64"),
    })
    tree = sh.evaluate_tree(p, frame, genes={"__pip__": 0.0001, "__pair__": "EURUSD"})
    body = sh.evaluate_source(src, frame, genes={"__pip__": 0.0001, "__pair__": "EURUSD"})
    eq = sh.equivalence(body.long, body.short, tree)
    assert eq.ok


# ---------------------------------------------------------------------------
# R85 (Phase 7j) — the friction arithmetic report.
# ---------------------------------------------------------------------------
def test_friction_breakdown_reports_a_near_miss_as_a_number():
    # the Phase 7i best: gross 1.283x friction. Show the distance, not a silence.
    # gross 128.3, friction 100 -> net 28.3 -> paid 1.283 < 3.0
    d = law.friction_breakdown(128.3, 28.3)
    assert d["gate_ok"] is False
    assert d["paid_multiple"] == pytest.approx(1.283, abs=1e-3)
    assert d["breakeven_ratio"] == law.FRICTION_MULTIPLE
    assert d["distance_from_bar"] == pytest.approx(1.283 - 3.0, abs=1e-3)
    # the extra gross R needed to reach 3x on this friction: 3*100 - 128.3
    assert d["gap_to_bar_r"] == pytest.approx(171.7, abs=1e-1)


def test_friction_breakdown_gap_is_zero_when_the_bar_is_cleared():
    d = law.friction_breakdown(1000.0, 700.0)  # paid 3.333 >= 3.0
    assert d["gate_ok"] is True
    assert d["gap_to_bar_r"] == 0.0
    assert d["distance_from_bar"] > 0.0


def test_friction_breakdown_zero_friction_is_reported_not_hidden():
    d = law.friction_breakdown(50.0, 50.0)
    assert d["paid_multiple"] is None        # inf is not a JSON number
    assert d["gate_ok"] is False


def test_friction_breakdown_agrees_with_the_sealed_verdict():
    for gross, net in ((100.0, 80.0), (1000.0, -2840.0), (-5.0, -5.0),
                       (60.0, 40.0), (59.99, 39.99), (50.0, 50.0)):
        v = law.gross_to_friction_verdict(gross, net)
        d = law.friction_breakdown(gross, net)
        assert d["gate_ok"] is bool(v.ok)
        assert d["reason"] == v.reason
