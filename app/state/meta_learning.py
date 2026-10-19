"""E1 -- META-LEARNING: the state improves its own WAY of learning.

First Amendment, doctrine E1. Autonomy at the first level asks "did the state get
better?". Meta-learning asks the harder question: "did the state get better AT
GETTING BETTER?". Every learning mechanism is itself an evolution target -- the
way the state learns is not fixed, it is bred.

This module makes that measurable. Each mechanism carries a ``generativity``
reading: how good it is at producing BEHAVIOUR CHANGE (not activity, not noise).
The monthly audit ranks mechanisms by how much their generativity improved since
the prior reading, so a mechanism that has stopped teaching the state anything is
exposed -- and becomes an evolution target.

Pure at import (Scar #6): the table is data; the functions are reductions over the
readings the caller hands them.
"""

from __future__ import annotations

__all__ = [
    "LEARNING_TARGETS",
    "MECHANISM_GENERATIVITY",
    "generativity_delta",
    "meta_learning_audit",
]

# The mechanisms whose WAY of learning is itself evolvable (E1). These are the
# learning surfaces, distinct from the strategies they help breed.
LEARNING_TARGETS: tuple[str, ...] = (
    "autopsy", "tribunal", "eda", "surrogate", "probation", "bootstrap",
)

# The current generativity of each mechanism: a reading in [0, 1] of how strongly
# its output drives a BEHAVIOUR CHANGE (0 = records and changes nothing; 1 = every
# reading moves the search). These are honest, coarse, human-form readings (E5) --
# a gradient, not a pass/fail bit.
MECHANISM_GENERATIVITY: dict[str, float] = {
    "autopsy": 0.70,
    "tribunal": 0.65,
    "eda": 0.55,
    "surrogate": 0.60,
    "probation": 0.50,
    "bootstrap": 0.45,
}

# A mechanism whose generativity fell by at least this much since the prior audit
# is a META-LEARNING STALL: it is no longer teaching the state new behaviour.
STALL_DELTA: float = 0.05


def _bounded(value, *, name: str) -> float:
    """A generativity reading must be a finite number in [0, 1] (fail-closed)."""
    if value is None:
        raise ValueError(f"{name} generativity is unmeasured (never assume)")
    v = float(value)
    if not (0.0 <= v <= 1.0) or v != v:
        raise ValueError(f"{name} generativity must be in [0, 1], got {value!r}")
    return v


def generativity_delta(mechanism: str, prior: float, current: float) -> float:
    """The change in a mechanism's generativity: ``current - prior`` (both in [0,1])."""
    return round(_bounded(current, name=mechanism) - _bounded(prior, name=mechanism), 6)


def meta_learning_audit(*, prior: dict[str, float] | None = None,
                        current: dict[str, float] | None = None) -> dict:
    """The monthly meta-learning audit: which mechanisms got better at teaching?

    ``prior``/``current`` are ``mechanism -> generativity`` readings. A mechanism
    absent from either is reported UNMEASURED (never assumed). Mechanisms whose
    generativity fell by ``STALL_DELTA`` or more are named STALLED and become
    evolution targets; the highest-generativity mechanism is the TEACHER OF THE
    MONTH -- the way of learning most worth breeding from.
    """
    prior = prior if prior is not None else MECHANISM_GENERATIVITY
    current = current if current is not None else MECHANISM_GENERATIVITY

    rows: list[dict] = []
    stalled: list[str] = []
    improved: list[str] = []
    for mech in LEARNING_TARGETS:
        if mech not in prior or mech not in current:
            rows.append({"mechanism": mech, "prior": prior.get(mech),
                         "current": current.get(mech), "delta": None,
                         "reading": "unmeasured (never assumed)"})
            continue
        delta = generativity_delta(mech, prior[mech], current[mech])
        if delta <= -STALL_DELTA:
            stalled.append(mech)
        elif delta >= STALL_DELTA:
            improved.append(mech)
        rows.append({"mechanism": mech, "prior": prior[mech], "current": current[mech],
                     "delta": delta,
                     "reading": ("stalled (an evolution target)" if delta <= -STALL_DELTA
                                 else "improved" if delta >= STALL_DELTA else "steady")})

    measured = [r for r in rows if r["current"] is not None]
    teacher = (max(measured, key=lambda r: r["current"])["mechanism"]
               if measured else None)
    return {
        "doctrine": "E1 meta-learning: the state evolves its own way of learning",
        "n_targets": len(LEARNING_TARGETS),
        "targets": list(LEARNING_TARGETS),
        "rows": rows,
        "improved": improved,
        "stalled": stalled,
        "evolution_targets": stalled,  # the stalled mechanisms become evolution targets
        "teacher_of_the_month": teacher,
        "reading": (f"{len(measured)} measured; {len(improved)} improved, "
                    f"{len(stalled)} stalled; teacher={teacher}"),
    }
