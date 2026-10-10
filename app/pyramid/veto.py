"""THE META-LABEL VETO — the second brain that protects the account (Phase 3.2).

Where the Oracle says "how good does this signal look?", the VETO says "even so,
should the account take it?" It is the Phase-8 "Cervello del Veto", made real.

HOW IT LEARNS. The veto trains a tiny LOGISTIC REGRESSION on the honest judge's
own outcomes: each training row is one evaluated signal's ~8 FEATURES (AOS, domain
agreement, session, regime percentile, trust, funnel stage, family density class,
spread state) labelled by whether that signal's trade ended NET-POSITIVE (R17/R22
lineage — the label is NET R, never gross). The model is fit by plain gradient
descent; there is no external ML dependency.

WHAT IT DOES. At decision time the veto computes ``P(net-win | features)`` and, if
it is below :data:`DEFAULT_VETO_THRESHOLD`, the signal is VETOED (a yes/no gate).
Every veto is COUNTED per family/domain and enters the funnel report — nothing is
blocked silently.

WHAT IT NEVER DOES. The veto NEVER touches position sizing and NEVER alters the law.
It does not change the 1% Titanium Floor, the stop band, or the reward:risk gate;
those are the Constitution, and the veto is downstream of them. A test asserts the
veto's public surface carries no sizing field.

SELF-AUDIT. Performance is tracked as a confusion matrix over the signals it saw:
*would-have-won-but-vetoed* (a false veto — the costly mistake) and
*would-have-lost-and-vetoed* (a correct veto). A veto that vetoes winners is
surfaced to the tribunal so its THRESHOLD can be re-examined — never silently tuned.

Pure: deterministic given the training rows and seed (the fit is seeded, no RNG
beyond a fixed zero-initialization). No I/O, no services, no clock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "VETO_FEATURES",
    "DEFAULT_VETO_THRESHOLD",
    "FEATURE_NAMES",
    "VetoFeatures",
    "VetoModel",
    "VetoAudit",
    "clamp_threshold",
]

# The ~8 honest features (law-adjacent: pinned, closed set, order is the vector order).
VETO_FEATURES: tuple[str, ...] = (
    "aos",                # 1. the Oracle's score
    "domain_agreement",   # 2. do domain and priest votes agree
    "session",            # 3. session id, normalized
    "regime_percentile",  # 4. regime percentile
    "trust",              # 5. live trust
    "funnel_stage",       # 6. survival fraction through the funnel
    "density_class",      # 7. family density class [0,1]
    "spread_state",       # 8. spread health [0,1]
)
FEATURE_NAMES = VETO_FEATURES

# The default decision threshold: below this P(net-win) a signal is vetoed.
DEFAULT_VETO_THRESHOLD: float = 0.5


def clamp_threshold(t: float) -> float:
    """Clamp a threshold into the safe open interval (0, 1).

    Fail-closed: a threshold <= 0 would veto EVERYTHING (an account that never
    trades), and >= 1 would veto NOTHING (a veto that never fires). Both are
    refused by clamping into (EPS, 1-EPS), and the caller is told the realized
    value so the clamp is never silent.
    """
    eps = 1e-4
    try:
        v = float(t)
    except (TypeError, ValueError):
        return DEFAULT_VETO_THRESHOLD
    if v != v:  # NaN
        return DEFAULT_VETO_THRESHOLD
    return min(1.0 - eps, max(eps, v))


@dataclass(frozen=True)
class VetoFeatures:
    """The veto's feature vector for one signal. Missing -> None (dropped to 0.5)."""

    aos: float = 0.5
    domain_agreement: float = 0.5
    session: float = 0.5
    regime_percentile: float = 0.5
    trust: float = 0.5
    funnel_stage: float = 0.5
    density_class: float = 0.5
    spread_state: float = 0.5

    def vector(self) -> tuple[float, ...]:
        out = []
        for name in FEATURE_NAMES:
            v = getattr(self, name)
            if v is None or v != v:
                out.append(0.5)
            else:
                out.append(min(1.0, max(0.0, float(v))))
        return tuple(out)


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass
class VetoModel:
    """A tiny logistic regression: weights + bias, fit on labelled signals."""

    weights: tuple[float, ...] = field(default_factory=lambda: tuple(0.0 for _ in FEATURE_NAMES))
    bias: float = 0.0
    threshold: float = DEFAULT_VETO_THRESHOLD
    trained: bool = False
    training_rows: int = 0

    # -- training -----------------------------------------------------------
    def fit(
        self,
        rows: list[tuple[VetoFeatures, int]],
        *,
        epochs: int = 200,
        lr: float = 0.1,
        l2: float = 1e-3,
    ) -> "VetoModel":
        """Fit on ``(features, label)`` rows; label 1 == net-win (R17/R22)."""
        data = [(f.vector(), int(1 if y > 0 else 0)) for f, y in rows]
        d = len(FEATURE_NAMES)
        w = [0.0] * d
        b = 0.0
        n = max(1, len(data))
        for _ in range(max(0, int(epochs))):
            gw = [0.0] * d
            gb = 0.0
            for x, y in data:
                p = _sigmoid(sum(w[i] * x[i] for i in range(d)) + b)
                err = p - y
                for i in range(d):
                    gw[i] += err * x[i]
                gb += err
            for i in range(d):
                w[i] -= lr * (gw[i] / n + l2 * w[i])
            b -= lr * (gb / n)
        self.weights = tuple(w)
        self.bias = b
        self.training_rows = len(data)
        self.trained = len(data) > 0
        return self

    # -- inference ----------------------------------------------------------
    def probability(self, features: VetoFeatures) -> float:
        """``P(net-win | features)`` — bounded in (0,1), monotone in weighted score."""
        x = features.vector()
        z = sum(self.weights[i] * x[i] for i in range(len(FEATURE_NAMES))) + self.bias
        return _sigmoid(z)

    def vetoes(self, features: VetoFeatures) -> bool:
        """True iff the signal is vetoed (P(net-win) < threshold).

        An UNTRAINED model NEVER vetoes: with no evidence it cannot protect the
        account by blocking, and a silent untrained veto would be a lie.
        """
        if not self.trained:
            return False
        return self.probability(features) < clamp_threshold(self.threshold)

    def to_dict(self) -> dict:
        return {
            "weights": list(self.weights),
            "bias": self.bias,
            "threshold": self.threshold,
            "trained": self.trained,
            "training_rows": self.training_rows,
        }


@dataclass
class VetoAudit:
    """The veto's self-audit: a confusion matrix and per-family/domain veto counts."""

    threshold: float = DEFAULT_VETO_THRESHOLD
    vetoed_total: int = 0
    passed_total: int = 0
    # confusion over signals whose true NET outcome is known:
    would_have_won_but_vetoed: int = 0   # false veto — the costly mistake
    would_have_lost_and_vetoed: int = 0  # correct veto
    would_have_won_and_passed: int = 0   # correct pass
    would_have_lost_but_passed: int = 0  # missed loss
    vetoed_by_family: dict[str, int] = field(default_factory=dict)
    vetoed_by_domain: dict[str, int] = field(default_factory=dict)

    def observe(
        self, *, vetoed: bool, net_win: bool | None, family: str = "", domain: str = ""
    ) -> None:
        """Record one decision. ``net_win`` may be None if the outcome is unknown."""
        if vetoed:
            self.vetoed_total += 1
            self.vetoed_by_family[family] = self.vetoed_by_family.get(family, 0) + 1
            self.vetoed_by_domain[domain] = self.vetoed_by_domain.get(domain, 0) + 1
        else:
            self.passed_total += 1
        if net_win is None:
            return
        if vetoed and net_win:
            self.would_have_won_but_vetoed += 1
        elif vetoed and not net_win:
            self.would_have_lost_and_vetoed += 1
        elif not vetoed and net_win:
            self.would_have_won_and_passed += 1
        else:
            self.would_have_lost_but_passed += 1

    @property
    def false_veto_rate(self) -> float:
        """Fraction of vetoed signals that would have won (lower is better)."""
        if self.vetoed_total == 0:
            return 0.0
        return self.would_have_won_but_vetoed / self.vetoed_total

    def to_dict(self) -> dict:
        return {
            "threshold": self.threshold,
            "vetoed_total": self.vetoed_total,
            "passed_total": self.passed_total,
            "would_have_won_but_vetoed": self.would_have_won_but_vetoed,
            "would_have_lost_and_vetoed": self.would_have_lost_and_vetoed,
            "would_have_won_and_passed": self.would_have_won_and_passed,
            "would_have_lost_but_passed": self.would_have_lost_but_passed,
            "false_veto_rate": self.false_veto_rate,
            "vetoed_by_family": dict(self.vetoed_by_family),
            "vetoed_by_domain": dict(self.vetoed_by_domain),
        }
