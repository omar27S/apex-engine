"""SHADOW EXECUTION — R35: equivalence to a verified-causal reference (Phase 5).

The 4b challenge line was the epistemic ceiling of perturbation-based causality:
four mutation modes can only FAIL TO DISPROVE a leak. R35 closes it structurally.
Every body tree is ALSO evaluated NATIVELY by the app's own primitives — the very
helper functions the grammar emits into the body, already future-leak-tested by
the pure core (``tests/quant/test_causality.py``). The judge then requires the
body's sandbox output to EQUAL the shadow evaluation on the same frame (exact, or
within a documented tolerance). Equivalence to a verified-causal reference
replaces "failed to disprove".

HOW EQUIVALENCE IS EXACT BY CONSTRUCTION. :func:`evaluate_tree` execs the SAME
preamble helpers the emitted body runs (``grammar.preamble_helpers``) and
evaluates the SAME two expressions (``grammar.emit_expressions``) with the SAME
inputs and the SAME ``genes.json`` values. So the only honest source of a
mismatch is a body that did something the grammar did not emit — which is exactly
what the gate is meant to catch.

PURITY: no I/O at import. :func:`evaluate_tree` execs a string (the sealed
preamble) in a fresh namespace; nothing is written anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.pyramid.author import grammar as g

__all__ = [
    "ShadowResult",
    "EquivalenceResult",
    "evaluate_tree",
    "evaluate_source",
    "equivalence",
    "EXACT",
]

EXACT = 0.0


@dataclass
class ShadowResult:
    """A tree's native evaluation: its long/short masks and the concept string."""

    long: np.ndarray
    short: np.ndarray
    concept: str = ""


@dataclass
class EquivalenceResult:
    """Whether a body's sandbox output equals the shadow evaluation."""

    ok: bool
    mismatches: int
    detail: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "mismatches": int(self.mismatches),
                "detail": self.detail}


def _namespace() -> dict:
    """A fresh namespace with the sealed preamble helpers (the exact body code)."""
    ns: dict = {}
    exec(compile(g.preamble_helpers(), "<shadow_preamble>", "exec"), ns)
    return ns


def _arrays(frame: pd.DataFrame):
    cols = {
        "close": frame["close"].to_numpy(dtype="float64"),
        "high": frame["high"].to_numpy(dtype="float64"),
        "low": frame["low"].to_numpy(dtype="float64"),
        "open_": frame["open"].to_numpy(dtype="float64"),
        "volume": frame["volume"].to_numpy(dtype="float64"),
        "ts": frame["ts"].to_numpy(dtype="int64"),
    }
    if "dxy" in frame.columns:
        cols["_dxy"] = frame["dxy"].to_numpy(dtype="float64")
    return cols


def evaluate_tree(program: g.Program, frame: pd.DataFrame, genes: dict | None = None
                  ) -> ShadowResult:
    """Evaluate a grammar tree natively with the same primitives the body runs."""
    ns = _namespace()
    long_expr, short_expr, concept = g.emit_expressions(program)
    ctx = _arrays(frame)
    genes = dict(genes or {})
    # Mirror the body's R81/R82 context so the shadow reads the SAME pip/pair/dxy.
    _ctx = ns.get("_CTX")
    if _ctx is not None:
        try:
            _ctx["pip"] = float(genes.get("__pip__", 0.0) or 0.0)
        except (TypeError, ValueError):
            _ctx["pip"] = 0.0
        _ctx["pair"] = str(genes.get("__pair__", ""))
        _ctx["dxy"] = ctx.get("_dxy")
    ctx["_GENES"] = genes
    ctx.update(ns)
    long_raw = np.asarray(eval(long_expr, ns, ctx), dtype=bool)  # noqa: S307 - sealed expression
    short_raw = np.asarray(eval(short_expr, ns, ctx), dtype=bool)  # noqa: S307 - sealed expression
    return ShadowResult(long=long_raw, short=short_raw, concept=concept)


def evaluate_source(source: str, frame: pd.DataFrame, genes: dict | None = None) -> ShadowResult:
    """Evaluate a body's EMITTED SOURCE natively (a reference for the sandbox).

    The emitted source carries a ``main()`` bound to protocol file I/O, so we run
    only its helper section and then evaluate the two expressions it would use. A
    body whose source diverges from the grammar (a hand-written body) may fail to
    expose the expected expressions; that raises here, and the judge treats a
    shadow that cannot run as a NON-match (fail-closed).
    """
    helpers = g.preamble_helpers()
    ns: dict = {}
    exec(compile(helpers, "<shadow_helpers>", "exec"), ns)
    # Recover the two expressions from the source by importing its main body is
    # fragile; instead re-parse the expression strings the emitter would produce
    # is not possible from arbitrary source. For an emitted grammar body the
    # expressions live literally in ``long_raw = np.asarray(<expr>``; we locate
    # them by AST, refusing anything we cannot read.
    import ast

    tree = ast.parse(source)
    long_expr = short_expr = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            name = getattr(tgt, "id", None)
            if name == "long_raw" and isinstance(node.value, ast.Call):
                long_expr = ast.unparse(node.value.args[0])
            if name == "short_raw" and isinstance(node.value, ast.Call):
                short_expr = ast.unparse(node.value.args[0])
    if long_expr is None or short_expr is None:
        raise ValueError("source does not expose grammar expressions (not a grammar body)")
    ctx = _arrays(frame)
    ctx["_GENES"] = dict(genes or {})
    long_raw = np.asarray(eval(long_expr, ns, ctx), dtype=bool)  # noqa: S307
    short_raw = np.asarray(eval(short_expr, ns, ctx), dtype=bool)  # noqa: S307
    return ShadowResult(long=long_raw, short=short_raw)


def equivalence(
    body_long: np.ndarray,
    body_short: np.ndarray,
    shadow: ShadowResult,
    *,
    tolerance: float = EXACT,
) -> EquivalenceResult:
    """R35 equality gate: the body's masks must EQUAL the shadow's masks.

    ``tolerance`` is in *mismatched rows count* by default (exact). Callers may
    pass a small allowance, documented at the call site; the judge uses exact.
    """
    bl = np.asarray(body_long, dtype=bool)
    bs = np.asarray(body_short, dtype=bool)
    if bl.shape != shadow.long.shape or bs.shape != shadow.short.shape:
        return EquivalenceResult(
            False, max(bl.size, bs.size),
            f"shape mismatch: body {bl.shape}/{bs.shape} vs shadow "
            f"{shadow.long.shape}/{shadow.short.shape}",
        )
    mism = int(np.count_nonzero(bl != shadow.long) + np.count_nonzero(bs != shadow.short))
    if mism <= tolerance:
        return EquivalenceResult(True, mism, "body output equals the shadow evaluation")
    return EquivalenceResult(
        False, mism,
        f"{mism} rows differ from the verified-causal shadow (R35 equivalence gate)",
    )
