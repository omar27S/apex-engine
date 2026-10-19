"""LAW OF LIFE 3 — THE MONSTROUS NETWORK (the web between minds).

The agents are connected CONTINUOUSLY: a message bus where every agent can talk
to every other, always. Discoveries broadcast instantly; questions asked openly;
help offered spontaneously. The INTERBRAIN is the shared working memory — the
current hypotheses, the open questions, the half-formed ideas. Any agent can pick
up another's half-thought and COMPLETE it; ideas have multiple parents. The
conversations are recorded: the raw material of the civilization's culture.

Pure at import (Scar #6): the bus and the interbrain are DATA the caller owns;
the functions here are reductions. Nothing touches disk.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "KINDS",
    "Message",
    "broadcast",
    "ask",
    "answer",
    "offer_help",
    "discover",
    "post_idea",
    "complete_idea",
    "network_digest",
    "record_exchange",
    "deliberation",
    "conversation_metrics",
    "echo_alarm",
    "devils_advocate",
]

# The kinds of traffic the bus carries. ``discovery`` is broadcast to all;
# ``question`` awaits an answer; ``help`` is spontaneous aid; ``idea`` enters the
# interbrain; ``decision`` announces a Council ruling.
KINDS: tuple[str, ...] = (
    "discovery", "question", "answer", "help", "idea", "decision", "dream",
)


class Message(dict):
    """One utterance on the bus (a plain dict, stamped and immutable in spirit)."""

    __slots__ = ()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(bus: list[dict], *, sender: str, kind: str, body: str,
          to: str = "*", ts: str = "") -> Message:
    if kind not in KINDS:
        raise ValueError(f"unknown message kind {kind!r}; known: {KINDS}")
    m = Message({"ts": ts or _stamp(), "from": sender, "to": to, "kind": kind,
                 "body": body})
    bus.append(m)
    return m


def broadcast(bus: list[dict], *, sender: str, body: str, ts: str = "") -> Message:
    """Announce a discovery to the whole civilization (to ``*``)."""
    return _emit(bus, sender=sender, kind="discovery", body=body, to="*", ts=ts)


def ask(bus: list[dict], *, sender: str, body: str, to: str = "*",
        ts: str = "", mode: str = "BELIEVE") -> Message:
    """Ask a question openly (awaits an answer on the same thread)."""
    m = _emit(bus, sender=sender, kind="question", body=body, to=to, ts=ts)
    m["mode"] = str(mode)
    return m


def answer(bus: list[dict], *, sender: str, body: str, to: str = "*",
           ts: str = "", re: int | None = None, mode: str = "KNOW") -> Message:
    """ANSWER an open question (revives the dead question->answer channel).

    ``re`` is the index of the question in the bus being answered; when given, the
    question is marked answered so the UNANSWERED list shrinks. A question the
    civilization ignores is a thought it abandoned — this is the pipe that closes it.
    """
    m = _emit(bus, sender=sender, kind="answer", body=body, to=to, ts=ts)
    m["mode"] = str(mode)
    if re is not None and 0 <= int(re) < len(bus):
        m["re"] = int(re)
        bus[int(re)]["answered"] = True
        bus[int(re)]["answered_by"] = sender
    return m


def offer_help(bus: list[dict], *, sender: str, body: str, to: str = "*",
               ts: str = "") -> Message:
    """Offer help spontaneously."""
    return _emit(bus, sender=sender, kind="help", body=body, to=to, ts=ts)


def discover(bus: list[dict], *, sender: str, body: str, ts: str = "") -> Message:
    """Alias of :func:`broadcast` for a discovered fact (readability at call sites)."""
    return broadcast(bus, sender=sender, body=body, ts=ts)


def post_idea(interbrain: list[dict], *, author: str, idea: str,
              parents: list[str] | None = None, ts: str = "") -> dict:
    """Put a half-formed idea into the shared working memory (the interbrain).

    ``parents`` names the ideas this one builds on — an idea may have MULTIPLE
    parents (it can be completed from any agent's half-thought).
    """
    node = {
        "ts": ts or _stamp(),
        "author": author,
        "idea": idea,
        "parents": list(parents or []),
        "status": "open",
        "completed_by": None,
    }
    interbrain.append(node)
    return node


def complete_idea(interbrain: list[dict], *, index: int, by: str,
                  note: str = "") -> dict:
    """Another agent COMPLETES an open idea (ideas have multiple parents)."""
    node = interbrain[index]
    if node.get("status") == "complete":
        raise ValueError(f"idea {index} is already complete (by {node['completed_by']})")
    node["status"] = "complete"
    node["completed_by"] = by
    node["completion"] = note
    return node


def network_digest(bus: list[dict], interbrain: list[dict]) -> dict:
    """A compact reading of the network: traffic by kind, open ideas, helpers."""
    by_kind: dict[str, int] = {}
    for m in bus:
        by_kind[m.get("kind", "?")] = by_kind.get(m.get("kind", "?"), 0) + 1
    open_ideas = [n for n in interbrain if n.get("status") != "complete"]
    return {
        "messages": len(bus),
        "by_kind": by_kind,
        "ideas": len(interbrain),
        "open_ideas": len(open_ideas),
        "multi_parent_ideas": sum(1 for n in interbrain if len(n.get("parents", [])) > 1),
        "reading": (f"{len(bus)} message(s) on the bus ({by_kind}); "
                    f"{len(interbrain)} idea(s) in the interbrain, "
                    f"{len(open_ideas)} open"),
    }


def record_exchange(bus: list[dict], *, sender: str, kind: str, body: str,
                    to: str = "*") -> None:
    """Convenience: append a pre-typed exchange (used by the cycle/minutes)."""
    _emit(bus, sender=sender, kind=kind, body=body, to=to)


# --- D2 — THE DELIBERATION CEREMONY ----------------------------------------

def deliberation(*, question: str, voices: list[dict] | None = None,
                 tension: dict | None = None, resolution: str = "",
                 minorities: list[dict] | None = None, ts: str = "") -> dict:
    """A STRUCTURED deliberation record: the Council thinks OUT LOUD.

    The five-part ceremony:
      * OPENING — the question, stated precisely;
      * THE VOICES — each mind's position WITH its epistemic mode and context packet;
      * THE TENSION — the real disagreement, NAMED (not smoothed over);
      * THE RESOLUTION — how the tension was resolved and WHY;
      * THE MINORITIES — dissenting positions PRESERVED (the Cassandra Protocol:
        a dissent that later proves right is surfaced and its author credited).

    Honest: an empty voices list yields an honest record (the question was asked,
    no one spoke), never a fabricated debate.
    """
    v = [dict(x) for x in (voices or [])]
    # The tension is only NAMED when there are genuinely opposing voices; otherwise
    # the record admits there was no disagreement (never an invented conflict).
    sides = {str(x.get("stance", "")).lower() for x in v if x.get("stance")}
    has_conflict = bool(tension) or ({"for", "against"} <= sides)
    return {
        "ts": ts,
        "opening": str(question),
        "voices": v,
        "tension": (dict(tension) if tension else
                    ({"for": sorted(x.get("who") for x in v
                                    if str(x.get("stance", "")).lower() == "for"),
                      "against": sorted(x.get("who") for x in v
                                        if str(x.get("stance", "")).lower() == "against"),
                      "named": "the minds disagree on this question"}
                     if has_conflict else None)),
        "resolution": str(resolution),
        "minorities": [dict(x) for x in (minorities or [])],
        "conflict": has_conflict,
        "reading": (f"deliberation: {len(v)} voice(s); "
                    + ("tensione nominata" if has_conflict else "nessuna tensione")),
    }


# --- D5 — THE NETWORK'S HEALTH (communication as a vital sign) --------------

def conversation_metrics(bus: list[dict], *, exchanges: list[dict] | None = None) -> dict:
    """The night's CONVERSATION METRICS: sent/received/answered per channel/kind.

    Also surfaces the UNANSWERED LIST — the questions that died, because a question
    the civilization ignores is a thought it abandoned. ``response_depth`` is the
    mean number of context steps carried by the night's messages (how much thinking
    rides each utterance).
    """
    by_kind: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    for m in bus:
        by_kind[m.get("kind", "?")] = by_kind.get(m.get("kind", "?"), 0) + 1
        ch = m.get("channel")
        if ch:
            by_channel[ch] = by_channel.get(ch, 0) + 1
    for u in (exchanges or []):
        ch = u.get("channel")
        if ch:
            by_channel[ch] = by_channel.get(ch, 0) + 1
    questions = [m for m in bus if m.get("kind") == "question"]
    unanswered = [{"body": q.get("body"), "from": q.get("from"), "ts": q.get("ts")}
                  for q in questions if not q.get("answered")]
    steps = [len((m.get("context") or {}).get("steps") or []) for m in bus]
    steps += [len((u.get("context") or {}).get("steps") or [])
              for u in (exchanges or [])]
    depth = round(sum(steps) / len(steps), 3) if steps else None
    return {
        "messages": len(bus),
        "by_kind": dict(sorted(by_kind.items())),
        "by_channel": dict(sorted(by_channel.items())),
        "questions": len(questions),
        "answered": len(questions) - len(unanswered),
        "unanswered": unanswered,
        "response_depth": depth,
        "reading": (f"{len(bus)} messaggio/i, {len(questions)} domanda/e "
                    f"({len(unanswered)} senza risposta); profondita' media "
                    f"{depth if depth is not None else '--'}"),
    }


def echo_alarm(exchanges: list[dict], *, agreement_floor: float = 0.9,
               min_voices: int = 3) -> dict:
    """THE ECHO WARNING: has the interbrain's diversity of opinion collapsed?

    Groupthink is the death of collective intelligence. When (nearly) every voice on
    the bus agrees (fewer than ``min_voices`` distinct positions among at least
    ``min_voices`` utterances, agreement at/over ``agreement_floor``), the alarm
    fires and the Guardians must trigger a deliberate devil's-advocate session.
    Honest: too few voices to judge -> no alarm (``None`` agreement), never a false
    positive.
    """
    positions = [str(e.get("position") or e.get("stance") or e.get("body") or "")
                 for e in (exchanges or [])]
    positions = [p for p in positions if p]
    n = len(positions)
    if n < min_voices:
        return {"alarm": False, "voices": n, "distinct": len(set(positions)),
                "agreement": None,
                "reading": "troppo pochi per giudicare (nessun allarme)"}
    distinct = len(set(positions))
    agreement = round(1.0 - (distinct - 1) / (n - 1), 4) if n > 1 else 1.0
    alarm = agreement >= agreement_floor and distinct < min_voices
    return {"alarm": alarm, "voices": n, "distinct": distinct,
            "agreement": agreement,
            "reading": (f"ECO: {agreement:.0%} d'accordo su {distinct} posizioni "
                        f"({n} voci) — serve un avvocato del diavolo"
                        if alarm else
                        f"diversita' sana: {distinct} posizioni su {n} voci")}


def devils_advocate(*, consensus: str, assignee: str, ts: str = "") -> dict:
    """ASSIGNED DISSENT: a strong mind must argue the OPPOSITE of the consensus.

    Triggered by the ECHO ALARM. The record shows both sides: the consensus and the
    assigned opposition, so the civilization keeps its capacity to disagree.
    """
    return {
        "ts": ts, "kind": "devils_advocate", "assignee": str(assignee),
        "consensus": str(consensus),
        "task": f"{assignee}: argue seriously AGAINST '{consensus}'",
        "reading": (f"avvocato del diavolo: {assignee} deve argomentare contro "
                    f"'{consensus}'"),
    }
