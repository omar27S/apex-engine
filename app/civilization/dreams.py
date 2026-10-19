"""LAW OF LIFE 8 — CREATIVE SLEEP (productive rest).

In low-activity moments the civilization DREAMS: it consolidates memory (the
episodic palace is reorganized and re-indexed), it reconnects distant ideas (the
serendipity engine: "this failure from 3 weeks ago resembles this success from
yesterday — why?"), and surfaces intuitions. Dreams are logged: the best
dream-born ideas enter the Market of Ideas on waking.

Pure at import (Scar #6): episodes are data; consolidation and serendipity are
reductions. The dream LOG is a list the caller owns.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "is_quiet",
    "consolidate",
    "serendipity",
    "dream",
    "dream_report",
]

# A cycle with at most this many interbrain messages is "quiet" enough to dream.
QUIET_MESSAGES: int = 3


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_quiet(bus: list[dict], *, threshold: int = QUIET_MESSAGES) -> bool:
    """Is the civilization quiet enough to sleep? (little traffic this cycle)."""
    return len(bus) <= threshold


def consolidate(episodes: list[dict]) -> dict:
    """Reorganize + re-index the episodic palace: index episodes by their lesson.

    Returns an index (lesson-key -> count) and the palace's size. This is the
    memory work of sleep — the palace, tidied, ready to be recalled.
    """
    index: dict[str, int] = {}
    for e in episodes:
        key = str(e.get("lesson") or "(no lesson)")[:80]
        index[key] = index.get(key, 0) + 1
    return {"episodes": len(episodes), "index": index,
            "distinct_lessons": len(index)}


def _tokens(text: str) -> set[str]:
    return {t for t in
            "".join(c.lower() if c.isalnum() else " " for c in str(text)).split()
            if len(t) > 2}


def _outcome(e: dict) -> str:
    """The episode's outcome, from the REAL schema (``net_r``) or a named field.

    ``episode_from_trade`` records the honest NET R under ``net_r``; older/hand-built
    episodes may carry an explicit ``outcome``. Reading only ``outcome`` left every
    real episode "unknown" and silenced serendipity (a dead dream, BUG-6).
    """
    if e.get("outcome") is not None:
        return str(e["outcome"])
    net = e.get("net_r")
    if isinstance(net, (int, float)):
        return "win" if net > 0 else "loss" if net < 0 else "wash"
    return "(unknown)"


def _context_text(e: dict) -> str:
    """The episode's context as text: ``features`` (the real schema) or ``context``."""
    ctx = e.get("context")
    if ctx is not None:
        return str(ctx)
    feats = e.get("features")
    if isinstance(feats, dict):
        return " ".join(f"{k}={v}" for k, v in sorted(feats.items()))
    return str(e.get("pair", ""))


def serendipity(episodes: list[dict], *, min_overlap: int = 2,
                max_pairs: int = 3) -> list[dict]:
    """Reconnect DISTANT episodes: an old failure resembling a recent success.

    Two episodes from different outcomes that share enough lesson/context tokens
    are surfaced as a QUESTION the civilization should ask itself ("why?").
    """
    pairs: list[dict] = []
    for i in range(len(episodes)):
        for j in range(i + 1, len(episodes)):
            a, b = episodes[i], episodes[j]
            oa, ob = _outcome(a), _outcome(b)
            if oa == ob:
                continue  # distant means a contrast: fail vs succeed
            ta = _tokens(str(a.get("lesson", "")) + " " + _context_text(a))
            tb = _tokens(str(b.get("lesson", "")) + " " + _context_text(b))
            shared = ta & tb
            if len(shared) >= min_overlap:
                pairs.append({
                    "a": _context_text(a) or a.get("pair"),
                    "outcome_a": oa,
                    "b": _context_text(b) or b.get("pair"),
                    "outcome_b": ob,
                    "shared": sorted(shared),
                    "question": (f"why does {oa} here resemble "
                                 f"{ob} there? shared: "
                                 f"{', '.join(sorted(shared))}"),
                })
            if len(pairs) >= max_pairs:
                return pairs
    return pairs


def dream(episodes: list[dict], *, bus: list[dict] | None = None,
          ts: str = "") -> dict:
    """One dream: consolidate the palace, surface serendipitous questions."""
    consolidation = consolidate(episodes)
    questions = serendipity(episodes)
    born = [{"idea": q["question"], "from": "dream/serendipity"}
            for q in questions]
    return {
        "ts": ts or _now(),
        "quiet": is_quiet(bus or []),
        "consolidation": consolidation,
        "serendipity": questions,
        "born_ideas": born,
        "reading": (f"consolidated {consolidation['episodes']} episode(s); "
                    f"{len(questions)} serendipitous question(s)"),
    }


def dream_report(dreams: list[dict]) -> dict:
    """A compact reading of the night's dreams and the ideas they surfaced."""
    born = [i for d in dreams for i in d.get("born_ideas", [])]
    return {"dreams": len(dreams), "born_ideas": born,
            "reading": (f"{len(dreams)} dream(s); {len(born)} dream-born idea(s)")}
