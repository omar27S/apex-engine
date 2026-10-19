"""LAW OF LIFE 7 — STRUCTURED CURIOSITY (the drive to explore the unknown).

Every agent carries a curiosity instinct pointing at the UNKNOWN — measured
novelty zones, where our knowledge is thinnest. When collective curiosity crosses
a threshold, the civilization ORGANIZES ITS OWN EXPLORATION: "we know nothing
about regime X — let's send scouts." Raids on ignorance, planned by the desire to
know. The curiosity map is drawn nightly: WHERE the civilization is curious, and
WHY.

Pure at import (Scar #6): coverage and agents are data; the functions reduce.
"""

from __future__ import annotations

from math import isfinite

__all__ = [
    "RAID_THRESHOLD",
    "novelty",
    "curiosity_instinct",
    "collective_curiosity",
    "raid_candidates",
    "curiosity_map",
]

# Collective curiosity (attention-weighted novelty in a zone) at or above which
# the civilization organizes a raid on that ignorance.
RAID_THRESHOLD: float = 1.5


def novelty(coverage: float) -> float:
    """How UNKNOWN a zone is: ``1 - coverage`` (coverage in [0, 1], fail-closed).

    Coverage is our measured knowledge depth of a zone (fraction of it studied).
    A zone we have barely touched has novelty near 1; a well-known zone near 0.
    """
    c = float(coverage)
    if not isfinite(c) or not (0.0 <= c <= 1.0):
        raise ValueError(f"coverage must be a finite fraction in [0, 1], got {coverage!r}")
    return round(1.0 - c, 6)


def curiosity_instinct(*, zone: str, coverage: float, strength: float = 1.0) -> dict:
    """One agent's curiosity pointing at a zone (novelty * the agent's strength)."""
    n = novelty(coverage)
    s = float(strength)
    if not isfinite(s) or s < 0.0:
        raise ValueError(f"strength must be a finite non-negative number, got {strength!r}")
    return {"zone": zone, "coverage": float(coverage), "novelty": n,
            "strength": round(s, 6), "pull": round(n * s, 6)}


def collective_curiosity(instincts: list[dict]) -> dict[str, float]:
    """Aggregate per-zone curiosity: the sum of every agent's pull toward it."""
    out: dict[str, float] = {}
    for i in instincts:
        out[i["zone"]] = round(out.get(i["zone"], 0.0) + float(i["pull"]), 6)
    return out


def raid_candidates(instincts: list[dict], *,
                    threshold: float = RAID_THRESHOLD) -> list[dict]:
    """Which zones the civilization chooses to raid (collective pull >= threshold)."""
    agg = collective_curiosity(instincts)
    raids = [{"zone": z, "pull": p} for z, p in agg.items() if p >= threshold]
    return sorted(raids, key=lambda r: (-r["pull"], r["zone"]))


def curiosity_map(instincts: list[dict], *,
                  threshold: float = RAID_THRESHOLD) -> dict:
    """THE CURIOSITY MAP — where the civilization is curious tonight, and WHY.

    ``why`` names the thinnest knowledge (the lowest coverage zone) in plain words.
    """
    agg = collective_curiosity(instincts)
    if not agg:
        return {"zones": [], "raids": [], "thinnest": None,
                "reading": "no curiosity measured (no zones)"}
    thinnest = min(instincts, key=lambda i: (i["coverage"], i["zone"]))
    zones = [{"zone": z, "pull": p} for z, p in
             sorted(agg.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {
        "zones": zones,
        "raids": raid_candidates(instincts, threshold=threshold),
        "thinnest": {"zone": thinnest["zone"], "coverage": thinnest["coverage"],
                     "why": (f"knowledge thinnest here: coverage "
                             f"{thinnest['coverage']:.2f} of {thinnest['zone']}")},
        "reading": (f"{len(zones)} zone(s); thinnest={thinnest['zone']} "
                    f"(coverage {thinnest['coverage']:.2f})"),
    }
