"""THE HONEST ENGINE — a pure, strategy-agnostic trade simulator.

Inputs are an M15 execution frame (already validated), boolean long/short signal
masks, a precomputed ATR(14) M15 array, structural stop/target level arrays, and
an exit policy. Level *derivation* is Phase 2's job; the engine only **enforces
the law** on whatever levels arrive, and records exactly what happened.

THE PESSIMISTIC-FILL LAW (``law.PESSIMISTIC_FILL``). Within a single bar the
engine checks the STOP before the TARGET: a bar whose range touches both the
stop and the target is booked as a **LOSS**. The intrabar path is unknowable from
OHLC, so the worst case wins. Likewise, when a bar gaps through a stop or target,
the fill is that bar's OPEN — the market's price — never the theoretical level.
This pessimism is deliberate: a scale that flatters itself measures nothing.

PER-BAR ORDER (fixed, documented, never reordered):
  a) gap check (j > entry bar): open beyond stop/target -> fill at that open.
  b) stop: long low <= cur_stop, short high >= cur_stop.
  c) parachute: first touch of entry +/- 2.5R arms it; cur_stop jumps to the
     +0.5R lock, which the stop may never violate again.
  d) target: long high >= target, short low <= target -> full close.
  e) trailing (only after arm): cur_stop = effective_stop(...) clamped by the lock.
  f) time stop: after max_bars_hold bars, close at the last close.

Pure: no I/O, no services, no global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import pandas as pd

from app.core import law
from app.core.data import validate

EXIT_STOP = "stop"
EXIT_TARGET = "target"
EXIT_TIME = "time"
EXIT_GAP_STOP = "gap_stop"
EXIT_GAP_TARGET = "gap_target"
VALID_EXIT_REASONS: tuple[str, ...] = (
    EXIT_STOP,
    EXIT_TARGET,
    EXIT_TIME,
    EXIT_GAP_STOP,
    EXIT_GAP_TARGET,
)

# Rejection gates, counted so honesty is auditable.
REJECT_VNSB = "vnsb"
REJECT_RR = "rr"
REJECT_RISK = "risk"
REJECT_LEVELS = "invalid_levels"
REJECT_NO_ENTRY_BAR = "no_entry_bar"


@dataclass(frozen=True)
class ExitPolicy:
    """When to leave a trade, beyond stop/target/parachute."""

    max_bars_hold: int | None = None
    trail_after_arm: bool = True


@dataclass(frozen=True)
class TradeRecord:
    """Everything the future Forensic Autopsy needs about one trade.

    ``r_multiple`` is the GROSS R the fills produced (the engine knows nothing of
    costs — it stays pure). ``pair``/``cost_r``/``net_r`` are R17 friction fields:
    the engine leaves ``pair=""`` and ``cost_r=0.0`` so its fills stay cost-free
    and deterministic; the evaluator stamps the pair and applies the sealed cost
    model in price->R conversion. Live callers of the engine see gross R, exactly
    as before.
    """

    direction: str
    entry_index: int
    entry_ts: int
    entry_price: float
    exit_index: int
    exit_ts: int
    exit_price: float
    stop_price: float
    target_price: float
    risk: float
    sl_pips: float
    r_multiple: float
    exit_reason: str
    parachute_armed: bool
    bars_held: int
    locked_stop: float | None
    lock_respected: bool
    pair: str = ""
    cost_r: float = 0.0
    net_r: float | None = None
    # R36 (Phase 5) — the RAMS adversarial slippage charged to this trade, in R.
    # Zero on a clean evaluation; set only inside app.quant.rams. It is an EXTRA
    # deduction already reflected in ``net_r`` when stamped (costs only worsen).
    ram_slippage_r: float = 0.0


class SimulationResult(NamedTuple):
    trades: list[TradeRecord]
    rejected: dict[str, int]


def _reject(rejected: dict[str, int], gate: str) -> None:
    rejected[gate] = rejected.get(gate, 0) + 1


def simulate(
    df: pd.DataFrame,
    long_signals: np.ndarray,
    short_signals: np.ndarray,
    atr: np.ndarray,
    stop_levels: np.ndarray,
    target_levels: np.ndarray,
    policy: ExitPolicy,
    *,
    pip: float,
    trailing_levels: np.ndarray | None = None,
) -> SimulationResult:
    """Walk every signal and return the trades it produced plus gate rejects.

    ``pip`` is the pair's pip size (from the Constellation). Signals are booleans
    aligned to ``df`` rows. All level/ATR arrays are aligned to ``df`` rows;
    ``None``/NaN levels reject the signal (fail-closed).
    """
    validate(df)
    n = len(df)
    if pip is None or pip <= 0:
        raise ValueError("pip must be positive")

    open_ = df["open"].to_numpy(dtype="float64")
    high = df["high"].to_numpy(dtype="float64")
    low = df["low"].to_numpy(dtype="float64")
    close = df["close"].to_numpy(dtype="float64")
    ts = df["ts"].to_numpy()

    for name, arr in (
        ("long_signals", long_signals),
        ("short_signals", short_signals),
        ("atr", atr),
        ("stop_levels", stop_levels),
        ("target_levels", target_levels),
    ):
        if len(arr) != n:
            raise ValueError(f"{name} length {len(arr)} != frame length {n}")

    trades: list[TradeRecord] = []
    rejected: dict[str, int] = {}

    for i in range(n):
        is_long = bool(long_signals[i])
        is_short = bool(short_signals[i])
        if not (is_long or is_short):
            continue
        if is_long and is_short:
            _reject(rejected, REJECT_LEVELS)  # ambiguous signal: refuse
            continue

        direction = "long" if is_long else "short"
        entry_index = i + 1
        if entry_index >= n:
            _reject(rejected, REJECT_NO_ENTRY_BAR)
            continue

        entry_price = open_[entry_index]
        stop_level = stop_levels[i]
        target_level = target_levels[i]
        atr_value = atr[i]

        if (
            not np.isfinite(stop_level)
            or not np.isfinite(target_level)
            or not np.isfinite(atr_value)
            or entry_price <= 0
        ):
            _reject(rejected, REJECT_LEVELS)
            continue

        risk = abs(entry_price - stop_level)
        sl_pips = risk / pip

        # risk > 0 is the first gate: a zero/negative stop distance is a
        # non-trade, regardless of what the band would say.
        if risk <= 0:
            _reject(rejected, REJECT_RISK)
            continue
        if law.vnsb_verdict(sl_pips, atr_value / pip).ok is False:
            _reject(rejected, REJECT_VNSB)
            continue
        if law.rr_verdict(abs(target_level - entry_price), risk).ok is False:
            _reject(rejected, REJECT_RR)
            continue

        # Levels must be oriented correctly around the entry (fail-closed).
        if direction == "long":
            if not (stop_level < entry_price < target_level):
                _reject(rejected, REJECT_LEVELS)
                continue
        else:
            if not (target_level < entry_price < stop_level):
                _reject(rejected, REJECT_LEVELS)
                continue

        trigger, locked_stop = law.parachute_levels(entry_price, stop_level, direction)
        cur_stop = stop_level
        armed = False
        lock_respected = True
        exit_price: float | None = None
        exit_reason: str | None = None
        exit_index = entry_index

        for j in range(entry_index, n):
            bars_held = j - entry_index + 1
            bar_o, bar_h, bar_l, bar_c = open_[j], high[j], low[j], close[j]

            # (a) gap through stop/target -> fill at the open.
            if j > entry_index:
                if direction == "long":
                    if bar_o <= cur_stop:
                        exit_price, exit_reason, exit_index = bar_o, EXIT_GAP_STOP, j
                        break
                    if bar_o >= target_level:
                        exit_price, exit_reason, exit_index = bar_o, EXIT_GAP_TARGET, j
                        break
                else:
                    if bar_o >= cur_stop:
                        exit_price, exit_reason, exit_index = bar_o, EXIT_GAP_STOP, j
                        break
                    if bar_o <= target_level:
                        exit_price, exit_reason, exit_index = bar_o, EXIT_GAP_TARGET, j
                        break

            # (b) stop BEFORE target — same-bar touch of both is a loss.
            if direction == "long" and bar_l <= cur_stop:
                exit_price, exit_reason, exit_index = cur_stop, EXIT_STOP, j
                break
            if direction == "short" and bar_h >= cur_stop:
                exit_price, exit_reason, exit_index = cur_stop, EXIT_STOP, j
                break

            # (c) parachute arm on first touch of the trigger.
            if not armed:
                if direction == "long" and bar_h >= trigger:
                    armed = True
                    cur_stop = locked_stop
                elif direction == "short" and bar_l <= trigger:
                    armed = True
                    cur_stop = locked_stop

            # (d) target.
            if direction == "long" and bar_h >= target_level:
                exit_price, exit_reason, exit_index = target_level, EXIT_TARGET, j
                break
            if direction == "short" and bar_l <= target_level:
                exit_price, exit_reason, exit_index = target_level, EXIT_TARGET, j
                break

            # (e) trailing, only after the arm.
            if armed and policy.trail_after_arm and trailing_levels is not None:
                candidate = trailing_levels[j]
                if np.isfinite(candidate):
                    cur_stop = law.effective_stop(
                        direction, entry_price, float(candidate), locked_stop
                    )
            if armed:
                if direction == "long" and cur_stop < locked_stop:
                    lock_respected = False
                if direction == "short" and cur_stop > locked_stop:
                    lock_respected = False

            # (f) time stop.
            if policy.max_bars_hold is not None and bars_held >= policy.max_bars_hold:
                exit_price, exit_reason, exit_index = bar_c, EXIT_TIME, j
                break
        else:
            # Ran out of data: close at the final close (still an honest exit).
            exit_price, exit_reason, exit_index = close[n - 1], EXIT_TIME, n - 1

        if exit_price is None:
            exit_price, exit_reason, exit_index = close[n - 1], EXIT_TIME, n - 1

        r_multiple = (
            (exit_price - entry_price) / risk
            if direction == "long"
            else (entry_price - exit_price) / risk
        )
        bars_held = exit_index - entry_index + 1

        trades.append(
            TradeRecord(
                direction=direction,
                entry_index=entry_index,
                entry_ts=int(ts[entry_index]),
                entry_price=float(entry_price),
                exit_index=exit_index,
                exit_ts=int(ts[exit_index]),
                exit_price=float(exit_price),
                stop_price=float(stop_level),
                target_price=float(target_level),
                risk=float(risk),
                sl_pips=float(sl_pips),
                r_multiple=float(r_multiple),
                exit_reason=exit_reason,
                parachute_armed=armed,
                bars_held=int(bars_held),
                locked_stop=float(locked_stop) if armed else None,
                lock_respected=lock_respected,
            )
        )

    return SimulationResult(trades, rejected)
