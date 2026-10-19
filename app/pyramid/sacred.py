"""THE SACRED FILES — sealed, hashed, and guarded (R29, Phase 4a).

Some files are the Constitution itself. A self-written body (Phase 4b) must never
be able to change them, and neither should a careless edit. This module pins the
SHA-256 of every sacred file; :func:`verify` recomputes them.

The guard test (``tests/pyramid/test_sacred.py``) calls :func:`verify` on every
suite run, so ANY change to a sacred byte — a refactor, a "tidy", a stray format
— fails the suite. Adding a file to the sacred set is a deliberate act: append
its relative path to :data:`SACRED_FILES` and pin its hash in :data:`SACRED_HASHES`
in the SAME commit, then :func:`stamp` (a helper) prints the values to paste.

Paths are relative to the backend package root (the parent of ``app/``), so a
hash is stable regardless of where the repo is checked out.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

__all__ = ["SACRED_FILES", "SACRED_HASHES", "SacredCheck", "ROOT", "hash_file",
           "verify", "stamp"]

# The backend root = the directory that contains "app/".
ROOT = Path(__file__).resolve().parents[2]

# The sealed set (R29). Append only with a matching hash — never remove silently.
SACRED_FILES: tuple[str, ...] = (
    "app/core/law.py",
    "app/core/pairs.py",
    "app/core/tick_value.py",
    "app/core/rate_oracle.py",
    "app/core/data.py",
    "app/quant/costs.py",
)

# The pinned SHA-256 of each sacred file, in the same order as SACRED_FILES.
SACRED_HASHES: dict[str, str] = {
    "app/core/law.py":
        "e329cf0a89a662bfaccb6a8c2ca92407da8692c5f69f1745735143f8bdb009c2",
    "app/core/pairs.py":
        "2377fdaba446cd371b0dad1a6e850b95771bdab6e6a1dea8e4c3238effd7d485",
    "app/core/tick_value.py":
        "17073218c2ace207ef74b3c04c72df7b5594f272fe73dd244b54d869a8bccced",
    "app/core/rate_oracle.py":
        "47ffc818fc294f71f93da5942c7ed7953da020c9798f03a7696018a75e6b2fb4",
    "app/core/data.py":
        "bb57626afa2983c9007eea82dd078c98ab2a03c73d0e7619b4c6aa5a2e15aaf8",
    "app/quant/costs.py":
        "fb588c28d1eae05d0564281cfb4f658e2a309931e9930ddebddc481ba624e642",
}


@dataclass(frozen=True)
class SacredCheck:
    ok: bool
    failures: dict[str, tuple[str, str]]  # rel_path -> (expected, found)

    def to_dict(self) -> dict:
        return {"ok": self.ok,
                "failures": {k: {"expected": e, "found": f}
                             for k, (e, f) in self.failures.items()}}


def hash_file(rel_path: str) -> str | None:
    p = ROOT / rel_path
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify() -> SacredCheck:
    """Recompute every sacred hash. Any mismatch (or missing file) fails."""
    failures: dict[str, tuple[str, str]] = {}
    for rel in SACRED_FILES:
        expected = SACRED_HASHES.get(rel, "")
        found = hash_file(rel) or "<missing>"
        if expected != found:
            failures[rel] = (expected, found)
    return SacredCheck(ok=not failures, failures=failures)


def stamp() -> dict[str, str]:
    """Return the current hashes (helpers to re-pin after a deliberate change)."""
    return {rel: (hash_file(rel) or "<missing>") for rel in SACRED_FILES}
