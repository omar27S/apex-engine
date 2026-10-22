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
    """Rank the School's lessons by the IMPROVEMENT they carried, not the summit they reached.

    R142 — THE DELTA TEACHER. The old law scored a lesson by the absolute survivors
    of the generations that carried it; in a civilization where nobody survives yet
    (the honest present), EVERY lesson scored zero, ``emphasize`` went empty and the
    ``retire`` list was drawn from ties — the teacher was destroying curriculum at
    random while the class was still learning to walk. The new law:

    * A lesson's PRIMARY evidence is the DELTA it carried — the generations WITH it
      vs the generations WITHOUT it (its own era as the control group), measured on
      survivors (the crown) and on the ranked-mind count (the engagement gradient
      that lives even at zero survivors). An association, said aloud as one — the
      teacher recommends, the School decides.
    * A surviving generation's lesson is STILL emphasized (the sufficient crown —
      the old law's truth, kept).
    * Retirement needs COMPARATIVE HARM, seen at least twice: a lesson carried by
      generations that did measurably WORSE on survivors than their era. Absence of
      survivors is NOT harm — the old retire-on-absence law dies here.
    * One appearance is an ANECDOTE, never a curriculum entry: unmeasured, kept.

    ``generations`` rows are ``{generation, lessons, survivors, ranked}`` (from
    ``mind.generation_archive``); ``survivors``/``ranked`` may be a count or a list.
    Honest: no generations -> an empty curriculum (never an invented lesson).
    """
    def _count(v) -> int:
        if isinstance(v, (list, tuple, set)):
            return len(v)
        if isinstance(v, bool) or v is None:
            return 0
        if isinstance(v, (int, float)):
            return int(v)
        return 0

    rows = [g for g in (generations or []) if isinstance(g, dict)]
    carriers: dict[str, list[dict]] = {}
    for g in rows:
        for les in (g.get("lessons") or []):
            carriers.setdefault(str(les), []).append(g)

    scored: list[dict] = []
    for les, with_gens in carriers.items():
        with_ids = {id(g) for g in with_gens}
        era = [g for g in rows if id(g) not in with_ids]
        appearances = len(with_gens)
        surv_sum = sum(_count(g.get("survivors")) for g in with_gens)
        ranked_sum = sum(_count(g.get("ranked")) for g in with_gens)
        delta_surv = delta_ranked = None
        if with_gens and era:
            m_surv_with = surv_sum / len(with_gens)
            m_surv_out = sum(_count(g.get("survivors")) for g in era) / len(era)
            m_rk_with = ranked_sum / len(with_gens)
            m_rk_out = sum(_count(g.get("ranked")) for g in era) / len(era)
            delta_surv = round(m_surv_with - m_surv_out, 4)
            delta_ranked = round(m_rk_with - m_rk_out, 4)
        scored.append({
            "lesson": les, "appearances": appearances, "survivors": surv_sum,
            "ranked_minds": ranked_sum, "delta_survivors": delta_surv,
            "delta_ranked": delta_ranked,
            "generations": [g.get("generation") for g in with_gens],
        })

    emphasized: list[str] = []
    retired: list[str] = []
    anecdotes = 0
    for r in scored:
        enough = r["appearances"] >= 2
        crowned = r["survivors"] > 0
        improving = enough and (
            (r["delta_survivors"] or 0) > 0 or (r["delta_ranked"] or 0) > 0)
        harmful = (enough and r["delta_survivors"] is not None
                   and r["delta_survivors"] < 0)
        if crowned or improving:
            r["verdict"] = "emphasize"
            emphasized.append(r["lesson"])
        elif harmful:
            r["verdict"] = "retire"
            retired.append(r["lesson"])
        elif enough:
            r["verdict"] = "hold"  # tested enough, no comparative harm: kept
        else:
            r["verdict"] = "anecdote"  # one appearance is not a curriculum
            anecdotes += 1
        r["score"] = r["survivors"]  # the crown stays the primary rank (legacy)

    ranked = sorted(scored, key=lambda r: (-r["survivors"],
                                           -(r["delta_survivors"]
                                             if r["delta_survivors"] is not None
                                             else -1e9),
                                           -r["appearances"], r["lesson"]))
    return {"lessons": ranked, "emphasize": emphasized[:3], "retire": retired[:3],
            "anecdotes": anecdotes,
            "reading": (f"curriculum: {len(ranked)} lezione/i, "
                        f"{len(emphasized)} da enfatizzare, {len(retired)} in "
                        f"ritiro comparativo, {anecdotes} aneddotiche"
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
