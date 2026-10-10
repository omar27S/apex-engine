"""THE DATA FOUNDATION — load, validate, resample, report gaps.

Canonical schema: ``ts`` (int64 epoch seconds, UTC, the bar's right edge /
close time), ``open``, ``high``, ``low``, ``close`` (float), ``volume`` (float).

Everything is fail-closed with the offending row number in the error. Gaps are
counted and returned by :func:`gap_report` — reported, never silently dropped.
Build Mode: no I/O at import time; :func:`load_parquet` reads only when called.

Timeframe convention: base bars are labeled by their right edge. Resampling uses
right-closed, right-labeled, epoch-aligned buckets, so a higher-timeframe bar
only ever contains lower bars that closed at or before its own right edge.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = ("ts", "open", "high", "low", "close", "volume")
PRICE_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close")
TF_MINUTES: dict[str, int] = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
VALID_TIMEFRAMES: tuple[str, ...] = tuple(TF_MINUTES)
MAX_REPORTED_ROWS = 5


class DataValidationError(ValueError):
    """Raised when a frame violates the canonical schema or its invariants."""


class GapReport(NamedTuple):
    """Missing-bar accounting between the first and last observed bar.

    ``base_minutes`` is the inferred native granularity (smallest observed
    positive spacing). ``missing_bars`` * ``base_minutes`` gives missing minutes.
    """

    observed_bars: int
    expected_bars: int
    missing_bars: int
    base_minutes: int | None

    @property
    def missing_minutes(self) -> int:
        if self.base_minutes is None:
            return 0
        return self.missing_bars * self.base_minutes


def _check_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"missing required column(s): {missing}")


def _rows(mask: np.ndarray) -> str:
    """Format the first few offending row numbers for an error message."""
    idx = np.flatnonzero(mask)
    shown = ", ".join(str(int(i)) for i in idx[:MAX_REPORTED_ROWS])
    if len(idx) > MAX_REPORTED_ROWS:
        shown += f", ... (+{len(idx) - MAX_REPORTED_ROWS} more)"
    return shown


def validate(
    df: pd.DataFrame, expected_step_seconds: int | None = None
) -> pd.DataFrame:
    """Validate a frame with vectorized checks and return it unchanged.

    Raises :class:`DataValidationError` on the first invariant violated, naming
    the offending row number(s) (0-based positional, first few reported).

    ``expected_step_seconds`` makes the cadence explicit: when given it must be a
    positive integer and every adjacent spacing must be a positive multiple of
    it. When omitted, cadence is not enforced here (gaps are reported separately
    by :func:`gap_report`).
    """
    if not isinstance(df, pd.DataFrame):
        raise DataValidationError(f"expected a DataFrame, got {type(df).__name__}")
    _check_columns(df)

    if not pd.api.types.is_integer_dtype(df["ts"]):
        raise DataValidationError("column 'ts' must be integer epoch seconds")
    for col in PRICE_COLUMNS + ("volume",):
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise DataValidationError(f"column '{col}' must be numeric")

    n = len(df)
    if n == 0:
        raise DataValidationError("empty frame")

    ts = df["ts"].to_numpy()
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    low = df["low"].to_numpy()
    c = df["close"].to_numpy()
    v = df["volume"].to_numpy()

    nan_mask = df[list(REQUIRED_COLUMNS)].isna().any(axis=1).to_numpy()
    if nan_mask.any():
        raise DataValidationError(f"NaN value at row(s) {_rows(nan_mask)}")

    nonpos = (o <= 0) | (h <= 0) | (low <= 0) | (c <= 0)
    if nonpos.any():
        raise DataValidationError(f"non-positive price at row(s) {_rows(nonpos)}")

    bad_high = h < np.maximum(o, c)
    if bad_high.any():
        i = int(np.flatnonzero(bad_high)[0])
        raise DataValidationError(
            f"high < max(open, close) at row {i} (high={h[i]}, open={o[i]}, close={c[i]})"
        )

    bad_low = low > np.minimum(o, c)
    if bad_low.any():
        i = int(np.flatnonzero(bad_low)[0])
        raise DataValidationError(
            f"low > min(open, close) at row {i} (low={low[i]}, open={o[i]}, close={c[i]})"
        )

    neg_vol = v < 0
    if neg_vol.any():
        raise DataValidationError(f"negative volume at row(s) {_rows(neg_vol)}")

    # Strictly increasing ts (monotonic, no duplicates).
    if n > 1:
        diffs = np.diff(ts)
        bad_ts = diffs <= 0
        if bad_ts.any():
            i = int(np.flatnonzero(bad_ts)[0]) + 1
            raise DataValidationError(
                f"ts not strictly increasing at row {i} (ts={ts[i]} <= {ts[i - 1]})"
            )

        if expected_step_seconds is not None:
            if not isinstance(expected_step_seconds, (int, np.integer)) or expected_step_seconds <= 0:
                raise DataValidationError(
                    "expected_step_seconds must be a positive integer"
                )
            step = int(expected_step_seconds)
            off_cadence = (diffs <= 0) | (np.mod(diffs, step) != 0)
            if off_cadence.any():
                raise DataValidationError(
                    f"ts spacing not a multiple of {step}s at row(s) {_rows(off_cadence)}"
                )

    return df


def load_parquet(path: str) -> pd.DataFrame:
    """Load a parquet file and return a validated canonical DataFrame."""
    df = pd.read_parquet(path)
    _check_columns(df)
    df = df.copy()
    df["ts"] = df["ts"].astype("int64")
    for col in PRICE_COLUMNS + ("volume",):
        df[col] = df[col].astype("float64")
    df = df[list(REQUIRED_COLUMNS)]
    return validate(df)


def gap_report(
    df: pd.DataFrame, expected_step_seconds: int | None = None
) -> GapReport:
    """Count missing bars/minutes between the first and last observed bar.

    Granularity is taken from ``expected_step_seconds`` when supplied; otherwise
    it is inferred as the smallest positive spacing between consecutive
    timestamps so that gaps do not distort the estimate. Vectorized. Reported,
    never dropped.
    """
    validate(df, expected_step_seconds)
    n = len(df)
    if n < 2:
        return GapReport(n, n, 0, None)
    ts = df["ts"].to_numpy()
    if expected_step_seconds is not None:
        base_seconds = int(expected_step_seconds)
    else:
        diffs = np.diff(ts)
        base_seconds = int(diffs.min())
    if base_seconds <= 0:
        return GapReport(n, n, 0, None)
    span = int(ts[-1] - ts[0])
    expected = span // base_seconds + 1
    missing = expected - n
    return GapReport(n, int(expected), int(missing), int(base_seconds // 60))


def infer_step_seconds(df: pd.DataFrame) -> int | None:
    """Return the smallest positive spacing between consecutive bars, or None."""
    if len(df) < 2:
        return None
    diffs = np.diff(df["ts"].to_numpy())
    positive = diffs[diffs > 0]
    if positive.size == 0:
        return None
    return int(positive.min())


# Spot FX reopens Sunday ~21:00-22:00 UTC and closes Friday ~21:00 UTC (or
# ~21:45 in non-US-DST stretches). A missing bar whose right edge falls in that
# window is a WEEKEND closure, not a hole. The boundary starts at Friday 21:00
# UTC because the earlier close is the conservative (wider) mark; it only ever
# classifies *missing* bars, so present bars are untouched.
def is_weekend_bar(right_edge_ts: int) -> bool:
    """True iff a bar's right edge (epoch seconds UTC) is in the weekend closure."""
    moment = pd.Timestamp(int(right_edge_ts), unit="s", tz="UTC")
    weekday = moment.dayofweek  # Monday=0 .. Sunday=6
    return weekday == 5 or weekday == 6 or (weekday == 4 and moment.hour >= 21)


# Fixed-date FX exchange holidays (UTC calendar) when the market is shut. These
# are recognized closures, not data holes; kept separate so the two-way weekend
# vs hole accounting stays honest.
def is_holiday_closure(right_edge_ts: int) -> bool:
    """True iff a bar's right edge falls on a fixed-date FX holiday (UTC)."""
    moment = pd.Timestamp(int(right_edge_ts), unit="s", tz="UTC")
    return (moment.month, moment.day) in ((1, 1), (12, 25), (12, 31))


class MissingBreakdown(NamedTuple):
    """Weekend closures, holiday closures, and TRUE holes among missing bars."""

    observed_bars: int
    expected_bars: int
    missing_bars: int
    weekend_bars: int
    holiday_bars: int
    true_hole_bars: int
    closed_pct: float


def missing_bars_breakdown(
    df: pd.DataFrame, expected_step_seconds: int = 900
) -> MissingBreakdown:
    """Classify every missing bar as a weekend closure, a holiday, or a true hole.

    Builds the full expected right-edge grid (every ``expected_step_seconds`` from
    the first to the last observed bar), subtracts the observed bars, and labels
    each missing grid point via :func:`is_weekend_bar` / :func:`is_holiday_closure`.
    Weekend takes precedence when the two overlap. Pure; nothing is dropped.
    """
    validate(df, expected_step_seconds)
    n = len(df)
    if n < 2:
        return MissingBreakdown(n, n, 0, 0, 0, 0, 0.0)

    observed = df["ts"].to_numpy()
    step = int(expected_step_seconds)
    grid = np.arange(int(observed[0]), int(observed[-1]) + 1, step, dtype="int64")
    present = np.isin(grid, observed)
    missing = grid[~present]

    if missing.size == 0:
        return MissingBreakdown(n, int(grid.size), 0, 0, 0, 0, 0.0)

    weekend = np.array([is_weekend_bar(int(t)) for t in missing], dtype=bool)
    holiday = np.array(
        [(not wk) and is_holiday_closure(int(t)) for wk, t in zip(weekend, missing)],
        dtype=bool,
    )
    weekend_bars = int(weekend.sum())
    holiday_bars = int(holiday.sum())
    true_holes = int(missing.size - weekend_bars - holiday_bars)
    closed = weekend_bars + holiday_bars
    return MissingBreakdown(
        observed_bars=n,
        expected_bars=int(grid.size),
        missing_bars=int(missing.size),
        weekend_bars=weekend_bars,
        holiday_bars=holiday_bars,
        true_hole_bars=true_holes,
        closed_pct=closed / missing.size,
    )


def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample a canonical frame to ``tf`` with strictly causal right-edge bars.

    Buckets are right-closed and right-labeled on epoch-aligned boundaries, so a
    bar labeled at time ``T`` contains only base bars that closed in ``(T - tf,
    T]``. Empty buckets are dropped, and a trailing bucket that has not closed
    (no base bar exactly on its right edge) is dropped as incomplete.
    """
    validate(df)
    key = tf.upper()
    if key not in TF_MINUTES:
        raise ValueError(f"unknown timeframe {tf!r}; valid: {VALID_TIMEFRAMES}")

    minutes = TF_MINUTES[key]
    frame = df.copy()
    frame.index = pd.to_datetime(frame["ts"], unit="s", utc=True)

    resampled = (
        frame.resample(f"{minutes}min", closed="right", label="right", origin="epoch")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["open"])
    )

    if len(resampled):
        last_right_edge = resampled.index[-1].value // 1_000_000_000
        if int(df["ts"].iloc[-1]) < int(last_right_edge):
            resampled = resampled.iloc[:-1]

    out = resampled.reset_index(drop=True)
    right_edges = resampled.index.as_unit("s").astype("int64").to_numpy()
    out.insert(0, "ts", right_edges)
    out["ts"] = out["ts"].astype("int64")
    return out[list(REQUIRED_COLUMNS)]
