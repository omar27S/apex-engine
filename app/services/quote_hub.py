"""THE HAWK'S EYE -- the live-market, multi-source QUOTE HUB (Part Two, Step 1).

The civilization opens its eyes on the market. This module is the honest STEP 1:
a MULTI-SOURCE QUOTE HUB that connects to free real-time feeds, keeps the last
state of every source, CROSS-VALIDATES them, and feeds a FLOW PROCESSOR that reads
each clean tick as it arrives (the river, not the batch).

Honesty (binding):
  * NO TRADES from live data yet. This is research: the signals come from the
    tapes; live is for the radar, the sensors, the learning. The CEO decides when
    live-readiness becomes live-trading.
  * A DIRTY TICK NEVER FEEDS ANYTHING. When two sources disagree beyond tolerance,
    the tick is flagged and the source's reliability score DROPS (fail-closed).
  * Rate-limit honesty: the hub stays within the free feeds' caps politely and the
    Letter reports the ACHIEVED velocity, never a hoped-for one.

Pure at import (Scar #6): the hub is a state object the caller drives; no socket is
opened at import. The real network loops live in ``tools/hawk_eye.py`` (VM service).
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "HUB_VERSION",
    "FREE_SOURCES",
    "DEFAULT_TOLERANCE_PIPS",
    "QuoteHub",
    "cross_validate",
    "FlowProcessor",
]

HUB_VERSION: int = 1

# The free, keyless-or-freely-authenticated sources the hub may use. Each is a
# WEBSOCKET/stream endpoint (or a documented free REST poll). The hub degrades
# gracefully: a source that is down simply reports inactive (never a false tick).
FREE_SOURCES: tuple[dict, ...] = (
    {"name": "oanda_v20_stream",
     "url": "wss://stream-fxpractice.oanda.com/v3/accounts/{account}/pricing/stream",
     "auth": "token", "kind": "websocket",
     "note": "OANDA v20 practice stream; free with a practice account token"},
    {"name": "polygon_forex_ws",
     "url": "wss://socket.polygon.io/forex",
     "auth": "apikey", "kind": "websocket",
     "note": "Polygon.io forex websocket; free tier with an API key"},
    {"name": "twelvedata_ws",
     "url": "wss://ws.twelvedata.com/v1/quotes/price",
     "auth": "apikey", "kind": "websocket",
     "note": "TwelveData price websocket; free tier"},
)

# Cross-validation tolerance: two sources agree on a pair within this many pips or
# the tick is DIRTY. A pip here is 1e-4 for a 5-digit FX pair (honest default).
DEFAULT_TOLERANCE_PIPS: float = 1.5


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cross_validate(quotes: list[dict], *, tolerance_pips: float = DEFAULT_TOLERANCE_PIPS,
                   pip: float = 1e-4) -> dict:
    """CROSS-VALIDATE the latest bid of each source for ONE pair.

    ``quotes`` is ``[{"source", "pair", "bid"}, ...]``. When 2+ sources agree within
    ``tolerance_pips`` the tick is CLEAN and the median bid is the accepted price.
    A source beyond tolerance is flagged and its name returned in ``divergent`` so
    the caller can DROP its reliability score. Fail-closed: fewer than two sources,
    or no agreement, means DIRTY -- nothing feeds.
    """
    bids = [q for q in quotes if isinstance(q.get("bid"), (int, float))]
    if len(bids) < 2:
        return {"clean": False, "price": None, "divergent": [q.get("source") for q in bids],
                "reason": "meno di due fonti con un prezzo: non validabile (fail-closed)",
                "reading": "tick sporco: serve una seconda fonte"}
    vals = sorted(float(q["bid"]) for q in bids)
    median = vals[len(vals) // 2]
    tol = float(tolerance_pips) * float(pip)
    divergent = [q.get("source") for q in bids
                 if abs(float(q["bid"]) - median) > tol]
    # a clean tick needs a MAJORITY of sources in agreement: at most n-2 outliers
    # (with two sources that means both must agree -- fail-closed).
    clean = len(divergent) <= len(bids) - 2
    return {
        "clean": clean,
        "price": (median if clean else None),
        "divergent": divergent,
        "tolerance": tol,
        "n_sources": len(bids),
        "reason": ("" if clean else "nessuna maggioranza entro la tolleranza"),
        "reading": (f"tick {'pulito' if clean else 'sporco'}: {len(bids)-len(divergent)}"
                    f"/{len(bids)} fonti d'accordo a {median}"),
    }


class QuoteHub:
    """The hub's STATE (the caller drives it; the sockets live in tools/hawk_eye.py).

    Keeps the last tick of every source, a per-source reliability score, the tick
    counter (for the ACHIEVED velocity) and the last accepted price per pair. A
    divergent source LOSES reliability (fail-closed); an agreeing source regains a
    little, slowly.
    """

    def __init__(self, *, tolerance_pips: float = DEFAULT_TOLERANCE_PIPS) -> None:
        self.tolerance_pips = float(tolerance_pips)
        self.last: dict[str, dict] = {}        # source -> last tick
        self.reliability: dict[str, float] = {}  # source -> [0,1]
        self.latency_ms: dict[str, float] = {}   # source -> last measured latency
        self.ticks_received: int = 0
        self.clean_ticks: int = 0
        self.dirty_ticks: int = 0
        self.accepted: dict[str, float] = {}    # pair -> last accepted price
        self.started_ts: str | None = None
        self.last_ts: str | None = None

    def start(self, ts: str = "") -> None:
        self.started_ts = ts or _now()

    def ingest(self, tick: dict, *, latency_ms: float | None = None) -> dict:
        """Take ONE tick from a source and return the cross-validation verdict.

        The tick is ``{"source", "pair", "bid"}``. The hub records it, validates it
        against the other sources' latest bids for the same pair, and only an
        ACCEPTED (clean) price enters ``accepted`` -- a dirty tick feeds nothing.
        ``latency_ms`` (the measured transport latency, when the caller has it) is
        recorded per source for the VISION HEALTH line.
        """
        src = tick.get("source")
        pair = tick.get("pair")
        if isinstance(latency_ms, (int, float)):
            self.latency_ms[str(src)] = round(float(latency_ms), 3)
        if not src or not pair or not isinstance(tick.get("bid"), (int, float)):
            self.dirty_ticks += 1
            return {"clean": False, "reason": "tick malformato (fail-closed)"}
        self.ticks_received += 1
        self.last[src] = dict(tick, ts=tick.get("ts") or _now())
        self.reliability.setdefault(src, 1.0)
        self.last_ts = self.last[src]["ts"]
        peers = [t for t in self.last.values() if t.get("pair") == pair]
        verdict = cross_validate(peers, tolerance_pips=self.tolerance_pips)
        if verdict["clean"]:
            self.clean_ticks += 1
            self.accepted[pair] = verdict["price"]
            for s in self.reliability:
                if s not in verdict["divergent"]:
                    self.reliability[s] = round(min(1.0, self.reliability[s] + 0.001), 4)
        else:
            self.dirty_ticks += 1
        for s in verdict["divergent"]:
            self.reliability[s] = round(max(0.0, self.reliability.get(s, 1.0) - 0.05), 4)
        return verdict

    def velocity(self, *, elapsed_s: float) -> dict:
        """The ACHIEVED velocity: ticks received per second, from real counters.

        A single live feed cannot be cross-validated (fail-closed), so its ticks
        never become "clean"; the achieved velocity is therefore measured on the
        ticks the eye actually RECEIVED, and the clean count is reported beside it.
        """
        # A legacy caller may have recorded only the clean/dirty counters; fall back
        # to their sum so the achieved rate is never lost.
        received = self.ticks_received or (self.clean_ticks + self.dirty_ticks)
        tps = (round(received / elapsed_s, 4)
               if elapsed_s and elapsed_s > 0 else None)
        return {"ticks_per_second": tps, "ticks_received": received,
                "clean_ticks": self.clean_ticks,
                "dirty_ticks": self.dirty_ticks,
                "sources_active": len(self.last),
                "reading": (f"{received} tick ricevuti "
                            f"({self.clean_ticks} puliti, {self.dirty_ticks} sporchi), "
                            f"{len(self.last)} fonti attive")}

    def snapshot(self, *, elapsed_s: float = 0.0) -> dict:
        """The hub's durable reading (written by the VM service for the Letter)."""
        return {
            "hub_version": HUB_VERSION,
            "started_ts": self.started_ts,
            "last_ts": self.last_ts,
            "tolerance_pips": self.tolerance_pips,
            "accepted": dict(sorted(self.accepted.items())),
            "reliability": dict(sorted(self.reliability.items())),
            "latency_ms": dict(sorted(self.latency_ms.items())),
            **self.velocity(elapsed_s=elapsed_s),
        }


class FlowProcessor:
    """THE FLOW PROCESSOR -- every clean tick is processed as it ARRIVES.

    The river, not the batch: each accepted tick is (a) compared against the
    episodic memory (similar situations recalled), (b) classified by the regime
    radar, and (c) absorbed into the orderflow pressure reading -- all in-stream.
    The processor is PURE: it holds counters + the last readings, and the heavy
    recall/classification is the caller's (the hub passes what it has).
    """

    def __init__(self) -> None:
        self.processed: int = 0
        self.last_reading: dict | None = None

    def process(self, *, pair: str, price: float, regime: str | None = None,
                recalled: int | None = None, pressure: float | None = None,
                latency_ms: float | None = None) -> dict:
        self.processed += 1
        self.last_reading = {
            "pair": pair, "price": price, "regime": regime,
            "recalled_episodes": recalled, "orderflow_pressure": pressure,
            "latency_ms": latency_ms,
            "reading": (f"{pair}@{price} regime={regime or 'n/d'} "
                        f"episodi={recalled if recalled is not None else 'n/d'} "
                        f"pressione={pressure if pressure is not None else 'n/d'}"),
        }
        return self.last_reading

    def digest(self) -> dict:
        return {"processed": self.processed,
                "last": self.last_reading,
                "reading": (f"{self.processed} tick processati a flusso"
                            if self.processed else "nessun tick processato")}
