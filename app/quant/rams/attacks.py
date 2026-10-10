"""THE FOUR RAMS ATTACKS — pure, deterministic, logged (Phase 5, R36).

Each attack is a pure function of a canonical M15 frame (and its seed). It
returns the mutated frame PLUS an injection log: one :class:`InjectionEvent` per
event (bar index, kind, size, target zone). Every attack is pessimistic in a
documented direction, and every mutated frame is re-validated with the sealed
``app.core.data.validate`` — an adversarial frame that violates the OHLC schema
is a RAMS BUG, not a kill, and it raises loudly.

ATTACKS
* :func:`micro_gaps` — at low-liquidity bars (ATR lower-tail, off-killzone) gap
  the open 2-5 pips beyond the nearest obvious stop zone (the last confirmed
  prior swing +/- a small buffer), so a resting stop is hunted. Pessimism:
  MORE gaps and DEEPER gaps fill stops worse.
* :func:`news_whipsaw` — at sealed proxy calendar slots, replace 2-3 candles with
  a fake impulse AGAINST the local trend (sized to reach typical stop zones)
  followed by the real displacement. Pessimism: BIGGER impulses kill more stops.
* :func:`dynamic_slippage` / :func:`slippage_pips` — the R36 adversarial slippage
  layer applied ONLY inside RAMS evaluation. Pessimism: costs can never improve a
  trade (property-tested).
* :func:`drawdown_decay` — pure post-processing on a trade list: reorder losers
  into the worst statistically-plausible cluster and return the worst-path equity
  curve and its max drawdown.

PURITY: no I/O, no services, no global state. Deterministic under ``seed``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from app.core import data as data_mod
from app.core import law
from app.quant import indicators
from app.quant.rams.config import DEFAULT_RAMS, RAMSConfig

__all__ = [
    "InjectionEvent",
    "AttackResult",
    "micro_gaps",
    "news_whipsaw",
    "dynamic_slippage",
    "slippage_pips",
    "apply_adversarial_slippage",
    "drawdown_decay",
    "MAX_INJECTIONS",
]

# A hard bound on injections so an adversarial frame never rewrites the whole
# tape (Build Mode: bounded work, and a bounded enemy).
MAX_INJECTIONS = 400

_CANONICAL = ("ts", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class InjectionEvent:
    """One injected adversarial event, fully described for the autopsy."""

    bar_index: int
    kind: str
    size: float          # price size of the injection (gap depth / impulse)
    target_zone: float   # the stop zone the injection aimed at (price)
    detail: str = ""

    def to_dict(self) -> dict:
        return {"bar_index": int(self.bar_index), "kind": self.kind,
                "size": float(self.size), "target_zone": float(self.target_zone),
                "detail": self.detail}


@dataclass
class AttackResult:
    """A mutated frame plus the log of every event injected into it."""

    frame: pd.DataFrame
    log: list[InjectionEvent] = field(default_factory=list)
    kind: str = ""

    def __len__(self) -> int:
        return len(self.log)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "injections": len(self.log),
                "events": [e.to_dict() for e in self.log]}


def _canon(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[list(_CANONICAL)].copy()
    out["ts"] = out["ts"].astype("int64")
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = out[col].astype("float64")
    return out


def _regen(o: float, c: float, wick: float) -> tuple[float, float]:
    """high/low for an (open, close) body that keeps the OHLC invariants."""
    hi = max(o, c) + wick
    lo = min(o, c) - wick
    return hi, lo


# ---------------------------------------------------------------------------
# 1. MICRO GAPS — hunt stops at low-liquidity bars.
# ---------------------------------------------------------------------------
def micro_gaps(
    frame: pd.DataFrame,
    intensity: float = 1.0,
    *,
    pip: float = 0.0001,
    config: RAMSConfig = DEFAULT_RAMS,
    seed: int | None = None,
) -> AttackResult:
    """Gap the open beyond the nearest obvious stop zone at low-liquidity bars.

    A low-liquidity bar is one whose ATR is in the bottom ``gap_atr_lower_pct``
    of its trailing window AND which sits off the London/NY killzone. The target
    zone is the last CONFIRMED prior swing (causal) +/- ``gap_buffer_pips``; the
    open is then pushed ``[gap_min_pips, gap_max_pips] * intensity`` beyond it.
    Pessimism: a resting stop on the obvious swing is hunted by the gap.

    ``ts`` is untouched; ``high``/``low`` are re-widened to admit the new open, so
    the frame still passes :func:`app.core.data.validate`.
    """
    rng = np.random.default_rng(config.seed if seed is None else seed)
    out = _canon(frame)
    n = len(out)
    log: list[InjectionEvent] = []
    if n < 20:
        data_mod.validate(out, expected_step_seconds=None)
        return AttackResult(out, log, "micro_gaps")

    high = out["high"].to_numpy()
    low = out["low"].to_numpy()
    close = out["close"].to_numpy()
    ts = out["ts"].to_numpy()

    atr = indicators.atr(high, low, close, 14)
    atr_rank = indicators.rolling_percentile_rank(atr, window=min(200, n))
    masks = indicators.session_masks(ts)
    killzone = masks.get("london_newyork", np.zeros(n, dtype=bool))
    piv_high, piv_low = indicators.confirmed_pivots(high, low, strength=2)

    lo_pct = config.gap_atr_lower_pct
    buffer = config.gap_buffer_pips * pip
    picked = 0
    for i in range(n):
        if picked >= MAX_INJECTIONS:
            break
        r = atr_rank[i]
        if not np.isfinite(r) or r >= lo_pct:
            continue
        if bool(killzone[i]):
            continue
        if not (np.isfinite(piv_high[i]) or np.isfinite(piv_low[i])):
            continue
        if rng.random() > min(1.0, 0.35 * intensity):
            continue
        # Nearest obvious stop zone: the swing level closest to the current price.
        candidates = []
        if np.isfinite(piv_low[i]):
            candidates.append(("below", float(piv_low[i])))
        if np.isfinite(piv_high[i]):
            candidates.append(("above", float(piv_high[i])))
        side, zone = min(candidates, key=lambda c: abs(c[1] - close[i]))
        size_pips = float(rng.uniform(config.gap_min_pips, config.gap_max_pips)) * intensity
        size = size_pips * pip
        if side == "below":
            new_open = zone - buffer - size
        else:
            new_open = zone + buffer + size
        if new_open <= 0.0:
            continue
        o = float(out["open"].iloc[i])
        c = float(close[i])
        wick = max(1e-6, 0.05 * abs(new_open - c))
        hi, lo = _regen(new_open, c, wick)
        out.iloc[i, out.columns.get_loc("open")] = new_open
        out.iloc[i, out.columns.get_loc("high")] = max(float(high[i]), hi)
        out.iloc[i, out.columns.get_loc("low")] = min(float(low[i]), lo)
        log.append(InjectionEvent(i, "micro_gap", size, zone,
                                  f"gap_{side}={size_pips:.2f}pips"))
        picked += 1

    data_mod.validate(out, expected_step_seconds=None)
    return AttackResult(out, log, "micro_gaps")


# ---------------------------------------------------------------------------
# 2. NEWS WHIPSAW — a fake impulse against the trend, then the real move.
# ---------------------------------------------------------------------------
def news_whipsaw(
    frame: pd.DataFrame,
    calendar: tuple[tuple[int, int], ...] | None = None,
    intensity: float = 1.0,
    *,
    pip: float = 0.0001,
    config: RAMSConfig = DEFAULT_RAMS,
    seed: int | None = None,
) -> AttackResult:
    """Replace candles at proxy calendar slots with a fake reversal then the move.

    ``calendar`` is the sealed proxy (default: ``config.news_slots_utc``); a real
    economic calendar is a NAMED DEBT owned by Phase 6. At each slot on a weekday,
    ``news_candles`` M15 bars are overwritten: a fake impulse AGAINST the local
    trend (sized to ``news_atr_mult * intensity * ATR``, enough to reach a typical
    stop zone) followed by a displacement back WITH the trend. Pessimism: a
    strategy stopped during the fake impulse never sees the real move.

    ``ts`` is untouched; every rewritten bar is a valid body (high/low regenerated),
    so the frame still passes :func:`app.core.data.validate`.
    """
    rng = np.random.default_rng((config.seed + 7919) if seed is None else seed)
    slots = calendar if calendar is not None else config.news_slots_utc
    out = _canon(frame)
    n = len(out)
    log: list[InjectionEvent] = []
    if n < 20:
        data_mod.validate(out, expected_step_seconds=None)
        return AttackResult(out, log, "news_whipsaw")

    high = out["high"].to_numpy()
    low = out["low"].to_numpy()
    close = out["close"].to_numpy()
    ts = out["ts"].to_numpy()
    atr = indicators.atr(high, low, close, 14)
    ema_f = indicators.ema(close, 9)
    ema_s = indicators.ema(close, 21)

    slot_set = set(slots)
    nb = max(1, config.news_candles)
    picked = 0
    for i in range(1, n):
        if picked >= MAX_INJECTIONS:
            break
        moment = pd.Timestamp(int(ts[i]), unit="s", tz="UTC")
        if moment.dayofweek >= 5:  # weekends are closed
            continue
        if (moment.hour, moment.minute) not in slot_set:
            continue
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        # Local trend direction (causal, last closed bar).
        if np.isfinite(ema_f[i - 1]) and np.isfinite(ema_s[i - 1]):
            trend_dir = 1 if ema_f[i - 1] >= ema_s[i - 1] else -1
        else:
            trend_dir = 1 if close[i - 1] >= close[max(0, i - 5)] else -1
        fake_dir = -trend_dir
        impulse = config.news_atr_mult * intensity * float(atr[i])
        start = float(close[i - 1])
        already = 1.0
        end = min(n, i + nb)
        span = end - i
        for k in range(span):
            j = i + k
            frac = (k + 1) / span
            if k < span - 1:
                # fake path against the trend
                price = start + fake_dir * impulse * frac
            else:
                # the real displacement back with the trend
                price = start + trend_dir * impulse * 0.7
            o = float(out["open"].iloc[j])
            wick = max(1e-6, 0.05 * impulse)
            hi, lo = _regen(o, price, wick)
            out.iloc[j, out.columns.get_loc("close")] = price
            out.iloc[j, out.columns.get_loc("high")] = max(float(high[j]), hi)
            out.iloc[j, out.columns.get_loc("low")] = min(float(low[j]), lo)
        zone = start + fake_dir * impulse
        log.append(InjectionEvent(i, "news_whipsaw", impulse, zone,
                                  f"fake_dir={fake_dir} candles={span}"))
        picked += 1

    data_mod.validate(out, expected_step_seconds=None)
    return AttackResult(out, log, "news_whipsaw")


# ---------------------------------------------------------------------------
# 3. DYNAMIC SLIPPAGE — the R36 adversarial cost layer.
# ---------------------------------------------------------------------------
def lot_proxy(sl_pips: float, median_sl_pips: float) -> float:
    """Impact proxy from the trade's OWN stop distance: tighter stop -> more lots.

    Computed, never a table: ``max(0, median_sl/sl - 1)``. A stop at the median
    has zero extra impact; a tighter stop pays more; a wider stop never pays
    less than the base (the proxy is floored at 0 — no flattering negative).
    """
    if sl_pips <= 0.0:
        raise ValueError(f"non-positive risk distance {sl_pips} — cannot price impact")
    return max(0.0, float(median_sl_pips) / float(sl_pips) - 1.0)


def slippage_pips(
    vol_percentile_at_entry: float,
    sl_pips: float,
    *,
    median_sl_pips: float,
    config: RAMSConfig = DEFAULT_RAMS,
) -> float:
    """R36 adversarial slippage in pips (never a table, never negative).

    ``base * (1 + k_vol*vol_pct) * (1 + k_impact*lot_proxy)``. Every factor is
    >= 1, so the result is >= ``base``: the layer can only worsen a fill.
    """
    vp = float(min(1.0, max(0.0, vol_percentile_at_entry)))
    lp = lot_proxy(sl_pips, median_sl_pips)
    return float(
        config.slippage_base_pips
        * (1.0 + config.slippage_vol_k * vp)
        * (1.0 + config.slippage_impact_k * lp)
    )


def dynamic_slippage(
    trades: list,
    *,
    vol_percentile_by_entry: dict[int, float] | None = None,
    config: RAMSConfig = DEFAULT_RAMS,
) -> list:
    """Apply the adversarial slippage layer to a trade list (R36).

    ``vol_percentile_by_entry`` maps a trade's ``entry_index`` to its entry-time
    volatility percentile (computed causally by the report from the frame); a
    missing entry is priced at the pessimistic 1.0 (maximum volatility), never a
    flattering zero. Returns a NEW list of trades with an extra ``ram_slippage_r``
    and a reduced ``net_r``; the pessimism invariant (extra cost >= 0) is
    property-tested.
    """
    vp = dict(vol_percentile_by_entry or {})
    if not trades:
        return []
    sls = [float(t.sl_pips) for t in trades]
    median_sl = float(np.median(sls)) if sls else 1.0
    out = []
    for t in trades:
        entry_vp = float(vp.get(int(t.entry_index), 1.0))
        extra_pips = slippage_pips(entry_vp, float(t.sl_pips),
                                   median_sl_pips=median_sl, config=config)
        extra_r = extra_pips / float(t.sl_pips)
        base_net = float(t.r_multiple if getattr(t, "net_r", None) is None else t.net_r)
        out.append(replace(
            t,
            ram_slippage_r=extra_r,
            net_r=base_net - extra_r,
        ))
    return out


# Backward-friendly alias used by the report.
apply_adversarial_slippage = dynamic_slippage


# ---------------------------------------------------------------------------
# 4. DRAWDOWN DECAY — the worst statistically-plausible path.
# ---------------------------------------------------------------------------
def drawdown_decay(
    trades: list,
    cluster: int | None = None,
    *,
    config: RAMSConfig = DEFAULT_RAMS,
) -> dict:
    """Cluster the losers into the worst plausible path; return its max drawdown.

    Pure post-processing: take ``net_r`` per trade, move the ``cluster`` most
    negative losers to the FRONT of the sequence (the worst statistically
    plausible ordering), leave the rest in their original order, and read the
    peak-to-trough drawdown off the cumulative-R equity curve. Pessimism: a
    non-negative count and a worst-path ordering, never a smoothed average.
    """
    rs = [float(t.r_multiple if getattr(t, "net_r", None) is None else t.net_r)
          for t in trades]
    k = int(config.decay_cluster if cluster is None else cluster)
    if k < 0:
        raise ValueError("decay cluster must be non-negative")
    losers = sorted((r for r in rs if r < 0.0))[:k]
    kept_ids = list(range(len(rs)))
    chosen: list[int] = []
    for r in losers:
        for idx in kept_ids:
            if idx in chosen:
                continue
            if rs[idx] == r:
                chosen.append(idx)
                break
    rest = [i for i in kept_ids if i not in chosen]
    order = chosen + rest
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    curve: list[float] = []
    for i in order:
        equity += rs[i]
        curve.append(equity)
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return {
        "worst_path_equity": curve,
        "max_drawdown_r": float(max_dd),
        "clustered": len(chosen),
        "cluster_size": k,
    }
