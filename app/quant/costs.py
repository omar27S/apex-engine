"""THE FRICTION LAYER — what the broker charges before the market pays (R18).

R17 NET-R DOCTRINE: ranking is on NET R. A genome that wins by less than it pays
is a loser, and this module is what makes that visible. Gross R survives only as a
diagnostic field in reports; it may never decide survival, titles, or breeding.

R18 COSTS ARE LAW-ADJACENT. Every assumption below is documented in place — its
source, its conservativeness DIRECTION, and its date — and the whole sealed model
is pinned by SHA-256 (see ``tests/quant/test_costs.py``). Changing a spread or a
slippage figure is a DELIBERATE commit: edit the constant, recompute the manifest
hash, and update the pin in the same commit, so the diff records intent. A silent
edit fails the suite.

R20 — TWO BOOKS, ONE JUDGE. There are two sealed books:

* **CONSERVATIVE** (``CONSERVATIVE_COST_MODEL``) — wider spreads, worse slippage.
  This is the SELECTION book: every rank, every promotion, every exile is decided
  against it. "Survive it and you survive reality." See ``SELECTION_COST_MODEL``.
* **REALISTIC** (``REALISTIC_COST_MODEL``) — tighter spreads, gentler slippage.
  REPORTING ONLY. It may describe a run; it may NEVER rank one. Selection is
  structurally barred from it by :func:`require_selection_book`.

Both books are hash-pinned (R18). Phase 6 live quotes replace the REALISTIC book
only, by deliberate commit; the conservative book stays as the survival margin.

DEBT-010 — BID-ONLY DATA. The historical tape is bid-derived; there is no live
ask. The spreads below are therefore CONSERVATIVE STATIC PROXIES, not measured.
They are pessimism in the safe direction (round-trip cost is charged once, in
full, at the worst plausible level) and they are explicitly TEMPORARY: Phase 6
broker specs replace them with live measured spreads and commissions. They must
be REPLACED there, never silently patched here.

PESSIMISM BY CONSTRUCTION:
- Entry slips AGAINST the position by ``slippage_pips``.
- A stop exit slips AGAINST by ``stop_slippage_pips`` (stops fill late in fast
  tape — worse than targets); a target exit fills clean.
- The full spread is charged once per round trip.
- Commission is charged per lot when set; today it is 0.0 BY DOCUMENTED ASSUMPTION
  (see below), never a silent zero.

So ``net_r = gross_r - cost_r`` with ``cost_r >= 0`` always: costs can never
IMPROVE a trade. That invariant is property-tested.

Pure: no I/O, no services, no global mutable state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.core.constellation import CONSTELLATION_PAIRS
from app.quant.engine import EXIT_GAP_STOP, EXIT_STOP

__all__ = [
    "CostModel",
    "CONSERVATIVE_COST_MODEL",
    "REALISTIC_COST_MODEL",
    "SELECTION_COST_MODEL",
    "REPORTING_COST_MODEL",
    "DEFAULT_COST_MODEL",
    "STOP_EXIT_REASONS",
    "BOOKS",
    "is_selection_book",
    "require_selection_book",
    "manifest_digest",
    "book_digests",
    "round_trip_cost_r",
    "net_r_after_costs",
]

# Exit reasons that fill AGAINST the position (stops, including gap stops). A
# target/time exit fills clean. Single source: the engine's reason constants.
STOP_EXIT_REASONS: frozenset[str] = frozenset({EXIT_STOP, EXIT_GAP_STOP})

# ---------------------------------------------------------------------------
# THE CONSERVATIVE BOOK — the SELECTION book (R20). MAJORS tight, core CROSSES
# wider, JPY crosses widest. Every number is ROUNDED UP.
#
# These are conservative retail-ECN spread proxies, as-of 2025-01-01, in pips.
# They are EXOGENOUS market inputs (not derivable quantities), so they are a
# deliberate table — unlike pip value, which is computed. The keys are validated
# against the sealed Constellation by ``_validate_spread_table``, so no stray
# pair can enter.
# ---------------------------------------------------------------------------
_CONSERVATIVE_SPREAD_PIPS: dict[str, float] = {
    # majors
    "EURUSD": 0.8,
    "GBPUSD": 1.0,
    "USDJPY": 0.9,
    "USDCHF": 1.2,
    "AUDUSD": 1.0,
    "USDCAD": 1.2,
    "NZDUSD": 1.5,
    # core crosses (non-JPY)
    "EURGBP": 1.5,
    "EURCHF": 1.8,
    "EURAUD": 2.0,
    # core crosses (JPY)
    "EURJPY": 1.5,
    "GBPJPY": 2.0,
    "AUDJPY": 1.8,
    "CADJPY": 2.0,
    "NZDJPY": 2.2,
}

# ---------------------------------------------------------------------------
# THE REALISTIC BOOK — the REPORTING book (R20), never the judge. Tighter
# spreads (the tight end of a liquid ECN), gentler slippage. It exists to
# describe a run for the CEO; it may never rank one. Phase 6 replaces THIS book
# with live measured spreads, by deliberate commit.
#
# Rule enforced by test: every realistic spread is STRICTLY TIGHTER than the
# conservative spread for the same pair, and realistic slippage is no worse.
# Selection is therefore always harder than reporting — survival margin, not
# a fait accompli.
# ---------------------------------------------------------------------------
_REALISTIC_SPREAD_PIPS: dict[str, float] = {
    # majors
    "EURUSD": 0.2,
    "GBPUSD": 0.3,
    "USDJPY": 0.2,
    "USDCHF": 0.4,
    "AUDUSD": 0.3,
    "USDCAD": 0.4,
    "NZDUSD": 0.6,
    # core crosses (non-JPY)
    "EURGBP": 0.5,
    "EURCHF": 0.7,
    "EURAUD": 0.8,
    # core crosses (JPY)
    "EURJPY": 0.5,
    "GBPJPY": 0.8,
    "AUDJPY": 0.7,
    "CADJPY": 0.8,
    "NZDJPY": 0.9,
}


def _validate_spread_table(table: Mapping[str, float]) -> None:
    """Fail-closed: the table must cover EXACTLY the Constellation, all positive."""
    keys = set(table)
    expected = set(CONSTELLATION_PAIRS)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        raise ValueError(
            f"spread table must cover the Constellation exactly: "
            f"missing={missing} extra={extra}"
        )
    for pair, value in table.items():
        if not (isinstance(value, (int, float)) and value > 0.0):
            raise ValueError(f"spread for {pair} must be a positive number, got {value!r}")


_validate_spread_table(_CONSERVATIVE_SPREAD_PIPS)
_validate_spread_table(_REALISTIC_SPREAD_PIPS)


@dataclass(frozen=True)
class CostModel:
    """The sealed friction model: spreads, slippage, commission (R18/R20).

    All values are PESSIMISTIC in direction. ``spread_pips`` maps every canonical
    Constellation pair to its static round-trip spread; a lookup for an unknown
    pair fails closed (loud), never a default.

    ``book`` is ``"selection"`` (the conservative book, R20) or ``"reporting"``
    (the realistic book). Only a selection book may rank a candidate; see
    :func:`require_selection_book`.
    """

    name: str
    spread_pips: Mapping[str, float]
    slippage_pips: float           # adverse entry slip, per side
    stop_slippage_pips: float      # EXTRA adverse slip on stop fills
    commission_per_lot_usd: float  # 0.0 today — documented assumption
    commission_usd_per_r: float    # commission expressed in R, if known; else 0.0
    as_of: str                     # date the parameters were fixed
    book: str = "selection"        # "selection" (ranks) or "reporting" (describes)

    def spread_for(self, pair: str) -> float:
        """Static spread in pips for a canonical pair; unknown pair fails closed."""
        try:
            return float(self.spread_pips[pair])
        except KeyError as exc:
            raise KeyError(
                f"no sealed spread for pair {pair!r}; the Constellation is closed "
                f"and a default would be a permissive fallback (fail-closed)"
            ) from exc

    def to_manifest(self) -> dict:
        """Canonical, order-stable parameter view for hashing and audit."""
        return {
            "name": self.name,
            "book": self.book,
            "spread_pips": {k: float(v) for k, v in sorted(self.spread_pips.items())},
            "slippage_pips": float(self.slippage_pips),
            "stop_slippage_pips": float(self.stop_slippage_pips),
            "commission_per_lot_usd": float(self.commission_per_lot_usd),
            "commission_usd_per_r": float(self.commission_usd_per_r),
            "as_of": self.as_of,
        }

    def digest(self) -> str:
        """SHA-256 of the canonical manifest (R18)."""
        blob = json.dumps(self.to_manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


def manifest_digest(model: "CostModel | None" = None) -> str:
    """Digest of ``model`` (default: the sealed SELECTION instance)."""
    return (model or SELECTION_COST_MODEL).digest()


# ---------------------------------------------------------------------------
# R20 — THE TWO BOOKS. Changing any number here REQUIRES updating the pinned
# SHA-256 values in tests/quant/test_costs.py in the same commit (R18).
#
# Commission = 0.0 is a DOCUMENTED ASSUMPTION, not a silent zero: the broker
# spec (per-lot commission) arrives in Phase 6. TODO(owner: Phase 6 broker
# integration) — set commission_per_lot_usd from the funded-account schedule.
# ---------------------------------------------------------------------------
CONSERVATIVE_COST_MODEL = CostModel(
    name="apex_conservative_v1",
    spread_pips=MappingProxyType(dict(_CONSERVATIVE_SPREAD_PIPS)),
    slippage_pips=0.5,
    stop_slippage_pips=1.0,
    commission_per_lot_usd=0.0,
    commission_usd_per_r=0.0,
    as_of="2025-01-01",
    book="selection",
)

REALISTIC_COST_MODEL = CostModel(
    name="apex_realistic_v1",
    spread_pips=MappingProxyType(dict(_REALISTIC_SPREAD_PIPS)),
    slippage_pips=0.3,
    stop_slippage_pips=0.5,
    commission_per_lot_usd=0.0,
    commission_usd_per_r=0.0,
    as_of="2025-01-01",
    book="reporting",
)

# The aliases the rest of the codebase reads. SELECTION is the judge; REPORTING
# describes. ``DEFAULT_COST_MODEL`` is kept for backward compatibility and is the
# SELECTION book (ranking must never default to the gentler book).
SELECTION_COST_MODEL = CONSERVATIVE_COST_MODEL
REPORTING_COST_MODEL = REALISTIC_COST_MODEL
DEFAULT_COST_MODEL = SELECTION_COST_MODEL

# Name -> model, for audits and the R19/era tooling.
BOOKS: Mapping[str, CostModel] = MappingProxyType(
    {"conservative": CONSERVATIVE_COST_MODEL, "realistic": REALISTIC_COST_MODEL}
)


def is_selection_book(model: CostModel) -> bool:
    """True iff ``model`` is a SELECTION book (may rank, per R20)."""
    return getattr(model, "book", "selection") == "selection"


def require_selection_book(model: CostModel) -> "CostModel":
    """Fail-closed guard: return ``model`` iff it is a selection book.

    R20 is enforced structurally: a caller that means to SELECT (rank, promote,
    exile) must pass the model through here first, so the reporting book can never
    silently become the judge.
    """
    if not is_selection_book(model):
        raise ValueError(
            f"cost model {getattr(model, 'name', model)!r} is a "
            f"{getattr(model, 'book', '?')!r} book; only a SELECTION book may rank "
            f"a candidate (R20)"
        )
    return model


def book_digests() -> dict[str, str]:
    """Both books' SHA-256 digests, for the audit line (R18/R20)."""
    return {name: m.digest() for name, m in BOOKS.items()}


def round_trip_cost_r(trade, model: CostModel = DEFAULT_COST_MODEL) -> float:
    """Cost of one round trip, in R units, from the trade's own risk distance.

    ``cost_pips = spread + entry_slip + (stop_slip if the exit was a stop)``.
    Converted with the trade's OWN risk: ``cost_r = cost_pips / sl_pips``, plus an
    explicit R-denominated commission when the broker spec supplies one. A trade
    with a non-positive risk distance is impossible from the engine (it rejects
    ``risk <= 0``); encountering one here is a bug, so it fails CLOSED and LOUD
    rather than dividing into a flattering number.
    """
    sl_pips = float(trade.sl_pips)
    if not (sl_pips > 0.0):
        raise ValueError(
            f"trade has non-positive risk distance ({sl_pips} pips); cannot price "
            f"costs — fail-closed (the engine guarantees risk > 0)"
        )
    exit_slip = model.stop_slippage_pips if trade.exit_reason in STOP_EXIT_REASONS else 0.0
    cost_pips = model.spread_for(trade.pair) + model.slippage_pips + exit_slip
    return cost_pips / sl_pips + model.commission_usd_per_r


def net_r_after_costs(gross_r: float, trade, model: CostModel = DEFAULT_COST_MODEL) -> float:
    """``gross_r - cost_r``; costs can only ever subtract (pessimism invariant)."""
    return float(gross_r) - round_trip_cost_r(trade, model)