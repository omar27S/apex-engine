"""THE RANKS OF THE PYRAMID — seven hundred roles, exact arithmetic (Phase 3.1).

The pyramid is ROLES, not individuals. Every rank has a sealed headcount; the
genomes that fill a role are drawn from the honest tournament, never declared.

    RANK 0 — THE ORACLE (1)             final confidence per candidate (AOS)
    RANK 1 — HIGH PRIESTS (4)           one per domain
    RANK 2 — GENERALS (80)              15 active (one per operational pair) + 65 reserve
    RANK 3 — SOLDIERS (210)             one live genome each
    RANK 4 — AVANT-GARDE (300)          exploration swarm (no live vote)
    RANK 5 — SPECTRE RESEARCHERS (105)  free-thinking corps (notes only)

    1 + 4 + 80 + 210 + 300 + 105 = 700  (pinned by test)

THE ARITHMETIC ADJUSTMENT (documented, per the directive). The ranking text named
"28 generals", but ``1 + 4 + 28 + 210 + 300 + 105 = 648`` — that is seven hundred
minus 52. The directive says the number 700 is law and to adjust RESERVE duty to
make it exact. So RANK 2 is 80: one ACTIVE general per pair and the rest hold
RESERVE duty. THE STUDY-PAIR FIREWALL (Founding Charter) keeps the TRADE domain at
15 operational pairs (the 15 study pairs are sensors only), so RANK 2 is 15 active
(one per operational pair) + 65 reserve = 80. The 700 is unchanged.

DOMAINS. The four domains are Trend, Mean-Reversion, Volatility, Liquidity. Every
one of the 47 signal families is mapped to exactly one domain in :data:`DOMAIN_MAP`
(validated at import, fail-closed — a missing or duplicated family is a loud error,
never a default).

Build Mode: pure definitions and pure constructors. No I/O, no servers, no loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constellation import OPERATIONAL_PAIRS
from app.pyramid.doctrine import RESERVE_ROTATION_PERIOD
from app.quant.genome import FAMILIES, StrategyGenome

__all__ = [
    "ORACLE",
    "PRIESTS",
    "GENERALS",
    "SOLDIERS",
    "AVANT_GARDE",
    "SPECTRES",
    "RANK_COUNTS",
    "RANK_NAMES",
    "PYRAMID_SIZE",
    "ACTIVE_GENERALS",
    "RESERVE_GENERALS",
    "DOMAINS",
    "DOMAIN_MAP",
    "PAIR_DOMAIN",
    "domain_of",
    "Priest",
    "General",
    "Soldier",
    "AvantGarde",
    "Spectre",
    "build_priests",
    "build_generals",
    "build_soldiers",
    "build_avant_garde",
    "build_spectres",
    "PyramidRoster",
]

# ---------------------------------------------------------------------------
# The ranks (sealed).
# ---------------------------------------------------------------------------
ORACLE = 0
PRIESTS = 1
GENERALS = 2
SOLDIERS = 3
AVANT_GARDE = 4
SPECTRES = 5

RANK_COUNTS: dict[int, int] = {
    ORACLE: 1,
    PRIESTS: 4,
    GENERALS: 80,
    SOLDIERS: 210,
    AVANT_GARDE: 300,
    SPECTRES: 105,
}

RANK_NAMES: dict[int, str] = {
    ORACLE: "The Oracle",
    PRIESTS: "High Priests",
    GENERALS: "Generals",
    SOLDIERS: "Soldiers",
    AVANT_GARDE: "Avant-Garde",
    SPECTRES: "Spectre Researchers",
}

PYRAMID_SIZE: int = 700

ACTIVE_GENERALS: int = len(OPERATIONAL_PAIRS)   # one per OPERATIONAL pair (15; study pairs are sensors)
RESERVE_GENERALS: int = RANK_COUNTS[GENERALS] - ACTIVE_GENERALS  # 50 — reserve duty


def _validate_arithmetic() -> None:
    """The 700 is law. Fail-closed at import if the ranks do not sum to it."""
    total = sum(RANK_COUNTS.values())
    if total != PYRAMID_SIZE:
        raise ValueError(
            f"pyramid ranks must sum to {PYRAMID_SIZE}, got {total}: {RANK_COUNTS}"
        )
    if RANK_COUNTS[ORACLE] != 1:
        raise ValueError("there is exactly one Oracle")
    if RANK_COUNTS[PRIESTS] != len(DOMAINS):
        raise ValueError("one High Priest per domain")
    if RANK_COUNTS[GENERALS] != ACTIVE_GENERALS + RESERVE_GENERALS:
        raise ValueError("generals = active (per pair) + reserve")


# ---------------------------------------------------------------------------
# Domains.
# ---------------------------------------------------------------------------
DOMAINS: tuple[str, ...] = ("Trend", "Mean-Reversion", "Volatility", "Liquidity")

# Every family -> exactly one domain. This is a deliberate, sealed mapping (the
# directive calls it a "sealed DOMAIN_MAP"); it is validated against FAMILIES at
# import so it can never drift out of sync with the family registry.
DOMAIN_MAP: dict[str, str] = {
    # --- Trend: direction-following and continuation reading ---
    "trend_pullback": "Trend",
    "breakout": "Trend",
    "macd_momentum": "Trend",
    "choch_fvg": "Trend",
    "bos_premium_discount": "Trend",
    "fvg_momentum": "Trend",
    "silver_bullet": "Trend",
    "ict_2022_model": "Trend",
    "momentum_ignition": "Trend",
    "mtf_divergence": "Trend",
    "fib_ote_confluence": "Trend",
    "ensemble": "Trend",
    # --- Mean-Reversion: fade / equilibrium-restoring reading ---
    "mean_reversion": "Mean-Reversion",
    "rsi_reversal": "Mean-Reversion",
    "cointegration_statarb": "Mean-Reversion",
    "dealing_range": "Mean-Reversion",
    "rsi_divergence": "Mean-Reversion",
    "vwap_reversion": "Mean-Reversion",
    "zscore_reversion": "Mean-Reversion",
    "pin_bar": "Mean-Reversion",
    "hikkake": "Mean-Reversion",
    "fib_confluence": "Mean-Reversion",
    "harmonic_proxy": "Mean-Reversion",
    "hurst_reversion_filtered": "Mean-Reversion",
    "time_based_reversal": "Mean-Reversion",
    # --- Volatility: expansion / contraction / regime reading ---
    "keltner_expansion": "Volatility",
    "bb_keltner_squeeze": "Volatility",
    "keltner_pullback": "Volatility",
    "hurst_regime": "Volatility",
    "atr_squeeze_breakout": "Volatility",
    "london_orb": "Volatility",
    "ny_orb": "Volatility",
    "vcp_breakout": "Volatility",
    # --- Liquidity: pools, sweeps, imbalance reading ---
    "wyckoff_spring": "Liquidity",
    "order_block": "Liquidity",
    "volume_delta": "Liquidity",
    "ob_atr_rank": "Liquidity",
    "liq_sweep_ote": "Liquidity",
    "asian_range_sweep": "Liquidity",
    "eqhl_tap": "Liquidity",
    "judas_swing": "Liquidity",
    "turtle_soup": "Liquidity",
    "engulfing_liquidity": "Liquidity",
    "volume_profile_v": "Liquidity",
    # --- Machine learning (Mega Phase 2, Section D): learned models join the map ---
    "ml_gradient_boosting": "Trend",
    "ml_lstm_pattern": "Trend",
    "ml_bayesian_regime": "Volatility",
}


def _validate_domain_map() -> None:
    """Fail-closed: DOMAIN_MAP covers FAMILIES exactly once, into known domains."""
    mapped = set(DOMAIN_MAP)
    known = set(FAMILIES)
    if mapped != known:
        missing = sorted(known - mapped)
        extra = sorted(mapped - known)
        raise ValueError(
            f"DOMAIN_MAP must cover all families exactly once: "
            f"missing={missing} extra={extra}"
        )
    for family, domain in DOMAIN_MAP.items():
        if domain not in DOMAINS:
            raise ValueError(f"family {family!r} maps to unknown domain {domain!r}")


_validate_arithmetic()
_validate_domain_map()


def domain_of(family: str) -> str:
    """The domain of a family; an unknown family fails closed (loud)."""
    try:
        return DOMAIN_MAP[family]
    except KeyError as exc:
        raise KeyError(
            f"no sealed domain for family {family!r}; the mapping is closed and a "
            f"default would be a hidden assumption (fail-closed)"
        ) from exc


# ---------------------------------------------------------------------------
# Pair -> domain, for generals. Every OPERATIONAL pair has one ACTIVE general
# that owns its domain vote. The mapping is deterministic and sealed.
# ---------------------------------------------------------------------------
PAIR_DOMAIN: dict[str, str] = {
    "EURUSD": "Trend",
    "GBPUSD": "Trend",
    "USDJPY": "Trend",
    "USDCHF": "Mean-Reversion",
    "AUDUSD": "Trend",
    "USDCAD": "Mean-Reversion",
    "NZDUSD": "Trend",
    "EURGBP": "Mean-Reversion",
    "EURJPY": "Trend",
    "GBPJPY": "Volatility",
    "EURCHF": "Mean-Reversion",
    "EURAUD": "Liquidity",
    "AUDJPY": "Volatility",
    "CADJPY": "Liquidity",
    "NZDJPY": "Liquidity",
}


def _validate_pair_domain() -> None:
    if set(PAIR_DOMAIN) != set(OPERATIONAL_PAIRS):
        raise ValueError("PAIR_DOMAIN must cover the operational pairs exactly")
    for pair, domain in PAIR_DOMAIN.items():
        if domain not in DOMAINS:
            raise ValueError(f"pair {pair!r} maps to unknown domain {domain!r}")


_validate_pair_domain()


# ---------------------------------------------------------------------------
# The roles.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Priest:
    """A High Priest: owns one domain, aggregates its soldiers' votes (Rank 1)."""

    rank: int
    seat: int
    domain: str


@dataclass(frozen=True)
class General:
    """A General: a pair-domain commander (Rank 2).

    ``duty`` is ``"active"`` (owns a pair's domain vote; 15 of these, one per pair)
    or ``"reserve"`` (65 spares, no live pair ownership).
    """

    rank: int
    seat: int
    pair: str
    domain: str
    duty: str


@dataclass(frozen=True)
class Soldier:
    """A Soldier: one live genome, with a domain and a pair assignment (Rank 3)."""

    rank: int
    seat: int
    genome: StrategyGenome
    trust: float
    domain: str
    pair: str

    @property
    def signature(self) -> str:
        return self.genome.signature()


@dataclass(frozen=True)
class AvantGarde:
    """An Avant-Garde scout: exploration duty, NO live vote (Rank 4)."""

    rank: int
    seat: int
    seed: int  # deterministic per-seat exploration seed


@dataclass(frozen=True)
class Spectre:
    """A Spectre Researcher: polymath sandbox, notes only, never signals (Rank 5)."""

    rank: int
    seat: int


def build_priests(n: int = RANK_COUNTS[PRIESTS]) -> tuple[Priest, ...]:
    """One High Priest per domain, in the sealed domain order."""
    if n != RANK_COUNTS[PRIESTS]:
        raise ValueError(
            f"there must be exactly {RANK_COUNTS[PRIESTS]} High Priests (one per "
            f"domain), got {n} (fail-closed)"
        )
    return tuple(Priest(rank=PRIESTS, seat=i, domain=d) for i, d in enumerate(DOMAINS))


def reserve_rotation(step: int, reserves: int = RESERVE_GENERALS) -> tuple[tuple[int, str], ...]:
    """R26 — the sealed deterministic reserve-duty schedule.

    Returns ``(reserve_seat, pair)`` pairs for a muster at ``step`` (the muster
    generation counter). Reserve seat ``s`` shadows pair
    ``OPERATIONAL_PAIRS[(s + step) % len(OPERATIONAL_PAIRS)]``: advancing
    ``step`` by one rotates every reserve onto the next pair, so over
    :data:`RESERVE_ROTATION_PERIOD` steps a reserve visits EVERY operational pair
    exactly once. Every pair is thus shadowed by roughly ``RESERVE_GENERALS/n``
    reserves at all times — no uncovered territory, and no reserve is ever
    decorative (each is bound to a real pair each step).

    The schedule is a pure function of ``step``: deterministic, reproducible, and
    sealed. Negative steps are normalized into the period so the schedule closes.
    """
    n = len(OPERATIONAL_PAIRS)
    order = [str(p) for p in OPERATIONAL_PAIRS]
    # Keep pair order canonical (as sealed) so the schedule is stable under dict
    # iteration order changes elsewhere.
    step_n = int(step) % n
    out: list[tuple[int, str]] = []
    for i in range(max(0, int(reserves))):
        slot = (i + step_n) % n
        out.append((i, order[slot]))
    return tuple(out)


def build_generals(
    pairs: tuple[str, ...] = OPERATIONAL_PAIRS,
    reserves: int = RESERVE_GENERALS,
    *,
    step: int = 0,
) -> tuple[General, ...]:
    """The 15 ACTIVE generals (one per operational pair) plus ``reserves`` on RESERVE duty.

    Active generals cover every pair exactly ONCE (no duplicate pair assignment).
    Reserves are placed on pairs by the sealed R26 rotation schedule
    (:func:`reserve_rotation`) for the given ``step``, so their ``pair`` is a real
    assignment, never a placeholder. Active duty remains ownership; reserve duty is
    rotation, and the ``duty`` field keeps the two unmistakable in every audit.
    """
    if set(pairs) != set(OPERATIONAL_PAIRS):
        raise ValueError("active generals must command exactly the operational pairs")
    active = [
        General(rank=GENERALS, seat=i, pair=pair, domain=PAIR_DOMAIN[pair], duty="active")
        for i, pair in enumerate(OPERATIONAL_PAIRS)
    ]
    rotation = reserve_rotation(step, reserves)
    reserve = [
        General(
            rank=GENERALS,
            seat=ACTIVE_GENERALS + seat,
            pair=pair,
            domain=PAIR_DOMAIN[pair],
            duty="reserve",
        )
        for seat, pair in rotation
    ]
    out = tuple(active + reserve)
    if len(out) != RANK_COUNTS[GENERALS]:
        raise ValueError(
            f"generals must number {RANK_COUNTS[GENERALS]}, got {len(out)} (fail-closed)"
        )
    return out


def build_soldiers(
    genomes: list[StrategyGenome],
    trust: dict[str, float] | None = None,
    cap: int = RANK_COUNTS[SOLDIERS],
) -> tuple[Soldier, ...]:
    """Muster Soldiers from distinct genomes, capped at the rank headcount.

    Genomes are de-duplicated by signature (order preserved), so no genome holds
    two seats. Each soldier's domain comes from its family (sealed DOMAIN_MAP) and
    its pair is assigned round-robin over the operational pairs — deterministic and
    balanced. Fewer genomes than ``cap`` is an HONEST shortfall: the seats beyond
    the muster are left VACANT and reported, never filled with a placeholder.
    """
    trust = dict(trust or {})
    seen: set[str] = set()
    soldiers: list[Soldier] = []
    for g in genomes:
        sig = g.signature()
        if sig in seen:
            continue
        seen.add(sig)
        if len(soldiers) >= cap:
            break
        pair = OPERATIONAL_PAIRS[len(soldiers) % len(OPERATIONAL_PAIRS)]
        soldiers.append(
            Soldier(
                rank=SOLDIERS,
                seat=len(soldiers),
                genome=g,
                trust=float(trust.get(sig, 0.0)),
                domain=domain_of(g.family),
                pair=pair,
            )
        )
    return tuple(soldiers)


def build_avant_garde(n: int = RANK_COUNTS[AVANT_GARDE]) -> tuple[AvantGarde, ...]:
    """The exploration swarm: ``n`` scouts, each with a deterministic seed."""
    return tuple(AvantGarde(rank=AVANT_GARDE, seat=i, seed=i) for i in range(n))


def build_spectres(n: int = RANK_COUNTS[SPECTRES]) -> tuple[Spectre, ...]:
    """The free-thinking corps: ``n`` researchers (notes only)."""
    return tuple(Spectre(rank=SPECTRES, seat=i) for i in range(n))


@dataclass
class PyramidRoster:
    """The full muster: every rank's occupants, plus honest vacancy counts.

    ``vacancies`` records how many SOLDIER seats were left unfilled (the only rank
    whose headcount depends on how much DNA reality produced). The structural
    counts in :data:`RANK_COUNTS` are law regardless of territory.
    """

    priests: tuple[Priest, ...]
    generals: tuple[General, ...]
    soldiers: tuple[Soldier, ...]
    avant_garde: tuple[AvantGarde, ...]
    spectres: tuple[Spectre, ...]
    oracle_name: str = "oracle"

    defensiveness: float = 0.0       # R25 realized scout budget fraction

    @property
    def soldier_vacancies(self) -> int:
        return RANK_COUNTS[SOLDIERS] - len(self.soldiers)

    def reserve_duty(self) -> dict[str, int]:
        """R26 — how many reserve officers shadow each operational pair."""
        out = {p: 0 for p in OPERATIONAL_PAIRS}
        for g in self.generals:
            if g.duty == "reserve":
                out[g.pair] = out.get(g.pair, 0) + 1
        return out

    def counts(self) -> dict[str, int]:
        return {
            "oracle": 1,
            "priests": len(self.priests),
            "generals": len(self.generals),
            "soldiers": len(self.soldiers),
            "avant_garde": len(self.avant_garde),
            "spectres": len(self.spectres),
        }

    def to_dict(self) -> dict:
        return {
            "counts": self.counts(),
            "structural": {RANK_NAMES[k]: v for k, v in RANK_COUNTS.items()},
            "soldier_vacancies": self.soldier_vacancies,
            "domains": list(DOMAINS),
            "priests": [{"seat": p.seat, "domain": p.domain} for p in self.priests],
            "active_generals": [
                {"pair": g.pair, "domain": g.domain, "duty": g.duty}
                for g in self.generals if g.duty == "active"
            ],
            "reserve_generals": sum(1 for g in self.generals if g.duty == "reserve"),
            "reserve_duty": self.reserve_duty(),
            "defensiveness": self.defensiveness,
            "soldiers_by_domain": self._soldiers_by_domain(),
        }

    def _soldiers_by_domain(self) -> dict[str, int]:
        out = {d: 0 for d in DOMAINS}
        for s in self.soldiers:
            out[s.domain] = out.get(s.domain, 0) + 1
        return out


def muster(
    genomes: list[StrategyGenome],
    trust: dict[str, float] | None = None,
    *,
    avant_garde: int = RANK_COUNTS[AVANT_GARDE],
    spectres: int = RANK_COUNTS[SPECTRES],
    rotation_step: int = 0,
) -> PyramidRoster:
    """Assemble the whole roster from a pool of genomes (one call, no I/O)."""
    return PyramidRoster(
        priests=build_priests(),
        generals=build_generals(step=rotation_step),
        soldiers=build_soldiers(genomes, trust),
        avant_garde=build_avant_garde(avant_garde),
        spectres=build_spectres(spectres),
    )