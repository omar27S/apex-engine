"""THE FORWARD-TEST CHAMBER -- JUMP 3: CONTINUOUS FORWARD-TEST (the present is the judge).

Strategies were tested on 2019-2026 history, but today's market is different. A system
living in the past does not see the present. This chamber makes the PRESENT the judge:

  * THE FORWARD-TEST CHAMBER -- every surviving strategy (net-positive in any
    tournament) is automatically enrolled. Every hour the falcon's real data (the last
    60 minutes) is compared against what each enrolled strategy WOULD HAVE DONE: the
    entry it would have taken and the ACTUAL outcome (+0.3R / -0.2R / no-trigger). This
    is NOT a backtest -- it is testing against the REAL PRESENT as it happens;
  * THE DUAL SCORE -- every strategy carries TWO scores: the BACKTEST SCORE (the
    tournaments) and the LIVE SCORE (the chamber). The ranking weighs the LIVE score
    MORE (60/40): the system prefers strategies that work NOW. A strategy with a great
    backtest but a terrible live score is flagged "STALE" and drops until the live
    score recovers;
  * THE LIVE-SCORE RENDERING -- the Letter's "IL PRESENTE GIUDICA" section: the top
    live scores, the biggest stale strategies, and the divergence history/present.

Honesty is binding: a window with no known outcome is "no-trigger" (``None``), never a
fabricated 0R; a strategy with no live sample has a live score of ``None`` (unmeasured),
never a flattering default. Pure at import (Scar #6): the observations come from the
caller; the chamber never reads the wall clock.
"""

from __future__ import annotations

__all__ = [
    "FORWARD_TEST_VERSION",
    "LIVE_WEIGHT",
    "BACKTEST_WEIGHT",
    "STALE_BACKTEST_FLOOR",
    "STALE_LIVE_FLOOR",
    "FORWARD_WINDOW_MINUTES",
    "FAMILY_DIRECTION",
    "enroll",
    "is_enrolled",
    "record_window",
    "live_score",
    "dual_score",
    "stale_flag",
    "rank_strategies",
    "forward_test_block",
    "tape_window",
    "replay_strategy",
    "record_live_window",
    "RESUME_HORIZONS",
    "live_resume",
    "live_gap",
    "evidence_ledger",
]

FORWARD_TEST_VERSION: int = 2

# The ranking formula: THE GREAT INVERSION -- the LIVE score weighs 90%, the backtest
# only 10%. The PRESENT is the ONLY judge: a magnificent backtest with a negative live
# score is DEGRADED to STALE; a mediocre backtest with strong live performance is
# PROMOTED (it has a LIVE EDGE the backtest cannot see).
LIVE_WEIGHT: float = 0.9
BACKTEST_WEIGHT: float = 0.1

# STALE: a great backtest (>= floor) with a terrible live score (<= floor) -- the
# market has moved past the strategy. BOTH must be MEASURED for the flag to fire.
STALE_BACKTEST_FLOOR: float = 0.5
STALE_LIVE_FLOOR: float = 0.0

# The forward-test window: the falcon's last 60 minutes.
FORWARD_WINDOW_MINUTES: int = 60


def _chamber(state: dict) -> dict:
    st = state if state is not None else {}
    return st.setdefault("forward_test", {"enrolled": [], "windows": {}})


def enroll(state: dict, strategy: str, *, source: str = "tournament") -> dict:
    """Enroll a surviving strategy in the Forward-Test program (deduplicated).

    Returns the enrollment row. Honest: an empty strategy id enrolls nothing.
    """
    sid = str(strategy or "").strip()
    if not sid:
        return {"enrolled": False, "strategy": "", "reading": "arruolamento vuoto"}
    ch = _chamber(state)
    if sid not in ch["enrolled"]:
        ch["enrolled"].append(sid)
    return {"enrolled": True, "strategy": sid, "source": source,
            "n_enrolled": len(ch["enrolled"]),
            "reading": f"{sid}: arruolata nel forward-test ({len(ch['enrolled'])} in prova)"}


def is_enrolled(state: dict, strategy: str) -> bool:
    return str(strategy) in (((state or {}).get("forward_test") or {}).get("enrolled") or [])


def record_window(state: dict, strategy: str, *,
                  entry_ts: str = "", outcome_r: float | None = None,
                  pair: str = "", ts: str = "") -> dict:
    """Log ONE forward-test window for a strategy: the entry it would have taken and
    the ACTUAL outcome (``None`` = no-trigger, never a fabricated 0R).

    The window is appended to the chamber's per-strategy log. Honest: an empty
    strategy logs nothing.
    """
    sid = str(strategy or "").strip()
    if not sid:
        return {}
    ch = _chamber(state)
    if sid not in ch["enrolled"]:
        ch["enrolled"].append(sid)
    row = {"ts": str(ts), "entry_ts": str(entry_ts), "pair": str(pair),
           "outcome_r": (float(outcome_r) if isinstance(outcome_r, (int, float))
                         else None)}
    ch["windows"].setdefault(sid, []).append(row)
    del ch["windows"][sid][:-200]
    return row


def live_score(state: dict, strategy: str) -> dict:
    """The strategy's LIVE score: the mean of its KNOWN forward-test outcomes.

    Honest: no known outcome -> ``None`` (the present has not judged yet); a
    no-trigger window is counted but never scored as 0R.
    """
    rows = (((state or {}).get("forward_test") or {}).get("windows") or {}).get(
        str(strategy)) or []
    known = [r["outcome_r"] for r in rows
             if isinstance(r.get("outcome_r"), (int, float))]
    n = len(known)
    if not n:
        return {"score": None, "n": 0, "windows": len(rows), "measured": False,
                "reading": f"{strategy}: il presente non ha ancora giudicato"}
    return {"score": round(sum(known) / n, 4), "n": n, "windows": len(rows),
            "measured": True,
            "reading": (f"{strategy}: punteggio dal vivo {sum(known) / n:+.3f}R "
                        f"su {n} finestre")}


def dual_score(*, backtest: float | None, live: float | None) -> dict:
    """The DUAL SCORE: the backtest blended with the live score (LIVE weighs MORE).

    ``dual = 0.4 * backtest + 0.6 * live``. Honest: an unmeasured live score leaves the
    dual as the BACKTEST alone, flagged ``measured=False`` -- the present has not yet
    voted, so the past stands (but the Letter says the live axis is missing).
    """
    if live is None:
        return {"dual": backtest, "backtest": backtest, "live": None,
                "measured": False,
                "reading": "punteggio doppio: solo storico (il presente non misurato)"}
    if backtest is None:
        return {"dual": live, "backtest": None, "live": live, "measured": True,
                "reading": "punteggio doppio: solo presente (storico non misurato)"}
    dual = BACKTEST_WEIGHT * float(backtest) + LIVE_WEIGHT * float(live)
    return {"dual": round(dual, 4), "backtest": backtest, "live": live,
            "measured": True,
            "reading": (f"punteggio doppio: {dual:.3f} "
                        f"(storico {backtest:.3f} x {BACKTEST_WEIGHT:.0%} + "
                        f"presente {live:.3f} x {LIVE_WEIGHT:.0%})")}


def stale_flag(*, backtest: float | None, live: float | None,
               backtest_floor: float = STALE_BACKTEST_FLOOR,
               live_floor: float = STALE_LIVE_FLOOR) -> dict:
    """Flag a strategy STALE: great history, terrible present (the market moved past it).

    Honest: BOTH scores must be measured -- an unmeasured live score never flags stale.
    """
    if not isinstance(backtest, (int, float)) or not isinstance(live, (int, float)):
        return {"stale": False, "measured": False,
                "reading": "stale non valutabile (un asse non misurato)"}
    is_stale = float(backtest) >= backtest_floor and float(live) <= live_floor
    return {"stale": is_stale, "measured": True, "backtest": backtest, "live": live,
            "reading": ("STALE: lo storico e' forte ma il presente e' debole "
                        "-- il mercato e' andato oltre"
                        if is_stale else "non stale (storico e presente coerenti)")}


def rank_strategies(state: dict, backtest_scores: dict) -> list[dict]:
    """Rank the strategies by the DUAL score (live weighs more), flagging the stale.

    ``backtest_scores`` maps strategy -> historical fitness. Only ENROLLED strategies
    with a known live score participate; each row carries the dual score, the two
    parts and the stale flag. Sorted by dual descending, then by id (stable).
    """
    out: list[dict] = []
    for sid in (((state or {}).get("forward_test") or {}).get("enrolled") or []):
        bt = backtest_scores.get(sid)
        ls = live_score(state, sid)
        dual = dual_score(backtest=bt, live=ls["score"])
        fl = stale_flag(backtest=bt, live=ls["score"])
        out.append({"strategy": sid, "dual": dual["dual"], "backtest": bt,
                    "live": ls["score"], "live_n": ls["n"], "stale": fl["stale"],
                    "stale_measured": fl["measured"]})
    out.sort(key=lambda r: (-(r["dual"] if isinstance(r["dual"], (int, float))
                              else float("-inf")), r["strategy"]))
    return out


def forward_test_block(state: dict, backtest_scores: dict | None = None) -> dict:
    """The chamber's block for the artifact + the Letter ("IL PRESENTE GIUDICA").

    Ranks the enrolled strategies, names the top live scores, the biggest stale
    strategies, and the divergence between history and the present. Honest: no
    enrollment -> an empty block that says so.
    """
    st = state if state is not None else {}
    bt = dict(backtest_scores or {})
    rows = rank_strategies(st, bt)
    ranked = [r for r in rows if isinstance(r["dual"], (int, float))]
    stale = [r for r in rows if r["stale"]]
    diverging = [r for r in rows if isinstance(r["live"], (int, float))
                 and isinstance(r["backtest"], (int, float))
                 and (r["live"] - r["backtest"]) <= -STALE_BACKTEST_FLOOR]
    block = {
        "enrolled": len(((st.get("forward_test") or {}).get("enrolled") or [])),
        "judged": len(ranked),
        "top": ranked[:5],
        "stale": [{"strategy": r["strategy"], "backtest": r["backtest"],
                   "live": r["live"]} for r in stale],
        "divergence": [{"strategy": r["strategy"],
                        "gap": round(r["live"] - r["backtest"], 4)}
                       for r in diverging],
        "measured": bool(ranked),
    }
    block["reading"] = (
        f"il presente giudica: {len(ranked)} strategie valutate, {len(stale)} stale"
        + (f"; migliore {ranked[0]['strategy']} ({ranked[0]['dual']:+.3f})"
           if ranked else " (nessuna prova ancora)")
    )
    st["forward_test_summary"] = block
    return block


# --- DEBT-059: A TRUE 60-MINUTE LIVE TAPE REPLAY ---------------------------

# The honest family -> direction map for the coarse live replay. A trend/momentum/
# breakout/structure family leans WITH the session delta; a mean-reversion family
# leans AGAINST it; a volatility/pattern family is directional only on a strong
# delta (else it stays flat -- no fabricated trigger).
FAMILY_DIRECTION: dict[str, str] = {
    "trend": "with", "momentum": "with", "breakout": "with", "structure": "with",
    "meanrev": "against", "relative": "against",
    "volatility": "strong_with", "pattern": "strong_with", "volume": "strong_with",
    "ensemble": "with",
}


def _parse_ts(value) -> "datetime | None":
    """Parse a tape timestamp (epoch float or ISO string) to UTC, or ``None``."""
    from datetime import datetime, timezone
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    v = str(value or "").strip().replace("Z", "+00:00")
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tape_window(ticks: list[dict], *, now_ts: str = "",
                minutes: int = FORWARD_WINDOW_MINUTES) -> dict:
    """The TRUE forward-test window: the falcon's last ``minutes`` of REAL ticks.

    Returns the window's ticks (sorted by time), the first/last price, the session
    DELTA (last - first, in pips if the ticks carry a price), and the tick count.
    Honest: an unparseable timestamp, or fewer than two priced ticks, yields
    ``measured=False`` (never a fabricated move). Pure: the caller supplies
    ``now_ts``; the window never reads the wall clock.
    """
    if not ticks:
        return {"ticks": [], "measured": False, "n": 0, "delta": None,
                "reading": "nessuna tape da riprodurre"}
    end = _parse_ts(now_ts)
    rows: list[tuple] = []
    for t in ticks:
        dt = _parse_ts(t.get("ts"))
        price = t.get("price")
        if dt is None or not isinstance(price, (int, float)):
            continue
        rows.append((dt, float(price), t.get("pair")))
    if end is not None:
        cutoff = end.timestamp() - int(minutes) * 60
        rows = [r for r in rows if r[0].timestamp() >= cutoff]
    rows.sort(key=lambda r: r[0])
    if len(rows) < 2:
        return {"ticks": [{"ts": r[0].isoformat(), "price": r[1]} for r in rows],
                "measured": False, "n": len(rows), "delta": None,
                "reading": (f"tape insufficiente ({len(rows)} tick) nella finestra "
                            f"di {minutes} min")}
    first, last = rows[0][1], rows[-1][1]
    return {
        "ticks": [{"ts": r[0].isoformat(), "price": r[1], "pair": r[2]} for r in rows],
        "measured": True, "n": len(rows), "first": first, "last": last,
        "delta": round(last - first, 6),
        "window_minutes": int(minutes),
        "reading": (f"tape viva: {len(rows)} tick in {minutes} min, "
                    f"delta {last - first:+.5f}"),
    }


def replay_strategy(tape: dict, family_group: str, *,
                    strong_delta: float | None = None) -> dict:
    """What would this strategy have DONE on the live tape window?

    The coarse, honest replay: the direction clause of the family group (WITH /
    AGAINST / strong-only) is compared to the window's realized move, and the
    outcome is the SIGNED move in the strategy's favour. Honest: an unmeasured
    window (no tape / no move) is a NO-TRIGGER (``outcome_r=None``), never a
    fabricated 0R; a family group with no direction rule never triggers.
    """
    if not tape.get("measured"):
        return {"triggered": False, "direction": None, "outcome_r": None,
                "measured": False, "reading": "nessun segnale (tape non misurata)"}
    delta = tape.get("delta")
    if not isinstance(delta, (int, float)) or delta == 0.0:
        return {"triggered": False, "direction": None, "outcome_r": None,
                "measured": True, "reading": "nessun trigger (il prezzo non si e' mosso)"}
    rule = FAMILY_DIRECTION.get(str(family_group), "")
    if not rule:
        return {"triggered": False, "direction": None, "outcome_r": None,
                "measured": True,
                "reading": f"nessuna regola di direzione per {family_group}"}
    d = 1.0 if delta > 0 else -1.0
    if rule == "against":
        d = -d
    elif rule == "strong_with":
        if strong_delta is None or abs(delta) < float(strong_delta):
            return {"triggered": False, "direction": None, "outcome_r": None,
                    "measured": True,
                    "reading": "nessun trigger (mossa troppo debole per una strategia "
                               "di forza)"}
    outcome = round(abs(delta), 6) if d > 0 else round(-abs(delta), 6)
    return {"triggered": True, "direction": "long" if d > 0 else "short",
            "outcome_r": outcome, "measured": True,
            "reading": (f"trigger {'long' if d > 0 else 'short'} sul tape vivo: "
                        f"{outcome:+.5f}")}


def record_live_window(state: dict, *, strategy: str, family: str, ticks: list[dict],
                       now_ts: str = "", minutes: int = FORWARD_WINDOW_MINUTES,
                       pair: str = "", strong_delta: float | None = None) -> dict:
    """Replay the live tape window for one enrolled strategy and LOG it (DEBT-059).

    This is the true forward window the chamber always promised: the falcon's last
    ``minutes`` of REAL ticks, replayed against the strategy's family group. Honest:
    an unmeasured window is logged as a no-trigger (``outcome_r=None``), never a
    fabricated outcome -- the chamber's ``live_score`` counts it but never scores it
    as 0R. Returns the logged row (or ``{}`` for an empty strategy).
    """
    from app.factory import realms
    sid = str(strategy or "").strip()
    if not sid:
        return {}
    tape = tape_window(ticks, now_ts=now_ts, minutes=minutes)
    group = realms.family_group(str(family))
    rep = replay_strategy(tape, group, strong_delta=strong_delta)
    return record_window(state, sid, ts=now_ts, outcome_r=rep["outcome_r"],
                         pair=pair, entry_ts=(tape["ticks"][0]["ts"]
                                              if tape.get("ticks") else ""))


# --- THE LIVE EVIDENCE LEDGER (THE REAL HUNT, Part Three) ------------------

# The live-resume horizons (hours) and their window sizes.
RESUME_HORIZONS: dict[str, int] = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}


def live_resume(state: dict, strategy: str, *,
                now_ts: str = "", horizons: dict | None = None) -> dict:
    """A strategy's LIVE RESUME: what it would have done over 24h / 7d / 30d.

    Reads the chamber's window log (the accumulated forward-test data) and summarises
    each horizon: the number of judged windows, the live expectancy and the win rate.
    Honest: a horizon with no known outcome reports ``None`` (the present has not
    judged it yet) -- never a fabricated expectancy.
    """
    sid = str(strategy or "")
    rows = (((state or {}).get("forward_test") or {}).get("windows") or {}).get(sid) or []
    now = _parse_ts(now_ts)
    out: dict[str, dict] = {}
    for label, hours in (horizons or RESUME_HORIZONS).items():
        cut = None
        if now is not None:
            from datetime import timedelta
            cut = now - timedelta(hours=int(hours))
        sel = []
        for r in rows:
            t = _parse_ts(r.get("ts"))
            if cut is None or t is None or t >= cut:
                sel.append(r)
        known = [r["outcome_r"] for r in sel
                 if isinstance(r.get("outcome_r"), (int, float))]
        wins = [x for x in known if x > 0]
        out[label] = {
            "windows": len(sel), "judged": len(known),
            "expectancy": round(sum(known) / len(known), 4) if known else None,
            "win_rate": round(len(wins) / len(known), 4) if known else None,
        }
    return {"strategy": sid, "horizons": out,
            "measured": any(h["judged"] for h in out.values()),
            "reading": (f"{sid}: dal vivo "
                        + ", ".join(f"{k} {v['expectancy']:+.3f}R" if v["expectancy"]
                                    is not None else f"{k} --"
                                    for k, v in out.items()))}


def live_gap(state: dict, strategy: str, backtest: float | None, *,
             now_ts: str = "", horizon: str = "7d") -> dict:
    """The GAP between a strategy's live resume and its backtest expectation.

    A large POSITIVE gap = the strategy is BETTER than history suggests (a fresh edge);
    a large NEGATIVE gap = the edge is DECAYING. Honest: an unmeasured live or backtest
    axis -> ``None`` (the gap is not invented).
    """
    resume = live_resume(state, strategy, now_ts=now_ts)
    live = (resume["horizons"].get(horizon) or {}).get("expectancy")
    if not isinstance(live, (int, float)) or not isinstance(backtest, (int, float)):
        return {"gap": None, "measured": False, "live": live, "backtest": backtest,
                "reading": f"{strategy}: gap non misurato (un asse manca)"}
    gap = round(float(live) - float(backtest), 4)
    return {"gap": gap, "measured": True, "live": live, "backtest": backtest,
            "fresh_edge": gap > 0, "decaying": gap < 0,
            "reading": (f"{strategy}: gap {gap:+.3f}R (dal vivo {live:+.3f} vs storico "
                        f"{backtest:+.3f}) -- "
                        + ("vantaggio fresco" if gap > 0 else "vantaggio in decadenza"))}


def evidence_ledger(state: dict, backtest_scores: dict | None = None, *,
                    now_ts: str = "") -> dict:
    """THE LIVE EVIDENCE LEDGER: every strategy's live resume + its live/backtest gap.

    PUBLIC to all agents (the Council and the Cathedral's Column 7 consult it
    directly). Honest: a strategy with no judged window carries ``None`` resumes.
    """
    bt = dict(backtest_scores or {})
    rows = []
    for sid in (((state or {}).get("forward_test") or {}).get("enrolled") or []):
        resume = live_resume(state, sid, now_ts=now_ts)
        gap = live_gap(state, sid, bt.get(sid), now_ts=now_ts)
        rows.append({"strategy": sid, "resume": resume["horizons"],
                     "gap": gap["gap"], "fresh_edge": gap.get("fresh_edge"),
                     "decaying": gap.get("decaying")})
    return {"rows": rows, "n": len(rows),
            "measured": any(r["resume"].get("7d", {}).get("judged") for r in rows),
            "reading": f"libro delle prove dal vivo: {len(rows)} strategie"}
