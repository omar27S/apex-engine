"""R69 — THE EVALUATION STAIRCASE.

Progressive screening so a genome that dies early costs SECONDS, not minutes:

* ROUND 1 (cheap): 1 pair, 6 months, early-stop. Almost everything is screened
  here and most things die here.
* ROUND 2 (medium): 5 pairs, the full era. Survivors of round 1 are re-judged.
* ROUND 3 (full): the unseen gauntlet. Only finalists reach it.

The staircase is a PURE policy: given a pool of genomes and the three evaluator
callables it runs the funnel and reports, honestly, how many entered and left
each round. A genome killed in round 1 is never evaluated further — that is the
whole saving.

Fail-closed (Scar #1): a round with no evaluator is refused; a pool that empties
stops there (the honest outcome), it does not re-run.

Pure at import; no I/O, no loop beyond the bounded pool x rounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "STAIRCASE_ROUNDS",
    "RoundSpec",
    "StaircaseResult",
    "StaircaseError",
    "screen",
]


@dataclass(frozen=True)
class RoundSpec:
    """One rung of the staircase (its identity is sealed here)."""

    name: str
    pairs: int
    months: float
    early_stop: bool


# The sealed staircase (R69). A genome surviving all three has faced, cheaply
# first, 1 pair / 6 months -> 5 pairs / full era -> the unseen gauntlet.
STAIRCASE_ROUNDS: tuple[RoundSpec, ...] = (
    RoundSpec(name="screen", pairs=1, months=6.0, early_stop=True),
    RoundSpec(name="era", pairs=5, months=0.0, early_stop=True),
    RoundSpec(name="gauntlet", pairs=5, months=0.0, early_stop=False),
)


class StaircaseError(ValueError):
    """A staircase request was refused (fail-closed)."""


@dataclass
class StaircaseResult:
    """The honest funnel ledger."""

    entered: dict = field(default_factory=dict)
    passed: dict = field(default_factory=dict)
    survivors: list = field(default_factory=list)
    rounds_run: int = 0

    def to_dict(self) -> dict:
        return {
            "rounds_run": self.rounds_run,
            "entered": dict(self.entered),
            "passed": dict(self.passed),
            "survivors": len(self.survivors),
            "cheapest_first": [r.name for r in STAIRCASE_ROUNDS[: self.rounds_run]],
        }


def screen(pool, evaluators, *, rounds=STAIRCASE_ROUNDS) -> StaircaseResult:
    """Run the progressive screen.

    ``pool`` is an iterable of genomes. ``evaluators`` maps a round NAME to a
    callable ``(genome, round) -> bool`` that returns True iff the genome
    survives that round. The staircase runs rounds in order; each round sees only
    the previous round's survivors.
    """
    specs = tuple(rounds)
    if not specs:
        raise StaircaseError("the staircase needs at least one round")
    for spec in specs:
        fn = evaluators.get(spec.name)
        if not callable(fn):
            raise StaircaseError(
                f"no evaluator for round {spec.name!r} — fail-closed"
            )

    current = list(pool)
    result = StaircaseResult()
    for spec in specs:
        result.entered[spec.name] = len(current)
        if not current:
            result.passed[spec.name] = 0
            break
        fn = evaluators[spec.name]
        survivors = [g for g in current if fn(g, spec)]
        result.passed[spec.name] = len(survivors)
        result.rounds_run += 1
        current = survivors
    result.survivors = current
    return result
