"""THE RED COUNCIL -- the anti-fragility engine (THE REAL HUNT, Part Five).

A system that only argues FOR its own trades is fragile: it cannot see its own
blindness. The Red Council is the standing opposition:

  * THE PERMANENT DEVIL'S ADVOCATE -- before any CLASS A signal the Red Council MUST
    present the strongest possible case AGAINST the trade (built from the ACTUAL
    weaknesses: an unmeasured required column, a column whose measured accuracy is
    poor, the Dragon's objection). The signal fires ONLY IF the Cathedral's case
    SURVIVES the attack;
  * THE WEEKLY SELF-NEGATION -- every week the Dragon writes the "ANTI-REPORT": the
    case that everything the system believes is WRONG (the top strategies may be
    overfit, the regime model may see patterns in noise, the edge may be decaying).
    The system then ACTIVELY SEEKS evidence (anti-strategies, regime anomalies, a
    shrinking live edge). Found -> adapt before the market punishes; not found ->
    confidence is TESTED, not assumed;
  * THE CASSANDRA PROTOCOL -- the Red Council is REWARDED for being right when the
    majority is wrong.

Honesty is binding: the devil's argument is constructed from the REAL weaknesses of
the proposal, never invented; a case "survives" only when no MEASURED counter exists
(an unmeasured axis is named as an unknown, not fabricated into a refutation); the
Cassandra ledger moves only on a real resolved outcome. Pure at import (Scar #6).
"""

from __future__ import annotations

__all__ = [
    "RED_COUNCIL_VERSION",
    "red_council",
    "devil_advocate",
    "weekly_self_negation",
    "cassandra_reward",
    "red_council_block",
]

RED_COUNCIL_VERSION: int = 1

# A confirmed column whose measured accuracy is below this is a MEASURED weakness.
WEAK_COLUMN_ACCURACY: float = 0.50


def red_council(state: dict) -> dict:
    """The Red Council's persistent structures (created empty on first access)."""
    st = state if state is not None else {}
    return st.setdefault("red_council", {
        "version": RED_COUNCIL_VERSION,
        "challenges": [],       # the devil's arguments (and whether the case survived)
        "anti_reports": [],     # the weekly self-negations
        "cassandra": {"hits": 0, "n": 0},   # right when the majority was wrong
        "last": None,
    })


def devil_advocate(state: dict, proposal: dict, *, ts: str = "") -> dict:
    """Attack a proposed CLASS A signal with the strongest measured counter-case.

    The attack is built from the proposal's REAL weaknesses: an unmeasured required
    column (an unknown), a confirmed column whose measured accuracy is poor, or the
    Dragon's recorded objection. ``survives`` is True only when NO measured counter
    exists (the case stands, tested). Honest: an unmeasured column is named as an
    unknown, never fabricated into a refutation.
    """
    p = proposal or {}
    gate = p.get("gate") or {}
    cols = p.get("columns") or []
    accuracies = p.get("accuracies") or {}
    dragon_objection = p.get("dragon_objection")

    counters: list[dict] = []
    unmeasured = [c.get("column") for c in cols
                  if c.get("confirmed") is True and not c.get("measured")]
    # (a confirmed column is by construction measured; keep the guard for safety)
    for c in cols:
        name = c.get("column")
        if c.get("confirmed") is not True:
            continue
        a = (accuracies.get(name) or {})
        acc = a.get("accuracy")
        if isinstance(acc, (int, float)) and acc < WEAK_COLUMN_ACCURACY:
            counters.append({"kind": "weak_column", "column": name,
                             "accuracy": acc,
                             "reading": f"la colonna {name} ha sbagliato "
                                        f"{1 - acc:.0%} delle volte"})
    for name in unmeasured:
        counters.append({"kind": "unmeasured", "column": name,
                         "reading": f"la colonna {name} e' un'incognita"})
    if dragon_objection:
        counters.append({"kind": "dragon", "reading": str(dragon_objection)})

    measured_counters = [c for c in counters if c["kind"] in ("weak_column", "dragon")]
    survives = not measured_counters and gate.get("class") == "A"
    if not counters:
        argument = ("non trovo una crepa misurata: l'accusa non regge -- il caso "
                    "della Cattedrale SOPRAVVIVE all'attacco")
    else:
        argument = "il caso piu' forte contro: " + "; ".join(
            c["reading"] for c in counters[:4])
    rec = {"ts": str(ts), "survives": bool(survives),
           "counters": counters, "class": gate.get("class"), "argument": argument}
    rc = red_council(state)
    rc.setdefault("challenges", []).append(rec)
    del rc["challenges"][:-400]
    return {"survives": bool(survives), "argument": argument, "counters": counters,
            "reading": ("il Consiglio Rosso: il caso sopravvive (nessuna crepa "
                        "misurata)" if survives
                        else "il Consiglio Rosso: " + argument)}


def weekly_self_negation(state: dict, *, week: str = "", ts: str = "",
                         live_edge: float | None = None,
                         top_strategies: list | None = None) -> dict:
    """The Dragon's weekly ANTI-REPORT -- the case that everything believed is wrong.

    Then the system SEEKS evidence: the anti-strategies to test, the regime anomalies
    to probe, the check that the live edge is not shrinking. Honest: an unmeasured
    live edge is named as unknown (the shrinkage is not invented).
    """
    claims = [
        "le migliori strategie potrebbero essere overfit",
        "il modello di regime potrebbe vedere schemi nel rumore",
        "il vantaggio potrebbe gia' stare decadendo",
    ]
    evidence_to_seek = [
        {"probe": "anti-strategie", "what": "testare l'OPPOSTO di cio' che funziona"},
        {"probe": "anomalie di regime", "what": "cercare regimi che rompono il modello"},
        {"probe": "erosione del vantaggio", "what": "misurare se l'edge dal vivo si "
                                                    "restringe"},
    ]
    shrinking = None
    if isinstance(live_edge, (int, float)):
        shrinking = bool(live_edge <= 0.0)
    rec = {"ts": str(ts), "week": str(week), "claims": claims,
           "seek": evidence_to_seek, "top_strategies": list(top_strategies or [])[:5],
           "live_edge": (float(live_edge) if isinstance(live_edge, (int, float))
                         else None),
           "shrinking": shrinking}
    rc = red_council(state)
    rc.setdefault("anti_reports", []).append(rec)
    del rc["anti_reports"][:-100]
    return {**rec,
            "reading": ("anti-rapporto: 3 accuse al sistema; prove da cercare "
                        + ("-- l'edge dal vivo si sta restringendo"
                           if shrinking else "(-- l'edge dal vivo non misurato"
                           if shrinking is None else "(-- l'edge dal vivo regge"))}


def cassandra_reward(state: dict, *, right_against_majority: bool, ts: str = "") -> dict:
    """Reward the Red Council when it was RIGHT while the majority was wrong."""
    rc = red_council(state)
    cas = rc.setdefault("cassandra", {"hits": 0, "n": 0})
    cas["n"] = int(cas.get("n") or 0) + 1
    if right_against_majority:
        cas["hits"] = int(cas.get("hits") or 0) + 1
    rate = round(cas["hits"] / cas["n"], 4) if cas["n"] else None
    return {"hits": cas["hits"], "n": cas["n"], "rate": rate,
            "reading": (f"Cassandra: {cas['hits']}/{cas['n']} volte giusto contro la "
                        f"maggioranza" if right_against_majority else
                        "Cassandra: la maggioranza aveva ragione stavolta")}


def red_council_block(state: dict) -> dict:
    """The Red Council's block for the artifact + the Letter."""
    rc = red_council(state)
    cas = rc.get("cassandra") or {"hits": 0, "n": 0}
    last = (rc.get("challenges") or [None])[-1]
    anti = (rc.get("anti_reports") or [None])[-1]
    rate = (round(cas["hits"] / cas["n"], 4) if cas.get("n") else None)
    return {
        "version": RED_COUNCIL_VERSION,
        "challenges": len(rc.get("challenges") or []),
        "anti_reports": len(rc.get("anti_reports") or []),
        "cassandra": {"hits": cas.get("hits", 0), "n": cas.get("n", 0), "rate": rate},
        "last_challenge": last,
        "last_anti_report": anti,
        "measured": bool(last or anti or cas.get("n")),
        "reading": (f"Consiglio Rosso: {len(rc.get('challenges') or [])} attacchi, "
                    f"{len(rc.get('anti_reports') or [])} anti-rapporti, Cassandra "
                    f"{cas.get('hits', 0)}/{cas.get('n', 0)}"),
    }
