"""THE LIVE MOUTH -- the organ that speaks to the PRESENT (R113, 2026-10-21).

The wound this module closes is the oldest one in the body: the signal
generator asked the market "would you enter RIGHT NOW?" while reading a
parquet history that ended NINE DAYS before (the mouth spoke of a market
that no longer existed; the eye was alive, the nerve was cut). The live
tape (R112) gives the wire a memory; this module gives the memory a VOICE:

* :func:`read_tape` -- the tape's bars per symbol, tolerant of a torn tail;
* :func:`stitch_history` -- the deep parquet past + the living present, one
  honest frame (duplicates dropped by timestamp, the GAP declared, never
  bridged with a fabricated bar);
* :func:`stale_guard` -- a frame whose last bar is older than three M15
  turns is BLIND: the mouth says "non vedo" and never invents an entry on
  a dead tape (the guard that kills the old lie forever);
* :func:`resolve_open` -- yesterday's words scored against today's price:
  each open candidate walks the bars born after it, target before stop
  (an ambiguous bar resolves as the STOP -- pessimism is honesty's default),
  and what never resolved expires marked to the last close;
* :func:`live_evidence` -- the strategy's LIVE hit record as a Wilson
  lower bound (the same 95% arithmetic the factory crowns with): a young
  strategy speaks with ``None`` confidence, never an invented number;
* :func:`agreement` -- how many co-firing strategies point the same way on
  the same pair (a consensus is a fact; a lone voice is a fact too, and
  the block never hides which one spoke).

Honesty is binding (the Director's laws, at the mouth):
  * MEASURE BEFORE SPEECH -- no bars, no candidates; stale bars, no
    candidates; the blindness is SAID, never papered over;
  * THE RECEIPT IS EVIDENCE -- every turn appends a row to the signal
    ledger (born, resolved, blind, with reasons), so the organ's own life
    is auditable like every other organ's;
  * PURE AT IMPORT (Scar #6) -- no I/O in the math; the CLI owns the disk.
"""

from __future__ import annotations

import math

__all__ = [
    "MOUTH_VERSION", "STALE_MAX_BARS", "HORIZON_BARS",
    "read_tape", "bars_from_rows", "stitch_history", "stale_guard",
    "resolve_open", "resolve_many", "live_evidence", "agreement",
    "wilson_lb",
]

MOUTH_VERSION: int = 1
# A last bar older than THREE M15 turns (45 min) is a dead tape: blind.
STALE_MAX_BARS: int = 3
# A candidate the market neither stopped nor targeted within a day (96 M15
# bars) expires, marked to the last close (an honest end, never a zombie).
HORIZON_BARS: int = 96


def wilson_lb(wins: int, trials: int, z: float = 1.96) -> float:
    """The same Wilson lower bound the factory crowns with (95%, two-sided).

    Re-derived here (not imported) so the mouth stays import-light and the
    arithmetic it judges with is the one it can read aloud. ``trials <= 0``
    has no evidence: 0.0 (the bound at zero, not a rank).
    """
    if trials <= 0:
        return 0.0
    n = float(trials)
    p = float(wins) / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    spread = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return (center - spread) / denom


# ---------------------------------------------------------------------------
# THE TAPE -- reading the wire's memory
# ---------------------------------------------------------------------------
def read_tape(text: str) -> dict[str, list[dict]]:
    """Parse the tape's JSONL text into ``{symbol: [bar, ...]}`` (torn-safe).

    A line that is not a closed ``m15_bar`` (a crash mid-write, a foreign
    row) is skipped, never guessed from. Bars come out sorted by open time,
    one per timestamp (a duplicate open_ms keeps the FIRST -- the tape is
    append-only; a re-write would be a re-write of history).
    """
    out: dict[str, dict[int, dict]] = {}
    for line in str(text).splitlines():
        line = line.strip()
        if not line:
            continue
        import json
        try:
            row = json.loads(line)
        except ValueError:
            continue  # torn tail: skipped, not fabricated
        if not isinstance(row, dict) or row.get("kind") != "m15_bar":
            continue
        sym = row.get("symbol")
        om = row.get("open_ms")
        cm = row.get("close_ms")
        if not isinstance(sym, str) or not isinstance(om, int):
            continue
        # THE HOUSE LABELS AN M15 BAR BY ITS CLOSE (the parquet's tongue: the
        # resampler drops a trailing H1 bucket whose right edge no base bar
        # carries -- so a bar holding 22:45-23:00 must be ts 23:00, not 22:45).
        # The tape's ``close_ms`` IS that label; open_ms + 900 is the fallback.
        close_s = ((int(cm) if isinstance(cm, int) else om + 900_000)) // 1000
        try:
            bar = {"ts": close_s,
                   "open": float(row["o"]), "high": float(row["h"]),
                   "low": float(row["l"]), "close": float(row["c"]),
                   "volume": float(row.get("n") or 0.0),
                   "ticks": int(row.get("n") or 0),
                   "source": str(row.get("source") or "")}
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(bar[k]) for k in ("open", "high", "low", "close")):
            continue
        per_sym = out.setdefault(sym, {})
        if bar["ts"] not in per_sym:           # a duplicate open keeps the first
            per_sym[bar["ts"]] = bar
    return {s: [rows[ts] for ts in sorted(rows)] for s, rows in out.items()}


def bars_from_rows(rows) -> list[dict]:
    """Normalize pre-parsed bar rows (parquet tails, test fixtures) to bars.

    Accepts dicts shaped like the tape's bar rows (``open_ms``/``o``/``h``/
    ``l``/``c``/``n`` -- translated to seconds once, here) OR already-canonical
    bars (``ts``/``open``/... in SECONDS); returns the canonical list, sorted
    by open time, one per timestamp.
    """
    canonical: dict[int, dict] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if "ts" in r and "close" in r:
            ts = r.get("ts")
            bar = dict(r)
        else:
            om = r.get("open_ms")
            try:
                # the house label: the bar's CLOSE edge, in seconds
                ts = ((int(om) + 900_000) // 1000
                      if isinstance(om, int) else None)
                bar = {"ts": ts, "open": float(r["o"]),
                       "high": float(r["h"]), "low": float(r["l"]),
                       "close": float(r["c"]),
                       "volume": float(r.get("n") or 0.0),
                       "ticks": int(r.get("n") or 0),
                       "source": str(r.get("source") or "")}
            except (KeyError, TypeError, ValueError):
                continue
        if not isinstance(ts, int):
            continue
        if not all(isinstance(bar.get(k), (int, float)) for k in
                   ("open", "high", "low", "close")):
            continue
        if ts not in canonical:
            canonical[ts] = bar
    return [canonical[ts] for ts in sorted(canonical)]


# ---------------------------------------------------------------------------
# THE STITCH -- the deep past meets the living present
# ---------------------------------------------------------------------------
def stitch_history(parquet_tail: list[dict], live_bars: list[dict],
                   *, min_live_bars: int = 12_000) -> tuple[list[dict], dict]:
    """One honest frame from the parquet past + the tape's present.

    * duplicates (same ``ts``) keep the TAPE's bar -- the live eye is the
      younger witness of the same minute;
    * bars are sorted by ``ts``; the GAP between the parquet's last and the
      tape's first is COUNTED and declared (never bridged: a missing bar is
      an honest missing bar);
    * when the tape alone carries ``>= min_live_bars`` bars (default 12_000:
      the deepest H1 warmup -- the same number the Grand's tail asks) the
      stitch drops the parquet entirely: the young witness has enough
      memory of its own, and the meta says so.

    Returns ``(bars, meta)`` where meta is the provenance the artifact must
    carry: ``{"source": "stitch"|"live"|"parquet", "parquet_bars",
    "live_bars", "gap_bars"}``.
    """
    live = sorted((b for b in (live_bars or [])
                   if isinstance(b, dict) and isinstance(b.get("ts"), int)),
                  key=lambda b: b["ts"])
    past = sorted((b for b in (parquet_tail or [])
                   if isinstance(b, dict) and isinstance(b.get("ts"), int)),
                  key=lambda b: b["ts"])

    if len(live) >= max(1, int(min_live_bars)):
        meta = {"source": "live", "parquet_bars": 0, "live_bars": len(live),
                "gap_bars": 0}
        return list(live), meta

    by_ts: dict[int, dict] = {}
    for b in past:
        by_ts[b["ts"]] = b
    first_live_ts = live[0]["ts"] if live else None
    if first_live_ts is not None:
        stale_past = [b for b in past if b["ts"] >= first_live_ts]
        for b in stale_past:               # the tape owns the minutes it saw
            by_ts.pop(b["ts"], None)
    for b in live:
        by_ts[b["ts"]] = b
    bars = [by_ts[ts] for ts in sorted(by_ts)]

    gap_bars = 0
    if bars and live and past and past[-1]["ts"] < (first_live_ts or 0):
        step_s = 900                          # one M15, in the bars' own unit
        holes = int(((first_live_ts or 0) - past[-1]["ts"]) // step_s) - 1
        gap_bars = max(0, holes)
    meta = {"source": ("stitch" if past and live else
                       ("live" if live else "parquet")),
            "parquet_bars": len([b for b in bars if b.get("source", "") == ""]),
            "live_bars": len(live), "gap_bars": gap_bars}
    return bars, meta


# ---------------------------------------------------------------------------
# THE GUARD -- a dead tape speaks nothing
# ---------------------------------------------------------------------------
def stale_guard(bars: list[dict], *, now_epoch_s: float, m15_s: int = 900,
                max_bars: int = STALE_MAX_BARS) -> tuple[bool, str, float]:
    """Is the frame's last bar young enough to speak about the PRESENT?

    The bars' ``ts`` is EPOCH SECONDS (the canonical unit, the parquet's
    tongue); ``now_epoch_s`` speaks the same unit. Returns
    ``(speaks, reason, last_bar_age_s)``. A last bar older than ``max_bars``
    M15 turns is a dead tape: the mouth declares blindness (``reason`` says
    so in plain words) -- the old wound (nine-day-old bars birthing "live"
    entries) is closed by this guard forever.
    """
    if not bars:
        return False, "nastro vuoto (nessuna barra)", -1.0
    last_ts = bars[-1]["ts"]
    age_s = max(0.0, float(now_epoch_s) - float(last_ts))
    limit_s = float(max_bars) * float(m15_s)
    if age_s > limit_s:
        return False, f"nastro fermo ({age_s/60.0:.0f} min), bocca chiusa", age_s
    return True, "nastro vivo", age_s


# ---------------------------------------------------------------------------
# THE RESOLUTION -- yesterday's words, today's price
# ---------------------------------------------------------------------------
def resolve_open(candidate: dict, bars: list[dict], *,
                 horizon_bars: int = HORIZON_BARS) -> dict | None:
    """Walk the bars born after a candidate; return its outcome or ``None``.

    Rules (honest, pessimistic where ambiguous):

    * the walk starts at the first bar whose ``ts`` is STRICTLY after the
      candidate's bar (its own birth bar cannot resolve it);
    * a bar whose path could touch BOTH the target and the stop is resolved
      as the STOP -- when the tape cannot say which came first, the mouth
      assumes the market punished it first (pessimism is honesty here);
    * target hit first -> ``outcome_r = +target_rr``; stop hit first ->
      ``outcome_r = -1.0`` (the unit every organ already thinks in);
    * neither within ``horizon_bars`` -> ``expired``: marked to the last
      walked close, ``outcome_r`` = signed distance in R -- the position's
      honest mark. Expiry fires ONLY when the walk has SEEN the whole
      horizon (a 15-minute-old candidate with one bar walked is STILL
      OPEN, not expired -- the live wound of 23:15 UTC, 2026-10-20, where
      forty-one newborn words were "expired" by one bar, fixed the same
      hour);
    * fewer bars than the horizon and no hit -> ``None``: the market has
      not finished speaking.
    """
    if not isinstance(candidate, dict):
        return None
    entry = candidate.get("entry_price")
    stop_d = candidate.get("stop_distance")
    target_d = candidate.get("target_distance")
    direction = candidate.get("direction")
    bar_ts = candidate.get("bar_ts")
    if bar_ts is None:                      # 0 is a bar too -- never `or`
        bar_ts = candidate.get("open_ms")
    if not (isinstance(entry, (int, float)) and isinstance(stop_d, (int, float))
            and stop_d > 0 and direction in (1, -1)
            and isinstance(bar_ts, int)):
        return None  # an unmeasurable candidate is never resolved by guessing
    target_rr = None
    if isinstance(target_d, (int, float)) and target_d > 0:
        target_rr = float(target_d) / float(stop_d)

    walk = [b for b in bars if b["ts"] > bar_ts][:max(1, int(horizon_bars))]
    for b in walk:
        if direction == 1:
            hit_t = target_d is not None and b["high"] >= entry + target_d
            hit_s = b["low"] <= entry - stop_d
        else:
            hit_t = target_d is not None and b["low"] <= entry - target_d
            hit_s = b["high"] >= entry + stop_d
        if hit_s:                       # ambiguous or stop-first: punished
            return {"outcome": "stop", "outcome_r": -1.0,
                    "resolved_ts": b["ts"], "bars_held": walk.index(b) + 1}
        if hit_t:
            return {"outcome": "target", "outcome_r": float(target_rr or 0.0),
                    "resolved_ts": b["ts"], "bars_held": walk.index(b) + 1}
    if len(walk) >= max(1, int(horizon_bars)):
        # the horizon is EXHAUSTED without a hit: the honest end, marked to
        # the last close (a young walk is not an end -- the word stays open)
        last_close = walk[-1]["close"]
        moved = (last_close - entry) * direction
        return {"outcome": "expired", "outcome_r": round(moved / float(stop_d), 4),
                "resolved_ts": walk[-1]["ts"], "bars_held": len(walk)}
    return None  # the market has not finished speaking yet


def resolve_many(candidates: list[dict], bars_by_pair: dict[str, list[dict]],
                 *, horizon_bars: int = HORIZON_BARS) -> dict[int, dict]:
    """Resolve every open candidate against its pair's bars -> ``{id: outcome}``."""
    out: dict[int, dict] = {}
    for c in candidates or []:
        cid = c.get("id")
        bars = (bars_by_pair or {}).get(str(c.get("pair") or ""))
        if cid is None or not bars:
            continue
        got = resolve_open(c, bars, horizon_bars=horizon_bars)
        if got is not None:
            out[int(cid)] = got
    return out


# ---------------------------------------------------------------------------
# THE EVIDENCE -- confidence is live-proven or absent
# ---------------------------------------------------------------------------
def live_evidence(resolved_rows: list[dict], strategy_id: str) -> dict:
    """The strategy's LIVE record: wins/trials as the Wilson lower bound.

    ``resolved_rows`` are the ledger's resolved candidates (each with
    ``strategy_id`` and ``outcome``). A win is a ``target``; a stop is a
    loss; an ``expired`` row does not count either way (an unfinished
    argument is not evidence for or against). A strategy with no resolved
    record carries ``None`` -- the mouth says "unproven", never a fake 0.5.
    """
    wins = trials = 0
    for r in resolved_rows or []:
        if str(r.get("strategy_id") or "") != str(strategy_id):
            continue
        oc = r.get("outcome")
        if oc == "target":
            wins += 1
            trials += 1
        elif oc == "stop":
            trials += 1
    if trials <= 0:
        return {"n": 0, "wins": 0, "wilson_lb": None}
    return {"n": int(trials), "wins": int(wins),
            "wilson_lb": round(wilson_lb(wins, trials), 4)}


def agreement(candidates: list[dict]) -> dict[str, dict]:
    """The consensus block: per (pair, direction), how many voices and which.

    Returns ``{"EURUSD|1": {"pair": "EURUSD", "direction": 1, "voices": 3,
    "strategies": [sig, ...]}}`` -- the artifact's readers see at a glance
    whether a signal is a choir or a lone hunter (both honest, never merged).
    """
    out: dict[str, dict] = {}
    for c in candidates or []:
        pair = str(c.get("pair") or "")
        d = c.get("direction")
        if not pair or d not in (1, -1):
            continue
        key = f"{pair}|{int(d)}"
        blk = out.setdefault(key, {"pair": pair, "direction": int(d),
                                   "voices": 0, "strategies": []})
        blk["voices"] += 1
        sig = str(c.get("strategy_id") or "")
        if sig and sig not in blk["strategies"]:
            blk["strategies"].append(sig)
    return out
