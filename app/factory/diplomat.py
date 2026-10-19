"""THE DIPLOMAT -- the hyper-heuristic meta-brain (Mega Phase 2, Section F, Lever 16).

The tournament evolves; the Diplomat decides HOW. It watches the population's STATE
and selects an OPERATOR from a sealed menu, so the factory's behaviour is chosen from
evidence rather than fixed in code:

  * diversity LOW (everyone looks the same)          -> MUTATE / RANDOM / DIVERSIFY
  * diversity HIGH but performance LOW (chaos)       -> PRUNE / REFINE (exploit)
  * performance FLAT for 3+ generations              -> SPECIALIZE / HYBRIDIZE (restructure)
  * performance RISING                               -> keep refining (don't break it)

Each operator carries a MEASURED EFFECT SIZE (how much it moved the population the last
time it was used). The Diplomat weighs: the current state + the historical operator
effectiveness + the Dragon's recommendation, and emits ONE decision with its reasoning.

Honesty is binding: an operator never used has effect ``None`` (never a fabricated
zero); a flat/rising reading with no history is labelled unmeasured. The report is the
weekly Letter line: which operators ran, their measured effect, and next week's plan.

Pure at import (Scar #6): the population, the history and the Dragon's word come from
the caller.
"""

from __future__ import annotations

__all__ = [
    "DIPLOMAT_VERSION",
    "OPERATORS",
    "FLAT_GENERATIONS",
    "MAX_OPERATORS",
    "population_state",
    "operator_effect_sizes",
    "select_operator",
    "diplomat_block",
]

DIPLOMAT_VERSION: int = 1

# The sealed operator menu (the directive's eight moves).
OPERATORS: tuple[str, ...] = (
    "MUTATE", "CROSSOVER", "DIRECT", "RANDOM",
    "PRUNE", "SPECIALIZE", "DIVERSIFY", "HYBRIDIZE",
)

# Performance is "flat" after this many generations without a material move.
FLAT_GENERATIONS: int = 3
# At most this many operators are ordered per generation (the directive's menu draw).
MAX_OPERATORS: int = 2

_MATERIAL_MOVE: float = 0.01  # in R


def population_state(population: list[dict], *, performance_history: list[float] | None = None,
                     diversity_bar: float = 0.35) -> dict:
    """Read the population's diversity + performance trend from REAL rows.

    ``population`` is a list of ``{family, net_r, ...}`` rows; ``diversity_bar`` is the
    distinct-family share above which the population is considered diverse. Honest:
    with no rows the state is ``measured=False``.
    """
    rows = [r for r in (population or []) if isinstance(r, dict)]
    n = len(rows)
    if n == 0:
        return {"measured": False, "n": 0, "diversity": None,
                "performance": None, "trend": "unmeasured",
                "reading": "diplomato: popolazione non misurata"}
    fams = [str(r.get("family") or "") for r in rows]
    distinct = len({f for f in fams if f})
    diversity = distinct / n
    # family entropy, a second diversity view (0 = monoculture)
    counts: dict[str, int] = {}
    for f in fams:
        counts[f] = counts.get(f, 0) + 1
    ent = 0.0
    for c in counts.values():
        p = c / n
        ent -= p * (p if p > 0 else 1)
    perf_vals = [float(r["net_r"]) for r in rows if isinstance(r.get("net_r"), (int, float))]
    performance = (sum(perf_vals) / len(perf_vals)) if perf_vals else None
    hist = [float(x) for x in (performance_history or []) if isinstance(x, (int, float))]
    trend = "unmeasured"
    if len(hist) >= 2:
        recent = hist[-(FLAT_GENERATIONS + 1):]
        deltas = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
        if deltas and all(abs(d) < _MATERIAL_MOVE for d in deltas):
            trend = "flat"
        elif deltas and deltas[-1] > _MATERIAL_MOVE:
            trend = "rising"
        elif deltas and deltas[-1] < -_MATERIAL_MOVE:
            trend = "falling"
        else:
            trend = "flat"
    return {"measured": True, "n": n, "diversity": round(diversity, 4),
            "family_entropy": round(ent, 4), "performance": performance,
            "trend": trend, "diverse": bool(diversity >= diversity_bar),
            "reading": (f"diplomato: diversita' {diversity:.2f}, "
                        f"performance {performance if performance is None else round(performance, 3)}, "
                        f"tendenza {trend}")}


def operator_effect_sizes(history: list[dict]) -> dict:
    """Measure each operator's EFFECT SIZE (mean performance delta the rounds it ran).

    ``history`` is a list of ``{operators: [...], delta: float}`` rounds. An operator
    never used is absent from the result (its effect is UNMEASURED, never a fabricated
    0.0). The returned dict maps ``operator -> {effect, n}``.
    """
    acc: dict[str, list[float]] = {}
    for round_ in (history or []):
        ops = round_.get("operators") if isinstance(round_, dict) else None
        delta = round_.get("delta") if isinstance(round_, dict) else None
        if not isinstance(delta, (int, float)):
            continue
        for op in (ops or []):
            acc.setdefault(str(op), []).append(float(delta))
    return {op: {"effect": round(sum(v) / len(v), 5), "n": len(v)}
            for op, v in acc.items() if v}


def select_operator(state: dict, *, operator_stats: dict | None = None,
                    dragon_recommendation: str | None = None) -> dict:
    """Choose the operators for the next generation, with a stated reason.

    Priority (the directive's rules):
      1. FLAT trend -> restructure (SPECIALIZE + HYBRIDIZE);
      2. performance FALLING -> refresh (RANDOM + DIVERSIFY);
      3. diversity LOW -> explore (MUTATE + RANDOM);
      4. diversity HIGH but performance LOW/negative -> exploit (PRUNE + CROSSOVER);
      5. performance RISING -> refine gently (CROSSOVER + DIRECT).
    The Dragon's recommendation, when it names a valid operator, is folded in first.
    Returns ``{operators, reason, measured, basis}``.
    """
    if not state.get("measured"):
        return {"operators": [], "reason": "stato non misurato", "measured": False}
    trend = state.get("trend")
    diverse = state.get("diverse")
    perf = state.get("performance")
    chosen: list[str] = []
    reason = ""
    if trend == "flat":
        chosen = ["SPECIALIZE", "HYBRIDIZE"]
        reason = f"performance piatta per {FLAT_GENERATIONS}+ generazioni -- ristrutturare"
    elif trend == "falling":
        chosen = ["RANDOM", "DIVERSIFY"]
        reason = "performance in calo -- rinfrescare l'esplorazione"
    elif not diverse:
        chosen = ["MUTATE", "RANDOM"]
        reason = "diversita' bassa -- mutazione aggressiva ed esplorazione"
    elif perf is not None and perf <= 0:
        chosen = ["PRUNE", "CROSSOVER"]
        reason = "diversita' alta ma performance debole -- sfruttare e potare"
    else:
        chosen = ["CROSSOVER", "DIRECT"]
        reason = "performance in crescita -- raffinare senza rompere"
    dragon = str(dragon_recommendation or "").upper()
    if dragon in OPERATORS and dragon not in chosen:
        chosen = [dragon] + [c for c in chosen][:MAX_OPERATORS - 1]
        reason += f"; il Drago raccomanda {dragon}"
    # tie-break by measured effect: if a chosen operator has a NEGATIVE measured
    # effect and an unchosen one is positive, prefer the positive one (evidence).
    stats = operator_stats or {}
    if stats:
        for i, op in enumerate(list(chosen)):
            eff = (stats.get(op) or {}).get("effect")
            if isinstance(eff, (int, float)) and eff < 0:
                better = [o for o in OPERATORS
                          if isinstance((stats.get(o) or {}).get("effect"), (int, float))
                          and stats[o]["effect"] > eff and o not in chosen]
                if better:
                    better.sort(key=lambda o: -stats[o]["effect"])
                    chosen[i] = better[0]
                    reason += f"; sostituito {op} con {better[0]} (effetto misurato)"
    return {"operators": chosen[:MAX_OPERATORS], "reason": reason,
            "measured": True, "basis": {"trend": trend, "diverse": diverse, "perf": perf}}


def diplomat_block(population: list[dict], *, performance_history: list[float] | None = None,
                   operator_history: list[dict] | None = None,
                   dragon_recommendation: str | None = None) -> dict:
    """The weekly Letter block: the state, the decision, the measured effects, the plan."""
    state = population_state(population, performance_history=performance_history)
    stats = operator_effect_sizes(operator_history or [])
    decision = select_operator(state, operator_stats=stats,
                               dragon_recommendation=dragon_recommendation)
    effects = {op: stats[op] for op in OPERATORS if op in stats}
    return {
        "version": DIPLOMAT_VERSION,
        "state": state,
        "decision": decision,
        "operator_effects": effects,
        "measured": bool(decision.get("measured")),
        "reading": (f"IL DIPLOMATO HA DECISO: {', '.join(decision['operators']) or '--'} "
                    f"-- {decision['reason']}"
                    if decision.get("measured") else
                    "IL DIPLOMATO HA DECISO: -- (stato non misurato)"),
    }
