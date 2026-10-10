"""TRUST SCORES — a genome's live reliability (Phase 3.1).

Trust is the pyramid's memory of *how a genome has actually performed*, so that
Rank 1 and Rank 2 aggregate their soldiers by reliability rather than by headcount.
It is deliberately narrow:

* **Updated ONLY by the honest evaluator.** Nothing else writes a trust score — not
  a priest, not a general, not a tool. The single writer is
  :meth:`TrustBook.observe`, and callers feed it the evaluator's own NET-R
  aggregates (R17).
* **A decaying mean of net-R.** New evidence moves the mean toward the observation;
  what happened long ago is decayed by AGE, so a genome must keep earning its trust.
* **Down-weighted by age.** :meth:`TrustBook.scores` decays a stale entry further
  the longer it has gone unobserved, so trust fades without new evidence.

Probation. A soldier whose trust is zero or negative has stopped paying; it enters
the PROBATION LIST, which is surfaced in every audit. Probation is not deletion:
no soldier is ever silently removed. Death goes through the death ledger (R21), as
always — this module only names who is on watch.

Pure: no I/O, no services. Deterministic given the observation sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ALPHA",
    "HALF_LIFE",
    "TrustEntry",
    "TrustBook",
    "decay_factor",
]

# EWMA weight for a fresh observation (evidence of one tournament evaluation).
ALPHA: float = 0.4
# Age (in tournament generations) over which a stale trust score halves.
HALF_LIFE: float = 3.0


def decay_factor(age: float, half_life: float = HALF_LIFE) -> float:
    """``0.5 ** (age / half_life)`` — 1.0 at age 0, 0.5 at one half-life.

    Fail-closed on a non-positive half-life (a decay with no timescale is a
    division by zero waiting to happen): raise rather than return a flattering 1.0.
    """
    if half_life <= 0:
        raise ValueError(f"half_life must be positive, got {half_life!r} (fail-closed)")
    if age <= 0:
        return 1.0
    return 0.5 ** (age / half_life)


@dataclass
class TrustEntry:
    """One genome's live reliability state."""

    signature: str
    mean_r: float = 0.0          # decaying EWMA of NET R (R17)
    observations: int = 0
    last_generation: int = 0

    def observed(self) -> bool:
        return self.observations > 0


@dataclass
class TrustBook:
    """The live trust registry: one :class:`TrustEntry` per genome signature.

    The book is mutable state BY DESIGN (trust updates as reality reports), but it
    is pure: no clock, no file, no service. ``generation`` is supplied by the
    caller so the book is fully deterministic under a seed.
    """

    alpha: float = ALPHA
    half_life: float = HALF_LIFE
    entries: dict[str, TrustEntry] = field(default_factory=dict)

    def observe(self, signature: str, mean_r: float, generation: int) -> TrustEntry:
        """Fold one honest evaluation's mean NET R into a genome's trust.

        This is the SOLE writer. The first observation seeds the mean directly (no
        phantom prior); later observations decay the old mean by age, then blend.
        """
        entry = self.entries.get(signature)
        if entry is None:
            entry = TrustEntry(signature=signature, mean_r=float(mean_r),
                               observations=1, last_generation=int(generation))
            self.entries[signature] = entry
            return entry
        age = max(0, int(generation) - entry.last_generation)
        decayed = entry.mean_r * decay_factor(age, self.half_life)
        entry.mean_r = (1.0 - self.alpha) * decayed + self.alpha * float(mean_r)
        entry.observations += 1
        entry.last_generation = int(generation)
        return entry

    def score(self, signature: str, at_generation: int | None = None) -> float:
        """A genome's age-decayed trust; 0.0 for an unknown genome (no evidence)."""
        entry = self.entries.get(signature)
        if entry is None or not entry.observed():
            return 0.0
        if at_generation is None:
            return entry.mean_r
        age = max(0, int(at_generation) - entry.last_generation)
        return entry.mean_r * decay_factor(age, self.half_life)

    def scores(self, at_generation: int | None = None) -> dict[str, float]:
        """All known genomes' scores, aged to ``at_generation``."""
        return {sig: self.score(sig, at_generation) for sig in self.entries}

    def probation(self, at_generation: int | None = None) -> list[str]:
        """Signatures whose decayed trust is <= 0 — the PROBATION LIST.

        Surfaced in every audit. Probation is a watch, never a silent deletion: a
        probationary genome keeps its seat until the death ledger records its end.
        Sorted for stable reporting.
        """
        return sorted(
            sig for sig, value in self.scores(at_generation).items() if value <= 0.0
        )

    def to_dict(self, at_generation: int | None = None) -> dict:
        return {
            "scores": self.scores(at_generation),
            "probation": self.probation(at_generation),
            "observations": {s: e.observations for s, e in self.entries.items()},
        }