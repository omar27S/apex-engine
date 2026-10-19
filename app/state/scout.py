"""APEX-SCOUT -- a cheap probe that ranks the tape BEFORE the army spends.

R25 splits the sealed evaluation budget into an ARMY share and a SCOUT share; this
module makes the scout's OUTPUT real. Given a cheap, honest per-pair proxy (how
alive a tape is), it ranks the universe and keeps the top names, so the next draw
spends the army where the tape is most likely to pay.

The scout never claims fitness -- it proposes where to LOOK. The army still
proves every candidate through the full tournament. A scout is a hypothesis
generator, not a verdict.

Pure at import (Scar #6): the budget split and the ranking are pure functions of
the caller's measured inputs; nothing here reads the host or the clock.
"""

from __future__ import annotations

__all__ = [
    "FLOOR_KEEP",
    "scout_allocation",
    "rank_pairs",
    "kept_pairs",
    "scout_report",
]

# A scout that keeps fewer names than this is not a scout, it is a coin toss.
FLOOR_KEEP: int = 3


def scout_allocation(total_evals: int, scout_fraction: float) -> dict:
    """Split a sealed evaluation budget (R25) into army + scout shares.

    Fail-closed: a fraction outside ``[0, 1]`` is refused (the doctrine does the
    same), so a bad config can never hand the scouts the whole budget. The scout
    share is floored and the army takes the remainder -- the two always sum to
    ``total_evals`` (no eval is lost or invented).
    """
    if not 0.0 <= float(scout_fraction) <= 1.0:
        raise ValueError("scout_fraction must be within [0, 1]")
    total = int(total_evals)
    if total < 0:
        raise ValueError("total_evals must not be negative")
    scout = int(round(total * float(scout_fraction)))
    return {"total": total, "scout": scout, "army": total - scout,
            "scout_fraction": float(scout_fraction)}


def rank_pairs(scores: dict[str, float]) -> list[tuple[str, float]]:
    """Order pairs by a scout score, highest first; ties break by name (stable)."""
    return sorted(scores.items(), key=lambda kv: (-float(kv[1]), kv[0]))


def kept_pairs(scores: dict[str, float], keep: int) -> list[str]:
    """The top ``keep`` names by scout score (never fewer than ``FLOOR_KEEP``)."""
    n = max(int(keep), FLOOR_KEEP)
    return [name for name, _ in rank_pairs(scores)[:n]]


def scout_report(*, allocation: dict, scores: dict[str, float],
                 keep: int) -> dict:
    """The scout's nightly reading: the split, the ranking, and the kept names."""
    ranked = rank_pairs(scores)
    kept = kept_pairs(scores, keep)
    return {
        "allocation": allocation,
        "ranked": [{"pair": p, "score": float(s)} for p, s in ranked],
        "kept": kept,
        "n_ranked": len(ranked),
        "n_kept": len(kept),
        "reading": (f"scout ranked {len(ranked)} pair(s), kept {len(kept)} "
                    f"({allocation['scout']}/{allocation['total']} evals)"),
    }
