"""THE DECISION ASSISTANT — Section D of MEGA PHASE 4 (the CEO's decision brief).

When the CEO faces a choice (enter manually, adjust a parameter, approve a strategic
change), the system assembles a DECISION BRIEF: the arguments FOR with their
evidence, the arguments AGAINST (the Red Council's position), the historical
outcomes of similar decisions, and the Dragon's recommendation -- so the CEO decides
with maximum information. The CEO still decides.

Honest: an argument is listed only when its evidence exists; the recommendation is
None when no measured basis exists (never a coin-flip dressed as advice).

Pure at import (Scar #6): the readings are data; the functions reduce. No I/O.
"""

from __future__ import annotations

__all__ = ["arguments_for", "arguments_against", "historical_outcomes",
           "recommendation", "decision_brief", "decision_prompt"]


def arguments_for(*, option: str, evidence: dict | None) -> list[dict]:
    """The case FOR the option, each argument tied to its evidence."""
    ev = evidence or {}
    out: list[dict] = []
    if ev.get("expectancy_r") is not None and float(ev["expectancy_r"]) > 0:
        out.append({"argument": "expectancy positiva", "evidence": ev["expectancy_r"]})
    if ev.get("net_r") is not None and float(ev["net_r"]) > 0:
        out.append({"argument": "rendimento netto positivo", "evidence": ev["net_r"]})
    if ev.get("win_rate") is not None and float(ev["win_rate"]) >= 0.5:
        out.append({"argument": "win rate sopra il 50%", "evidence": ev["win_rate"]})
    if ev.get("regime") == "trending" and ev.get("family"):
        out.append({"argument": "il regime e' allineato alla famiglia",
                    "evidence": f"{ev['family']} in {ev['regime']}"})
    return out


def arguments_against(*, option: str, evidence: dict | None,
                      red_council: dict | None) -> list[dict]:
    """The case AGAINST: the Red Council's challenge + the measured weak points."""
    ev = evidence or {}
    rc = red_council or {}
    out: list[dict] = []
    if rc.get("last_challenge", {}).get("argument"):
        out.append({"argument": "Consiglio Rosso", "evidence":
                    rc["last_challenge"]["argument"]})
    if ev.get("dd_r") is not None and float(ev["dd_r"]) > 10:
        out.append({"argument": "drawdown elevato", "evidence": ev["dd_r"]})
    if ev.get("friction_gap") is not None and float(ev["friction_gap"]) < 0:
        out.append({"argument": "il costo supera il rendimento lordo",
                    "evidence": ev["friction_gap"]})
    if not out:
        out.append({"argument": "nessun argomento contrario misurato",
                    "evidence": None})
    return out


def historical_outcomes(*, history: dict | None, option: str = "") -> dict:
    """The historical outcomes of similar decisions (honest: the Letter history)."""
    nights = [n for n in ((history or {}).get("nights") or []) if isinstance(n, dict)]
    if not nights:
        return {"n": 0, "reading": "storico non misurato"}
    vals = []
    for n in nights[-7:]:
        v = (n.get("metrics") or {}).get("expectancy_r")
        if v is not None:
            vals.append(float(v))
    if not vals:
        return {"n": len(nights), "reading": "storico senza expectancy misurata"}
    avg = sum(vals) / len(vals)
    pos = sum(1 for v in vals if v > 0)
    return {"n": len(vals), "avg_expectancy": round(avg, 4), "positive": pos,
            "reading": (f"{pos}/{len(vals)} notti positive, expectancy media "
                        f"{avg:+.3f}R")}


def recommendation(*, for_args: list[dict], against_args: list[dict],
                   historical: dict) -> dict:
    """The Dragon's recommendation with its reasoning (honest: may be 'wait')."""
    f = len([a for a in for_args if a.get("evidence") is not None])
    a = len([a for a in against_args if a.get("evidence") is not None])
    if f == 0 and a == 0:
        return {"call": "attendere", "reason": "nessuna prova misurata: non decide il caso"}
    if f > a:
        return {"call": "procedere", "reason": f"{f} prove a favore vs {a} contro"}
    if a > f:
        return {"call": "astenersi", "reason": f"{a} prove contro vs {f} a favore"}
    return {"call": "attendere", "reason": "prove in equilibrio: il CEO decide"}


def decision_brief(*, option: str, evidence: dict | None,
                   red_council: dict | None, history: dict | None,
                   ts: str = "") -> dict:
    """Assemble the full decision brief (the CEO still decides)."""
    fa = arguments_for(option=option, evidence=evidence)
    aa = arguments_against(option=option, evidence=evidence, red_council=red_council)
    ho = historical_outcomes(history=history, option=option)
    rec = recommendation(for_args=fa, against_args=aa, historical=ho)
    return {"ts": ts, "option": option, "for": fa, "against": aa,
            "historical": ho, "recommendation": rec,
            "reading": f"{option}: {rec['call']} ({rec['reason']})"}


def decision_prompt(b: dict) -> str:
    return (
        "Sei il Drago di APEX. Il CEO deve decidere. Scrivi il BRIEFING DI DECISIONE "
        "in italiano, onesto e diretto: gli argomenti a favore (con prove), i "
        "contrari (il Consiglio Rosso), lo storico, e la tua raccomandazione con la "
        "ragione. Non inventare prove; il CEO decide.\n"
        f"OPZIONE: {b.get('option')}\nA FAVORE: {b.get('for')}\n"
        f"CONTRO: {b.get('against')}\nSTORICO: {b.get('historical')}\n")
