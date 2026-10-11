"""R77 — THE EXPANDING GAUNTLET (closes DEBT-029).

A FIXED exam is a curriculum for cheaters. The unseen crown gauntlet used to
always draw the same three seeds (7, 11, 13); with enough volume a population can
memorize them. R77 replaces the constant with a MOVING exam:

* the unseen pool is :data:`UNSEEN_POOL` — 32 sealed seeds;
* every crown verdict draws :data:`DRAWS_PER_VERDICT` DISTINCT seeds;
* the draw is a deterministic schedule indexed on the factory-ledger run number
  (:func:`draw_seeds`), so the same run always faces the same exam and the run is
  reproducible;
* no drawn triple repeats within a rolling window of :data:`ROLLING_WINDOW`
  verdicts.

The schedule is a stride permutation over the 3-subsets of the pool: the
multiplicative stride is coprime with the subset count, so the subset index
visits every distinct triple exactly once before repeating — which makes the
window guarantee a theorem, not a hope. ``draw_seeds`` needs no history: it is
resume-safe (only the verdict index matters), so a resumed night draws the same
exam.

R77 does NOT touch the SEEN-seed selection schedule (R42): the enemy faces during
selection are unchanged. It changes only the EXAM the finalists face.

Pure at import; no I/O. Build Mode: pure arithmetic.
"""

from __future__ import annotations

import hashlib
import math
from itertools import combinations

__all__ = [
    "UNSEEN_POOL",
    "DRAWS_PER_VERDICT",
    "ROLLING_WINDOW",
    "pool_digest",
    "draw_seeds",
    "draw_record",
    "draw_schedule",
    "rolling_window_ok",
]

# The sealed unseen pool: 32 seeds, disjoint from the seen selection seeds (0,1,2).
UNSEEN_POOL: tuple[int, ...] = tuple(range(7, 39))
DRAWS_PER_VERDICT: int = 3
ROLLING_WINDOW: int = 20


def pool_digest(pool: tuple[int, ...] = UNSEEN_POOL) -> str:
    """SHA-256 of the sealed pool (a certificate records what exam it faced)."""
    blob = ",".join(str(int(s)) for s in pool)
    return hashlib.sha256(blob.encode()).hexdigest()


def _combos(pool: tuple[int, ...]) -> list[tuple[int, ...]]:
    return list(combinations(tuple(pool), DRAWS_PER_VERDICT))


def _stride(count: int) -> int:
    """A stride coprime with ``count`` — a full-cycle permutation of the subsets."""
    if count <= 1:
        return 1
    s = max(1, count // 3)
    while math.gcd(s, count) != 1:
        s += 1
    return s


def _validate(pool: tuple[int, ...]) -> None:
    if len(pool) < DRAWS_PER_VERDICT:
        raise ValueError(
            f"R77 pool of {len(pool)} cannot draw {DRAWS_PER_VERDICT} distinct "
            f"seeds (fail-closed)"
        )
    if len(set(pool)) != len(pool):
        raise ValueError("R77 pool has duplicates (fail-closed)")
    count = len(_combos(pool))
    if count < ROLLING_WINDOW:
        raise ValueError(
            f"R77 subset count {count} < window {ROLLING_WINDOW}: the no-repeat "
            f"window cannot be guaranteed (fail-closed)"
        )


_validate(UNSEEN_POOL)


def draw_seeds(
    verdict_index: int,
    *,
    pool: tuple[int, ...] = UNSEEN_POOL,
    window: int = ROLLING_WINDOW,
) -> tuple[int, ...]:
    """The DISTINCT seeds verdict number ``verdict_index`` faces (deterministic).

    ``verdict_index`` is the factory-ledger verdict counter (0-based). The draw is
    a stride permutation of the pool's 3-subsets, so no triple repeats within
    ``window`` verdicts (and in fact within ``C(len(pool), 3)`` verdicts).
    """
    if int(verdict_index) < 0:
        raise ValueError("R77 verdict_index must be >= 0 (fail-closed)")
    if window > len(_combos(pool)):
        raise ValueError("R77 window exceeds the subset count (fail-closed)")
    combos = _combos(pool)
    count = len(combos)
    idx = (int(verdict_index) * _stride(count)) % count
    return tuple(sorted(int(s) for s in combos[idx]))


def draw_record(
    verdict_index: int, *, pool: tuple[int, ...] = UNSEEN_POOL
) -> dict:
    """The certificate-shaped record of one draw (seeds + the exam identity)."""
    seeds = draw_seeds(verdict_index, pool=pool)
    return {
        "verdict_index": int(verdict_index),
        "seeds": list(seeds),
        "pool_size": len(pool),
        "pool_digest": pool_digest(pool),
        "draws_per_verdict": DRAWS_PER_VERDICT,
        "rolling_window": ROLLING_WINDOW,
    }


def draw_schedule(
    n: int, *, pool: tuple[int, ...] = UNSEEN_POOL, start: int = 0
) -> list[tuple[int, ...]]:
    """The next ``n`` draws starting at verdict ``start`` (for audits/tests)."""
    return [draw_seeds(start + i, pool=pool) for i in range(int(n))]


def rolling_window_ok(
    draws: list[tuple[int, ...]],
    *,
    window: int = ROLLING_WINDOW,
) -> bool:
    """True iff no drawn triple repeats within any rolling ``window`` of verdicts.

    ``draws[i]`` is consecutive verdict ``i``. Two identical draws must be at
    least ``window`` apart; a repeat closer than that (or adjacent) fails. This is
    the R77 invariant, checked over a real schedule prefix.
    """
    tail: list[tuple[int, ...]] = []
    for d in draws:
        key = tuple(sorted(int(s) for s in d))
        if key in tail:
            return False
        tail.append(key)
        if len(tail) > window - 1:
            tail.pop(0)
    return True
