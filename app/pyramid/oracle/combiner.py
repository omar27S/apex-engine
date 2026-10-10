"""THE ORACLE COMBINER — the Bayesian-ish brain over acolytes and priests (3.2).

The Oracle turns the 45 acolyte scores and the 4 priest outputs into ONE number:
the **AOS** ("Apex Oracle Score") in ``[0, 1]``, per candidate signal.

HOW IT COMBINES. It is a weighted LOGIT-AND-NORMAL integral, not a black box:

1. Each input (acolyte or priest) contributes its score as evidence in log-odds.
   A score ``s`` maps to log-odds ``log(s / (1 - s))`` with a small clip so 0/1 do
   not blow up. Neutral 0.5 -> 0 evidence; confidently good -> strong positive.
2. Weights start UNIFORM (one weight per input). The weighted evidence is summed
   and passed through a logistic. This is exactly a weighted logistic combiner: a
   naive-Bayes-shaped aggregate whose inputs are independent-ish votes.
3. The result is a ranking score, NOT a calibrated probability.

WEIGHTS ARE SANCTIONED-EVOLUTION-ONLY. Phase 4's self-coding engine may adjust the
WEIGHTS through the sanctioned evolution path (a versioned weight vector). It may
NOT rewrite this combiner, and it may NOT touch the acolyte/priest definitions
without a sealed commit. The hard rule is documented here and asserted structurally:
:func:`combine` takes its weights as data and never mutates its own code path.

CALIBRATION HONESTY. This is the UNCALIBRATED v1. The AOS is a RANKING, not a
probability; a reliability-binning calibration layer is deferred to Phase 3.3. The
muster report says so, loudly, every time.

Determinism. Given the same inputs and weights, the AOS is bit-identical. The
combiner uses no randomness.

Pure: no I/O, no clock, no services.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.pyramid.oracle.acolytes import ACOLYTE_VIEWS, score_acolytes
from app.pyramid.oracle.context import OracleContext
from app.pyramid.oracle.priests import PRIEST_DOMAINS, priest_outputs

__all__ = [
    "UNCALIBRATED_NOTE",
    "OracleWeights",
    "OracleVerdict",
    "combine",
    "score",
    "uniform_weights",
]

UNCALIBRATED_NOTE: str = (
    "AOS is UNCALIBRATED v1 — a RANKING, not a probability. "
    "Reliability-binning calibration is deferred to Phase 3.3."
)

# Clip so a 0/1 acolyte score does not send the log-odds to infinity.
_EPS: float = 1e-3


def _logit(score: float) -> float:
    s = min(1.0 - _EPS, max(_EPS, float(score)))
    return math.log(s / (1.0 - s))


def _logistic(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass(frozen=True)
class OracleWeights:
    """The Oracle's weight vector — uniform by default.

    ``acolyte`` maps acolyte name -> weight; ``priest`` maps domain -> weight;
    ``bias`` is the prior log-odds (0 == neutral 0.5 prior). Weights are DATA:
    Phase 4 may evolve them via the sanctioned path, never by editing the combiner.
    """

    acolyte: dict[str, float] = field(default_factory=dict)
    priest: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0

    def weight_for(self, name: str) -> float:
        return float(self.acolyte.get(name, 1.0))

    def priest_weight(self, domain: str) -> float:
        return float(self.priest.get(domain, 1.0))


def uniform_weights(acolyte_scale: float = 1.0, priest_scale: float = 1.0) -> OracleWeights:
    """Uniform weights: every acolyte ``acolyte_scale``, every priest ``priest_scale``."""
    return OracleWeights(
        acolyte={v.name: acolyte_scale for v in ACOLYTE_VIEWS},
        priest={d: priest_scale for d in PRIEST_DOMAINS},
        bias=0.0,
    )


@dataclass(frozen=True)
class OracleVerdict:
    """The Oracle's judgement of one candidate signal."""

    aos: float                              # final Apex Oracle Score in [0,1]
    acolyte_scores: dict[str, float | None]
    acolyte_missing: tuple[str, ...]
    priest_outputs: dict[str, float]
    evidence: float                         # summed weighted log-odds (diagnostic)
    uncalibrated: bool = True
    note: str = UNCALIBRATED_NOTE

    def to_dict(self) -> dict:
        return {
            "aos": self.aos,
            "acolyte_missing": list(self.acolyte_missing),
            "priest_outputs": dict(self.priest_outputs),
            "evidence": self.evidence,
            "uncalibrated": self.uncalibrated,
            "note": self.note,
        }


def combine(
    acolyte_scores: dict[str, float | None],
    priests: dict[str, float],
    weights: OracleWeights | None = None,
) -> "tuple[float, float, tuple[str, ...]]":
    """Weighted-logistic combination -> ``(aos, evidence, missing_names)``.

    Missing acolytes (``None``) are DROPPED and reported. If EVERY acolyte is
    missing AND there is no usable evidence, the function FAILS CLOSED: it raises
    ``ValueError`` rather than emit a confident default. An Oracle with no eyes
    must not guess.
    """
    weights = weights or uniform_weights()
    missing: list[str] = []
    evidence = float(weights.bias)
    total_weight = 0.0

    present = 0
    for view in ACOLYTE_VIEWS:
        s = acolyte_scores.get(view.name)
        if s is None:
            missing.append(view.name)
            continue
        w = weights.weight_for(view.name)
        evidence += w * _logit(s)
        total_weight += w
        present += 1

    for domain in PRIEST_DOMAINS:
        p = priests.get(domain)
        if p is None:
            continue
        w = weights.priest_weight(domain)
        evidence += w * _logit(p)
        total_weight += w
        present += 1

    if present == 0:
        raise ValueError(
            "the Oracle has no usable evidence (all acolytes and priests missing) — "
            "failing closed rather than emitting a default (Scar #1)"
        )
    # Weighted AVERAGE of the input log-odds (normalized by the total weight of
    # present inputs), so the AOS is a bounded consensus, not a sum that saturates
    # as more inputs agree. bias is added AFTER normalization as a prior.
    normalized = (evidence / total_weight) if total_weight > 0 else evidence
    normalized += float(weights.bias)
    return _logistic(normalized), evidence, tuple(missing)


def score(
    ctx: OracleContext,
    *,
    weights: OracleWeights | None = None,
    domain_trust: dict[str, float] | None = None,
    seated_domains: set[str] | None = None,
) -> OracleVerdict:
    """Score one candidate: acolytes -> priests -> combiner -> the AOS."""
    a_scores = score_acolytes(ctx)
    p_out = priest_outputs(a_scores, domain_trust, seated_domains)
    aos, evidence, missing = combine(a_scores, p_out, weights)
    return OracleVerdict(
        aos=aos,
        acolyte_scores=a_scores,
        acolyte_missing=missing,
        priest_outputs=p_out,
        evidence=evidence,
    )
