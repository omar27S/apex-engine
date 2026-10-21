"""D3 -- THE DD LEDGER: the account's memory of pain.

The measured-DD report's original wound was amnesia. Each night's realized DD
was measured from a fresh equity curve (equity restarts at zero every night),
so a single good night after a bad week could restore "fully deployable" --
the one lie the charter's 8% LIVE LAW can never afford. The tournament's DD
block answered only "how deep was TONIGHT's dip", while the account's DD is
accumulated across every night the elite set has realized.

This module gives the DD a MEMORY, the same cure E1 received (Cure 4):

* each night's REALIZED contribution (the finalists' pooled net-R) is folded
  into a durable, committed ledger -- one entry per night, idempotent on
  ``(date, seed)`` so a re-run replaces its own entry and never double-counts;
* the ACCUMULATED DD is the peak-to-trough drawdown of the cumulative curve
  ACROSS nights -- the account-shaped number the deployable fraction rides on;
* the stored per-entry snapshots (equity/peak/dd after each night) are
  re-derived on every fold, so the durable file is always internally
  consistent, never a stack of stale audit numbers.

HONESTY RULES (never a flattering zero):

* research-grade numbers NEVER touch the account curve: a night with no
  surviving finalist records a flat 0.0 labelled ``no_finalist`` -- its
  candidate DD is reported, never banked;
* an unmeasured night is labelled ``unmeasured`` (it moved nothing, because
  nothing was realized), never fabricated as a gain;
* a MEASURED zero accumulated DD (a monotonic realized curve) is not a
  missing number -- it is a curve with no drawdown, reported as such.

DD is DATA, not a cage: nothing here constrains a search. The ledger measures
and reports; the CEO scales the deployed fraction. Pure at import (Scar #6):
the caller owns the file I/O (:func:`load_ledger` / :func:`append_night`).
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "LEDGER_VERSION",
    "load_ledger",
    "with_night",
    "append_night",
    "accumulated_dd",
    "latest_prior_dd",
    "nights_realized",
]

LEDGER_VERSION: int = 1


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def load_ledger(path: str | Path) -> list[dict]:
    """Read the committed DD ledger (a JSON list); corrupt or absent -> empty."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("nights") or []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def _walk(entries: list[dict]) -> list[dict]:
    """Re-derive the cumulative curve's snapshots over the WHOLE ledger.

    One point per night: the night's net-R is the equity step. Every entry
    carries ``equity_after`` / ``peak_after`` / ``dd_after`` so a future audit
    can re-read the account's walk from the durable file alone. A mid-history
    replacement re-derives everything after it -- the snapshots can never go
    stale.
    """
    equity = 0.0
    peak = 0.0
    dd = 0.0
    out: list[dict] = []
    for e in entries:
        equity += float(_num(e.get("net_r")) or 0.0)
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
        row = dict(e)
        row["equity_after"] = round(equity, 4)
        row["peak_after"] = round(peak, 4)
        row["dd_after"] = round(dd, 4)
        out.append(row)
    return out


def with_night(history: list[dict], *, date: str, seed: int, net_r: float,
               basis: str, dd_tonight: float | None,
               dd_basis: str = "", cap: int = 400) -> list[dict]:
    """Fold tonight's entry into the ledger WITHOUT writing anything (pure).

    Idempotent on ``(date, seed)``: a re-run of the same night REPLACES its own
    entry instead of duplicating it (the groundhog cure's discipline applied to
    the account's memory). The last ``cap`` nights are kept so the durable file
    never grows without bound.
    """
    entry = {
        "version": LEDGER_VERSION,
        "date": str(date),
        "seed": int(seed) if _num(seed) is not None else 0,
        "basis": str(basis),
        "net_r": round(float(_num(net_r) or 0.0), 4),
        "dd_tonight": (round(float(dd_tonight), 4)
                       if _num(dd_tonight) is not None else None),
        "dd_basis": str(dd_basis or basis),
    }
    entries = list(history or [])
    # Replace IN PLACE: a re-run of the same night must keep its position in
    # the curve -- appending it at the end would scramble the chronology and
    # walk the account's equity through the wrong order of nights.
    replaced = False
    for i, e in enumerate(entries):
        if str(e.get("date")) == entry["date"] and e.get("seed") == entry["seed"]:
            entries[i] = entry
            replaced = True
            break
    if not replaced:
        entries.append(entry)
    return _walk(entries[-cap:])


def append_night(path: str | Path, *, date: str, seed: int, net_r: float,
                 basis: str, dd_tonight: float | None,
                 dd_basis: str = "", cap: int = 400) -> list[dict]:
    """Fold tonight's entry AND commit it to the durable ledger (the I/O half).

    The caller owns the DECISION to grow the memory (a test suite is not a
    night); this function only performs the honest fold-and-write.
    """
    history = with_night(load_ledger(path), date=date, seed=seed, net_r=net_r,
                         basis=basis, dd_tonight=dd_tonight,
                         dd_basis=dd_basis, cap=cap)
    # R136: the pain ledger lands through THE ATOMIC PEN -- whole-or-old,
    # never torn (the guardian reads this file through load_ledger; a torn
    # pain is "a language no organ shares", R132's named wound).
    from app.state import atomic  # noqa: E402 -- local, like every pen import
    atomic.write_json(path, history)
    return history


def accumulated_dd(history: list[dict]) -> float | None:
    """The account-shaped DD: peak-to-trough of the curve ACROSS nights.

    ``None`` only when the ledger is empty (no night ever realized); a flat
    curve of unmeasured/no-finalist nights is an honest ``0.0`` -- measured
    nothing, banked nothing, never a flattering guess.
    """
    entries = [e for e in (history or []) if isinstance(e, dict)]
    if not entries:
        return None
    return _walk(entries)[-1]["dd_after"]


def latest_prior_dd(history: list[dict]) -> float | None:
    """The accumulated DD as of the LAST stored night -- tonight's PRIOR.

    The trend the charter reports compares the account DD after tonight
    against this number, so ``dd_trend`` finally measures the memory, not the
    eternal "unknown" of a report that forgot every night before it.
    """
    entries = [e for e in (history or []) if isinstance(e, dict)]
    if not entries:
        return None
    prior = _walk(entries)[-1]["dd_after"]
    return prior if prior > 0.0 else None


def nights_realized(history: list[dict]) -> int:
    """How many stored nights actually REALIZED on the account curve.

    Only ``finalists`` nights moved the curve; ``no_finalist`` and
    ``unmeasured`` nights are flat by construction (research-grade numbers are
    never banked). This count is the memory's honest depth.
    """
    return sum(1 for e in (history or [])
               if isinstance(e, dict) and e.get("basis") == "finalists")
