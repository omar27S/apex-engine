"""THE GRAMMAR — a typed AST of causal signal primitives (Phase 4b, R31).

The Author (``synth``) NEVER free-types Python. It composes bodies from this
TYPED grammar; a tree that violates the typing rules cannot be constructed, and
:func:`emit_python` turns a valid tree into real Python source that honors the
Phase-4a body protocol and passes the R31 static gate.

TYPING (strong, checked at construction):

    series  x series  -> series  (elementwise)
    series  x scalar  -> series
    series            -> bool    (via a comparison)
    bool    x bool    -> bool

The OUTPUT of a body tree is exactly ``(long_bool, short_bool)`` — a
:class:`Program`. Depth and leaf count are sealed constants; a tree outside them
raises at construction, so an invalid tree cannot exist.

DETERMINISM. ``emit_python`` is a pure function of the tree: the same tree emits
byte-identical source. No timestamps, no dict ordering, no randomness.

PURITY. This module builds strings and validates dataclasses. It does no I/O at
import and imports no service. It reads the gene NAME SET from
``app.quant.genome`` (to bound ``gene`` references) — a pure import.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Node",
    "Program",
    "GrammarError",
    "GRAMMAR_MAX_DEPTH",
    "GRAMMAR_MAX_LEAVES",
    "GRAMMAR_CONST_RANGES",
    "SERIES_KINDS",
    "SCALAR_KINDS",
    "BOOL_KINDS",
    "PRIMITIVE_KINDS",
    "node",
    "validate",
    "emit_python",
    "PROTOCOL_PREAMBLE",
]

# --- sealed grammar bounds (one declaration; pinned by test) ---------------
GRAMMAR_MAX_DEPTH = 6
GRAMMAR_MAX_LEAVES = 24

# Bounded-constant ranges, keyed by ROLE (per-node-type range). A scalar const's
# value MUST come from one of these ranges — a grammar can never invent a wild
# threshold.
GRAMMAR_CONST_RANGES: dict[str, tuple[float, float]] = {
    "threshold": (-4.0, 4.0),
    "period_scale": (0.0, 1.0),
    "level": (0.0, 1.0),
}

SERIES = "series"
SCALAR = "scalar"
BOOL = "bool"

_TYPES = (SERIES, SCALAR, BOOL)


class GrammarError(ValueError):
    """A tree violated the grammar. Raised at construction, never later."""


# ---------------------------------------------------------------------------
# Node primitives. Each spec declares its child TYPES (in order) and its own
# output type. Params are validated against a per-kind rule.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Spec:
    out: str
    inputs: tuple[str, ...] = ()
    params: str = ""


SERIES_KINDS: dict[str, _Spec] = {
    "ema": _Spec(SERIES, params="period:int"),
    "rsi": _Spec(SERIES, params="period:int"),
    "atr": _Spec(SERIES, params="period:int"),
    "macd_hist": _Spec(SERIES, params="fast:int,slow:int,signal:int"),
    "bb_dist": _Spec(SERIES, params="period:int,k:float"),
    "donchian_pos": _Spec(SERIES, params="period:int"),
    "keltner_dist": _Spec(SERIES, params="period:int,k:float"),
    "zscore": _Spec(SERIES, params="period:int"),
    "hurst_pct": _Spec(SERIES, params="window:int,rank_window:int"),
    "vwap_dev": _Spec(SERIES, params="period:int"),
    "session_vwap_dist": _Spec(SERIES, params=""),
    "absret_pct": _Spec(SERIES, params="period:int"),
    "arith": _Spec(SERIES, inputs=(SERIES, SERIES), params="op:str"),
    # --- R81 (Phase 7h) — price-level nodes ---------------------------------
    "dist_round": _Spec(SERIES, params="step_pips:int"),
    # --- R83 (Phase 7h) — prior-day context ---------------------------------
    "prior_day_dir": _Spec(SERIES, params=""),
    "prior_day_atr_pct": _Spec(SERIES, params="period:int"),
    "gap_pips": _Spec(SERIES, params=""),
    # --- R82 (Phase 7h) — cross-instrument sensors (read-only) --------------
    "dxy_proxy": _Spec(SERIES, params="period:int"),
    "dxy_ret": _Spec(SERIES, params="lag:int"),
    "dxy_corr": _Spec(SERIES, params="window:int"),
    # --- R87 (Phase 7j) — patience: the "structured pullback" clock ---------
    "bars_since_range": _Spec(SERIES, params="window:int"),
    # --- R89 (Phase 7k) — gross-edge: signed move + pullback geometry --------
    # (i) multi-day displacement: the signed distance price has traveled from
    #     its origin ``window`` closed bars back, in units of the current ATR —
    #     the "entry only after price travels > 2x ATR" distance measure.
    "vol_displacement": _Spec(SERIES, params="window:int"),
    # (ii) pullback depth in [0, 1]: where the close sits inside its trailing
    #      ``window`` range (1 = at the window low, 0 = at the window high) — the
    #      geometry of a pullback INTO a trend, the gross-fat entry location.
    "pullback_depth": _Spec(SERIES, params="window:int"),
}

SCALAR_KINDS: dict[str, _Spec] = {
    "const": _Spec(SCALAR, params="role:str,value:float"),
    "gene": _Spec(SCALAR, params="name:str"),
}

BOOL_KINDS: dict[str, _Spec] = {
    "compare": _Spec(BOOL, params="op:str"),
    "crosses_above": _Spec(BOOL, inputs=(SERIES, SERIES)),
    "crosses_below": _Spec(BOOL, inputs=(SERIES, SERIES)),
    "and": _Spec(BOOL, inputs=(BOOL, BOOL)),
    "or": _Spec(BOOL, inputs=(BOOL, BOOL)),
    "not": _Spec(BOOL, inputs=(BOOL,)),
    "session": _Spec(BOOL, params="session_id:int"),
    "killzone": _Spec(BOOL, params="start_hour:int,end_hour:int"),
    # --- R81 (Phase 7h) — calendar nodes -----------------------------------
    "day_of_week": _Spec(BOOL, params="dow:int"),
    "day_of_month": _Spec(BOOL, params="lo:int,hi:int"),
    "nth_weekday": _Spec(BOOL, params="n:int,dow:int"),
    "jpy_holiday_window": _Spec(BOOL, params="days_before:int,days_after:int"),
    "round_number_hit": _Spec(BOOL, params="step_pips:int,tol_pips:float"),
    # --- R83 (Phase 7h) — prior-day context ---------------------------------
    "gap_open": _Spec(BOOL, params="min_pips:float"),
    # --- R82 (Phase 7h) — cross-instrument lagged reaction ------------------
    "dxy_lag_align": _Spec(BOOL, params="lag:int"),
    # --- R87 (Phase 7j) — PATIENCE NODES -----------------------------------
    # (a) n-quiet-bars-then-event: fire only after ``bars`` calm bars (a bar is
    #     calm when its range is within the quiet fraction of the rolling window).
    "n_quiet_bars": _Spec(BOOL, params="bars:int,window:int,quiet:float"),
    # (c) regime-gated firing: trade only when the current ATR sits in the top
    #     ``bucket`` (0-1) of its own trailing history — volatile-realm access.
    "atr_quartile": _Spec(BOOL, params="window:int,bucket:float"),
    # (d) no-clustering: at least ``bars`` bars since the last occurrence of the
    #     child signal (min distance between entries; friction compounds per entry).
    "min_gap_bars": _Spec(BOOL, inputs=(BOOL,), params="bars:int"),
    # --- R89 (Phase 7k) — THE GROSS-EDGE HUNT -------------------------------
    # (e) session-boundary reversal: fire on a strong directional move right at a
    #     session boundary (the 24h/8h/16h/21h events), fading a stretched leg.
    #     ``front`` is the signed move scale (e.g. zscore); ``fade`` its threshold.
    "session_boundary_reversal": _Spec(BOOL, inputs=(SERIES,), params="fade:float"),
}

PRIMITIVE_KINDS: dict[str, _Spec] = {**SERIES_KINDS, **SCALAR_KINDS, **BOOL_KINDS}

_COMPARE_OPS = {">", "<", ">=", "<="}
_ARITH_OPS = {"+", "-", "*", "/"}


def _gene_names() -> frozenset[str]:
    from app.quant.genome import GENE_BOUNDS_BY_NAME

    return frozenset(GENE_BOUNDS_BY_NAME)


@dataclass(frozen=True)
class Node:
    """One typed node of the grammar. Validates itself on construction."""

    kind: str
    params: tuple = ()
    children: tuple["Node", ...] = ()

    def __post_init__(self):
        spec = PRIMITIVE_KINDS.get(self.kind)
        if spec is None:
            raise GrammarError(f"unknown node kind {self.kind!r}")
        got = tuple(c.type for c in self.children)
        if self.kind in ("compare", "arith"):
            for t in got:
                if t not in (SERIES, SCALAR):
                    raise GrammarError(f"{self.kind} operands must be series or scalar")
            if SERIES not in got:
                raise GrammarError(
                    f"{self.kind} needs at least one series operand (two scalars is meaningless)"
                )
        elif got != spec.inputs:
            raise GrammarError(
                f"{self.kind}: expected child types {spec.inputs}, got {got}"
            )
        self._validate_params()
        depth, leaves = _shape(self)
        if depth > GRAMMAR_MAX_DEPTH:
            raise GrammarError(f"tree depth {depth} exceeds {GRAMMAR_MAX_DEPTH}")
        if leaves > GRAMMAR_MAX_LEAVES:
            raise GrammarError(f"leaf count {leaves} exceeds {GRAMMAR_MAX_LEAVES}")

    @property
    def type(self) -> str:
        return PRIMITIVE_KINDS[self.kind].out

    def _validate_params(self):
        p = self.params
        if self.kind in ("ema", "rsi", "atr", "donchian_pos", "zscore", "vwap_dev",
                         "absret_pct"):
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 2, 400)
        elif self.kind == "macd_hist":
            _need_int(self.kind, p, 3)
            _range_int(self.kind, p[0], 2, 60)
            _range_int(self.kind, p[1], 3, 120)
            if p[0] >= p[1]:
                raise GrammarError("macd_hist fast must be < slow")
            _range_int(self.kind, p[2], 2, 60)
        elif self.kind in ("bb_dist", "keltner_dist"):
            _need_float(self.kind, p, 2)
            _range_int(self.kind, p[0], 2, 200)
            if not (0.2 <= float(p[1]) <= 5.0):
                raise GrammarError(f"{self.kind} k out of range: {p[1]}")
        elif self.kind == "hurst_pct":
            _need_int(self.kind, p, 2)
            _range_int(self.kind, p[0], 20, 400)
            _range_int(self.kind, p[1], 20, 1000)
        elif self.kind == "session_vwap_dist":
            if p:
                raise GrammarError("session_vwap_dist takes no params")
        elif self.kind == "arith":
            if len(p) != 1 or p[0] not in _ARITH_OPS:
                raise GrammarError(f"arith op invalid: {p!r}")
        elif self.kind == "const":
            _need_float(self.kind, p, 2)
            role = str(p[0])
            if role not in GRAMMAR_CONST_RANGES:
                raise GrammarError(f"unknown const role {role!r}")
            lo, hi = GRAMMAR_CONST_RANGES[role]
            if not (lo <= float(p[1]) <= hi):
                raise GrammarError(f"const {p[1]} outside role {role} range [{lo},{hi}]")
        elif self.kind == "gene":
            if len(p) != 1 or str(p[0]) not in _gene_names():
                raise GrammarError(f"unknown gene reference {p!r}")
        elif self.kind in ("compare", "crosses_above", "crosses_below"):
            if self.kind == "compare":
                if len(p) != 1 or p[0] not in _COMPARE_OPS:
                    raise GrammarError(f"compare op invalid: {p!r}")
            elif p:
                raise GrammarError(f"{self.kind} takes no params")
        elif self.kind in ("and", "or", "not"):
            if p:
                raise GrammarError(f"{self.kind} takes no params")
            if self.kind == "not" and len(self.children) != 1:
                raise GrammarError("not takes exactly one child")
            if self.kind in ("and", "or") and len(self.children) != 2:
                raise GrammarError(f"{self.kind} takes exactly two children")
        elif self.kind == "session":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 1, 3)
        elif self.kind == "killzone":
            _need_int(self.kind, p, 2)
            _range_int(self.kind, p[0], 0, 23)
            _range_int(self.kind, p[1], 1, 24)
            if p[0] >= p[1]:
                raise GrammarError("killzone start must be < end")
        # --- R81 price-level / calendar ------------------------------------
        elif self.kind == "dist_round":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 5, 500)
        elif self.kind == "round_number_hit":
            if len(p) != 2:
                raise GrammarError("round_number_hit needs (step_pips, tol_pips)")
            _range_int(self.kind, p[0], 5, 500)
            tol = float(p[1])
            if not (0.0 < tol <= 50.0):
                raise GrammarError(f"round_number_hit tol out of range: {p[1]}")
        elif self.kind == "day_of_week":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 0, 6)
        elif self.kind == "day_of_month":
            _need_int(self.kind, p, 2)
            _range_int(self.kind, p[0], 1, 31)
            _range_int(self.kind, p[1], 1, 31)
            if p[0] > p[1]:
                raise GrammarError("day_of_month lo must be <= hi")
        elif self.kind == "nth_weekday":
            _need_int(self.kind, p, 2)
            _range_int(self.kind, p[0], 1, 5)
            _range_int(self.kind, p[1], 0, 6)
        elif self.kind == "jpy_holiday_window":
            _need_int(self.kind, p, 2)
            _range_int(self.kind, p[0], 0, 5)
            _range_int(self.kind, p[1], 0, 5)
        # --- R83 prior-day context -----------------------------------------
        elif self.kind == "prior_day_dir":
            if p:
                raise GrammarError("prior_day_dir takes no params")
        elif self.kind == "prior_day_atr_pct":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 5, 400)
        elif self.kind == "gap_pips":
            if p:
                raise GrammarError("gap_pips takes no params")
        elif self.kind == "gap_open":
            if len(p) != 1:
                raise GrammarError("gap_open needs (min_pips,)")
            minp = float(p[0])
            if not (0.0 <= minp <= 200.0):
                raise GrammarError(f"gap_open min_pips out of range: {p[0]}")
        # --- R82 cross-instrument sensors ----------------------------------
        elif self.kind == "dxy_proxy":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 2, 400)
        elif self.kind == "dxy_ret":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 0, 96)
        elif self.kind == "dxy_corr":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 20, 500)
        elif self.kind == "dxy_lag_align":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 0, 96)
        # --- R87 patience --------------------------------------------------
        elif self.kind == "bars_since_range":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 5, 400)
        elif self.kind == "n_quiet_bars":
            # (bars, window, quiet): fire after ``bars`` calm bars; a bar is calm
            # when its true range <= quiet * ATR(window).
            if len(p) != 3:
                raise GrammarError("n_quiet_bars needs (bars, window, quiet)")
            _range_int(self.kind, p[0], 4, 200)   # >= 4 (an hour of M15 patience floor)
            _range_int(self.kind, p[1], 10, 400)
            q = float(p[2])
            if not (0.1 <= q <= 1.2):
                raise GrammarError(f"n_quiet_bars quiet out of range: {p[2]}")
        elif self.kind == "atr_quartile":
            if len(p) != 2:
                raise GrammarError("atr_quartile needs (window, bucket)")
            _range_int(self.kind, p[0], 20, 500)
            b = float(p[1])
            if not (0.5 <= b <= 0.95):
                raise GrammarError(f"atr_quartile bucket out of range: {p[1]}")
        elif self.kind == "min_gap_bars":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 1, 8000)   # R89: allow ~5-entries/year spacing
        # --- R89 gross-edge hunt -------------------------------------------
        elif self.kind == "vol_displacement":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 4, 384)   # a multi-day displacement ref
        elif self.kind == "pullback_depth":
            _need_int(self.kind, p, 1)
            _range_int(self.kind, p[0], 8, 400)
        elif self.kind == "session_boundary_reversal":
            if len(p) != 1:
                raise GrammarError("session_boundary_reversal needs (fade,)")
            f = float(p[0])
            if not (0.5 <= f <= 4.0):
                raise GrammarError(f"session_boundary_reversal fade out of range: {p[0]}")


def _need_int(kind, p, n):
    if len(p) != n or any(not isinstance(v, int) or isinstance(v, bool) for v in p):
        raise GrammarError(f"{kind}: expected {n} int param(s), got {p!r}")


def _need_float(kind, p, n):
    if len(p) != n:
        raise GrammarError(f"{kind}: expected {n} param(s), got {p!r}")
    if isinstance(p[0], bool):
        raise GrammarError(f"{kind}: param 0 must not be bool")
    if not isinstance(p[1], (int, float)) or isinstance(p[1], bool):
        raise GrammarError(f"{kind}: param 1 must be numeric")


def _range_int(kind, value, lo, hi):
    if not (lo <= int(value) <= hi):
        raise GrammarError(f"{kind}: param {value} outside [{lo},{hi}]")


def _shape(n: Node) -> tuple[int, int]:
    if not n.children:
        return 1, 1
    depths, leaves = [], 0
    for c in n.children:
        d, l = _shape(c)
        depths.append(d)
        leaves += l
    return 1 + max(depths), leaves


def node(kind: str, params=(), children=()) -> Node:
    """Construct a validated :class:`Node` (convenience, same rules)."""
    return Node(kind, tuple(params), tuple(children))


@dataclass(frozen=True)
class Program:
    """A complete body tree: the long and short bool programs."""

    long: Node
    short: Node
    concept: str = ""

    def __post_init__(self):
        if self.long.type != BOOL or self.short.type != BOOL:
            raise GrammarError("Program.long and Program.short must be bool nodes")
        d = max(_shape(self.long)[0], _shape(self.short)[0])
        l = _shape(self.long)[1] + _shape(self.short)[1]
        if d > GRAMMAR_MAX_DEPTH:
            raise GrammarError(f"program depth {d} exceeds {GRAMMAR_MAX_DEPTH}")
        if l > GRAMMAR_MAX_LEAVES:
            raise GrammarError(f"program leaves {l} exceeds {GRAMMAR_MAX_LEAVES}")


def validate(program: Program) -> Program:
    """Re-validate a program (idempotent; useful after deserialization)."""
    if not isinstance(program, Program):
        raise GrammarError("not a Program")
    return program


# ---------------------------------------------------------------------------
# Emit. Pure, deterministic.
# ---------------------------------------------------------------------------
class _Emitter:
    def expr(self, n: Node) -> str:
        k, p = n.kind, n.params
        if k == "ema":
            return f"_ema(close, {p[0]})"
        if k == "rsi":
            return f"_rsi(close, {p[0]})"
        if k == "atr":
            return f"_atr(high, low, close, {p[0]})"
        if k == "macd_hist":
            return f"_macd_hist(close, {p[0]}, {p[1]}, {p[2]})"
        if k == "bb_dist":
            return f"_bb_dist(close, {p[0]}, {float(p[1])!r})"
        if k == "donchian_pos":
            return f"_donchian_pos(high, low, close, {p[0]})"
        if k == "keltner_dist":
            return f"_keltner_dist(close, high, low, {p[0]}, {float(p[1])!r})"
        if k == "zscore":
            return f"_zscore(close, {p[0]})"
        if k == "hurst_pct":
            return f"_hurst_pct(close, {p[0]}, {p[1]})"
        if k == "vwap_dev":
            return f"_vwap_dev(close, volume, {p[0]})"
        if k == "session_vwap_dist":
            return "_session_vwap_dist(close, high, low, volume, ts)"
        if k == "absret_pct":
            return f"_absret_pct(close, {p[0]})"
        # --- R81 price-level / R83 prior-day / R82 cross-instrument ---------
        if k == "dist_round":
            return f"_dist_round(close, {p[0]})"
        if k == "prior_day_dir":
            return "_prior_day_dir(close, ts)"
        if k == "prior_day_atr_pct":
            return f"_prior_day_atr_pct(high, low, close, ts, {p[0]})"
        if k == "gap_pips":
            return "_gap_pips(open_, close, ts)"
        if k == "dxy_proxy":
            return f"_dxy_proxy(_dxy_arr(len(close)), {p[0]})"
        if k == "dxy_ret":
            return f"_dxy_ret(_dxy_arr(len(close)), {p[0]})"
        if k == "dxy_corr":
            return f"_dxy_corr(close, _dxy_arr(len(close)), {p[0]})"
        # --- R87 patience ---------------------------------------------------
        if k == "bars_since_range":
            return f"_bars_since_range(high, low, close, {p[0]})"
        if k == "arith":
            return f"({self.expr(n.children[0])} {p[0]} {self.expr(n.children[1])})"
        if k == "const":
            return repr(float(p[1]))
        if k == "gene":
            return f'float(_GENES.get({str(p[0])!r}, float("nan")))'
        if k == "compare":
            return f"({self.expr(n.children[0])} {p[0]} {self.expr(n.children[1])})"
        if k == "crosses_above":
            return f"_cross_above({self.expr(n.children[0])}, {self.expr(n.children[1])})"
        if k == "crosses_below":
            return f"_cross_below({self.expr(n.children[0])}, {self.expr(n.children[1])})"
        if k == "and":
            return f"({self.expr(n.children[0])} & {self.expr(n.children[1])})"
        if k == "or":
            return f"({self.expr(n.children[0])} | {self.expr(n.children[1])})"
        if k == "not":
            return f"(~{self.expr(n.children[0])})"
        if k == "session":
            return f"_session_mask(ts, {p[0]})"
        if k == "killzone":
            return f"_killzone(ts, {p[0]}, {p[1]})"
        # --- R81 calendar ---------------------------------------------------
        if k == "day_of_week":
            return f"_day_of_week(ts, {p[0]})"
        if k == "day_of_month":
            return f"_day_of_month_window(ts, {p[0]}, {p[1]})"
        if k == "nth_weekday":
            return f"_nth_weekday(ts, {p[0]}, {p[1]})"
        if k == "jpy_holiday_window":
            return f"_jpy_holiday_window(ts, _pair(), {p[0]}, {p[1]})"
        if k == "round_number_hit":
            return f"_round_number_hit(close, {p[0]}, {float(p[1])!r})"
        # --- R83 prior-day --------------------------------------------------
        if k == "gap_open":
            return f"_gap_open(open_, close, ts, {float(p[0])!r})"
        # --- R82 cross-instrument -------------------------------------------
        if k == "dxy_lag_align":
            return f"_dxy_lag_align(close, _dxy_arr(len(close)), {p[0]})"
        # --- R87 patience ---------------------------------------------------
        if k == "n_quiet_bars":
            return f"_n_quiet_bars(high, low, close, {p[0]}, {p[1]}, {float(p[2])!r})"
        if k == "atr_quartile":
            return f"_atr_quartile(high, low, close, {p[0]}, {float(p[1])!r})"
        if k == "min_gap_bars":
            return f"_min_gap_bars({self.expr(n.children[0])}, {p[0]})"
        # --- R89 gross-edge hunt --------------------------------------------
        if k == "vol_displacement":
            return f"_vol_displacement(close, high, low, {p[0]})"
        if k == "pullback_depth":
            return f"_pullback_depth(high, low, close, {p[0]})"
        if k == "session_boundary_reversal":
            return (f"_session_boundary_reversal(ts, {self.expr(n.children[0])}, "
                    f"{float(p[0])!r})")
        raise GrammarError(f"cannot emit node kind {k!r}")


# The protocol preamble: the ONLY I/O is the protocol reader/writer, and the
# ONLY imports are the sanctioned ones (numpy/pandas + json/os). Every primitive
# is causal (reads only past/current closed bars) and deterministic.
PROTOCOL_PREAMBLE = '''"""APEX generated_body - composed from the typed grammar (Phase 4b).

Deterministic, causal, protocol-honoring. Reads input.parquet, writes
output.json. No network, no nested process, no import of APEX code.
"""
import json
import os

import numpy as np
import pandas as pd


# R81/R82 context (filled in main from genes.json + the injected DXY column; the
# shadow fills the same dict). A dict mutated in place avoids a `global` statement
# the R31 gate does not whitelist.
_CTX = dict()


def _pip():
    try:
        return float(_CTX.get("pip", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _pair():
    return str(_CTX.get("pair", ""))


def _dxy_arr(n):
    d = _CTX.get("dxy")
    if d is None:
        return _nan(n)
    a = np.asarray(d, dtype="float64")
    return a if len(a) == n else _nan(n)


def _is_jpy(pair):
    s = str(pair)
    return s[3:6] == "JPY" or s[:3] == "JPY"


def _nan(n):
    return np.full(n, np.nan, dtype="float64")


def _sma(x, p):
    out = _nan(len(x))
    if p <= 1 or len(x) < p:
        return out
    c = np.cumsum(np.insert(np.nan_to_num(x, nan=0.0), 0, 0.0))
    out[p - 1:] = (c[p:] - c[:-p]) / p
    return out


def _ema(x, p):
    out = _nan(len(x))
    if p <= 0:
        return out
    a = 2.0 / (p + 1.0)
    acc = 0.0
    seen = 0
    seed = 0.0
    started = False
    for i in range(len(x)):
        v = x[i]
        if not np.isfinite(v):
            continue
        if not started:
            seed += v
            seen += 1
            if seen >= p:
                acc = seed / p
                out[i] = acc
                started = True
            continue
        acc = a * v + (1.0 - a) * acc
        out[i] = acc
    return out


def _rsi(close, p):
    n = len(close)
    out = _nan(n)
    if p <= 0 or n < p + 1:
        return out
    gain = 0.0
    loss = 0.0
    for i in range(1, n):
        d = close[i] - close[i - 1]
        up = d if d > 0 else 0.0
        dn = -d if d < 0 else 0.0
        if i <= p:
            gain += up
            loss += dn
            if i == p:
                gain /= p
                loss /= p
                out[i] = 100.0 - 100.0 / (1.0 + (gain / loss if loss > 0 else np.inf))
        else:
            gain = (gain * (p - 1) + up) / p
            loss = (loss * (p - 1) + dn) / p
            out[i] = 100.0 - 100.0 / (1.0 + (gain / loss if loss > 0 else np.inf))
    return out


def _atr(high, low, close, p):
    n = len(close)
    tr = _nan(n)
    if n:
        tr[0] = high[0] - low[0]
    for i in range(1, n):
        a = high[i] - low[i]
        b = abs(high[i] - close[i - 1])
        c = abs(low[i] - close[i - 1])
        tr[i] = max(a, b, c)
    return _ema(tr, p)


def _macd_hist(close, f, s, sig):
    line = _ema(close, f) - _ema(close, s)
    return line - _ema(line, sig)


def _bb_dist(close, p, k):
    n = len(close)
    mid = _sma(close, p)
    out = _nan(n)
    for i in range(p - 1, n):
        w = close[i - p + 1:i + 1]
        sd = w.std(ddof=0)
        den = k * sd
        out[i] = (close[i] - mid[i]) / den if den > 0 else 0.0
    return out


def _donchian_pos(high, low, close, p):
    n = len(close)
    out = _nan(n)
    for i in range(p, n):
        up = high[i - p:i].max()
        lo = low[i - p:i].min()
        rng = up - lo
        out[i] = (close[i] - lo) / rng if rng > 0 else 0.0
    return out


def _keltner_dist(close, high, low, p, k):
    n = len(close)
    mid = _ema(close, p)
    at = _atr(high, low, close, p)
    out = _nan(n)
    for i in range(n):
        den = k * at[i]
        if np.isfinite(den) and den > 0:
            out[i] = (close[i] - mid[i]) / den
    return out


def _zscore(close, p):
    n = len(close)
    out = _nan(n)
    for i in range(p - 1, n):
        w = close[i - p + 1:i + 1]
        sd = w.std(ddof=0)
        out[i] = (close[i] - w.mean()) / sd if sd > 0 else 0.0
    return out


def _rolling_rank(values, window):
    n = len(values)
    out = _nan(n)
    for i in range(window, n):
        w = values[i - window + 1:i + 1]
        finite = w[np.isfinite(w)]
        if len(finite) < 2 or not np.isfinite(values[i]):
            continue
        out[i] = float((finite <= values[i]).sum()) / float(len(finite))
    return out


def _hurst(values, window):
    n = len(values)
    out = _nan(n)
    lags = (2, 3, 4, 6, 8, 12, 16)
    for i in range(window, n):
        w = values[i - window + 1:i + 1]
        if not np.all(np.isfinite(w)):
            continue
        tau = []
        ok = True
        for lag in lags:
            d = w[lag:] - w[:-lag]
            sd = d.std(ddof=0)
            if sd <= 0:
                ok = False
                break
            tau.append(sd)
        if not ok:
            continue
        x = np.log(np.asarray(lags, dtype="float64"))
        y = np.log(np.asarray(tau, dtype="float64"))
        A = np.vstack([x, np.ones(len(x))]).T
        slope = np.linalg.lstsq(A, y, rcond=None)[0][0]
        out[i] = slope
    return out


def _hurst_pct(close, window, rank_window):
    return _rolling_rank(_hurst(close, window), rank_window)


def _vwap_dev(close, volume, p):
    n = len(close)
    pv = _sma(close * volume, p)
    vv = _sma(volume, p)
    out = _nan(n)
    for i in range(n):
        den = vv[i]
        out[i] = (close[i] - pv[i] / den) if (np.isfinite(den) and den > 0) else 0.0
    return out


def _day_id(ts):
    return ts - (ts % 86400)


def _session_vwap_dist(close, high, low, volume, ts):
    n = len(close)
    typical = (high + low + close) / 3.0
    out = _nan(n)
    day = _day_id(ts)
    num = 0.0
    den = 0.0
    cur = None
    for i in range(n):
        if day[i] != cur:
            cur = day[i]
            num = 0.0
            den = 0.0
        num += typical[i] * volume[i]
        den += volume[i]
        out[i] = (close[i] - num / den) if den > 0 else 0.0
    return out


def _absret_pct(close, p):
    n = len(close)
    r = _nan(n)
    for i in range(1, n):
        r[i] = abs(close[i] / close[i - 1] - 1.0) if close[i - 1] else 0.0
    return _rolling_rank(r, p)


def _cross_above(a, b):
    n = len(a)
    out = np.zeros(n, dtype=bool)
    for i in range(1, n):
        out[i] = bool(a[i] > b[i] and a[i - 1] <= b[i - 1])
    return out


def _cross_below(a, b):
    n = len(a)
    out = np.zeros(n, dtype=bool)
    for i in range(1, n):
        out[i] = bool(a[i] < b[i] and a[i - 1] >= b[i - 1])
    return out


def _session_mask(ts, sid):
    # UTC session windows, closed-bar membership (same convention as the platform).
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        h = int((ts[i] % 86400) // 3600)
        if sid == 1:
            out[i] = 0 <= h < 8
        elif sid == 2:
            out[i] = 7 <= h < 16
        else:
            out[i] = 12 <= h < 21
    return out


def _killzone(ts, h0, h1):
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        h = int((ts[i] % 86400) // 3600)
        out[i] = h0 <= h < h1
    return out


# --- R81/R82/R83 (Phase 7h) helpers. All causal (closed bars only). ---------
# Calendar is derived from the UTC epoch by pure integer arithmetic (no import),
# so a body never needs a datetime module and the sandbox stays import-narrow.
def _civil(z):
    z = int(z) + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    if m <= 2:
        y = y + 1
    return y, m, d


def _day_of_week(ts, dow):
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        out[i] = ((int(ts[i]) // 86400) + 3) % 7 == dow
    return out


def _day_of_month_window(ts, lo, hi):
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        _, _, d = _civil(int(ts[i]) // 86400)
        out[i] = lo <= d <= hi
    return out


def _nth_weekday(ts, nth, dow):
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        day = int(ts[i]) // 86400
        _, _, d = _civil(day)
        if ((day + 3) % 7) != dow:
            continue
        # d is the day of the month; the nth occurrence spans [(n-1)*7+1, n*7].
        out[i] = (nth - 1) * 7 + 1 <= d <= nth * 7
    return out


# Static, documented bank-holiday calendar (UTC) for the JPY bloc. NOT derived
# from any data feed (no new data): a hand-written table of (month, day) fixed
# holidays. An approximation by design; the node's caveat is documented in the
# Phase 7h log rather than hidden.
_JPY_HOLIDAYS = ((1, 1), (1, 2), (1, 3), (2, 11), (3, 20), (3, 21),
                 (4, 29), (5, 3), (5, 4), (5, 5), (7, 17), (8, 11),
                 (9, 18), (9, 23), (10, 9), (11, 3), (11, 23), (12, 31))


def _jpy_holiday_window(ts, pair, before, after):
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    if not _is_jpy(pair):
        return out
    holidays = _JPY_HOLIDAYS
    for i in range(n):
        day = int(ts[i]) // 86400
        # Scan a small +/- window of days around each bar, cheap and clear.
        for off in range(-after, before + 1):
            _, m, d = _civil(day + off)
            if (m, d) in holidays:
                out[i] = True
                break
    return out


def _dist_round(close, step_pips):
    n = len(close)
    out = _nan(n)
    pip = _pip()
    if not (np.isfinite(pip) and pip > 0 and step_pips > 0):
        return out
    for i in range(n):
        v = close[i]
        if not np.isfinite(v):
            continue
        pips = v / pip
        nearest = round(pips / step_pips) * step_pips
        out[i] = pips - nearest
    return out


def _round_number_hit(close, step_pips, tol_pips):
    d = _dist_round(close, step_pips)
    n = len(d)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        if np.isfinite(d[i]):
            out[i] = abs(d[i]) <= tol_pips
    return out


def _day_stats(ts, open_, high, low, close):
    n = len(ts)
    day = np.asarray([int(t) // 86400 for t in ts], dtype="int64")
    first_open = _nan(n)
    last_close = _nan(n)
    day_high = _nan(n)
    day_low = _nan(n)
    j = 0
    while j < n:
        k = j
        while k + 1 < n and day[k + 1] == day[j]:
            k += 1
        fh = high[j:k + 1]
        fl = low[j:k + 1]
        for i in range(j, k + 1):
            first_open[i] = open_[j]
            last_close[i] = close[k]
            day_high[i] = np.nanmax(fh)
            day_low[i] = np.nanmin(fl)
        j = k + 1
    return day, first_open, last_close, day_high, day_low


def _prior_day_dir(close, ts):
    """Sign of the PRIOR completed UTC day's move (last close - first close)."""
    n = len(ts)
    out = _nan(n)
    day, first_open, last_close, _, _ = _day_stats(ts, close, close, close, close)
    # first_open here == first close of the day (we passed close for open/high/low)
    prev_day = None
    prev_dir = np.nan
    prev_first = np.nan
    prev_last = np.nan
    j = 0
    while j < n:
        k = j
        while k + 1 < n and day[k + 1] == day[j]:
            k += 1
        for i in range(j, k + 1):
            out[i] = prev_dir
        if np.isfinite(prev_first) and np.isfinite(prev_last) and prev_last != prev_first:
            prev_dir = 1.0 if prev_last > prev_first else -1.0
        prev_first = first_open[j]
        prev_last = last_close[k]
        j = k + 1
    return out


def _prior_day_atr_pct(high, low, close, ts, period):
    """Percentile rank of the PRIOR day's range among the last ``period`` days."""
    n = len(ts)
    out = _nan(n)
    day, _, _, dh, dl = _day_stats(ts, close, high, low, close)
    # one range per day, in order, plus the day boundary index
    days = []
    ranges = []
    j = 0
    while j < n:
        k = j
        while k + 1 < n and day[k + 1] == day[j]:
            k += 1
        days.append(day[j])
        ranges.append(dh[j] - dl[j])
        j = k + 1
    # for bar i in day-index di, use rank of ranges[di-1] among ranges before it
    di_of_bar = np.zeros(n, dtype="int64")
    j = 0
    di = 0
    while j < n:
        k = j
        while k + 1 < n and day[k + 1] == day[j]:
            k += 1
        for i in range(j, k + 1):
            di_of_bar[i] = di
        di += 1
        j = k + 1
    for i in range(n):
        d0 = di_of_bar[i] - 1
        if d0 < 1:
            continue
        hist = np.asarray(ranges[max(0, d0 - period):d0], dtype="float64")
        hist = hist[np.isfinite(hist)]
        if len(hist) < 2:
            continue
        out[i] = float((hist <= ranges[d0]).sum()) / float(len(hist))
    return out


def _gap_pips(open_, close, ts):
    """Today's first open minus the prior day's last close, in pips."""
    n = len(open_)
    out = _nan(n)
    day, first_open, last_close, _, _ = _day_stats(ts, open_, close, close, close)
    prev_last = np.nan
    pip = _pip()
    j = 0
    while j < n:
        k = j
        while k + 1 < n and day[k + 1] == day[j]:
            k += 1
        for i in range(j, k + 1):
            if np.isfinite(prev_last) and np.isfinite(pip) and pip > 0:
                out[i] = (first_open[i] - prev_last) / pip
        prev_last = last_close[k]
        j = k + 1
    return out


def _gap_open(open_, close, ts, min_pips):
    g = _gap_pips(open_, close, ts)
    n = len(g)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        if np.isfinite(g[i]):
            out[i] = abs(g[i]) >= min_pips
    return out


def _dxy_ret(dxy, lag):
    n = len(dxy)
    out = _nan(n)
    for i in range(n):
        j = i - int(lag)
        if j >= 1 and np.isfinite(dxy[i]) and np.isfinite(dxy[j]) and dxy[j] != 0:
            out[i] = dxy[i] / dxy[j] - 1.0
    return out


def _dxy_proxy(dxy, period):
    return _ema(dxy, period)


def _dxy_corr(close, dxy, window):
    n = len(close)
    out = _nan(n)
    pr = _nan(n)
    dr = _nan(n)
    for i in range(1, n):
        if close[i - 1]:
            pr[i] = close[i] / close[i - 1] - 1.0
        if np.isfinite(dxy[i]) and np.isfinite(dxy[i - 1]) and dxy[i - 1]:
            dr[i] = dxy[i] / dxy[i - 1] - 1.0
    for i in range(window, n):
        a = pr[i - window + 1:i + 1]
        b = dr[i - window + 1:i + 1]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() < 3:
            continue
        aa = a[m]
        bb = b[m]
        sa = aa.std(ddof=0)
        sb = bb.std(ddof=0)
        if sa > 0 and sb > 0:
            out[i] = float(((aa - aa.mean()) * (bb - bb.mean())).mean() / (sa * sb))
    return out


def _dxy_lag_align(close, dxy, lag):
    """Lag 9 read-only sensor: the pair's current move agrees with the DXY move
    ``lag`` closed bars ago (the leader-follower lag), a pure causal comparison."""
    n = len(close)
    out = np.zeros(n, dtype=bool)
    for i in range(1, n):
        j = i - int(lag)
        if j < 1 or not (np.isfinite(dxy[j]) and np.isfinite(dxy[j - 1])):
            continue
        dxy_move = dxy[j] - dxy[j - 1]
        pair_move = close[i] - close[i - 1]
        if dxy_move == 0 or pair_move == 0:
            continue
        out[i] = (dxy_move > 0) == (pair_move > 0)
    return out


# --- R87 (Phase 7j) PATIENCE helpers. All causal (closed bars only). ---------
# The dense-shooter failure: many entries, per-trade friction compounding into
# thousands of R. These primitives express PATIENCE — quiet-before-event, wide
# volatility regimes, a minimum distance between entries, and a pullback clock.
def _true_range(high, low, close):
    n = len(close)
    tr = _nan(n)
    if n:
        tr[0] = high[0] - low[0]
    for i in range(1, n):
        a = high[i] - low[i]
        b = abs(high[i] - close[i - 1])
        c = abs(low[i] - close[i - 1])
        tr[i] = max(a, b, c)
    return tr


def _n_quiet_bars(high, low, close, bars, window, quiet):
    """True iff the last ``bars`` CLOSED bars were all calm (range <= quiet*ATR).

    The patience gate: a body ANDs this with its real event, so the event only
    fires after a stretch of calm — no firing into the middle of a storm. Causal:
    it reads bars i-bars..i-1, never bar i's own future.
    """
    n = len(close)
    at = _atr(high, low, close, window)
    tr = _true_range(high, low, close)
    calm = np.zeros(n, dtype=bool)
    for i in range(n):
        den = at[i]
        calm[i] = bool(np.isfinite(den) and den > 0 and np.isfinite(tr[i])
                       and tr[i] <= quiet * den)
    out = np.zeros(n, dtype=bool)
    for i in range(bars, n):
        out[i] = bool(calm[i - bars:i].all())
    return out


def _atr_quartile(high, low, close, window, bucket):
    """True iff the current ATR ranks at/above ``bucket`` within its trailing
    ``window`` — the volatile-realm access gate (top quartile = bucket 0.75)."""
    n = len(close)
    at = _atr(high, low, close, 14)
    out = np.zeros(n, dtype=bool)
    for i in range(window, n):
        w = at[i - window + 1:i + 1]
        fin = w[np.isfinite(w)]
        if len(fin) < 5 or not np.isfinite(at[i]):
            continue
        rank = float((fin <= at[i]).sum()) / float(len(fin))
        out[i] = rank >= bucket
    return out


def _min_gap_bars(child, bars):
    """Keep only a child signal's firings that are >= ``bars`` apart.

    No clustering: friction compounds PER ENTRY, so two entries a few bars apart
    pay two full round trips. Causal: the spacing is measured from the last KEPT
    entry, always in the past.
    """
    n = len(child)
    out = np.zeros(n, dtype=bool)
    last = -(10 ** 9)
    for i in range(n):
        if bool(child[i]) and (i - last) >= bars:
            out[i] = True
            last = i
    return out


def _bars_since_range(high, low, close, window):
    """COILEDNESS in [0, 1]: the fraction of the trailing ``window`` with no new
    range extreme. A value near 0 means price just broke out; near 1 means it has
    been coiled inside its range the whole window (the pullback clock)."""
    n = len(close)
    out = _nan(n)
    last = -1
    for i in range(n):
        if i >= window:
            up = np.nanmax(high[i - window:i])
            lo = np.nanmin(low[i - window:i])
            if (np.isfinite(up) and close[i] > up) or (np.isfinite(lo) and close[i] < lo):
                last = i
        since = i - last if last >= 0 else i
        out[i] = min(1.0, float(since) / float(window))
    return out


def _vol_displacement(close, high, low, window):
    """R89 (Phase 7k) — the signed multi-day DISPLACEMENT: how far, in units of
    the current ATR, price has traveled from its origin ``window`` closed bars
    back. Positive = price is above its origin (an up-leg); the distance measure
    the "entry only after price travels > 2x ATR" mandate requires. Causal: reads
    only closed bars up to and including i."""
    n = len(close)
    at = _atr(high, low, close, 14)
    out = _nan(n)
    for i in range(window, n):
        den = at[i]
        if np.isfinite(den) and den > 0 and np.isfinite(close[i - window]) and np.isfinite(close[i]):
            out[i] = (close[i] - close[i - window]) / den
    return out


def _pullback_depth(high, low, close, window):
    """R89 (Phase 7k) — pullback geometry in [0, 1]: where the close sits inside
    its trailing ``window`` range (0 = at the window high, 1 = at the window low).
    The gross-fat entry is a shallow pullback INTO an established up-leg (near 0)
    or a bounce off the low of a down-leg (near 1). Causal (closed bars only)."""
    n = len(close)
    out = _nan(n)
    for i in range(window, n):
        up = np.nanmax(high[i - window:i])
        lo = np.nanmin(low[i - window:i])
        rng = up - lo
        if np.isfinite(rng) and rng > 0 and np.isfinite(close[i]):
            out[i] = min(1.0, max(0.0, (up - close[i]) / rng))
    return out


def _session_boundary_reversal(ts, front, fade):
    """R89 (Phase 7k) — fire a REVERSAL at a session boundary. A session boundary
    is the bar whose hour is one of {{0, 8, 16, 21}} UTC (the Tokyo/London/NY
    turns). ``front`` is a signed stretch measure (e.g. a z-score); the gate fires
    once per boundary when the leg into the boundary is stretched by ``fade``.
    Causal: the hour is a property of the CURRENT closed bar only."""
    n = len(ts)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        h = int((ts[i] % 86400) // 3600)
        if h == 0 or h == 8 or h == 16 or h == 21:
            v = front[i]
            if np.isfinite(v) and abs(v) >= fade:
                out[i] = True
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    frame = pd.read_parquet(os.path.join(here, "input.parquet"))
    with open(os.path.join(here, "genes.json")) as fh:
        _GENES = json.load(fh)
    close = frame["close"].to_numpy(dtype="float64")
    high = frame["high"].to_numpy(dtype="float64")
    low = frame["low"].to_numpy(dtype="float64")
    open_ = frame["open"].to_numpy(dtype="float64")
    volume = frame["volume"].to_numpy(dtype="float64")
    ts = frame["ts"].to_numpy(dtype="int64")
    # R81/R82 context: pair metadata (from genes) and the read-only DXY proxy
    # series (an injected CAUSAL column; absent -> NaN, so a body that needs it
    # simply never fires rather than inventing a value). A dict mutated in place
    # avoids a `global` statement the R31 gate does not whitelist.
    _CTX["pip"] = float(_GENES.get("__pip__", 0.0) or 0.0)
    _CTX["pair"] = str(_GENES.get("__pair__", ""))
    if "dxy" in frame.columns:
        _CTX["dxy"] = frame["dxy"].to_numpy(dtype="float64")
    else:
        _CTX["dxy"] = None
    long_raw = np.asarray({long_expr}, dtype=bool)
    short_raw = np.asarray({short_expr}, dtype=bool)
    out = {{
        "protocol": 1,
        "long": [int(bool(x)) for x in long_raw],
        "short": [int(bool(x)) for x in short_raw],
        "meta": {{"concept": {concept!r}, "family": "generated_body"}},
    }}
    with open(os.path.join(here, "output.json"), "w") as fh:
        json.dump(out, fh)


if __name__ == "__main__":
    main()
'''


def emit_python(program: Program) -> str:
    """Emit deterministic, protocol-honoring Python source for ``program``."""
    program = validate(program)
    em = _Emitter()
    long_expr = em.expr(program.long)
    short_expr = em.expr(program.short)
    return PROTOCOL_PREAMBLE.format(
        long_expr=long_expr, short_expr=short_expr, concept=program.concept
    )


def emit_expressions(program: Program) -> tuple[str, str, str]:
    """Return ``(long_expr, short_expr, concept)`` — the two bool expressions.

    R35 (Phase 5) SHADOW EXECUTION uses this: the SAME expressions the body runs in
    the sandbox are evaluated natively against the SAME helper primitives in
    :data:`PROTOCOL_PREAMBLE`, so the shadow is equivalent by construction. Pure.
    """
    program = validate(program)
    em = _Emitter()
    return em.expr(program.long), em.expr(program.short), program.concept


def preamble_helpers() -> str:
    """The helper-function section of :data:`PROTOCOL_PREAMBLE` (no ``main``).

    Split at ``def main():`` so the shadow can exec the primitives without the
    protocol's file I/O. This is the exact code the emitted body runs.
    """
    return PROTOCOL_PREAMBLE.split("def main():", 1)[0]
