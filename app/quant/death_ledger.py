"""THE DEATH LEDGER — every genome death, recorded and never hidden.

Scar #8 says an honest system surfaces its own weaknesses. The breeding layer
kills a great many genomes (early stops, tournament floors, apoptosis, retirement,
tribunal removal). This module makes those deaths auditable: an append-only
JSONL ledger plus a :func:`summary` reader, so a family that dies *systematically*
is EXPOSED by the aggregate counts instead of vanishing silently.

A record is one JSON object per line::

    {"signature": "...", "family": "breakout", "generation": 3,
     "cause": "early_stop", "detail": "...", "date": "..."}

The ledger path is gitignored (``data/history/.deaths.jsonl``). Build Mode: no
I/O at import; the file is touched only when a caller records or reads.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["CAUSES", "LEDGER_PATH", "DeathRecord", "record", "summary", "summarize", "load"]

LEDGER_PATH = "data/history/.deaths.jsonl"

# The closed set of death causes. An unknown cause is a bug in the caller, so
# ``record`` raises rather than writing an untriageable line.
#
# "friction" (R21) is the exile cause: a genome whose final NET R is <= 0 died to
# costs, not to a rank. It is a first-class death so the ledger's by-cause counts
# expose how much of the population reality invoiced.
CAUSES: frozenset[str] = frozenset(
    {"early_stop", "tournament_floor", "apoptosis", "retirement", "tribunal", "friction"}
)


class DeathRecord(dict):
    """A single death, as a plain dict subclass (JSON-serializable as-is)."""

    __slots__ = ()


def record(
    signature: str,
    family: str,
    generation: int,
    cause: str,
    *,
    detail: str = "",
    date: str = "",
    path: str | None = None,
) -> DeathRecord:
    """Append one death to the ledger. Raises on an unknown ``cause``.

    Append-only: a line is never rewritten or removed. The caller owns the
    ``signature``/``family``; this module only journals them.
    """
    if cause not in CAUSES:
        raise ValueError(f"unknown death cause {cause!r}; expected one of {sorted(CAUSES)}")
    entry = DeathRecord(
        signature=str(signature),
        family=str(family),
        generation=int(generation),
        cause=str(cause),
        detail=str(detail),
        date=str(date),
    )
    target = Path(path) if path else Path(LEDGER_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def load(path: str | None = None) -> list[dict]:
    """Read the ledger, skipping corrupt lines rather than raising.

    A half-written line (a crash mid-append) must never break an audit; the
    readable records are returned and the bad line is ignored.
    """
    target = Path(path) if path else Path(LEDGER_PATH)
    try:
        raw = target.read_text()
    except OSError:
        return []
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def summary(path: str | None = None) -> dict:
    """Aggregate the ledger: totals per family and per cause, plus the record count.

    Returns ``{"total": int, "by_family": {family: count}, "by_cause": {cause: count}}``.
    This is the autopsy entry point: a family dominating the death counts is a
    systematic failure worth a tribunal session, not a footnote.
    """
    records = load(path)
    return summarize(records)


def summarize(records: list[dict]) -> dict:
    """Aggregate an already-loaded list of death records (same shape as ``summary``).

    The tournament holds its deaths in memory; this lets it aggregate them with
    the SAME code path as the on-disk ledger, so the two can never diverge.
    """
    by_family: dict[str, int] = {}
    by_cause: dict[str, int] = {}
    for r in records:
        fam = str(r.get("family", "?"))
        cause = str(r.get("cause", "?"))
        by_family[fam] = by_family.get(fam, 0) + 1
        by_cause[cause] = by_cause.get(cause, 0) + 1
    return {"total": len(records), "by_family": by_family, "by_cause": by_cause}
