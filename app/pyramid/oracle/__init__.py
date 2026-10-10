"""THE ORACLE — Rank 0 made real (Phase 3.2).

The Oracle is the pyramid's confidence brain. It answers one question per candidate
signal: "how much evidence is there that this signal is worth taking?" — and answers
it with a single number, the AOS, in ``[0, 1]``.

Its layers, bottom to top:

1. **45 ACOLYTES** (:mod:`acolytes`) — pure, deterministic views of one feature each;
2. **4 HIGH PRIESTS** (:mod:`priests`) — one per domain, weighting their acolytes by
   LIVE TRUST;
3. **THE COMBINER** (:mod:`combiner`) — a weighted-logistic (Bayesian-ish) integral
   emitting the AOS.

HONEST LIMITS (stated, never implied):

* The AOS is **UNCALIBRATED v1** — a ranking, not a probability. Calibration by
  reliability bins is Phase 3.3.
* Weights start UNIFORM. Phase 4's self-coding engine may move WEIGHTS only, through
  the sanctioned evolution path — never the combiner code (hard rule).

Build Mode: pure. Import-time it builds the 45 views once (deterministic); no I/O,
no servers, no loops beyond that build.
"""

from __future__ import annotations

from app.pyramid.oracle.acolytes import (
    ACOLYTE_COUNT,
    ACOLYTE_VIEWS,
    AcolyteView,
    acolyte_names,
    score_acolytes,
)
from app.pyramid.oracle.combiner import (
    UNCALIBRATED_NOTE,
    OracleVerdict,
    OracleWeights,
    combine,
    score,
    uniform_weights,
)
from app.pyramid.oracle.context import OracleContext
from app.pyramid.oracle.priests import (
    PRIEST_DOMAINS,
    Priest,
    priest_outputs,
)

__all__ = [
    "ACOLYTE_COUNT",
    "ACOLYTE_VIEWS",
    "AcolyteView",
    "PRIEST_DOMAINS",
    "Priest",
    "OracleContext",
    "OracleVerdict",
    "OracleWeights",
    "UNCALIBRATED_NOTE",
    "acolyte_names",
    "score_acolytes",
    "priest_outputs",
    "combine",
    "score",
    "uniform_weights",
]
