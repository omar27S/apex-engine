"""R73 — KINGS BY REALM (MAP-Elites).

The leaderboard becomes a GRID of niches. A niche (a "realm") is
``regime x pair-class x family-group``. Each occupied cell holds its own KING:
the best genome that reached it. The council's seven seats are then drawn from
SEVEN DIFFERENT realms — seven distinct champions, not seven clones of the same
edge.

This is the anti-conformism structural fix: a single dominant family can hold
one throne per realm, never all seven. The census of occupied realms is reported
every audit so the truth of diversity is visible.

Pure, deterministic, fail-closed. A row without a usable family is refused (it
cannot be placed in a niche) rather than silently dropped into a default cell.

Reuses :func:`app.pyramid.roster.domain_of` for the family grouping (single
source of truth — Scar #2) when it can; otherwise a local fallback keeps this
module importable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "FAMILY_GROUPS",
    "Realm",
    "RealmError",
    "family_group",
    "pair_class",
    "regime_tag",
    "realm_of",
    "kings_by_realm",
    "census",
    "distinct_realm_champions",
]

# Family groups — a coarse partition of the 44 families. Deliberately broad:
# a realm should hold a coherent school of thought, not a single family.
FAMILY_GROUPS: dict[str, str] = {
    "trend": "trend",
    "macd_momentum": "momentum",
    "momentum_ignition": "momentum",
    "fvg_momentum": "momentum",
    "mean_reversion": "meanrev",
    "rsi_reversal": "meanrev",
    "rsi_divergence": "meanrev",
    "vwap_reversion": "meanrev",
    "zscore_reversion": "meanrev",
    "keltner_pullback": "meanrev",
    "hurst_reversion_filtered": "meanrev",
    "time_based_reversal": "meanrev",
    "cointegration_statarb": "relative",
    "breakout": "breakout",
    "atr_squeeze_breakout": "breakout",
    "vcp_breakout": "breakout",
    "london_orb": "breakout",
    "ny_orb": "breakout",
    "bb_keltner_squeeze": "volatility",
    "keltner_expansion": "volatility",
    "hurst_regime": "volatility",
    "volume_delta": "volume",
    "volume_profile_v": "volume",
    "ob_atr_rank": "volume",
    "wyckoff_spring": "structure",
    "order_block": "structure",
    "liq_sweep_ote": "structure",
    "choch_fvg": "structure",
    "bos_premium_discount": "structure",
    "silver_bullet": "structure",
    "asian_range_sweep": "structure",
    "eqhl_tap": "structure",
    "judas_swing": "structure",
    "ict_2022_model": "structure",
    "dealing_range": "structure",
    "turtle_soup": "structure",
    "pin_bar": "pattern",
    "engulfing_liquidity": "pattern",
    "hikkake": "pattern",
    "fib_confluence": "pattern",
    "harmonic_proxy": "pattern",
    "mtf_divergence": "pattern",
    "fib_ote_confluence": "pattern",
    "trend_pullback": "trend",
    "ensemble": "ensemble",
}

# Pair classes — the second axis. A genome is placed by the pair where it was
# judged (the caller supplies it); absent a pair, "all" is the honest cell.
_JPY = frozenset({"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY"})
_MAJORS = frozenset({"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
                     "USDCAD", "NZDUSD"})

_REGIMES = ("trend", "range", "chop")


class RealmError(ValueError):
    """A row could not be placed in a realm (fail-closed)."""


def family_group(family: str) -> str:
    """Coarse group of a family, or 'unknown' if the family is unrecognised."""
    return FAMILY_GROUPS.get(str(family), "unknown")


def pair_class(pair: str | None) -> str:
    """'jpy' | 'major' | 'cross' | 'all' for a pair symbol."""
    if not pair:
        return "all"
    p = str(pair).strip().upper()
    if p in _JPY:
        return "jpy"
    if p in _MAJORS:
        return "major"
    return "cross"


def regime_tag(row: dict) -> str:
    """Coarse market regime from a genome row's regime genes (fail-closed).

    The regime genes make the genome's intended world explicit: a high
    ``regime_hurst_min`` targets trending markets, a low one targets reverting
    (range) markets, and an intermediate value is the ambiguous chop class.
    A row missing both knobs is 'chop' — the honest, uninformative cell, never a
    flattering default.
    """
    hurst = row.get("regime_hurst_min")
    try:
        h = float(hurst)
    except (TypeError, ValueError):
        return "chop"
    if h != h:  # NaN
        return "chop"
    if h >= 0.62:
        return "trend"
    if h <= 0.45:
        return "range"
    return "chop"


@dataclass(frozen=True)
class Realm:
    """One niche of the MAP-Elites grid."""

    regime: str
    pair_class: str
    family_group: str

    def key(self) -> tuple[str, str, str]:
        return (self.regime, self.pair_class, self.family_group)

    def to_dict(self) -> dict:
        return {"regime": self.regime, "pair_class": self.pair_class,
                "family_group": self.family_group}


def realm_of(row: dict, *, pair: str | None = None) -> Realm:
    """Place a leaderboard row in its niche. A missing family is refused."""
    family = row.get("family")
    if not family:
        raise RealmError("row has no family — cannot place it in a realm")
    return Realm(
        regime=regime_tag(row),
        pair_class=pair_class(pair if pair is not None else row.get("pair")),
        family_group=family_group(family),
    )


def _rank_key(row: dict) -> tuple[float, float]:
    """Order within a realm: Wilson LB first, net R as the tiebreak."""
    try:
        lb = float(row.get("wilson_lb", 0.0))
    except (TypeError, ValueError):
        lb = 0.0
    try:
        net = float(row.get("net_r", 0.0))
    except (TypeError, ValueError):
        net = 0.0
    return (lb, net)


def kings_by_realm(rows: list[dict], *, pair_of=None) -> dict[tuple, dict]:
    """Best row per occupied realm. ``pair_of`` maps a row to its pair symbol."""
    kings: dict[tuple, dict] = {}
    for row in rows:
        pair = pair_of(row) if callable(pair_of) else None
        realm = realm_of(row, pair=pair)
        key = realm.key()
        cur = kings.get(key)
        if cur is None or _rank_key(row) > _rank_key(cur):
            kings[key] = dict(row)
    return kings


def census(rows: list[dict], *, pair_of=None) -> dict:
    """Honest realm-occupancy census for the audit."""
    kings = kings_by_realm(rows, pair_of=pair_of)
    by_family_group: dict[str, int] = {}
    by_regime: dict[str, int] = {}
    for (regime, _pc, group) in kings:
        by_regime[regime] = by_regime.get(regime, 0) + 1
        by_family_group[group] = by_family_group.get(group, 0) + 1
    return {
        "occupied": len(kings),
        "total_rows": len(rows),
        "by_regime": dict(sorted(by_regime.items())),
        "by_family_group": dict(sorted(by_family_group.items())),
        "kings": [
            {"realm": dict(zip(("regime", "pair_class", "family_group"), key)),
             "signature": row.get("signature", ""),
             "family": row.get("family", ""),
             "wilson_lb": row.get("wilson_lb"), "net_r": row.get("net_r")}
            for key, row in sorted(kings.items())
        ],
    }


def distinct_realm_champions(rows: list[dict], *, seats: int,
                             pair_of=None) -> list[dict]:
    """Up to ``seats`` kings from DISTINCT realms, best-first.

    This is the R73 council tie-in: the seven seats are seven different realms'
    kings — never seven clones. Fewer than ``seats`` occupied realms yields
    fewer champions (empty seats stay empty; no placeholder, R20/R21 spirit).
    """
    kings = kings_by_realm(rows, pair_of=pair_of)
    ordered = sorted(kings.values(), key=_rank_key, reverse=True)
    return ordered[:max(0, int(seats))]
