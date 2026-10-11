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

R85 — THE GROSS-TO-FRICTION GATE (Phase 7i). Round 1 additionally applies the
sealed gross-to-friction gate (``law.gross_to_friction_verdict``): a candidate
whose GROSS edge cannot pay FRICTION_MULTIPLE (3.0) times the friction it was
invoiced is rejected in the CHEAP round, before it can cost the expensive ones. A
`FrictionGate` is supplied by the caller (it reports gross_r + friction_r + the
verdict); its rejections are counted and explained in ``StaircaseResult`` so the
gate is NEVER a silent killer.

Fail-closed (Scar #1): a round with no evaluator is refused; a pool that empties
stops there (the honest outcome), it does not re-run.

Pure at import; no I/O, no loop beyond the bounded pool x rounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core import law

__all__ = [
    "STAIRCASE_ROUNDS",
    "RoundSpec",
    "StaircaseResult",
    "StaircaseError",
    "FrictionGate",
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
    friction_rejected: int = 0            # R85 — count rejected by the gate
    friction_reasons: dict = field(default_factory=dict)  # R85 — reason -> count

    def to_dict(self) -> dict:
        return {
            "rounds_run": self.rounds_run,
            "entered": dict(self.entered),
            "passed": dict(self.passed),
            "survivors": len(self.survivors),
            "cheapest_first": [r.name for r in STAIRCASE_ROUNDS[: self.rounds_run]],
            # R85 — the gate reports its rejections; a silent killer is forbidden.
            "friction_gate": {
                "multiple": law.FRICTION_MULTIPLE,
                "rejected": self.friction_rejected,
                "reasons": dict(sorted(self.friction_reasons.items())),
            },
        }


@dataclass(frozen=True)
class FrictionGate:
    """R85 — a round-1 gate reading: the gross edge and the friction it was invoiced.

    ``gross_r`` and ``friction_r`` are computed by the caller's evaluator (the
    staircase does not run the engine). The sealed ruling lives in
    ``law.gross_to_friction_verdict`` — the staircase only counts and reports.
    """

    gross_r: float
    friction_r: float

    def verdict(self):
        from app.core.law import gross_to_friction_verdict

        return gross_to_friction_verdict(self.gross_r, self.gross_r - self.friction_r)


def screen(pool, evaluators, *, rounds=STAIRCASE_ROUNDS, friction_gate=None) -> StaircaseResult:
    """Run the progressive screen.

    ``pool`` is an iterable of genomes. ``evaluators`` maps a round NAME to a
    callable ``(genome, round) -> bool`` that returns True iff the genome
    survives that round. The staircase runs rounds in order; each round sees only
    the previous round's survivors.

    R85: when ``friction_gate`` is supplied it is a callable ``genome -> FrictionGate
    | None`` consulted at the FIRST round (the cheap screen). ``None`` means the
    gate did not speak (no data — do not block); a returned gate that fails the
    sealed verdict rejects the genome and its reason is counted for the report.
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
        survivors = []
        for g in current:
            # R85 — the gross-to-friction gate applies at round 1 only. It runs
            # before the (still cheap) round-1 evaluation, so a body that cannot
            # pay friction never spends even the screen.
            if spec is specs[0] and callable(friction_gate):
                gate = friction_gate(g)
                if gate is not None:
                    v = gate.verdict()
                    if not v.ok:
                        result.friction_rejected += 1
                        key = f"gross={v.gross_r:.1f}|friction={v.friction_r:.1f}|{v.reason}"
                        result.friction_reasons[key] = result.friction_reasons.get(key, 0) + 1
                        continue
            if fn(g, spec):
                survivors.append(g)
        result.passed[spec.name] = len(survivors)
        result.rounds_run += 1
        current = survivors
    result.survivors = current
    return result
