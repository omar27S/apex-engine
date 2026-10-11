"""THE JUDGE — the R30/R31/R32/R35 gates for a self-written body (Phases 4a/4b/5).

A body must pass, IN ORDER:

  0. THE STATIC GATE (R31). Its SOURCE is parsed and walked against an AST
     whitelist before any execution; a blacklisted name/attribute/import dies
     with cause ``"static_gate"``.
  1. ISOLATED EXECUTION (the sandbox). A crash, hang, network call, nested
     process, native escape (ctypes/mmap), filesystem mutation, or a write
     outside the temp dir kills it: cause ``"sandbox_death"``. A malformed output
     envelope kills it: cause ``"protocol_violation"``.
  2. DETERMINISM. The identical input is run twice; the two ``output.json`` byte
     strings must match. A body that varies run-to-run dies: ``"nondeterministic"``.
  3. SHADOW EQUIVALENCE (R35, Phase 5). When a grammar ``program`` is supplied,
     the body's output must EQUAL its native shadow evaluation — the app's own
     primitives (already future-leak-tested) on the same frame. A body that
     diverges from its verified-causal reference dies: ``"shadow_mismatch"``.
     This replaces PREDICTED equivalence for "failed to disprove" and closes the
     4b challenge line.
  4. CAUSALITY (R32/R35). The frame is perturbed strictly after an index ``t`` in
     SIX independent ways (reflect wicks, permute future rows, delete the future,
     shift future timestamps, affine-rescale the future, swap non-adjacent future
     values) and the body is re-run each time; its signals at/before ``t`` must
     not move under ANY mode. A body that peeks at the future dies:
     ``"future_leak"``. Aligning on the timestamp (not the row index) keeps the
     check honest when bars are deleted or permuted.
  5. THE HONEST ENGINE. The surviving masks are fed through the SAME evaluator,
     stop geometry, cost stamp and aggregation as any genome (R17/R20/R22). A
     body is judged like anyone else — no discounts for being artificial.

No appeal inside a phase (R10: the tribunal reviews between phases). Each gate
maps to exactly one sealed death cause; the first failure wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.pyramid.sandbox import protocol as proto
from app.pyramid.sandbox import static_gate
from app.pyramid.sandbox.runner import (
    CAUSE_PROTOCOL,
    CAUSE_SANDBOX_DEATH,
    SandboxConfig,
    SandboxDeath,
    run_body,
)

__all__ = ["CAUSE_NONDETERMINISTIC", "CAUSE_FUTURE_LEAK", "CAUSE_SHADOW_MISMATCH",
           "BodyVerdict", "judge_body"]

CAUSE_NONDETERMINISTIC = "nondeterministic"
CAUSE_FUTURE_LEAK = "future_leak"
CAUSE_SHADOW_MISMATCH = "shadow_mismatch"

# Geometry genes a body's genome must carry; family is only a dispatch selector
# (bypassed here), so a neutral valid family is used purely as the geometry
# carrier — the verdict records the body's real label separately.
_GEOMETRY_FAMILY = "trend_pullback"


@dataclass
class BodyVerdict:
    """The judge's ruling on one body."""

    alive: bool
    causes: list[str] = field(default_factory=list)
    family: str = "generated_body"
    gates: dict = field(default_factory=dict)
    performance: dict | None = None
    signals: int = 0
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "alive": self.alive,
            "causes": list(self.causes),
            "family": self.family,
            "gates": dict(self.gates),
            "performance": self.performance,
            "signals": self.signals,
            "detail": self.detail,
        }


def _mutate_reflect_wicks(m15: pd.DataFrame, t_ts: int) -> pd.DataFrame:
    """Mode 1 — reflect OHLC strictly after ``t_ts`` about the anchor close and
    swap the wicks, so shape AND level of every future bar change while OHLC
    ordering stays valid."""
    out = m15.copy()
    seg = out["ts"].to_numpy() > t_ts
    anchor = float(out["close"].iloc[0])
    for col in ("open", "close"):
        out.loc[seg, col] = 2.0 * anchor - out.loc[seg, col].to_numpy()
    hi = out.loc[seg, "high"].to_numpy()
    lo = out.loc[seg, "low"].to_numpy()
    out.loc[seg, "high"] = 2.0 * anchor - lo
    out.loc[seg, "low"] = 2.0 * anchor - hi
    out.loc[seg, "volume"] = 0.0
    return out


def _mutate_permute_future(m15: pd.DataFrame, t_ts: int) -> pd.DataFrame:
    """Mode 2 — permute the future OHLCV rows in a fixed, deterministic order
    while leaving the timestamps in place (so the frame stays a valid, monotonic
    tape). A causal body sees the same past; a peek at any later bar's value
    changes.
    """
    out = m15.copy()
    idx = np.where(out["ts"].to_numpy() > t_ts)[0]
    cols = ["open", "high", "low", "close", "volume"]
    if len(idx) >= 2:
        rolled = np.roll(idx, 1)
        out.loc[idx, cols] = m15.loc[rolled, cols].to_numpy()
    return out


def _mutate_delete_future(m15: pd.DataFrame, t_ts: int) -> pd.DataFrame:
    """Mode 3 — delete every future bar. A body that indexes the last row (or
    counts bars forward) shifts; a causal body's earlier signals do not."""
    out = m15.copy()
    keep = out["ts"].to_numpy() <= t_ts
    return out.loc[keep].reset_index(drop=True)


def _mutate_shift_ts(m15: pd.DataFrame, t_ts: int) -> pd.DataFrame:
    """Mode 4 — shift every future timestamp by a fixed +7 days, keeping the
    prices and the strict monotonic ordering. A body keyed on future TIME (e.g.
    the weekday of a later bar) moves; a causal body's earlier signals do not.
    """
    out = m15.copy()
    seg = out["ts"].to_numpy() > t_ts
    out.loc[seg, "ts"] = out.loc[seg, "ts"].to_numpy() + 7 * 86400
    return out


def _mutate_affine_rescale(m15: pd.DataFrame, t_ts: int) -> pd.DataFrame:
    """Mode 5 (R35) — affine-rescale every future OHLC bar about the past close.

    ``p' = past_close + 1.7 * (p - past_close)`` (a positive scale and a shift),
    so the shape is stretched while OHLC ordering and positivity hold (the scale
    is > 1, so no price folds through zero). A body keyed on future LEVEL or
    future SHAPE moves; a causal body's earlier signals do not.
    """
    out = m15.copy()
    seg = out["ts"].to_numpy() > t_ts
    anchor = float(out["close"].iloc[0])
    scale = 1.7
    for col in ("open", "high", "low", "close"):
        out.loc[seg, col] = anchor + scale * (out.loc[seg, col].to_numpy() - anchor)
    out.loc[seg, "volume"] = out.loc[seg, "volume"].to_numpy() * scale
    return out


def _mutate_value_swap(m15: pd.DataFrame, t_ts: int) -> pd.DataFrame:
    """Mode 6 (R35) — swap values across NON-ADJACENT future bars, timestamps fixed.

    Every future bar's OHLC is replaced by that of the future bar 3 positions
    ahead (a cyclic, deterministic swap that preserves timestamps and keeps each
    row a valid body). A body that reads a specific later bar's value changes; a
    causal body's earlier signals do not.
    """
    out = m15.copy()
    idx = np.where(out["ts"].to_numpy() > t_ts)[0]
    cols = ["open", "high", "low", "close", "volume"]
    if len(idx) >= 4:
        shifted = np.roll(idx, -3)
        out.loc[idx, cols] = m15.loc[shifted, cols].to_numpy()
    return out


# The six R32/R35 causality mutation modes. A body must survive ALL of them.
_MUTATION_MODES = (
    ("reflect_wicks", _mutate_reflect_wicks),
    ("permute_future", _mutate_permute_future),
    ("delete_future", _mutate_delete_future),
    ("shift_ts", _mutate_shift_ts),
    ("affine_rescale", _mutate_affine_rescale),
    ("value_swap", _mutate_value_swap),
)


def judge_body(
    body_source: str,
    m15: pd.DataFrame,
    pair: str,
    pip: float,
    genes: dict,
    *,
    config: SandboxConfig | None = None,
    eval_config=None,
    causality_check: bool = True,
    program=None,
    major_frames: dict | None = None,
) -> BodyVerdict:
    """Run the R31 gate, the R30 gates, and (R35) the shadow-equivalence gate.

    When ``program`` (a :class:`app.pyramid.author.grammar.Program`) is supplied,
    the body's sandbox output must EQUAL its native shadow evaluation — closing
    the 4b challenge line for grammar bodies. Reference/escape bodies are judged
    without the shadow gate (there is no tree to compare against).

    When ``major_frames`` is supplied (R82), a causal read-only USD-index proxy is
    built from those majors and injected as a ``dxy`` column on the execution
    frame, and the pair/pip travel in the body's gene env — so the calendar,
    price-level and cross-instrument grammar nodes have what they need.
    """
    from app.core import data as data_mod
    from app.quant import evaluator as ev
    from app.quant import frames as frames_mod
    from app.quant.genome import StrategyGenome

    config = config or SandboxConfig()

    # --- GATE 0: the R31 static gate (before any execution) --------------------
    sv = static_gate.check_source(body_source)
    if not sv.ok:
        return BodyVerdict(alive=False, causes=[static_gate.CAUSE_STATIC_GATE],
                           gates={"static_gate": sv.to_dict()},
                           detail="; ".join(sv.violations))

    m15 = data_mod.validate(m15)
    F = frames_mod.build_frames(m15, pair, pip)
    exec_frame = F.exec[["ts", "open", "high", "low", "close", "volume"]].copy()
    if major_frames:
        from app.pyramid.author import sensors as sensors_mod

        exec_frame["dxy"] = sensors_mod.dxy_proxy_series(
            exec_frame["ts"].to_numpy(), major_frames)
    # The body's gene env carries the pair metadata the R81/R82 nodes read.
    genes = {**dict(genes), "__pip__": float(pip), "__pair__": str(pair)}

    # --- GATE 1: isolated execution -------------------------------------------
    try:
        run = run_body(body_source, exec_frame, genes=genes, config=config)
    except SandboxDeath as d:
        cause = d.cause
        return BodyVerdict(alive=False, causes=[cause],
                           gates={"sandbox": {"ok": False, "detail": d.detail}})
    gates = {"static_gate": {"ok": True},
             "sandbox": {"ok": True, "artifacts": run.artifacts}}

    # --- GATE 2: determinism ---------------------------------------------------
    try:
        run2 = run_body(body_source, exec_frame, genes=genes, config=config)
    except SandboxDeath as d:
        return BodyVerdict(alive=False, causes=[d.cause], gates=gates)
    if run2.output_json != run.output_json:
        return BodyVerdict(
            alive=False, causes=[CAUSE_NONDETERMINISTIC], gates=gates,
            detail="two runs on identical input produced different output.json",
        )
    gates["determinism"] = {"ok": True, "runs": 2}

    long_m, short_m = run.long, run.short

    # --- GATE 3 (R35): shadow equivalence to a verified-causal reference -------
    if program is not None:
        from app.pyramid.author import shadow as shadow_mod

        try:
            shadow = shadow_mod.evaluate_tree(program, exec_frame, genes)
        except Exception as e:  # a shadow that cannot run is a fail-closed death
            return BodyVerdict(alive=False, causes=[CAUSE_SHADOW_MISMATCH], gates=gates,
                               detail=f"shadow evaluation failed: {e}")
        eq = shadow_mod.equivalence(long_m, short_m, shadow)
        gates["shadow"] = eq.to_dict()
        if not eq.ok:
            return BodyVerdict(alive=False, causes=[CAUSE_SHADOW_MISMATCH], gates=gates,
                               detail=eq.detail)

    # --- GATE 4: causality, across ALL six mutation modes ----------------------
    if causality_check:
        n_exec = len(exec_frame)
        t_idx = min(n_exec - 2, max(1, n_exec // 2))
        t_ts = int(exec_frame["ts"].iloc[t_idx])
        original_ts = exec_frame["ts"].to_numpy()
        mode_results = {}
        for name, mutate in _MUTATION_MODES:
            mutated = mutate(m15, t_ts)
            Fm = frames_mod.build_frames(mutated, pair, pip)
            exec_m = Fm.exec[["ts", "open", "high", "low", "close", "volume"]].copy()
            if major_frames:
                from app.pyramid.author import sensors as sensors_mod

                # The proxy is rebuilt from the UNMUTATED majors, so it is
                # invariant under any mutation of the traded pair's future.
                exec_m["dxy"] = sensors_mod.dxy_proxy_series(
                    exec_m["ts"].to_numpy(), major_frames)
            try:
                runm = run_body(body_source, exec_m, genes=genes, config=config)
            except SandboxDeath as d:
                return BodyVerdict(alive=False, causes=[d.cause], gates=gates)
            # Compare only rows the mutated frame still shares with the original,
            # at timestamps <= t. Align on the timestamp, not the position, so a
            # deletion/permutation is handled honestly.
            kept_ts = exec_m["ts"].to_numpy()
            common = np.isin(original_ts, kept_ts) & (original_ts <= t_ts)
            pos_m = {int(t): i for i, t in enumerate(kept_ts)}
            same = True
            for i in np.where(common)[0]:
                j = pos_m[int(original_ts[i])]
                if bool(long_m[i]) != bool(runm.long[j]) or bool(short_m[i]) != bool(runm.short[j]):
                    same = False
                    break
            mode_results[name] = same
            if not same:
                return BodyVerdict(
                    alive=False, causes=[CAUSE_FUTURE_LEAK], gates=gates,
                    detail=f"signals at/before t={t_ts} moved under mode {name!r}",
                )
        gates["causality"] = {"ok": True, "t_ts": t_ts, "modes": mode_results}

    # --- GATE 5: the honest engine ---------------------------------------------
    geometry = {k: v for k, v in dict(genes).items()
                if k != "family" and not str(k).startswith("__")}
    geometry["family"] = _GEOMETRY_FAMILY
    try:
        genome = StrategyGenome.from_dict(geometry)
    except Exception as e:  # a bad geometry gene set is a protocol problem
        return BodyVerdict(alive=False, causes=[CAUSE_PROTOCOL], gates=gates,
                           detail=f"genes do not form a valid geometry: {e}")
    report = ev.evaluate(
        genome, {pair: F}, eval_config or ev.EvaluationConfig(),
        signals_by_pair={pair: (long_m, short_m, {})},
    )
    metrics = report.metrics
    gates["evaluation"] = {"ok": True}
    return BodyVerdict(
        alive=True,
        causes=[],
        family="generated_body",
        gates=gates,
        performance={
            "trades": int(metrics.trades),
            "net_r": float(metrics.net_r),
            "gross_r": float(getattr(metrics, "gross_r", 0.0)),
            "win_rate": float(getattr(metrics, "win_rate", 0.0)),
            "profit_factor": getattr(metrics, "profit_factor", None),
            "max_drawdown_r": float(getattr(metrics, "max_drawdown_r", 0.0)),
            "diagnostic": bool(report.diagnostic),
        },
        signals=int(np.count_nonzero(long_m) + np.count_nonzero(short_m)),
    )
