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
        "c37a791632a3fd75771aab21ed995d9e935c1acc32bb8f3eaa2622e51a20a885",
    "app/core/pairs.py":
        "3ecd3ebe1f19924c3f9c2f22987e06ffcc3cfd29d6a7bb62b582db508b54ced0",
    "app/core/tick_value.py":
        "17073218c2ace207ef74b3c04c72df7b5594f272fe73dd244b54d869a8bccced",
    "app/core/rate_oracle.py":
        "a5a60a56b28b95ea2130543bc8d86faa390896aa4820387cb8ebd1873e59332e",
    "app/core/data.py":
        "bb57626afa2983c9007eea82dd078c98ab2a03c73d0e7619b4c6aa5a2e15aaf8",
    "app/quant/costs.py":
        "d0d33949568d8cf4f4948850686b4fe23b58ea268dc6554c8bc06e19b98ad3c7",
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
