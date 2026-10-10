"""R68 — ISLAND FEDERATION.

Each machine is an ISLAND with its own population. Champions MIGRATE between
islands through the vault: an island exports its champions as a migration commit
(other islands pull it) and imports champions from the others. No island starves
another — the exchange is bounded and symmetric in spirit.

A migration is a sealed, deterministic artefact: it carries the champions'
genomes (as dicts), their realms, their fitness, and a digest over the whole
payload so a corrupted migration is refused, never silently merged.

Building the exported payload is PURE here (no I/O). The tool layer writes and
reads it.

Fail-closed (Scar #1): an empty export is refused; a migration whose digest does
not match its content is refused.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

__all__ = [
    "MigrationError",
    "Migration",
    "build_migration",
    "verify_migration",
    "merge_migrants",
    "MIGRATION_SCHEMA",
]

MIGRATION_SCHEMA = 1


class MigrationError(ValueError):
    """A migration was refused (fail-closed)."""


@dataclass(frozen=True)
class Migration:
    """One island's champion export."""

    source_island: str
    generation: int
    champions: tuple[dict, ...]      # each: {genome, family, realm, wilson_lb, net_r}
    digest: str

    def to_dict(self) -> dict:
        return {
            "schema": MIGRATION_SCHEMA,
            "source_island": self.source_island,
            "generation": int(self.generation),
            "champions": [dict(c) for c in self.champions],
            "digest": self.digest,
        }


def _digest(source_island: str, generation: int, champions) -> str:
    blob = json.dumps(
        {"source_island": source_island, "generation": int(generation),
         "champions": [dict(c) for c in champions]},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def build_migration(source_island: str, generation: int, champions,
                    *, max_champions: int = 10) -> Migration:
    """Seal an island's champions into a migration (deterministic, bounded)."""
    if not source_island:
        raise MigrationError("a migration needs a source island")
    champs = [dict(c) for c in champions][: max(0, int(max_champions))]
    if not champs:
        raise MigrationError("refusing an empty migration (fail-closed)")
    for c in champs:
        if "genome" not in c:
            raise MigrationError("every migrant must carry its genome")
    return Migration(source_island=source_island, generation=int(generation),
                     champions=tuple(champs),
                     digest=_digest(source_island, generation, champs))


def verify_migration(payload: dict) -> Migration:
    """Rebuild and verify a migration from its dict; refuse on any mismatch."""
    if not isinstance(payload, dict):
        raise MigrationError("migration must be a dict")
    if int(payload.get("schema", -1)) != MIGRATION_SCHEMA:
        raise MigrationError(f"unknown migration schema {payload.get('schema')!r}")
    source = str(payload.get("source_island", ""))
    generation = int(payload.get("generation", 0))
    champs = payload.get("champions") or []
    if not source or not champs:
        raise MigrationError("migration is missing island or champions")
    expected = _digest(source, generation, champs)
    if expected != str(payload.get("digest", "")):
        raise MigrationError(
            f"migration digest mismatch: expected {expected}, got "
            f"{payload.get('digest')!r} (fail-closed)"
        )
    return Migration(source_island=source, generation=generation,
                     champions=tuple(dict(c) for c in champs), digest=expected)


def merge_migrants(local_genomes, migrants: list[dict]) -> list:
    """Return local genomes plus non-duplicate migrant genomes (dedup by sig).

    ``local_genomes`` are :class:`StrategyGenome`; ``migrants`` are migration
    champion dicts (each with a ``genome`` dict). A migrant whose signature is
    already present is skipped — no island doubles its population with a clone.
    """
    from app.quant.genome import StrategyGenome

    seen = {str(g.signature()) for g in local_genomes}
    merged = list(local_genomes)
    for migrant in migrants:
        data = migrant.get("genome")
        if not data:
            continue
        g = StrategyGenome.from_dict(data)
        sig = str(g.signature())
        if sig in seen:
            continue
        seen.add(sig)
        merged.append(g)
    return merged
