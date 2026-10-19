"""E6 -- EPISODIC MEMORY: every closed trade becomes a narrative the state recalls.

First Amendment, doctrine E6. Every closed trade becomes a narrative EPISODE:
context + decision + outcome + lesson. Episodes are indexed by similarity, so a
similar situation AWAKENS the memories of what happened before and what was
learned. The episodic palace grows nightly and is consulted before every proposal.

This is the old sage's memory for the state: not a table of numbers, but a store
of STORIES the state can be reminded of.

Pure at import (Scar #6): the episode store is data; similarity and recall are
reductions. The store lives in memory (the caller persists it), never I/O here.
"""

from __future__ import annotations

import math

__all__ = [
    "Episode",
    "episode_from_trade",
    "similarity",
    "recall",
    "consult_before_proposal",
    "episodic_report",
]


class Episode(dict):
    """One trade's narrative: context + decision + outcome + lesson (E6)."""

    __slots__ = ()


def _vec(features: dict) -> list[float]:
    """A stable numeric vector from a feature dict (sorted keys, fail-closed)."""
    out: list[float] = []
    for k in sorted(features):
        v = float(features[k])
        if not math.isfinite(v):
            raise ValueError(f"feature {k!r} is not finite: {features[k]!r} (fail-closed)")
        out.append(v)
    return out


def episode_from_trade(*, pair: str, features: dict, decision: str, net_r: float,
                       lesson: str = "") -> Episode:
    """Build an episode from a closed trade (E6).

    ``features`` is the decision-time context vector; ``decision`` names what the
    state did; ``net_r`` is the honest NET R outcome (R17); ``lesson`` is the
    human-form takeaway the state writes for itself. A missing lesson is DERIVED
    from the outcome so no episode is ever blank.
    """
    net = float(net_r)
    if not math.isfinite(net):
        raise ValueError(f"net_r must be finite, got {net_r!r} (fail-closed)")
    if not lesson:
        lesson = ("the setup paid" if net > 0 else
                  "the setup cost us -- remember this context" if net < 0 else
                  "the setup was a wash")
    return Episode(
        pair=str(pair),
        features={str(k): float(v) for k, v in features.items()},
        decision=str(decision),
        net_r=net,
        lesson=str(lesson),
    )


def similarity(a: dict, b: dict) -> float:
    """Cosine similarity of two contexts in [0, 1] (negative folded to 0).

    Only the shared feature keys are compared; a context with no overlap is
    dissimilar (0.0) -- the state does not pretend to recall what it never saw.
    """
    keys = sorted(set(a) & set(b))
    if not keys:
        return 0.0
    va = [float(a[k]) for k in keys]
    vb = [float(b[k]) for k in keys]
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(y * y for y in vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return round(max(0.0, dot / (na * nb)), 6)


def recall(episodes: list[dict], context: dict, *, k: int = 5,
           min_similarity: float = 0.5) -> list[dict]:
    """The episodes most similar to ``context`` (E6), strongest first.

    A similarity floor means a genuinely novel context awakens NOTHING -- the state
    admits it has not seen this before, rather than forcing a weak match.
    """
    if k <= 0:
        raise ValueError(f"k must be >= 1, got {k!r}")
    scored = []
    for ep in episodes:
        s = similarity(ep.get("features", {}), context)
        if s >= min_similarity:
            scored.append({"similarity": s, "episode": ep})
    scored.sort(key=lambda x: -x["similarity"])
    return scored[:k]


def consult_before_proposal(episodes: list[dict], context: dict, *,
                            k: int = 5, min_similarity: float = 0.5) -> dict:
    """What the sage recalls before a proposal (E6).

    Returns the awakened episodes plus a human-form ``prior`` (the similarity-
    weighted mean NET R of what happened in similar situations) and the lessons.
    An empty recall is honest: ``prior`` is ``None`` with a reason, never a zero
    that would masquerade as evidence.
    """
    recalled = recall(episodes, context, k=k, min_similarity=min_similarity)
    if not recalled:
        return {"recalled": [], "n": 0, "prior_net_r": None,
                "lessons": [],
                "reading": "no similar episode -- this context is new to the state"}
    wsum = sum(r["similarity"] for r in recalled)
    prior = sum(r["similarity"] * float(r["episode"].get("net_r", 0.0))
                for r in recalled) / wsum
    return {
        "recalled": recalled,
        "n": len(recalled),
        "prior_net_r": round(prior, 6),
        "lessons": [r["episode"].get("lesson", "") for r in recalled],
        "reading": (f"{len(recalled)} episode(s) recalled; prior net R {prior:+.2f}"),
    }


def consult_proposal(episodes: list[dict], context: dict, *,
                     k: int = 5, min_similarity: float = 0.5) -> dict:
    """The SAGE's consultation on the trade-proposal path (E6, Cure 5).

    Before a proposal is made, the sage recalls the episodes most similar to the
    proposal's context and returns a similarity-weighted prior. The result is
    recorded WITH the proposal, so every proposal carries the sage's fingerprint:
    which episodes were recalled and what they teach. An empty recall is honest
    (``advisory_none``), never a forced weak match.
    """
    c = consult_before_proposal(episodes, context, k=k, min_similarity=min_similarity)
    c["sensor"] = "E6_sage"
    c["context"] = dict(context or {})
    return c


def episodic_report(episodes: list[dict]) -> dict:
    """The episodic palace's standing report (E6)."""
    pairs: dict[str, int] = {}
    wins = 0
    for ep in episodes:
        pairs[ep.get("pair", "?")] = pairs.get(ep.get("pair", "?"), 0) + 1
        if float(ep.get("net_r", 0.0)) > 0:
            wins += 1
    n = len(episodes)
    return {
        "doctrine": "E6 episodic memory: every trade is a narrative, recalled by similarity",
        "n_episodes": n,
        "by_pair": pairs,
        "wins": wins,
        "win_rate": round(wins / n, 4) if n else None,
        "reading": f"{n} episode(s) in the palace" + ("" if n else " (empty)"),
    }
