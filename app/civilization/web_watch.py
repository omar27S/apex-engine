"""THE LIVING WEB WATCH -- the eyes outside, watching CONTINUOUSLY (Part Two).

The patrol was one pass a night; this makes it a STANDING WATCH: every 2 hours a
different agent takes the watch (ForexFactory, central banks, news, the economic
calendar) so that at ANY moment someone is looking outside. The watch extracts the
NEWS PULSE (what the world is emotionally focused on), watches the EVENT HORIZON
(30 minutes before a high-impact event the Council gets a STANDING ALERT), ranks the
sources it finds, and carries a SOCIAL EAR (the crowd's whisper: Fear & Greed,
public Reddit, StockTwits).

Honesty is binding: a page that fails to fetch is an honest "non visto" (never a
fabricated fact); the pulse over no news is ``None``; an unmeasured event calendar is
empty, not invented. All social data is CONTEXT (Law 9 spirit): it INFORMS, it never
trades. Read-only: only GET on public pages (the navigator's cage extends here).

Pure at import (Scar #6): the schedule, the pulse reduction, the event horizon and
the contrarian flag are pure; the fetching lives in ``tools/web_watch.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "WATCH_VERSION",
    "WATCH_AGENTS",
    "WATCH_INTERVAL_HOURS",
    "EVENT_LEAD_MINUTES",
    "HIGH_IMPACT",
    "PULSE_KINDS",
    "watch_slot",
    "patrol_rotation",
    "news_pulse",
    "event_horizon",
    "standing_alert",
    "rank_sources",
    "social_ear",
    "contrarian_flag",
    "web_watch_block",
]

WATCH_VERSION: int = 1

# The agents that rotate onto the watch (a standing roster; the caller supplies the
# real census and the rotation picks from it -- this is the fallback roster).
WATCH_AGENTS: tuple[str, ...] = ("explorer-1", "sniper-1", "philosopher-1",
                                 "king-trend", "king-range", "falcon")

# The watch rotates every 2 hours.
WATCH_INTERVAL_HOURS: int = 2

# A standing alert fires this many minutes before a high-impact event.
EVENT_LEAD_MINUTES: int = 30

# The event impacts that warrant a standing alert.
HIGH_IMPACT: tuple[str, ...] = ("high", "alto")

# The emotional pulses the news is classified into.
PULSE_KINDS: tuple[str, ...] = ("rate_decision", "crisis", "earnings", "inflation",
                                "employment", "geopolitics", "quiet")


def _parse(ts: str) -> datetime | None:
    v = str(ts or "").strip().replace("Z", "+00:00")
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def watch_slot(ts: str) -> dict:
    """Which 2-hour watch slot a timestamp falls in (the rotation's clock)."""
    dt = _parse(ts)
    if dt is None:
        return {"slot": None, "measured": False, "reading": "orologio non misurato"}
    slot = dt.hour // WATCH_INTERVAL_HOURS
    return {"slot": slot, "hour": dt.hour, "measured": True,
            "reading": f"turno di guardia: slot {slot} (ore {dt.hour:02d})"}


def patrol_rotation(ts: str, *, agents: tuple[str, ...] | None = None) -> dict:
    """Whose turn it is on the watch -- a different agent every 2 hours, forever.

    Honest: an unparseable timestamp picks nobody (``agent=None``).
    """
    roster = tuple(agents) if agents else WATCH_AGENTS
    slot = watch_slot(ts)
    if slot["slot"] is None or not roster:
        return {"agent": None, "slot": None, "measured": False,
                "reading": "nessun agente di guardia (orologio non misurato)"}
    agent = roster[slot["slot"] % len(roster)]
    return {"agent": agent, "slot": slot["slot"], "measured": True,
            "reading": f"guardia web: turno di {agent}"}


def news_pulse(headlines: list[str]) -> dict:
    """The NEWS PULSE: what the financial world is emotionally focused on right now.

    Classifies a list of real headlines into a dominant pulse kind by keyword. Honest:
    no headlines -> ``quiet`` with ``measured=False`` (never an invented mood).
    """
    text = " ".join(str(h) for h in (headlines or [])).lower()
    if not text.strip():
        return {"pulse": None, "measured": False, "matches": {},
                "reading": "polso delle notizie non misurato (nessun titolo)"}
    keywords = {
        "rate_decision": ("rate", "fed", "ecb", "boj", "fomc", "hike", "cut", "tassi"),
        "crisis": ("crisis", "crash", "default", "collapse", "crisi", "panic"),
        "earnings": ("earnings", "guidance", "revenue", "utili", "quarter"),
        "inflation": ("inflation", "cpi", "ppi", "inflazione", "prices"),
        "employment": ("jobs", "payrolls", "unemployment", "occupazione", "nfp"),
        "geopolitics": ("war", "sanctions", "tariff", "election", "guerra", "dazi"),
    }
    matches = {k: sum(1 for w in words if w in text) for k, words in keywords.items()}
    matches = {k: n for k, n in matches.items() if n}
    if not matches:
        pulse = "quiet"
    else:
        pulse = max(matches.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return {"pulse": pulse, "measured": True, "matches": matches,
            "reading": f"il mondo dice: {pulse}"}


def event_horizon(events: list[dict], *, now: str) -> dict:
    """Watch the economic calendar LIVE and build the standing alert.

    ``events`` is ``[{name, ts, impact}, ...]``. An event within
    :data:`EVENT_LEAD_MINUTES` of ``now`` with a HIGH impact is a STANDING ALERT.
    Honest: an unparseable event timestamp is skipped, never guessed.
    """
    now_dt = _parse(now)
    alerts: list[dict] = []
    upcoming: list[dict] = []
    for e in (events or []):
        e_dt = _parse(e.get("ts", ""))
        if e_dt is None or now_dt is None:
            continue
        minutes = (e_dt - now_dt).total_seconds() / 60.0
        row = {"name": e.get("name"), "ts": e.get("ts"),
               "impact": e.get("impact"), "minutes": round(minutes, 1)}
        if -5 <= minutes <= 24 * 60:
            upcoming.append(row)
        impact = str(e.get("impact") or "").lower()
        if impact in HIGH_IMPACT and 0 <= minutes <= EVENT_LEAD_MINUTES:
            alerts.append(row)
    upcoming.sort(key=lambda r: r["minutes"])
    return {"alerts": alerts, "upcoming": upcoming[:10],
            "reading": (f"orizzonte eventi: {len(alerts)} avvisi in {EVENT_LEAD_MINUTES} min"
                        if alerts else "orizzonte eventi: nessun evento imminente")}


def standing_alert(horizon: dict) -> dict | None:
    """The single loudest standing alert (or ``None`` when the horizon is calm)."""
    alerts = (horizon or {}).get("alerts") or []
    if not alerts:
        return None
    first = alerts[0]
    return {**first, "reading": (f"AVVISO: {first.get('name')} tra "
                                 f"{first.get('minutes')} min -- il falco allarga gli occhi")}


def rank_sources(sources: list[dict]) -> list[dict]:
    """Rank the watch's sources by reliability x freshness (the watch learns WHERE).

    ``sources`` is ``[{name, ok_count, fail_count, last_ok_ts}, ...]``. A source with
    no attempts is excluded (never ranked on nothing).
    """
    ranked: list[dict] = []
    for s in (sources or []):
        ok = int(s.get("ok_count") or 0)
        fail = int(s.get("fail_count") or 0)
        attempts = ok + fail
        if attempts <= 0:
            continue
        score = round(ok / attempts, 4)
        ranked.append({**s, "score": score, "attempts": attempts})
    ranked.sort(key=lambda r: (-r["score"], r.get("name") or ""))
    return ranked


def social_ear(fear_greed: dict | None, reddit: list[dict] | None,
               stocktwits: list[dict] | None) -> dict:
    """The SOCIAL EAR: the crowd's mood from free, read-only public sources.

    Honest: every absent source is ``None``; the ear reports only what it measured.
    """
    fg = fear_greed or {}
    fg_value = fg.get("value")
    reddit_rows = list(reddit or [])
    st_rows = list(stocktwits or [])
    bullish = sum(1 for r in st_rows if str(r.get("sentiment")).lower() == "bullish")
    bearish = sum(1 for r in st_rows if str(r.get("sentiment")).lower() == "bearish")
    return {
        "fear_greed": fg_value if isinstance(fg_value, (int, float)) else None,
        "reddit_posts": len(reddit_rows) if reddit is not None else None,
        "stocktwits_bullish": bullish if stocktwits is not None else None,
        "stocktwits_bearish": bearish if stocktwits is not None else None,
        "measured": any(x is not None for x in (fg_value,
                                                len(reddit_rows) if reddit is not None else None,
                                                bullish if stocktwits is not None else None)),
        "reading": (f"orecchio sociale: paura/avidita {fg_value}"
                    if isinstance(fg_value, (int, float))
                    else "orecchio sociale: non misurato"),
    }


def contrarian_flag(ear: dict) -> dict | None:
    """A CONTRARIAN OPPORTUNITY FLAG when the crowd is EXTREMELY one-sided.

    Not a trade signal -- a context the Council sees. Fires when Fear & Greed is at an
    extreme, or StockTwits is overwhelmingly bullish/bearish.
    """
    fg = (ear or {}).get("fear_greed")
    bull = (ear or {}).get("stocktwits_bullish")
    bear = (ear or {}).get("stocktwits_bearish")
    if isinstance(fg, (int, float)) and (fg <= 20 or fg >= 80):
        side = "fear" if fg <= 20 else "greed"
        return {"flag": "contrarian", "side": side, "value": fg,
                "reading": f"bandiera contraria: folla in {side} estremo ({fg})"}
    if isinstance(bull, int) and isinstance(bear, int) and bull + bear >= 20:
        share = bull / (bull + bear)
        if share >= 0.85:
            return {"flag": "contrarian", "side": "greed", "value": round(share, 3),
                    "reading": f"bandiera contraria: folla tutta rialzista ({share:.0%})"}
        if share <= 0.15:
            return {"flag": "contrarian", "side": "fear", "value": round(share, 3),
                    "reading": f"bandiera contraria: folla tutta ribassista ({share:.0%})"}
    return None


def web_watch_block(state: dict, *, now: str = "") -> dict:
    """The web watch's block for the Letter: the rotation, the pulse, the horizon."""
    w = (state or {}).get("web_watch") or {}
    rotation = patrol_rotation(now) if now else {"agent": None, "measured": False,
                                                 "reading": "guardia non misurata"}
    horizon = event_horizon(w.get("events") or [], now=now)
    alert = standing_alert(horizon)
    ear = social_ear(w.get("fear_greed"), w.get("reddit"), w.get("stocktwits"))
    flag = contrarian_flag(ear)
    return {
        "guard": rotation["agent"],
        "pulse": w.get("pulse"),
        "alert": alert,
        "contrarian": flag,
        "ear": ear,
        "reading": (f"guardia web: {rotation['agent'] or '--'}; "
                    f"polso: {w.get('pulse') or '--'}"
                    + (f"; {alert['reading']}" if alert else "")),
    }
