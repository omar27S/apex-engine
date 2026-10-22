"""THE CAREER LEDGER -- R142: the civilization's memory of MERIT across nights.
R143 -- THE MONEY CURRENCY: the diploma now certifies EXPECTANCY, not applause.

The wound this module closes is the oldest one in the learning loop: a family's
evidence was born and buried inside a single night. Each dawn the tournament
measured every family from zero, so a strategy that did three honest trades a
night for twenty nights -- a REAL track record, the kind a human prop desk would
hire -- accumulated nothing. The civilization certified nobody, its theories
starved, its teacher flattened, its curriculum retired lessons at random. Zero
survivors was not a verdict on the families; it was the echo of a memory that
reset every dawn.

R143 closes the SECOND wound the Dragon named aloud in the letter of 2026-10-21:
"il libro dei soldi e' pieno; il libro del sapere e' vuoto" -- 72.73 R of realized
profit with ZERO certified survivors, because the bar certified the WRONG
CURRENCY. A Wilson lower bound of 0.45 on the WIN RATE ignores the payoff
geometry the law itself mandates (RR floor 1:2.5): a family that wins 40% of
its trades at RR 3.2 prints +0.60R per trade and could NEVER certify (it would
need ~55% observed over 100+ trades), while a 55%-winner at RR 0.9 bleeds to
death and sailed through. The money book and the wisdom book kept different
currencies, so they never agreed, so nothing ever deployed.

THE CAREER now certifies in the money currency:

* :func:`career_step` -- fold ONE night's leaderboard into the ledger. Idempotent
  per ``(family, date)``: a re-run night REPLACES its receipt (a receipt, never a
  double count -- the diary-echo lesson, applied to merit itself);
* :func:`expectancy_lb` -- the Bernoulli-R lower bound: the Wilson 95% lower
  bound on the win rate, paid at the CONSERVATIVE payoff ``min(realized average
  win RR, the law's 1:2.5 floor)``. A family is certified only when the 95%
  bound on its per-trade NET R clears :data:`CAREER_EXPECTANCY_BAR_R` -- the
  same 95% discipline, the currency the account actually pays in;
* :func:`certified_families` -- a family whose CAREER clears the expectancy bar
  with at least ``CAREER_MIN_TRADES`` lifetime trades AND a lifetime of positive
  net R (the money book must agree with the rate book) is certified EVEN ON A
  NIGHT IT DID NOT WIN. Evidence compounds; merit does not restart every dawn.

Honesty is binding:
  * A night with no ``wins`` in its rows pools nothing into the bound (never a
    fabricated win count -- a rate is not decompressed into wins);
  * ``net_r`` sums only what was measured; a family with wins but no readable
    lifetime net R cannot derive its payoff and stays UNCERTIFIED (fail-closed);
  * the conservative payoff takes the MINIMUM of the realized average win and
    the law's floor -- a family is never certified on a payoff richer than the
    one it actually realized, nor on one richer than the Constitution allows;
  * an empty ledger reports zero families, never an invented career.

Pure at import (Scar #6): the caller supplies the leaderboard rows and the date;
this module never reads the wall clock, never touches the disk.
"""

from __future__ import annotations

import math

__all__ = [
    "CAREER_VERSION",
    "CAREER_EXPECTANCY_BAR_R",
    "CAREER_MIN_TRADES",
    "CAREER_KEEP_DATES",
    "LAW_RR_FLOOR",
    "career_state",
    "career_step",
    "career_rows",
    "certified_families",
    "career_report",
    "pooled_wilson_lb",
    "expectancy_lb",
]

CAREER_VERSION: int = 2

# The Constitution's payoff floor (1:2.5 R:R), re-declared here so the career
# can read its own law aloud (import-light, like the Wilson arithmetic below).
# The suite pins the sync with ``genome.GENE_BOUNDS`` (Law 12: a copy that
# drifts is a copy that lies).
LAW_RR_FLOOR: float = 2.5

# The certification bar, in the money currency: the 95% Wilson-lower-bound on
# the per-trade NET expectancy (R units, costs already inside the receipts).
# 0.05R net per trade, provable at 95% with the law-floor payoff, is a REAL,
# deployable edge -- the diploma is no longer applause for winning often, it is
# the arithmetic of getting paid.
CAREER_EXPECTANCY_BAR_R: float = 0.05

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
    career["version"] = CAREER_VERSION
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
    """The pooled lifetime record per family, best career first (honest bound).

    R143: the rank key is the EXPECTANCY lower bound in R -- the money currency.
    The Wilson win-rate bound rides along as a diagnostic (``wilson_lb``), but
    the diploma is bought with expectancy, not with applause.
    """
    out: list[dict] = []
    for fam, entry in (career.get("families") or {}).items():
        pooled = _pooled(entry)
        lb = pooled_wilson_lb(pooled["wins"], pooled["trades"])
        wins = pooled["wins"]
        trades = pooled["trades"]
        net_r = pooled["net_r"]
        # the realized average win, in R, DERIVED from the money the family
        # actually banked: net = wins*W - losses*1 (each loss costs its risk).
        avg_win_rr = None
        if wins is not None and wins > 0 and net_r is not None:
            losses = max(0, trades - wins)
            avg_win_rr = round((float(net_r) + losses) / float(wins), 4)
        # the conservative payoff: never richer than realized, never richer
        # than the Constitution's floor allows.
        rr_floor = (round(min(avg_win_rr, LAW_RR_FLOOR), 4)
                    if avg_win_rr is not None else None)
        exp_lb = expectancy_lb(lb, rr_floor)
        out.append({
            "family": fam,
            "nights": pooled["nights"],
            "trades": trades,
            "wins": wins,
            "net_r": net_r,
            "wilson_lb": lb,
            "avg_win_rr": avg_win_rr,
            "rr_floor_used": rr_floor,
            "expectancy_lb_r": exp_lb,
            "certified": bool(
                trades >= CAREER_MIN_TRADES
                and net_r is not None and float(net_r) > 0.0
                and exp_lb is not None and exp_lb >= CAREER_EXPECTANCY_BAR_R),
        })
    out.sort(key=lambda r: (-(_rank_num(r["expectancy_lb_r"])),
                            -r["trades"], r["family"]))
    return out


def _rank_num(v) -> float:
    """None sorts last (unknown is not worst, but it is not first either)."""
    return float(v) if isinstance(v, (int, float)) else float("-inf")


def expectancy_lb(wilson_lb: float | None, rr_floor: float | None) -> float | None:
    """The Bernoulli-R lower bound on the per-trade NET expectancy.

    ``E_LB = p_LB * (1 + RR_floor) - 1`` -- the 95%-sure win rate paid at the
    conservative payoff. ``None`` when either input is unreadable (fail-closed:
    no fabricated bound, ever).
    """
    if wilson_lb is None or rr_floor is None:
        return None
    return round(wilson_lb * (1.0 + float(rr_floor)) - 1.0, 4)


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
        "bar_r": CAREER_EXPECTANCY_BAR_R,
        "min_trades": CAREER_MIN_TRADES,
        "reading": (f"carriere: {len(rows)} famiglia/e, {len(certified)} "
                    f"certificata/e per aspettativa netta (>= {CAREER_EXPECTANCY_BAR_R}R "
                    f"al 95%, payoff al pavimento di legge)"
                    if rows else "carriere: nessuna famiglia ancora registrata"),
    }
