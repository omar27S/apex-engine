"""THE FITNESS — how honestly a lineage is ranked.

R17 NET-R DOCTRINE. Ranking is by the **Wilson 95% lower bound** of the NET win
rate (``metrics.wins`` is already net-derived), and the tiebreakers use NET R. A
gross R appears only as a diagnostic field (``gross_r``) and never enters a rank
key. The judge pays its own drinks.

The Wilson bound rewards evidence, not luck: a genome that went 20/30 is ranked
BELOW another whose observed win rate is lower but whose sample is larger and
steadier. Under ``min_trades`` trades a genome is **UNRANKED** — insufficient
evidence, never a zero floor (a no-trade genome is not "worst", it is unknown).

Tiebreakers, in order: net_r (higher), then max drawdown (lower), then trades
(more). A zero-loss genome has ``profit_factor = None``; it ranks by its Wilson
bound like any other — no infinity anywhere.

R16 — THE LOTTERY TAX GATES TITLES, NOT LIFE. The promotion bar rises with the
number of candidates judged (``log10`` of trials): the more genomes you try, the
higher the bar a Champion must clear, because a lucky maximum is more likely. The
tax decides CHAMPION promotion ONLY — survival and breeding inside the tournament
are governed by plain fitness. Losers don't die for the tax; they just don't get
crowned.

Pure, no I/O, no services.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.quant.metrics import MetricsReport

__all__ = [
    "BASE_WR_LB",
    "LOTTERY_TAX_PER_DECADE",
    "DEFAULT_MIN_TRADES",
    "WILSON_Z",
    "FIXABLE_CAUSES",
    "wilson_lower_bound",
    "autopsy_resilience",
    "FitnessResult",
    "fitness",
    "promotion_bar",
    "is_promotable",
]

# R16 — sealed lottery-tax constants.
BASE_WR_LB = 0.40
LOTTERY_TAX_PER_DECADE = 0.02
DEFAULT_MIN_TRADES = 30
WILSON_Z = 1.96  # 95% two-sided

# R39 (Phase 6a) — the ENGINEERED (fixable-by-hardening) autopsy causes. Structural
# failure and regime misread are SIGNAL problems, not hardening problems; they are
# deliberately excluded from ``autopsy_resilience``.
FIXABLE_CAUSES: frozenset[str] = frozenset(
    {"stop_hunt_gap", "news_whipsaw", "slippage_erosion"}
)


def autopsy_resilience(fixable_deaths: int, trades: int) -> float:
    """R39 — the share of trades that did NOT die to an engineered cause.

    ``1 - fixable_deaths / trades``. A zero-trade genome has no evidence: defined
    as 0.0 (fail-closed — not a passing 1.0). Clamped to [0, 1] and monotone
    NON-INCREASING in ``fixable_deaths`` and non-decreasing in ``trades``.
    """
    n = int(trades)
    if n <= 0:
        return 0.0
    f = max(0, int(fixable_deaths))
    return max(0.0, min(1.0, 1.0 - f / n))



def wilson_lower_bound(wins: int, trades: int, z: float = WILSON_Z) -> float:
    """Wilson score interval lower bound of the binomial proportion.

    Derived from first principles:

        center = p_hat + z^2 / (2n)
        spread = z * sqrt( (p_hat (1 - p_hat) + z^2 / (4n)) / n )
        LB     = (center - spread) / (1 + z^2 / n)

    ``trades <= 0`` has no evidence: returns 0.0 (the bound at zero, not a rank).
    """
    if trades <= 0:
        return 0.0
    n = float(trades)
    p = float(wins) / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    spread = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return (center - spread) / denom


@dataclass(frozen=True)
class FitnessResult:
    """A genome's fitness: the rank key plus the honest ingredients behind it.

    ``net_r`` is the ranked quantity; ``gross_r`` is DIAGNOSTIC ONLY (R17) and is
    never part of ``key()``. ``wins``/``win_rate`` are NET wins.

    R39 (Phase 6a) — ``autopsy_resilience`` joins the tuple as a tiebreak between
    the Wilson LB and net R. It is ``1 - fixable_deaths / trades`` over the
    adversarial world (engineered causes only). Default 1.0 (no adversarial
    evidence supplied) so a legacy clean-only caller is unchanged.
    """

    ranked: bool
    wilson_lb: float
    win_rate: float
    trades: int
    net_r: float
    max_drawdown_r: float
    reason: str
    gross_r: float = 0.0  # DIAGNOSTIC ONLY — must not enter the rank key
    autopsy_resilience: float = 1.0  # R39 tiebreak; DIAGNOSTIC-adjacent
    # THE FULL FEEDING — the report fields the Letter's table reads, carried through
    # the rank result so the durable report never drops them (never a rank key).
    profit_factor: float | None = None
    gross_profit_r: float = 0.0
    gross_loss_r: float = 0.0
    wins: int = 0

    def key(self) -> tuple:
        """Sort key, best-first under ``min`` (any value = lower is better).

        R39 tiebreak order: adversarial Wilson LB -> autopsy_resilience (higher
        better) -> net_r (higher) -> drawdown (lower) -> trades (more).

        Raises if unranked: an unranked genome has no key and must never be sorted
        as if it did (that would smuggle in a zero floor).
        """
        if not self.ranked:
            raise ValueError("unranked genome has no rank key")
        return (
            -self.wilson_lb,
            -self.autopsy_resilience,
            -self.net_r,
            self.max_drawdown_r,
            -self.trades,
        )


def fitness(
    report: MetricsReport,
    min_trades: int = DEFAULT_MIN_TRADES,
    *,
    fixable_deaths: int | None = None,
) -> FitnessResult:
    """Rank a union report by the Wilson LB, with the documented tiebreakers.

    ``fixable_deaths`` (R39, optional) is the count of adversarial losses the
    autopsy attributed to an ENGINEERED cause; when supplied, ``autopsy_resilience``
    is computed from it. When omitted (a clean-only caller), resilience defaults to
    1.0 and the rank key is unchanged for identical clean metrics.
    """
    wins = report.wins
    trades = report.trades
    lb = wilson_lower_bound(wins, trades)
    ranked = trades >= int(min_trades)
    reason = "ranked" if ranked else f"unranked: trades {trades} < min_trades {min_trades}"
    resilience = (
        1.0 if fixable_deaths is None
        else autopsy_resilience(int(fixable_deaths), trades)
    )
    return FitnessResult(
        ranked=ranked,
        wilson_lb=lb,
        win_rate=report.win_rate,
        trades=trades,
        net_r=report.net_r,
        max_drawdown_r=report.max_drawdown_r,
        reason=reason,
        gross_r=report.gross_r,
        autopsy_resilience=resilience,
        profit_factor=report.profit_factor,
        gross_profit_r=report.gross_profit_r,
        gross_loss_r=report.gross_loss_r,
        wins=report.wins,
    )


def promotion_bar(trials: int) -> float:
    """The R16 lottery-tax bar: ``BASE + TAX * log10(max(trials, 10))``.

    Monotone non-decreasing in ``trials``; the floor ``trials >= 10`` pins the
    smallest bar at ``BASE + TAX`` (0.42) so a handful of probes can never demand
    a bar below the base rate.
    """
    return BASE_WR_LB + LOTTERY_TAX_PER_DECADE * math.log10(max(int(trials), 10))


def is_promotable(wilson_lb: float, trials: int) -> bool:
    """A candidate is promotable iff its Wilson LB clears the bar at ``trials``."""
    return float(wilson_lb) >= promotion_bar(trials)
