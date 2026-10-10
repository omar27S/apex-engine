"""R12 — THE SEED VAULT (immigration against premature convergence).

A population that breeds only from its own elite converges on a local optimum and
stops exploring. R12 reserves a fixed fraction of every population for uniformly
random fresh DNA — immigration — so no elite can ever occupy the whole population,
and the vault of reserved DNA persists across tournaments.

This module is the policy and its persistent store:

* :data:`IMMIGRATION_FRACTION` = 0.05 (5% fresh DNA per population).
* :func:`immigration_quota` — how many slots a population of a given size must
  hand to immigrants (at least one for any non-empty population).
* :func:`reserve` — overwrite the tail of a population with fresh random genomes
  (uniformly drawn, *not* weighted by any family table), and
* :func:`save_vault` / :func:`load_vault` — the cross-tournament vault
  (``data/history/.vault.jsonl``, gitignored) so reserved DNA survives a restart.

Build Mode: pure policy functions; the vault file is touched only when a caller
saves or loads.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.quant import breeding
from app.quant.genome import StrategyGenome

__all__ = [
    "IMMIGRATION_FRACTION",
    "VAULT_PATH",
    "immigration_quota",
    "reserve",
    "draw_immigrants",
    "save_vault",
    "load_vault",
]

IMMIGRATION_FRACTION = 0.05
VAULT_PATH = "data/history/.vault.jsonl"


def immigration_quota(size: int) -> int:
    """Slots reserved for fresh DNA in a population of ``size`` (R12).

    At least one for a non-empty population, so exploration never fully stops;
    zero only for an empty population.
    """
    if size <= 0:
        return 0
    return max(1, int(round(size * IMMIGRATION_FRACTION)))


def draw_immigrants(rng, size: int) -> list[StrategyGenome]:
    """``immigration_quota(size)`` uniformly-random fresh genomes.

    Uniform over families via the standard draw (the vault does not bias toward
    any family — that is the whole point of immigration).
    """
    return [breeding.random_genome(rng) for _ in range(immigration_quota(size))]


def reserve(population: list[StrategyGenome], rng) -> list[StrategyGenome]:
    """Return ``population`` with its tail replaced by fresh immigrants.

    Guarantees no elite occupies 100% of a non-empty population. The elites kept
    are the population minus the quota (order preserved from the front).
    """
    size = len(population)
    quota = immigration_quota(size)
    if quota == 0:
        return []
    keep = size - quota
    elites = list(population[:keep])
    return elites + draw_immigrants(rng, size)


def save_vault(genomes: list[StrategyGenome], path: str | None = None) -> str:
    """Append ``genomes`` to the persistent vault (JSONL of genome dicts)."""
    target = Path(path) if path else Path(VAULT_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a") as fh:
        for g in genomes:
            fh.write(json.dumps(g.to_dict(), sort_keys=True, default=str) + "\n")
    return str(target)


def load_vault(path: str | None = None) -> list[StrategyGenome]:
    """Read the vault, skipping corrupt lines (a bad line never breaks a load)."""
    target = Path(path) if path else Path(VAULT_PATH)
    try:
        raw = target.read_text()
    except OSError:
        return []
    out: list[StrategyGenome] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(StrategyGenome.from_dict(json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out
