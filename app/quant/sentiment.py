"""THE GROK SENSOR -- real-time crowd sentiment from X (Mega Phase 2, Section H).

When the CEO provides a Grok/X API key, this sensor searches X for ``$PAIR`` cashtags,
extracts the trading crowd's REAL-TIME sentiment, and turns it into a feature
("X sentiment on EURUSD: 68% bullish from 847 posts in the last hour"). An extreme
(>= 85% one way) fires the CONTRARIAN FLAG. It also tracks the VELOCITY of finance
topics (#FOMC, #ECB, #DXY, ...) as an early news pulse.

When no key is provided, the sensor is HONESTLY UNAVAILABLE -- it never fabricates a
sentiment. The social ear (Reddit + StockTwits) is expanded to the same shape, so the
feature exists with or without a paid key.

Honesty is binding: an absent key, an empty search, or an unreachable endpoint reports
``available=False`` / ``measured=False``, never a made-up share. Network I/O fires ONLY
when a key is present and a caller asks (Build Mode: no I/O at import, no scheduler).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

__all__ = [
    "SENTIMENT_VERSION",
    "EXTREME_SHARE",
    "NEWS_TOPICS",
    "grok_available",
    "grok_sentiment",
    "topic_velocity",
    "crowd_feature",
    "sentiment_block",
]

SENTIMENT_VERSION: int = 1

# The extreme threshold: at or above this one-sided share the contrarian flag fires.
EXTREME_SHARE: float = 0.85

# The finance topics whose VELOCITY is tracked (breaking-news proxy).
NEWS_TOPICS: tuple[str, ...] = ("FOMC", "ECB", "DXY", "inflation", "forex", "NFP", "CPI")


def grok_available() -> bool:
    """True when a Grok/X key is configured (never a fabricated availability)."""
    return bool(os.environ.get("GROK_API_KEY") or os.environ.get("X_API_KEY"))


def grok_sentiment(pair: str, *, url: str | None = None, key: str | None = None,
                   timeout: float = 10.0) -> dict:
    """Search X for ``$pair`` and return the crowd's measured sentiment.

    Reads ``GROK_API_URL`` / ``GROK_API_KEY`` (or ``X_API_KEY``). Honest: with no key
    this returns ``available=False`` WITHOUT any network call. With a key it POSTs an
    OpenAI-compatible query and parses ``{posts, bullish, bearish}``; any failure
    returns ``available=True, measured=False`` with the reason -- never a guess.
    """
    key = key if key is not None else (os.environ.get("GROK_API_KEY")
                                       or os.environ.get("X_API_KEY", ""))
    url = url or os.environ.get("GROK_API_URL", "")
    if not key:
        return {"available": False, "measured": False, "pair": pair,
                "reading": "sensore Grok: non disponibile (nessuna chiave)"}
    if not url:
        return {"available": True, "measured": False, "pair": pair,
                "reading": "sensore Grok: chiave presente ma nessun endpoint"}
    payload = json.dumps({"query": f"${pair}", "topics": list(NEWS_TOPICS)}).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {"available": True, "measured": False, "pair": pair,
                "error": type(exc).__name__,
                "reading": f"sensore Grok: irraggiungibile ({type(exc).__name__})"}
    posts = data.get("posts")
    bullish = data.get("bullish")
    bearish = data.get("bearish")
    return _summarize(pair, posts, bullish, bearish, source="grok")


def _summarize(pair: str, posts, bullish, bearish, *, source: str) -> dict:
    """Turn raw counts into the honest sentiment feature + contrarian reading."""
    n_posts = int(posts) if isinstance(posts, (int, float)) else None
    b = int(bullish) if isinstance(bullish, (int, float)) else None
    s = int(bearish) if isinstance(bearish, (int, float)) else None
    if b is None or s is None or (b + s) == 0:
        return {"available": True, "measured": False, "pair": pair, "source": source,
                "posts": n_posts,
                "reading": f"sentiment {source} {pair}: non misurato (nessun post)"}
    share = b / (b + s)
    extreme = share >= EXTREME_SHARE or share <= (1 - EXTREME_SHARE)
    flag = None
    if extreme:
        side = "greed" if share >= EXTREME_SHARE else "fear"
        flag = {"flag": "contrarian", "side": side, "share": round(share, 3),
                "reading": f"bandiera contraria: folla {side} estremo su {pair} "
                           f"({share:.0%})"}
    return {
        "available": True, "measured": True, "pair": pair, "source": source,
        "posts": n_posts, "bullish": b, "bearish": s, "bull_share": round(share, 4),
        "extreme": bool(extreme), "contrarian": flag,
        "reading": (f"sentiment {source} {pair}: {share:.0%} rialzista "
                    f"({b+s} post" + (f", {n_posts} nell'ultima ora" if n_posts else "") + ")"),
    }


def topic_velocity(topics: dict | None, *, window_minutes: int = 15,
                   accel_threshold: float = 3.0) -> dict:
    """The news pulse: which finance topic is ACCELERATING (a breaking-news proxy).

    ``topics`` maps topic -> list of mention counts over time buckets (most recent
    last). Velocity = last bucket vs the trailing mean; acceleration = velocity vs the
    previous velocity. Honest: a topic with too few buckets is unmeasured.
    """
    out: dict = {}
    for topic, series in (topics or {}).items():
        vals = [float(v) for v in (series or []) if isinstance(v, (int, float))]
        if len(vals) < 3:
            out[topic] = {"measured": False}
            continue
        recent = vals[-1]
        base = sum(vals[:-1]) / len(vals[:-1]) or 1.0
        velocity = recent / base
        prev = vals[-2] / (sum(vals[:-2]) / len(vals[:-2]) or 1.0) if len(vals) > 2 else 1.0
        accel = velocity / prev if prev > 0 else velocity
        out[topic] = {"measured": True, "velocity": round(velocity, 3),
                      "acceleration": round(accel, 3),
                      "breaking": bool(accel >= accel_threshold)}
    breaking = [t for t, v in out.items() if v.get("breaking")]
    return {"topics": out, "breaking": breaking,
            "reading": (f"polso notizie: {', '.join(breaking)} accelerano"
                        if breaking else "polso notizie: nessun argomento in accelerazione")}


def crowd_feature(sentiment: dict | None, ear: dict | None) -> dict:
    """One honest feature combining the Grok sensor and the social ear (Reddit/StockTwits).

    Either source may be absent; the feature reports which were measured and a single
    ``bull_share`` in [0,1] (``None`` when neither measured).
    """
    shares = []
    sources = []
    if isinstance((sentiment or {}).get("bull_share"), (int, float)):
        shares.append(float(sentiment["bull_share"]))
        sources.append(sentiment.get("source", "grok"))
    e = ear or {}
    bull = e.get("stocktwits_bullish")
    bear = e.get("stocktwits_bearish")
    if isinstance(bull, int) and isinstance(bear, int) and (bull + bear) > 0:
        shares.append(bull / (bull + bear))
        sources.append("stocktwits")
    bull_share = round(sum(shares) / len(shares), 4) if shares else None
    return {"bull_share": bull_share, "sources": sources,
            "measured": bool(shares),
            "reading": (f"folla: {bull_share:.0%} rialzista ({', '.join(sources)})"
                        if bull_share is not None else "folla: non misurata")}


def sentiment_block(*, pair: str = "EURUSD", topics: dict | None = None,
                    ear: dict | None = None) -> dict:
    """The Letter block: the Grok sensor + the news pulse + the combined crowd feature."""
    sent = grok_sentiment(pair)
    pulse = topic_velocity(topics)
    feat = crowd_feature(sent if sent.get("measured") else None, ear)
    return {"version": SENTIMENT_VERSION, "sensor": sent, "pulse": pulse,
            "crowd": feat,
            "measured": bool(sent.get("measured") or pulse.get("breaking") or feat.get("measured")),
            "reading": (sent.get("reading") if sent.get("measured")
                        else feat.get("reading"))}
