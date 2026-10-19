"""THE HAWK'S EYE -- THE REAL MARKET (Part Two: pipes, feeds and the orderflow).

The civilization's market eye, built in layers so each is testable WITHOUT a socket:

* THE PARSERS -- the exact wire format of each free feed (OANDA v20 stream, the
  TwelveData price websocket, the Polygon forex websocket) is decoded here. Pure
  functions: a JSON frame in, a normalized ``{source, pair, bid, ask, ts}`` tick
  out. No socket, no clock, no I/O -- so the decode is pinned by tests.
* THE ORDERFLOW -- the tick-rule classification (uptick = buyer aggression,
  downtick = seller aggression), the cumulative delta per pair per session, the
  imbalance bursts, and the spread behaviour (the spread IS orderflow information:
  its widening tells the fear). Pure reductions over the ticks the hub accepted.
* THE FUTURES CONTEXT -- the currency-futures legs (6E/6B/6J/DXY-relevant) watched
  as CONTEXT sensors, with the futures lead/lag vs spot as a radar reading ("the
  futures moved first by X seconds" -- the institutions' footsteps).
* THE VISION HEALTH -- with 2+ live sources the hub reports the agreement rate
  between sources, the latency per source and the reliability over time.

Honesty (binding): NO TRADES. A dirty tick never feeds. A feed without credentials
is inactive -- never a fabricated tick. A quote feed carries no volume, so the
orderflow volume proxy is named a proxy (tick counts), never a real traded volume.

Pure at import (Scar #6): parsers and reductions; the sockets live in
``tools/hawk_eye.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "MARKET_VERSION",
    "FUTURES_LEGS",
    "decode_oanda",
    "decode_twelvedata",
    "decode_polygon",
    "decode_kraken",
    "parse_tick",
    "normalize_pair",
    "session_key",
    "OrderflowRadar",
    "futures_context",
    "vision_health",
]

MARKET_VERSION: int = 1

# THE CURRENCY-FUTURES VISION -- the free futures-side views of the dollar and the
# majors, watched as CONTEXT sensors (never a trade surface). Each leg names the
# CME contract and the spot pair it leads/lags. CME's free delayed quotes and the
# free futures quotes some plans include are the sources; a leg with no reading is
# honestly absent, never invented.
FUTURES_LEGS: tuple[dict, ...] = (
    {"contract": "6E", "name": "Euro FX futures", "currency": "EUR",
     "spot": "EURUSD", "cme_symbol": "6E"},
    {"contract": "6B", "name": "British Pound futures", "currency": "GBP",
     "spot": "GBPUSD", "cme_symbol": "6B"},
    {"contract": "6J", "name": "Japanese Yen futures", "currency": "JPY",
     "spot": "USDJPY", "cme_symbol": "6J"},
    {"contract": "6A", "name": "Australian Dollar futures", "currency": "AUD",
     "spot": "AUDUSD", "cme_symbol": "6A"},
    {"contract": "DX", "name": "US Dollar Index futures", "currency": "USD",
     "spot": "DXY", "cme_symbol": "DX"},
)

# The pip size per pair family (the hub's tolerance is expressed in pips). A JPY
# quote is 2-decimal, everything else 4-decimal; honest default 1e-4.
_PIP_JPY = 1e-2
_PIP_DEFAULT = 1e-4


def normalize_pair(symbol: str) -> str:
    """Normalize a feed's symbol to the project's ``EURUSD`` form.

    Accepts ``EUR_USD`` (OANDA), ``EUR/USD`` (TwelveData), ``C:EURUSD`` (Polygon)
    and ``EURUSD``. An empty/unknown symbol is returned unchanged (fail-open on the
    label, the caller's cross-validation still gates the tick).
    """
    s = (symbol or "").strip().upper()
    if not s:
        return ""
    if s.startswith("C:"):
        s = s[2:]
    s = s.replace("/", "").replace("_", "").replace("-", "")
    return s


def pip_for(pair: str) -> float:
    """The pip size for a normalized pair (JPY quote = 0.01, else 0.0001)."""
    p = normalize_pair(pair)
    return _PIP_JPY if p.endswith("JPY") else _PIP_DEFAULT


def session_key(ts: str = "") -> str:
    """The session label a tick belongs to (the trading day, UTC).

    The orderflow delta accumulates PER PAIR PER SESSION. A missing/odd timestamp
    falls back to the current UTC date -- the session is a label, never a number
    that could be invented.
    """
    m = str(ts or "")[:10]
    if len(m) == 10 and m[4] == "-" and m[7] == "-":
        return m
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # reject NaN


def _ts(v) -> str:
    """A best-effort ISO-8601 UTC timestamp from a feed's own time field."""
    if v is None or v == "":
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, (int, float)):
        # seconds or milliseconds since the epoch.
        secs = float(v)
        if secs > 1e12:
            secs /= 1000.0
        try:
            return datetime.fromtimestamp(secs, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        except (OverflowError, OSError, ValueError):
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(v)


def decode_oanda(frame: dict, *, source: str = "oanda_v20_stream") -> dict | None:
    """Decode ONE OANDA v20 pricing-stream frame into a normalized tick.

    OANDA sends ``{"type": "PRICE", "instrument": "EUR_USD", "bids": [{"price"}],
    "asks": [{"price"}], "time": ...}`` plus HEARTBEAT frames (no price). A frame
    without a bid is not a tick: ``None`` (fail-closed).
    """
    if not isinstance(frame, dict):
        return None
    if str(frame.get("type", "")).upper() == "HEARTBEAT":
        return None
    bids = frame.get("bids") or []
    asks = frame.get("asks") or []
    bid = _f(bids[0].get("price")) if bids and isinstance(bids[0], dict) else None
    ask = _f(asks[0].get("price")) if asks and isinstance(asks[0], dict) else None
    if bid is None:
        return None
    pair = normalize_pair(frame.get("instrument", ""))
    if not pair:
        return None
    return {"source": source, "pair": pair, "bid": bid, "ask": ask,
            "ts": _ts(frame.get("time"))}


def decode_twelvedata(frame: dict, *, source: str = "twelvedata_ws") -> dict | None:
    """Decode ONE TwelveData price-websocket frame into a normalized tick.

    TwelveData sends ``{"event": "price", "symbol": "EUR/USD", "price": ...,
    "timestamp": ...}``; a status/error frame (``{"event": "subscribe-status"}`` or
    ``{"status": "error"}``) carries no price and yields ``None``.
    """
    if not isinstance(frame, dict):
        return None
    if frame.get("status") == "error":
        return None
    if str(frame.get("event", "")).lower() not in ("", "price"):
        return None
    price = _f(frame.get("price"))
    if price is None:
        return None
    pair = normalize_pair(frame.get("symbol", ""))
    if not pair:
        return None
    # TwelveData's price stream gives one price (mid); the tick carries it as bid.
    return {"source": source, "pair": pair, "bid": price, "ask": None,
            "ts": _ts(frame.get("timestamp"))}


def decode_polygon(frame: dict, *, source: str = "polygon_forex_ws") -> dict | None:
    """Decode ONE Polygon forex-websocket frame into a normalized tick.

    Polygon sends ``{"ev": "C", "p": "EUR/USD", "b": <bid>, "a": <ask>, "t": ms}``
    for quotes (``C``); other events (``status``, ``A`` aggregates without a bid)
    yield ``None`` when they carry no bid.
    """
    if not isinstance(frame, dict):
        return None
    ev = str(frame.get("ev", "")).upper()
    if ev in ("STATUS", "SUBSCRIBE"):
        return None
    bid = _f(frame.get("b"))
    ask = _f(frame.get("a"))
    if bid is None:
        return None
    pair = normalize_pair(frame.get("p", ""))
    if not pair:
        return None
    return {"source": source, "pair": pair, "bid": bid, "ask": ask,
            "ts": _ts(frame.get("t"))}


def decode_kraken(frame, *, source: str = "kraken_public_ws") -> dict | None:
    """Decode ONE Kraken public-websocket frame into a normalized tick.

    Kraken's public feed needs NO key and carries REAL FX majors. A ticker frame is
    the JSON ARRAY ``[channelID, {"b": [bid, ...], "a": [ask, ...], "c": [close, ...]},
    "ticker", "EUR/USD"]``; the arrays are ``[price_string, whole_lot_volume,
    lot_volume]`` so the price is the FIRST element. Every non-ticker frame (the
    ``{"event": ...}`` system/subscription status objects, heartbeats) yields
    ``None`` -- the decoder accepts only a real ticker quote.
    """
    if not isinstance(frame, list) or len(frame) < 4:
        return None
    if str(frame[-2]) != "ticker":
        return None
    q = frame[1]
    if not isinstance(q, dict):
        return None

    def _first(seq):
        if isinstance(seq, (list, tuple)) and seq:
            return _f(seq[0])
        return _f(seq)

    bid = _first(q.get("b"))
    ask = _first(q.get("a"))
    if bid is None:
        return None
    pair = normalize_pair(frame[-1])
    if not pair:
        return None
    return {"source": source, "pair": pair, "bid": bid, "ask": ask, "ts": _ts(None)}


_DECODERS = {
    "oanda": decode_oanda,
    "oanda_v20_stream": decode_oanda,
    "twelvedata": decode_twelvedata,
    "twelvedata_ws": decode_twelvedata,
    "polygon": decode_polygon,
    "polygon_forex_ws": decode_polygon,
    "kraken": decode_kraken,
    "kraken_public_ws": decode_kraken,
}


def parse_tick(source_name: str, frame) -> dict | None:
    """Route a raw frame to its source's decoder (unknown source -> ``None``)."""
    fn = _DECODERS.get(str(source_name or "").lower())
    if fn is None:
        return None
    return fn(frame)


class OrderflowRadar:
    """The REAL orderflow reading, accumulated from the ticks the hub accepted.

    Tick-rule classification: a tick whose bid is ABOVE the last bid for its pair is
    buyer aggression (an uptick), below is seller aggression (a downtick); an equal
    bid is neutral. The cumulative delta is (upticks - downticks) per pair per
    session -- the aggression balance. An imbalance BURST is a run of same-side
    ticks past ``burst_min``. The spread behaviour is tracked per source (a widening
    spread is the fear). All counters; a feed with no volume field reports the tick
    count as the honest PROXY (named a proxy, never a real volume).
    """

    def __init__(self, *, burst_min: int = 5) -> None:
        self.burst_min = int(burst_min)
        self.last_bid: dict[str, float] = {}          # pair -> last bid
        self.delta: dict[str, int] = {}               # (pair|session) -> delta
        self.ticks: dict[str, int] = {}               # (pair|session) -> ticks
        self.bursts: dict[str, int] = {}              # (pair|session) -> bursts
        self._run: dict[str, int] = {}                # pair -> signed run length
        self.spread: dict[str, list] = {}             # source -> [spreads]
        self.last: dict | None = None

    def _key(self, pair: str, ts: str) -> str:
        return f"{pair}|{session_key(ts)}"

    def ingest(self, tick: dict) -> dict:
        """Classify ONE tick and fold it into the per-pair session reading."""
        pair = tick.get("pair")
        bid = _f(tick.get("bid"))
        if not pair or bid is None:
            return {"side": "neutral", "reason": "tick senza prezzo"}
        prev = self.last_bid.get(pair)
        side = "neutral"
        if prev is not None:
            if bid > prev:
                side = "up"
            elif bid < prev:
                side = "down"
        self.last_bid[pair] = bid
        k = self._key(pair, tick.get("ts", ""))
        self.ticks[k] = self.ticks.get(k, 0) + 1
        d = self.delta.get(k, 0)
        if side == "up":
            d += 1
        elif side == "down":
            d -= 1
        self.delta[k] = d
        # a same-side run past burst_min is one imbalance burst.
        run = self._run.get(pair, 0)
        if side == "neutral":
            run = 0
        elif (side == "up" and run >= 0) or (side == "down" and run <= 0):
            run += (1 if side == "up" else -1)
        else:
            run = (1 if side == "up" else -1)
        self._run[pair] = run
        if abs(run) == self.burst_min:
            self.bursts[k] = self.bursts.get(k, 0) + 1
        # the spread behaviour (the fear), when the feed carries a bid AND an ask.
        ask = _f(tick.get("ask"))
        if ask is not None and ask >= bid:
            src = tick.get("source") or "?"
            self.spread.setdefault(src, []).append(round(ask - bid, 8))
            self.spread[src] = self.spread[src][-500:]
        self.last = {"pair": pair, "bid": bid, "side": side, "delta": d, "key": k}
        return {"side": side, "delta": d, "key": k}

    def digest(self, *, top: int = 5) -> dict:
        """The orderflow reading for the Letter ("il flusso oggi")."""
        by_pair: dict[str, dict] = {}
        for k, d in self.delta.items():
            pair, _, sess = k.partition("|")
            cur = by_pair.get(pair)
            if cur is None or sess > cur["session"]:
                by_pair[pair] = {"session": sess, "delta": d,
                                 "ticks": self.ticks.get(k, 0),
                                 "bursts": self.bursts.get(k, 0)}
        spreads = {s: (round(sum(v) / len(v), 8) if v else None)
                   for s, v in self.spread.items()}
        top_delta = sorted(by_pair.items(),
                           key=lambda kv: -abs(kv[1]["delta"]))[:top]
        reading = ("nessun tick accettato: il flusso non e' ancora misurato"
                   if not by_pair else
                   "flusso: " + ", ".join(
                       f"delta {v['delta']:+d} su {p} ({v['ticks']} tick, "
                       f"{v['bursts']} burst)" for p, v in top_delta))
        return {
            "by_pair": dict(sorted(by_pair.items())),
            "mean_spread_by_source": dict(sorted(spreads.items())),
            "bursts_total": sum(self.bursts.values()),
            "ticks_total": sum(self.ticks.values()),
            "volume_proxy": "tick_count (un feed di quotazioni non porta volume reale)",
            "reading": reading,
        }


def futures_context(*, futures_quotes: dict | None = None,
                    spot_quotes: dict | None = None, lag_tolerance_s: float = 2.0) -> dict:
    """The futures CONTEXT reading: the lead/lag of each futures leg vs spot.

    ``futures_quotes`` maps a contract (``6E``) to ``{"bid", "ts"}`` and
    ``spot_quotes`` maps the spot pair (``EURUSD``) to the same. When both are
    present the reading computes the futures lead/lag in seconds (the futures'
    timestamp minus the spot's) -- "the futures moved first by X seconds". A leg
    without a reading is honestly absent (never invented).
    """
    fq = futures_quotes or {}
    sq = spot_quotes or {}

    def _as_quote(q):
        """Accept either a ``{"bid", "ts"}`` dict or a bare price float."""
        if isinstance(q, dict):
            return q
        if isinstance(q, (int, float)):
            return {"bid": float(q), "ts": None}
        return {}

    legs: list[dict] = []
    for leg in FUTURES_LEGS:
        c = leg["contract"]
        f = _as_quote(fq.get(c))
        s = _as_quote(sq.get(leg["spot"]))
        row = {"contract": c, "name": leg["name"], "spot": leg["spot"],
               "watched": bool(f), "futures_bid": f.get("bid"),
               "spot_bid": s.get("bid")}
        lag = None
        if f and s and f.get("ts") and s.get("ts"):
            lag = _seconds_between(f["ts"], s["ts"])
        row["lead_lag_s"] = lag
        if lag is not None and abs(lag) <= lag_tolerance_s:
            row["reading"] = "futures e spot sincroni"
        elif lag is not None:
            row["reading"] = (f"i futures hanno mosso prima di {abs(lag):.1f}s"
                              if lag < 0 else
                              f"lo spot ha mosso prima di {abs(lag):.1f}s")
        else:
            row["reading"] = "contesto futures non misurato per questa gamba"
        legs.append(row)
    watched = [r for r in legs if r["watched"]]
    return {
        "legs": legs,
        "n_watched": len(watched),
        "n_legs": len(legs),
        "reading": (f"{len(watched)}/{len(legs)} gambe futures osservate"
                    + (f"; {watched[0]['reading']}" if watched else
                       "; nessun futuro osservato (contesto assente, mai inventato)")),
    }


def _seconds_between(ts_a, ts_b) -> float | None:
    """Seconds from ``ts_b`` to ``ts_a`` (a minus b); ``None`` if unparseable."""
    def _parse(v):
        if isinstance(v, (int, float)):
            s = float(v)
            return s / 1000.0 if s > 1e12 else s
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            return None
    a, b = _parse(ts_a), _parse(ts_b)
    if a is None or b is None:
        return None
    return round(a - b, 3)


def vision_health(hub_snapshot: dict, *, orderflow: dict | None = None) -> dict:
    """The nightly VISION HEALTH line: agreement, latency, reliability, orderflow.

    Reads the hub's own snapshot (its per-source last tick, reliability scores and
    counters) and the orderflow digest. Reports the agreement rate between sources,
    the latency per source when the hub measured one, and the reliability over time.
    A reading the hub did not produce is honestly absent.
    """
    snap = hub_snapshot or {}
    rel = snap.get("reliability") or {}
    lat = snap.get("latency_ms") or {}
    clean, dirty = snap.get("clean_ticks"), snap.get("dirty_ticks")
    agree = None
    if isinstance(clean, (int, float)) and isinstance(dirty, (int, float)):
        total = clean + dirty
        agree = round(clean / total, 4) if total else None
    of = orderflow or {}
    return {
        "sources_active": snap.get("sources_active"),
        "ticks_per_second": snap.get("ticks_per_second"),
        "agreement_rate": agree,
        "latency_ms": dict(sorted(lat.items())) if isinstance(lat, dict) else {},
        "reliability": dict(sorted(rel.items())) if isinstance(rel, dict) else {},
        "orderflow": of.get("reading"),
        "bursts_total": of.get("bursts_total"),
        "reading": (f"vista: {snap.get('sources_active')} fonti a "
                    f"{snap.get('ticks_per_second')} tick/s; accordo "
                    f"{agree if agree is not None else 'non misurato'}"
                    + (f"; {of.get('reading')}" if of.get("reading") else "")),
    }
