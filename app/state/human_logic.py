"""E5 -- THE HUMAN LOGIC DOCTRINE: gradients, not dead binary.

First Amendment, doctrine E5. No dead binary logic anywhere. Every decision logic
is HUMAN in form -- graduated, contextual, nuanced ("very likely", "almost
exhausted", "if... then perhaps") -- and every logic is a permanent evolution
subject; none is ever finished.

This module provides the shared human-form primitives so the rest of the state
stops writing hard yes/no:

* :func:`sigmoid` -- a fixed threshold becomes a smooth curve.
* :func:`graded` -- a hard yes/no becomes a label on a gradient.
* :func:`confidence_band` -- a scalar becomes a contextual band ("almost certain"
  .. "very unlikely"), never a bare boolean.
* :func:`if_then_perhaps` -- the "if... then perhaps" connective: a conditional
  that returns a graded likelihood, not a boolean.

Fail-closed: a non-finite input is refused (a gradient off NaN is how a state
hallucinates a decision). Pure at import (Scar #6).
"""

from __future__ import annotations

import math

__all__ = [
    "GRADIENT_LABELS",
    "LOGIC_EVOLUTION_TARGETS",
    "sigmoid",
    "graded",
    "confidence_band",
    "if_then_perhaps",
]

# The gradient labels, from the strongest to the weakest reading. A binary "yes/no"
# is replaced by a point on this scale (E5).
GRADIENT_LABELS: tuple[str, ...] = (
    "almost certain", "very likely", "likely", "plausible",
    "uncertain", "unlikely", "very unlikely", "almost impossible",
)

# Every decision logic is a permanent evolution subject (E5): none is finished.
LOGIC_EVOLUTION_TARGETS: tuple[str, ...] = (
    "entry_gate", "stop_band", "parachute", "veto", "ensemble_quorum",
    "orchestra_consensus", "regime_classifier",
)


def _finite(value, *, name: str) -> float:
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite, got {value!r} (fail-closed)")
    return v


def sigmoid(x, *, k: float = 1.0, x0: float = 0.0) -> float:
    """A smooth 0..1 curve through a would-be threshold: ``1/(1+e^-k(x-x0))``.

    This is the "fixed threshold becomes a curve" primitive: ``x0`` is where the
    old hard cut lived; ``k`` sets how sharp the gradient is (``k`` large approaches
    the old binary -- but never is one).
    """
    x = _finite(x, name="x")
    k = _finite(k, name="k")
    x0 = _finite(x0, name="x0")
    z = k * (x - x0)
    # Clamp the exponent to avoid overflow; the tails are 0/1 to machine precision.
    z = max(-60.0, min(60.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def graded(value, *, x0: float = 0.0, k: float = 1.0) -> dict:
    """A scalar -> a human-form graded reading (E5), never a bare boolean.

    Returns the smooth ``score`` in [0, 1], its ``label`` on ``GRADIENT_LABELS``,
    and the ``yes``/``no`` bits as DIAGNOSTICS only -- the decision surface is the
    gradient, the bits are a convenience, and the doctrine forbids deciding on them.
    """
    score = sigmoid(value, k=k, x0=x0)
    n = len(GRADIENT_LABELS)
    # Map score in [0,1] to a label index 0 (strongest) .. n-1 (weakest).
    idx = min(n - 1, int((1.0 - score) * n))
    return {
        "score": round(score, 6),
        "label": GRADIENT_LABELS[idx],
        "yes_diagnostic": score >= 0.5,
        "reading": f"{GRADIENT_LABELS[idx]} (score {score:.3f})",
    }


def confidence_band(p, *, bands: tuple[tuple[float, str], ...] | None = None) -> str:
    """A probability -> a contextual confidence band (E5), never a boolean.

    ``bands`` is a descending list of ``(lower_bound, label)``; the first whose
    bound the probability clears wins. The default mirrors ``GRADIENT_LABELS``.
    """
    p = _finite(p, name="p")
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"p must be in [0, 1], got {p!r}")
    if bands is None:
        n = len(GRADIENT_LABELS)
        bands = tuple((1.0 - (i + 1) / n, GRADIENT_LABELS[i]) for i in range(n))
    for lower, label in bands:
        if p >= lower:
            return label
    return bands[-1][1]


def if_then_perhaps(condition_score, then_score, *, else_score: float = 0.0) -> dict:
    """The "if... then perhaps" connective: a graded conditional (E5).

    ``condition_score`` and ``then_score`` are graded readings in [0, 1]; the
    result is their soft conjunction (a product), a graded likelihood -- never a
    hard boolean. ``else_score`` is the floor when the condition is weak.
    """
    c = _finite(condition_score, name="condition_score")
    t = _finite(then_score, name="then_score")
    e = _finite(else_score, name="else_score")
    if not (0.0 <= c <= 1.0 and 0.0 <= t <= 1.0):
        raise ValueError("condition_score and then_score must be in [0, 1]")
    likelihood = c * t + (1.0 - c) * e
    return {"likelihood": round(likelihood, 6),
            "label": confidence_band(likelihood),
            "reading": f"if ({c:.2f}) then perhaps ({t:.2f}) -> {likelihood:.3f}"}
