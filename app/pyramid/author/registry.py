"""THE BODY REGISTRY — R34: generated bodies exist on disk, and only on disk.

The CONSTITUTION body is a pinned literal: its source is
:data:`app.pyramid.sandbox.protocol.HELLO_BODY_SOURCE`, sealed by SHA-256
(:data:`CONSTITUTION_BODY_HASH`). No generated body may ever replace it — a
submission whose hash equals the constitution's is refused.

Every other generated body is written under ``app/pyramid/generated/bodies/``
with a name derived from its source hash. The registry is how a produced body
survives a process and how the evaluation path (e.g. :mod:`app.pyramid.oracle`
relative-value needs) finds a body's source by its signature.

PURITY: importing this module does no I/O. Files are touched only by
:func:`store` / :func:`load` / :func:`list_bodies`. In Build Mode nothing is
written. A body is source TEXT that has ALREADY passed the judge; loading it
back re-verifies nothing here — the caller re-runs the gate if it re-executes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "FAMILY_GENERATED_BODY",
    "CONSTITUTION_BODY_HASH",
    "BODIES_DIR",
    "body_hash",
    "store",
    "load",
    "exists",
    "list_bodies",
    "is_constitution",
    "RegistryError",
    "BodyRecord",
]

# The 45th family. Held out of genome.FAMILIES (R1) — it is not a genome family
# and must never be drawn by the breeding layer; it enters the pyramid only
# through the attended Author.
FAMILY_GENERATED_BODY = "generated_body"

# The narrowed + widened constitution pin (R34). Widened in Phase 4b: the sandbox
# bootstrap changed (sanctioned libs are pre-imported before the audit hook).
# Narrowed: verified in the same phase's AGENTS.md log, so the pin was widened
# ONCE, deliberately, and never drifts silently. :func:`app.pyramid.sacred.verify`
# re-asserts it from the sealed file on every purge.
CONSTITUTION_BODY_HASH = "ebb4044317997933377585802bf5443f5a93ca7974196964385d9c04710e4811"

BODIES_DIR = Path(__file__).resolve().parents[1] / "generated" / "bodies"


class RegistryError(Exception):
    """A registry operation refused (fail-closed)."""


@dataclass(frozen=True)
class BodyRecord:
    """A stored body's identity and provenance."""

    body_id: str
    concept: str
    family: str
    parent: str | None
    source_path: str

    def to_dict(self) -> dict:
        return {
            "body_id": self.body_id, "concept": self.concept,
            "family": self.family, "parent": self.parent,
            "source_path": self.source_path,
        }


def body_hash(source: str) -> str:
    """SHA-256 of a body's source (the registry id)."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def is_constitution(source: str) -> bool:
    """True iff ``source`` is the sealed constitution body."""
    return body_hash(source) == CONSTITUTION_BODY_HASH


def verify_constitution() -> bool:
    """R34 pin check: the live reference body still hashes to the sealed pin.

    Imported lazily so this module stays pure at import. The sacred/registry
    guard test calls this on every suite run.
    """
    from app.pyramid.sandbox.protocol import HELLO_BODY_SOURCE

    return body_hash(HELLO_BODY_SOURCE) == CONSTITUTION_BODY_HASH


def _dir(directory: str | Path | None = None) -> Path:
    return Path(directory) if directory is not None else BODIES_DIR


def exists(body_id: str, *, directory: str | Path | None = None) -> bool:
    return (_dir(directory) / f"{body_id}.py").exists()


def store(source: str, *, concept: str = "", family: str = FAMILY_GENERATED_BODY,
          parent: str | None = None, directory: str | Path | None = None) -> BodyRecord:
    """Persist a body's source under its hash. Refuses the constitution body.

    Fail-closed: a source that produces no legal id, or the constitution body,
    is refused. The write is atomic (temp file + replace).
    """
    if not source or not source.strip():
        raise RegistryError("refusing to store an empty body")
    bid = body_hash(source)
    if bid == CONSTITUTION_BODY_HASH:
        raise RegistryError(
            "refusing to store the constitution body as a generated body (R34)"
        )
    d = _dir(directory)
    d.mkdir(parents=True, exist_ok=True)
    src = d / f"{bid}.py"
    tmp = d / f".{bid}.py.tmp"
    tmp.write_text(source, encoding="utf-8")
    tmp.replace(src)
    meta = d / f"{bid}.json"
    tmpm = d / f".{bid}.json.tmp"
    tmpm.write_text(json.dumps({
        "body_id": bid, "concept": concept, "family": family,
        "parent": parent, "source_path": str(src),
    }, sort_keys=True), encoding="utf-8")
    tmpm.replace(meta)
    return BodyRecord(bid, concept, family, parent, str(src))


def load(body_id: str, *, directory: str | Path | None = None) -> str:
    """Return a stored body's source, or raise. Refuses the constitution id."""
    if body_id == CONSTITUTION_BODY_HASH:
        raise RegistryError("the constitution body is not a generated body")
    src = _dir(directory) / f"{body_id}.py"
    if not src.exists():
        raise RegistryError(f"no stored body {body_id!r}")
    return src.read_text(encoding="utf-8")


def list_bodies(*, directory: str | Path | None = None) -> list[BodyRecord]:
    """Every stored body, sorted by id (deterministic)."""
    d = _dir(directory)
    if not d.exists():
        return []
    out: list[BodyRecord] = []
    for meta in sorted(d.glob("*.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(BodyRecord(
            body_id=data.get("body_id", ""), concept=data.get("concept", ""),
            family=data.get("family", ""), parent=data.get("parent"),
            source_path=data.get("source_path", ""),
        ))
    return out
