"""THE MULTI-LAYER STRATEGIES -- JUMP 7: from rules to organisms.

Strategies were flat: one rule, one timeframe, one pair. Real edge lives in HIERARCHY:
the macro (D1) opens a tactical (H4) opportunity that triggers an execution (M15)
setup. This module gives a strategy LAYERS:

  * THE LAYERED GENOME -- a strategy may be composed of 2-3 coordinated sub-strategies
    on different timeframes: the STRATEGIC layer (D1: the macro thesis -- "the trend is
    down, only short setups"), the TACTICAL layer (H4: the setup detector), and the
    EXECUTION layer (M15: the trigger). Each layer names a family (its school) and a
    coordination clause (which higher-timeframe context it reads, and which direction it
    permits). The layers are bound by a coordination CONTRACT: execution only fires when
    tactical approves, tactical only proposes when strategic allows;
  * THE LAYER-UNAWARE ENGINE -- no engine rewrite is needed. The layered genome
    COMPILES DOWN to the existing signal+gate model: the execution layer's family drives
    the signal (the genome's own ``family``), and the strategic/tactical layers compile
    to extra GATE masks over the higher-timeframe context the frames already carry
    (D1 trend, H4 structure). :func:`layer_masks` returns those masks; the evaluator
    ANDs them onto the raw signals -- the same gate stack the confluence gate uses;
  * THE LAYER REPORTING -- the Letter notes a multi-layer champion ("campionato a 3
    strati (D1>H4>M15)"), and :func:`multi_layer_stats` answers honestly whether
    layered strategies outperform flat ones (``None`` when there is nothing to compare).

Honesty is binding. A genome with no layers is FLAT and :func:`layer_masks` is a
no-op (never a phantom gate); a layer with an unreadable higher-timeframe context
suppresses its signals (fail-closed, never a fabricated alignment); a multi-layer
comparison with no layered strategies reports ``None`` (never an invented edge). Pure
at import (Scar #6): the masks are reductions over the frames the caller supplies.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "LAYERS_VERSION",
    "LAYER_ROLES",
    "LAYER_TIMEFRAMES",
    "LAYER_GATES",
    "make_layer",
    "compose_layers",
    "is_layered",
    "layer_count",
    "compile_layers",
    "layer_masks",
    "layer_summary",
    "mutate_layers",
    "multi_layer_stats",
]

LAYERS_VERSION: int = 1

# The roles, in coordination order (strategic allows, tactical proposes, execution fires).
LAYER_ROLES: tuple[str, ...] = ("strategic", "tactical", "execution")

# The timeframe each role lives on.
LAYER_TIMEFRAMES: dict[str, str] = {
    "strategic": "D1", "tactical": "H4", "execution": "M15"}

# The higher-timeframe context each gate reads (the frames already carry both).
LAYER_GATES: dict[str, str] = {"d1_trend": "D1", "h4_structure": "H4"}


def make_layer(role: str, family: str, *, gate: str = "", direction: int = 0) -> dict:
    """Build ONE layer: a role, a school (family), a gate, and a direction clause.

    ``gate`` names the higher-timeframe context the layer reads (``d1_trend`` /
    ``h4_structure``); the execution layer reads no gate (it IS the signal).
    ``direction``: 0 = both sides allowed (aligned to the gate), 1 = long only,
    -1 = short only. Fail-closed: an unknown role or gate is refused.
    """
    if role not in LAYER_ROLES:
        raise ValueError(f"unknown layer role {role!r}; known: {LAYER_ROLES}")
    if gate and gate not in LAYER_GATES:
        raise ValueError(f"unknown layer gate {gate!r}; known: {tuple(LAYER_GATES)}")
    if role == "execution" and gate:
        raise ValueError("the execution layer reads no gate (it is the signal)")
    if direction not in (-1, 0, 1):
        raise ValueError("layer direction must be -1, 0 or 1")
    return {"role": role, "timeframe": LAYER_TIMEFRAMES[role], "family": str(family),
            "gate": str(gate), "direction": int(direction)}


def compose_layers(*, execution_family: str, strategic_family: str = "",
                   tactical_family: str = "", strategic_direction: int = 0,
                   tactical_direction: int = 0) -> tuple[dict, ...]:
    """Compose a 2-3 layer stack (execution required; strategic/tactical optional).

    The gate for each optional layer defaults to its timeframe's context. Returns the
    layers in coordination order (strategic -> tactical -> execution).
    """
    layers: list[dict] = []
    if strategic_family:
        layers.append(make_layer("strategic", strategic_family,
                                 gate="d1_trend", direction=strategic_direction))
    if tactical_family:
        layers.append(make_layer("tactical", tactical_family,
                                 gate="h4_structure", direction=tactical_direction))
    layers.append(make_layer("execution", execution_family))
    return tuple(layers)


def is_layered(genome) -> bool:
    """True when the genome carries a coordination stack (else it is FLAT)."""
    return bool(getattr(genome, "layers", ()))


def layer_count(genome) -> int:
    return len(getattr(genome, "layers", ()) or ())


def compile_layers(genome) -> dict:
    """The COORDINATION CONTRACT, made explicit (the compile-down description).

    Returns the ordered roles, the timeframes, the gates and the direction clauses --
    the honest statement of how the stack compiles to the signal+gate model. A flat
    genome reports ``layered=False`` (no phantom contract).
    """
    layers = list(getattr(genome, "layers", ()) or ())
    if not layers:
        return {"layered": False, "n_layers": 0, "roles": [], "timeframes": [],
                "gates": [], "reading": "strategia piatta (nessuno strato)"}
    return {
        "layered": True,
        "n_layers": len(layers),
        "roles": [l.get("role") for l in layers],
        "timeframes": [l.get("timeframe") for l in layers],
        "gates": [l.get("gate") for l in layers],
        "directions": [l.get("direction") for l in layers],
        "reading": " -> ".join(str(l.get("timeframe")) for l in layers),
    }


def layer_masks(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """The higher-layer GATE masks (long, short) for a layered genome.

    A FLAT genome (no layers) yields all-True masks -- a no-op (never a phantom gate).
    Each non-execution layer requires the trade direction to agree with its
    higher-timeframe context (D1 trend / H4 structure). Fail-closed: an unreadable
    context (NaN) suppresses the signal, never a fabricated alignment.
    """
    f = ctx.frames
    n = len(f)
    long_ok = np.ones(n, dtype=bool)
    short_ok = np.ones(n, dtype=bool)
    layers = list(getattr(genome, "layers", ()) or ())
    if not layers:
        return long_ok, short_ok
    for layer in layers:
        gate = str(layer.get("gate") or "")
        if not gate:
            continue  # the execution layer is the signal itself
        if gate == "d1_trend":
            fast = np.asarray(f.trend_ema_fast, dtype="float64")
            slow = np.asarray(f.trend_ema_slow, dtype="float64")
        elif gate == "h4_structure":
            fast = np.asarray(f.structure_ema_fast, dtype="float64")
            slow = np.asarray(f.structure_ema_slow, dtype="float64")
        else:
            continue
        finite = np.isfinite(fast) & np.isfinite(slow)
        up = finite & (fast > slow)
        down = finite & (fast < slow)
        d = int(layer.get("direction", 0))
        if d >= 0:
            long_ok &= up
        else:
            long_ok &= False
        if d <= 0:
            short_ok &= down
        else:
            short_ok &= False
    return long_ok, short_ok


def layer_summary(genome) -> dict:
    """The layer reporting for the Letter (a multi-layer champion is named)."""
    c = compile_layers(genome)
    if not c["layered"]:
        return {"layered": False, "n_layers": 0,
                "reading": "strategia a strato singolo"}
    tfs = c["timeframes"]
    return {"layered": True, "n_layers": c["n_layers"], "timeframes": tfs,
            "reading": f"campionato a {c['n_layers']} strati "
                       f"({' > '.join(str(t) for t in tfs)})"}


def mutate_layers(genome, rng, *, rate: float = 0.1) -> tuple[dict, ...]:
    """Mutate a stack's COORDINATION clauses (direction/strength), not the DNA genes.

    A layer may flip its permitted direction or drop/add an optional layer. Honest:
    a flat genome mutates nothing (layers evolve only where they exist); the stack is
    always re-normalised to a valid coordination order.
    """
    layers = list(getattr(genome, "layers", ()) or ())
    if not layers:
        return ()
    out: list[dict] = []
    for layer in layers:
        l = dict(layer)
        if l.get("role") != "execution" and rng.random() < rate:
            l["direction"] = int(rng.choice([-1, 0, 1]))
        out.append(l)
    return tuple(out)


def multi_layer_stats(rows: list[dict]) -> dict:
    """Do multi-layer strategies OUTPERFORM flat ones? (the data answers, honestly).

    ``rows`` is a leaderboard-like list of ``{net_r, layers}``. Reports the mean net_r
    of the layered vs the flat cohorts and the delta. Honest: a cohort with no rows
    reports ``None`` (never an invented edge); the comparison is ``None`` unless BOTH
    cohorts have a measured mean.
    """
    layered = [float(r["net_r"]) for r in (rows or [])
               if r.get("layers") and isinstance(r.get("net_r"), (int, float))]
    flat = [float(r["net_r"]) for r in (rows or [])
            if not r.get("layers") and isinstance(r.get("net_r"), (int, float))]
    ml = round(sum(layered) / len(layered), 4) if layered else None
    fl = round(sum(flat) / len(flat), 4) if flat else None
    delta = (round(ml - fl, 4) if (ml is not None and fl is not None) else None)
    return {
        "n_layered": len(layered), "n_flat": len(flat),
        "mean_layered": ml, "mean_flat": fl, "delta": delta,
        "measured": delta is not None,
        "reading": (
            f"multi-strato vs piatto: {ml:+.3f}R vs {fl:+.3f}R "
            f"(delta {delta:+.3f})" if delta is not None
            else f"confronto multi-strato non misurato "
                 f"(multi {len(layered)}, piatte {len(flat)})"),
    }
