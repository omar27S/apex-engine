"""THE STUDY-PAIR FIREWALL — the 15 operational rule, enforced structurally.

CEO ruling (Founding Charter, binding): trades are proposed ONLY on the 15
operational pairs (majors + core crosses). The additional 15 study pairs are
SENSORS ONLY — data sources, macro context, cross-confirmation. The system READS
them; it does not trade or optimise them.

This module is the single structural gate. A study-pair signal can never become a
trade because the only door from a signal to a trade proposal —
:func:`gate_trade_proposal` — refuses any pair outside
:data:`app.core.constellation.OPERATIONAL_PAIRS`. There is no flag, override, or
research mode that widens the trade path; "SENSORS ONLY" is not a policy the state
may reinterpret, it is a wall.

Study pairs remain fully usable as CONTEXT: :func:`may_signal_as_context` is
permissive for every study pair, so cross-confirmation layers are unaffected. The
wall is on the TRADE path, not the READING path.

Pure at import (Scar #6): no I/O, no services, no loops.
"""

from __future__ import annotations

from app.core.constellation import (
    CONSTELLATION_PAIRS,
    OPERATIONAL_PAIRS,
    STUDY_PAIRS,
)
from app.core.law import normalize_pair

__all__ = [
    "OPERATIONAL_PAIRS",
    "STUDY_PAIRS",
    "is_operational",
    "is_study_pair",
    "role_of",
    "may_signal_as_context",
    "may_be_evolution_target",
    "FirewallBreach",
    "gate_trade_proposal",
    "firewall_report",
]

_OPERATIONAL_SET = frozenset(OPERATIONAL_PAIRS)
_STUDY_SET = frozenset(STUDY_PAIRS)


class FirewallBreach(ValueError):
    """Raised when a study pair (or a non-member) is pushed onto the trade path."""


def is_operational(symbol: str) -> bool:
    """True iff ``symbol`` is one of the 15 pairs on which trades may be proposed."""
    canonical = normalize_pair(symbol)
    return canonical is not None and canonical in _OPERATIONAL_SET


def is_study_pair(symbol: str) -> bool:
    """True iff ``symbol`` is a sensor-only study pair (never traded)."""
    canonical = normalize_pair(symbol)
    return canonical is not None and canonical in _STUDY_SET


def role_of(symbol: str) -> str | None:
    """``"operational"``, ``"study"``, or ``None`` for a non-member."""
    canonical = normalize_pair(symbol)
    if canonical is None:
        return None
    if canonical in _OPERATIONAL_SET:
        return "operational"
    if canonical in _STUDY_SET:
        return "study"
    return None


def may_signal_as_context(symbol: str) -> bool:
    """Context/confirmation is open to EVERY member — study pairs are sensors.

    This is the permissive half of the firewall: a study pair's signal may feed a
    context or cross-confirmation layer. It may never feed the trade path.
    """
    canonical = normalize_pair(symbol)
    return canonical is not None and canonical in (_OPERATIONAL_SET | _STUDY_SET)


def may_be_evolution_target(symbol: str) -> bool:
    """Evolution targets are the 15 operational pairs ONLY (study pairs are not
    optimised)."""
    return is_operational(symbol)


def gate_trade_proposal(symbol: str) -> str:
    """THE wall. Return the canonical pair, or raise :class:`FirewallBreach`.

    Fail-closed: a study pair and a non-member are both refused. Every path that
    turns a signal into a trade proposal must pass through here, so a sensor-only
    pair can never become a trade.
    """
    canonical = normalize_pair(symbol)
    if canonical is None:
        raise FirewallBreach(f"{symbol!r} is not a canonical pair (fail-closed)")
    if canonical not in _OPERATIONAL_SET:
        role = "a study pair (SENSORS ONLY)" if canonical in _STUDY_SET else "not a member"
        raise FirewallBreach(
            f"{canonical} is {role}; trades are proposed ONLY on the 15 "
            f"operational pairs (Founding Charter: study pairs are sensors)"
        )
    return canonical


def firewall_report() -> dict:
    """The firewall's standing report, for the nightly STATE REPORT (act 5).

    Names the 15 operational trade pairs and the 15 sensor-only study pairs, so
    every night's summary proves the split is intact and the state never traded a
    sensor.
    """
    return {
        "rule": "trades are proposed ONLY on the 15 operational pairs; the 15 study "
                "pairs are SENSORS ONLY (context/cross-confirmation, never trades)",
        "n_operational": len(OPERATIONAL_PAIRS),
        "n_study": len(STUDY_PAIRS),
        "operational_pairs": list(OPERATIONAL_PAIRS),
        "study_pairs": list(STUDY_PAIRS),
        "reading": (f"{len(OPERATIONAL_PAIRS)} operational / {len(STUDY_PAIRS)} study "
                    f"= {len(CONSTELLATION_PAIRS)} members; sensors never trade"),
    }


# Import-time proof that the split is exactly the sealed roster: 15 + 15 = 30,
# disjoint, and complete. A silent drift in either half is a loud error.
if len(OPERATIONAL_PAIRS) != 15 or len(STUDY_PAIRS) != 15:
    raise ValueError(
        f"the firewall expects 15 operational + 15 study, got "
        f"{len(OPERATIONAL_PAIRS)} + {len(STUDY_PAIRS)}"
    )
if set(OPERATIONAL_PAIRS) & set(STUDY_PAIRS):
    raise ValueError("operational and study pairs must be disjoint")
if set(OPERATIONAL_PAIRS) | set(STUDY_PAIRS) != set(CONSTELLATION_PAIRS):
    raise ValueError("operational + study must cover the Constellation exactly")
