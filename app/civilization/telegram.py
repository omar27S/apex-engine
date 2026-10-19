"""THE CEO'S VOICE — Section D of MEGA PHASE 4 (the Telegram command router).

The civilization speaks once a day (the Letter). This module makes it RESPONSIVE:
the CEO sends a command and the system answers in plain Italian from the artifacts it
already publishes. The router is PURE -- it reads an artifacts dict and returns the
reply text; the CLI (:mod:`tools.telegram_router`) does the I/O and may ask the Dragon
to phrase the reply in its own voice.

Commands:
  /status      -- the system's current state (the tube + the heartbeat)
  /caccia      -- today's hunting report (the tournament + the signals)
  /rischio     -- the portfolio risk profile (stress test + drawdown)
  /performance -- the week's numbers (the Letter history)
  /aiuto       -- what the system needs from the CEO (open items)
  /para        -- the Parachute's levels (the LAW 4 stop management)
  /deepseek-pro -- summon the Pro Sage for ONE extraordinary consultation (the
                   budget doctrine: Pro is the exception, never the default)

Honesty: an unknown command names the known ones; a missing artifact yields an
explicit "non misurato", never an invented number.

Pure at import (Scar #6): the readings are data; the functions reduce. No I/O.
"""

from __future__ import annotations

__all__ = [
    "COMMANDS",
    "PRO_COMMAND",
    "parse_command",
    "route",
    "help_text",
]

# THE ONE PRO SESSION (the CEO's order): /deepseek-pro summons the expensive Pro head
# for a single extraordinary consultation. Every other command stays on Flash.
PRO_COMMAND: str = "/deepseek-pro"

# command -> (one-line description for /aiuto)
COMMANDS: dict[str, str] = {
    "/status": "lo stato attuale del sistema (il tubo + il battito)",
    "/caccia": "il rapporto di caccia di oggi (torneo + segnali)",
    "/rischio": "il profilo di rischio del portafoglio (stress test + drawdown)",
    "/performance": "i numeri della settimana (la storia delle Lettere)",
    "/aiuto": "cio' di cui il sistema ha bisogno dal CEO",
    "/para": "i livelli del Paracadute (la legge 4)",
    PRO_COMMAND: "una consultazione straordinaria col Saggio Pro (una sola)",
}


def help_text() -> str:
    lines = ["Comandi disponibili:"]
    for cmd, desc in COMMANDS.items():
        lines.append(f"  {cmd} -- {desc}")
    return "\n".join(lines)


def parse_command(text: str) -> dict | None:
    """Parse a Telegram message into ``{command, args}`` or None (not a command).

    Tolerates the ``@botname`` suffix Telegram appends in groups and a leading slash.
    """
    if not text:
        return None
    raw = str(text).strip()
    if not raw.startswith("/"):
        return None
    parts = raw.split()
    cmd = parts[0].split("@", 1)[0].lower()
    return {"command": cmd, "args": parts[1:]}


def _num(v, unit: str = "") -> str:
    if v is None:
        return "non misurato"
    return f"{v}{unit}"


def _status(art: dict) -> str:
    tube = art.get("apex_state") or {}
    a = tube.get("artifact") or tube.get("pipe", {}).get("artifact") or tube
    hb = tube.get("heartbeat") or tube.get("pipe", {}).get("heartbeat") or {}
    L = ["STATO DEL SISTEMA",
         f"  ore macchina: {_num(a.get('machine_hours'))}",
         f"  coda: {_num(a.get('queue_depth'))}",
         f"  tornei oggi: {_num(a.get('tournaments_today'))}",
         f"  sopravvissuti: {_num(a.get('survivors_today'))}"]
    if hb.get("reading"):
        L.append(f"  battito: {hb['reading']}")
    elif hb.get("done") is not None:
        L.append(f"  battito: {hb.get('done')} job, ultimo {hb.get('ts')}")
    return "\n".join(L)


def _caccia(art: dict) -> str:
    rep = art.get("report") or {}
    sg = rep.get("signal_generation") or art.get("civ", {}).get("signal_generation") or {}
    lb = rep.get("leaderboard") or []
    L = ["RAPPORTO DI CACCIA",
         f"  generazioni: {_num(rep.get('generations'))}",
         f"  popolazione finale: {_num(rep.get('population'))}",
         f"  candidati segnale: {_num(sg.get('n_candidates'))} "
         f"(accettati {_num(sg.get('n_accepted'))})",
         f"  strategie in classifica: {len(lb)}"]
    if lb:
        top = lb[0]
        L.append(f"  migliore: {top.get('family')} "
                 f"({_num(top.get('adv_net_r', top.get('net_r')), 'R')}, "
                 f"win rate {_num(top.get('adv_win_rate', top.get('win_rate')))})")
    return "\n".join(L)


def _rischio(art: dict) -> str:
    civ = art.get("civ") or {}
    st = civ.get("stress_test") or {}
    ledger = st.get("ledger") or {}
    L = ["PROFILO DI RISCHIO"]
    obs = ledger.get("observed") or {}
    if obs:
        L.append(f"  danno osservato: {_num(obs.get('portfolio_damage_pct'), '%')}")
        L.append(f"  peggior strategia: {obs.get('worst_strategy')} "
                 f"({_num(obs.get('worst_r'), 'R')})")
    else:
        L.append("  danno osservato: non misurato")
    scen = ledger.get("scenarios") or []
    for s in scen[:3]:
        L.append(f"  {s.get('kind')}: {s.get('reading')}")
    return "\n".join(L)


def _performance(art: dict) -> str:
    hist = art.get("letter_history") or {}
    nights = hist.get("nights") or []
    if not nights:
        return "PERFORMANCE\n  storia non misurata (nessuna Lettera registrata)"
    L = ["PERFORMANCE (ultime notti)"]
    for n in nights[-5:]:
        m = n.get("metrics") or {}
        L.append(f"  {n.get('date')}: win rate migliore {_num(m.get('wr_best'))}, "
                 f"portafoglio {_num(m.get('wr_portfolio'))}, "
                 f"expectancy {_num(m.get('expectancy_r'), 'R')}, "
                 f"DD {_num(m.get('dd_r'), 'R')}")
    return "\n".join(L)


def _aiuto(art: dict) -> str:
    """What the system needs from the CEO: the open items + the standing asks."""
    L = ["DI COSA HO BISOGNO DAL CEO",
         "  (le voci aperte non risolvibili nella sandbox)"]
    items = art.get("open_items") or []
    if items:
        for it in items[:8]:
            L.append(f"  - {it}")
    else:
        L.append("  - nessuna voce aperta registrata")
    L.append("  Per rispondere: apri una Lettera, o invia un comando qui.")
    return "\n".join(L)


def _para(art: dict) -> str:
    """The Parachute's levels (LAW 4) for the day's candidate, if measurable."""
    law = art.get("parachute") or {}
    if law.get("levels"):
        L = ["PARACADUTE (legge 4)"]
        for lv in law["levels"]:
            L.append(f"  {lv.get('pair')}: innesco {lv.get('trigger')}, "
                     f"stop bloccato a {lv.get('lock')}")
        return "\n".join(L)
    return ("PARACADUTE (legge 4)\n"
            "  nessun livello calcolabile: serve un candidato con ingresso e rischio\n"
            "  regola: al tocco di +2.5R lo stop si blocca a +0.5R, per sempre")


def _deepseek_pro(art: dict) -> str:
    """The preamble for /deepseek-pro; the CLI summons the Pro head for the answer.

    The router is PURE (no model call), so this returns the request; the CLI replaces
    the reply with the Pro head's word (honest: no key -> the CLI says so).
    """
    return ("CONSULTAZIONE STRAORDINARIA (Saggio Pro)\n"
            "  il CEO ha chiesto una sessione Pro: il Saggio risponde con la testa "
            "piu' profonda.\n"
            "  (una sola: la dottrina di budget tiene il Pro come eccezione)")


_ROUTES = {
    "/status": _status, "/caccia": _caccia, "/rischio": _rischio,
    "/performance": _performance, "/aiuto": _aiuto, "/para": _para,
    PRO_COMMAND: _deepseek_pro,
}


def route(parsed: dict, *, artifacts: dict) -> dict:
    """Route a parsed command to a plain-Italian reply (never raises, never invents).

    Returns ``{command, reply, known, needs_model, pro, model_prompt}``. ``needs_model``
    is True when a Dragon voice would improve the reply (the CLI may call it); the plain
    reply is ALWAYS present so /status works with no key. ``pro`` is True ONLY for
    ``/deepseek-pro``: the CLI then summons the expensive Pro head for that ONE
    consultation (the CEO's /deepseek-pro).
    """
    cmd = (parsed or {}).get("command")
    if cmd not in _ROUTES:
        return {"command": cmd, "known": False, "needs_model": False, "pro": False,
                "reply": f"Comando sconosciuto: {cmd}\n\n{help_text()}",
                "model_prompt": ""}
    reply = _ROUTES[cmd](artifacts or {})
    pro = cmd == PRO_COMMAND
    return {"command": cmd, "known": True, "needs_model": cmd != "/aiuto",
            "pro": pro, "reply": reply,
            "model_prompt": ("Riscrivi in italiano, voce del Drago di APEX, diretto e "
                             f"breve, questa risposta al CEO:\n{reply}")}
