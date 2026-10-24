"""R155 — THE LIVE CROWN's counter (the mouth's ledger, read as an account).

The Dragon's demand of 2026-10-23 (R147) made the split law: the account's
crown carries ``realized_from_dispatch_r`` BESIDE the finalists' paper R,
"honestly None until the first real order exists". The live mouth (R113) has
been dispatching paper orders on the live tape since 2026-10-20 22:38 -- every
candidate born is an order placed, every ``candidate_resolved`` row is that
order judged by the real market (stop / target / expired, in R-multiples).
6229 dispatches were judged before this module existed; the crown still said
``dispatched_trades: 0`` because nothing READ the ledger.

This module is that reading. ONE pass over the ledger rows produces the
house's LIVE account: how many orders were dispatched, how many judged, the
net-R the tape paid, the drawdown the live curve ate (peak-to-trough of the
cumulative R stream, in file order -- the ledger is append-only), and the
per-family truth the Dragon asked for ("guarda quanti dei 778 sopravvivono").

Honesty (the Director's laws, binding on the account as on everything):

* MEASURE BEFORE SPEECH (Law 1) -- every number here is counted from real
  ledger rows; nothing is extrapolated from the research account;
* THE DEAD MUST BE PROVEN (Law 2) -- an absent ledger is ``basis: absent``
  with honest zeros, never a fabricated live number; malformed rows are
  skipped AND counted (``skipped_rows``), never guessed from;
* THE RECEIPT IS EVIDENCE (Law 5) -- ``first_dispatch_ts`` / ``last_ts``
  name the span the account speaks of, so a stale ledger can never pose as
  a live one.

Pure at import (Scar #6): the counting is pure; only
:func:`live_dispatch_evidence_from_path` touches the disk (fail-open to the
honest ``absent`` basis -- a missing ledger is the mouth's silence, named).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

__all__ = [
    "ABSENT_BASIS",
    "LIVE_BASIS",
    "live_dispatch_evidence",
    "live_dispatch_evidence_from_path",
]

# What the basis string says when the ledger cannot speak.
ABSENT_BASIS = "absent (no mouth ledger yet -- the mouth never spoke)"
LIVE_BASIS = "mouth ledger (paper orders judged on the live tape)"


def _absent() -> dict:
    """The honest zero account: everything unmeasured, nothing fabricated."""
    return {"basis": ABSENT_BASIS,
            "dispatched": 0,
            "resolved": 0,
            "open_now": 0,
            "wins": 0,
            "live_net_r": None,
            "live_dd_r": None,
            "outcomes": {},
            "by_family": {},
            "first_dispatch_ts": None,
            "last_ts": None,
            "skipped_rows": 0}


def live_dispatch_evidence(rows: Iterable[dict | str | bytes]) -> dict:
    """One pass over the mouth's ledger rows -> the house's LIVE account.

    Rows are dicts (already parsed) or raw lines (parsed here; the malformed
    ones are skipped and counted). The counts:

    * ``dispatched``  -- candidates BORN across all mouth turns (each birth
      is a paper order placed on the tape); with no mouth_turn rows at all,
      the resolved count is the honest floor;
    * ``resolved`` / ``wins`` / ``live_net_r`` -- the judged orders and the
      net-R the tape paid (sum of ``outcome_r``; a resolution without a
      numeric R is counted as judged but never sums a fabricated zero);
    * ``live_dd_r``  -- the peak-to-trough of the cumulative R curve, in
      file order (the ledger is append-only, so file order IS time order);
      ``None`` when nothing was ever judged, ``0.0`` when the live curve
      never dipped (a MEASURED zero, not a missing number);
    * ``by_family``  -- the Dragon's question answered at bloodline grain;
    * ``outcomes``   -- the tape's verdicts by name (stop / target / expired).
    """
    out = _absent()
    out["basis"] = LIVE_BASIS
    born_from_turns = 0
    equity = 0.0
    peak = 0.0
    dd = 0.0
    families: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            try:
                row = json.loads(row)
            except (ValueError, TypeError):
                if row not in (None, ""):
                    out["skipped_rows"] += 1
                continue
            if not isinstance(row, dict):
                out["skipped_rows"] += 1
                continue
        kind = row.get("kind")
        ts = row.get("ts")
        if ts:
            if out["last_ts"] is None or str(ts) > str(out["last_ts"]):
                out["last_ts"] = ts
        if kind == "mouth_turn":
            new = row.get("candidates_new")
            if isinstance(new, int) and new > 0:
                born_from_turns += new
                if out["first_dispatch_ts"] is None:
                    out["first_dispatch_ts"] = ts
            open_now = row.get("open_now")
            if isinstance(open_now, int) and open_now >= 0:
                out["open_now"] = open_now
        elif kind == "candidate_resolved":
            out["resolved"] += 1
            outcome = row.get("outcome")
            if outcome is not None:
                out["outcomes"][str(outcome)] = out["outcomes"].get(str(outcome), 0) + 1
            born = row.get("born_ts")
            if born and (out["first_dispatch_ts"] is None
                         or str(born) < str(out["first_dispatch_ts"])):
                out["first_dispatch_ts"] = born
            r = row.get("outcome_r")
            if isinstance(r, (int, float)):
                r = float(r)
                out["live_net_r"] = (out["live_net_r"] or 0.0) + r
                if r > 0:
                    out["wins"] += 1
                equity += r
                peak = max(peak, equity)
                dd = max(dd, peak - equity)
            fam = row.get("family") or "?"
            fd = families.setdefault(fam, {"resolved": 0, "net_r": 0.0, "wins": 0})
            fd["resolved"] += 1
            if isinstance(r, float):
                fd["net_r"] += r
                if r > 0:
                    fd["wins"] += 1
    if out["resolved"] > 0:
        out["live_dd_r"] = round(dd, 4)
        out["live_net_r"] = round(out["live_net_r"], 4)
        out["by_family"] = {
            fam: {"resolved": fd["resolved"],
                  "net_r": round(fd["net_r"], 4),
                  "wins": fd["wins"]}
            for fam, fd in sorted(families.items(),
                                  key=lambda kv: -kv[1]["net_r"])}
    out["dispatched"] = born_from_turns if born_from_turns > 0 else out["resolved"]
    return out


def live_dispatch_evidence_from_path(path: str | Path) -> dict:
    """The ledger on disk -> the live account (absent file -> honest zeros).

    Fail-open BY DESIGN and NAMED: a missing or unreadable ledger is the
    mouth's silence (``basis: absent``), never a zero that could pose as a
    measured account. A torn tail (a half-written last line) loses that one
    row to ``skipped_rows`` and keeps the rest of the account standing.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _absent()
    rows = [line for line in text.splitlines() if line.strip()]
    if not rows:
        return _absent()
    return live_dispatch_evidence(rows)
