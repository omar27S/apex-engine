"""THE HISTORIAN -- the memory that heals itself (R118).

Before this organ, the deep parquet frame was a photograph: taken once by
the blood supply (``tools/fetch_history.py``) and then left to fossilize
while the organism lived on. On 2026-10-20 the audit measured the wound:
the factory's universe (``_load_universe`` reads the parquet TAIL) ended at
2026-10-09 04:00 UTC -- eleven days of evolution crowned champions of a
market that no longer existed, and the mouth's stitched frame declared an
honest ``gap_bars: 1129``. The photograph was accurate and dead.

The historian is the cure, and it is built on six laws:

1. THE PAST IS NEVER REWRITTEN. An existing parquet bar always wins a
   timestamp collision. New bars may only be APPENDED after the edge.
   (``keep="first"`` with the old frame first in the concatenation.)

2. MONOTONIC OR DEATH. If the healed frame would not pass
   ``app.core.data.validate`` (strictly increasing ts, positive prices,
   coherent high/low), NOTHING is written -- the old memory stays whole,
   the failure is spoken in the health artifact. The write is atomic
   (``.tmp`` + ``os.replace``), so a crash mid-heal cannot bruise the past.

3. THE MARKET SLEEPS ON WEEKENDS. An empty Saturday/Sunday chunk is
   closure, not failure. A chunk that lies entirely inside a UTC weekend
   is not even asked of the network; a partially-empty chunk counts its
   weekend days as closed and its silent weekdays as a soft signal
   (holidays exist; lag exists; neither is a wound).

4. TWO FEEDS, ONE MEMORY. The deep hole is filled by the Dukascopy blood
   supply (the same source, schema and side as the original photograph);
   the fresh edge is folded from the LIVE M15 tape (R112) -- the organism's
   own eyes. On a timestamp collision between the two feeds, Dukascopy
   wins (the deeper source is the more authoritative one), and the tape
   only ever extends BEYOND it. Every folded bar carries the tape's tick
   count as its volume -- the same tick-count semantics Dukascopy uses.

5. EVERY WOUND IS SPOKEN. Fetch errors are carried VERBATIM into the
   health artifact. A pair that cannot be healed keeps its old memory and
   a verdict that says why. The artifact reports what IS, including its
   own failures -- an organ that cannot confess is an organ that lies.

6. THE ARTIFACT IS THE ORGAN'S VOICE. ``history_health.json`` (committed
   by the heart with the other state files) speaks the frame's age, the
   bars healed per pair, the feeds' contributions, and the verdict. The
   guardian (14th check, ``history_edge``) reads this voice -- the
   guardian never re-derives what an organ can simply tell it.

Operational shape (deploy/historian/, daily at 02:37 UTC, before the Grand):

    python -m tools.historian --pairs EURUSD GBPUSD ...   # heal + speak
    python -m tools.historian --dry-run                   # diagnose only

The historian never touches the sealed red lines: it adds no pairs to the
constellation, changes no position sizing, proposes no trades. It is a
memory organ, not a hand.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from app.core import data as data_mod
from app.core.data import DataValidationError

HISTORIAN_VERSION = 1

# The M15 cadence of the deep frame (seconds).
STEP_S = 900

# Verdict thresholds for the EDGE AGE (seconds since the newest deep bar).
FRESH_S = 36 * 3600          # < 36h: the frame saw yesterday at least
STALE_S = 96 * 3600          # < 96h: a weekend may explain it (72h + lag)
# >= 96h with no hard failure is "stale"; a hard failure or an invalid
# healed frame is "wounded" regardless of age. The GUARDIAN fails the
# organism at the harsher 120h (five days -- past any weekend + holiday).

# The blood supply's honest lag guard: never ask Dukascopy for the last
# N hours (its freeserv feed trails the present; asking is not wrong, but
# counting the answer as "the edge" would be -- the TAPE is the fresh edge).
DEFAULT_LAG_HOURS = 6

# Fetch shape (mirrors the blood supply's own manners).
DEFAULT_MAX_CHUNK_DAYS = 3
DEFAULT_PACING_S = 0.6

# The fetcher contract: (instrument "EUR/USD", start, end) -> (frame|None, error|None)
# A frame with no rows is a VALID answer (market closed); an error string is
# a FAILURE. The fetcher must never raise.
Fetcher = Callable[[str, _dt.datetime, _dt.datetime], tuple[Optional[pd.DataFrame], Optional[str]]]


# ---------------------------------------------------------------------------
# the real fetcher (the blood supply, asked politely)
# ---------------------------------------------------------------------------
def dukascopy_fetcher(instrument: str, start: _dt.datetime,
                      end: _dt.datetime) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """One Dukascopy ask with the supply's own backoff manners. Never raises."""
    try:
        import dukascopy_python as dk
    except Exception as exc:  # pragma: no cover - environment wound, spoken
        return None, f"import dukascopy_python: {type(exc).__name__}: {exc}"
    last_error: Optional[str] = None
    for attempt in range(1, 4):
        try:
            frame = dk.fetch(instrument, "15MIN", "B", start, end, max_retries=2)
            if frame is not None and len(frame) > 0:
                return frame, None
            return None, None  # empty is a valid answer (closure/lag)
        except Exception as exc:  # noqa: BLE001 - network layer, spoken verbatim
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < 3:
            time.sleep(1.5 * (2 ** (attempt - 1)))
    return None, last_error


# ---------------------------------------------------------------------------
# the tape reader (the organism's own eyes, R112)
# ---------------------------------------------------------------------------
def read_tape(tape_path: str | Path) -> tuple[dict[str, list[dict]], int, int]:
    """Read the live M15 tape into per-symbol APEX-schema rows.

    Returns (per_symbol_rows, malformed_lines, non_bar_lines). Malformed
    lines are counted and skipped -- the tape is append-only history, and a
    torn tail (a crash mid-write) is expected once in an organism's life.
    """
    per_symbol: dict[str, list[dict]] = {}
    malformed = 0
    non_bar = 0
    path = Path(tape_path)
    if not path.exists():
        return per_symbol, malformed, non_bar
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                malformed += 1
                continue
            if not isinstance(d, dict) or d.get("kind") != "m15_bar":
                non_bar += 1
                continue
            bar = _tape_bar_to_apex(d)
            if bar is None:
                malformed += 1
                continue
            per_symbol.setdefault(str(d.get("symbol")), []).append(bar)
    return per_symbol, malformed, non_bar


def _tape_bar_to_apex(d: dict) -> Optional[dict]:
    """One tape bar -> APEX schema row, or None when the bar is malformed."""
    try:
        ts = int(d["open_ms"]) // 1000
        o = float(d["o"]); h = float(d["h"]); low = float(d["l"]); c = float(d["c"])
        vol = float(d.get("n", 0.0))
    except Exception:
        return None
    if ts <= 0 or o <= 0 or h <= 0 or low <= 0 or c <= 0 or vol < 0:
        return None
    if h < max(o, c) or low > min(o, c):
        return None
    if ts % STEP_S != 0:  # the tape opens on the M15 grid by law (R112)
        return None
    return {"ts": ts, "open": o, "high": h, "low": low, "close": c, "volume": vol}


# ---------------------------------------------------------------------------
# the healing of one pair
# ---------------------------------------------------------------------------
@dataclass
class PairReport:
    pair: str
    verdict: str                    # healed | fresh | stale | wounded | absent
    bars_before: int = 0
    bars_after: int = 0
    deep_added: int = 0             # bars from the blood supply
    tape_added: int = 0             # bars folded from the live tape
    market_closed_days: int = 0     # honest weekend closure days
    empty_weekday_days: int = 0     # soft signal (holidays, supply lag)
    tape_rejected: int = 0          # incoming tape bars refused by geometry
    edge_ts: int = 0                # epoch seconds of the newest deep bar
    edge_age_s: int = 0             # now - edge_ts
    failures: list[str] = field(default_factory=list)
    skipped: bool = False           # true when nothing needed healing

    def as_dict(self) -> dict:
        return asdict(self)


def _days_touched(start: _dt.datetime, end: _dt.datetime) -> list[_dt.date]:
    """Every calendar date whose day is even partly inside [start, end).

    A window closing at midnight does NOT touch its closing date (nothing
    of that day lies inside); any later closing time touches it.
    """
    if end <= start:
        return []
    first = start.date()
    if end.time() == _dt.time(0, 0):
        last = end.date() - _dt.timedelta(days=1)
    else:
        last = end.date()
    if last < first:
        return []
    days: list[_dt.date] = []
    cursor = first
    while cursor <= last:
        days.append(cursor)
        cursor += _dt.timedelta(days=1)
    return days


def _weekend_days(start: _dt.datetime, end: _dt.datetime) -> int:
    """Count Sat/Sun UTC days touched by [start, end) (partial days count)."""
    return sum(1 for d in _days_touched(start, end) if d.weekday() >= 5)


def _total_days(start: _dt.datetime, end: _dt.datetime) -> int:
    return len(_days_touched(start, end))


def _dukascopy_to_apex(frame: pd.DataFrame) -> pd.DataFrame:
    """The blood supply's own conversion (fetched frames are UTC-indexed)."""
    ts = frame.index.as_unit("s").astype("int64").to_numpy()
    return pd.DataFrame({
        "ts": ts.astype("int64"),
        "open": frame["open"].to_numpy(dtype="float64"),
        "high": frame["high"].to_numpy(dtype="float64"),
        "low": frame["low"].to_numpy(dtype="float64"),
        "close": frame["close"].to_numpy(dtype="float64"),
        "volume": frame["volume"].to_numpy(dtype="float64"),
    })


def _valid_apex_bar(b: dict) -> bool:
    """Defense in depth: every bar entering the frame is checked alone."""
    try:
        ts = int(b["ts"]); o = float(b["open"]); h = float(b["high"])
        low = float(b["low"]); c = float(b["close"]); v = float(b["volume"])
    except (KeyError, TypeError, ValueError):
        return False
    if ts <= 0 or o <= 0 or h <= 0 or low <= 0 or c <= 0 or v < 0:
        return False
    if h < max(o, c) or low > min(o, c):
        return False
    if ts % STEP_S != 0:
        return False
    return True


def heal_pair(
    pair: str,
    parquet_path: str | Path,
    tape_bars: list[dict],
    now: _dt.datetime,
    fetcher: Fetcher,
    *,
    lag_hours: int = DEFAULT_LAG_HOURS,
    max_chunk_days: int = DEFAULT_MAX_CHUNK_DAYS,
    pacing_s: float = DEFAULT_PACING_S,
    write: bool = True,
) -> PairReport:
    """Heal one pair's deep memory. LAWS 1-5 are enforced here.

    ``write=False`` is the diagnosis mode (``--dry-run``): everything is
    measured, nothing is written.
    """
    path = Path(parquet_path)
    report = PairReport(pair=pair, verdict="wounded")
    if not path.exists():
        report.verdict = "absent"
        report.failures.append("parquet absent -- the historian never "
                               "creates a deep frame, it only heals one")
        report.skipped = True
        return report

    try:
        old = data_mod.load_parquet(str(path))
    except Exception as exc:  # the existing memory is unreadable: DO NOT touch it
        report.failures.append(f"existing parquet unreadable: "
                               f"{type(exc).__name__}: {exc}")
        return report

    report.bars_before = len(old)
    report.edge_ts = int(old["ts"].iloc[-1])
    now_epoch = int(now.timestamp())

    # ---- the deep window: [edge + 1 bar, now - lag] ----------------------
    deep_start = _dt.datetime.fromtimestamp(report.edge_ts + STEP_S, _dt.timezone.utc)
    deep_end = now - _dt.timedelta(hours=lag_hours)
    deep_frames: list[pd.DataFrame] = []
    instrument = f"{pair[:3]}/{pair[3:]}"

    if deep_start < deep_end:
        cursor = deep_start
        while cursor < deep_end:
            chunk_end = min(cursor + _dt.timedelta(days=max_chunk_days), deep_end)
            total = _total_days(cursor, chunk_end)
            weekend = _weekend_days(cursor, chunk_end)
            if total > 0 and weekend == total:
                # LAW 3: the whole chunk is the market's sleep -- don't even ask
                report.market_closed_days += total
            else:
                frame, error = fetcher(instrument, cursor, chunk_end)
                if error is not None:
                    report.failures.append(f"{instrument} "
                                           f"[{cursor.date()},{chunk_end.date()}): {error}")
                elif frame is not None and len(frame) > 0:
                    deep_frames.append(_dukascopy_to_apex(frame))
                else:
                    # empty on a (partly) weekday chunk: soft signal, split honestly
                    report.market_closed_days += weekend
                    report.empty_weekday_days += (total - weekend)
                if pacing_s > 0:
                    time.sleep(pacing_s)
            cursor = chunk_end
    else:
        report.skipped = True

    # ---- assemble: old wins, deep second, tape last (LAW 1 + LAW 4) ------
    old_ts = set(int(t) for t in old["ts"].tolist())
    parts: list[pd.DataFrame] = [old]
    deep_all = (pd.concat(deep_frames, ignore_index=True)
                .drop_duplicates(subset="ts", keep="first")
                if deep_frames else None)
    if deep_all is not None:
        parts.append(deep_all)
    deep_ts = set()
    if deep_all is not None:
        deep_ts = set(int(t) for t in deep_all["ts"].tolist()) - old_ts
    tape_kept: list[dict] = []
    for b in tape_bars:
        if not _valid_apex_bar(b):
            report.tape_rejected += 1
            continue
        if b["ts"] <= report.edge_ts or b["ts"] in old_ts or b["ts"] in deep_ts:
            continue  # the tape only rides BEYOND what the deep feeds wrote
        tape_kept.append(b)
    if tape_kept:
        parts.append(pd.DataFrame(tape_kept))

    merged = pd.concat(parts, ignore_index=True)
    merged = merged.sort_values("ts", kind="stable")
    merged = merged.drop_duplicates(subset="ts", keep="first").reset_index(drop=True)
    merged = merged[list(data_mod.REQUIRED_COLUMNS)]
    merged["ts"] = merged["ts"].astype("int64")
    for col in data_mod.PRICE_COLUMNS + ("volume",):
        merged[col] = merged[col].astype("float64")

    report.bars_after = len(merged)
    report.deep_added = len(deep_ts)
    report.tape_added = len(tape_kept)
    report.edge_ts = int(merged["ts"].iloc[-1]) if len(merged) else report.edge_ts
    report.edge_age_s = max(0, now_epoch - report.edge_ts)

    # ---- LAW 2: monotonic or death ---------------------------------------
    try:
        data_mod.validate(merged)
    except DataValidationError as exc:
        report.failures.append(f"healed frame would not validate: {exc}")
        report.bars_after = report.bars_before  # nothing was written
        return report

    # ---- the write (atomic) ----------------------------------------------
    if write and report.bars_after != report.bars_before:
        tmp = path.with_suffix(".parquet.tmp")
        merged.to_parquet(tmp, index=False)
        os.replace(tmp, path)

    if report.failures:
        report.verdict = "wounded"
    elif report.edge_age_s >= STALE_S:
        report.verdict = "stale"
    elif report.bars_after != report.bars_before:
        report.verdict = "healed"
    elif report.edge_age_s < FRESH_S:
        report.verdict = "fresh"
    else:
        report.verdict = "stale"
    return report


# ---------------------------------------------------------------------------
# the whole constellation
# ---------------------------------------------------------------------------
def heal_all(
    pairs: list[str],
    data_dir: str | Path,
    tape_path: str | Path,
    out_path: str | Path,
    now: _dt.datetime,
    fetcher: Fetcher,
    *,
    lag_hours: int = DEFAULT_LAG_HOURS,
    max_chunk_days: int = DEFAULT_MAX_CHUNK_DAYS,
    pacing_s: float = DEFAULT_PACING_S,
    write: bool = True,
) -> dict:
    """Heal every pair and speak the health artifact (LAW 6)."""
    per_symbol, malformed, non_bar = read_tape(tape_path)
    reports: dict[str, dict] = {}
    for pair in pairs:
        tape_bars = per_symbol.get(pair, [])
        rep = heal_pair(
            pair, Path(data_dir) / f"{pair}_M15.parquet", tape_bars, now,
            fetcher, lag_hours=lag_hours, max_chunk_days=max_chunk_days,
            pacing_s=pacing_s, write=write,
        )
        reports[pair] = rep.as_dict()

    wounded = [p for p, r in reports.items() if r["verdict"] == "wounded"]
    absent = [p for p, r in reports.items() if r["verdict"] == "absent"]
    oldest = max(reports.items(), key=lambda kv: kv[1]["edge_age_s"], default=None)

    if wounded or absent:
        verdict = "wounded"
    elif oldest and oldest[1]["edge_age_s"] >= STALE_S:
        verdict = "stale"
    else:
        verdict = "healthy"

    artifact = {
        "version": HISTORIAN_VERSION,
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": verdict,
        "heals": sum(1 for r in reports.values() if r["verdict"] == "healed"),
        "bars_healed": sum(r["bars_after"] - r["bars_before"]
                           for r in reports.values()
                           if r["verdict"] == "healed"),
        "deep_bars": sum(r["deep_added"] for r in reports.values()),
        "tape_bars": sum(r["tape_added"] for r in reports.values()),
        "market_closed_days": sum(r["market_closed_days"] for r in reports.values()),
        "oldest_edge": {"pair": oldest[0], "age_h": round(oldest[1]["edge_age_s"] / 3600, 1)}
                      if oldest else None,
        "tape": {"malformed": malformed, "non_bar": non_bar},
        "wounded": wounded,
        "absent": absent,
        "pairs": reports,
    }

    out = Path(out_path)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(artifact, indent=1, sort_keys=True))
    os.replace(tmp, out)
    return artifact
