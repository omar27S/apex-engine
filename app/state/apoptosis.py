"""E4 -- THE CYCLE OF THE WEAK: apoptosis and the Children of the King.

First Amendment, doctrine E4. Weak and useless agents are retired WITH HONOUR:
their death is apoptosis, and their death causes feed the learning (E2). Their
seats are taken by CHILDREN OF THE KING -- new agents carrying the structure and
DNA of the strongest King in the system, plus a LIGHT mutation, so the royal blood
spreads while each child explores its own path.

Two rules are structural, not stylistic:

* WEAKNESS IS DECIDED BY DATA, NEVER BY MOOD. A family is weak only when the
  survivability evidence says so: every member the adversary tested died. The
  evidence comes from ``app.quant.tribunal.survivability_findings`` (R38/R39), so
  the verdict is a reading, not an opinion.
* NO BLIND CLONE ARMY. A child is a MUTATED copy of the King (light jitter), never
  a byte-identical duplicate -- a clone army explores nothing. Each child carries
  the King's family/structure and its own path.

Pure at import (Scar #6). The RNG is passed in (seeded), so the royal line is
reproducible.
"""

from __future__ import annotations

from app.quant import breeding, tribunal

__all__ = [
    "MIN_WEAKNESS_FAILURES",
    "CHILD_MUTATION_RATE",
    "weak_families",
    "retire_weak",
    "children_of_the_king",
    "apoptosis_report",
]

# A family must have at least this many ADVERSARY-TESTED failures (and zero
# certified survivors) to be called weak by data.
MIN_WEAKNESS_FAILURES: int = 3

# The light mutation applied to each child (E4: royal blood spreads, each child
# explores its own path -- never a blind clone).
CHILD_MUTATION_RATE: float = 0.15
CHILD_MUTATION_JITTER: float = 0.10


def weak_families(certificates: list[dict], *,
                  min_failures: int = MIN_WEAKNESS_FAILURES) -> list[dict]:
    """Families that are WEAK BY DATA: every tested member died (E4).

    Uses the R38/R39 survivability certificates. A family with ``certified == 0``
    and at least ``min_failures`` failed members is weak; a family that certified
    even one member is NOT (the data has not condemned it). Returns evidence per
    weak family -- the death cause that feeds the learning (E2).
    """
    findings = tribunal.survivability_findings(certificates)
    weak: list[dict] = []
    for fam, box in findings["by_family"].items():
        if box.get("certified", 0) == 0 and box.get("failed", 0) >= min_failures:
            weak.append({
                "family": fam,
                "certified": box.get("certified", 0),
                "failed": box.get("failed", 0),
                "failed_keys": box.get("failed_keys", {}),
                "cause": "apoptosis",
                "evidence": "0 certified, all tested members died under the adversary",
            })
    return sorted(weak, key=lambda w: (-w["failed"], w["family"]))


def retire_weak(certificates: list[dict], *,
                min_failures: int = MIN_WEAKNESS_FAILURES) -> dict:
    """Retire the weak families with honour; return the seats that free up.

    The retired count IS the number of seats that the Children of the King fill.
    The death cause (``apoptosis``) is in the sealed death ledger's closed set, so
    each retirement is a first-class, auditable death.
    """
    weak = weak_families(certificates, min_failures=min_failures)
    return {
        "retired": weak,
        "n_retired": len(weak),
        "seats_freed": len(weak),
        "cause": "apoptosis",
        "reading": (f"{len(weak)} family(ies) retired with honour; "
                    f"{len(weak)} seat(s) freed for the Children of the King"),
    }


def children_of_the_king(king, rng, *, n: int) -> list:
    """``n`` light mutations of the King -- the royal line (E4).

    Each child carries the King's structure (family, member shape) with a LIGHT
    jitter, so no two children are identical and none is a blind clone. ``king`` is
    a ``StrategyGenome``; ``rng`` is a seeded ``numpy`` Generator (reproducible).
    A non-positive ``n`` is refused (fail-closed: a dynasty of zero is not a cycle).
    """
    if n <= 0:
        raise ValueError(f"children_of_the_king needs n >= 1, got {n!r}")
    children = []
    for _ in range(int(n)):
        children.append(breeding.mutate_genome(
            king, rng, rate=CHILD_MUTATION_RATE, jitter=CHILD_MUTATION_JITTER))
    return children


def apoptosis_report(certificates: list[dict], *,
                     min_failures: int = MIN_WEAKNESS_FAILURES) -> dict:
    """The Cycle of the Weak's report: who is retired, and why (by data)."""
    r = retire_weak(certificates, min_failures=min_failures)
    return {
        "doctrine": "E4 the Cycle of the Weak: retire by data, replace with the King's children",
        "retired": r["retired"],
        "n_retired": r["n_retired"],
        "seats_for_children": r["seats_freed"],
        "rule": ("weakness is decided by survivability DATA (0 certified, all tested "
                 "died); replacements are light mutations of the King, never clones"),
        "reading": r["reading"],
    }
