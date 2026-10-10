"""R75 — THE TURBO BUDGET LAW.

Public-repo bursts are bounded and the bounds are SEALED here: at most a fixed
number of bursts per day, a fixed wall-clock ceiling per burst, and a fixed
concurrency ceiling. The public runner pool is shared infrastructure; saturation
is both a ToS risk and a correctness risk (a throttled runner produces dishonest
timings). The law is pinned by a SHA-256 manifest so a silent widening is a
deliberate commit, exactly as R18 pinned the cost model.

If GitHub throttles anyway the law says: back off, halve, report — never push
through. :func:`backoff` computes the halved budget; :func:`check_burst` refuses
a burst that would exceed any sealed bound.

Pure at import (Scar #6).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

__all__ = [
    "TurboBudget",
    "TURBO_BUDGET",
    "TurboBudgetExceeded",
    "budget_manifest_digest",
    "backoff",
]

# The sealed bounds (R75). Deliberately conservative: GitHub-hosted public
# runners are free but shared; a burst is a few hours, never saturation.
MAX_BURSTS_PER_DAY = 3
MAX_BURST_SECONDS = 2 * 60 * 60      # 2 hours
MAX_CONCURRENT_JOBS = 20


@dataclass(frozen=True)
class TurboBudget:
    """The sealed burst budget (R75)."""

    max_bursts_per_day: int = MAX_BURSTS_PER_DAY
    max_burst_seconds: int = MAX_BURST_SECONDS
    max_concurrent_jobs: int = MAX_CONCURRENT_JOBS

    def to_dict(self) -> dict:
        return {
            "max_bursts_per_day": self.max_bursts_per_day,
            "max_burst_seconds": self.max_burst_seconds,
            "max_concurrent_jobs": self.max_concurrent_jobs,
        }


TURBO_BUDGET = TurboBudget()


class TurboBudgetExceeded(ValueError):
    """A burst was refused for exceeding a sealed R75 bound (fail-closed)."""


def budget_manifest_digest(budget: TurboBudget = TURBO_BUDGET) -> str:
    """SHA-256 of the sealed budget (R18-style pin)."""
    blob = json.dumps(budget.to_dict(), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _positive(name: str, value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise TurboBudgetExceeded(f"{name} must be an integer, got {value!r}")
    if number <= 0:
        raise TurboBudgetExceeded(f"{name} must be positive, got {number!r}")
    return number


def check_burst(
    *,
    bursts_today: int,
    requested_seconds: int,
    concurrency: int,
    budget: TurboBudget = TURBO_BUDGET,
) -> None:
    """Refuse a burst that would exceed a sealed bound. Raises, never warns."""
    bursts_today = _positive("bursts_today", bursts_today) if bursts_today else 0
    if bursts_today >= budget.max_bursts_per_day:
        raise TurboBudgetExceeded(
            f"{bursts_today} bursts already today; the sealed law allows "
            f"{budget.max_bursts_per_day}/day (R75)"
        )
    seconds = _positive("requested_seconds", requested_seconds)
    if seconds > budget.max_burst_seconds:
        raise TurboBudgetExceeded(
            f"requested {seconds}s exceeds the sealed {budget.max_burst_seconds}s "
            f"burst ceiling (R75)"
        )
    conc = _positive("concurrency", concurrency)
    if conc > budget.max_concurrent_jobs:
        raise TurboBudgetExceeded(
            f"requested {conc} concurrent jobs exceeds the sealed "
            f"{budget.max_concurrent_jobs} (R75)"
        )


def backoff(budget: TurboBudget = TURBO_BUDGET) -> TurboBudget:
    """The throttle response (R75): HALVE every bound, never push through."""
    return TurboBudget(
        max_bursts_per_day=max(1, budget.max_bursts_per_day // 2),
        max_burst_seconds=max(1, budget.max_burst_seconds // 2),
        max_concurrent_jobs=max(1, budget.max_concurrent_jobs // 2),
    )
