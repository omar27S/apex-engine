"""THE FOUR HIGH PRIESTS — domain aggregators above the acolytes (Phase 3.2).

Each High Priest owns ONE domain (Trend, Mean-Reversion, Volatility, Liquidity)
and aggregates that domain's acolytes, WEIGHTED BY LIVE TRUST. The priests are the
layer between the 45 dumb acolytes and the Oracle's combiner: they turn a bag of
per-feature votes into a per-domain confidence in ``[0, 1]``.

A priest's trust is the trust of the SOLDIERS it commands in that domain (fed to
it by the runtime from the honest :class:`~app.pyramid.trust.TrustBook`). A domain
with no soldiers gets a neutral prior of 0.5 — the priest still speaks, but its
voice is unproven, and that is stated (never a silent zero).

Pure: no I/O, no clock. Deterministic given the acolyte scores and trusts.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.pyramid.oracle.acolytes import ACOLYTE_VIEWS, AcolyteView
from app.pyramid.roster import DOMAINS

__all__ = [
    "PRIEST_DOMAINS",
    "ACOLYTES_BY_DOMAIN",
    "Priest",
    "priest_outputs",
    "domain_of_acolyte",
]

PRIEST_DOMAINS: tuple[str, ...] = tuple(DOMAINS)

# Which acolyte GROUP speaks for which domain. The market view informs every
# domain; the domain-specific weighting is expressed through trust, not a hard
# partition, so every priest hears all acolytes but weights its own group higher.
_DOMAIN_GROUP: dict[str, str] = {
    "Trend": "market",
    "Mean-Reversion": "signal",
    "Volatility": "risk",
    "Liquidity": "chain",
}


def domain_of_acolyte(view: AcolyteView) -> str:
    """The domain an acolyte primarily serves (its group maps to one domain)."""
    for domain, group in _DOMAIN_GROUP.items():
        if view.group == group:
            return domain
    return "Trend"


ACOLYTES_BY_DOMAIN: dict[str, tuple[AcolyteView, ...]] = {
    d: tuple(v for v in ACOLYTE_VIEWS if domain_of_acolyte(v) == d)
    for d in PRIEST_DOMAINS
}


@dataclass(frozen=True)
class Priest:
    """One High Priest: domain, live trust, and a neutral-prior flag."""

    domain: str
    trust: float = 0.0          # trust of the soldiers this priest commands
    seated: bool = False        # at least one soldier in the domain

    def output(self, acolyte_scores: dict[str, float | None]) -> float:
        """Aggregate this domain's acolytes into a ``[0,1]`` confidence.

        Missing acolytes are dropped. If EVERY acolyte this priest would read is
        missing, the priest returns its neutral prior 0.5 (never a fabricated win).
        The trust multiplier is centered so trust 0 == neutral weight, positive
        trust raises the priest's distance from 0.5, negative trust lowers it.
        """
        own = ACOLYTES_BY_DOMAIN.get(self.domain, ())
        present = [
            acolyte_scores[v.name]
            for v in own
            if acolyte_scores.get(v.name) is not None
        ]
        base = sum(present) / len(present) if present else 0.5
        # Trust weights the priest's confidence: higher trust -> pull toward 1,
        # lower -> toward 0.5 (a proven domain speaks with conviction).
        trust_factor = 0.5 + 0.5 * (self.trust / (1.0 + abs(self.trust)))
        return min(1.0, max(0.0, 0.5 + (base - 0.5) * (0.5 + trust_factor)))


def priest_outputs(
    acolyte_scores: dict[str, float | None],
    domain_trust: dict[str, float] | None = None,
    seated_domains: set[str] | None = None,
) -> dict[str, float]:
    """The four priests' outputs, keyed by domain, in sealed domain order."""
    domain_trust = dict(domain_trust or {})
    seated = set(seated_domains or ())
    out: dict[str, float] = {}
    for domain in PRIEST_DOMAINS:
        priest = Priest(
            domain=domain,
            trust=float(domain_trust.get(domain, 0.0)),
            seated=domain in seated,
        )
        out[domain] = priest.output(acolyte_scores)
    return out
