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
    "SECOND_SIGHT_WEIGHT",
    "OracleWeights",
    "OracleVerdict",
    "combine",
    "score",
    "second_sight",
    "uniform_weights",
]

UNCALIBRATED_NOTE: str = (
    "AOS is UNCALIBRATED v1 — a RANKING, not a probability. "
    "Reliability-binning calibration is deferred to Phase 3.3."
)

# C3 — THE ORACLE'S SECOND SIGHT. The AOS consumes the One Brain's cognitive
# package (intuition confidence, emotion, simulation coverage, theory survival) as
# extra scoring features. The blend weight is SMALL: the 45 acolytes remain the
# spine of the score; cognition informs it. The brain and the scorer become one,
# without either erasing the other.
SECOND_SIGHT_WEIGHT: float = 0.25

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
    second_sight: dict | None = None        # C3 — the brain's cognitive view
    uncalibrated: bool = True
    note: str = UNCALIBRATED_NOTE

    def to_dict(self) -> dict:
        return {
            "aos": self.aos,
            "acolyte_missing": list(self.acolyte_missing),
            "priest_outputs": dict(self.priest_outputs),
            "evidence": self.evidence,
            "second_sight": self.second_sight,
            "uncalibrated": self.uncalibrated,
            "note": self.note,
        }


def combine(
    acolyte_scores: dict[str, float | None],
    priests: dict[str, float],
    weights: OracleWeights | None = None,
    cognitive: dict | None = None,
) -> "tuple[float, float, tuple[str, ...]]":
    """Weighted-logistic combination -> ``(aos, evidence, missing_names)``.

    Missing acolytes (``None``) are DROPPED and reported. If EVERY acolyte is
    missing AND there is no usable evidence, the function FAILS CLOSED: it raises
    ``ValueError`` rather than emit a confident default. An Oracle with no eyes
    must not guess.

    C3 — when ``cognitive`` (the One Brain's package for this candidate) is given,
    the AOS is blended with the Oracle's SECOND SIGHT over it: the acolyte consensus
    stays the spine (weight ``1 - SECOND_SIGHT_WEIGHT``) and cognition informs the
    rest. Without a cognitive package the AOS is unchanged (honest).
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
    aos = _logistic(normalized)
    if cognitive:
        ss = second_sight(cognitive)
        if ss["score"] is not None:
            aos = ((1.0 - SECOND_SIGHT_WEIGHT) * aos
                   + SECOND_SIGHT_WEIGHT * float(ss["score"]))
    return aos, evidence, tuple(missing)


def second_sight(cognitive: dict | None) -> dict:
    """C3 — the Oracle's SECOND SIGHT over a cognitive package (the brain's view).

    Blends the package's measured features into a single ``[0,1]`` score:
    intuition confidence (how strong the gut), theory survival (is the claim alive),
    simulation coverage (were the fragile points covered), and emotion (a calm mind
    scores higher than a fearful one). FEELING and DREAM are taken at their tongue
    weight — a feeling INFORMS the score, it never dominates it.

    Honest: with no measured feature the score is ``None`` (the second sight is
    silent), never a neutral 0.5 masquerading as knowledge.
    """
    if not cognitive:
        return {"score": None, "features": {}, "n": 0,
                "reading": "seconda vista silenziosa (nessun pacchetto cognitivo)"}
    feats: dict[str, float] = {}
    intr = cognitive.get("intuition") or {}
    conf = intr.get("confidence")
    if isinstance(conf, (int, float)):
        # A bullish gut informs fully; a bearish gut lowers the second sight.
        seen, up = intr.get("seen"), intr.get("up")
        bearish = isinstance(seen, int) and seen > 0 and isinstance(up, int) \
            and up * 2 < seen
        feats["intuition"] = float(conf) * (0.3 if bearish else 1.0)
    theory = cognitive.get("theory") or {}
    status = str(theory.get("status", ""))
    if status:
        feats["theory"] = {"supported": 1.0, "untested": 0.5,
                           "weakening": 0.35, "falsified": 0.0}.get(status, 0.5)
    sim = cognitive.get("simulation") or {}
    if sim.get("fragile_points"):
        covered = cognitive.get("covered")
        if covered is not None:
            feats["simulation"] = (len(set(covered) & set(sim["fragile_points"]))
                                   / len(sim["fragile_points"]))
        else:
            feats["simulation"] = 0.5
    emo = cognitive.get("emotion")
    if emo:
        from app.civilization import tongue as _tg
        base = {"calm": 0.7, "excitement": 0.6, "disgust": 0.4, "fear": 0.2}.get(
            str(emo), 0.5)
        feats["emotion"] = base * _tg.MODALITY_WEIGHTS[_tg.FEEL]
    if not feats:
        return {"score": None, "features": {}, "n": 0,
                "reading": "seconda vista silenziosa (nessun tratto misurato)"}
    score = round(sum(feats.values()) / len(feats), 6)
    return {"score": min(1.0, max(0.0, score)), "features": feats, "n": len(feats),
            "reading": f"seconda vista: {score:.3f} su {len(feats)} tratto/i"}


def score(
    ctx: OracleContext,
    *,
    weights: OracleWeights | None = None,
    domain_trust: dict[str, float] | None = None,
    seated_domains: set[str] | None = None,
    cognitive: dict | None = None,
) -> OracleVerdict:
    """Score one candidate: acolytes -> priests -> combiner -> the AOS.

    C3 — when a ``cognitive`` package (the One Brain's view of this candidate) is
    given, the AOS is blended with the Oracle's second sight over it.
    """
    a_scores = score_acolytes(ctx)
    p_out = priest_outputs(a_scores, domain_trust, seated_domains)
    aos, evidence, missing = combine(a_scores, p_out, weights, cognitive=cognitive)
    return OracleVerdict(
        aos=aos,
        acolyte_scores=a_scores,
        acolyte_missing=missing,
        priest_outputs=p_out,
        evidence=evidence,
        second_sight=(second_sight(cognitive) if cognitive else None),
    )
