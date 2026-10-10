"""R67 — THE SLICED TOURNAMENT.

A tournament can run as N parallel slices. Each slice is an independent
population shard evaluated on a PAIR-SUBSET; a coordinator then FUSES the slice
leaderboards into one, breeding across slices, and signs ONE certificate.

Determinism is the whole game: under a fixed ``(seed, slice-set)`` the partition
of pairs, the derived per-slice seeds, the fused ordering and the certificate
payload are byte-identical. That makes a distributed burst reproducible — the
TURBO's parallel jobs can be replayed.

Fail-closed (Scar #1): asking for more slices than there are pairs is refused
(a slice with no pair cannot be evaluated); an empty slice-set is refused.

Pure at import; no I/O.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

__all__ = [
    "SliceSpec",
    "SliceError",
    "partition_pairs",
    "slice_seed",
    "make_slices",
    "dedup_best",
    "fuse_leaderboards",
    "fuse_certificate_summary",
]


class SliceError(ValueError):
    """A slice request was refused (fail-closed)."""


@dataclass(frozen=True)
class SliceSpec:
    """One slice: a pair-subset, a seed, and a stable index."""

    index: int
    pairs: tuple[str, ...]
    seed: int

    def to_dict(self) -> dict:
        return {"index": self.index, "pairs": list(self.pairs), "seed": self.seed}


def partition_pairs(pairs, n_slices: int) -> tuple[tuple[str, ...], ...]:
    """Split a pair list into ``n_slices`` balanced, disjoint, deterministic groups.

    The pairs are sorted first (canonical order) then dealt round-robin so the
    groups are balanced and no pair appears twice. Fail-closed when there are
    fewer pairs than slices (a slice must have at least one pair).
    """
    canonical = tuple(sorted({str(p).strip().upper() for p in pairs if str(p).strip()}))
    n = int(n_slices)
    if n < 1:
        raise SliceError(f"n_slices must be >= 1, got {n}")
    if len(canonical) < n:
        raise SliceError(
            f"{len(canonical)} pairs cannot fill {n} slices (each slice needs a "
            f"pair) — fail-closed"
        )
    groups: list[list[str]] = [[] for _ in range(n)]
    for i, pair in enumerate(canonical):
        groups[i % n].append(pair)
    return tuple(tuple(g) for g in groups)


def slice_seed(base_seed: int, index: int, salt: str = "") -> int:
    """A deterministic per-slice seed derived from (base_seed, index, salt)."""
    blob = f"{int(base_seed)}:{int(index)}:{salt}"
    digest = hashlib.sha256(blob.encode()).hexdigest()
    return int(digest[:8], 16) % (2 ** 31 - 1)


def make_slices(pairs, n_slices: int, base_seed: int = 0,
                salt: str = "") -> tuple[SliceSpec, ...]:
    """The deterministic slice-set for ``(base_seed, n_slices, pairs, salt)``."""
    groups = partition_pairs(pairs, n_slices)
    return tuple(
        SliceSpec(index=i, pairs=groups[i],
                  seed=slice_seed(base_seed, i, salt))
        for i in range(len(groups))
    )


def _row_key(row: dict) -> tuple[float, float]:
    try:
        lb = float(row.get("wilson_lb", 0.0))
    except (TypeError, ValueError):
        lb = 0.0
    try:
        net = float(row.get("net_r", 0.0))
    except (TypeError, ValueError):
        net = 0.0
    return (lb, net)


def dedup_best(rows) -> list[dict]:
    """Dedup rows by signature, keeping the best-ranked occurrence.

    A genome that reached two slices is counted ONCE, at its best rank — the
    fusion never inflates a signature's standing by counting clones.
    """
    best: dict[str, dict] = {}
    for row in rows:
        sig = str(row.get("signature", ""))
        if not sig:
            continue
        cur = best.get(sig)
        if cur is None or _row_key(row) > _row_key(cur):
            best[sig] = dict(row)
    return list(best.values())


def fuse_leaderboards(rows_by_slice: dict[int, list[dict]],
                      *, top_n: int | None = None) -> list[dict]:
    """Merge slice leaderboards into one ranked table (deterministic).

    Rows are deduped by signature, then ranked by ``(wilson_lb, net_r)`` with the
    signature as the final tiebreak so the order is total and reproducible.
    """
    merged = dedup_best(
        row for rows in rows_by_slice.values() for row in (rows or [])
    )
    merged.sort(
        key=lambda r: (_row_key(r), str(r.get("signature", ""))),
        reverse=True,
    )
    if top_n is not None:
        merged = merged[: max(0, int(top_n))]
    return merged


def fuse_certificate_summary(slices, rows_by_slice: dict[int, list[dict]],
                             fused: list[dict]) -> dict:
    """The ONE certificate's slice summary — deterministic under slice-set."""
    blob = json.dumps([s.to_dict() for s in slices], sort_keys=True)
    return {
        "slices": [s.to_dict() for s in slices],
        "slice_set_digest": hashlib.sha256(blob.encode()).hexdigest()[:16],
        "per_slice_sizes": {str(s.index): len(rows_by_slice.get(s.index, []))
                            for s in slices},
        "fused_size": len(fused),
        "fused_top": [
            {"signature": r.get("signature", ""), "family": r.get("family", ""),
             "wilson_lb": r.get("wilson_lb"), "net_r": r.get("net_r")}
            for r in fused[:10]
        ],
    }
