"""THE TRADE TICKET -- the complete signal with its full WHY (THE REAL HUNT,
Part Six).

When the Cathedral fires a CLASS A signal the CEO receives a COMPLETE NARRATIVE: not
just WHAT to trade, but WHY -- which of the seven columns aligned (each with its
evidence), which hunter triggered, what the Dragon says, and what the Red Council
argued (and why it was overruled).

Honesty is binding: a ticket is built ONLY from a real CLASS A gate; the WHY cites the
MEASURED evidence of each column; an unmeasured confidence is ``None`` (never an
invented probability); the Red Council's argument is included verbatim. Pure at import
(Scar #6): the caller supplies the gate, the columns, the hunter and the voices.
"""

from __future__ import annotations

__all__ = [
    "TICKET_VERSION",
    "build_ticket",
    "ticket_lines",
    "tickets",
]

TICKET_VERSION: int = 1

# The RR floor (the Ten Laws: RR 2.5+ forever).
RR_FLOOR: float = 2.5


def tickets(state: dict) -> list[dict]:
    """The issued tickets (created empty on first access)."""
    st = state if state is not None else {}
    return st.setdefault("tickets", [])


def build_ticket(*, pair: str, direction: int, entry: float | None, sl: float | None,
                 tp: float | None, gate: dict, columns: list[dict],
                 hunter: dict | None = None, dragon: str = "",
                 red_council: dict | None = None, ts: str = "",
                 confidence: float | None = None) -> dict:
    """Build the complete trade ticket for a CLASS A signal (or honestly decline).

    Returns ``{ok, ticket}``. ``ok`` is False (with a reason) unless the gate is
    CLASS A and the RR is at or above the floor -- a ticket is never issued for a
    weaker setup. The WHY lists every confirmed column with its evidence.
    """
    g = gate or {}
    if g.get("class") != "A":
        return {"ok": False, "reason": "non e' un segnale di CLASSE A",
                "reading": "nessun ticket: la Cattedrale non ha parlato (7/7)"}
    rr = None
    if all(isinstance(x, (int, float)) for x in (entry, sl, tp)):
        risk = abs(float(entry) - float(sl))
        reward = abs(float(tp) - float(entry))
        rr = round(reward / risk, 3) if risk > 0 else None
    if rr is not None and rr < RR_FLOOR:
        return {"ok": False, "reason": f"RR {rr} sotto il pavimento {RR_FLOOR}",
                "reading": "nessun ticket: il rapporto rischio/rendimento e' sotto 2.5"}
    why = [{"column": c.get("column"), "evidence": c.get("detail")}
           for c in (columns or []) if c.get("confirmed") is True]
    ticket = {
        "ts": str(ts), "pair": str(pair),
        "direction": ("long" if int(direction) > 0 else "short"),
        "entry": entry, "sl": sl, "tp": tp, "rr": rr,
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
        "columns_aligned": [w["column"] for w in why],
        "why": why,
        "hunter": (hunter or {}).get("hunter") if hunter else None,
        "hunter_reading": (hunter or {}).get("reading") if hunter else None,
        "dragon": str(dragon or ""),
        "red_council": (red_council or {}).get("argument"),
        "red_council_survived": bool((red_council or {}).get("survives")),
    }
    return {"ok": True, "ticket": ticket,
            "reading": (f"TICKET {ticket['direction']} {pair}: "
                        f"7/7 colonne, RR {rr}, cacciatore {ticket['hunter']}")}


def ticket_lines(ticket: dict) -> list[str]:
    """The ticket as Letter lines (the complete narrative for the CEO)."""
    t = ticket or {}
    L: list[str] = []
    L.append(f"**TICKET DI CACCIA -- {t.get('pair')} {t.get('direction')}**")
    L.append(f"  - ingresso {t.get('entry')} | SL {t.get('sl')} | TP {t.get('tp')} "
             f"| RR {t.get('rr')} | confidenza {t.get('confidence')}")
    L.append(f"  - il PERCHE': {len(t.get('columns_aligned') or [])}/7 colonne "
             f"allineate -- {', '.join(t.get('columns_aligned') or [])}")
    for w in (t.get("why") or [])[:7]:
        L.append(f"    - {w.get('column')}: {w.get('evidence')}")
    if t.get("hunter"):
        L.append(f"  - cacciatore: {t.get('hunter')} -- {t.get('hunter_reading')}")
    if t.get("dragon"):
        L.append(f"  - il Drago: {t.get('dragon')}")
    if t.get("red_council"):
        L.append(f"  - il Consiglio Rosso ha attaccato: {t.get('red_council')} "
                 f"({'il caso ha resistito' if t.get('red_council_survived') else 'non resistito'})")
    return L
