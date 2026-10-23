"""LAW OF LIFE 1 — THE STATE LEDGER (the Council's minutes; the autobiography).

Every decision the civilization makes is recorded in the STATE LEDGER WITH ITS
REASONING (WHY the civilization chose it). The minutes are the civilization's
autobiography: not a log of timers firing, but a record of THOUGHT — what was
decided, why, on what evidence, and with what expected effect.

Pure at import (Scar #6): the ledger is a list the caller owns; the functions
append and digest. Fail-closed: a decision with no WHY is refused — an action
without reasoning is not a decision, it is a reflex.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "DECISION_KINDS",
    "decision_entry",
    "record",
    "minutes_digest",
    "CouncilLedgerError",
]

DECISION_KINDS: tuple[str, ...] = (
    "cure_family",     # a family is sick — cure it (R147: with a COURSE, then retire)
    "retire_family",   # R147 — E4: the cure course is spent, the family retires by data
    "honor_refusal",   # R147 — the One Brain refused: the Council honors the veto (E9)
    "populate_realm",  # a realm is empty — populate it
    "forge_burst",     # an idea is promising — FORGE IT (a burst)
    "focus_research",  # strong in X, weak in Y — focus research
    "birth",           # the garden spawns agents
    "death",           # the weak are retired (with legacy)
    "dream",           # a creative-sleep consolidation entered the market
    "meta_learning",   # evolve the way we learn (LAW 6)
    "ambition",        # set the current ambition (LAW 9)
    "authorize",       # the CEO authorized a bounded exploration (an OUTSIDE order)
    "settle_idea",     # a forged idea settled from its REAL outcome (LAW 5, Cure 1)
    "replenish_attention",  # the per-cycle attention allowance (LAW 5, Cure 1)
    "play",             # the playground: a role tried with no capital at risk
    "one_brain",        # the collective decided (the One Brain, with its soul)
)


class CouncilLedgerError(ValueError):
    """A decision was refused (fail-closed): no reasoning, or an unknown kind."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decision_entry(*, kind: str, what: str, why: str, evidence: str = "",
                   expected_effect: str = "", ts: str = "",
                   extra: dict | None = None) -> dict:
    """One Council decision, WITH its reasoning (the WHY is mandatory).

    ``evidence`` names the reading the decision rests on; ``expected_effect`` is how
    the civilization expects the world to change. Both may be empty (an early
    decision may rest on reasoning alone) — but ``why`` never is. ``extra`` carries
    structured decision data (e.g. the chosen burst size) for downstream use.
    """
    if kind not in DECISION_KINDS:
        raise CouncilLedgerError(
            f"unknown decision kind {kind!r}; known: {DECISION_KINDS}")
    if not str(why).strip():
        raise CouncilLedgerError(
            "a decision without reasoning is a reflex — the WHY is mandatory")
    entry = {
        "ts": ts or _now(),
        "kind": kind,
        "what": what,
        "why": why,
        "evidence": evidence,
        "expected_effect": expected_effect,
    }
    if extra:
        entry.update(extra)
    return entry


def record(ledger: list[dict], *, kind: str, what: str, why: str,
           evidence: str = "", expected_effect: str = "", ts: str = "",
           extra: dict | None = None) -> dict:
    """Append one reasoned decision to the STATE LEDGER and return it."""
    entry = decision_entry(kind=kind, what=what, why=why, evidence=evidence,
                           expected_effect=expected_effect, ts=ts, extra=extra)
    ledger.append(entry)
    return entry


def minutes_digest(ledger: list[dict], *, last: int = 5) -> dict:
    """A compact reading of the minutes: the count by kind and the latest decisions."""
    by_kind: dict[str, int] = {}
    for e in ledger:
        by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
    tail = ledger[-last:] if last > 0 else []
    return {
        "decisions": len(ledger),
        "by_kind": dict(sorted(by_kind.items())),
        "latest": [{"kind": e.get("kind"), "what": e.get("what"), "why": e.get("why")}
                   for e in tail],
        "reading": f"{len(ledger)} decision(s) recorded: {by_kind}",
    }
