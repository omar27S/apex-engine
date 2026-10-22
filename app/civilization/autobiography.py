"""THE AUTOBIOGRAPHICAL MEMORY -- JUMP 5: the system knows WHO IT IS.

The civilization had archives (ledgers, photographs, deaths) but no NARRATIVE of
itself -- it could not tell its own story. This module gives it one:

  * THE CHAPTER WRITER -- at every Grand, the Deep Dragon writes ONE CHAPTER of the
    civilization's autobiography: what happened today, what was learned, what changed
    in who we are -- narrative form, not a data dump. The chapter carries the day's
    significant events (regime shifts, discoveries, notable deaths), the emotional arc
    (the collective mood's trajectory), the lessons, and what the civilization now
    believes that it did not believe yesterday. It is archived to
    ``autobiography/chapter_NN.md`` (and the state), the living story of the system;
  * THE AUTOBIOGRAPHICAL CONTEXT -- before major decisions the Council consults the
    RELEVANT chapters ("when we last faced a similar situation, chapter 12, we
    learned that..."). The Dragon's Theory of the Hunt references chapters, so the
    intellectual narrative connects with the experiential one;
  * THE IDENTITY EVOLUTION -- the self-model gains narrative depth: not just "what we
    are" but "how we became this" -- the trajectory, the turning points, the lessons
    that shaped us. Monthly, the chapters are distilled into a GENERATION SUMMARY
    (the chapters of one generation compressed to their essence) feeding the School.

Honesty is binding. A chapter with no measured events says so (never an invented
day); a lesson with no evidence is not written; an identity with no trajectory reports
the trajectory as unmeasured. Pure at import (Scar #6): the caller supplies the
timestamp and the day's real events; this module never reads the wall clock.
"""

from __future__ import annotations

import re

__all__ = [
    "AUTOBIOGRAPHY_VERSION",
    "SIGNIFICANT_KINDS",
    "autobiography",
    "chapters",
    "chapter_title",
    "compose_chapter",
    "write_chapter",
    "relevant_chapters",
    "identity_narrative",
    "distill_generation",
    "autobiography_block",
]

AUTOBIOGRAPHY_VERSION: int = 1

# The event kinds that earn a place in the day's chapter (the significant ones).
SIGNIFICANT_KINDS: tuple[str, ...] = (
    "regime_shift", "discovery", "death", "coronation", "treaty",
    "siren", "birth", "milestone",
)


def autobiography(state: dict) -> dict:
    """The living autobiography (created empty on first access, never reset)."""
    st = state if state is not None else {}
    return st.setdefault("autobiography", {
        "version": AUTOBIOGRAPHY_VERSION,
        "chapters": [],
        "generation_summaries": [],
    })


def chapters(state: dict) -> list[dict]:
    """Every chapter written so far (the story so far)."""
    return list(autobiography(state).get("chapters") or [])


def chapter_title(index: int, *, mood: str = "") -> str:
    """The chapter's title -- numbered and named by the day's dominant mood."""
    name = str(mood or "").strip()
    return f"CAPITOLO {int(index):02d}" + (f" -- {name}" if name else "")


def _significant(events: list[dict]) -> list[dict]:
    """The day's SIGNIFICANT events, in order (an unsignificant day yields none).

    R142 — THE DEEDS: a kind that starts with ``"deed:"`` is one of the kings'
    spontaneous acts, recorded in the civilization's diary (the receipt is the
    diary row itself). A deed is ALWAYS chapter-worthy: the book does not invent
    days, it reports the ones the civilization actually LIVED. Everything else
    still needs its kind in ``SIGNIFICANT_KINDS``.
    """
    out: list[dict] = []
    for e in events or []:
        kind = str((e or {}).get("kind", "")).strip()
        if kind in SIGNIFICANT_KINDS or kind.startswith("deed:"):
            out.append(dict(e))
    return out


def compose_chapter(*, index: int, date: str, events: list[dict],
                    mood: str = "", lessons: list[str] | None = None,
                    beliefs_now: list[str] | None = None,
                    beliefs_before: list[str] | None = None,
                    narrative: str = "") -> dict:
    """Compose ONE chapter from the day's measured events (narrative, not a dump).

    ``narrative`` (the Deep Dragon's prose) is used when present; otherwise a
    deterministic narrative is composed from the events, the mood, the lessons and
    the belief delta. Honest: a day with no significant event is written as such --
    "un giorno quieto" -- never padded with invented drama.
    """
    sig = _significant(events)
    lessons = [str(x) for x in (lessons or []) if str(x).strip()]
    now = [str(x) for x in (beliefs_now or []) if str(x).strip()]
    before = [str(x) for x in (beliefs_before or []) if str(x).strip()]
    new_beliefs = [b for b in now if b not in before]
    if not narrative:
        parts: list[str] = []
        if sig:
            parts.append("Oggi la civilta' ha vissuto: "
                         + "; ".join(str(e.get("reading") or e.get("kind"))
                                     for e in sig[:6]) + ".")
        else:
            parts.append("Un giorno quieto: nessun evento significativo misurato.")
        if mood:
            parts.append(f"L'umore collettivo: {mood}.")
        if lessons:
            parts.append("Cio' che abbiamo imparato: " + "; ".join(lessons[:4]) + ".")
        if new_beliefs:
            parts.append("Ora crediamo cio' che ieri non credevamo: "
                         + "; ".join(new_beliefs[:4]) + ".")
        narrative = " ".join(parts)
    return {
        "index": int(index),
        "date": str(date),
        "title": chapter_title(index, mood=mood),
        "events": sig,
        "mood": str(mood),
        "lessons": lessons,
        "beliefs_now": now,
        "new_beliefs": new_beliefs,
        "narrative": narrative,
        "measured": bool(sig or lessons or mood or narrative),
    }


def write_chapter(state: dict, *, date: str, events: list[dict] | None = None,
                  mood: str = "", lessons: list[str] | None = None,
                  beliefs_now: list[str] | None = None,
                  beliefs_before: list[str] | None = None,
                  narrative: str = "", ts: str = "") -> dict:
    """Append ONE chapter to the autobiography (the day's story, archived).

    The chapter index is the next in sequence. Idempotent per date: a second write for
    the same date REPLACES the day's chapter (a re-run never doubles the story).
    Returns the chapter (with ``written`` and the honest ``reading``).
    """
    auto = autobiography(state)
    rows = auto["chapters"]
    existing = next((c for c in rows if str(c.get("date")) == str(date)), None)
    index = int(existing["index"]) if existing else len(rows) + 1
    ch = compose_chapter(index=index, date=date, events=list(events or []),
                         mood=mood, lessons=lessons, beliefs_now=beliefs_now,
                         beliefs_before=beliefs_before, narrative=narrative)
    ch["ts"] = str(ts)
    if existing:
        rows[rows.index(existing)] = ch
    else:
        rows.append(ch)
    del rows[:-400]
    return {**ch, "written": True,
            "reading": (f"{ch['title']}: {ch['narrative'][:160]}"
                        if ch["narrative"] else f"{ch['title']}: (nessuna parola)")}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", str(text).lower()) if len(t) > 2}


def relevant_chapters(state: dict, *, situation: str = "", regime: str = "",
                      n: int = 3) -> list[dict]:
    """The chapters most relevant to a situation (the autobiographical context).

    Relevance is measured by token overlap between the situation/regime and each
    chapter's narrative + events. Honest: with no chapters (or no situation) it
    returns ``[]`` -- the Council then decides without a precedent, and says so.
    """
    rows = chapters(state)
    if not rows:
        return []
    q = _tokens(situation) | _tokens(regime)
    if not q:
        return []
    scored: list[tuple[int, dict]] = []
    for c in rows:
        blob = " ".join([str(c.get("narrative", "")), str(c.get("mood", "")),
                         " ".join(str(e.get("reading") or e.get("kind")
                                   for e in (c.get("events") or [])))])
        overlap = len(q & _tokens(blob))
        if overlap:
            scored.append((overlap, c))
    scored.sort(key=lambda t: (-t[0], -int(t[1].get("index", 0))))
    return [c for _, c in scored[:max(0, int(n))]]


def identity_narrative(state: dict, *, n: int = 8) -> dict:
    """THE IDENTITY EVOLUTION: how we became this (the trajectory, the turning points).

    Reads the chapters into a trajectory -- the turning points (chapters with
    significant events), the recurring lessons, and the beliefs that were adopted
    along the way. Honest: with no chapters the trajectory is unmeasured.
    """
    rows = chapters(state)
    if not rows:
        return {"measured": False, "trajectory": [], "turning_points": [],
                "lessons": [], "beliefs_adopted": [],
                "reading": "traiettoria non misurata (nessun capitolo scritto)"}
    turning = [{"index": c["index"], "title": c.get("title"),
                "event": str((c.get("events") or [{}])[0].get("reading", ""))}
               for c in rows if c.get("events")]
    lessons: list[str] = []
    for c in rows:
        for lesson in (c.get("lessons") or []):
            if lesson not in lessons:
                lessons.append(lesson)
    adopted: list[str] = []
    for c in rows:
        for b in (c.get("new_beliefs") or []):
            if b not in adopted:
                adopted.append(b)
    return {
        "measured": True,
        "chapters": len(rows),
        "trajectory": [{"index": c["index"], "title": c.get("title"),
                        "mood": c.get("mood")} for c in rows[-max(0, int(n)):]],
        "turning_points": turning[-max(0, int(n)):],
        "lessons": lessons,
        "beliefs_adopted": adopted,
        "reading": (f"come siamo diventati questo: {len(rows)} capitoli, "
                    f"{len(turning)} punti di svolta, {len(adopted)} convinzioni nuove"),
    }


def distill_generation(state: dict, *, label: str = "", n: int = 30,
                       ts: str = "") -> dict:
    """Distil the last generation of chapters into a GENERATION SUMMARY (monthly).

    Compresses the chapters' essence -- the arc, the recurring lessons, the beliefs
    adopted -- into one summary feeding the School's curriculum. Honest: with no
    chapters the summary is unmeasured (never invented).

    R142 — THE ANTI-REPRINT GUARD: the album never photographs the same page twice.
    Only chapters with an index BEYOND the last summary's reach enter the next
    distillation; a call with no fresh chapter is an honest ``distilled: False``
    and NOTHING is appended (the old law re-printed the same chapter into summary
    after summary -- ten identical photographs of one quiet day, and the School
    read one page forever).
    """
    auto = autobiography(state)
    summaries = auto["generation_summaries"]
    rows = chapters(state)[-max(1, int(n)):]
    if not rows:
        return {"distilled": False, "reading": "nessun capitolo da distillare"}
    last_idx = max((max((int(c) for c in (s.get("chapters") or []) if isinstance(c, int)),
                        default=0)
                      for s in summaries), default=0)
    fresh = [c for c in rows if int(c.get("index") or 0) > last_idx]
    if not fresh:
        return {"distilled": False,
                "reading": "nessun capitolo nuovo: l'album non ristampa la stessa foto"}
    lessons: list[str] = []
    for c in fresh:
        for lesson in (c.get("lessons") or []):
            if lesson not in lessons:
                lessons.append(lesson)
    adopted: list[str] = []
    for c in fresh:
        for b in (c.get("new_beliefs") or []):
            if b not in adopted:
                adopted.append(b)
    moods = [str(c.get("mood")) for c in fresh if c.get("mood")]
    summary = {
        "label": str(label) or f"{fresh[0].get('date')}..{fresh[-1].get('date')}",
        "chapters": [c["index"] for c in fresh],
        "new_chapters": [c["index"] for c in fresh],
        "n_chapters": len(fresh),
        "lessons": lessons,
        "beliefs_adopted": adopted,
        "moods": moods,
        "ts": str(ts),
        "reading": (f"una generazione in essenza: {len(fresh)} capitolo/i nuovo/i, "
                    f"{len(lessons)} lezioni, {len(adopted)} convinzioni nuove"),
    }
    summaries.append(summary)
    del summaries[:-24]
    return {**summary, "distilled": True}


def autobiography_block(state: dict) -> dict:
    """The autobiography block for the artifact + the Letter (honest, bounded).

    Renders the latest chapter's summary, the identity trajectory and the count of
    chapters. Honest: with no chapters the block reports ``measured=False``.
    """
    rows = chapters(state)
    if not rows:
        return {"measured": False, "chapters": 0, "latest": None,
                "reading": "autobiografia: nessun capitolo ancora"}
    latest = rows[-1]
    ident = identity_narrative(state)
    return {
        "measured": True,
        "chapters": len(rows),
        "latest": latest,
        "turning_points": ident.get("turning_points") or [],
        "lessons": ident.get("lessons") or [],
        "reading": (f"{latest.get('title')}: "
                    f"{str(latest.get('narrative', ''))[:200]}"),
    }
