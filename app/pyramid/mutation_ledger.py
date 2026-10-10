"""THE MUTATION LEDGER — every birth, verdict, and death, append-only (Phase 4a).

Self-written code is dangerous precisely because it is *ours*. This ledger is the
chain of custody: nothing a body does is anonymous, and the nuclear switch
(:func:`purge_generated`) is proven, not promised.

FORMAT. One JSON object per line (JSONL), append-only, never rewritten:

  * ``{"kind": "birth", "era": E, "body_id": ..., "source_hash": ..., "parent": ...,
      "concept": "...", "origin": "generated"|"reference"}``
  * ``{"kind": "verdict", "era": E, "body_id": ..., "alive": bool, "causes": [...],
      "family": "...", "performance": {...}, "gates": {...}}``
  * ``{"kind": "death", "era": E, "body_id": ..., "cause": "sandbox_death", ...}``
  * ``{"kind": "purge", "era": E, "removed": [...], "sacred_ok": true}``

PURGE (the CEO's nuclear switch). :func:`purge_generated` deletes every body file
under ``app/pyramid/generated/`` and every generated artifact, records the purge
in the ledger, and then RE-VERIFIES the sacred files (R29) — a purge that touched
a sacred byte is a failure, reported loudly.

Pure at import. The only I/O is inside the explicit methods.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.pyramid import sacred

__all__ = ["MutationLedger", "body_hash", "GENERATED_DIR"]

# The one directory a code-writer may ever write to (R29). Resolved from this file.
GENERATED_DIR = Path(__file__).resolve().parent / "generated"


def body_hash(source: str) -> str:
    """SHA-256 of a body's source — its identity on the ledger (R23 coarse lineage)."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass
class MutationLedger:
    """An append-only JSONL ledger plus the purge switch."""

    path: Path
    era: int = 0
    _cache: list[dict] | None = field(default=None, repr=False)

    # -- io -----------------------------------------------------------------
    def _append(self, record: dict) -> dict:
        record = dict(record)
        record.setdefault("era", self.era)
        record.setdefault("ts", int(time.time()))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        self._cache = None
        return record

    def records(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = []
            return self._cache
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        self._cache = out
        return out

    # -- lifecycle ----------------------------------------------------------
    def birth(self, source: str, *, concept: str, parent: str | None = None,
              origin: str = "generated") -> str:
        """Record a body's birth; return its id (the source hash).

        Lineage only — the ledger never writes body artifacts. R34 persistence of
        a generated body is the AUTHOR's job (:mod:`app.pyramid.author.registry`),
        kept separate so recording and storing never couple.
        """
        bid = body_hash(source)
        self._append({
            "kind": "birth", "body_id": bid, "source_hash": bid,
            "parent": parent, "concept": concept, "origin": origin,
        })
        return bid

    def verdict(self, body_id: str, verdict) -> dict:
        """Record a judge verdict (alive or dead)."""
        d = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict)
        rec = {"kind": "verdict", "body_id": body_id, "alive": d["alive"],
               "causes": d.get("causes", []), "family": d.get("family", ""),
               "performance": d.get("performance"), "gates": d.get("gates", {})}
        self._append(rec)
        if not d["alive"]:
            for cause in d.get("causes", []) or ["unknown"]:
                self._append({"kind": "death", "body_id": body_id, "cause": cause,
                              "detail": d.get("detail", "")})
        return rec

    # -- the nuclear switch -------------------------------------------------
    def purge_generated(self) -> dict:
        """Delete every generated body and artifact; record it; re-verify R29."""
        removed: list[str] = []
        if GENERATED_DIR.exists():
            for p in sorted(GENERATED_DIR.rglob("*"), reverse=True):
                if p.is_dir():
                    p.rmdir()
                else:
                    p.unlink()
                removed.append(str(p.relative_to(GENERATED_DIR)))
        # Re-verify the sacred files survived the purge untouched (R29).
        check = sacred.verify()
        rec = self._append({"kind": "purge", "removed": removed, "sacred_ok": check.ok,
                            "sacred_failures": check.failures})
        return rec

    # -- reporting ----------------------------------------------------------
    def summary(self) -> dict:
        by_cause: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        by_era: dict[str, dict[str, int]] = {}
        births = verdicts = 0
        for r in self.records():
            kind = r.get("kind", "?")
            by_kind[kind] = by_kind.get(kind, 0) + 1
            era = str(r.get("era", "?"))
            ebox = by_era.setdefault(era, {})
            ebox[kind] = ebox.get(kind, 0) + 1
            if kind == "birth":
                births += 1
            elif kind == "verdict":
                verdicts += 1
            elif kind == "death":
                cause = r.get("cause", "unknown")
                by_cause[cause] = by_cause.get(cause, 0) + 1
        alive = sum(1 for r in self.records()
                    if r.get("kind") == "verdict" and r.get("alive"))
        return {
            "total_records": len(self.records()),
            "births": births,
            "verdicts": verdicts,
            "alive": alive,
            "dead": verdicts - alive,
            "by_kind": by_kind,
            "by_cause": by_cause,
            "by_era": by_era,
        }
