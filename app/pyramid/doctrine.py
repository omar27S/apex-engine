"""PHASE 3.2 DOCTRINE — the sealed numbers of the Oracle era.

These are LAW-ADJACENT numbers (like the cost books, R18), so they live in ONE
place, are pinned by a SHA-256 manifest, and may not be re-declared elsewhere
(Scar #2). Changing any of them is a deliberate commit that updates the pinned
hash in the same change.

R24 — TRADE-DENOMINATED SLICES. Avant-Garde exploration slices are measured in
      TRADES, not bars. A scout assembles a slice that reaches
      :data:`AVANT_GARDE_TRADE_TARGET` trades; the sealed ``min_trades`` (30) is
      untouched — the SLICE adapts to the bar, never the bar to the slice. A slice
      that cannot reach the quota on ANY assembly is reported as UNFOUND, loudly.

R25 — AVANT-GARDE BUDGET FRACTION. Exploration consumes exactly
      :data:`AVANT_GARDE_BUDGET_FRACTION` of the evaluation budget. The chosen unit
      is EVALUATIONS (genome-evaluations): it is the most honest unit — wall-clock
      is machine-dependent and bars are not comparable across pairs, but one
      genome-evaluation is the same work everywhere. The army (tournament) and the
      scouts (avant-garde) therefore can never starve each other.

R26 — RESERVE GENERALS ON DUTY. The reserve generals rotate onto constellation
      pairs by a SEALED deterministic schedule
      (:func:`app.pyramid.roster.reserve_rotation`), so no pair is ever left
      without a commanding officer. See the roster module for the schedule; this
      file seals only the rotation period.

Build Mode: pure constants and pure helpers. No I/O, no services.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

__all__ = [
    "AVANT_GARDE_TRADE_TARGET",
    "AVANT_GARDE_BUDGET_FRACTION",
    "RESERVE_ROTATION_PERIOD",
    "doctrine_digest",
    "split_budget",
    "scout_runs_for_budget",
]

# R24 — how many TRADES an exploration slice must reach (not bars).
AVANT_GARDE_TRADE_TARGET: int = 200

# R25 — the fraction of the evaluation budget the scouts consume. Exactly 15%.
# The army takes the remainder. Chosen unit: genome-evaluations (see docstring).
AVANT_GARDE_BUDGET_FRACTION: float = 0.15

# R26 — how many pairs the reserve rotation keeps a reserve officer on, per step.
# The schedule advances one pair per muster generation; period 15 visits every
# constellation pair exactly once before repeating (zero uncovered territory).
RESERVE_ROTATION_PERIOD: int = 15


def _validate() -> None:
    if AVANT_GARDE_TRADE_TARGET <= 0:
        raise ValueError("R24 trade target must be positive (fail-closed)")
    if not (0.0 < AVANT_GARDE_BUDGET_FRACTION < 1.0):
        raise ValueError("R25 budget fraction must be in (0,1) (fail-closed)")
    if RESERVE_ROTATION_PERIOD <= 0:
        raise ValueError("R26 rotation period must be positive (fail-closed)")


_validate()


@dataclass(frozen=True)
class DoctrineManifest:
    """The sealed R24/R25/R26 numbers, in one pinned record."""

    trade_target: int = AVANT_GARDE_TRADE_TARGET
    budget_fraction: float = AVANT_GARDE_BUDGET_FRACTION
    rotation_period: int = RESERVE_ROTATION_PERIOD

    def digest(self) -> str:
        blob = f"R24={self.trade_target};R25={self.budget_fraction!r};R26={self.rotation_period}"
        return hashlib.sha256(blob.encode()).hexdigest()


MANIFEST = DoctrineManifest()


def doctrine_digest() -> str:
    """SHA-256 of the sealed doctrine numbers (pinned by test)."""
    return MANIFEST.digest()


def split_budget(total_evals: int, fraction: float = AVANT_GARDE_BUDGET_FRACTION) -> tuple[int, int]:
    """Split ``total_evals`` into ``(army_evals, scout_evals)`` at ``fraction``.

    The scouts take ``round(total * fraction)``; the army takes the rest, so the
    two ALWAYS sum to ``total`` exactly (no evaluation is created or lost). Integer
    rounding is the only source of drift from the ideal fraction, and it is bounded
    by half an evaluation; the caller may report the realized ratio.
    """
    if total_evals < 0:
        raise ValueError("total_evals must be >= 0 (fail-closed)")
    if not (0.0 < fraction < 1.0):
        raise ValueError("fraction must be in (0,1) (fail-closed)")
    scouts = int(round(total_evals * fraction))
    # Never let rounding hand the scouts the whole budget or starve them to zero
    # when the budget is non-trivial (an exploration with no eyes is a silent lie).
    if total_evals > 0:
        scouts = max(1, min(total_evals - 1, scouts))
    army = total_evals - scouts
    return army, scouts


def scout_runs_for_budget(
    scout_evals: int, population: int, generations: int = 1
) -> int:
    """How many micro-runs fit in ``scout_evals`` (each costs pop*generations)."""
    per_run = max(1, int(population) * max(1, int(generations)))
    return max(0, int(scout_evals) // per_run)
