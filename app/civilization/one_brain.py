"""THE ONE BRAIN — the collective that decides (the One Brain, Part Two).

This is the single deciding mind: hundreds of individual faculties (``mind``)
integrated into ONE decision with a soul. It is NOT a vote — it is a WEIGHTED
FIELD, where each contributing mind's input counts in proportion to its MEASURED
reliability (calibration, simulation accuracy, intuition hit-rate, theory survival,
emotional calibration). Minds that think well matter more.

  * THE INTEGRATION LAYER — ``integration_package``: every proposal carries its
    complete cognitive package (analysis, intuition, emotion, simulation, theory,
    lineage).
  * THE WEIGHING — ``reliability_weights`` + ``weigh``: the reliability-weighted
    field, recomputed nightly, heritable.
  * THE DECISION — ``decide``: a trade is born only when the integrated field
    clears the bar; the DECISION RECORD carries its full soul.
  * THE VETO — ``veto``: checks the THINKING, not just the rules.
  * THE KELLY VOICE — ``kelly_voice``: advises only; the 1% Titanium Floor is law.
  * THE UNIFIED MARKET MODEL — ``market_model`` / ``market_model_changed``: one
    shared, versioned picture of how the market relates.
  * THE EMERGENCE METRIC — ``synergy_score`` / ``metacognition_generation``: does
    the One Brain exceed the sum of its parts?

Pure at import (Scar #6): a reduction over the caller's data. No I/O, no clock, no
RNG. Honest measurement (R47): an unmeasured quantity is ``None`` — never invented.
"""

from __future__ import annotations

from app.civilization import gaze
from app.civilization import mind
from app.civilization import tongue

__all__ = [
    "INTUITION_BAR",
    "DANGER_SHARE",
    "SUPPORT_BAR",
    "VISION_BAR",
    "TITANIUM_FLOOR",
    "integration_package",
    "cognitive_view",
    "second_sight",
    "reliability_weights",
    "weigh",
    "decide",
    "veto",
    "refusal_entry",
    "reconsider_refusals",
    "veto_calibration",
    "kelly_voice",
    "market_model",
    "market_model_changed",
    "synergy_score",
    "metacognition_generation",
]

# The gates the integrated field must clear for a decision to be born.
INTUITION_BAR: float = 0.5      # the strongest pattern-recognizers must agree
DANGER_SHARE: float = 0.5       # a population this afraid screams danger
SUPPORT_BAR: float = 0.5        # weighted support must beat weighted opposition
# The Gaze: a visual-context claim must SEE this clearly to be called convergent
# seeing (below it the eye's read is reported but not treated as convergence).
VISION_BAR: float = 0.6
# The 1% Titanium Floor is LAW: the Kelly voice advises, and can never size above it.
TITANIUM_FLOOR: float = 0.01


# --- THE INTEGRATION LAYER --------------------------------------------------

def integration_package(*, proposal: dict, thought: dict | None = None,
                        intuition: dict | None = None, emotion: str | None = None,
                        simulation: dict | None = None, theory: dict | None = None,
                        visual: dict | None = None,
                        lineage: list[str] | None = None) -> dict:
    """Assemble a proposal's COMPLETE cognitive package (the integration layer).

    Every field is optional and honestly absent when the mind did not produce it —
    the package never fabricates an analysis, an intuition, or a simulation it does
    not have. ``visual`` is the Gaze's context: what the eyes SAW of this proposal
    (a VEDO claim), carried as first-class evidence into the deliberation.
    """
    return {
        "proposal": dict(proposal or {}),
        "analysis": thought,
        "intuition": intuition,
        "emotion": emotion,
        "simulation": simulation,
        "theory": theory,
        "visual": visual,
        "lineage": list(lineage or []),
    }


# --- C3 — THE ORACLE'S SECOND SIGHT (the brain feeds the scorer) ------------

def cognitive_view(package: dict) -> dict:
    """Adapt a cognitive PACKAGE into the flat view the Oracle's second sight reads.

    The Oracle's :func:`app.pyramid.oracle.combiner.second_sight` consumes
    ``{intuition, theory, simulation, emotion, covered}``; a package stores the same
    facts nested under ``analysis``/``intuition``/... This bridge is the ONE place
    the brain and the scorer meet — a pure reduction, honest (missing stays missing).
    """
    pkg = package or {}
    return {
        "intuition": pkg.get("intuition"),
        "theory": pkg.get("theory"),
        "simulation": pkg.get("simulation"),
        "emotion": pkg.get("emotion"),
        "covered": pkg.get("covered"),
    }


def second_sight(package: dict) -> dict:
    """The Oracle's second sight over a cognitive package (imported lazily).

    Lazy import: the Oracle lives in the pyramid, the brain in the civilization —
    keeping the import at call time preserves the pure, bottom-up import graph.
    """
    from app.pyramid.oracle.combiner import second_sight as _ss
    return _ss(cognitive_view(package))


# --- THE WEIGHING (the reliability-weighted field) --------------------------

def reliability_weights(minds: dict) -> dict:
    """Recompute each mind's weight from its MEASURED reliability axes (nightly).

    ``minds`` maps an agent to its reliability axes (calibration, simulation
    accuracy, intuition hit-rate, theory survival, emotional calibration). A mind
    with no measured axis gets weight ``None`` (it is not trusted) — the weights are
    honest and heritable (king-children inherit their parent's cognitive DNA).
    """
    out: dict[str, float | None] = {}
    for agent, axes in (minds or {}).items():
        a = axes or {}
        out[str(agent)] = mind.thinking_weight(
            calibration=a.get("calibration"),
            simulation_accuracy=a.get("simulation_accuracy"),
            intuition_hit_rate=a.get("intuition_hit_rate"),
            theory_survival=a.get("theory_survival"),
            emotional_calibration=a.get("emotional_calibration"))
    return out


def weigh(*, supporters: list[str], opposers: list[str],
          weights: dict, visual_supporters: list[str] | None = None) -> dict:
    """The weighted field for one proposal: supporters vs opposers, by reliability.

    The score is ``(support - oppose) / (support + oppose)`` over the MEASURED
    weights. ``score`` is ``None`` when no weighted mind contributed — an unweighed
    proposal is never flattered to a verdict.

    THE EYES WEIGH (the Gaze, Part Five): a supporter whose mode was VEDO ("I SEE")
    carries the eye's extra trust (:data:`gaze.VEDO_FIELD_BONUS`). The bonus is a
    stated constant, not a hidden multiplier; an unmeasured mind still weighs 0.
    """
    sup = sum(float(weights.get(a) or 0.0) for a in supporters)
    vis = set(visual_supporters or [])
    bonus = sum(float(weights.get(a) or 0.0) * (gaze.VEDO_FIELD_BONUS - 1.0)
                for a in supporters if a in vis)
    opp = sum(float(weights.get(a) or 0.0) for a in opposers)
    total = sup + bonus + opp
    score = round((sup + bonus - opp) / total, 6) if total > 0 else None
    return {"support": round(sup, 6), "visual_support": round(bonus, 6),
            "oppose": round(opp, 6),
            "score": score, "supporters": list(supporters),
            "visual_supporters": sorted(vis & set(supporters)),
            "opposers": list(opposers), "weighed_minds": len(supporters) + len(opposers)}


# --- THE DECISION (with a soul) ---------------------------------------------

def decide(pkg: dict, *, weights: dict, mood: dict, model: dict | None = None,
           supporters: list[str] | None = None, opposers: list[str] | None = None,
           visual_supporters: list[str] | None = None, ts: str = "") -> dict | None:
    """The DECISION RECORD — a trade born only when the integrated field clears.

    Every gate is explicit and honest: the analysis must be sound (a falsifier and a
    prediction), the strongest pattern-recognizers must agree (a confident
    intuition), the collective emotion must not be screaming danger, the
    simulation's fragile points must be covered by the plan, and the theory must
    survive. The record carries its SOUL: which minds supported it, which opposed,
    the collective mood, and what the simulation feared. Returns ``None`` when any
    gate fails (no trade — honest).
    """
    prop = pkg.get("proposal") or {}
    analysis = pkg.get("analysis") or {}
    intuition = pkg.get("intuition") or {}
    sim = pkg.get("simulation") or {}
    theory = pkg.get("theory") or {}

    reasons: list[str] = []
    # 1. sound analysis: the deliberate mind produced a falsifier and a prediction.
    if not str(analysis.get("falsifier", "")).strip() or \
       not str(analysis.get("prediction", "")).strip():
        reasons.append("analisi non solida: manca falsificatore o previsione")
    # 2. the strongest pattern-recognizers agree (a confident, BULLISH intuition).
    #    ``intuition_confidence`` measures the gut's STRENGTH (|2*up/seen - 1|), not
    #    its DIRECTION: a shape seen 1-up-of-10 is confident (0.8) but expects a
    #    LOSS. Clearing the "intuitions agree" gate on strength alone let a bearish
    #    gut endorse a long trade — a direction bug (BUG-8). A gut with a measured
    #    direction must lean UP; an unmeasured-direction gut is judged by strength.
    conf = intuition.get("confidence")
    seen = intuition.get("seen")
    up = intuition.get("up")
    if conf is None or float(conf) < INTUITION_BAR:
        reasons.append("nessuna intuizione forte concorde")
    elif isinstance(seen, int) and seen > 0 and isinstance(up, int) and up * 2 < seen:
        reasons.append("l'intuizione e' forte ma ribassista: il gut prevede una perdita")
    # 3. the collective emotion is not screaming danger.
    counts = (mood or {}).get("counts") or {}
    pop = (mood or {}).get("population") or 0
    fear_share = (counts.get("fear", 0) / pop) if pop else 0.0
    if fear_share >= DANGER_SHARE:
        reasons.append(f"l'umore collettivo grida pericolo (paura {fear_share:.0%})")
    # 4. the simulation's fragile points are covered by the plan.
    if not sim.get("fragile_points"):
        reasons.append("simulazione senza punti fragili: overconfidence")
    # 5. the theory survives (a falsified theory cannot justify a trade).
    if str(theory.get("status", "")) == "falsified":
        reasons.append("la teoria e' stata falsificata dai dati")
    # 6. the world model must not contradict the trade (when one exists).
    if model and str(model.get("status", "")) == "contradicts":
        reasons.append("il modello del mondo contraddice il trade")

    field = weigh(supporters=list(supporters or []), opposers=list(opposers or []),
                  weights=weights, visual_supporters=visual_supporters)
    if field["score"] is None or field["score"] < SUPPORT_BAR:
        reasons.append("il campo pesato non supera la soglia di supporto")

    if reasons:
        return {"ts": ts, "proposal": prop, "decided": False, "reasons": reasons,
                "field": field, "soul": None}
    return {
        "ts": ts, "proposal": prop, "decided": True, "reasons": [],
        "field": field,
        "soul": {
            "supporters": field["supporters"], "opposers": field["opposers"],
            "mood": (mood or {}).get("dominant"),
            "simulation_fears": sim.get("fragile_points", []),
            "theory": theory.get("claim"),
            "analysis": analysis.get("hypothesis"),
            "visual": pkg.get("visual"),
            "lineage": pkg.get("lineage", []),
        },
    }


# --- THE VETO (the buttafuori, cognitively complete) ------------------------

def veto(decision: dict, *, belief_ledger: list[dict], mood: dict) -> dict:
    """The cognitively-complete veto: check the THINKING, not only the rules.

    A proposal is vetoed when it contradicts a recorded belief reversal (the belief
    ledger), when the emotion is clouding the analysis (fear at danger levels with a
    decided trade), or when its simulation's fragile point was left uncovered.
    Returns ``{"vetoed": bool, "reasons": [...]}``.
    """
    if not decision.get("decided"):
        return {"vetoed": False, "reasons": []}
    reasons: list[str] = []
    prop = decision.get("proposal") or {}
    soul = decision.get("soul") or {}
    # 1. consistency with the belief ledger: the idea was RETRACTED (believed, then
    #    abandoned). A retraction is recorded with ``after`` = "(retracted)"; the
    #    match is on the row's *before* text (what was believed), not on the
    #    placeholder — matching the placeholder was a dead check (BUG-4).
    idea = str(prop.get("idea") or prop.get("what") or "").lower()
    for b in belief_ledger or []:
        retracted = "retract" in str(b.get("after", "")).lower()
        believed = str(b.get("before", "")).lower()
        if idea and retracted and (idea in believed or believed in idea):
            reasons.append(f"contraddice il belief ledger: {b.get('reason')}")
    # 2. emotion clouding the analysis.
    counts = (mood or {}).get("counts") or {}
    pop = (mood or {}).get("population") or 0
    if pop and counts.get("fear", 0) / pop >= DANGER_SHARE:
        reasons.append("la paura collettiva sta annebbiando l'analisi")
    # 3. an uncovered fragile point: the plan claims to cover some conditions, but a
    #    feared condition is NOT among them. The old loop was a no-op (it never
    #    appended a reason) — a fragile point the plan forgot was never vetoed.
    fears = soul.get("simulation_fears") or []
    covered = set(soul.get("covered") or prop.get("covers") or [])
    if prop.get("covers") or soul.get("covered"):
        for f in fears:
            if f not in covered:
                reasons.append(f"punto fragile non coperto dal piano: {f}")
    return {"vetoed": bool(reasons), "reasons": reasons}


# --- C4 — THE VETO'S MEMORY (the ledger of refusals) ------------------------

def refusal_entry(decision: dict, *, ts: str = "") -> dict:
    """Record a REFUSAL in the veto's memory: what was blocked, and WHY.

    Every rejected proposal is remembered so it can be re-evaluated LATER ("was the
    veto right?"). Carries the idea, the veto's reasons, and the field score — the
    honest fingerprint of the refusal. ``was_right`` stays ``None`` until the world
    answers (never a self-congratulating default).
    """
    prop = decision.get("proposal") or {}
    reasons = [str(r) for r in (decision.get("reasons") or [])]
    return {
        "ts": ts,
        "idea": prop.get("idea") or prop.get("what"),
        "reasons": reasons,
        "field_score": (decision.get("field") or {}).get("score"),
        "vetoed": bool(decision.get("vetoed")),
        "was_right": None,   # unmeasured until the night's outcome is known
        "reading": f"rifiutato: {prop.get('idea') or prop.get('what')} — {'; '.join(reasons)}",
    }


def reconsider_refusals(refusals: list[dict], *, survivors: list[str] | None = None,
                        ts: str = "") -> list[dict]:
    """Re-evaluate past refusals: "was the veto right?" (the veto learns from history).

    A refusal is marked ``was_right`` when the night's REAL survivors are known: a
    veto was RIGHT if no surviving strategy matches the blocked idea's shape (the
    thing the veto blocked did not become a winner), and WRONG if a survivor's
    family matches the blocked idea. Honest: with no survivors measured the
    ``was_right`` stays ``None`` (never an invented verdict).
    """
    surv = {str(s).lower() for s in (survivors or [])}
    out: list[dict] = []
    for r in refusals or []:
        row = dict(r)
        idea = str(row.get("idea") or "").lower()
        if surv and idea:
            matched = any(s in idea or idea in s for s in surv)
            row["was_right"] = (not matched)
            row["reconsidered_ts"] = ts
        out.append(row)
    return out


def veto_calibration(refusals: list[dict]) -> dict:
    """The veto's own calibration: of the refusals we could judge, how many were right?

    ``rate`` is ``None`` when nothing has been judged yet (honest — the veto has no
    track record). ``accuracy`` is the share of judged refusals that were right.
    """
    judged = [r for r in (refusals or []) if r.get("was_right") is not None]
    if not judged:
        return {"judged": 0, "right": 0, "rate": None,
                "reading": "calibrazione del veto non misurata (nessun rifiuto giudicato)"}
    right = sum(1 for r in judged if r["was_right"])
    rate = round(right / len(judged), 6)
    return {"judged": len(judged), "right": right, "rate": rate,
            "reading": (f"il veto aveva ragione {right}/{len(judged)} volte "
                        f"({rate:.0%})")}


# --- THE KELLY VOICE (advisory only) ----------------------------------------

def kelly_voice(edge: float | None, *, floor: float = TITANIUM_FLOOR) -> dict:
    """The Kelly-optimal conviction for a proposal — ADVISORY ONLY.

    Reports the edge strength and the Kelly fraction it implies, but the advised
    size is pinned to the 1% Titanium Floor: it can never be undercut or overridden
    by the system (an edge strong enough to suggest more is a decision for the CEO,
    flagged with ``wants_more``). ``edge`` unmeasured -> ``None`` conviction.
    """
    if edge is None:
        return {"edge": None, "kelly_fraction": None, "advised_size": floor,
                "floor": floor, "wants_more": False, "reading": "conviction non misurata"}
    e = float(edge)
    f = max(0.0, min(1.0, e))          # a bounded Kelly fraction from the edge
    return {"edge": round(e, 6), "kelly_fraction": round(f, 6),
            "advised_size": floor, "floor": floor, "wants_more": f > floor,
            "reading": (f"edge {round(e, 4)}; il sistema consiglia {floor:.0%} (Floor); "
                        + ("l'edge suggerisce di piu' — decide il CEO" if f > floor
                           else "entro la Legge"))}


# --- THE UNIFIED MARKET MODEL (the Renaissance secret) ----------------------

def market_model(*, pairs: list[str] | None = None, flows: dict | None = None,
                 regimes: dict | None = None, sessions: dict | None = None,
                 version: int = 1, ts: str = "") -> dict:
    """ONE shared, versioned picture of how the market relates (the world model).

    Every agent's experience feeds it: the pairs in play, the flows, the regimes,
    the sessions. It is the civilization's shared reality — updated nightly,
    questioned by the philosophers, versioned like the certificates. Honest: an axis
    with no measurement is an empty structure, never an invented relationship.
    """
    return {
        "version": int(version), "ts": ts,
        "pairs": sorted(str(p) for p in (pairs or [])),
        "flows": {str(k): v for k, v in (flows or {}).items()},
        "regimes": {str(k): v for k, v in (regimes or {}).items()},
        "sessions": {str(k): v for k, v in (sessions or {}).items()},
        "belief": "il modello non ha ancora una lettura del mondo",
    }


def market_model_changed(old: dict | None, new: dict) -> dict:
    """What the civilization now believes DIFFERENTLY about the market (versioned).

    Compares two model versions across the pairs/regimes axes and reports the
    changes; ``changed`` is False and the reading is honest when nothing moved (or
    when there is no prior model — a first version is not a change).
    """
    if not old:
        return {"changed": False, "version": new.get("version"),
                "changes": [], "reading": "primo modello del mondo (nessun confronto)"}
    changes: list[str] = []
    for axis in ("pairs", "regimes", "sessions", "flows"):
        o, n = old.get(axis) or {}, new.get(axis) or {}
        if isinstance(o, list):
            o = {x: True for x in o}
        if isinstance(n, list):
            n = {x: True for x in n}
        for k in sorted(set(o) | set(n)):
            if o.get(k) != n.get(k):
                changes.append(f"{axis}.{k}: {o.get(k)!r} -> {n.get(k)!r}")
    return {"changed": bool(changes), "version": new.get("version"),
            "changes": changes,
            "reading": (f"il modello e' cambiato: {'; '.join(changes[:3])}"
                        if changes else "il modello del mondo non e' cambiato")}


# --- THE EMERGENCE METRIC (does the One Brain exceed the sum?) --------------

def synergy_score(*, collective_quality: float | None,
                  best_individual_quality: float | None) -> float | None:
    """The SYNERGY SCORE: the One Brain's quality vs the best single mind's.

    ``> 1`` means the collective is truly greater than its parts. ``None`` when
    either side is unmeasured (no invented proof that the architecture works).
    """
    if collective_quality is None or best_individual_quality is None:
        return None
    b = float(best_individual_quality)
    if b == 0.0:
        return None
    return round(float(collective_quality) / b, 6)


def metacognition_generation(*, generation: int, quality: float | None,
                             previous: float | None) -> dict:
    """Compare a generation's reasoning quality to the previous (intelligence evolves).

    "Generation N thinks X% better than N-1". ``delta_pct`` is ``None`` when either
    quality is unmeasured — the evolution of intelligence is never invented.
    """
    if quality is None or previous is None or float(previous) == 0.0:
        return {"generation": int(generation), "quality": quality,
                "previous": previous, "delta_pct": None,
                "reading": f"generazione {generation}: confronto non misurato"}
    delta = (float(quality) - float(previous)) / abs(float(previous)) * 100.0
    return {"generation": int(generation), "quality": round(float(quality), 6),
            "previous": round(float(previous), 6), "delta_pct": round(delta, 3),
            "reading": f"generazione {generation} pensa {delta:+.1f}% vs la precedente"}
