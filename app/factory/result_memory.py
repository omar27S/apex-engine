"""R70 — RESULT MEMORY (the evaluation cache).

An evaluation is expensive. An UNCHANGED genome facing the SAME world (same
world-seed) over the SAME slice must NEVER be re-evaluated. This module is a
caller-owned read-through cache keyed by
``(genome signature, world-seed, slice identity)``, structurally identical in
spirit to the R59 vote cache but one level up: it memoizes the whole
``EvaluationReport`` (its honest metrics + per-pair reports), not a single
member's masks.

The night report must show the REUSE RATIO (hits / total). A ratio of 0.0 is a
legitimate, honest reading: it means nothing repeated. A fabricated reuse is
impossible here — the cache only returns what a real prior evaluation produced.

Slice identity reuses the R59 :func:`app.quant.vote_cache.slice_identity` so the
train/wounded/test tapes can never collide even at equal length (single source of
truth, Scar #2).

Pure at import; no I/O.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

__all__ = ["ResultMemory", "result_key", "MISS_RESULT"]

MISS_RESULT = object()


@dataclass
class ResultMemory:
    """A read-through cache of honest evaluation reports (R70).

    ``get_or_compute(key, compute)`` calls ``compute()`` ONLY on a miss and
    returns a DEEP COPY of the stored report, so a caller mutating its report
    can never corrupt what the cache remembers (the same isolation discipline as
    the R59 vote cache).
    """

    def __init__(self) -> None:
        self._store: dict[tuple, object] = {}
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._store)

    def get_or_compute(self, key: tuple, compute):
        stored = self._store.get(key)
        if stored is not None:
            self.hits += 1
            return copy.deepcopy(stored)
        self.misses += 1
        value = compute()
        self._store[key] = copy.deepcopy(value)
        return value

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._store),
            "reuse_ratio": (self.hits / total) if total else 0.0,
        }


def result_key(signature: str, world_seed: int, slice_id: str) -> tuple:
    """The R70 cache key: DNA + world + slice. All three are mandatory."""
    return (str(signature), int(world_seed), str(slice_id))
