"""THE MEMBER VOTE CACHE (R59, Phase 7c) — pay for a member's signals once.

An ensemble's masks are a quorum over its members' masks. The SAME concrete
member genome appears in many ensembles (and, under R58, is often a former elite
that was already judged as a SINGLE). Recomputing its gate stack for every
ensemble that contains it is pure waste.

R59 keys a member's vote on the exact quadruple that determines it::

    (member signature, pair, world seed, slice identity)

* **member signature** — the DNA (``StrategyGenome.signature()``).
* **pair** — the instrument.
* **world seed** — the R42 rotation face (0 for the clean world).
* **slice identity** — a content digest of the evaluated frames, so a clean tape
  and a wounded tape, or a train and a test slice, can NEVER share a key even if
  they happen to be the same length.

FAIL-CLOSED ON COLLISION. The key carries the member signature, and the stored
payload re-states it; a hit whose stored signature differs from the requested one
is a hard :class:`VoteCacheCollision` (never a silent wrong vote). A payload is
copied on read and on write, so a caller mutating the returned masks cannot
poison the cache.

Build Mode: a plain in-memory map. No I/O, no globals — the caller owns the
instance and its lifetime (one cache per run/world).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

__all__ = [
    "VoteCacheCollision",
    "slice_identity",
    "member_vote_key",
    "MemberVoteCache",
    "MISS",
]

# A unique sentinel distinguishing "absent" from a cached all-False mask.
MISS = object()


class VoteCacheCollision(RuntimeError):
    """A cache key was reused for a DIFFERENT member (fail-closed)."""


def slice_identity(frames) -> str:
    """A content digest of the evaluated frames (R59 slice identity).

    Stable over the execution timestamps and closes, so two different tapes —
    clean vs wounded, train vs test — never collide even at equal length. Pure
    and deterministic; never depends on wall-clock or memory address.
    """
    exec_df = getattr(frames, "exec", frames)
    ts = np.ascontiguousarray(exec_df["ts"].to_numpy(), dtype="int64")
    close = np.ascontiguousarray(exec_df["close"].to_numpy(), dtype="float64")
    h = hashlib.sha1()
    h.update(str(getattr(frames, "pair", "")).encode())
    h.update(ts.tobytes())
    h.update(close.tobytes())
    return h.hexdigest()[:16]


def member_vote_key(member, pair: str, world_seed: int, slice_id: str) -> tuple:
    """The R59 cache key. The member signature is the DNA half of the identity."""
    sig = member.signature() if hasattr(member, "signature") else str(member)
    return (str(sig), str(pair), int(world_seed), str(slice_id))


@dataclass
class _Payload:
    signature: str
    long: np.ndarray
    short: np.ndarray
    counts: dict
    extra: dict


class MemberVoteCache:
    """An explicit, caller-owned read-through cache of member signal masks.

    ``get_or_compute(key, signature, compute)`` returns the cached
    ``(long, short, counts, extra)`` for ``key`` or computes and stores it.
    ``compute`` is only called on a miss, so a warm cache makes a repeated
    member FREE (the R59 promise). ``hits``/``misses`` are the honest arithmetic
    the property tests pin.
    """

    def __init__(self) -> None:
        self._store: dict[tuple, _Payload] = {}
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._store)

    def get_or_compute(self, key: tuple, signature: str, compute):
        """Read-through: cached payload for ``key`` or ``compute()`` then store."""
        stored = self._store.get(key)
        if stored is not None:
            if stored.signature != str(signature):
                raise VoteCacheCollision(
                    f"cache collision at {key}: stored member {stored.signature} "
                    f"!= requested {signature} (fail-closed)"
                )
            self.hits += 1
            return (
                stored.long.copy(), stored.short.copy(),
                dict(stored.counts), dict(stored.extra),
            )
        self.misses += 1
        long_m, short_m, counts, extra = compute()
        self._store[key] = _Payload(
            signature=str(signature),
            long=np.array(long_m, dtype=bool, copy=True),
            short=np.array(short_m, dtype=bool, copy=True),
            counts=dict(counts or {}),
            extra=dict(extra or {}),
        )
        return (
            np.array(long_m, dtype=bool, copy=True),
            np.array(short_m, dtype=bool, copy=True),
            dict(counts or {}), dict(extra or {}),
        )

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._store),
            "hit_rate": (self.hits / total) if total else 0.0,
        }
