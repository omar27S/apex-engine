"""THE SYNTH — random bodies, mutation, and crossover (Phase 4b).

All three are deterministic under a seeded ``numpy.random.Generator``; every
product is a valid :class:`grammar.Program` (construction validates typing,
bounds, depth and leaf count). A depth-aware generator guarantees BOTH
directions (long and short) are always constructible: a program is only built
when both sides reach a bool, else the draw is retried a bounded number of
times (never an infinite loop, Build Mode).

Lineage: :func:`signature` is a stable hash of the emitted source, so two
structurally different bodies never collide and a mutation is visible.
"""

from __future__ import annotations

import hashlib

import numpy as np

from app.pyramid.author import grammar as g

__all__ = [
    "random_body",
    "mutate_body",
    "crossover_body",
    "signature",
    "TREE_MAX_ATTEMPTS",
]

TREE_MAX_ATTEMPTS = 64  # bounded retry for a type-valid draw (never unbounded)

_SERIES_LEAVES = tuple(k for k in g.SERIES_KINDS if k != "arith")
_ARITH_OPS = ("+", "-", "*", "/")
_COMPARE_OPS = (">", "<", ">=", "<=")


def signature(source: str) -> str:
    """A stable body id: SHA-256 of the emitted source."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Params.
# ---------------------------------------------------------------------------
def _series_leaf(rng) -> g.Node:
    k = str(rng.choice(_SERIES_LEAVES))
    if k in ("ema", "rsi", "atr", "donchian_pos", "zscore", "vwap_dev", "absret_pct"):
        return g.node(k, (int(rng.integers(3, 60)),))
    if k == "macd_hist":
        fast = int(rng.integers(3, 20))
        slow = fast + int(rng.integers(3, 30))
        return g.node(k, (fast, slow, int(rng.integers(2, 12))))
    if k in ("bb_dist", "keltner_dist"):
        return g.node(k, (int(rng.integers(10, 60)), float(round(rng.uniform(0.5, 3.0), 3))))
    if k == "hurst_pct":
        return g.node(k, (int(rng.integers(30, 200)), int(rng.integers(50, 500))))
    if k == "session_vwap_dist":
        return g.node(k)
    # --- R81/R82/R83 (Phase 7h) new series leaves ---------------------------
    if k == "dist_round":
        return g.node(k, (int(rng.choice((25, 50, 100))),))
    if k == "prior_day_dir":
        return g.node(k)
    if k == "prior_day_atr_pct":
        return g.node(k, (int(rng.integers(20, 200)),))
    if k == "gap_pips":
        return g.node(k)
    if k == "dxy_proxy":
        return g.node(k, (int(rng.integers(3, 60)),))
    if k == "dxy_ret":
        return g.node(k, (int(rng.integers(0, 48)),))
    if k == "dxy_corr":
        return g.node(k, (int(rng.integers(30, 200)),))
    # --- R87 (Phase 7j) patience series leaf --------------------------------
    if k == "bars_since_range":
        return g.node(k, (int(rng.integers(10, 200)),))
    # --- R89 (Phase 7k) gross-edge series leaves ----------------------------
    if k == "vol_displacement":
        return g.node(k, (int(rng.integers(8, 240)),))
    if k == "pullback_depth":
        return g.node(k, (int(rng.integers(12, 200)),))
    raise g.GrammarError(f"no draw rule for series leaf {k!r}")


def _scalar(rng) -> g.Node:
    if rng.random() < 0.5:
        role = str(rng.choice(tuple(g.GRAMMAR_CONST_RANGES)))
        lo, hi = g.GRAMMAR_CONST_RANGES[role]
        return g.node("const", (role, float(round(rng.uniform(lo, hi), 3))))
    from app.quant.genome import GENE_BOUNDS_BY_NAME

    names = tuple(sorted(GENE_BOUNDS_BY_NAME))
    return g.node("gene", (str(rng.choice(names)),))


def _series(rng, depth: int) -> g.Node:
    """Draw a series node, bounded by depth."""
    if depth <= 0 or rng.random() < 0.55:
        return _series_leaf(rng)
    op = str(rng.choice(_ARITH_OPS))
    a = _series_or_scalar(rng, depth - 1)
    b = _series_or_scalar(rng, depth - 1)
    # arith requires at least one series operand to stay a series.
    if a.type != g.SERIES and b.type != g.SERIES:
        a = _series_leaf(rng)
    return g.node("arith", (op,), (a, b))


def _series_or_scalar(rng, depth: int) -> g.Node:
    if rng.random() < 0.7:
        return _series(rng, depth)
    return _scalar(rng)


def _bool(rng, depth: int) -> g.Node:
    """Draw a bool node. Depth bounded, retried by the caller if it stays too deep."""
    if depth <= 0:
        return _compare(rng, 0)
    r = rng.random()
    if r < 0.4:
        return _compare(rng, depth - 1)
    if r < 0.5:
        return g.node("crosses_above", (), (_series(rng, depth - 1), _series(rng, depth - 1)))
    if r < 0.6:
        return g.node("crosses_below", (), (_series(rng, depth - 1), _series(rng, depth - 1)))
    if r < 0.68:
        return g.node("session", (int(rng.integers(1, 4)),))
    if r < 0.76:
        h0 = int(rng.integers(0, 20))
        return g.node("killzone", (h0, h0 + int(rng.integers(1, 5))))
    # --- R81 calendar / price-level bool leaves -----------------------------
    if r < 0.80:
        return g.node("day_of_week", (int(rng.integers(0, 7)),))
    if r < 0.83:
        lo = int(rng.integers(1, 28))
        return g.node("day_of_month", (lo, lo + int(rng.integers(0, 4))))
    if r < 0.855:
        return g.node("nth_weekday", (int(rng.integers(1, 6)), int(rng.integers(0, 7))))
    if r < 0.875:
        return g.node("jpy_holiday_window", (int(rng.integers(0, 3)), int(rng.integers(0, 3))))
    if r < 0.90:
        return g.node("round_number_hit", (int(rng.choice((25, 50, 100))),
                                           float(round(rng.uniform(2.0, 15.0), 2))))
    # --- R83 gap -----------------------------------------------------------------
    if r < 0.915:
        return g.node("gap_open", (float(round(rng.uniform(5.0, 40.0), 2)),))
    # --- R82 cross-instrument lagged reaction ------------------------------------
    if r < 0.93:
        return g.node("dxy_lag_align", (int(rng.integers(0, 24)),))
    # --- R87 (Phase 7j) patience bool nodes ---------------------------------
    if r < 0.95:
        return g.node("n_quiet_bars", (int(rng.integers(6, 40)),
                                       int(rng.integers(20, 160)),
                                       float(round(rng.uniform(0.4, 1.0), 2))))
    if r < 0.965:
        return g.node("atr_quartile", (int(rng.integers(40, 260)),
                                       float(round(rng.uniform(0.6, 0.9), 2))))
    if r < 0.975:
        return g.node("min_gap_bars", (int(rng.integers(2, 24)),),
                      (_bool(rng, depth - 1),))
    # --- R89 (Phase 7k) gross-edge bool node --------------------------------
    if r < 0.982:
        return g.node("session_boundary_reversal",
                      (float(round(rng.uniform(1.0, 3.0), 2)),),
                      (_series(rng, depth - 1),))
    if r < 0.99:
        return g.node("not", (), (_bool(rng, depth - 1),))
    combinator = "and" if rng.random() < 0.5 else "or"
    return g.node(combinator, (), (_bool(rng, depth - 1), _bool(rng, depth - 1)))


def _compare(rng, depth: int) -> g.Node:
    op = str(rng.choice(_COMPARE_OPS))
    a = _series_or_scalar(rng, max(0, depth))
    b = _series_or_scalar(rng, max(0, depth))
    # compare requires at least one series operand.
    if a.type != g.SERIES and b.type != g.SERIES:
        a = _series_leaf(rng)
    return g.node("compare", (op,), (a, b))


# ---------------------------------------------------------------------------
# Public: random_body.
# ---------------------------------------------------------------------------
def random_body(rng, *, concept: str = "synthesized", max_depth: int | None = None) -> g.Program:
    """A fresh valid program. Retries (bounded) until both sides type-check."""
    top = g.GRAMMAR_MAX_DEPTH - 1 if max_depth is None else max_depth
    for _ in range(TREE_MAX_ATTEMPTS):
        depth = int(rng.integers(1, top + 1))
        long_n = _bool(rng, depth)
        short_n = _bool(rng, depth)
        try:
            return g.Program(long=long_n, short=short_n, concept=concept)
        except g.GrammarError:
            continue
    # A deterministic, minimal fallback (never a crash, always legal).
    return _minimal_program(concept)


def _minimal_program(concept: str) -> g.Program:
    long_n = g.node("compare", (">",), (_series_leaf(np.random.default_rng(0)),
                                        g.node("const", ("threshold", 0.0))))
    short_n = g.node("compare", ("<",), (_series_leaf(np.random.default_rng(1)),
                                          g.node("const", ("threshold", 0.0))))
    return g.Program(long=long_n, short=short_n, concept=concept)


# ---------------------------------------------------------------------------
# Mutation and crossover: operate on the typed tree, type-preserving.
# ---------------------------------------------------------------------------
def _nodes(n: g.Node, path: tuple = ()) -> list[tuple[tuple, g.Node]]:
    out = [(path, n)]
    for i, c in enumerate(n.children):
        out.extend(_nodes(c, path + (i,)))
    return out


def _replace(root: g.Node, path: tuple, new: g.Node) -> g.Node:
    if not path:
        return new
    idx = path[0]
    children = list(root.children)
    children[idx] = _replace(children[idx], path[1:], new)
    return g.node(root.kind, root.params, tuple(children))


def mutate_body(program: g.Program, rng) -> g.Program:
    """A mutated copy: subtree replacement or parameter jitter, type-preserving.

    A subtree is only replaced by a node of the SAME type, so the tree stays
    well-typed; construction re-validates bounds/depth/leaves. Deterministic.
    """
    side = "long" if rng.random() < 0.5 else "short"
    root = getattr(program, side)
    candidates = _nodes(root)
    path, target = candidates[int(rng.integers(0, len(candidates)))]
    new_node = _mutate_node(target, rng)
    try:
        rebuilt = _replace(root, path, new_node)
        if side == "long":
            return g.Program(long=rebuilt, short=program.short, concept=program.concept)
        return g.Program(long=program.long, short=rebuilt, concept=program.concept)
    except g.GrammarError:
        return program  # a mutation that breaks the grammar is a no-op, not a crash


def _mutate_node(n: g.Node, rng) -> g.Node:
    t = n.type
    if t == g.SERIES:
        return _series(rng, 2)
    if t == g.SCALAR:
        return _scalar(rng)
    return _bool(rng, 2)


def crossover_body(a: g.Program, b: g.Program, rng) -> g.Program:
    """Typed subtree swap: take a node of the matching type from ``b`` into ``a``.

    Deterministic. If no compatible socket exists the parent is returned
    unchanged (a legal, honest no-op).
    """
    for _ in range(TREE_MAX_ATTEMPTS):
        side = "long" if rng.random() < 0.5 else "short"
        root_a = getattr(a, side)
        root_b = getattr(b, side)
        cand_a = _nodes(root_a)
        target = cand_a[int(rng.integers(0, len(cand_a)))]
        path, node_a = target
        want = node_a.type
        donors = [nd for _, nd in _nodes(root_b) if nd.type == want]
        if not donors:
            continue
        donor = donors[int(rng.integers(0, len(donors)))]
        try:
            rebuilt = _replace(root_a, path, donor)
            if side == "long":
                return g.Program(long=rebuilt, short=a.short, concept=a.concept)
            return g.Program(long=a.long, short=rebuilt, concept=a.concept)
        except g.GrammarError:
            continue
    return a
