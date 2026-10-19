"""THE LEARNING AUDIT — which learning mechanisms actually close the loop.

Charter act 5. Autonomy means getting BETTER, not busier: a mechanism that records
a failure but changes nothing is a LOOP-LEAKER; a mechanism whose failure output
feeds back into behaviour (breeding, quotas, next-night decisions, hypothesis
generation) is a LOOP-CLOSER.

This module is the inventory and the classification, made executable. A leak is
fixed when its output is WIRED to a consumer — ``closes_the_loop`` proves that by
requiring a named consumer symbol, not a vibe.

Pure at import (Scar #6): the tables are constants; the functions are reductions.
"""

from __future__ import annotations

__all__ = [
    "LEARNING_MECHANISMS",
    "loop_closers",
    "loop_leakers",
    "closes_the_loop",
    "learning_audit",
]

# (mechanism, produces, consumer). ``consumer`` is the code that ACTS on the
# output. ``consumer is None`` => the output is recorded and nothing reads it =>
# a LOOP-LEAKER. This table is the honest audit; it names real modules.
LEARNING_MECHANISMS: tuple[dict, ...] = (
    {"mechanism": "autopsy", "module": "app.quant.autopsy",
     "produces": "death causes per trade",
     "consumer": "app.quant.tribunal.autopsy_weight_delta", "loop": "closer"},
    {"mechanism": "tribunal", "module": "app.quant.tribunal",
     "produces": "weight deltas from autopsies",
     "consumer": "app.factory.staircase", "loop": "closer"},
    {"mechanism": "eda", "module": "app.factory.eda",
     "produces": "distribution candidates",
     "consumer": "app.factory.cma", "loop": "closer"},
    {"mechanism": "surrogate", "module": "app.factory.surrogate",
     "produces": "skip/hit gate on cheap fitness",
     "consumer": "app.quant.tournament.run", "loop": "closer"},
    {"mechanism": "probation", "module": "app.factory.probation",
     "produces": "quota ruling from ensemble history",
     "consumer": "tools.run_dual_tournament._probation_decision", "loop": "closer"},
    # act 4 — the bootstrap was the one LOOP-LEAKER. It produced a long-run
    # distribution that nothing read. It is now FIXED: tools.champion_session_7
    # .stability_verdict consumes it and GATES the champion's promotion.
    {"mechanism": "bootstrap", "module": "tools.champion_session_7",
     "produces": "long-run distribution on the pooled trade stream",
     "consumer": "tools.champion_session_7.stability_verdict", "loop": "closer"},
)


def closes_the_loop(mechanism: dict) -> bool:
    """A mechanism closes the loop iff it names a real consumer."""
    return bool(mechanism.get("consumer"))


def loop_closers(mechanisms=LEARNING_MECHANISMS) -> list[dict]:
    return [m for m in mechanisms if closes_the_loop(m)]


def loop_leakers(mechanisms=LEARNING_MECHANISMS) -> list[dict]:
    return [m for m in mechanisms if not closes_the_loop(m)]


def learning_audit(*, fixed: tuple[str, ...] = ()) -> dict:
    """The charter's learning audit: closers vs leakers, and leaks FIXED this phase.

    ``fixed`` names mechanisms whose leak was repaired this phase (their consumer
    is now wired) — the audit moves them from leaker to closer.
    """
    mechanisms = []
    for m in LEARNING_MECHANISMS:
        m = dict(m)
        if m["mechanism"] in fixed:
            m["consumer"] = m.get("consumer") or "wired-this-phase"
            m["loop"] = "closer"
            m["fixed_this_phase"] = True
        mechanisms.append(m)
    leakers = [m for m in mechanisms if not closes_the_loop(m)]
    return {
        "n_mechanisms": len(mechanisms),
        "n_closers": len(mechanisms) - len(leakers),
        "n_leakers": len(leakers),
        "closers": [m["mechanism"] for m in mechanisms if closes_the_loop(m)],
        "leakers": [m["mechanism"] for m in leakers],
        "fixed_this_phase": list(fixed),
        "leaker_detail": leakers,
        "reading": ("every mechanism changes behaviour" if not leakers else
                    f"{len(leakers)} leaker(s): {[m['mechanism'] for m in leakers]}"),
    }
