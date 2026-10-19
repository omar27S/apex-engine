"""THE PRESENT SABOTEUR -- JUMP 6: CONTINUOUS STRESS-TEST (the future attacked now).

RAMS attacks tournaments on historical data, but the biggest danger is: "would our
CURRENT strategies survive what is happening RIGHT NOW if it goes wrong?" Every hour
the Present Saboteur attacks the ACTIVE portfolio with what could happen NOW:

  * THE CONTINUOUS STRESS-TEST -- a FLASH CRASH ("if the market dropped 2% in the next
    5 minutes, what happens to our active strategies?", using their ACTUAL stop
    levels), a SPREAD EXPLOSION ("if spreads tripled NOW, which strategies are
    crushed?"), and a NEWS SHOCK ("if a high-impact event fired NOW -- the web watch
    knows if one is 30 minutes away -- what is the damage?"). The results are the
    STRESS-TEST LEDGER: the portfolio's real-time vulnerability profile;
  * THE SURVIVAL THRESHOLD -- a maximum acceptable damage profile. If ANY scenario
    exceeds it, the SURVIVAL ALARM fires: the Council is notified, the Letter shows the
    vulnerability, the Dragon recommends defensive actions. The alarm is HONEST: it may
    fire often at first -- each firing leads to adaptation;
  * THE DEFENSIVE EVOLUTION -- the stress results feed the tournament as a NEW FITNESS
    DIMENSION: strategies that survive the present gain a survival bonus, so evolution
    selects for ROBUSTNESS, not just backtest fitness. The Saboteur's attacks now
    include PRESENT-DERIVED scenarios ("attack them with what could happen NOW").

Honesty is binding: an unmeasured axis yields ``None`` (never a fabricated loss); a
scenario over no strategies reports ``None`` damage, never 0. Pure at import
(Scar #6): the readings + the portfolio come from the caller; no wall clock is read.
"""

from __future__ import annotations

__all__ = [
    "STRESS_VERSION",
    "FLASH_CRASH_DROP_PCT",
    "SPREAD_EXPLOSION_MULT",
    "NEWS_SHOCK_PCT",
    "NEWS_LEAD_MINUTES",
    "DEFAULT_MAX_DAMAGE_PCT",
    "SURVIVAL_BONUS",
    "flash_crash_damage",
    "spread_explosion_damage",
    "news_shock_damage",
    "stress_scenarios",
    "survival_threshold",
    "defensive_bonus",
    "present_scenarios",
    "stress_test",
    "stress_test_block",
    "portfolio_from_leaderboard",
    "observed_damage",
]

STRESS_VERSION: int = 1

# The three present attacks.
FLASH_CRASH_DROP_PCT: float = 0.02      # a 2% drop in the next 5 minutes
SPREAD_EXPLOSION_MULT: float = 3.0      # spreads tripled
NEWS_SHOCK_PCT: float = 0.015           # a high-impact event fires a 1.5% shock
NEWS_LEAD_MINUTES: int = 30             # the web watch knows if an event is this near

# The Council's default survival threshold: no scenario may cost more than this share
# of the account in the next hour.
DEFAULT_MAX_DAMAGE_PCT: float = 0.02

# The survival bonus a fully stress-robust strategy earns (bounded, a bonus only).
SURVIVAL_BONUS: float = 0.05


def _damage_of(row: dict, shock_pct: float) -> float | None:
    """The account-fraction damage to ONE strategy from a ``shock_pct`` adverse move.

    A strategy carries ``stop_pct`` (its stop distance as a fraction of price) and
    ``risk_pct`` (the account fraction at risk if stopped). A shock at or beyond the
    stop loses the full risk; a smaller shock loses proportionally. Honest: an
    unmeasured ``risk_pct`` or ``stop_pct`` -> ``None`` (never a fabricated loss).
    """
    risk = row.get("risk_pct")
    stop = row.get("stop_pct")
    if not isinstance(risk, (int, float)) or not isinstance(stop, (int, float)) or stop <= 0:
        return None
    if shock_pct >= stop:
        return float(risk)
    return float(risk) * (shock_pct / stop)


def _aggregate(kind: str, rows: list[dict], shock_pct: float,
               *, label: str) -> dict:
    """Sum the damage across the portfolio for one scenario (honest)."""
    damages = [(_damage_of(r, shock_pct), r) for r in (rows or [])]
    known = [(d, r) for d, r in damages if d is not None]
    if not known:
        return {"kind": kind, "damage_pct": None, "n_at_risk": 0,
                "n_unmeasured": len(damages), "affected": [],
                "reading": f"{label}: danno non misurato (nessuna strategia valutabile)"}
    total = sum(d for d, _ in known)
    affected = sorted({str(r.get("strategy")) for _, r in known if _ > 0})
    return {"kind": kind, "damage_pct": round(total, 6), "n_at_risk": len(known),
            "n_unmeasured": len(damages) - len(known), "affected": affected,
            "reading": (f"{label}: danno {total:.2%} su {len(known)} strategie "
                        f"({len(affected)} colpite)")}


def flash_crash_damage(portfolio: list[dict], *,
                       drop_pct: float = FLASH_CRASH_DROP_PCT) -> dict:
    """Scenario (a): the market drops ``drop_pct`` NOW -- what happens to the portfolio?

    Uses each strategy's ACTUAL stop level. Honest: an unmeasured stop/risk is skipped.
    """
    return _aggregate("flash_crash", portfolio, drop_pct,
                      label=f"flash crash -{drop_pct:.1%}")


def spread_explosion_damage(portfolio: list[dict], *,
                            mult: float = SPREAD_EXPLOSION_MULT) -> dict:
    """Scenario (b): spreads multiply ``mult`` times NOW -- which strategies are crushed?

    A strategy is CRUSHED when the multiplied spread eats its whole edge. Honest: an
    unmeasured edge or spread is skipped, never assumed safe.
    """
    crushed: list[dict] = []
    n_unmeasured = 0
    for r in (portfolio or []):
        edge = r.get("edge_pips")
        spread = r.get("spread_pips")
        risk = r.get("risk_pct")
        if not all(isinstance(v, (int, float)) for v in (edge, spread, risk)):
            n_unmeasured += 1
            continue
        if mult * float(spread) >= float(edge):
            crushed.append(r)
    if not crushed and n_unmeasured == len(portfolio or []):
        return {"kind": "spread_explosion", "damage_pct": None, "n_at_risk": 0,
                "n_unmeasured": n_unmeasured, "affected": [],
                "reading": "spread tripli: danno non misurato (nessuna strategia valutabile)"}
    total = sum(float(r.get("risk_pct") or 0.0) for r in crushed)
    affected = sorted({str(r.get("strategy")) for r in crushed})
    return {"kind": "spread_explosion", "damage_pct": round(total, 6),
            "n_at_risk": len(portfolio or []) - n_unmeasured,
            "n_unmeasured": n_unmeasured, "affected": affected,
            "reading": (f"spread x{mult:.0f}: danno {total:.2%} "
                        f"({len(crushed)} strategie schiacciate)")}


def news_shock_damage(portfolio: list[dict], *,
                      shock_pct: float = NEWS_SHOCK_PCT) -> dict:
    """Scenario (c): a high-impact event fires NOW -- what is the damage?"""
    return _aggregate("news_shock", portfolio, shock_pct,
                      label=f"shock notizie {shock_pct:.1%}")


def stress_scenarios(portfolio: list[dict]) -> list[dict]:
    """All three present attacks on the portfolio, in order."""
    return [flash_crash_damage(portfolio),
            spread_explosion_damage(portfolio),
            news_shock_damage(portfolio)]


def survival_threshold(scenarios: list[dict], *,
                       max_damage_pct: float = DEFAULT_MAX_DAMAGE_PCT) -> dict | None:
    """The SURVIVAL ALARM: fires when ANY scenario exceeds the threshold (honest).

    An unmeasured scenario (``damage_pct`` is ``None``) never triggers the alarm --
    no data is not a breach. Returns the worst breach, or ``None``.
    """
    breaches = [s for s in (scenarios or [])
                if isinstance(s.get("damage_pct"), (int, float))
                and s["damage_pct"] > max_damage_pct]
    if not breaches:
        return None
    worst = max(breaches, key=lambda s: s["damage_pct"])
    return {"worst": worst["kind"], "damage_pct": worst["damage_pct"],
            "threshold_pct": max_damage_pct, "breaches": [s["kind"] for s in breaches],
            "reading": (f"ALLARME DI SOPRAVVIVENZA: {worst['kind']} costa "
                        f"{worst['damage_pct']:.2%} (soglia {max_damage_pct:.2%})")}


def defensive_bonus(*, damage_pct: float | None,
                    bonus: float = SURVIVAL_BONUS) -> dict:
    """The DEFENSIVE EVOLUTION bonus: a stress-robust strategy earns a survival edge.

    ``robustness = 1 - min(1, damage / threshold)``; the bonus is bounded. Honest: an
    unmeasured damage leaves the fitness UNCHANGED (no bonus, no penalty).
    """
    if not isinstance(damage_pct, (int, float)):
        return {"bonus": 0.0, "robustness": None, "measured": False,
                "reading": "bonus di sopravvivenza: non misurato (fitness invariata)"}
    robustness = max(0.0, 1.0 - min(1.0, max(0.0, float(damage_pct))
                                    / DEFAULT_MAX_DAMAGE_PCT))
    return {"bonus": round(bonus * robustness, 6), "robustness": round(robustness, 4),
            "measured": True,
            "reading": (f"bonus di sopravvivenza: +{bonus * robustness:.4f} "
                        f"(robustezza {robustness:.0%})")}


def present_scenarios(reading: dict, *, events: list[dict] | None = None,
                      now_ts: str = "") -> list[dict]:
    """The PRESENT-DERIVED attacks for RAMS: what could happen NOW (not history).

    Scales the flash crash to the pair's MEASURED volatility (3x the current
    volatility, floored at the nominal 2%), and fires a news shock only when the web
    watch knows a high-impact event is within the lead window. Honest: no measured
    volatility -> the nominal scenario, flagged ``derived=False``.
    """
    r = reading or {}
    vol = r.get("volatility_pips")
    drop = FLASH_CRASH_DROP_PCT
    derived = False
    if isinstance(vol, (int, float)) and vol > 0:
        # volatility in pips -> a rough fraction (10 pips ~ 0.1% on a major).
        drop = max(FLASH_CRASH_DROP_PCT, min(0.1, (3.0 * float(vol)) / 10_000.0))
        derived = True
    out = [{"kind": "flash_crash", "drop_pct": round(drop, 6), "derived": derived,
            "reading": f"attacco presente: caduta {drop:.2%} "
                       f"({'dalla volatilita misurata' if derived else 'nominale'})"}]
    near = _near_event(events or [], now_ts=now_ts)
    if near:
        out.append({"kind": "news_shock", "shock_pct": NEWS_SHOCK_PCT,
                    "event": near.get("name"), "derived": True,
                    "reading": f"attacco presente: shock su {near.get('name')}"})
    return out


def _near_event(events: list[dict], *, now_ts: str) -> dict | None:
    from datetime import datetime, timezone

    def _p(ts):
        v = str(ts or "").strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(v)
        except ValueError:
            return None
        return d.replace(tzinfo=d.tzinfo or timezone.utc).astimezone(timezone.utc)

    now = _p(now_ts)
    if now is None:
        return None
    for e in (events or []):
        if str(e.get("impact") or "").lower() != "high":
            continue
        when = _p(e.get("ts"))
        if when is None:
            continue
        mins = (when - now).total_seconds() / 60.0
        if 0 <= mins <= NEWS_LEAD_MINUTES:
            return e
    return None


def stress_test(portfolio: list[dict], *, reading: dict | None = None,
                events: list[dict] | None = None, ts: str = "",
                max_damage_pct: float = DEFAULT_MAX_DAMAGE_PCT) -> dict:
    """One STRESS-TEST turn: run the three attacks, threshold them, log the ledger row.

    Returns the ledger row (scenarios + the survival alarm). The row is what feeds the
    artifact, the Letter and the Dragon's defensive advice.
    """
    scenarios = stress_scenarios(portfolio)
    alarm = survival_threshold(scenarios, max_damage_pct=max_damage_pct)
    observed = observed_damage(portfolio)
    row = {"ts": str(ts), "n_strategies": len(portfolio or []),
           "scenarios": scenarios, "observed": observed, "alarm": alarm,
           "present": present_scenarios(reading or {}, events=events, now_ts=ts),
           "reading": (alarm["reading"] if alarm else
                       f"stress-test: nessuno scenario oltre la soglia "
                       f"({max_damage_pct:.2%})")}
    return row


def portfolio_from_leaderboard(leaderboard: list[dict], *,
                               risk_pct: float = 0.01,
                               atr_pips: float = 10.0) -> list[dict]:
    """Build the ACTIVE portfolio for the stress-test from the real leaderboard rows.

    Each row's risk geometry is DERIVED honestly from its genes: the stop distance is
    ``sl_atr_mult`` ATRs (converted to a price fraction via ``atr_pips``); the account
    risk per trade is the fixed ``risk_pct``; the edge is the row's realized ``net_r``
    per trade. Honest: a row without a numeric ``net_r`` still gets a portfolio entry,
    but its edge is ``None`` so the spread scenario skips it (never assumed safe).
    """
    out: list[dict] = []
    for r in (leaderboard or []):
        sl = r.get("sl_atr_mult")
        stop_pct = (float(sl) * float(atr_pips) / 10_000.0
                    if isinstance(sl, (int, float)) else None)
        trades = r.get("trades")
        net_r = r.get("net_r")
        edge_pips = None
        if isinstance(net_r, (int, float)) and isinstance(trades, int) and trades > 0:
            edge_pips = float(net_r) * float(atr_pips) / float(trades)
        out.append({"strategy": str(r.get("signature") or r.get("family") or ""),
                    "family": r.get("family"),
                    "stop_pct": stop_pct, "risk_pct": risk_pct,
                    "edge_pips": edge_pips, "spread_pips": r.get("spread_pips"),
                    "measured_dd_r": r.get("measured_dd_r")})
    return out


def observed_damage(portfolio: list[dict], *,
                    risk_pct: float = 0.01) -> dict:
    """DEBT-065: the MAXIMUM DAMAGE the portfolio ALREADY took (the real drawdown).

    The stress scenarios project what COULD happen; this reads what DID. Each
    leaderboard row carries a MEASURED ``measured_dd_r`` (its worst realized
    drawdown in R). The account-fraction damage is ``dd_r * risk_pct`` (each R is
    ``risk_pct`` of the account). The worst single strategy AND the portfolio
    (sum) are reported, so the Letter can fill the "danno" axis with a real
    number instead of "non misurato".

    Honest: a row with no numeric ``measured_dd_r`` is skipped; no measured row
    -> ``damage_pct`` is ``None`` (never a fabricated loss).
    """
    rows = [r for r in (portfolio or [])
            if isinstance(r.get("measured_dd_r"), (int, float))]
    if not rows:
        return {"kind": "observed", "damage_pct": None, "worst_r": None,
                "worst_strategy": None, "n_measured": 0, "n_total": len(portfolio or []),
                "reading": "danno osservato: non misurato (nessun dd_r sulle strategie)"}
    worst = max(rows, key=lambda r: float(r["measured_dd_r"]))
    worst_r = float(worst["measured_dd_r"])
    total_r = sum(float(r["measured_dd_r"]) for r in rows)
    return {"kind": "observed", "damage_pct": round(worst_r * risk_pct, 6),
            "portfolio_damage_pct": round(total_r * risk_pct, 6),
            "worst_r": round(worst_r, 4), "worst_strategy": worst.get("strategy"),
            "n_measured": len(rows), "n_total": len(portfolio or []),
            "reading": (f"danno osservato: {worst_r:.2f}R sul peggiore "
                        f"({worst.get('strategy')}), "
                        f"{worst_r * risk_pct:.2%} dell'account su {len(rows)} strategie")}


def stress_test_block(state: dict, *, portfolio: list[dict] | None = None,
                      reading: dict | None = None, events: list[dict] | None = None,
                      ts: str = "", max_damage_pct: float = DEFAULT_MAX_DAMAGE_PCT,
                      keep: int = 24) -> dict:
    """The stress-test block for the artifact + the Letter ("LO STRESS-TEST").

    Runs a turn, appends the ledger row to the state (bounded), and returns the block
    with the vulnerability profile and any alarm.
    """
    st = state if state is not None else {}
    if reading is None:
        reading = (st.get("falcon") or {}).get("readings") or {}
    if events is None:
        events = ((st.get("web_watch") or {}).get("events")
                  or ((st.get("web_watch") or {}).get("horizon") or {}).get("events")
                  or [])
    row = stress_test(portfolio or [], reading=reading, events=events, ts=ts,
                      max_damage_pct=max_damage_pct)
    ledger = st.setdefault("stress_test", {"ledger": []})
    ledger.setdefault("ledger", []).append(row)
    del ledger["ledger"][:-max(1, int(keep))]
    block = {"ledger": ledger["ledger"][-1], "alarm": row["alarm"],
             "reading": row["reading"]}
    st["stress_test_summary"] = block
    return block
