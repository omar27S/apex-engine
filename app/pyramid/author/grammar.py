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
