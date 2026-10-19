"""E8 -- THE COLLABORATIVE WORLD: all is shared, the work converges.

First Amendment, doctrine E8. Countless parallel studies -- every agent explores,
every team researches -- but ALL IS SHARED: every discovery, every failure, every
datum enters the common memory. No isolated towers. The final work is not a sum;
it is convergent collaboration: every team contributes its piece to the mosaic.

This module is the COMMON MEMORY: one append-only store every team writes to and
reads from. Its health is measured by CONVERGENCE, not by volume -- a world where
every team rediscovers the same thing alone is not collaborating.

Pure at import (Scar #6): the store is data; the functions reduce the findings the
caller contributes.
"""

from __future__ import annotations

__all__ = [
    "Finding",
    "contribute",
    "common_memory_digest",
    "convergence",
    "collaboration_report",
]


class Finding(dict):
    """One shared discovery/failure/datum contributed to the common memory (E8)."""

    __slots__ = ()


def contribute(memory: list[dict], *, team: str, kind: str, key: str,
               detail: str = "") -> dict:
    """Add one finding to the COMMON memory and return it (E8).

    ``kind`` is ``"discovery"``, ``"failure"`` or ``"datum"``. Every contribution
    is stamped with the contributing team so credit (and blame) is shared openly.
    """
    if kind not in ("discovery", "failure", "datum"):
        raise ValueError(f"kind must be discovery/failure/datum, got {kind!r}")
    f = Finding(team=str(team), kind=str(kind), key=str(key), detail=str(detail))
    memory.append(f)
    return f


def common_memory_digest(memory: list[dict]) -> dict:
    """The shared memory at a glance: how many teams, what kinds, how many keys."""
    teams: set[str] = set()
    kinds: dict[str, int] = {}
    keys: set[str] = set()
    for f in memory:
        teams.add(f.get("team", "?"))
        kinds[f.get("kind", "?")] = kinds.get(f.get("kind", "?"), 0) + 1
        keys.add(f.get("key", "?"))
    return {"n_findings": len(memory), "n_teams": len(teams),
            "kinds": kinds, "n_distinct_keys": len(keys),
            "teams": sorted(teams)}


def convergence(memory: list[dict]) -> dict:
    """How CONVERGENT the collaboration is (E8), not how busy.

    A key discovered by MORE THAN ONE team is CONVERGENT EVIDENCE -- independent
    teams agreeing is the mosaic forming. A key only one team has is an ISOLATED
    tower. The convergence ratio is convergent keys / distinct keys: 1.0 means the
    world is fully shared; 0.0 means nobody corroborates anybody.
    """
    by_key: dict[str, set[str]] = {}
    for f in memory:
        if f.get("kind") == "failure":
            continue  # failures are lessons, not claims to corroborate
        by_key.setdefault(f.get("key", "?"), set()).add(f.get("team", "?"))
    if not by_key:
        return {"convergent_keys": 0, "isolated_keys": 0, "distinct_keys": 0,
                "convergence_ratio": None,
                "reading": "no claims yet -- nothing to converge"}
    convergent = {k: sorted(v) for k, v in by_key.items() if len(v) > 1}
    isolated = sorted(k for k, v in by_key.items() if len(v) == 1)
    return {
        "convergent_keys": len(convergent),
        "isolated_keys": len(isolated),
        "distinct_keys": len(by_key),
        "convergence_ratio": round(len(convergent) / len(by_key), 4),
        "convergent": convergent,
        "isolated": isolated,
        "reading": (f"{len(convergent)}/{len(by_key)} keys corroborated by >1 team"),
    }


def collaboration_report(memory: list[dict]) -> dict:
    """The Collaborative World's standing report (E8)."""
    digest = common_memory_digest(memory)
    conv = convergence(memory)
    return {
        "doctrine": "E8 the Collaborative World: all is shared; the work converges",
        "digest": digest,
        "convergence": conv,
        "reading": (f"{digest['n_findings']} finding(s) from {digest['n_teams']} "
                    f"team(s); {conv['reading']}"),
    }
