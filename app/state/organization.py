"""THE REORGANIZATION — the pyramid's first self-designed organisation.

Charter act 3. The state reorganises itself (roles, chains, specialisations, new
agents) as the agents judge best. MERITOCRACY IS LAW: command is earned by
demonstrated understanding — the Trust Score (:mod:`app.pyramid.trust`) is the
right to command. Whoever understands most leads; every commander has aides who
have aides.

This module PROPOSES the organisation (a pure structure) and records it in the
STATE LEDGER. It does not staff it: staffing is drawn from the honest tournament,
and Trust Scores are written ONLY by the evaluator (trust.py's single-writer rule).

Pure at import (Scar #6): no I/O, no services.
"""

from __future__ import annotations

__all__ = [
    "SPECIALISATIONS",
    "CHAIN_OF_COMMAND",
    "merit_order",
    "commander_of",
    "reorganization_entry",
    "sensor_corps_entry",
]

# The new specialisations (beyond the sealed 700-role ranks). Each is a SUPPORT
# corps: it advises, invents, or studies; it never votes (voting stays with the
# sealed ranks). ``aides`` = how many subordinates aid this specialisation.
SPECIALISATIONS: tuple[dict, ...] = (
    {"name": "inventors", "duty": "author/synthesise new bodies", "aides": 3},
    {"name": "researchers", "duty": "study the world (C: outside study)", "aides": 2},
    {"name": "philosophers", "duty": "state the doctrines and their invariants", "aides": 2},
    {"name": "mathematicians", "duty": "prove the arithmetic; guard the ledger", "aides": 2},
    {"name": "commanders", "duty": "command by Trust Score; hold aides", "aides": 4},
    # THE SENSOR CORPS (Founding Charter — the study-pair firewall's organisation).
    # It READS the 15 study pairs as sensors (context/cross-confirmation) and NEVER
    # trades them. Its duty is the firewall's second half, made a standing role.
    {"name": "sensor_corps",
     "duty": "read the 15 study pairs as SENSORS (context only, never trade)", "aides": 2},
)

# THE CHAIN OF COMMAND: rank order of command authority. Higher = commands. The
# chain is meritocratic — a seat is held by the highest Trust Score at that rank,
# not by seniority (Charter A).
CHAIN_OF_COMMAND: tuple[str, ...] = (
    "spectres", "avant_garde", "soldiers", "generals", "priests",
    "commanders", "oracle",
)


def merit_order(candidates: list[dict]) -> list[dict]:
    """Rank candidates by Trust Score (desc), tie-break by signature (stable).

    Each candidate is ``{"signature": str, "trust": float}``. Trust is the right to
    command; the most understanding leads. A non-finite trust is refused (a
    commander chosen off a missing number is how a state gets a bad leader).
    """
    clean = []
    for c in candidates:
        t = float(c.get("trust", 0.0))
        if t != t or t in (float("inf"), float("-inf")):
            raise ValueError(f"trust must be finite, got {t!r} for {c.get('signature')!r}")
        clean.append({"signature": c["signature"], "trust": t})
    return sorted(clean, key=lambda c: (-c["trust"], c["signature"]))


def commander_of(candidates: list[dict]) -> dict | None:
    """The candidate with the highest Trust Score — the one who commands."""
    order = merit_order(candidates)
    return order[0] if order else None


def reorganization_entry() -> dict:
    """The STATE LEDGER entry for the reorganisation (what/why/expected effect)."""
    return {
        "change": "add five support specialisations; meritocratic chain of command",
        "roles_added": [s["name"] for s in SPECIALISATIONS],
        "chain_of_command": list(CHAIN_OF_COMMAND),
        "why": ("the charter grants self-organisation; command must be earned by "
                "demonstrated understanding (Trust Score), not seniority"),
        "expected_effect": ("faster invention (inventors), grounded doctrine "
                            "(philosophers), airtight arithmetic (mathematicians), "
                            "and command that follows the evidence"),
        "staffing": "drawn from the honest tournament; trust written only by the evaluator",
        "implemented_now": "the structure + merit-order rule (pure); staffing pending",
    }


def sensor_corps_entry() -> dict:
    """The STATE LEDGER entry for the SENSOR CORPS (the firewall's organisation).

    The study-pair firewall made the 15 study pairs untradeable; this makes the
    reading of them a STANDING ROLE, so the sensors are studied every night (not
    ignored) while the trade gate still refuses them.
    """
    from app.state.firewall import OPERATIONAL_PAIRS, STUDY_PAIRS

    return {
        "change": "add the sensor_corps specialisation",
        "duty": "read the 15 study pairs as SENSORS (context/cross-confirmation only)",
        "sensor_pairs": list(STUDY_PAIRS),
        "operational_pairs": list(OPERATIONAL_PAIRS),
        "why": ("the firewall forbids trading the study pairs, but their data must "
                "still be STUDIED; a standing corps guarantees the sensors are read"),
        "expected_effect": ("cross-confirmation context the operational pairs can use, "
                            "with zero risk of a sensor being traded"),
        "never": "the sensor_corps proposes no trade; the firewall gate refuses any anyway",
        "implemented_now": "the role + its reading duty (pure); nightly reading pending",
    }
