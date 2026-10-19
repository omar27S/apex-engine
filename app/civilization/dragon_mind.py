"""THE COGNITIVE CONTINUUM -- JUMP 1: the Dragon never resets.

Every Dragon consultation used to rebuild context from zero: the Dragon "woke up",
answered, "slept". There was no continuous consciousness -- no memory of what it said
yesterday, no awareness of whether its advice worked. This module gives the Dragon a
CONTINUOUS mind:

  * THE PERSISTENT CONTEXT -- the Dragon's mind lives in a rolling buffer
    (``state['dragon_mind']``): every thought and observation is APPENDED, never reset.
    The buffer is bounded (a rolling window, not infinite memory) but it is
    CONTINUOUS -- the Dragon wakes with its memory intact;
  * THE REACTION LOOP -- the Dragon sees its OWN history ("I said X yesterday, the
    result was Y, I now believe Z"): a later consultation reacts to what it said
    last time and what actually happened;
  * THE FLOW-AWARENESS LOOP -- after a micro-tournament the Dragon updates its
    UNDERSTANDING ("this mutation direction produced these survivors -- my model of
    what works in this regime has shifted"), feeding a rolling THEORY OF THE HUNT;
  * THE THEORY OF THE HUNT -- the Dragon's current, evolving understanding of where
    edge exists and why, written and VERSIONED. When the theory changes the reason is
    noted and the old theory is archived: the intellectual autobiography of the
    strongest mind.

Honesty is binding. An empty mind reports an empty mind (never an invented thought); a
theory with no evidence carries the reason it changed and nothing fabricated. Pure at
import (Scar #6): every reduction takes the state + the timestamp it is given; it never
reads the wall clock and never performs I/O.
"""

from __future__ import annotations

__all__ = [
    "MIND_VERSION",
    "CONTEXT_WINDOW",
    "THEORY_TAG",
    "mind",
    "context_window",
    "observe",
    "record_outcome",
    "theory",
    "revise_theory",
    "flow_awareness",
    "continuity_prompt",
    "mind_block",
]

MIND_VERSION: int = 1

# The rolling context window: the last N thoughts/observations the Dragon keeps in
# view. Bounded (cost honesty) but continuous -- the window slides, it never resets.
CONTEXT_WINDOW: int = 20

# The tag on a theory-of-the-hunt entry (the intellectual autobiography's spine).
THEORY_TAG: str = "TEORIA DELLA CACCIA"


def mind(state: dict) -> dict:
    """The Dragon's persistent mind (created empty on first access, never reset)."""
    st = state if state is not None else {}
    return st.setdefault("dragon_mind", {
        "version": MIND_VERSION,
        "thoughts": [],
        "observations": [],
        "theory": None,
        "theory_history": [],
    })


def context_window(state: dict, *, n: int = CONTEXT_WINDOW) -> list[dict]:
    """The last ``n`` thoughts the Dragon holds in view (the rolling window).

    Honest: an empty mind returns ``[]`` (the Dragon has not thought yet), never a
    placeholder. The window is what is SERIALIZED between consultations, so the
    Dragon sleeps between calls but wakes with this context intact.
    """
    rows = list((mind(state).get("thoughts") or []))
    return rows[-max(0, int(n)):] if n else []


def observe(state: dict, *, ts: str, kind: str, text: str,
            source: str = "") -> dict:
    """Append one thought/observation to the persistent mind (the continuum grows).

    ``kind`` is "thought" (the Dragon's own words) or "observation" (something it
    noticed -- a flow result, a regime change). The buffer is bounded to the rolling
    window times a small factor, so it is continuous without growing forever. Honest:
    blank text records nothing.
    """
    body = str(text or "").strip()
    if not body:
        return {}
    m = mind(state)
    row = {"ts": str(ts), "kind": str(kind), "text": body, "source": str(source),
           "outcome": None}
    if kind == "thought":
        m["thoughts"].append(row)
        del m["thoughts"][:-(CONTEXT_WINDOW * 5)]
    else:
        m["observations"].append(row)
        del m["observations"][:-(CONTEXT_WINDOW * 5)]
    return row


def record_outcome(state: dict, *, ts: str, outcome: str,
                   text: str = "") -> dict:
    """Record what HAPPENED after the Dragon's last thought (the reaction loop).

    This is the self-awareness: the next consultation reads "I said X, the result was
    Y". Honest: with no prior thought there is nothing to react to (nothing recorded).
    """
    m = mind(state)
    thoughts = list(m.get("thoughts") or [])
    if not thoughts:
        return {}
    last = thoughts[-1]
    last["outcome"] = str(outcome or "")
    last["outcome_ts"] = str(ts)
    if text:
        last["outcome_text"] = str(text)
    return last


def theory(state: dict) -> dict | None:
    """The Dragon's current THEORY OF THE HUNT (its evolving model), or ``None``."""
    return mind(state).get("theory")


def revise_theory(state: dict, *, thesis: str, reason: str, ts: str = "",
                  evidence: dict | None = None) -> dict:
    """Revise the Theory of the Hunt; archive the old one WITH the reason.

    The Dragon's understanding evolves: a new thesis supersedes the old, the version
    increments, and the OLD theory is archived (with the reason it changed) -- the
    intellectual autobiography. Honest: an unchanged thesis (same text) is a no-op
    (``changed=False``), and a blank thesis is refused (never a fabricated theory).
    """
    body = str(thesis or "").strip()
    if not body:
        return {"changed": False, "reason": "teoria vuota (rifiutata)",
                "theory": theory(state)}
    m = mind(state)
    old = m.get("theory")
    if old and str(old.get("thesis", "")).strip() == body:
        return {"changed": False, "reason": "teoria invariata", "theory": old}
    new = {
        "version": int((old or {}).get("version", 0)) + 1,
        "tag": THEORY_TAG,
        "thesis": body,
        "reason": str(reason or ""),
        "ts": str(ts),
        "evidence": dict(evidence or {}),
    }
    if old:
        archived = dict(old)
        archived["superseded_by_version"] = new["version"]
        archived["superseded_reason"] = str(reason or "")
        archived["superseded_ts"] = str(ts)
        m.setdefault("theory_history", []).append(archived)
        del m["theory_history"][:-100]
    m["theory"] = new
    return {"changed": True, "old": old, "theory": new,
            "reading": (f"teoria della caccia v{new['version']}: {body}"
                        + (f" (perche': {reason})" if reason else ""))}


def flow_awareness(state: dict, *, ts: str, survivors: int | None,
                   families: list[str] | None = None, regime: str = "",
                   note: str = "") -> dict:
    """THE FLOW-AWARENESS LOOP: update the Dragon's model after a micro-tournament.

    The Dragon does not merely read a result -- it updates its UNDERSTANDING: which
    mutation directions produced survivors, and what that says about where edge lives
    in the current regime. Honest: an unmeasured survivor count updates nothing
    (never a fabricated learning).
    """
    fams = sorted({str(f) for f in (families or []) if str(f)})
    if survivors is None and not note:
        return {"updated": False, "reading": "nessun risultato misurato da apprendere"}
    text = (f"flusso: {survivors if survivors is not None else '--'} sopravvissuti"
            + (f" ({', '.join(fams)})" if fams else "")
            + (f" nel regime {regime}" if regime else "")
            + (f" -- {note}" if note else ""))
    observe(state, ts=ts, kind="observation", text=text, source="flow")
    return {"updated": True, "survivors": survivors, "families": fams,
            "regime": regime, "reading": text}


def continuity_prompt(state: dict, *, n: int = CONTEXT_WINDOW) -> str:
    """The Dragon's OWN history, rendered for the next consultation.

    "I said X yesterday, the result was Y, I now believe Z" -- self-aware continuity.
    Honest: an empty mind returns an empty string (no invented history).
    """
    window = context_window(state, n=n)
    th = theory(state)
    if not window and not th:
        return ""
    lines: list[str] = []
    if th:
        lines.append(f"La tua TEORIA DELLA CACCIA (v{th.get('version')}): "
                     f"{th.get('thesis')}")
        if th.get("reason"):
            lines.append(f"  (l'ultima volta l'hai cambiata perche': {th.get('reason')})")
    if window:
        lines.append("I tuoi ultimi pensieri e cio' che ne e' seguito:")
        for row in window:
            line = f"  - [{row.get('ts')}] {row.get('text')}"
            if row.get("outcome") is not None:
                line += f"  -> esito: {row.get('outcome')}"
            lines.append(line)
    return "\n".join(lines)


def mind_block(state: dict, *, n: int = CONTEXT_WINDOW) -> dict:
    """The Dragon-mind block for the artifact + the Letter (honest, bounded).

    Renders the continuity: how many thoughts the mind holds, the rolling window's
    most recent entries, the current Theory of the Hunt and how many times it changed.
    Honest: an empty mind reports ``measured=False`` (the Dragon has not thought yet).
    """
    m = mind(state)
    window = context_window(state, n=n)
    th = theory(state)
    history = list(m.get("theory_history") or [])
    return {
        "version": MIND_VERSION,
        "n_thoughts": len(m.get("thoughts") or []),
        "n_observations": len(m.get("observations") or []),
        "window": window[-5:],
        "theory": th,
        "theory_revisions": len(history),
        "continuity": bool(window or th),
        "measured": bool(window or th),
        "reading": (
            f"mente del Drago: {len(m.get('thoughts') or [])} pensieri, "
            f"{len(history)} revisioni della teoria"
            + (f"; teoria v{th['version']}" if th else " (nessuna teoria ancora)")
            if (window or th) else "mente del Drago: nessun pensiero ancora"),
    }
