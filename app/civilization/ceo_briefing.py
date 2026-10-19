"""THE CEO'S BRIEFING — Section D of MEGA PHASE 4 (the weekly personal letter).

Every Monday the Dragon writes a briefing for the CEO alone: the week's numbers, the
three things that matter, the one decision that would benefit most from the CEO's
input, and an honest self-assessment. This module builds the STRUCTURE from the
published artifacts (numbers that are real); the Dragon supplies the prose. Honest:
with no history the numbers read "non misurato", never invented.

Pure at import (Scar #6): the readings are data; the functions reduce. No I/O.
"""

from __future__ import annotations

__all__ = ["weekly_summary", "top_three", "decision_needing_ceo", "self_assessment",
           "briefing", "briefing_prompt"]


def _nights(history: dict | None) -> list[dict]:
    return [n for n in ((history or {}).get("nights") or []) if isinstance(n, dict)]


def weekly_summary(history: dict | None, *, n: int = 7) -> dict:
    """The week's numbers from the Letter history (honest averages over what exists)."""
    nights = _nights(history)[-n:]
    if not nights:
        return {"n": 0, "reading": "settimana non misurata"}
    wrs = [m for m in (_metric(x, "wr_best") for x in nights) if m is not None]
    exps = [m for m in (_metric(x, "expectancy_r") for x in nights) if m is not None]
    dds = [m for m in (_metric(x, "dd_r") for x in nights) if m is not None]
    def _avg(v):
        return round(sum(v) / len(v), 4) if v else None
    return {"n": len(nights), "wr_best_avg": _avg(wrs), "expectancy_avg": _avg(exps),
            "dd_avg": _avg(dds),
            "reading": (f"{len(nights)} notti; win rate {_avg(wrs)}, "
                        f"expectancy {_avg(exps)}R, DD {_avg(dds)}R")}


def _metric(night: dict, key: str):
    m = night.get("metrics") or {}
    return m.get(key)


def top_three(*, report: dict | None, civilization: dict | None,
              meta: dict | None = None) -> list[str]:
    """The three most important things the CEO should know (from real signals)."""
    out: list[str] = []
    rep = report or {}
    civ = civilization or {}
    # 1. the best strategy's standing.
    lb = rep.get("leaderboard") or []
    if lb:
        top = lb[0]
        out.append(f"la migliore strategia ({top.get('family')}) e' a "
                   f"{top.get('adv_net_r', top.get('net_r'))}R")
    # 2. the survivor count (the army's size).
    if rep.get("population") is not None:
        out.append(f"la popolazione e' {rep.get('population')}; "
                   f"{len(rep.get('final_population') or [])} in classifica")
    # 3. the learning trajectory (meta).
    if meta and meta.get("efficiency"):
        out.append(f"apprendimento: {meta['efficiency'].get('reading')}")
    elif civ.get("generativity", {}).get("reading"):
        out.append(f"generativita': {civ['generativity']['reading']}")
    return out[:3] or ["nessun dato misurato questa settimana"]


def decision_needing_ceo(*, civilization: dict | None, report: dict | None) -> dict:
    """The ONE decision that would benefit most from CEO input (honest pick).

    Prefers an explicit CEO request (the system's own standing asks); otherwise the
    ticket gate / the top candidate that the Cathedral refused.
    """
    civ = civilization or {}
    for d in (civ.get("decisions") or []):
        if isinstance(d, dict) and d.get("source") == "ceo":
            return {"what": d.get("what"), "why": d.get("why"),
                    "reading": f"in attesa del CEO: {d.get('what')}"}
    ticket = civ.get("ticket") or {}
    if ticket.get("reason"):
        return {"what": "sbloccare il biglietto (gate non A)", "why": ticket.get("reason"),
                "reading": f"il biglietto non e' passato: {ticket.get('reason')}"}
    return {"what": None, "why": None,
            "reading": "nessuna decisione urgente: il sistema procede da solo"}


def self_assessment(*, meta: dict | None, civilization: dict | None) -> str:
    """The system's honest self-assessment: are we improving, and where are we stuck?"""
    eff = (meta or {}).get("efficiency") or {}
    if eff.get("measured"):
        accel = eff.get("acceleration")
        if accel is None:
            return f"sto imparando ({eff.get('reading')}), ma non ho ancora una tendenza"
        if accel > 0:
            return f"sto accelerando: {eff.get('reading')} (accelerazione {accel:+.0%})"
        return f"sto rallentando: {eff.get('reading')} (accelerazione {accel:+.0%})"
    return "non misurato: servono piu' notti per giudicare il mio apprendimento"


def briefing(*, history: dict | None, report: dict | None, civilization: dict | None,
             meta: dict | None, ts: str = "", dragon_prose: str | None = None) -> dict:
    """Assemble the weekly briefing (structure + optional Dragon prose)."""
    summary = weekly_summary(history)
    three = top_three(report=report, civilization=civilization, meta=meta)
    decision = decision_needing_ceo(civilization=civilization, report=report)
    assess = self_assessment(meta=meta, civilization=civilization)
    b = {"ts": ts, "week_summary": summary, "top_three": three,
         "decision": decision, "self_assessment": assess,
         "dragon_prose": dragon_prose}
    b["reading"] = (f"briefing: {summary['reading']}; "
                    f"decisione: {decision['reading']}")
    return b


def briefing_prompt(b: dict) -> str:
    """The prompt the Dragon answers to write the briefing in its own voice."""
    return (
        "Sei il Drago di APEX. Scrivi il BRIEFING SETTIMANALE per il CEO, in italiano, "
        "personale, onesto, diretto. Usa SOLO questi numeri misurati; se un numero "
        "manca, dillo. Struttura: i numeri della settimana; le 3 cose piu' importanti; "
        "la 1 decisione che serve dal CEO; la tua autovalutazione onesta.\n"
        f"NUMERI: {b.get('week_summary')}\n"
        f"TRE COSE: {b.get('top_three')}\n"
        f"DECISIONE: {b.get('decision')}\n"
        f"AUTOVALUTAZIONE: {b.get('self_assessment')}\n")
