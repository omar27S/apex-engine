"""THE CAREER LEDGER -- R142: the civilization's memory of MERIT across nights.

The wound this module closes is the oldest one in the learning loop: a family's
evidence was born and buried inside a single night. Each dawn the tournament
measured every family from zero, so a strategy that did three honest trades a
night for twenty nights -- a REAL track record, the kind a human prop desk would
hire -- accumulated nothing. The certification bar (a Wilson lower bound at 0.45)
is nearly unreachable inside ONE night of M15 candidates, and so the civilization
certified nobody, its theories starved, its teacher flattened, its curriculum
retired lessons at random. Zero survivors was not a verdict on the families; it
was the echo of a memory that reset every dawn.

THE CAREER closes it:

* :func:`career_step` -- fold ONE night's leaderboard into the ledger. Idempotent
  per ``(family, date)``: a re-run night REPLACES its receipt (a receipt, never a
  double count -- the diary-echo lesson, applied to merit itself);
* :func:`career_rows` / :func:`career_report` -- the pooled LIFETIME record per
  family: nights, trades, wins, net R, and the pooled Wilson lower bound over the
  SAME arithmetic the night certifies with (one law, two altitudes);
* :func:`certified_families` -- a family whose CAREER clears the same 0.45 bar
  with at least ``CAREER_MIN_TRADES`` lifetime trades is certified EVEN ON A NIGHT
  IT DID NOT WIN. Evidence compounds; merit does not restart every dawn.

Honesty is binding:
  * A night with no ``wins`` in its rows pools nothing into the bound (never a
    fabricated win count -- a rate is not decompressed into wins);
  * ``net_r`` sums only what was measured;
  * an empty ledger reports zero families, never an invented career.

Pure at import (Scar #6): the caller supplies the leaderboard rows and the date;
this module never reads the wall clock, never touches the disk.
"""

from __future__ import annotations

import math

__all__ = [
    "CAREER_VERSION",
    "CAREER_CERT_BAR",
    "CAREER_MIN_TRADES",
    "CAREER_KEEP_DATES",
    "career_state",
    "career_step",
    "career_rows",
    "certified_families",
    "career_report",
    "pooled_wilson_lb",
]

CAREER_VERSION: int = 1

# The certification bar: the SAME Wilson-lower-bound bar the night certifies with
# (one law at two altitudes -- the night is the exam, the career is the diploma).
CAREER_CERT_BAR: float = 0.45

# A career needs a TRACK RECORD, not a hot night: thirty lifetime trades minimum.
CAREER_MIN_TRADES: int = 30

# Per-family night receipts kept (the career's raw memory; the pools are derived
# from these receipts, so a corrected night corrects the career).
CAREER_KEEP_DATES: int = 40


def career_state(state: dict) -> dict:
    """The career ledger living inside the civilization's state (get-or-create)."""
    career = state.get("family_careers")
    if not isinstance(career, dict):
        career = {}
    career.setdefault("version", CAREER_VERSION)
    career.setdefault("families", {})
    state["family_careers"] = career
    return career


def _receipt(row: dict) -> dict:
    """One family's receipt from ONE leaderboard row (measured fields only)."""
    def _int(v) -> int | None:
        if isinstance(v, bool) or v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        return None

    trades = _int(row.get("adv_trades", row.get("trades")))
    wins = _int(row.get("wins"))
    net = row.get("adv_net_r", row.get("net_r"))
    lb = row.get("adv_lb", row.get("wilson_lb"))
    return {
        "trades": trades if trades is not None and trades >= 0 else 0,
        # never fabricated: wins absent from the row stay absent (None)
        "wins": wins if wins is not None and wins >= 0 else None,
        "net_r": (round(float(net), 4)
                  if isinstance(net, (int, float)) and not isinstance(net, bool)
                  else None),
        "night_lb": (round(float(lb), 4)
                     if isinstance(lb, (int, float)) and not isinstance(lb, bool)
                     else None),
    }


def career_step(career: dict, leaderboard: list, *, date: str, ts: str = "") -> dict:
    """Fold ONE night's leaderboard into the ledger (idempotent per family+date).

    Every leaderboard row is a family's receipt for the night: re-running the same
    night's report REPLACES the receipt (a corrected night corrects the career);
    a different night adds a new one. Rows without a family are ignored; a row
    without trades still records the family SHOWED UP (an honest zero-trade night).
    """
    fams = career.setdefault("families", {})
    day = str(date)
    for row in leaderboard or []:
        if not isinstance(row, dict):
            continue
        fam = str(row.get("family") or "").strip()
        if not fam:
            continue
        entry = fams.setdefault(fam, {"dates": {}})
        entry["dates"][day] = _receipt(row)
        # the career's raw memory stays bounded: the last CAREER_KEEP_DATES receipts
        for old in sorted(entry["dates"])[:-CAREER_KEEP_DATES]:
            del entry["dates"][old]
    career["version"] = career.get("version") or CAREER_VERSION
    career["ts"] = str(ts)
    return career


def _pooled(fam: dict) -> dict:
    """The family's pooled lifetime record, DERIVED from its receipts."""
    dates = fam.get("dates") or {}
    trades = sum(int(r.get("trades") or 0) for r in dates.values())
    win_rows = [r for r in dates.values() if r.get("wins") is not None]
    wins = sum(int(r["wins"]) for r in win_rows) if win_rows else None
    nets = [r.get("net_r") for r in dates.values() if r.get("net_r") is not None]
    return {"nights": len(dates), "trades": trades, "wins": wins,
            "net_r": round(sum(nets), 4) if nets else None}


def pooled_wilson_lb(wins: int | None, trades: int) -> float | None:
    """The Wilson 95% lower bound over the POOLED counts (None without wins).

    Re-derived here (not imported) so the career stays import-light and the
    arithmetic it certifies with is the one it can read aloud -- the same 95%
    two-sided arithmetic the night's ``adv_lb`` and the factory crown use.
    """
    if wins is None or trades <= 0:
        return None
    n = float(trades)
    p = float(wins) / n
    z = 1.96
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return round(max(0.0, (centre - margin) / denom), 4)


def career_rows(career: dict) -> list[dict]:
    """The pooled lifetime record per family, best career first (honest bound)."""
    out: list[dict] = []
    for fam, entry in (career.get("families") or {}).items():
        pooled = _pooled(entry)
        lb = pooled_wilson_lb(pooled["wins"], pooled["trades"])
        out.append({
            "family": fam,
            "nights": pooled["nights"],
            "trades": pooled["trades"],
            "wins": pooled["wins"],
            "net_r": pooled["net_r"],
            "wilson_lb": lb,
            "certified": bool(lb is not None
                              and lb >= CAREER_CERT_BAR
                              and pooled["trades"] >= CAREER_MIN_TRADES),
        })
    out.sort(key=lambda r: (-(r["wilson_lb"] if r["wilson_lb"] is not None else -1.0),
                            -r["trades"], r["family"]))
    return out


def certified_families(career: dict) -> list[str]:
    """The families whose LIFETIME evidence clears the bar (sorted, honest)."""
    return sorted(r["family"] for r in career_rows(career) if r["certified"])


def career_report(career: dict) -> dict:
    """The standing career reading for the One Brain block and the Letter."""
    rows = career_rows(career)
    certified = [r for r in rows if r["certified"]]
    best = rows[:3]
    return {
        "version": CAREER_VERSION,
        "families": len(rows),
        "nights_total": sum(r["nights"] for r in rows),
        "certified": [r["family"] for r in certified],
        "best": best,
        "bar": CAREER_CERT_BAR,
        "min_trades": CAREER_MIN_TRADES,
        "reading": (f"carriere: {len(rows)} famiglia/e, {len(certified)} "
                    f"certificata/e su prove di vita intera"
                    if rows else "carriere: nessuna famiglia ancora registrata"),
    }
