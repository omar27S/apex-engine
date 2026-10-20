"""HONEST METRICS — only what the trades actually did.

No smoothing, no annualization, no invented statistics. ``profit_factor`` is
``None`` when there are no losses (infinity is not a number you can rank). Drawdown
is read off the realized net-R equity curve, in R, peak to trough.

R17 — NET R IS THE JUDGE. Wins, losses, ties, win rate, net R, drawdown and
profit factor are all derived from ``trade.net_r`` (the R after the sealed cost
model). Gross R appears ONLY as a diagnostic (``gross_r``, ``gross_win_rate``): it
may never decide survival, titles, or breeding. A trade whose ``net_r`` has not
been stamped by the evaluator falls back to its gross ``r_multiple`` (a naked
Pre-friction trade is its own net) — the tournament always stamps it.

A trade is a win when its NET R multiple is positive, a loss when negative, and a
tie when exactly zero. Ties are reported separately so the counts reconcile:
``trades == wins + losses + ties``.

R103 (the behavioral atlas) — the DIRECTION CENSUS: ``long_trades`` and
``short_trades`` count the trades by the side the engine recorded (a trade's
``direction`` field, "long"/"short"). They default to 0 so every legacy
construction stays valid; the atlas reads their SHARE as one measured axis
of behavior (never a rank key — a direction bias is a DESCRIPTION, not a
verdict).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.quant.engine import TradeRecord


def trade_net_r(t: TradeRecord) -> float:
    """The trade's net R: the stamped value when present, else its gross R."""
    return float(t.r_multiple if t.net_r is None else t.net_r)


@dataclass(frozen=True)
class MetricsReport:
    trades: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    net_r: float
    avg_r: float
    gross_profit_r: float
    gross_loss_r: float
    profit_factor: float | None
    max_drawdown_r: float
    exit_reason_breakdown: dict[str, dict[str, float]]
    parachute_locks: int
    avg_bars_held: float
    rejected: dict[str, int] = field(default_factory=dict)
    gross_r: float = 0.0           # DIAGNOSTIC ONLY (R17) — never ranks
    gross_win_rate: float = 0.0    # DIAGNOSTIC ONLY (R17) — never ranks
    gross_wins: int = 0            # DIAGNOSTIC ONLY (R17) — never ranks
    # R103 — the direction census (the atlas's third axis; never a rank key).
    long_trades: int = 0
    short_trades: int = 0


def _max_drawdown_r(r_sequence: list[float]) -> float:
    """Largest peak-to-trough drop of the cumulative-R equity curve."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in r_sequence:
        equity += r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return max_dd


def aggregate(
    trades: list[TradeRecord], rejected: dict[str, int] | None = None
) -> MetricsReport:
    """Summarize a trade stream honestly, ranking on NET R (R17)."""
    rejected = dict(rejected or {})
    n = len(trades)
    if n == 0:
        return MetricsReport(
            trades=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.0,
            net_r=0.0,
            avg_r=0.0,
            gross_profit_r=0.0,
            gross_loss_r=0.0,
            profit_factor=None,
            max_drawdown_r=0.0,
            exit_reason_breakdown={},
            parachute_locks=0,
            avg_bars_held=0.0,
            rejected=rejected,
            gross_r=0.0,
            gross_win_rate=0.0,
            gross_wins=0,
            long_trades=0,
            short_trades=0,
        )

    rs = [trade_net_r(t) for t in trades]
    gross = [t.r_multiple for t in trades]
    wins = sum(1 for r in rs if r > 0)
    losses = sum(1 for r in rs if r < 0)
    ties = n - wins - losses

    gross_profit = sum(r for r in rs if r > 0)
    gross_loss = -sum(r for r in rs if r < 0)  # positive magnitude
    net_r = sum(rs)

    profit_factor = None if gross_loss == 0 else gross_profit / gross_loss

    breakdown: dict[str, dict[str, float]] = {}
    for t, r in zip(trades, rs):
        bucket = breakdown.setdefault(t.exit_reason, {"count": 0, "net_r": 0.0})
        bucket["count"] += 1
        bucket["net_r"] += r

    # R103 — the direction census (side by the engine's own record; a trade
    # with no direction field falls in neither count, and the share of such
    # strays is visible from trades - (long + short)).
    long_trades = sum(1 for t in trades if str(getattr(t, "direction", "")) == "long")
    short_trades = sum(1 for t in trades if str(getattr(t, "direction", "")) == "short")

    return MetricsReport(
        trades=n,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=wins / n,
        net_r=net_r,
        avg_r=net_r / n,
        gross_profit_r=gross_profit,
        gross_loss_r=gross_loss,
        profit_factor=profit_factor,
        max_drawdown_r=_max_drawdown_r(rs),
        exit_reason_breakdown=breakdown,
        parachute_locks=sum(1 for t in trades if t.parachute_armed),
        avg_bars_held=sum(t.bars_held for t in trades) / n,
        rejected=rejected,
        gross_r=sum(gross),
        gross_win_rate=sum(1 for r in gross if r > 0) / n,
        gross_wins=sum(1 for r in gross if r > 0),
        long_trades=long_trades,
        short_trades=short_trades,
    )
