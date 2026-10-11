"""R78 — PROBATION EXECUTION (closes DEBT-040/036).

DEBT-036 ("the ensemble thesis is unproven") and DEBT-040 ("the ensemble's
contribution is losing") must be settled by DATA, not by doctrine. After the first
:data:`PROBATION_MIN_NIGHTS` volume-nights the ledger knows enough to rule:

* measure the ENSEMBLE RANKED-SHARE — the fraction of ranked candidates that are
  ensembles (both elite- and random-sourced members), across the counted nights;
* if that share stays below :data:`ENSEMBLE_SHARE_FLOOR` (5%), the guaranteed
  ensemble quota AUTOMATICALLY drops from :data:`BASE_QUOTA` (25%) to
  :data:`PROBATION_QUOTA` (10%);
* otherwise the quota is unchanged.

The ruling is deterministic and reproduces from the folded night tables alone
(resume-safe), and the tribunal ledger records it WITH the numbers (the caller
writes one ledger line; see :func:`ruling_record`). No night, no ruling: fewer
than ten volume-nights yields ``probation_pending``, never a fabricated verdict.

Pure at import; no I/O. Build Mode: pure arithmetic over recorded tables.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

__all__ = [
    "PROBATION_MIN_NIGHTS",
    "ENSEMBLE_SHARE_FLOOR",
    "BASE_QUOTA",
    "PROBATION_QUOTA",
    "ProbationError",
    "measure",
    "ruling",
    "decide",
    "ruling_record",
    "ruling_digest",
]

# Sealed numbers (R78). Changing any is a deliberate commit.
PROBATION_MIN_NIGHTS: int = 10
ENSEMBLE_SHARE_FLOOR: float = 0.05
BASE_QUOTA: float = 0.25
PROBATION_QUOTA: float = 0.10

_ENSEMBLE_ARMS = ("ensemble_elite", "ensemble_random")


class ProbationError(ValueError):
    """A probation request was refused (fail-closed)."""


def _row_by_arm(table) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for row in table or []:
        arm = str(row.get("arm", ""))
        if arm:
            rows[arm] = row
    return rows


def _night_totals(table) -> tuple[int, int]:
    """``(ensemble_ranked, total_ranked)`` for one night's survival table."""
    rows = _row_by_arm(table)
    ens = sum(int(rows.get(a, {}).get("ranked", 0)) for a in _ENSEMBLE_ARMS)
    total = sum(int(r.get("ranked", 0)) for r in rows.values())
    return ens, total


def measure(night_tables: list) -> dict:
    """Aggregate the ensemble ranked-share over volume-nights (nights with data).

    A night with zero ranked candidates contributes no rows and is NOT counted
    (an empty night is not evidence). Fail-closed on a non-list input.
    """
    if not isinstance(night_tables, list):
        raise ProbationError("night_tables must be a list (fail-closed)")
    nights = 0
    ens_ranked = 0
    total_ranked = 0
    per_night: list[dict] = []
    for i, table in enumerate(night_tables):
        ens, total = _night_totals(table)
        if total <= 0:
            continue
        nights += 1
        ens_ranked += ens
        total_ranked += total
        per_night.append({"night_index": i, "ensemble_ranked": ens,
                          "total_ranked": total,
                          "share": (ens / total) if total else 0.0})
    share = (ens_ranked / total_ranked) if total_ranked else 0.0
    return {
        "nights_counted": nights,
        "ensemble_ranked": ens_ranked,
        "total_ranked": total_ranked,
        "ensemble_ranked_share": share,
        "share_pct": round(share * 100.0, 4),
        "share_floor": ENSEMBLE_SHARE_FLOOR,
        "min_nights": PROBATION_MIN_NIGHTS,
        "per_night": per_night,
    }


def ruling(measurement: dict) -> dict:
    """The automatic R78 ruling from a :func:`measure` result."""
    nights = int(measurement.get("nights_counted", 0))
    share = float(measurement.get("ensemble_ranked_share", 0.0))
    if nights < PROBATION_MIN_NIGHTS:
        return {
            "state": "probation_pending",
            "nights_counted": nights,
            "nights_required": PROBATION_MIN_NIGHTS,
            "ensemble_ranked_share": share,
            "quota_before": BASE_QUOTA,
            "quota_after": None,
            "triggered": False,
            "reason": (f"{nights}/{PROBATION_MIN_NIGHTS} volume-nights — the data "
                       f"is not yet in; no ruling"),
        }
    triggered = share < ENSEMBLE_SHARE_FLOOR
    return {
        "state": "probation_ruled",
        "nights_counted": nights,
        "nights_required": PROBATION_MIN_NIGHTS,
        "ensemble_ranked_share": share,
        "share_floor": ENSEMBLE_SHARE_FLOOR,
        "quota_before": BASE_QUOTA,
        "quota_after": PROBATION_QUOTA if triggered else BASE_QUOTA,
        "triggered": triggered,
        "reason": (
            f"ensemble ranked-share {share:.4%} < floor "
            f"{ENSEMBLE_SHARE_FLOOR:.2%} over {nights} nights — quota drops to "
            f"{PROBATION_QUOTA:.0%}"
            if triggered else
            f"ensemble ranked-share {share:.4%} >= floor "
            f"{ENSEMBLE_SHARE_FLOOR:.2%} over {nights} nights — quota unchanged"
        ),
    }


def decide(night_tables: list) -> dict:
    """Measure then rule — the full R78 decision, with its numbers."""
    m = measure(night_tables)
    return {**m, "ruling": ruling(m)}


def _plane(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def ruling_digest(decision: dict) -> str:
    """SHA-256 of a decision (the tribunal ledger pins the ruling it recorded)."""
    return hashlib.sha256(_plane(decision).encode()).hexdigest()


def ruling_record(decision: dict, *, night: str, run_number: int) -> dict:
    """The tribunal-ledger line for a ruling: the numbers ride WITH the verdict."""
    r = decision.get("ruling", {})
    return {
        "kind": "ensemble_probation_ruling",
        "night": str(night),
        "run_number": int(run_number),
        "state": r.get("state"),
        "triggered": bool(r.get("triggered", False)),
        "nights_counted": int(r.get("nights_counted", 0)),
        "ensemble_ranked_share": float(decision.get("ensemble_ranked_share", 0.0)),
        "share_pct": float(decision.get("share_pct", 0.0)),
        "share_floor": float(decision.get("share_floor", ENSEMBLE_SHARE_FLOOR)),
        "quota_before": r.get("quota_before"),
        "quota_after": r.get("quota_after"),
        "reason": r.get("reason"),
        "digest": ruling_digest(decision),
    }
