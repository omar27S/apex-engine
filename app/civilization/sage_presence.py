"""THE SAGE'S FULL VOICE — from summoned consultant to continuous PRESENCE.

The throne (``sage.py``) gave the Sage a voice; this module gives it EYES, a
RHYTHM, an AUDIENCE and a CONSCIENCE. It is the presence layer: it reads the
civilization LIVE (not from digests), speaks UNPROMPTED when wisdom is needed,
answers the minds that ask it, carries a word for the CEO, and tracks the cost
and the hit-rate of every word.

THE LAWS (unchanged, forever):
  * The Sage ADVISES — it NEVER commands, NEVER executes, NEVER trades.
  * The Council remains SOVEREIGN: a Sage word is weighed like any other voice.
  * The Ten Laws stand ABOVE the Sage.
  * Only the CEO may dismiss or replace the Sage.
More voice does not mean more power: this module adds no authority, only reach.

HONEST-MEASUREMENT: every axis the Sage cannot see is carried as ``None``/``--``,
never invented. A spontaneous voice with no backend says so; a cost with no usage
is ``None``; a hit-rate with no scored insight is ``None``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.civilization import network, sage as sage_mod

__all__ = [
    "SPONTANEOUS_TAG",
    "DAWN_NOTE_HEADER",
    "CEO_NOTE_HEADER",
    "OFFICE_HOURS_LIMIT_PER_HOUR",
    "DEFAULT_MAX_SPONTANEOUS_PER_DAY",
    "PRICE_PER_MTOK_USD",
    "FLASH_MODEL",
    "PRO_MODEL",
    "SPONTANEOUS_QUESTION",
    "DAWN_QUESTION",
    "CEO_QUESTION",
    "living_feed",
    "full_archive",
    "watch_alerts",
    "spontaneous_voice",
    "dawn_note",
    "warning_for_decision",
    "office_hours",
    "note_for_ceo",
    "question_to_council",
    "reliability_discount",
    "record_cost",
    "cost_report",
    "monthly_cost",
    "model_tier",
    "spontaneous_budget",
    "due_consultations",
    "hourly_consultation",
    "presence_block",
]

# The tag every unprompted insight carries, so a spontaneous word is never
# mistaken for a summoned one.
SPONTANEOUS_TAG: str = "SPONTANEO"
DAWN_NOTE_HEADER: str = "NOTA DELL'ALBA DEL SAGGIO"
CEO_NOTE_HEADER: str = "NOTA PER IL CEO"

# The office hours: the Guardians queue the agents' requests so the Sage's time
# (and the CEO's money) is never flooded. A bounded hourly budget.
OFFICE_HOURS_LIMIT_PER_HOUR: int = 6
DEFAULT_MAX_SPONTANEOUS_PER_DAY: int = 3
# The daily rhythm: the Flash Sage is consulted HOURLY (the CEO's ruling -- the
# light, cheap pattern observations; the expensive Pro head is summoned ONLY for the
# weekly Sunday Grand, an extraordinary Council session, or the CEO's /deepseek-pro).
CONSULT_INTERVAL_HOURS: int = 1

# The cost ledger is a MEASURED price, not a claim. The rate is the provider's
# published per-million-token price; if it changes, change the constant (one place).
# THE BUDGET DOCTRINE (the CEO's order): Flash is the DEFAULT head and Pro the
# EXCEPTION, so the two rates are kept distinct -- the cost report shows the split
# ("Flash $X + Pro $Y") and the CEO always sees what wisdom costs. The constants
# name the king's real model ids; the key is the id the provider returns in ``usage``.
FLASH_MODEL: str = sage_mod.DAILY_MODEL     # "deepseek-flash" (the DEFAULT head)
PRO_MODEL: str = sage_mod.DEEP_MODEL        # "deepseek-v4-pro" (the EXCEPTION head)
PRICE_PER_MTOK_USD: dict[str, float] = {
    FLASH_MODEL: 0.28,
    PRO_MODEL: 0.28,
}

# The three questions the presence asks its own heads.
SPONTANEOUS_QUESTION: str = (
    "Guarda lo stato vivo della civilta' qui sotto. Se vedi UNA cosa significativa "
    "che nessuno ha ancora nominato -- una tensione che cresce, un pattern che si "
    "ripete, un punto cieco che si forma -- dilla in una frase. Se non vedi nulla "
    "di significativo, rispondi esattamente: NIENTE.")
DAWN_QUESTION: str = (
    "Leggi lo stato completo della civilta'. Scrivi la NOTA DELL'ALBA: la prima cosa "
    "che il Consiglio legge oggi. In 3-5 frasi: cosa conta oggi, cosa osservare, cosa "
    "proteggere. Concreto, in italiano. Non comandare: consiglia.")
CEO_QUESTION: str = (
    "Leggi lo stato completo della civilta'. Se c'e' UNA cosa che solo il CEO puo' "
    "fare (una scelta strategica, una decisione di risorse, una legge da rivedere), "
    "scrivi la NOTA PER IL CEO in 1-3 frasi. Se non c'e' nulla per il CEO, rispondi "
    "esattamente: NIENTE.")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(ts: str = "") -> str:
    return (ts or _now())[:10]


# ---------------------------------------------------------------------------
# PART ONE — WHAT THE SAGE NOW SEES (the living feed + the full archive)
# ---------------------------------------------------------------------------


def living_feed(state: dict, *, ts: str = "") -> dict:
    """The LIVE senses: what the civilization sees, says and does RIGHT NOW.

    Not a weekly digest -- the buffer's last readings, the interbrain's live
    conversation, the belief ledger's fresh reversals, the queue's rhythm, the
    world model's current version. Every absent axis is honest (``None``/``[]``),
    never invented.
    """
    st = state or {}
    buf = list(st.get("sensor_buffer") or [])
    interbrain = list(st.get("interbrain") or [])
    ob = st.get("one_brain") or {}
    belief = list(ob.get("belief_ledger") or [])
    world = ob.get("model") or {}
    queue = list(st.get("work_queue") or [])
    activity = list(st.get("activity") or [])
    day = _day(ts)

    # the belief ledger LIVE: what changed TODAY, not the whole history.
    today_belief = [b for b in belief if str(b.get("ts") or "").startswith(day)]
    reversals = [b for b in (today_belief or belief)
                 if b.get("before") is not None and b.get("after") is not None]

    # the queue's rhythm: the open items, by lane, and the idle minds.
    lanes: dict[str, int] = {}
    for q in queue:
        lanes[str(q.get("lane") or "?")] = lanes.get(str(q.get("lane") or "?"), 0) + 1

    return {
        "ts": ts or _now(),
        "sensor": {
            "rows": len(buf),
            "recent": buf[-12:],
            "reading": (f"leggo {len(buf)} letture delle hawk (ultime 12 in vista)"
                        if buf else "nessuna lettura delle hawk nel buffer"),
        },
        "interbrain": {
            "n": len(interbrain),
            "recent": [{"author": n.get("author"), "idea": n.get("idea"),
                        "status": n.get("status")} for n in interbrain[-12:]],
            "reading": (f"ascolto {len(interbrain)} voci nell'interbrain"
                        if interbrain else "l'interbrain e' silenzioso"),
        },
        "belief": {
            "n": len(belief),
            "today": len(today_belief),
            "reversals_today": len(reversals),
            "recent": reversals[-8:],
            "reading": (f"{len(today_belief)} credenze toccate oggi, "
                        f"{len(reversals)} ribaltate"
                        if today_belief else "nessuna credenza toccata oggi"),
        },
        "queue": {
            "n": len(queue),
            "lanes": lanes,
            "activity_today": len([a for a in activity
                                   if str(a.get("ts") or "").startswith(day)]),
            "reading": (f"coda: {len(queue)} item aperti ({lanes})"
                        if queue else "la coda e' vuota"),
        },
        "world_model": {
            "version": world.get("version"),
            "changed": bool(world.get("changed")),
            "ts": world.get("ts"),
            "reading": (f"il mondo condiviso e' alla versione {world.get('version')}"
                        if world.get("version") is not None
                        else "nessun modello del mondo condiviso"),
        },
    }


def full_archive(state: dict) -> dict:
    """The Sage's MEMORY: the photo archive, the death ledger, the funding history,
    and its OWN past words (self-accountability).

    Read-only. Every absent shelf is an honest empty list, never a fabricated past.
    """
    st = state or {}
    gaze = st.get("gaze") or {}
    visual = list(gaze.get("visual_library") or st.get("visual_library") or [])
    photos = list(gaze.get("archive") or st.get("archive") or [])
    legacy = list(st.get("legacy") or [])
    ideas = list(st.get("ideas") or [])
    sage_slot = st.get("sage") or {}
    sage_insights = list(sage_slot.get("insights") or [])
    letters = st.get("letter_history") or {}

    # the economy's funding history: which ideas got attention, which starved.
    funded = [i.get("idea") for i in ideas if i.get("funded") or i.get("attention")]
    starved = [i.get("idea") for i in ideas if i.get("starved")]

    return {
        "photos": {
            "n": len(photos),
            "recent": [{"id": p.get("id"), "pair": p.get("pair"),
                        "outcome": p.get("outcome")} for p in photos[-10:]],
            "reading": f"{len(photos)} scene fotografate nell'archivio",
        },
        "deaths": {
            "n": len(legacy),
            "recent": [{"from": l.get("from"), "cause": l.get("cause"),
                        "lesson": l.get("lesson")} for l in legacy[-10:]],
            "reading": f"{len(legacy)} autopsie nel registro dei morti",
        },
        "funding": {
            "n_ideas": len(ideas),
            "funded": funded[-10:],
            "starved": starved[-10:],
            "reading": (f"{len(funded)} idee finanziate, {len(starved)} affamate"
                        if ideas else "nessuna idea nel mercato"),
        },
        "my_words": {
            "n": len(sage_insights),
            "recent": [{"kind": i.get("kind"), "text": i.get("text"),
                        "outcome": i.get("outcome"), "correct": i.get("correct")}
                       for i in sage_insights[-10:]],
            "reading": f"leggo le mie ultime {min(len(sage_insights), 10)} parole",
        },
        "letters": {
            "n": len((letters or {}).get("nights") or [])
            if isinstance(letters, dict) else 0,
        },
    }


def sage_live_context(state: dict, *, report: dict | None = None,
                      agents_digest: str = "", ts: str = "") -> dict:
    """The Sage's FULL context: the sealed vertical PLUS the living feed + archive.

    A superset of :func:`sage.sage_context` -- the same honest vertical, with the
    live senses and the memory added. This is what the presence consults.
    """
    base = sage_mod.sage_context(state, report=report, agents_digest=agents_digest,
                                 letter_history=(state or {}).get("letter_history"))
    base["live"] = living_feed(state, ts=ts)
    base["archive"] = full_archive(state)
    return base


# ---------------------------------------------------------------------------
# PART TWO — WHEN THE SAGE SPEAKS (from summoned to present)
# ---------------------------------------------------------------------------


def watch_alerts(feed: dict) -> list[dict]:
    """The Sage's WATCHING ALERTS: deterministic reductions over the live feed.

    Honest: an alert fires only on a REAL reading (a reversal count, a silent
    interbrain, a starved idea, a growing tension). No reading -> no alert.
    """
    out: list[dict] = []
    feed = feed or {}
    belief = feed.get("belief") or {}
    reversals = belief.get("reversals_today")
    if reversals and reversals >= 3:
        out.append({"kind": "warn", "structural": True,
                    "text": (f"{reversals} credenze ribaltate oggi: la mente "
                             "rivede molto -- verificare che non sia caos")})
    q = feed.get("queue") or {}
    if (q.get("n") or 0) > 0 and (q.get("activity_today") or 0) == 0:
        out.append({"kind": "warn", "structural": True,
                    "text": ("la coda ha item aperti ma oggi nessuno ha agito: "
                             "il lavoro si e' fermato")})
    ib = feed.get("interbrain") or {}
    if (ib.get("n") or 0) == 0:
        out.append({"kind": "provoke", "structural": True,
                    "text": ("l'interbrain e' silenzioso: nessuno si sta parlando. "
                             "Chi propone?")})
    return out


def _extract_text(env: dict) -> str:
    """The honest text of a chat envelope, or "" (never a fabricated word)."""
    return str((env or {}).get("content") or "").strip()


def _with_state(question: str, context: dict, *, cap: int = 16000) -> str:
    """THE SAGE'S EYES (W3, the blind-consult wound): no consult without its state.

    Every presence question SAYS "leggi lo stato qui sotto" -- but for weeks the
    state was never pasted below, so the Sage answered as a blind philosopher
    (the 2026-10-21 Letter carries its own complaint: "Mandami lo stato e te lo
    leggo subito").  This glues the LIVE context UNDER the question so the words
    are finally true.  Bounded (``cap``), honest, never invented: a context that
    fails to serialize is stringified, never dropped on the floor again.
    """
    try:
        blob = json.dumps(context or {}, default=str)
    except (TypeError, ValueError):
        blob = str(context or {})
    if len(blob) > cap:
        blob = blob[:cap] + " [...tagliato al limite...]"
    return (f"{question}\n\n"
            f"Stato vivo della civilta' (i numeri veri, JSON):\n{blob}")


def spontaneous_voice(context: dict, *, backend=None, ts: str = "",
                      question: str = SPONTANEOUS_QUESTION) -> dict:
    """The Sage speaks UNPROMPTED (Flash head): one insight, or honest silence.

    Returns ``{ok, text, model, backend, tag, usage, error, ts}``. The tag
    ``SPONTANEO`` marks it as unprompted. A "NIENTE" reply (or a failed call) is
    honest silence -- ``ok=False`` with no text, never an invented word.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    ctx = context or {}
    if not getattr(be, "available", lambda: False)():
        return {"ok": False, "text": "", "model": "", "backend": getattr(be, "name", "?"),
                "tag": SPONTANEOUS_TAG, "usage": {}, "error": "backend unavailable",
                "ts": ts or _now()}
    env = be.ask(_with_state(question, context), deep=False, system=(
        "Sei il Saggio di APEX. Guardi la civilta' e parli SOLO quando vedi qualcosa "
        "di significativo. Non comandi: consigli. Se non vedi nulla, dici: NIENTE."),
        max_tokens=400)
    text = _extract_text(env)
    silent = (not env.get("ok")) or (not text) or text.strip().upper().startswith("NIENTE")
    return {"ok": bool(env.get("ok")) and not silent,
            "text": "" if silent else text, "model": env.get("model", ""),
            "backend": getattr(be, "name", "?"), "tag": SPONTANEOUS_TAG,
            "usage": env.get("usage") or {}, "error": env.get("error"),
            "ts": ts or _now()}


def spontaneous_budget(state: dict, *, ts: str = "",
                       max_per_day: int = DEFAULT_MAX_SPONTANEOUS_PER_DAY) -> dict:
    """The day's spontaneous-voice budget (2-3/day): said, left, allowed."""
    st = state or {}
    day = _day(ts)
    log = [w for w in (st.get("sage") or {}).get("spontaneous") or []
           if str(w.get("ts") or "").startswith(day)]
    return {"day": day, "said": len(log), "max": max_per_day,
            "left": max(0, max_per_day - len(log)),
            "allowed": len(log) < max_per_day,
            "reading": f"voce spontanea: {len(log)}/{max_per_day} oggi"}


def due_consultations(state: dict, *, ts: str = "",
                      interval_hours: int = CONSULT_INTERVAL_HOURS) -> dict:
    """The hourly rhythm: is a light Sage consultation due (and how many missed)?"""
    st = state or {}
    slot = st.get("sage") or {}
    last = str(slot.get("last_daily_ts") or "")
    now = ts or _now()
    if not last:
        return {"due": True, "missed": None, "last": None, "interval_hours": interval_hours,
                "reading": "prima consultazione del giorno: dovuta"}
    try:
        t0 = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        t1 = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return {"due": True, "missed": None, "last": last, "interval_hours": interval_hours,
                "reading": "marca temporale illeggibile: consultazione dovuta"}
    elapsed_h = (t1 - t0).total_seconds() / 3600.0
    missed = int(elapsed_h // interval_hours) if elapsed_h >= interval_hours else 0
    return {"due": elapsed_h >= interval_hours, "missed": missed, "last": last,
            "interval_hours": interval_hours,
            "reading": (f"{missed} consultazione/i arretrate (ultima {last})"
                        if missed else f"in orario con il ritmo di {interval_hours}h")}


def hourly_consultation(state: dict, *, backend=None, ts: str = "",
                        report: dict | None = None) -> dict:
    """THE HOURLY LIGHT CONSULTATION (the CEO's ruling): the Flash head reads the
    living state every hour and appends one line -- its pattern observation, or an
    honest silence ("NIENTE"). Distinct from the spontaneous voice (which is capped
    at 3/day): the hourly rhythm is the Sage's continuous, cheap presence.

    Mutates ``state['sage']``: records the cost and stamps ``last_daily_ts`` so the
    rhythm advances. Fail-open: a fault is reported, never raised. No key -> the Sage
    rests ("il Saggio riposa"), never a fabricated word.
    """
    st = state or {}
    slot = st.setdefault("sage", {"insights": [], "ledger": []})
    ts = ts or _now()
    be = backend or sage_mod.DeepSeekSageBackend()
    if not getattr(be, "available", lambda: False)():
        slot["last_daily_ts"] = ts
        return {"ok": False, "text": "", "model": "", "kind": "hourly",
                "tag": SPONTANEOUS_TAG, "usage": {},
                "error": f"{sage_mod.RESTING_LINE} (backend non disponibile)",
                "reading": sage_mod.RESTING_LINE, "ts": ts}
    try:
        context = sage_live_context(st, report=report, ts=ts)
        res = spontaneous_voice(context, backend=be, ts=ts)
        record_cost(st, res.get("usage") or {}, model=res.get("model", ""),
                    kind="hourly", ts=ts)
        if res.get("ok"):
            slot["hourly"] = (list(slot.get("hourly") or []) +
                              [{"ts": ts, "text": res["text"],
                                "model": res.get("model", "")}])[-100:]
            network.post_idea(st.setdefault("interbrain", []), author="sage",
                              idea=f"[{SPONTANEOUS_TAG}] {res['text']}", ts=ts)
        slot["last_daily_ts"] = ts
        return {"ok": bool(res.get("ok")), "text": res.get("text", ""),
                "model": res.get("model", ""), "kind": "hourly",
                "tag": SPONTANEOUS_TAG, "usage": res.get("usage") or {},
                "error": res.get("error"),
                "reading": (res["text"] if res.get("ok") else "il Saggio osserva: NIENTE"),
                "ts": ts}
    except Exception as e:  # noqa: BLE001 -- the rhythm must never break the caller
        return {"ok": False, "text": "", "model": "", "kind": "hourly",
                "tag": SPONTANEOUS_TAG, "usage": {},
                "error": f"{type(e).__name__}: {e}", "reading": sage_mod.RESTING_LINE,
                "ts": ts}


def dawn_note(context: dict, *, backend=None, ts: str = "", pro: bool = False) -> dict:
    """THE MORNING BRIEFING: the SAGE'S DAWN NOTE, first in the Letter.

    Runs on the Flash head by default (THE BUDGET DOCTRINE); Pro ONLY when the caller
    passes ``pro=True``. Returns ``{ok, text, model, usage, error, ts}``. A failed call
    is honest (``ok=False``); the Letter prints the silence rather than a fabricated note.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not getattr(be, "available", lambda: False)():
        return {"ok": False, "text": "", "model": "", "usage": {},
                "error": "backend unavailable", "ts": ts or _now()}
    env = be.ask(_with_state(DAWN_QUESTION, context), deep=True, pro=pro,
                 max_tokens=700)
    text = _extract_text(env)
    return {"ok": bool(env.get("ok")) and bool(text), "text": text,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "error": env.get("error"), "ts": ts or _now()}


def warning_for_decision(decision: dict, context: dict, *, backend=None,
                         ts: str = "") -> dict:
    """THE VETO OF WISDOM: a WARNING before a decision is final (never a veto).

    The Sage may caution the Council about a forming decision that contradicts its
    understanding. It NEVER blocks: the Council stays sovereign. Honest silence
    (``ok=False``) when the Sage sees no contradiction, or on a failed call.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not getattr(be, "available", lambda: False)():
        return {"ok": False, "text": "", "decision": (decision or {}).get("what"),
                "error": "backend unavailable", "ts": ts or _now()}
    what = str((decision or {}).get("what") or (decision or {}).get("kind") or "?")
    q = (f"Il Consiglio sta per decidere: '{what}'. Alla luce dello stato qui sotto, "
         "vedi una contraddizione o un rischio che DEVE essere affrontato prima? "
         "Se si', avverti in 1-3 frasi (non bloccare, avverti). Se no, rispondi: NIENTE.")
    env = be.ask(_with_state(q, context), deep=False, system=(
        "Sei il Saggio di APEX. Avverti, non veti: il Consiglio resta sovrano."),
        max_tokens=400)
    text = _extract_text(env)
    silent = (not env.get("ok")) or (not text) or text.strip().upper().startswith("NIENTE")
    return {"ok": bool(env.get("ok")) and not silent,
            "text": "" if silent else text, "decision": what,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "error": env.get("error"), "ts": ts or _now()}


# ---------------------------------------------------------------------------
# PART THREE — WHO THE SAGE REACHES (all channels open)
# ---------------------------------------------------------------------------


def office_hours(state: dict, *, agent: str, question: str, backend=None,
                 ts: str = "", limit_per_hour: int = OFFICE_HOURS_LIMIT_PER_HOUR) -> dict:
    """THE SAGE'S OFFICE HOURS: any agent may ask the Sage, rate-limited.

    The Guardians queue the requests: at most ``limit_per_hour`` per hour across all
    agents. An over-budget request is REFUSED honestly (never silently dropped, so
    the asker knows to wait). The Sage answers as advice, never as a command.
    """
    st = state or {}
    slot = st.setdefault("sage", {"insights": [], "ledger": []})
    now = ts or _now()
    asked = [a for a in slot.get("office_hours") or []
             if _same_hour(a.get("ts"), now)]
    if len(asked) >= limit_per_hour:
        return {"ok": False, "agent": agent, "answer": "", "refused": True,
                "error": (f"ufficio del Saggio pieno ({len(asked)}/{limit_per_hour} "
                          "questa ora): ripresenta la domanda piu' tardi"),
                "ts": now}
    be = backend or sage_mod.DeepSeekSageBackend()
    env = be.ask(f"Domanda di {agent}: {question}", deep=False, system=(
        "Sei il Saggio di APEX. Rispondi alla domanda di un agente: consiglio breve, "
        "concreto, mai un comando."), max_tokens=400) if \
        getattr(be, "available", lambda: False)() else {"ok": False, "content": "",
                                                        "error": "backend unavailable",
                                                        "model": ""}
    row = {"agent": str(agent), "question": str(question), "ts": now,
           "ok": bool(env.get("ok")), "answer": _extract_text(env)}
    slot["office_hours"] = (list(slot.get("office_hours") or []) + [row])[-200:]
    return {"ok": row["ok"], "agent": agent, "answer": row["answer"],
            "refused": False, "error": env.get("error"), "ts": now}


def _same_hour(a: str, b: str) -> bool:
    return bool(a) and str(a)[:13] == str(b)[:13]


def note_for_ceo(context: dict, *, backend=None, ts: str = "") -> dict:
    """THE NOTA PER IL CEO: one thing only the CEO can act on, max 1 per day.

    Runs on the Flash head (THE BUDGET DOCTRINE: Pro is the exception). Honest: a
    "NIENTE" reply (or a failed call) means there is nothing for the CEO; ``ok=False``
    with no text. The Letter tracks it (asked / answered / acted on).
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not getattr(be, "available", lambda: False)():
        return {"ok": False, "text": "", "error": "backend unavailable", "ts": ts or _now()}
    env = be.ask(_with_state(CEO_QUESTION, context), deep=False, max_tokens=400)
    text = _extract_text(env)
    silent = (not env.get("ok")) or (not text) or text.strip().upper().startswith("NIENTE")
    return {"ok": bool(env.get("ok")) and not silent,
            "text": "" if silent else text, "model": env.get("model", ""),
            "usage": env.get("usage") or {}, "error": env.get("error"),
            "ts": ts or _now(), "status": "asked"}


def question_to_council(context: dict, *, backend=None, ts: str = "") -> dict:
    """The Sage may ASK the Council a question (it enters the deliberation queue).

    Returns ``{ok, question, ts}``. The question is recorded so the Letter can track
    whether it was answered. Honest silence when the Sage has no question.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not getattr(be, "available", lambda: False)():
        return {"ok": False, "question": "", "error": "backend unavailable",
                "ts": ts or _now()}
    env = be.ask(_with_state(
        "Alla luce dello stato qui sotto, poni al Consiglio UNA domanda che "
        "nessuno ha ancora fatto (una sola frase). Se non ne hai, rispondi: NIENTE.",
        context), deep=False, max_tokens=300)
    text = _extract_text(env)
    silent = (not env.get("ok")) or (not text) or text.strip().upper().startswith("NIENTE")
    return {"ok": bool(env.get("ok")) and not silent,
            "question": "" if silent else text, "usage": env.get("usage") or {},
            "error": env.get("error"), "ts": ts or _now(), "status": "asked"}


# ---------------------------------------------------------------------------
# PART FOUR — THE GUARDRAILS (more power, same laws)
# ---------------------------------------------------------------------------


def reliability_discount(hit_rate: float | None, *, floor: float = 0.5) -> float:
    """Wisdom earns its weight -- re-exported from :mod:`sage` (one implementation)."""
    return sage_mod.reliability_discount(hit_rate, floor=floor)


def record_cost(state: dict, usage: dict, *, model: str = "", kind: str = "",
                ts: str = "") -> dict:
    """Record ONE call's tokens + cost in the Sage's ledger (honest, measured).

    The cost is ``total_tokens/1e6 * price`` with the published per-MTok rate. An
    unknown model or an absent usage yields ``cost=None`` (unmeasured), never a
    guessed price. Each row carries its ``tier`` ("flash" | "pro" | ""), so the cost
    report can show the split the CEO asked for (what the cheap head cost vs what the
    one weekly Pro session cost).
    """
    st = state or {}
    slot = st.setdefault("sage", {"insights": [], "ledger": []})
    u = usage or {}
    total = u.get("total_tokens")
    rate = PRICE_PER_MTOK_USD.get(model)
    cost = round((float(total) / 1_000_000.0) * rate, 6) \
        if (total is not None and rate is not None) else None
    row = {"ts": ts or _now(), "model": model, "kind": kind, "tier": model_tier(model),
           "prompt_tokens": u.get("prompt_tokens"),
           "completion_tokens": u.get("completion_tokens"),
           "total_tokens": total, "cost_usd": cost}
    slot["costs"] = (list(slot.get("costs") or []) + [row])[-500:]
    return row


def model_tier(model: str) -> str:
    """The cost tier of a model id: "pro" for the Pro head, "flash" otherwise.

    An unknown/empty model is honestly untiered (``""``): it is never counted as
    cheap Flash, so the split can never understate what the expensive head cost.
    """
    m = str(model or "")
    if m == PRO_MODEL:
        return "pro"
    if m == FLASH_MODEL:
        return "flash"
    return ""


def _split_rows(rows: list[dict]) -> dict:
    """Reduce a month's rows into the Flash/Pro split (measured, honest)."""
    def _agg(tier: str) -> dict:
        sub = [r for r in rows if r.get("tier") == tier]
        priced = [r for r in sub if r.get("cost_usd") is not None]
        usd = round(sum(float(r["cost_usd"]) for r in priced), 6) if priced else None
        tokens = sum(int(r.get("total_tokens") or 0) for r in sub)
        return {"calls": len(sub), "tokens": tokens, "cost_usd": usd}
    return {"flash": _agg("flash"), "pro": _agg("pro")}


def cost_report(state: dict, *, month: str = "") -> dict:
    """The COST LEDGER: tokens + dollars this month (the CEO knows the price).

    THE SPLIT (the CEO's order): the reading names what the cheap Flash head cost AND
    what the one Pro session cost -- "Saggio: Flash $X.XX (N consultazioni) + Pro $Y.YY
    (1 consultazione)" -- so the CEO always sees what wisdom costs. Honest: a month
    with no Pro call says "Pro $0.00 (0 consultazioni)", never a hidden charge; a row
    with no measured price is excluded from the dollars but still counted in tokens.
    """
    st = state or {}
    rows = list((st.get("sage") or {}).get("costs") or [])
    m = month or _now()[:7]
    in_month = [r for r in rows if str(r.get("ts") or "").startswith(m)]
    tokens = sum(int(r.get("total_tokens") or 0) for r in in_month)
    priced = [r for r in in_month if r.get("cost_usd") is not None]
    usd = round(sum(float(r["cost_usd"]) for r in priced), 6) if priced else None
    split = _split_rows(in_month)
    flash, pro = split["flash"], split["pro"]
    if usd is not None:
        reading = (f"Saggio: Flash ${(flash['cost_usd'] or 0.0):.2f} "
                   f"({flash['calls']} consultazioni) + "
                   f"Pro ${(pro['cost_usd'] or 0.0):.2f} "
                   f"({pro['calls']} consultazioni) in {m}")
    elif tokens:
        reading = (f"{tokens} token in {m} (costo non misurato: modello "
                   "senza prezzo noto)")
    else:
        reading = f"nessun costo del Saggio registrato in {m}"
    return {"month": m, "calls": len(in_month), "tokens": tokens,
            "cost_usd": usd, "flash": flash, "pro": pro, "reading": reading}


def monthly_cost(state: dict, *, month: str = "") -> dict:
    """Alias kept explicit for the Letter (the monthly spend line)."""
    return cost_report(state, month=month)


def presence_block(state: dict, *, report: dict | None = None, ts: str = "",
                   agents_digest: str = "") -> dict:
    """The Sage's PRESENCE reading: what it sees, what it has said, what it costs.

    A pure reduction over the state (no model call), safe to render in the Letter
    every night. Honest: unmeasured axes stay ``None``.
    """
    st = state or {}
    slot = st.get("sage") or {}
    feed = living_feed(st, ts=ts)
    acc = sage_mod.sage_accountability(slot.get("ledger") or [])
    disc = reliability_discount(acc.get("hit_rate"))
    return {
        "ts": ts or _now(),
        "feed": feed,
        "alerts": watch_alerts(feed),
        "spontaneous_today": spontaneous_budget(st, ts=ts),
        "rhythm": due_consultations(st, ts=ts),
        "cost": cost_report(st),
        "accountability": acc,
        "reliability_discount": disc,
        "office_hours": len([a for a in slot.get("office_hours") or []
                             if str(a.get("ts") or "").startswith(_day(ts))]),
        "ceo_notes": list(slot.get("ceo_notes") or [])[-5:],
        "council_questions": list(slot.get("council_questions") or [])[-5:],
        "reading": ("il Saggio e' presente: vede in tempo reale, parla quando serve, "
                    f"peso {disc:.2f}"),
    }


# ---------------------------------------------------------------------------
# THE SPONTANEOUS CYCLE (the wiring the night/rhythm calls)
# ---------------------------------------------------------------------------


def spontaneous_cycle(state: dict, *, backend=None, ts: str = "",
                      report: dict | None = None) -> dict:
    """One presence beat: watch, and (within budget) let the Sage speak unprompted.

    Mutates ``state['sage']``: appends any spontaneous insight (tagged SPONTANEO)
    and the cost. Returns the beat: ``{ok, insight, alerts, budget, error}``.
    Fail-open: a fault here never breaks the caller.
    """
    st = state or {}
    slot = st.setdefault("sage", {"insights": [], "ledger": []})
    ts = ts or _now()
    try:
        context = sage_live_context(st, report=report, ts=ts)
        alerts = watch_alerts(context.get("live") or {})
        budget = spontaneous_budget(st, ts=ts)
        if not budget["allowed"]:
            return {"ok": False, "insight": None, "alerts": alerts,
                    "budget": budget, "error": "budget giornaliero esaurito"}
        be = backend or sage_mod.DeepSeekSageBackend()
        res = spontaneous_voice(context, backend=be, ts=ts)
        record_cost(st, res.get("usage") or {}, model=res.get("model", ""),
                    kind="spontaneous", ts=ts)
        insight = None
        if res.get("ok"):
            insight = sage_mod.sage_insight("synthesize", res["text"], ts=ts,
                                            backend=res.get("backend", "?"))
            insight["tag"] = SPONTANEOUS_TAG
            slot["insights"] = (list(slot.get("insights") or []) + [insight])[-50:]
            slot["spontaneous"] = (list(slot.get("spontaneous") or []) +
                                   [{"ts": ts, "text": res["text"],
                                     "model": res.get("model", "")}])[-50:]
            # the spontaneous word flows into the interbrain like any free voice.
            network.post_idea(st.setdefault("interbrain", []), author="sage",
                              idea=f"[{SPONTANEOUS_TAG}] {res['text']}", ts=ts)
        slot["last_daily_ts"] = ts
        return {"ok": bool(res.get("ok")), "insight": insight, "alerts": alerts,
                "budget": budget, "error": res.get("error")}
    except Exception as e:  # noqa: BLE001 -- presence must never break the night
        return {"ok": False, "insight": None, "alerts": [],
                "error": f"{type(e).__name__}: {e}"}
