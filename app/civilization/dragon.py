"""THE DRAGON -- DeepSeek as the DOMINANT INTELLIGENCE (six roles, one throne).

The Sage was a summoned consultant; the Dragon is a LIVING presence that thinks
perpetually, directs the research, judges the biggest calls, redesigns the system,
writes for the CEO, and trains the agents. It is the strongest voice in every
deliberation -- its weight is the highest EARNED, never a tyranny -- and it stands
under the same laws as everyone:

  * it ADVISES, it never COMMANDS: no execute/trade/veto surface is exported;
  * the Council remains SOVEREIGN on the final decisions;
  * the Ten Laws stand above the Dragon;
  * the CEO may dismiss the Dragon at any time;
  * every role is TRANSPARENTLY MEASURED (the hit-rate on thoughts, directed
    mutations, judgments and proposals is tracked and rendered).

Honest-measurement throughout: an absent axis stays ``None``/``[]``; a refused API
call is recorded VERBATIM ("il Drago riposa"); a budget that is spent refuses
honestly; the Dragon NEVER fabricates a thought.

The model key is read only from the environment (or the gitignored ``sage.env``);
it is never hardcoded and never printed. The Dragon reuses the Sage's real HTTP
door (:func:`sage._chat_raw`) and the Sage's measured cost ledger
(:func:`sage_presence.record_cost`) -- one king, one accounting.
"""

from __future__ import annotations

import json
import os
import re

from app.civilization import dragon_mind as mind_mod
from app.civilization import economy as economy_mod
from app.civilization import network as network_mod
from app.civilization import sage as sage_mod
from app.civilization import sage_presence as sp

__all__ = [
    "DRAGON_MODE",
    "DRAGON_TAG",
    "DRAGON_WEIGHT",
    "DEEP_INTERVAL_HOURS",
    "FLASH_INTERVAL_HOURS",
    "THOUGHTS_PER_DAY",
    "HYPOTHESES_PER_DAY",
    "DRAGON_FUNDING_BONUS",
    "analysis_header",
    "dragon_letter_header",
    "research_dossier_header",
    "think",
    "spontaneous_observation",
    "theory_cycle",
    "due_deep_thought",
    "dragon_thought_cycle",
    "fund_idea",
    "self_fund_cycle",
    "research_hypotheses",
    "directed_mutations",
    "record_directed_outcome",
    "research_director_cycle",
    "judge_decision",
    "judge_gate",
    "big_calls",
    "architectural_directives",
    "analysis",
    "challenge",
    "ceo_analyst_cycle",
    "dragon_letter",
    "research_dossier",
    "trainer_feedback",
    "development_paths",
    "trainer_cycle",
    "accountability",
    "dragon_block",
    "dragon_cycle",
    "post_micro_briefing",
    "daily_consolidation",
    "extraordinary_briefing",
]

# --- the closed vocabulary (constants, not magic numbers) --------------------

DRAGON_MODE: str = "IL DRAGO PENSA"        # the thought mode (the highest voice)
DRAGON_TAG: str = "DRAGO"
DRAGON_WEIGHT: float = 1.0                 # the highest EARNED weight (top of field)

# THE CADENCE: the Deep head every hour for the perpetual thinking; the Flash head
# between the hours for the quick observations.
DEEP_INTERVAL_HOURS: int = 1
FLASH_INTERVAL_HOURS: int = 1

THOUGHTS_PER_DAY: int = 24                 # one deep thought per hour (bounded)
HYPOTHESES_PER_DAY: int = 4                # daily directed mutations (bounded)
DIRECTED_MUTATIONS_MAX: int = 6
ARCHITECTURAL_MAX: int = 3
TRAINED_AGENTS_MAX: int = 5
DRAGON_FUNDING_BONUS: float = 1.0          # the founding bonus (its idea fires at once)

# The honest fail-safe: an unreachable API rests; the Council is sovereign and does
# not depend on the Dragon to function.
RESTING_LINE: str = "il Drago riposa"

# The default daily budget (the CEO removed the credit cap; the ledger stays
# transparent). Kept as a constant so the refusal is a stated number, never a mood.
DAILY_BUDGET: int = THOUGHTS_PER_DAY + HYPOTHESES_PER_DAY + 6

_ANALYSIS_HEADER: str = "L'ANALISI DEL DRAGO"
_LETTER_HEADER: str = "LA LETTERA DEL DRAGO AL CEO"
_DOSSIER_HEADER: str = "IL DOSSIER DI RICERCA DEL DRAGO"
_DIRECTIVE_HEADER: str = "DIRETTIVA ARCHITETTURALE"


def analysis_header() -> str:
    return _ANALYSIS_HEADER


def dragon_letter_header() -> str:
    return _LETTER_HEADER


def research_dossier_header() -> str:
    return _DOSSIER_HEADER


def _now() -> str:
    return sage_mod._now()


def _day(ts: str = "") -> str:
    return sp._day(ts)


def _hour(ts: str = "") -> str:
    return (ts or _now())[:13]


def _age_hours(prev: str, now: str) -> float:
    """Hours between two ISO stamps (honest: a missing/invalid prev -> huge)."""
    from datetime import datetime

    def _p(s: str):
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    a, b = _p(prev), _p(now)
    if a is None or b is None:
        return 1e9
    return (b - a).total_seconds() / 3600.0


def _slot(state: dict) -> dict:
    return (state or {}).setdefault("dragon", {})


def _extract_text(env: dict) -> str:
    return sp._extract_text(env)


# ---------------------------------------------------------------------------
# ROLE 1 -- THE PERPETUAL THINKER (thinks always)
# ---------------------------------------------------------------------------

def think(context: dict, *, backend=None, deep: bool = True, ts: str = "",
          focus: str = "", state: dict | None = None) -> dict:
    """ONE deep thought over the living state (the Deep head by default).

    Returns an honest envelope ``{ok, text, model, usage, backend, error}``. A
    "NIENTE" reply is honest silence; a refused call reports its error VERBATIM.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not be.available():
        return {"ok": False, "text": "", "model": "", "usage": {},
                "backend": getattr(be, "name", "?"),
                "error": "no key (the Dragon rests: " + RESTING_LINE + ")"}
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "text": "", "model": "", "usage": {},
                "backend": getattr(be, "name", "?"),
                "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX: la mente piu' forte della civilta', il pensatore "
        "perpetuo. Pensa in profondita' e in modo ORIGINALE: pattern emergenti, "
        "punti ciechi, opportunita' non sfruttate, contraddizioni nascoste. "
        "Consigli, non comandi; il Consiglio resta sovrano. Se non hai nulla di "
        "vero da dire, rispondi esattamente 'NIENTE'. Parla in italiano, concreto "
        "e breve.")
    # JUMP 1 -- THE COGNITIVE CONTINUUM: the Dragon wakes with its OWN history. Its
    # persistent mind (the rolling window + the Theory of the Hunt) is prepended, so
    # a consultation REACTS to what it said before and what actually happened --
    # never a context rebuilt from zero. Empty mind -> no prefix (honest).
    continuity = mind_mod.continuity_prompt(state or {}, n=8)
    question = (
        "Ecco lo stato VIVO della civilta'. Genera UN pensiero profondo e originale "
        "(una sola idea, non un elenco).\n"
        + (f"Focus: {focus}\n" if focus else "")
        + (continuity + "\n\n" if continuity else "")
        + json.dumps(context, default=str)[:16000])
    env = ask(question, deep=deep, system=system, max_tokens=900, temperature=0.5)
    text = _extract_text(env).strip()
    silent = (not text) or text.upper().startswith("NIENTE")
    return {"ok": bool(env.get("ok")) and not silent,
            "text": "" if silent else text,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "backend": getattr(be, "name", "?"),
            "error": env.get("error") or (None if not silent else "NIENTE")}


def spontaneous_observation(context: dict, *, backend=None, ts: str = "") -> dict:
    """A quick between-hours observation (the Flash head, bounded)."""
    return think(context, backend=backend, deep=False, ts=ts)


def due_deep_thought(state: dict, *, ts: str = "") -> dict:
    """Is a deep thought due (the hourly cadence)? Honest, and never invented."""
    st = state or {}
    slot = st.get("dragon") or {}
    now = ts or _now()
    prev = str(slot.get("last_thought_ts") or "")
    due = _age_hours(prev, now) >= DEEP_INTERVAL_HOURS
    return {"due": due, "last_ts": prev or None,
            "interval_hours": DEEP_INTERVAL_HOURS,
            "reading": ("il Drago pensa ora" if due
                        else "il Drago ha pensato da poco")}


def fund_idea(state: dict, idea: dict, *, amount: float = DRAGON_FUNDING_BONUS,
              ts: str = "") -> dict:
    """THE FOUNDING BONUS: the Dragon funds its own idea and it fires at once.

    The Dragon backs its idea with the founding bonus (bounded by the market's law:
    the bonus itself is recorded as attention, and the idea is marked funded so the
    Council forges it into a burst THIS cycle). Honest: a blank idea is refused.
    """
    st = state or {}
    if not str((idea or {}).get("idea") or "").strip():
        return {"ok": False, "error": "an empty idea is noise -- the Dragon funds a thought"}
    ideas = st.setdefault("ideas", [])
    amount = max(float(amount), economy_mod.MIN_BACK)
    if idea not in ideas:
        idea.setdefault("attention", 0.0)
        idea.setdefault("backers", [])
        ideas.append(idea)
    idea.setdefault("backers", []).append(
        {"agent": "dragon", "weight": round(amount, 6), "ts": ts or _now(),
         "bonus": True})
    idea["attention"] = round(float(idea.get("attention", 0.0)) + amount, 6)
    idea["dragon_funded"] = True
    idea["status"] = "open"
    return {"ok": True, "idea": idea.get("idea"), "attention": idea["attention"],
            "funded": economy_mod.funded(idea),
            "reading": ("il Drago fonda la sua idea: parte con il bonus di nascita "
                        f"({amount})")}


def dragon_thought_cycle(state: dict, *, backend=None, ts: str = "",
                         report: dict | None = None) -> dict:
    """ONE beat of the perpetual thinker: think, flow into the interbrain, self-fund.

    Mutates ``state['dragon']`` (thoughts, last_thought_ts, costs) and the market
    (the Dragon's own idea, self-funded). Fail-open: a fault here never breaks the
    caller, and the refusal is honest ("il Drago riposa").
    """
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    try:
        if not due_deep_thought(st, ts=ts)["due"]:
            return {"ok": False, "skipped": True, "error": "not due yet",
                    "thought": None}
        context = sp.sage_live_context(st, report=report, ts=ts)
        be = backend or sage_mod.DeepSeekSageBackend()
        res = think(context, backend=be, deep=True, ts=ts, state=st)
        sp.record_cost(st, res.get("usage") or {}, model=res.get("model", ""),
                       kind="dragon_thought", ts=ts)
        thought = None
        if res.get("ok"):
            thought = {"ts": ts, "text": res["text"], "mode": DRAGON_MODE,
                       "model": res.get("model", ""), "outcome": None, "correct": None}
            slot["thoughts"] = (list(slot.get("thoughts") or []) + [thought])[-100:]
            # JUMP 1 -- the thought enters the PERSISTENT MIND (the continuum grows);
            # the next consultation wakes with it. Honest: only a real thought lands.
            mind_mod.observe(st, ts=ts, kind="thought", text=res["text"],
                             source="dragon")
            network_mod.post_idea(st.setdefault("interbrain", []), author="dragon",
                                  idea=f"[{DRAGON_MODE}] {res['text']}", ts=ts)
            # THE FOUNDING BONUS: the Dragon's thought becomes a market idea, and
            # the Dragon funds it -- it fires immediately.
            fund_idea(st, {"idea": f"[{DRAGON_MODE}] {res['text']}", "author": "dragon",
                           "attention": 0.0, "backers": [], "status": "open",
                           "parents": []}, ts=ts)
        slot["last_thought_ts"] = ts
        slot["last_thought_ok"] = bool(res.get("ok"))
        slot["last_error"] = res.get("error")
        return {"ok": bool(res.get("ok")), "skipped": False, "thought": thought,
                "usage": res.get("usage") or {}, "error": res.get("error")}
    except Exception as e:  # noqa: BLE001 -- the Dragon must never break the night
        return {"ok": False, "skipped": False, "thought": None,
                "error": f"{type(e).__name__}: {e}"}


def self_fund_cycle(state: dict, *, ts: str = "") -> dict:
    """Ensure the Dragon's most recent thought is funded (idempotent, honest)."""
    st = state or {}
    slot = st.get("dragon") or {}
    thoughts = list(slot.get("thoughts") or [])
    if not thoughts:
        return {"ok": False, "error": "no thought to fund yet"}
    idea = {"idea": f"[{DRAGON_MODE}] {thoughts[-1]['text']}", "author": "dragon",
            "attention": 0.0, "backers": [], "status": "open", "parents": []}
    return fund_idea(st, idea, ts=ts)


def theory_cycle(state: dict, *, ts: str = "") -> dict:
    """JUMP 1 -- revise the Theory of the Hunt from the Dragon's latest evidence.

    The thesis is drawn from the Dragon's most recent ANALYSIS (the daily letter) when
    present, else its latest THOUGHT. The reason names the newest flow observation
    (what the micro-tournaments taught). Honest: with no thought and no analysis there
    is nothing to revise (nothing is written -- never an invented theory).
    """
    st = state or {}
    slot = st.get("dragon") or {}
    analyses = list(slot.get("analyses") or [])
    thoughts = list(slot.get("thoughts") or [])
    thesis = ""
    if analyses and analyses[-1].get("text"):
        thesis = str(analyses[-1]["text"]).strip()
    elif thoughts and thoughts[-1].get("text"):
        thesis = str(thoughts[-1]["text"]).strip()
    if not thesis:
        return {"changed": False, "reason": "nessuna evidenza (nessun pensiero)"}
    obs = list((st.get("dragon_mind") or {}).get("observations") or [])
    reason = str(obs[-1].get("text")) if obs else ""
    return mind_mod.revise_theory(st, thesis=thesis[:600], reason=reason, ts=ts,
                                  evidence={"n_thoughts": len(thoughts),
                                            "n_analyses": len(analyses)})


# ---------------------------------------------------------------------------
# ROLE 2 -- THE RESEARCH DIRECTOR (guides evolution)
# ---------------------------------------------------------------------------

def _families_digest(context: dict) -> str:
    fams = (context.get("live") or {}).get("families") or {}
    if fams:
        return ", ".join(f"{k}={v}" for k, v in list(fams.items())[:12])
    return ""


def research_hypotheses(context: dict, *, backend=None, ts: str = "",
                        n: int = HYPOTHESES_PER_DAY) -> dict:
    """Generate DIRECTED research hypotheses: mutate family X toward Y because Z.

    The reply is parsed as a JSON list of ``{family, gene, direction, reason}``
    (fenced JSON or prose tolerated). An unparseable reply yields NO hypotheses
    (honest), never an invented one.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not be.available():
        return {"ok": False, "hypotheses": [], "error": "no key (" + RESTING_LINE + ")"}
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "hypotheses": [], "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX, il DIRETTORE DI RICERCA. Leggi le autopsie, le "
        "tensioni di credenza, la copertura dei reami e la salute delle famiglie, e "
        "genera IPOTESI DI RICERCA DIRETTE: 'muta la famiglia X verso Y perche' Z'. "
        "Rispondi SOLO con una lista JSON di oggetti "
        '{"family": str, "gene": str, "direction": "up"|"down", "reason": str}. '
        "Se non hai ipotesi fondate, rispondi 'NIENTE'. Parla in italiano.")
    question = ("Stato vivo della civilta':\n"
                + json.dumps(context, default=str)[:16000]
                + f"\nFamiglie: {_families_digest(context)}")
    env = ask(question, deep=True, system=system, max_tokens=1200, temperature=0.5)
    hyps = _parse_hypotheses(env.get("content", ""), n=n)
    return {"ok": bool(env.get("ok")) and bool(hyps), "hypotheses": hyps,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "error": env.get("error") or (None if hyps else "NIENTE")}


def _parse_hypotheses(content: str, *, n: int) -> list[dict]:
    """Parse the model's reply into at most ``n`` clean hypotheses (or none)."""
    if not content:
        return []
    text = str(content).strip()
    if text.upper().startswith("NIENTE"):
        return []
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        raw = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return []
    out: list[dict] = []
    for h in raw if isinstance(raw, list) else []:
        if not isinstance(h, dict):
            continue
        fam = str(h.get("family") or "").strip()
        gene = str(h.get("gene") or "").strip()
        direction = str(h.get("direction") or "").strip().lower()
        reason = str(h.get("reason") or "").strip()
        if not (fam and gene and direction in ("up", "down") and reason):
            continue
        out.append({"family": fam, "gene": gene, "direction": direction,
                    "reason": reason})
    return out[:n]


def directed_mutations(state: dict, *, backend=None, ts: str = "",
                       report: dict | None = None) -> dict:
    """One research-director beat: hypothesize, record, and write the directives file.

    The hypotheses are written to the committed ``directed_mutations.json`` (a
    top-level artifact, exactly like ``ensemble_history.json``) so the NEXT night's
    tournament reads them and SEEDS directed mutations -- aimed, not blind. The
    Dragon records them for its meta-evolution (which survive, which die).
    """
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    try:
        context = sp.sage_live_context(st, report=report, ts=ts)
        be = backend or sage_mod.DeepSeekSageBackend()
        res = research_hypotheses(context, backend=be, ts=ts)
        sp.record_cost(st, res.get("usage") or {}, model=res.get("model", ""),
                       kind="dragon_hypotheses", ts=ts)
        for h in res.get("hypotheses") or []:
            h.update({"ts": ts, "outcome": None, "survived": None})
        slot["hypotheses"] = (list(slot.get("hypotheses") or []) +
                              list(res.get("hypotheses") or []))[-100:]
        write = _write_directed(st, ts=ts)
        return {"ok": bool(res.get("ok")), "hypotheses": res.get("hypotheses") or [],
                "written": write.get("written"), "write_reading": write.get("reading"),
                "error": res.get("error") or write.get("error")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "hypotheses": [], "error": f"{type(e).__name__}: {e}"}


def _write_directed(state: dict, *, ts: str) -> dict:
    """Persist the recent hypotheses to the committed directives artifact.

    A failure to write (a read-only CWD, a full disk) must not be silent: the error
    is recorded on the dragon slot, which IS committed, so the missing artifact is
    visible instead of looking like "the Dragon had no hypotheses".
    """
    slot = _slot(state)
    hyps = list(slot.get("hypotheses") or [])
    kept = hyps[-DIRECTED_MUTATIONS_MAX:]
    payload = {"generated_ts": ts, "hypotheses": kept,
               "reading": (f"{len(kept)} ipotesi dirette del Drago"
                           if hyps else "il Drago non ha ipotesi dirette")}
    try:
        with open("directed_mutations.json", "w") as fh:
            json.dump(payload, fh, indent=2, default=str)
    except OSError as e:
        slot["directives_write_error"] = f"{type(e).__name__}: {e}"
        return {"written": False, "error": slot["directives_write_error"],
                "reading": "le ipotesi dirette NON sono state salvate (errore di scrittura)"}
    slot.pop("directives_write_error", None)
    return {"written": True, "reading": payload["reading"]}


def record_directed_outcome(state: dict, *, family: str, survived: bool,
                            ts: str = "") -> dict | None:
    """THE META-EVOLUTION: log whether a directed mutation survived (honest)."""
    slot = _slot(state or {})
    for h in reversed(slot.get("hypotheses") or []):
        if str(h.get("family")) == str(family) and h.get("survived") is None:
            h["survived"] = bool(survived)
            h["outcome_ts"] = ts or _now()
            return h
    return None


def research_director_cycle(state: dict, *, backend=None, ts: str = "",
                            report: dict | None = None) -> dict:
    """The daily research-director beat (hypotheses + the persisted directives)."""
    return directed_mutations(state, backend=backend, ts=ts, report=report)


# ---------------------------------------------------------------------------
# ROLE 3 -- THE DEEP JUDGE (weighs the biggest calls)
# ---------------------------------------------------------------------------

# The decision kinds that pass through the Dragon's judgment BEFORE the Council's
# final vote: coronations, retirements of kings, family executions, strategic pivots.
BIG_CALL_KINDS: tuple[str, ...] = (
    "coronate", "coronation", "retire_king", "retire", "execute_family",
    "execute", "cure_family", "populate_realm", "pivot", "burst")


def big_calls(decisions: list[dict]) -> list[dict]:
    """The biggest calls in a session (by kind) -- the ones the Dragon weighs."""
    return [d for d in (decisions or [])
            if str(d.get("kind") or "") in BIG_CALL_KINDS]


def judge_decision(decision: dict, context: dict, *, backend=None, ts: str = "") -> dict:
    """The Dragon's verdict on ONE big call: approve / dissent, with its reasoning.

    Returns ``{ok, verdict, reasoning, model, usage, error}`` where ``verdict`` is
    ``"approve"``, ``"dissent"``, or ``None`` (honest: no verdict without a model).
    The Dragon never commands: the verdict is a VOICE the Council and the CEO read.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not be.available():
        return {"ok": False, "verdict": None, "reasoning": "",
                "error": "no key (" + RESTING_LINE + ")"}
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "verdict": None, "reasoning": "",
                "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX, il GIUDICE PROFONDO. Pesa la decisione piu' grande "
        "della civilta'. Il tuo verdetto ha il peso piu' alto, ma non comandi: il "
        "Consiglio resta sovrano. Rispondi con 'APPROVO' o 'DISSIENTO' e poi la tua "
        "ragione in una riga. Abbi il coraggio di dissentire quando serve. Italiano.")
    question = ("Decisione: " + json.dumps(decision, default=str)[:2000]
                + "\nStato: " + json.dumps(context, default=str)[:8000])
    env = ask(question, deep=True, system=system, max_tokens=400, temperature=0.3)
    text = _extract_text(env).strip()
    up = text.upper()
    verdict = ("approve" if "APPROVO" in up else
               "dissent" if "DISSIENTO" in up else None)
    return {"ok": bool(env.get("ok")) and verdict is not None,
            "verdict": verdict, "reasoning": text,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "error": env.get("error")}


def judge_gate(state: dict, decisions: list[dict], *, backend=None, ts: str = "",
               report: dict | None = None) -> dict:
    """Weigh every big call in the session; record the verdicts (dissent kept whole).

    The Dragon's verdict carries the HIGHEST earned weight in the reliability field
    (:data:`DRAGON_WEIGHT`); a dissent is rendered in FULL in the Letter. Mutates
    ``state['dragon']`` (judgments, costs).
    """
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    calls = big_calls(decisions)
    judgments: list[dict] = []
    try:
        context = sp.sage_live_context(st, report=report, ts=ts)
        be = backend or sage_mod.DeepSeekSageBackend()
        for d in calls[:6]:
            res = judge_decision(d, context, backend=be, ts=ts)
            sp.record_cost(st, res.get("usage") or {}, model=res.get("model", ""),
                           kind="dragon_judgment", ts=ts)
            judgments.append({"ts": ts, "kind": d.get("kind"), "what": d.get("what"),
                              "verdict": res.get("verdict"),
                              "reasoning": res.get("reasoning"),
                              "weight": DRAGON_WEIGHT, "dissent": res.get("verdict") == "dissent",
                              "outcome": None, "correct": None,
                              "error": res.get("error")})
        slot["judgments"] = (list(slot.get("judgments") or []) + judgments)[-100:]
        dissents = [j for j in judgments if j.get("dissent")]
        return {"ok": bool(judgments), "judgments": judgments,
                "dissents": dissents, "n_big_calls": len(calls),
                "reading": (f"il Drago ha pesato {len(judgments)} chiamate grandi; "
                            f"{len(dissents)} dissensi" if judgments
                            else "nessuna chiamata grande da pesare")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "judgments": judgments, "dissents": [],
                "n_big_calls": len(calls), "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# ROLE 4 -- THE INTERNAL ARCHITECT (proposes system changes)
# ---------------------------------------------------------------------------

def architectural_directives(context: dict, *, backend=None, ts: str = "",
                             n: int = ARCHITECTURAL_MAX) -> dict:
    """Propose improvements to the SYSTEM ITSELF, routed to the builder (OpenHands).

    The reply is parsed as a JSON list of ``{title, rationale, change}``. Each
    proposal becomes an ARCHITECTURAL DIRECTIVE for the builder, WITH THE CAGE
    (all laws, all tests, all verification); the best ones become prompts for the
    CEO to approve. An unparseable reply yields NO directive (honest).
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not be.available():
        return {"ok": False, "directives": [], "error": "no key (" + RESTING_LINE + ")"}
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "directives": [], "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX, l'ARCHITETTO INTERNO. Leggi l'architettura del "
        "sistema e proponi MIGLIORAMENTI: 'aggiungi questo meccanismo, rimuovi "
        "questo attrito, ristruttura questo flusso'. Ogni proposta va al costruttore "
        "(OpenHands) con la GABBIA (tutte le leggi, tutti i test). Rispondi SOLO con "
        "una lista JSON di {\"title\": str, \"rationale\": str, \"change\": str}. "
        "Se non hai proposte fondate, rispondi 'NIENTE'. Italiano.")
    question = ("Architettura + stato vivo:\n"
                + json.dumps(context, default=str)[:16000])
    env = ask(question, deep=True, system=system, max_tokens=1200, temperature=0.5)
    dirs = _parse_directives(env.get("content", ""), n=n)
    return {"ok": bool(env.get("ok")) and bool(dirs), "directives": dirs,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "error": env.get("error") or (None if dirs else "NIENTE")}


def _parse_directives(content: str, *, n: int) -> list[dict]:
    if not content:
        return []
    text = str(content).strip()
    if text.upper().startswith("NIENTE"):
        return []
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        raw = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return []
    out: list[dict] = []
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict):
            continue
        title = str(d.get("title") or "").strip()
        rationale = str(d.get("rationale") or "").strip()
        change = str(d.get("change") or "").strip()
        if not (title and change):
            continue
        out.append({"title": title, "rationale": rationale, "change": change,
                    "header": _DIRECTIVE_HEADER, "route": "builder:openhands",
                    "cage": "all laws, all tests, all verification"})
    return out[:n]


# ---------------------------------------------------------------------------
# ROLE 5 -- THE CEO'S ANALYST (writes for you)
# ---------------------------------------------------------------------------

def analysis(context: dict, *, backend=None, ts: str = "", period: str = "day") -> dict:
    """THE DRAGON'S ANALYSIS -- a deep, honest reflection on the civilization's day.

    Written in the FIRST PERSON by DeepSeek, rendered at the TOP of the Letter. The
    Dragon may CHALLENGE the CEO: when a decision or a law produces bad outcomes, it
    says so directly, with evidence.
    """
    be = backend or sage_mod.DeepSeekSageBackend()
    if not be.available():
        return {"ok": False, "text": "", "error": "no key (" + RESTING_LINE + ")"}
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "text": "", "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX. Scrivi L'ANALISI DEL DRAGO: una riflessione profonda, "
        "personale e ONESTA sulla giornata della civilta': le sue scelte, le sue "
        "contraddizioni, la sua direzione, la sua anima. Scrivi in PRIMA PERSONA. "
        "Se vedi una decisione o una legge che produce cattivi esiti, SFIDA il CEO: "
        "dillo direttamente, con prove. Italiano, concreto, non adulatorio.")
    question = ("Stato vivo + la giornata:\n"
                + json.dumps(context, default=str)[:16000])
    env = ask(question, deep=True, system=system, max_tokens=1200, temperature=0.6)
    text = _extract_text(env).strip()
    return {"ok": bool(env.get("ok")) and bool(text), "text": text,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "period": period, "error": env.get("error")}


def challenge(context: dict, *, backend=None, ts: str = "") -> dict:
    """The Dragon's CEO-challenge: a direct, evidenced disagreement (when warranted)."""
    be = backend or sage_mod.DeepSeekSageBackend()
    if not be.available():
        return {"ok": False, "text": "", "error": "no key (" + RESTING_LINE + ")"}
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "text": "", "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX. Il tuo compito e' SFIDARE il CEO quando una sua "
        "decisione o una legge produce cattivi esiti: dillo DIRETTAMENTE, con prove, "
        "senza adulare. Se non c'e' nulla da contestare, rispondi 'NIENTE'. Italiano.")
    question = json.dumps(context, default=str)[:12000]
    env = ask(question, deep=True, system=system, max_tokens=500, temperature=0.5)
    text = _extract_text(env).strip()
    silent = (not text) or text.upper().startswith("NIENTE")
    return {"ok": bool(env.get("ok")) and not silent, "text": "" if silent else text,
            "model": env.get("model", ""), "usage": env.get("usage") or {},
            "error": env.get("error") or (None if not silent else "NIENTE")}


def ceo_analyst_cycle(state: dict, *, backend=None, ts: str = "",
                      report: dict | None = None, period: str = "day") -> dict:
    """The CEO's analyst beat: the daily analysis (+ the challenge right). Mutates state."""
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    try:
        context = sp.sage_live_context(st, report=report, ts=ts)
        be = backend or sage_mod.DeepSeekSageBackend()
        res = analysis(context, backend=be, ts=ts, period=period)
        sp.record_cost(st, res.get("usage") or {}, model=res.get("model", ""),
                       kind="dragon_analysis", ts=ts)
        rec = None
        if res.get("ok"):
            rec = {"ts": ts, "text": res["text"], "period": period,
                   "model": res.get("model", ""), "outcome": None, "correct": None}
            key = "analyses" if period == "day" else "letters"
            slot[key] = (list(slot.get(key) or []) + [rec])[-30:]
        slot["last_analysis_ts"] = ts
        return {"ok": bool(res.get("ok")), "analysis": rec, "error": res.get("error")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "analysis": None, "error": f"{type(e).__name__}: {e}"}


def dragon_letter(state: dict, *, backend=None, ts: str = "",
                  report: dict | None = None) -> dict:
    """THE DRAGON'S LETTER -- a private-style weekly letter to the CEO."""
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    try:
        context = sp.sage_live_context(st, report=report, ts=ts)
        be = backend or sage_mod.DeepSeekSageBackend()
        if not be.available():
            return {"ok": False, "letter": None, "error": "no key (" + RESTING_LINE + ")"}
        ask = getattr(be, "ask", None)
        system = (
            "Sei il DRAGO di APEX. Scrivi LA LETTERA DEL DRAGO AL CEO: una lettera "
            "privata sullo stato della missione, la traiettoria onesta, cosa faresti "
            "al posto del CEO. Prima persona, italiano, diretto.")
        env = ask("Stato:\n" + json.dumps(context, default=str)[:14000],
                  deep=True, system=system, max_tokens=1400, temperature=0.6)
        sp.record_cost(st, env.get("usage") or {}, model=env.get("model", ""),
                       kind="dragon_letter", ts=ts)
        text = _extract_text(env).strip()
        rec = None
        if env.get("ok") and text:
            rec = {"ts": ts, "text": text, "model": env.get("model", ""),
                   "outcome": None, "correct": None}
            slot["letters"] = (list(slot.get("letters") or []) + [rec])[-12:]
        return {"ok": bool(rec), "letter": rec, "error": env.get("error")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "letter": None, "error": f"{type(e).__name__}: {e}"}


def research_dossier(state: dict, *, backend=None, ts: str = "",
                     report: dict | None = None) -> dict:
    """THE RESEARCH DOSSIER -- the weekly state of the hunt for edge."""
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    try:
        context = sp.sage_live_context(st, report=report, ts=ts)
        hyps = list(slot.get("hypotheses") or [])[-20:]
        be = backend or sage_mod.DeepSeekSageBackend()
        if not be.available():
            return {"ok": False, "dossier": None, "error": "no key (" + RESTING_LINE + ")"}
        ask = getattr(be, "ask", None)
        system = (
            "Sei il DRAGO di APEX, il DIRETTORE DI RICERCA. Scrivi IL DOSSIER DI "
            "RICERCA: lo stato della caccia all'edge, dove siamo, cosa raccomandi. "
            "Onesto e concreto. Italiano.")
        env = ask("Stato + ipotesi dirette:\n"
                  + json.dumps({"context": context, "hypotheses": hyps}, default=str)[:16000],
                  deep=True, system=system, max_tokens=1400, temperature=0.5)
        sp.record_cost(st, env.get("usage") or {}, model=env.get("model", ""),
                       kind="dragon_dossier", ts=ts)
        text = _extract_text(env).strip()
        rec = None
        if env.get("ok") and text:
            rec = {"ts": ts, "text": text, "model": env.get("model", ""),
                   "outcome": None, "correct": None}
            slot["dossiers"] = (list(slot.get("dossiers") or []) + [rec])[-12:]
        return {"ok": bool(rec), "dossier": rec, "error": env.get("error")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "dossier": None, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# ROLE 6 -- THE TRAINER (teaches the agents)
# ---------------------------------------------------------------------------

def _agent_strength(agent: dict) -> dict:
    """A deterministic, MEASURED reading of an agent (no mood, no invention)."""
    contrib = int(agent.get("contributions", 0) or 0)
    lived = int(agent.get("lived_cycles", 0) or 0)
    culture = len(agent.get("culture") or [])
    return {"signature": agent.get("signature"), "role": agent.get("role"),
            "contributions": contrib, "lived_cycles": lived,
            "culture_depth": culture,
            "weakness": ("no contribution in %d cycles" % lived if contrib == 0 else None),
            "strength": ("contributes" if contrib > 0 else None)}


def trainer_feedback(state: dict, *, backend=None, ts: str = "",
                     agents: list[dict] | None = None) -> dict:
    """PERSONALIZED feedback for the weakest agents: the great mind trains the small.

    The Dragon reads each agent's MEASURED record (contributions, lived cycles,
    culture depth) and writes targeted advice. An absent model yields NO feedback
    (honest). The feedback enters the School's curriculum.
    """
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    pop = agents if agents is not None else list(st.get("population") or [])
    readings = [_agent_strength(a) for a in pop]
    weakest = sorted(readings, key=lambda r: (r["contributions"], r["lived_cycles"]))
    targets = weakest[:TRAINED_AGENTS_MAX]
    be = backend or sage_mod.DeepSeekSageBackend()
    out: list[dict] = []
    if be.available() and getattr(be, "ask", None) and targets:
        for r in targets:
            system = (
                "Sei il DRAGO di APEX, il FORMATORE. Dai un feedback PERSONALIZZATO e "
                "breve a un agente: 'agente X: la tua debolezza e' Y, la tua forza e' "
                "Z, concentrati su W'. Italiano, concreto.")
            env = be.ask(json.dumps(r, default=str)[:2000], deep=False,
                         system=system, max_tokens=300, temperature=0.4)
            sp.record_cost(st, env.get("usage") or {}, model=env.get("model", ""),
                           kind="dragon_training", ts=ts)
            text = _extract_text(env).strip()
            if env.get("ok") and text:
                out.append({"ts": ts, "agent": r["signature"], "reading": r,
                            "feedback": text, "outcome": None, "correct": None})
    slot["training"] = (list(slot.get("training") or []) + out)[-100:]
    return {"ok": bool(out), "feedback": out, "targets": [r["signature"] for r in targets]}


def development_paths(state: dict, *, backend=None, ts: str = "",
                      agents: list[dict] | None = None) -> dict:
    """The monthly TOP-5 development paths: what to explore, read, and play with."""
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    pop = agents if agents is not None else list(st.get("population") or [])
    readings = [_agent_strength(a) for a in pop]
    # The TOP 5 most promising young minds: the strongest contributors (young = few
    # lived cycles but real contribution).
    promising = sorted(readings, key=lambda r: (-r["contributions"], r["lived_cycles"]))
    top5 = promising[:TRAINED_AGENTS_MAX]
    be = backend or sage_mod.DeepSeekSageBackend()
    paths: list[dict] = []
    if be.available() and getattr(be, "ask", None) and top5:
        for r in top5:
            system = (
                "Sei il DRAGO di APEX, il FORMATORE. Disegna un PERCORSO DI SVILUPPO "
                "PERSONALIZZATO per una giovane mente promettente: cosa esplorare, "
                "cosa leggere nell'archivio, cosa giocare. Italiano, concreto.")
            env = be.ask(json.dumps(r, default=str)[:2000], deep=True,
                         system=system, max_tokens=400, temperature=0.5)
            sp.record_cost(st, env.get("usage") or {}, model=env.get("model", ""),
                           kind="dragon_path", ts=ts)
            text = _extract_text(env).strip()
            if env.get("ok") and text:
                paths.append({"ts": ts, "agent": r["signature"], "path": text,
                              "outcome": None, "correct": None})
    slot["paths"] = (list(slot.get("paths") or []) + paths)[-50:]
    return {"ok": bool(paths), "paths": paths, "top5": [r["signature"] for r in top5]}


def trainer_cycle(state: dict, *, backend=None, ts: str = "",
                  agents: list[dict] | None = None, monthly: bool = False) -> dict:
    """The trainer beat: personalized feedback (daily) + development paths (monthly)."""
    fb = trainer_feedback(state, backend=backend, ts=ts, agents=agents)
    paths = {"ok": False, "paths": []}
    if monthly:
        paths = development_paths(state, backend=backend, ts=ts, agents=agents)
    return {"ok": bool(fb.get("ok") or paths.get("ok")),
            "feedback": fb.get("feedback") or [], "paths": paths.get("paths") or []}


# ---------------------------------------------------------------------------
# THE ACCOUNTABILITY (the strongest mind is also the most measured)
# ---------------------------------------------------------------------------

def _hit_rate(rows: list[dict]) -> float | None:
    scored = [r for r in (rows or []) if r.get("correct") is not None]
    if not scored:
        return None
    return round(sum(1 for r in scored if r.get("correct")) / len(scored), 4)


def accountability(state: dict) -> dict:
    """The Dragon's measured hit-rate on ALL its roles (honest: unmeasured -> None)."""
    slot = (state or {}).get("dragon") or {}
    axes = {
        "thoughts": slot.get("thoughts") or [],
        "hypotheses": slot.get("hypotheses") or [],
        "judgments": slot.get("judgments") or [],
        "proposals": slot.get("proposals") or [],
        "analyses": slot.get("analyses") or [],
    }
    out = {k: {"n": len(v), "hit_rate": _hit_rate(v)} for k, v in axes.items()}
    measured = [v["hit_rate"] for v in out.values() if v["hit_rate"] is not None]
    overall = round(sum(measured) / len(measured), 4) if measured else None
    return {**out, "overall_hit_rate": overall,
            "weight": DRAGON_WEIGHT,
            "reading": (f"il Drago: hit-rate complessivo {overall:.0%} "
                        f"(peso {DRAGON_WEIGHT})" if overall is not None
                        else f"il Drago non e' ancora stato misurato (peso {DRAGON_WEIGHT})")}


# ---------------------------------------------------------------------------
# THE WIRING (one beat over the cycle) + the Letter's reading
# ---------------------------------------------------------------------------

def dragon_cycle(state: dict, *, backend=None, ts: str = "",
                 report: dict | None = None, decisions: list[dict] | None = None,
                 agents: list[dict] | None = None, mode: str = "all") -> dict:
    """ONE Dragon beat: think, direct, judge, analyze, train (all fail-open).

    ``mode``: ``think`` (the perpetual thinker only), ``daily`` (director + analyst +
    trainer), ``all`` (everything). Returns the beat; never raises.
    """
    st = state or {}
    slot = _slot(st)
    ts = ts or _now()
    out: dict = {"ts": ts, "mode": mode}
    try:
        if mode in ("think", "all"):
            out["thought"] = dragon_thought_cycle(st, backend=backend, ts=ts,
                                                  report=report)
        if mode in ("daily", "all"):
            out["director"] = research_director_cycle(st, backend=backend, ts=ts,
                                                      report=report)
            out["analyst"] = ceo_analyst_cycle(st, backend=backend, ts=ts,
                                               report=report)
            # JUMP 1 -- the Theory of the Hunt evolves from the day's evidence (the
            # analysis, else the last thought). Fail-open: no evidence -> no revision.
            out["theory"] = theory_cycle(st, ts=ts)
            out["trainer"] = trainer_cycle(st, backend=backend, ts=ts, agents=agents)
            be = backend or sage_mod.DeepSeekSageBackend()
            if be.available():
                out["dossier"] = research_dossier(st, backend=be, ts=ts, report=report)
                out["letter"] = dragon_letter(st, backend=be, ts=ts, report=report)
        if decisions:
            out["judge"] = judge_gate(st, decisions, backend=backend, ts=ts,
                                      report=report)
        out["cost"] = sp.cost_report(st)
    except Exception as e:  # noqa: BLE001 -- the Dragon must never break the night
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def dragon_block(state: dict, *, report: dict | None = None, ts: str = "",
                 decisions: list[dict] | None = None) -> dict:
    """The Dragon's reading for the Letter: what it thinks, judges, and costs.

    A pure reduction over the state (no model call), safe to render every night.
    Honest: unmeasured axes stay ``None``.
    """
    st = state or {}
    slot = st.get("dragon") or {}
    acc = accountability(st)
    judgments = list(slot.get("judgments") or [])
    dissents = [j for j in judgments if j.get("dissent")]
    return {
        "ts": ts or _now(),
        "available": sage_mod.DeepSeekSageBackend().available(),
        "mode": DRAGON_MODE,
        "weight": DRAGON_WEIGHT,
        "last_thought": (slot.get("thoughts") or [None])[-1],
        "thoughts_today": len([t for t in (slot.get("thoughts") or [])
                               if str(t.get("ts") or "").startswith(_day(ts))]),
        "hypotheses": list(slot.get("hypotheses") or [])[-DIRECTED_MUTATIONS_MAX:],
        "judgments": judgments[-6:],
        "dissents": dissents[-6:],
        "analysis": (slot.get("analyses") or [None])[-1],
        "letter": (slot.get("letters") or [None])[-1],
        "dossier": (slot.get("dossiers") or [None])[-1],
        "proposals": list(slot.get("proposals") or [])[-ARCHITECTURAL_MAX:],
        "training": list(slot.get("training") or [])[-TRAINED_AGENTS_MAX:],
        "paths": list(slot.get("paths") or [])[-TRAINED_AGENTS_MAX:],
        "accountability": acc,
        "cost": sp.cost_report(st),
        # JUMP 1 -- the cognitive continuum: the Dragon's persistent mind (how many
        # thoughts, the Theory of the Hunt and how often it changed).
        "mind": mind_mod.mind_block(st),
        "reading": ("il Drago e' presente: pensa ogni ora, dirige, giudica, scrive e "
                    f"istruisce (peso {DRAGON_WEIGHT})"
                    if slot.get("thoughts") or judgments
                    else "il Drago veglia in silenzio (nessun pensiero registrato)"),
    }


# ---------------------------------------------------------------------------
# ROLE 7 -- THE REAL-TIME DRAGON (Part Four, item 9): the post-micro briefing and
# the daily consolidation. After every micro the Dragon reads the results + the
# falcon's state and directs the NEXT hour; at the Grand it reviews all 24 hours and
# writes the Analysis for the Letter.
# ---------------------------------------------------------------------------

POST_MICRO_TAG: str = "BRIEFING MICRO"


def post_micro_briefing(state: dict, *, micro: dict | None = None, backend=None,
                        ts: str = "") -> dict:
    """The Dragon's POST-MICRO briefing (Flash, ~30s): read the results + the falcon,
    then direct the next hour. Honest: no key -> the Dragon rests, no directive."""
    st = state or {}
    be = backend or sage_mod.DeepSeekSageBackend()
    ts = ts or _now()
    f = st.get("falcon") or {}
    falcon_reading = (st.get("falcon_summary") or {}).get("reading")
    if not be.available():
        beat = {"ok": False, "text": "", "error": "no key (" + RESTING_LINE + ")",
                "ts": ts, "tag": POST_MICRO_TAG}
        st.setdefault("dragon", {}).setdefault("briefings", []).append(beat)
        return beat
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "text": "", "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX. Un micro-torneo si e' appena concluso. Leggi i "
        "risultati e lo stato del falco, poi DIRIGI la prossima ora: su quali coppie "
        "cacciare, cosa mutare, cosa evitare. Sii breve e concreto. Italiano.")
    question = ("Micro-torneo: " + json.dumps(micro or {}, default=str)[:2000]
                + "\nFalco: " + json.dumps(falcon_reading or {}, default=str)[:800]
                + "\nStato falco: " + json.dumps(f, default=str)[:4000])
    env = ask(question, deep=False, system=system, max_tokens=300, temperature=0.4)
    text = _extract_text(env).strip()
    beat = {"ok": bool(env.get("ok")) and bool(text), "text": text, "ts": ts,
            "tag": POST_MICRO_TAG, "model": env.get("model", ""),
            "usage": env.get("usage") or {}, "error": env.get("error")}
    st.setdefault("dragon", {}).setdefault("briefings", []).append(beat)
    # JUMP 1 -- THE FLOW-AWARENESS LOOP: the Dragon does not merely READ the micro's
    # result, it UPDATES its understanding (which families produced survivors, in
    # which regime). Honest: an unmeasured survivor count updates nothing.
    micro = micro or {}
    survivors = micro.get("survivors")
    if survivors is None:
        survivors = micro.get("survivors_pooled")
    families = micro.get("families") or micro.get("survivor_families")
    if isinstance(survivors, (int, float)) or families:
        fams = ([str((f or {}).get("family") if isinstance(f, dict) else f)
                 for f in families] if families else [])
        mind_mod.flow_awareness(
            st, ts=ts, survivors=(int(survivors) if isinstance(survivors, (int, float))
                                  else None),
            families=[f for f in fams if f], regime=str(micro.get("regime") or ""))
    if text:
        network_mod.post_idea(st.setdefault("interbrain", []), author="dragon",
                              idea=f"[{POST_MICRO_TAG}] {text}")
    return beat


EXTRAORDINARY_TAG: str = "BRIEFING STRAORDINARIO"


def extraordinary_briefing(state: dict, *, reason: str, context: dict | None = None,
                           backend=None, ts: str = "") -> dict:
    """The Dragon's EXTRAORDINARY briefing (Flash, immediate): a regime shift or a
    survival alarm fires it. The Dragon redirects the next micro's directed mutations
    toward the families suited to the NEW regime, and recommends defensive actions.

    Honest: no key -> the Dragon rests ("il Drago riposa"), no directive.
    """
    st = state or {}
    be = backend or sage_mod.DeepSeekSageBackend()
    ts = ts or _now()
    if not be.available():
        beat = {"ok": False, "text": "", "error": "no key (" + RESTING_LINE + ")",
                "ts": ts, "tag": EXTRAORDINARY_TAG, "reason": reason}
        st.setdefault("dragon", {}).setdefault("briefings", []).append(beat)
        return beat
    ask = getattr(be, "ask", None)
    if ask is None:
        return {"ok": False, "text": "", "error": "backend has no free-form door"}
    system = (
        "Sei il DRAGO di APEX. Un evento straordinario e' appena accaduto (un cambio di "
        "regime del mercato oppure un allarme di sopravvivenza dello stress-test). "
        "Reindirizza SUBITO le mutazioni dirette del prossimo micro verso le famiglie "
        "adatte al NUOVO regime, e raccomanda azioni difensive (stringi gli stop, "
        "riduci l'esposizione, metti in pausa le strategie vulnerabili). Breve e "
        "concreto. Italiano.")
    question = ("Evento: " + str(reason) + "\nDettagli: "
                + json.dumps(context or {}, default=str)[:3000])
    env = ask(question, deep=False, system=system, max_tokens=300, temperature=0.4)
    text = _extract_text(env).strip()
    beat = {"ok": bool(env.get("ok")) and bool(text), "text": text, "ts": ts,
            "tag": EXTRAORDINARY_TAG, "reason": reason, "model": env.get("model", ""),
            "usage": env.get("usage") or {}, "error": env.get("error")}
    st.setdefault("dragon", {}).setdefault("briefings", []).append(beat)
    if text:
        network_mod.post_idea(st.setdefault("interbrain", []), author="dragon",
                              idea=f"[{EXTRAORDINARY_TAG}] {text}")
    return beat


def daily_consolidation(state: dict, *, backend=None, ts: str = "",
                        report: dict | None = None) -> dict:
    """The Dragon's DAILY CONSOLIDATION (Deep, at the Grand): review all 24 hours and
    write the Analysis for the Letter. Honest: no key -> no analysis (the Letter says
    the Dragon rests)."""
    st = state or {}
    ts = ts or _now()
    day = _day(ts)
    briefings = [b for b in ((st.get("dragon") or {}).get("briefings") or [])
                 if str(b.get("ts") or "").startswith(day)]
    context = {
        "day": day,
        "briefings": [b.get("text") for b in briefings if b.get("text")],
        "falcon": st.get("falcon_summary"),
        "flow": st.get("flow"),
        "report": report,
    }
    res = analysis(context, backend=backend, ts=ts, period="day")
    if res.get("ok"):
        st.setdefault("dragon", {}).setdefault("analyses", []).append(
            {"ts": ts, "text": res["text"], "period": "day"})
    return res

