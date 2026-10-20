"""THE BEHAVIORAL ATLAS -- quality-diversity for the evolution (R103).

The Boss ordered the agents' logic raised to a level beyond the national
(2026-10-20), and the research answered with one clear name: QUALITY-DIVERSITY.
MAP-Elites (Mouret & Clune 2015) does not search for THE best solution -- it
maps a whole ARCHIVE of high-performers, one ELITE PER BEHAVIORAL NICHE,
because diversity is preparation for change: "if a change is needed, a
high-performing solution might already exist." The method has already carried
Llama 3's adversarial-prompt search (rainbow teaming) and Google's
AlphaEvolve. A market that switches regimes is exactly such a world.

THE ATLAS. Every ranked body is described by three MEASURED axes (never by its
genes -- behavior is what the tape saw, not what the DNA promised):

* ACTIVITY   -- trades taken: sparse / low / active / hyper (4 bins);
* HORIZON    -- average bars held: sniper / mid / marathon (3 bins);
* DIRECTION  -- the long share of trades: short-leaning / balanced /
                long-leaning (3 bins).

4 x 3 x 3 = 36 niches. One elite per niche: the best Wilson lower bound the
niche has ever produced (tiebreak net R). The pantry keeps the champions of
REALMS; the atlas keeps the champions of BEHAVIORS -- a trending marathon
long-hunter and a hyperactive sniper reverter are BOTH remembered, because
tomorrow's regime decides which one is king, and the atlas refuses to guess.

THE LAW, BINDING (fail-closed, like everything the Director seals):

* a body with no trades has NO behavior to describe -- it is not offered
  (the couch is not a niche, it is the absence of one);
* an unranked body (too little evidence) is not offered either -- the atlas
  is a map of measured behaviors, never of unknowns;
* the archive is bounded by construction (36 cells), pure (dict in, dict
  out), and fail-open at load (a torn file is a fresh map, never a crash);
* injection is dedup'd by signature and honours the Watchtower's gating at
  its own door -- the same law the pantry and the diaspora obey.

Pure module: no I/O, no app imports, no numpy. The factory wires it; the
tests prove it; the heart commits its file with the ledger (R101 doctrine).
"""

from __future__ import annotations

import json

__all__ = [
    "ACTIVITY_BINS", "HORIZON_BINS", "DIRECTION_BINS", "NICHES",
    "descriptor", "niche_id", "niche_name", "QDArchive",
]

# The measured axes. Each bin is (low, high, name); a value lands in the first
# bin whose high bound exceeds it (the last bin's high is the sky).
ACTIVITY_BINS: tuple[tuple[float, float, str], ...] = (
    (0.0, 15.0, "sparse"),
    (15.0, 40.0, "low"),
    (40.0, 80.0, "active"),
    (80.0, float("inf"), "hyper"),
)
HORIZON_BINS: tuple[tuple[float, float, str], ...] = (
    (0.0, 8.0, "sniper"),
    (8.0, 36.0, "mid"),
    (36.0, float("inf"), "marathon"),
)
DIRECTION_BINS: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.4, "short-leaning"),
    (0.4, 0.6, "balanced"),
    (0.6, 1.01, "long-leaning"),
)
NICHES: int = len(ACTIVITY_BINS) * len(HORIZON_BINS) * len(DIRECTION_BINS)  # 36


def _bin_of(value: float, bins) -> tuple[int, str]:
    v = float(value)
    for i, (_lo, hi, name) in enumerate(bins):
        if v < hi:
            return i, name
    return len(bins) - 1, bins[-1][2]


def descriptor(*, trades: int, avg_bars_held: float, long_share: float) -> dict | None:
    """The measured behavior of one body -- or ``None`` when there is none.

    ``trades <= 0`` means no behavior happened on the tape (the couch: absent,
    never a zero-bin); a ``long_share`` outside [0, 1] or a NaN anywhere is
    refused the same way (fail-closed: the atlas maps measurements, not
    guesses). All three numbers come from the evaluator's honest metrics.
    """
    try:
        t = int(trades)
        held = float(avg_bars_held)
        share = float(long_share)
    except (TypeError, ValueError):
        return None
    if t <= 0 or held != held or share != share:  # NaN guard
        return None
    if not (0.0 <= share <= 1.0):
        return None
    a_i, a_name = _bin_of(t, ACTIVITY_BINS)
    h_i, h_name = _bin_of(held, HORIZON_BINS)
    d_i, d_name = _bin_of(share, DIRECTION_BINS)
    return {"activity": a_name, "horizon": h_name, "direction": d_name,
            "trades": t, "avg_bars_held": round(held, 2),
            "long_share": round(share, 4),
            "_index": (a_i, h_i, d_i)}


def niche_id(desc: dict | None) -> int | None:
    """The niche's stable id 0..35 (``None`` for an absent behavior)."""
    if not isinstance(desc, dict):
        return None
    idx = desc.get("_index")
    if not isinstance(idx, tuple) or len(idx) != 3:
        return None
    a, h, d = idx
    return (int(a) * len(HORIZON_BINS) + int(h)) * len(DIRECTION_BINS) + int(d)


def niche_name(desc: dict | None) -> str:
    """The human niche: 'active/mid/balanced' (empty when absent)."""
    if not desc:
        return ""
    return f"{desc.get('activity')}/{desc.get('horizon')}/{desc.get('direction')}"


class QDArchive:
    """The map: 36 niches, one measured elite each.

    The MAP-Elites rule, sealed: an ``offer`` enters its niche when the niche
    is EMPTY, or when the challenger's Wilson lower bound beats the sitting
    elite's (tiebreak: net R, then trades). The sitting elite is never
    mutated -- replaced whole or kept whole. ``genome`` rides in the entry
    for the injection; every other field is the honest receipt.
    """

    def __init__(self, cells: dict[int, dict] | None = None):
        self.cells: dict[int, dict] = dict(cells or {})

    # -- the MAP-Elites rule ------------------------------------------------
    def offer(self, entry: dict) -> bool:
        """Offer one measured body. Returns True when the map changed."""
        if not isinstance(entry, dict):
            return False
        desc = entry.get("behavior")
        nid = niche_id(desc) if isinstance(desc, dict) else None
        if nid is None:
            return False  # no measured behavior -> no niche (fail-closed)
        wilson = entry.get("wilson_lb")
        if not isinstance(wilson, (int, float)) or wilson != wilson:
            return False  # an unmeasured score is a ghost (Law 3, same as the pantry)
        sitting = self.cells.get(nid)
        if sitting is None:
            self.cells[nid] = dict(entry)
            return True
        challenger = (float(wilson), float(entry.get("net_r") or 0.0),
                      int(entry.get("trades") or 0))
        sitting_key = (float(sitting.get("wilson_lb") or 0.0),
                       float(sitting.get("net_r") or 0.0),
                       int(sitting.get("trades") or 0))
        if challenger > sitting_key:
            self.cells[nid] = dict(entry)
            return True
        return False

    def offer_many(self, entries) -> int:
        """Offer many; returns how many CHANGED the map."""
        n = 0
        for e in entries or []:
            if self.offer(e):
                n += 1
        return n

    # -- the readings -------------------------------------------------------
    def coverage(self) -> float:
        """Occupied niches / 36 -- the atlas's own diversity measure."""
        return len(self.cells) / float(NICHES)

    def occupied(self) -> list[dict]:
        """The elites, best Wilson first (each row carries its niche)."""
        rows = []
        for nid, entry in self.cells.items():
            row = dict(entry)
            row["niche"] = nid
            row["niche_name"] = niche_name(entry.get("behavior"))
            rows.append(row)
        rows.sort(key=lambda r: (float(r.get("wilson_lb") or 0.0),
                                 float(r.get("net_r") or 0.0)), reverse=True)
        return rows

    def diversity_pool(self, cap: int) -> list[dict]:
        """The injection pool: the elites, best-first, at most ``cap``.

        The pool is the WHOLE MAP ordered by measure -- the caller (the
        factory) draws from the top and dedups against the signatures it has
        already seated, so one niche can never flood generation 0 while a
        better-niched elite waits. Diversity enters through COVERAGE, not
        through ignoring quality.
        """
        cap = max(0, int(cap))
        return [dict(e) for e in self.occupied()[:cap]]

    # -- the persistence (fail-open both ways) ------------------------------
    def to_dict(self) -> dict:
        return {"schema": 1, "kind": "qd_atlas",
                "niches_total": NICHES,
                "niches_occupied": len(self.cells),
                "coverage": round(self.coverage(), 4),
                "cells": {str(k): v for k, v in self.cells.items()}}

    @classmethod
    def from_dict(cls, data) -> "QDArchive":
        """A torn file is a fresh map (fail-open), never a crash."""
        if not isinstance(data, dict):
            return cls()
        cells = {}
        for k, v in (data.get("cells") or {}).items():
            try:
                cells[int(k)] = v
            except (TypeError, ValueError):
                continue
        return cls(cells)


def load_archive(path) -> QDArchive:
    """Read the island's atlas file (absent/torn -> a fresh empty map)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return QDArchive.from_dict(json.load(fh))
    except (OSError, ValueError):
        return QDArchive()


def save_archive(archive: QDArchive, path) -> bool:
    """Write the atlas (best-effort: the atlas is a passenger, never a gate)."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(archive.to_dict(), fh, indent=2, default=str)
        return True
    except (OSError, TypeError, ValueError):
        return False
