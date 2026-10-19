"""THE META-LEARNING ENGINE — Section C of MEGA PHASE 4 (learning how it learns).

The civilization learns strategies; it never measured HOW WELL it learns. This
module adds the second-order layer:

  * THE LEARNING EFFICIENCY METRIC -- the improvement in the best strategy per
    1,000 trials, this window vs the last, with the ACCELERATION between them.
  * THE CURRICULUM OPTIMIZER -- which lessons (the School's curriculum) came from
    the generations whose minds SURVIVED, so the lessons that produce winners are
    emphasized and the rest are retired.
  * THE CREATIVE LEAP DETECTOR -- the nights where the best strategy jumped
    DISCONTINUOUSLY, and the CONDITIONS that co-occurred with those leaps, so
    creativity can be reproduced deliberately.

Honesty (the founding rule): every metric is None until its evidence exists -- an
efficiency needs two nights, an acceleration needs three, a leap needs a baseline.
Nothing is invented.

Pure at import (Scar #6): the readings are data; the functions reduce. No I/O.
"""

from __future__ import annotations

import statistics

__all__ = [
    "efficiency_entry",
    "learning_efficiency",
    "curriculum_optimizer",
    "creative_leap",
    "leap_conditions",
    "conditions_from_night",
]


def efficiency_entry(*, date: str, best_r: float | None, trials: float | None,
                     conditions: dict | None = None) -> dict:
    """One night's row of the meta-learning history (append-only)."""
    return {"date": str(date), "best_r": best_r, "trials": trials,
            "conditions": conditions or {}}


def _best(rows: list[dict]) -> float | None:
    vals = [float(r["best_r"]) for r in rows if r.get("best_r") is not None]
    return max(vals) if vals else None


def _trials(rows: list[dict]) -> float:
    return sum(float(r.get("trials") or 0.0) for r in rows)


def _window_eff(prev_best: float | None, cur_best: float | None,
                trials: float) -> float | None:
    """R of improvement in the best strategy per 1,000 trials (None if undefined)."""
    if prev_best is None or cur_best is None or not trials:
        return None
    return (cur_best - prev_best) / (trials / 1000.0)


def learning_efficiency(history: list[dict], *, window: int = 7) -> dict:
    """This window's learning efficiency vs the prior window, and the acceleration.

    ``history`` rows are ``{date, best_r, trials}``. Honest: <2 nights -> unmeasured;
    a prior efficiency needs a third window -> the acceleration stays None.
    """
    nights = sorted((h for h in history if h.get("date") is not None),
                    key=lambda h: str(h["date"]))
    if len(nights) < 2:
        return {"measured": False, "efficiency_per_1k": None, "acceleration": None,
                "reading": "efficienza non misurata (meno di 2 notti)"}

    cur = nights[-window:]
    prior = nights[-2 * window:-window]
    if not prior:
        # a short history: the latest night vs everything before it (no overlap).
        cur = nights[-1:]
        prior = nights[:-1]
    cur_best, prior_best = _best(cur), _best(prior)
    eff_cur = _window_eff(prior_best, cur_best, _trials(cur))

    accel = None
    if len(nights) >= 3:
        pprior = nights[:max(1, len(nights) - len(cur) - len(prior))]
        if pprior and pprior != prior:
            eff_prior = _window_eff(_best(pprior), prior_best, _trials(prior))
            if eff_prior not in (None, 0) and eff_cur is not None:
                accel = round((eff_cur - eff_prior) / abs(eff_prior), 4)

    reading = "efficienza non misurata" if eff_cur is None else (
        f"efficienza {eff_cur:.4f}R/1k trial"
        + (f", accelerazione {accel:+.0%}" if accel is not None else ""))
    return {"measured": eff_cur is not None,
            "efficiency_per_1k": round(eff_cur, 6) if eff_cur is not None else None,
            "prior_best_r": prior_best, "cur_best_r": cur_best,
            "trials": _trials(cur), "acceleration": accel, "reading": reading}


def curriculum_optimizer(generations: list[dict]) -> dict:
    """Rank the School's lessons by the survival of the generations that carried them.

    ``generations`` rows are ``{generation, lessons, survivors, ranked}`` (from
    ``mind.generation_archive``). A lesson from a generation whose minds survived
    scores higher; ties break on how often it appears. Honest: no generations -> an
    empty curriculum (never an invented lesson).
    """
    scores: dict[str, dict] = {}
    for g in generations or []:
        surv = len(g.get("survivors") or [])
        for les in (g.get("lessons") or []):
            row = scores.setdefault(str(les), {"lesson": str(les), "appearances": 0,
                                               "survivors": 0, "generations": []})
            row["appearances"] += 1
            row["survivors"] += surv
            row["generations"].append(g.get("generation"))
    ranked = sorted(scores.values(),
                    key=lambda r: (-r["survivors"], -r["appearances"], r["lesson"]))
    for r in ranked:
        r["score"] = r["survivors"]
    emphasize = [r["lesson"] for r in ranked if r["survivors"] > 0][:3]
    # a lesson is RETIRED when NO generation that carried it ever produced a survivor
    # (not merely when it was absent from the emphasized few -- that would retire
    # every lesson beyond the top 3).
    retire = [r["lesson"] for r in ranked if r["survivors"] == 0][:3]
    return {"lessons": ranked, "emphasize": emphasize, "retire": retire,
            "reading": (f"curriculum: {len(ranked)} lezione/i, "
                        f"{len(emphasize)} da enfatizzare"
                        if ranked else "curriculum vuoto: nessuna generazione pesata")}


def creative_leap(history: list[dict], *, leap_factor: float = 2.0) -> dict:
    """Find the nights where the best strategy jumped DISCONTINUOUSLY.

    A leap is a night whose improvement in ``best_r`` is at least ``leap_factor`` x
    the median positive step of the history. Honest: needs >=3 nights and a positive
    baseline, else unmeasured.
    """
    nights = sorted((h for h in history if h.get("date") is not None),
                    key=lambda h: str(h["date"]))
    steps: list[tuple[dict, float]] = []
    for prev, cur in zip(nights, nights[1:]):
        b0, b1 = prev.get("best_r"), cur.get("best_r")
        if b0 is None or b1 is None:
            continue
        steps.append((cur, float(b1) - float(b0)))
    positive = [s for _, s in steps if s > 0]
    if len(nights) < 3 or not positive:
        return {"measured": False, "leaps": [], "median_step": None,
                "reading": "salti creativi non misurati (storia insufficiente)"}
    med = statistics.median(positive)
    leaps = [{"date": c.get("date"), "step_r": round(s, 4),
              "conditions": c.get("conditions") or {}}
             for c, s in steps if s >= leap_factor * med and s > 0]
    return {"measured": True, "leaps": leaps, "median_step": round(med, 4),
            "reading": (f"{len(leaps)} salto/i creativo/i su {len(steps)} passi "
                        f"(soglia {leap_factor}x la mediana {med:.3f})"
                        if leaps else "nessun salto creativo rilevato")}


def leap_conditions(leaps: list[dict]) -> dict:
    """Which conditions CO-OCCURRED with the leaps (the reproducible recipe).

    Tallies each boolean condition across the leap nights; a condition present in
    every leap is flagged as reproducible.
    """
    if not leaps:
        return {"conditions": {}, "reproducible": [],
                "reading": "nessun salto: nessuna condizione da riprodurre"}
    tally: dict[str, int] = {}
    for lp in leaps:
        for k, v in (lp.get("conditions") or {}).items():
            if v:
                tally[k] = tally.get(k, 0) + 1
    n = len(leaps)
    reproducible = sorted([k for k, c in tally.items() if c == n])
    return {"conditions": dict(sorted(tally.items())), "n_leaps": n,
            "reproducible": reproducible,
            "reading": (f"condizioni dei salti: {dict(sorted(tally.items()))}; "
                        f"riproducibili: {reproducible or 'nessuna costante'}")}


def conditions_from_night(*, one_brain: dict | None, dragon: dict | None,
                          civilization: dict | None) -> dict:
    """Read a night's creativity conditions from the artifacts (honest booleans)."""
    ob = one_brain or {}
    dr = dragon or {}
    civ = civilization or {}
    play = ob.get("play") or {}
    play_items = ob.get("play_items") or []
    regime = (civ.get("regime") or {}).get("regimes") or {}
    total = sum(int(v or 0) for v in regime.values())
    dead = int(regime.get("dead") or 0)
    return {
        "playground_active": bool(play.get("played") or play_items),
        "dragon_session": bool((dr.get("beat") or {}).get("thought", {}).get("ok")
                               or dr.get("available")),
        "unusual_regime": (total > 0 and dead / total >= 0.5),
    }
