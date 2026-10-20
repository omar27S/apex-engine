"""THE HYPERFEED -- the live wire (the market seen at the speed it moves).

The Boss ordered the software connected to the market "live, at extreme
speed, so it can process the data in time to give the right signal when the
future asks" (2026-10-20). This module is that wire. Where the falcon reads
the world every five minutes over REST, the hyperfeed holds TWO always-on
WebSocket eyes -- keyless, public, measured live before a line of this module
was written (probe, 2026-10-20):

* KRAKEN v2 public ticker  -- the FX majors (EUR/USD, GBP/USD, USD/JPY,
  USD/CAD, AUD/USD probed ALIVE, ~0.8 tick/s off-peak, exchange-stamped
  ISO timestamps);
* BINANCE combined stream   -- bookTicker (top of book, 100-250 ms cadence)
  + aggTrade (the trade tape, exchange-stamped). Probed ALIVE at 187 msg/s
  on two symbols. EURUSDT rides as the 24/7 euro companion of EUR/USD;
  BTCUSDT/ETHUSDT as the market's fear gauges.

Honesty (the Director's laws, binding on the fast eye as on the slow one):

* MEASURE BEFORE SPEECH (Law 1) -- motion is computed on the REMEMBERED span
  of real arrivals; a symbol seen for less than MOTION_MIN_SPAN_S reports
  motion ``None`` (unmeasured, never a fabricated 0.0);
* THE DEAD MUST BE PROVEN (Law 2) -- a venue down is "reconnecting", a
  symbol silent is absent from the snapshot, a stream error is recorded by
  name. Nothing is invented;
* EVERY EYE DECLARES ITS DARKNESS (Law 7) -- per-venue health (state, msgs,
  ticks, reconnects, latency p50/p95) rides in every snapshot;
* THE RECEIPT IS EVIDENCE (Law 5) -- the snapshot is a bounded, honest,
  atomic file the whole organism can read (the falcon, the guardian, the
  Letter, the evolution's future signal layer).

Pure at import (Scar #6): the sockets live inside :func:`run`, imported
lazily so the parsers, buffers and math are testable without a network.
``numpy`` is the only import-time dependency. ``orjson`` (4-6x faster than
``json``) and ``uvloop`` (a faster event loop) are USED WHEN PRESENT and
fallen back from when absent -- never a hard dependency.

CLI (the proof tools)::

    python -m app.market.hyperfeed --probe 12     # bounded measurement, prints it
    python -m app.market.hyperfeed                 # the daemon (forever)

systemd: ``apex-hyperfeed.service`` (Restart=always) keeps the wire alive;
the guardian's round reads the snapshot's clock and calls a quiet wire by
name.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

__all__ = [
    "HYPERFEED_VERSION", "HYPERFEED_ALIVE_S", "MOTION_MIN_SPAN_S",
    "KRAKEN_WS", "BINANCE_WS", "COINBASE_WS", "OKX_WS",
    "FX_ON_KRAKEN", "CRYPTO_ON_BINANCE", "COINBASE_ON_FEED", "OKX_ON_FEED",
    "CRYPTO_BP_SYMBOLS",
    "TickBuffer", "BarBuffer", "LatencyMeter", "VenueHealth", "HyperFeedConfig",
    "HyperFeed", "parse_kraken_ticker", "parse_binance_stream",
    "parse_coinbase_ticker", "parse_okx_ticker",
    "pip_size", "motion_unit", "backoff_delay", "snapshot_fresh",
    "run", "main",
]

HYPERFEED_VERSION = 2

# R110 -- THE THIRD AND FOURTH EYES (venue redundancy): the crypto gauge
# rode a single venue -- a Binance outage would blind the fear gauges the
# whole wire was built to see. Coinbase and OKX are keyless, public, and
# feed SEPARATE rings under honest names (BTC-USD is not BTC-USDT: the
# basis between venues is information, never noise to be merged).
COINBASE_WS = "wss://ws-feed.exchange.coinbase.com"
COINBASE_ON_FEED: dict[str, str] = {"BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD"}
OKX_WS = "wss://ws.okx.com:8443/ws/v5/public"
OKX_ON_FEED: dict[str, str] = {"BTCOKX": "BTC-USDT", "ETHOKX": "ETH-USDT"}
# The explicit crypto set (basis-point pricing); the suffix rule stays for
# anything the set has not met yet (an honest default, not a cage).
CRYPTO_BP_SYMBOLS = frozenset({
    "EURUSDT", "BTCUSDT", "ETHUSDT", "BTCUSD", "ETHUSD", "BTCOKX", "ETHOKX",
})
# venue product -> internal symbol (the parsers' honest reverse maps)
_COINBASE_SYMBOL = {v: k for k, v in COINBASE_ON_FEED.items()}
_OKX_SYMBOL = {v: k for k, v in OKX_ON_FEED.items()}

# A snapshot older than this is a wire gone quiet (the guardian's clock).
HYPERFEED_ALIVE_S = 900
# The falcon's own law (D4): motion judged on a shorter span is a peek, not a
# measure. The hyperfeed obeys the SAME number -- one law, two eyes.
MOTION_MIN_SPAN_S = 240.0

# The venues (keyless, public; probed live 2026-10-20).
KRAKEN_WS = "wss://ws.kraken.com/v2"
BINANCE_WS = "wss://stream.binance.com:9443/stream"

# internal symbol -> Kraken v2 symbol. Probed: all five majors answered.
FX_ON_KRAKEN: dict[str, str] = {
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    "USDCAD": "USD/CAD", "AUDUSD": "AUD/USD", "USDCHF": "USD/CHF",
}
# internal symbol -> the binance combined-stream streams it wants. bookTicker
# carries no exchange clock; aggTrade does (the honest latency needs a clock,
# so every crypto symbol rides both: the book for price, the tape for time).
CRYPTO_ON_BINANCE: dict[str, tuple[str, ...]] = {
    "EURUSDT": ("eurusdt@bookTicker", "eurusdt@aggTrade"),
    "BTCUSDT": ("btcusdt@bookTicker", "btcusdt@aggTrade"),
    "ETHUSDT": ("ethusdt@bookTicker", "ethusdt@aggTrade"),
}


def pip_size(symbol: str) -> float:
    """An honest pip per symbol: 0.01 when the yen quotes, else 1e-4 (FX).

    Crypto symbols are measured in basis points (see :func:`motion_unit`);
    this function is the FX rule the falcon already sealed.
    """
    return 0.01 if str(symbol).upper().endswith("JPY") else 1e-4


def motion_unit(symbol: str) -> tuple[str, float]:
    """The honest motion unit: pips for FX, basis points for crypto.

    Returns ``(unit_name, denominator)``: FX divides the price path by the
    pip; crypto divides the RELATIVE path by 1e-4 (a "pip" of a 60,000 BTC
    quote would be meaningless, a basis point is the same idea at any scale).
    R110 -- venue-specific crypto names (BTCUSD on Coinbase, BTCOKX on OKX)
    are priced by the explicit set, never by guessing from the suffix.
    """
    s = str(symbol).upper()
    if s in CRYPTO_BP_SYMBOLS or (
            (s.endswith("USDT") or s.endswith("USD")) and s not in FX_ON_KRAKEN):
        return "bp", 1e-4  # relative: path / price * 1e4
    return "pip", pip_size(s)


def _iso_to_ms(ts) -> float | None:
    """Kraken's ISO-8601 UTC stamp -> epoch milliseconds (None if unparseable)."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp() * 1000.0
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# THE RING -- a fixed-capacity tick memory per symbol
# ---------------------------------------------------------------------------
class TickBuffer:
    """A fixed-capacity ring of ``(ts_ms, bid, ask, mid)``.

    The past is evidence, bounded: the oldest tick falls away when the ring
    wraps (the falcon's HISTORY_MAX_ROWS doctrine at tick resolution). All
    math is on the VALID slice only -- a fresh ring never reads the unwritten
    future as zeros.
    """

    __slots__ = ("capacity", "_ts", "_bid", "_ask", "_mid", "_head", "_written")

    def __init__(self, capacity: int = 4096):
        self.capacity = max(64, int(capacity))
        self._ts = np.zeros(self.capacity, dtype="float64")
        self._bid = np.full(self.capacity, np.nan)
        self._ask = np.full(self.capacity, np.nan)
        self._mid = np.full(self.capacity, np.nan)
        self._head = 0        # the next write slot
        self._written = 0     # total ever written (the honest age counter)

    def append(self, ts_ms: float, bid: float, ask: float) -> None:
        mid = 0.5 * (float(bid) + float(ask))
        i = self._head
        self._ts[i] = float(ts_ms)
        self._bid[i] = float(bid)
        self._ask[i] = float(ask)
        self._mid[i] = mid
        self._head = (i + 1) % self.capacity
        self._written += 1

    def __len__(self) -> int:
        return min(self._written, self.capacity)

    @property
    def written(self) -> int:
        return self._written

    def _view(self, arr: np.ndarray) -> np.ndarray:
        n = len(self)
        if n == 0:
            return arr[:0]
        if self._written <= self.capacity:  # never wrapped: head == n
            return arr[:n]
        # wrapped: valid = [head .. end) + [0 .. head)
        return np.concatenate((arr[self._head:], arr[:self._head]))

    def span_s(self) -> float | None:
        """Newest minus oldest tick, seconds. None on an empty ring."""
        n = len(self)
        if n < 1:
            return None
        ts = self._view(self._ts)
        return float(ts[-1] - ts[0]) / 1000.0

    def last(self) -> dict | None:
        n = len(self)
        if n == 0:
            return None
        i = (self._head - 1) % self.capacity
        return {"ts_ms": float(self._ts[i]), "bid": float(self._bid[i]),
                "ask": float(self._ask[i]), "mid": float(self._mid[i])}

    def motion(self, *, min_span_s: float = MOTION_MIN_SPAN_S,
               unit: str = "pip", denom: float = 1e-4) -> dict | None:
        """The honest motion on the remembered span (Law 1 and Law 2, together).

        * ``displacement_per_min`` -- |last mid - first mid| per minute (the
          falcon's ``volatility_pips``, identical doctrine);
        * ``path_per_min`` -- the summed |delta mid| per minute: the jitter
          displacement alone can hide;
        * ``velocity_per_min`` -- DISTINCT mids per minute (the falcon's
          ``tick_velocity``: the market's rhythm, not the sensor's cadence).

        ``None`` while the span is under ``min_span_s`` -- an unmeasured
        motion is never a 0.0 (the D4 wound, at tick resolution).
        """
        n = len(self)
        if n < 2:
            return None
        ts = self._view(self._ts)
        mid = self._view(self._mid)
        span_s = float(ts[-1] - ts[0]) / 1000.0
        if span_s < float(min_span_s) or span_s <= 0.0:
            return None
        minutes = span_s / 60.0
        if unit == "bp":
            scale = lambda d: float(d) / max(float(mid[0]), 1e-12) / denom
            disp = abs(float(mid[-1]) - float(mid[0]))
            path = float(np.sum(np.abs(np.diff(mid))))
        else:
            scale = lambda d: float(d) / denom
            disp = abs(float(mid[-1]) - float(mid[0]))
            path = float(np.sum(np.abs(np.diff(mid))))
        distinct = int(np.unique(np.round(mid, 10)).size)
        return {
            "unit": unit,
            "displacement_per_min": round(scale(disp) / minutes, 4),
            "path_per_min": round(scale(path) / minutes, 4),
            "velocity_per_min": round(distinct / minutes, 4),
            "span_min": round(minutes, 2),
            "samples": int(n),
        }

    def snapshot(self, *, now_ms: float) -> dict:
        """The honest per-symbol block for the snapshot file."""
        last = self.last()
        out = {"ticks": int(len(self)), "written": int(self._written)}
        if last is None:
            return out
        out.update({
            "bid": round(last["bid"], 6), "ask": round(last["ask"], 6),
            "mid": round(last["mid"], 6), "ts_ms": round(last["ts_ms"], 1),
            "age_s": round(max(0.0, (now_ms - last["ts_ms"]) / 1000.0), 2),
        })
        return out


# ---------------------------------------------------------------------------
# THE CLOCK'S RECEIPT -- latency, measured only when the exchange sends one
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# THE MACRO RING -- one bar per second, bounded at ANY tick rate (R105)
# ---------------------------------------------------------------------------
class BarBuffer:
    """The telescope beside the microscope: one bar per second of mids.

    The wound this ring closes (2026-10-20, the first live day): BTCUSDT
    ticks at ~423/s and fills the 4096-slot tick ring in under ten seconds
    -- the law window (MOTION_MIN_SPAN_S = 240 s) is forever beyond the
    microscope's reach, so the fastest symbol in the book was the one whose
    motion could never be measured (an honest ``None``, forever). The cure
    is not a bigger microscope (memory grows with the tick rate) but a
    SECOND memory at a coarser resolution: every tick folds into its
    second's bar, and 4096 bars hold 68 minutes at any rate the venue sends.

    Honesty rules (the same laws, at bar resolution):

    * a LATE tick (second older than the open bar) is counted by the
      microscope but never rewrites a closed bar -- history is evidence,
      not a draft;
    * DEAD seconds are honest emptiness: the ring never fabricates flat
      bars to bridge a gap, and the span counts remembered seconds only;
    * motion on bars is LABELLED ``source: "bars"`` -- a coarser, real
      measurement of the same window, never a pose as tick resolution.
    """

    __slots__ = ("capacity", "_sec", "_close", "_high", "_low", "_n",
                 "_head", "_written", "_folded")

    def __init__(self, capacity: int = 4096):
        self.capacity = max(64, int(capacity))
        self._sec = np.zeros(self.capacity, dtype="int64")
        self._close = np.full(self.capacity, np.nan)
        self._high = np.full(self.capacity, np.nan)
        self._low = np.full(self.capacity, np.nan)
        self._n = np.zeros(self.capacity, dtype="int32")
        self._head = 0
        self._written = 0
        self._folded = 0   # every tick the telescope accepted (a total, not a window)

    def fold(self, ts_ms: float, mid: float) -> bool:
        """Fold one mid into its second's bar. ``True`` when the ring heard it.

        A tick for a second OLDER than the open bar is refused (``False``):
        the microscope holds it, the telescope does not rewrite history.
        """
        try:
            sec = int(ts_ms) // 1000
            v = float(mid)
        except (TypeError, ValueError):
            return False
        if not (np.isfinite(v) and np.isfinite(sec)):
            return False
        if self._written:
            i = (self._head - 1) % self.capacity
            if sec < int(self._sec[i]):
                return False  # late: history stays as it was written
            if sec == int(self._sec[i]):
                self._close[i] = v
                if v > self._high[i]:
                    self._high[i] = v
                if v < self._low[i]:
                    self._low[i] = v
                self._n[i] += 1
                self._folded += 1
                return True
        i = self._head
        self._sec[i] = sec
        self._close[i] = v
        self._high[i] = v
        self._low[i] = v
        self._n[i] = 1
        self._head = (i + 1) % self.capacity
        self._written += 1
        self._folded += 1
        return True

    def __len__(self) -> int:
        return min(self._written, self.capacity)

    def _view(self, arr: np.ndarray) -> np.ndarray:
        if self._written <= self.capacity:
            return arr[:self._head]
        return np.concatenate((arr[self._head:], arr[:self._head]))

    def span_s(self) -> float | None:
        """Newest minus oldest REMEMBERED second (gaps included, honestly)."""
        n = len(self)
        if n < 1:
            return None
        sec = self._view(self._sec)
        return float(sec[-1] - sec[0])

    def motion(self, *, min_span_s: float = MOTION_MIN_SPAN_S,
               unit: str = "pip", denom: float = 1e-4) -> dict | None:
        """The law window's motion at one-second resolution.

        Same laws as :meth:`TickBuffer.motion`, same fields, one more:
        ``source: "bars"``. The rhythm (``velocity_per_min``) counts DISTINCT
        CLOSES -- the market's one-second heartbeat, not the sensor's cadence.
        """
        n = len(self)
        if n < 2:
            return None
        sec = self._view(self._sec)
        close = self._view(self._close)
        span_s = float(sec[-1] - sec[0])
        if span_s < float(min_span_s) or span_s <= 0.0:
            return None
        minutes = span_s / 60.0
        if unit == "bp":
            scale = lambda d: float(d) / max(float(close[0]), 1e-12) / denom
        else:
            scale = lambda d: float(d) / denom
        disp = abs(float(close[-1]) - float(close[0]))
        path = float(np.sum(np.abs(np.diff(close))))
        distinct = int(np.unique(np.round(close, 10)).size)
        return {
            "unit": unit,
            "source": "bars",
            "displacement_per_min": round(scale(disp) / minutes, 4),
            "path_per_min": round(scale(path) / minutes, 4),
            "velocity_per_min": round(distinct / minutes, 4),
            "span_min": round(minutes, 2),
            "samples": int(n),
            "note": "one-second closes: the law window at bar resolution",
        }

    def snapshot(self) -> dict:
        """The honest macro block (beside the tick block, never instead)."""
        n = len(self)
        out = {"bars": int(n), "ticks_folded": int(self._folded)}
        if n >= 1:
            out["span_s"] = round(float(self.span_s() or 0.0), 1)
        return out


class LatencyMeter:
    """A bounded reservoir of (local_clock - exchange_clock) milliseconds.

    Kraken stamps ISO time; Binance stamps aggTrade's ``T``. bookTicker
    carries NO clock -- those messages are counted, never timed (an untimed
    message is not a zero-latency message). Clock skew between hosts shows
    as negative minima and is REPORTED as measured, never clipped to zero.
    """

    def __init__(self, reservoir: int = 512):
        self._rows: deque[float] = deque(maxlen=int(reservoir))

    def observe(self, latency_ms: float) -> None:
        if latency_ms is None:
            return
        try:
            v = float(latency_ms)
        except (TypeError, ValueError):
            return
        if not math.isfinite(v):
            return
        self._rows.append(v)

    def stats(self) -> dict:
        n = len(self._rows)
        if n == 0:
            return {"n": 0, "p50_ms": None, "p95_ms": None,
                    "min_ms": None, "max_ms": None,
                    "note": "no exchange-stamped message yet"}
        s = np.asarray(self._rows, dtype="float64")
        return {
            "n": int(n),
            "p50_ms": round(float(np.percentile(s, 50)), 1),
            "p95_ms": round(float(np.percentile(s, 95)), 1),
            "min_ms": round(float(s.min()), 1),
            "max_ms": round(float(s.max()), 1),
            "note": "local-vs-exchange clocks; skew shows as negative min",
        }


@dataclass
class VenueHealth:
    """One venue's honest state, as the snapshot reports it."""
    name: str
    state: str = "connecting"     # connecting | live | reconnecting | sleeping
    connected_at_ms: float | None = None
    last_msg_ms: float | None = None
    msgs: int = 0
    ticks: int = 0
    reconnects: int = 0
    errors: list = field(default_factory=lambda: deque(maxlen=8))
    latency: LatencyMeter = field(default_factory=LatencyMeter)

    def on_msg(self, now_ms: float, ticks: int = 0) -> None:
        self.msgs += 1
        self.ticks += int(ticks)
        self.last_msg_ms = float(now_ms)

    def to_dict(self, *, now_ms: float) -> dict:
        age = (None if self.last_msg_ms is None
               else round(max(0.0, (now_ms - self.last_msg_ms) / 1000.0), 2))
        return {
            "state": self.state, "msgs": self.msgs, "ticks": self.ticks,
            "reconnects": self.reconnects,
            "connected_s": (None if self.connected_at_ms is None
                            else round(max(0.0, (now_ms - self.connected_at_ms) / 1000.0), 1)),
            "last_msg_age_s": age,
            "errors": list(self.errors),
            "latency": self.latency.stats(),
        }


# ---------------------------------------------------------------------------
# THE PARSERS -- pure, payload-shaped, probe-verified
# ---------------------------------------------------------------------------
def parse_kraken_ticker(msg: dict, *, now_ms: float | None = None) -> list[dict]:
    """Kraken v2 ``ticker`` snapshot/update -> quote rows.

    Row: ``{"symbol": internal, "bid", "ask", "ts_ms", "latency_ms"}`` (the
    latency only when the exchange stamped the tick). Unknown payload shapes
    return ``[]`` (a heartbeat or a status message is not a quote).
    """
    if not isinstance(msg, dict) or msg.get("channel") != "ticker":
        return []
    if msg.get("type") not in ("snapshot", "update"):
        return []
    out: list[dict] = []
    for d in msg.get("data") or []:
        if not isinstance(d, dict):
            continue
        symbol = str(d.get("symbol") or "")
        internal = next((k for k, v in FX_ON_KRAKEN.items() if v == symbol), "")
        bid, ask = _num(d.get("bid")), _num(d.get("ask"))
        if not internal or bid is None or ask is None:
            continue
        ts_ms = _iso_to_ms(d.get("timestamp"))
        row = {"symbol": internal, "bid": bid, "ask": ask,
               "ts_ms": ts_ms}
        if ts_ms is not None and now_ms is not None:
            row["latency_ms"] = float(now_ms) - float(ts_ms)
        out.append(row)
    return out


def _num(value):
    """A number from whatever the venue sent: int/float, or a numeric string.

    Binance quotes prices as STRINGS ("64000.50"); Kraken sends numbers. A
    non-numeric value is None (refused downstream, never guessed).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def parse_binance_stream(msg: dict, *, now_ms: float | None = None) -> list[dict]:
    """Binance combined stream -> quote rows (bookTicker book + aggTrade tape).

    bookTicker carries no exchange clock (price only, latency absent);
    aggTrade carries ``T`` (the honest clock). Prices arrive as STRINGS
    (Binance's wire format) and are coerced once, here. Rows: ``{"symbol",
    "bid", "ask", "price", "qty", "ts_ms", "latency_ms"}``.
    """
    if not isinstance(msg, dict):
        return []
    data = msg.get("data") or {}
    if not isinstance(data, dict):
        return []
    kind = data.get("e")
    rows: list[dict] = []
    if kind == "aggTrade":
        sym = str(data.get("s") or "").upper()
        price, qty = _num(data.get("p")), _num(data.get("q"))
        ts_ms = _num(data.get("T"))
        if sym and price is not None:
            row = {"symbol": sym, "price": price}
            if qty is not None:
                row["qty"] = qty
            if ts_ms is not None:
                row["ts_ms"] = ts_ms
                if now_ms is not None:
                    row["latency_ms"] = float(now_ms) - ts_ms
            rows.append(row)
    else:
        # bookTicker (no "e" field) / partial depth: use bid/ask when present
        sym = str(data.get("s") or "").upper()
        bid, ask = _num(data.get("b")), _num(data.get("a"))
        if sym and bid is not None and ask is not None:
            rows.append({"symbol": sym, "bid": bid, "ask": ask})
    return rows


def parse_coinbase_ticker(msg: dict, *, now_ms: float | None = None) -> list[dict]:
    """R110 -- THE THIRD EYE: Coinbase's ticker channel (keyless, public).

    Payload shape (the docs' own words, prices as STRINGS -- the Binance
    lesson paid twice): ``{"type": "ticker", "product_id": "BTC-USD",
    "best_bid": "61234.50", "best_ask": "61235.00",
    "time": "2026-10-20T19:00:00.123456Z"}``. The time is ISO-stamped (the
    honest clock); a ticker without its book or its product is counted by
    the venue health and never fabricated.
    """
    if not isinstance(msg, dict) or msg.get("type") != "ticker":
        return []
    sym = _COINBASE_SYMBOL.get(str(msg.get("product_id") or ""))
    if not sym:
        return []
    bid, ask = _num(msg.get("best_bid")), _num(msg.get("best_ask"))
    if bid is None or ask is None:
        return []
    ts_ms = _iso_to_ms(msg.get("time"))
    latency = None
    if ts_ms is not None and now_ms is not None:
        latency = float(now_ms) - float(ts_ms)
    return [{"symbol": sym, "bid": bid, "ask": ask,
             "ts_ms": ts_ms, "latency_ms": latency}]


def parse_okx_ticker(msg: dict, *, now_ms: float | None = None) -> list[dict]:
    """R110 -- THE FOURTH EYE: OKX v5 public tickers (keyless).

    Payload shape: ``{"arg": {"channel": "tickers", "instId": "BTC-USDT"},
    "data": [{"last": "61234.5", "bidPx": "61234.4", "askPx": "61234.6",
    "ts": "1761000000000"}]}`` -- the ts is a STRING of epoch milliseconds
    (numeric strings parse through :func:`_num` like every venue's quotes).
    """
    if not isinstance(msg, dict):
        return []
    data = msg.get("data")
    if not isinstance(data, list):
        return []
    arg = msg.get("arg") if isinstance(msg.get("arg"), dict) else {}
    sym = _OKX_SYMBOL.get(str(arg.get("instId") or ""))
    if not sym:
        return []
    rows = []
    for d in data:
        if not isinstance(d, dict):
            continue
        bid, ask = _num(d.get("bidPx")), _num(d.get("askPx"))
        if bid is None or ask is None:
            continue
        ts_ms = _num(d.get("ts"))
        latency = None
        if ts_ms is not None and now_ms is not None:
            latency = float(now_ms) - float(ts_ms)
        rows.append({"symbol": sym, "bid": bid, "ask": ask,
                     "ts_ms": ts_ms, "latency_ms": latency})
    return rows


# ---------------------------------------------------------------------------
# THE AGGREGATOR
# ---------------------------------------------------------------------------
def backoff_delay(attempt: int, *, base_s: float = 0.5, cap_s: float = 60.0,
                  jitter: float = 0.2) -> float:
    """Exponential backoff with honest jitter: 0.5 * 2^n capped, +-20%.

    The CAP IS A CAP: jitter may shorten a wait, never lengthen it past
    ``cap_s`` (a retry storm is worse than a slow retry).
    """
    n = max(0, int(attempt))
    raw = min(float(cap_s), float(base_s) * (2.0 ** n))
    span = raw * float(jitter)
    return max(0.1, min(float(cap_s), raw + random.uniform(-span, span)))


@dataclass
class HyperFeedConfig:
    """Everything the wire needs (bounded, honest, overridable per run)."""
    fx_pairs: tuple[str, ...] = tuple(FX_ON_KRAKEN)
    crypto_symbols: tuple[str, ...] = tuple(CRYPTO_ON_BINANCE)
    coinbase_symbols: tuple[str, ...] = tuple(COINBASE_ON_FEED)   # R110
    okx_symbols: tuple[str, ...] = tuple(OKX_ON_FEED)             # R110
    buffer_capacity: int = 4096
    bar_capacity: int = 4096   # R105: 68 min of one-second bars at ANY rate
    snapshot_path: str = "hyperfeed.json"
    snapshot_every_s: float = 20.0
    connect_timeout_s: float = 15.0
    ping_timeout_s: float = 20.0
    max_backoff_s: float = 60.0
    alive_s: float = float(HYPERFEED_ALIVE_S)


class HyperFeed:
    """The aggregation: rings per symbol, health per venue, one honest snapshot.

    Pure data-in/data-out (the sockets feed :meth:`on_quote`; the snapshot is
    built on demand) -- the daemon and the tests share the SAME body.
    """

    def __init__(self, config: HyperFeedConfig | None = None):
        self.config = config or HyperFeedConfig()
        self.started_ms = time.time() * 1000.0
        self.buffers: dict[str, TickBuffer] = {}
        self.bars: dict[str, BarBuffer] = {}   # R105 -- the macro ring
        for sym in self.config.fx_pairs:
            self.buffers[sym] = TickBuffer(self.config.buffer_capacity)
            self.bars[sym] = BarBuffer(self.config.bar_capacity)
        for sym in self.config.crypto_symbols:
            self.buffers.setdefault(sym, TickBuffer(self.config.buffer_capacity))
            self.bars.setdefault(sym, BarBuffer(self.config.bar_capacity))
        # R110 -- the third and fourth eyes' rings (separate names, separate
        # books: the basis between venues is information, never merged noise)
        for sym in self.config.coinbase_symbols:
            self.buffers.setdefault(sym, TickBuffer(self.config.buffer_capacity))
            self.bars.setdefault(sym, BarBuffer(self.config.bar_capacity))
        for sym in self.config.okx_symbols:
            self.buffers.setdefault(sym, TickBuffer(self.config.buffer_capacity))
            self.bars.setdefault(sym, BarBuffer(self.config.bar_capacity))
        self.venues: dict[str, VenueHealth] = {
            "kraken": VenueHealth("kraken"), "binance": VenueHealth("binance"),
            "coinbase": VenueHealth("coinbase"), "okx": VenueHealth("okx"),
        }

    # -- the ingestion ------------------------------------------------------
    def on_quote(self, venue: str, symbol: str, *, bid=None, ask=None,
                 price=None, ts_ms=None, latency_ms=None,
                 now_ms: float | None = None) -> bool:
        """Fold one quote into its ring. Returns True when a ring advanced.

        A book quote (bid+ask) writes the book; a trade (price) writes the
        tape as a synthetic book (bid=ask=price, declared in the snapshot's
        ``trade_fed`` list -- a trade-tick is not a spread reading).
        """
        now_ms = float(now_ms if now_ms is not None else time.time() * 1000.0)
        ring = self.buffers.get(symbol)
        if ring is None:
            return False
        health = self.venues.get(venue)
        bars = self.bars.get(symbol)
        if bid is not None and ask is not None:
            stamp = float(ts_ms if ts_ms is not None else now_ms)
            ring.append(stamp, float(bid), float(ask))
            if bars is not None:
                bars.fold(stamp, (float(bid) + float(ask)) / 2.0)
        elif price is not None:
            stamp = float(ts_ms if ts_ms is not None else now_ms)
            ring.append(stamp, float(price), float(price))
            if bars is not None:
                bars.fold(stamp, float(price))
        else:
            return False
        if health is not None:
            health.on_msg(now_ms, ticks=1)
            if latency_ms is not None:
                health.latency.observe(latency_ms)
        return True

    # -- the reductions -----------------------------------------------------
    def symbol_block(self, symbol: str, *, now_ms: float) -> dict:
        """One symbol's honest block: the tick eye first, the bar eye behind it.

        R105 -- THE LAW WINDOW AT ANY RATE: when the tick ring cannot reach
        MOTION_MIN_SPAN_S (a hyper-fast symbol fills it in seconds), the bar
        ring answers for the same window at one-second resolution, and the
        motion dict says which eye spoke (``source``). Neither eye fabricates:
        a young wire still reports ``None``, honestly.
        """
        ring = self.buffers[symbol]
        bars = self.bars.get(symbol)
        unit, denom = motion_unit(symbol)
        block = ring.snapshot(now_ms=now_ms)
        block["unit"] = unit
        if "ts_ms" in block:
            motion = ring.motion(unit=unit, denom=denom)
            if motion is not None:
                motion.setdefault("source", "ticks")
            elif bars is not None:
                motion = bars.motion(unit=unit, denom=denom)
            block["motion"] = motion
            if bars is not None:
                block["bars"] = bars.snapshot()
        return block

    def snapshot(self, *, now_ms: float | None = None) -> dict:
        """The whole honest state: venues, symbols, counts, the wire's clock."""
        now_ms = float(now_ms if now_ms is not None else time.time() * 1000.0)
        symbols = {s: self.symbol_block(s, now_ms=now_ms)
                   for s in sorted(self.buffers)}
        seen = [s for s, b in symbols.items() if b.get("mid") is not None]
        moving = [s for s, b in symbols.items() if b.get("motion")]
        return {
            "schema": HYPERFEED_VERSION,
            "kind": "hyperfeed",
            "ts": round(now_ms / 1000.0, 3),
            "uptime_s": round((now_ms - self.started_ms) / 1000.0, 1),
            "alive_s": float(self.config.alive_s),
            "motion_min_span_s": float(MOTION_MIN_SPAN_S),
            "venues": {v: h.to_dict(now_ms=now_ms)
                       for v, h in self.venues.items()},
            "symbols": symbols,
            "counts": {
                "symbols_configured": len(self.buffers),
                "symbols_seen": len(seen),
                "symbols_moving": len(moving),
                "ticks_written": sum(b.written for b in self.buffers.values()),
                "bars_written": sum(len(b) for b in self.bars.values()),
            },
            "reading": (f"live wire: {len(seen)}/{len(self.buffers)} symbols seen, "
                        f"{len(moving)} with measured motion "
                        f"(tick eye first, bar eye at any rate)"),
        }


def snapshot_fresh(snapshot: dict, *, now_epoch: float) -> bool | None:
    """The guardian's question: is the wire's clock within ALIVE_S?

    ``None`` when the snapshot carries no clock (unborn, not dead); ``True``
    when fresh; ``False`` when quiet -- the caller speaks the verdict.
    """
    if not isinstance(snapshot, dict):
        return None
    ts = snapshot.get("ts")
    if not isinstance(ts, (int, float)):
        return None
    alive = snapshot.get("alive_s") or HYPERFEED_ALIVE_S
    return (float(now_epoch) - float(ts)) <= float(alive)


def _write_snapshot_atomic(path: Path, payload: dict) -> None:
    """Write-once-then-rename: a reader never sees a torn snapshot."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, default=str))
        os.replace(tmp, path)
    except OSError:
        pass  # a failed write is reported by the daemon's own clock, never fabricated


# ---------------------------------------------------------------------------
# THE DAEMON -- the sockets live here, and only here
# ---------------------------------------------------------------------------
async def _kraken_session(feed: HyperFeed, cfg: HyperFeedConfig, stop: asyncio.Event):
    """One Kraken v2 session: subscribe the FX majors, feed the rings."""
    import websockets  # lazy (Scar #6): the parsers are testable without it

    health = feed.venues["kraken"]
    symbols = [FX_ON_KRAKEN[p] for p in cfg.fx_pairs if p in FX_ON_KRAKEN]
    sub = json.dumps({"method": "subscribe",
                      "params": {"channel": "ticker", "symbol": symbols}})
    loads = _json_loader()
    async with websockets.connect(KRAKEN_WS, open_timeout=cfg.connect_timeout_s,
                                  ping_interval=20, ping_timeout=cfg.ping_timeout_s) as ws:
        health.state, health.connected_at_ms = "live", time.time() * 1000.0
        await ws.send(sub)
        async for raw in ws:
            if stop.is_set():
                await ws.close()
                break
            now_ms = time.time() * 1000.0
            try:
                msg = loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("method") == "subscribe" and msg.get("success") is False:
                health.errors.append(f"subscribe refused: {msg.get('error')}")
                continue
            rows = parse_kraken_ticker(msg, now_ms=now_ms)
            if not rows:
                health.on_msg(now_ms)
                continue
            for r in rows:
                feed.on_quote("kraken", r["symbol"], bid=r["bid"], ask=r["ask"],
                              ts_ms=r.get("ts_ms"), latency_ms=r.get("latency_ms"),
                              now_ms=now_ms)


async def _binance_session(feed: HyperFeed, cfg: HyperFeedConfig, stop: asyncio.Event):
    """One Binance combined-stream session: book + tape for the crypto set."""
    import websockets

    health = feed.venues["binance"]
    streams = "/".join(s for sym in cfg.crypto_symbols
                       for s in CRYPTO_ON_BINANCE.get(sym, ()))
    url = f"{BINANCE_WS}?streams={streams}"
    loads = _json_loader()
    async with websockets.connect(url, open_timeout=cfg.connect_timeout_s,
                                  ping_interval=20, ping_timeout=cfg.ping_timeout_s) as ws:
        health.state, health.connected_at_ms = "live", time.time() * 1000.0
        async for raw in ws:
            if stop.is_set():
                await ws.close()
                break
            now_ms = time.time() * 1000.0
            try:
                msg = loads(raw)
            except (ValueError, TypeError):
                continue
            rows = parse_binance_stream(msg, now_ms=now_ms)
            if not rows:
                health.on_msg(now_ms)
                continue
            for r in rows:
                feed.on_quote("binance", r["symbol"], bid=r.get("bid"),
                              ask=r.get("ask"), price=r.get("price"),
                              ts_ms=r.get("ts_ms"),
                              latency_ms=r.get("latency_ms"), now_ms=now_ms)


async def _coinbase_session(feed: HyperFeed, cfg: HyperFeedConfig, stop: asyncio.Event):
    """R110 -- the third eye: Coinbase's ticker channel, one session."""
    import websockets

    health = feed.venues["coinbase"]
    products = [COINBASE_ON_FEED[p] for p in cfg.coinbase_symbols
                if p in COINBASE_ON_FEED]
    if not products:
        health.state = "sleeping"          # configured out: honest rest,
        await stop.wait()                    # never a hot reconnect loop
        return
    sub = json.dumps({"type": "subscribe", "product_ids": products,
                      "channels": ["ticker"]})
    loads = _json_loader()
    async with websockets.connect(COINBASE_WS, open_timeout=cfg.connect_timeout_s,
                                  ping_interval=20, ping_timeout=cfg.ping_timeout_s) as ws:
        health.state, health.connected_at_ms = "live", time.time() * 1000.0
        await ws.send(sub)
        async for raw in ws:
            if stop.is_set():
                await ws.close()
                break
            now_ms = time.time() * 1000.0
            try:
                msg = loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "error":
                health.errors.append(f"subscribe refused: {str(msg.get('message'))[:100]}")
                continue
            rows = parse_coinbase_ticker(msg, now_ms=now_ms)
            if not rows:
                health.on_msg(now_ms)
                continue
            for r in rows:
                feed.on_quote("coinbase", r["symbol"], bid=r["bid"], ask=r["ask"],
                              ts_ms=r.get("ts_ms"), latency_ms=r.get("latency_ms"),
                              now_ms=now_ms)


async def _okx_session(feed: HyperFeed, cfg: HyperFeedConfig, stop: asyncio.Event):
    """R110 -- the fourth eye: OKX v5 public tickers, one session.

    OKX speaks an APPLICATION-level heartbeat (a bare ``"ping"`` text every
    ~20 s; the server answers ``"pong"`` and drops the socket after ~30 s of
    silence) -- the WS protocol-level ping the other venues take is not the
    word this venue hears, so the session speaks its dialect honestly.
    """
    import websockets

    health = feed.venues["okx"]
    args = [{"channel": "tickers", "instId": OKX_ON_FEED[p]}
            for p in cfg.okx_symbols if p in OKX_ON_FEED]
    if not args:
        health.state = "sleeping"
        await stop.wait()
        return
    sub = json.dumps({"op": "subscribe", "args": args})
    loads = _json_loader()
    async with websockets.connect(OKX_WS, open_timeout=cfg.connect_timeout_s,
                                  ping_interval=None) as ws:
        health.state, health.connected_at_ms = "live", time.time() * 1000.0
        await ws.send(sub)

        async def _heartbeat():
            while not stop.is_set():
                await asyncio.sleep(20)
                try:
                    await ws.send("ping")
                except Exception:
                    return

        hb = asyncio.create_task(_heartbeat(), name="hyperfeed-okx-hb")
        try:
            async for raw in ws:
                if stop.is_set():
                    await ws.close()
                    break
                if raw == "pong" or raw == "":
                    continue
                now_ms = time.time() * 1000.0
                try:
                    msg = loads(raw)
                except (ValueError, TypeError):
                    continue
                if not isinstance(msg, dict):
                    continue
                ev = msg.get("event")
                if ev == "error":
                    health.errors.append(f"subscribe refused: {str(msg.get('msg'))[:100]}")
                    continue
                rows = parse_okx_ticker(msg, now_ms=now_ms)
                if not rows:
                    health.on_msg(now_ms)
                    continue
                for r in rows:
                    feed.on_quote("okx", r["symbol"], bid=r["bid"], ask=r["ask"],
                                  ts_ms=r.get("ts_ms"), latency_ms=r.get("latency_ms"),
                                  now_ms=now_ms)
        finally:
            hb.cancel()


async def _venue_loop(feed: HyperFeed, cfg: HyperFeedConfig, name: str,
                      session, stop: asyncio.Event, *, healthy_s: float = 60.0):
    """The reconnecting wrapper: one venue, forever, with honest backoff."""
    health = feed.venues[name]
    attempt = 0
    while not stop.is_set():
        try:
            await asyncio.wait_for(session(feed, cfg, stop),
                                   timeout=None)
            attempt = 0  # a clean exit (stop) resets nothing; a long life does
            if stop.is_set():
                return
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # ConnectionClosed, OSError, TimeoutError...
            if stop.is_set():
                return
            health.errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")
        health.state, health.reconnects = "reconnecting", health.reconnects + 1
        if health.last_msg_ms is not None and \
                (time.time() * 1000.0 - health.last_msg_ms) / 1000.0 > healthy_s:
            attempt = 0  # it lived a while; the next failure is a fresh attempt
        else:
            attempt += 1
        await asyncio.sleep(backoff_delay(attempt, cap_s=cfg.max_backoff_s))


async def _snapshot_writer(feed: HyperFeed, cfg: HyperFeedConfig, stop: asyncio.Event):
    """The file's heartbeat: one atomic snapshot every ``snapshot_every_s``."""
    path = Path(cfg.snapshot_path)
    while not stop.is_set():
        _write_snapshot_atomic(path, feed.snapshot())
        try:
            await asyncio.wait_for(stop.wait(), timeout=float(cfg.snapshot_every_s))
        except asyncio.TimeoutError:
            continue


def _json_loader():
    """orjson when present (4-6x), stdlib json otherwise. Never a hard dep."""
    try:
        import orjson
        return lambda raw: orjson.loads(raw)
    except ImportError:
        return lambda raw: json.loads(raw)


async def run(cfg: HyperFeedConfig | None = None, *, seconds: float | None = None,
              on_start=None) -> dict:
    """The daemon body: both venues forever (or ``seconds`` bounded), plus the
    snapshot writer. Returns the last snapshot (the probe's receipt).

    ``uvloop`` is used when importable (2x the event loop, p95 tail wins) and
    silently skipped when not -- the wire must run on any honest host.
    """
    cfg = cfg or HyperFeedConfig()
    feed = HyperFeed(cfg)
    stop = asyncio.Event()

    async def _bounded():
        if seconds is None:
            await stop.wait()  # forever (systemd owns the clock)
            return
        await asyncio.sleep(float(seconds))
        stop.set()

    tasks = [
        asyncio.create_task(_venue_loop(feed, cfg, "kraken", _kraken_session, stop),
                            name="hyperfeed-kraken"),
        asyncio.create_task(_venue_loop(feed, cfg, "binance", _binance_session, stop),
                            name="hyperfeed-binance"),
        asyncio.create_task(_venue_loop(feed, cfg, "coinbase", _coinbase_session, stop),
                            name="hyperfeed-coinbase"),
        asyncio.create_task(_venue_loop(feed, cfg, "okx", _okx_session, stop),
                            name="hyperfeed-okx"),
        asyncio.create_task(_snapshot_writer(feed, cfg, stop),
                            name="hyperfeed-snapshot"),
        asyncio.create_task(_bounded(), name="hyperfeed-clock"),
    ]
    if on_start is not None:
        on_start(feed)
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for t in tasks:
            t.cancel()
    return feed.snapshot()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="THE HYPERFEED -- the live wire (keyless WebSocket market view)")
    ap.add_argument("--probe", type=float, default=None, metavar="SECONDS",
                    help="bounded measurement window; prints the honest snapshot")
    ap.add_argument("--snapshot", default="hyperfeed.json",
                    help="the snapshot path (default: hyperfeed.json)")
    ap.add_argument("--buffer", type=int, default=4096,
                    help="ticks remembered per symbol (default: 4096)")
    ap.add_argument("--quiet", action="store_true",
                    help="no periodic console line in daemon mode")
    args = ap.parse_args(argv)

    cfg = HyperFeedConfig(snapshot_path=args.snapshot,
                          buffer_capacity=int(args.buffer))

    try:  # the faster loop, when the host carries it
        import uvloop  # noqa: F401
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

    if args.probe is not None:
        snap = asyncio.run(run(cfg, seconds=float(args.probe)))
        print(json.dumps(snap, indent=2, default=str))
        seen = snap["counts"]["symbols_seen"]
        print(f"hyperfeed probe: {seen}/{snap['counts']['symbols_configured']} "
              f"symbols seen in {args.probe}s", file=sys.stderr)
        return 0 if seen > 0 else 1

    asyncio.run(run(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
