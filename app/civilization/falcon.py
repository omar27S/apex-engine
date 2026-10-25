"""THE FALCON -- the LIVING NAVIGATOR (the hawk elevated: eyes that RULE the flow).

The hawk was a passive watcher; the FALCON is the civilization's navigator. It owns
MULTIPLE EYES (free, keyless sources), a per-source health monitor, the MACRO RADAR
(DXY, WTI, US10Y, VIX seen LIVE), and COMMAND POWERS over the river:

  * PAIR SELECTION BY HEAT -- it ranks the pairs by live activity and picks the
    hottest for the next micro-tournament (evolution hunts where the prey moves);
  * REGIME FLAGGING -- a live regime per pair (trending/ranging/volatile/dead) so a
    tournament knows WHAT KIND of market it evolves for;
  * THE OPPORTUNITY SIREN -- an extraordinary reading fires a siren into the
    interbrain (the Council may convene; the Dragon may direct an emergency micro);
  * THE ORDERFLOW ENGINE -- aggression patterns, the cumulative session delta, the
    spread compass, and microstructure events cross-referenced with what followed;
  * THE FALCON'S MEMORY -- the tick history is a searchable archive ("when was the
    last time EURUSD moved this fast during London?").

Honesty is binding. A dead source is "la fonte X dorme", NEVER a fabricated tick. A
pair with no measured reading is NEVER selected by invented heat. An unmeasured
regime is ``None``. The falcon INFORMS and DIRECTS the search; it holds NO
execute/trade/veto surface -- the Council stays sovereign (the Ten Laws).

Pure at import (Scar #6): every reduction here takes the data it is given; the real
sockets/HTTP live in ``tools/falcon.py`` (the VM service).
"""

from __future__ import annotations

__all__ = [
    "FALCON_VERSION",
    "SOURCES",
    "WIRED_SOURCES",
    "MACRO_RADAR",
    "REGIMES",
    "SIREN_KINDS",
    "HEALTH_ALIVE_S",
    "HISTORY_MAX_ROWS",
    "HISTORY_MAX_AGE_S",
    "MOTION_MIN_SPAN_S",
    "pip_size",
    "merge_history",
    "window_motion",
    "DEAD_PRICE_SOURCES",
    "wire_revives_dead_pairs",
    "health_from_readings",
    "source_health",
    "source_health_report",
    "macro_radar",
    "pair_heat",
    "select_hot_pairs",
    "regime_flag",
    "regime_flags",
    "detect_siren",
    "fire_siren",
    "aggression_pattern",
    "cumulative_session_delta",
    "spread_compass",
    "detect_microstructure_events",
    "cross_reference_events",
    "archive_tick",
    "search_memory",
    "live_wire_block",
    "falcon_summary",
    "falcon_block",
]

FALCON_VERSION: int = 1

# A source silent this long is SLEEPING (honest, never a false tick). 15 minutes.
HEALTH_ALIVE_S: int = 900

# THE FALCON'S MEMORY (D4, 2026-10-20). The service reads every 5 minutes, so
# HISTORY_MAX_ROWS points per pair is ~2 hours of honest window; a point older
# than HISTORY_MAX_AGE_S falls away (the memory is bounded, the file never grows
# without end). MOTION_MIN_SPAN_S is the shortest window the motion is measured
# on: two samples 30 seconds apart say nothing about a market that ticks once a
# minute -- the old falcon measured its own sampling cadence and called frozen
# feeds "dead" for a rounding hair (the wound is numbered, D4).
HISTORY_MAX_ROWS: int = 24
HISTORY_MAX_AGE_S: float = 2.0 * 24.0 * 3600.0
MOTION_MIN_SPAN_S: float = 240.0


def pip_size(pair: str) -> float:
    """An honest pip per pair: 0.01 when the yen quotes, else 0.0001."""
    return 0.01 if str(pair).upper().endswith("JPY") else 1e-4

# The free, keyless-or-free-tier sources the falcon may open. Each carries its own
# reliability and its own fail-closed behaviour. ``keyless`` sources need no key.
SOURCES: tuple[dict, ...] = (
    {"name": "kraken_public", "kind": "websocket", "keyless": True,
     "covers": ("fx",), "note": "Kraken public ws; real FX majors, no key"},
    {"name": "binance_public", "kind": "websocket", "keyless": True,
     "covers": ("crypto", "context"),
     "note": "Binance public ws; BTC/ETH as the fear gauge of all markets"},
    {"name": "yahoo_finance", "kind": "rest", "keyless": True,
     "covers": ("macro", "futures", "indices"),
     "note": "Yahoo chart JSON; DXY/WTI/US10Y/VIX + CME futures context"},
    {"name": "twelvedata", "kind": "websocket", "keyless": False,
     "covers": ("fx",), "note": "TwelveData free tier; throttled"},
    {"name": "polygon_forex", "kind": "websocket", "keyless": False,
     "covers": ("fx",), "note": "Polygon forex ws; free tier"},
    {"name": "oanda_v20", "kind": "websocket", "keyless": False,
     "covers": ("fx",), "note": "OANDA v20 practice stream"},
    {"name": "ecb_sdw", "kind": "rest", "keyless": True,
     "covers": ("rates",), "note": "ECB Data Portal; MRO + deposit-facility policy rates "
                                "(probed live 2026-10-20: keyless JSON answers)"},
    {"name": "frankfurter_ecb", "kind": "rest", "keyless": True,
     "covers": ("fx",), "note": "Frankfurter (ECB reference FX); keyless majors"},
    {"name": "fred", "kind": "rest", "keyless": False,
     "covers": ("rates", "macro"), "note": "FRED; free key; FED funds + yields"},
    {"name": "fear_greed", "kind": "rest", "keyless": True,
     "covers": ("sentiment",), "note": "Fear & Greed Index; free JSON"},
    {"name": "reddit_public", "kind": "rest", "keyless": True,
     "covers": ("sentiment",), "note": "r/Forex + r/Trading public JSON; read-only "
                                "(probed 2026-10-20: 403 from the datacenter -- sleeps honestly, "
                                "the reader stays wired for the day it opens)"},
    {"name": "stocktwits_public", "kind": "rest", "keyless": True,
     "covers": ("sentiment",), "note": "StockTwits public feed; read-only "
                                 "(probed 2026-10-20: 403 -- sleeps honestly, wired for the day it opens)"},
    {"name": "hyperfeed", "kind": "file", "keyless": True,
     "covers": ("fx", "crypto", "ticks"),
     "note": "THE LIVE WIRE: the hyperfeed daemon's snapshot (WebSocket "
             "top-of-book at millisecond cadence, keyless). The falcon "
             "reads its file; the wire owns the speed, the falcon the meaning"},
)

# DEBT-064: the sources main actually reads today (a real reader feeds them).
# Every other declared source is honestly "declared but not wired" -- reported,
# never assumed alive.  D4 (2026-10-20): the eye grows from five to EIGHT wired
# sources -- ecb_sdw (policy rates, probed live), reddit_public and
# stocktwits_public (sentiment; both answer 403 from this datacenter today,
# so they sleep wired -- an honest "dorme", never a fabricated post).
WIRED_SOURCES: frozenset[str] = frozenset({
    "kraken_public", "frankfurter_ecb", "binance_public", "yahoo_finance",
    "fear_greed", "ecb_sdw", "reddit_public", "stocktwits_public",
    "hyperfeed",
})

# --- THE LIVE WIRE (the hyperfeed's snapshot, honestly read) ---------------

# R116 -- the sources whose price is a DAILY table, not a market: when the
# wire has a live quote for a pair these sources fed, the wire wins (a
# synthetic cross at WebSocket speed beats a reference rate published once
# a day; both are honest, but only one of them is ALIVE).
DEAD_PRICE_SOURCES: frozenset[str] = frozenset({"frankfurter_ecb", "ecb_sdw"})


def wire_revives_dead_pairs(prices: dict, motion: dict, snapshot: dict, *,
                            now_epoch: float,
                            max_age_s: float = float(HEALTH_ALIVE_S)
                            ) -> tuple[dict, dict]:
    """R116 -- the live wire revives the pairs the dead sources fed (pure).

    EURGBP, EURJPY, EURCHF and EURCAD rode Frankfurter's ECB table for the
    falcon's whole life: one quote a day, ``volatility_pips: 0.0`` -- a
    corpse's calm, not the market's. From R111 the wire derives those very
    crosses live from Kraken's legs; this function lets the wire's reading
    REPLACE a dead-source pair's price (and carry its MEASURED motion, the
    unit declared), while a pair a live source already feeds is left alone
    (the wire does not evict a witness that is awake). A sleeping wire
    changes nothing -- the falcon keeps its honest fallback.

    Returns ``(prices, motion)`` patched copies; never mutates the inputs.
    """
    prices = dict(prices or {})
    motion = dict(motion or {})
    if not isinstance(snapshot, dict):
        return prices, motion
    ts = snapshot.get("ts")
    if not isinstance(ts, (int, float)):
        return prices, motion
    if float(now_epoch) - float(ts) > max_age_s:
        return prices, motion           # the wire sleeps: nothing is invented
    syms = snapshot.get("symbols") or {}
    from datetime import datetime, timezone as _tz

    def _iso(ts_ms: float) -> str:
        try:
            return datetime.fromtimestamp(float(ts_ms) / 1000.0, _tz.utc
                                          ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError, OSError, OverflowError):
            return ""

    for sym, blk in syms.items():
        if not isinstance(blk, dict) or blk.get("mid") is None:
            continue
        age = blk.get("age_s")
        if not isinstance(age, (int, float)) or float(age) > max_age_s:
            continue                     # a stale symbol is not a reading
        cur = prices.get(sym) or {}
        cur_source = str(cur.get("source") or "")
        if sym in prices and cur_source not in DEAD_PRICE_SOURCES:
            continue                     # a live witness is never evicted
        row = {"price": float(blk["mid"]),
               "ts": _iso(blk.get("ts_ms") or ts * 1000.0),
               "source": "hyperfeed_wire"}
        syn = blk.get("synthetic")
        if isinstance(syn, dict):
            row["synthetic"] = {"legs": syn.get("legs"),
                                "op": syn.get("op")}
        prices[sym] = row
        m = blk.get("motion")
        if isinstance(m, dict) and isinstance(m.get("displacement_per_min"),
                                              (int, float)):
            motion[sym] = {
                "volatility_pips": float(m["displacement_per_min"]),
                "tick_velocity": float(m.get("velocity_per_min") or 0.0),
                "window_min": float(m.get("span_min") or 0.0),
                "samples": int(m.get("samples") or 0),
                "source": f"hyperfeed_wire:{m.get('source', 'ticks')}",
            }
    return prices, motion


def live_wire_block(snapshot: dict, *, now_epoch: float) -> dict:
    """The live wire's reading, age-gated and unit-declared (pure).

    ``snapshot`` is the hyperfeed daemon's file (``app.market.hyperfeed``).
    The block carries only what the wire MEASURED: per symbol the last
    bid/ask/mid with its age, and the motion computed on the wire's own
    remembered span (pips per minute for FX, basis points for crypto -- the
    unit rides in the block, never assumed). A wire older than
    :data:`HEALTH_ALIVE_S` is SLEEPING ("il filo dorme") and its symbols
    are empty -- a stale snapshot is history, not sight. An unparseable or
    absent snapshot is ``non misurato``. Never a fabricated tick.
    """
    if not isinstance(snapshot, dict):
        return {"state": "non misurato", "symbols": {}, "venues": {},
                "reading": "il filo vivo non ha scritto"}
    ts = snapshot.get("ts")
    if not isinstance(ts, (int, float)):
        return {"state": "non misurato", "symbols": {}, "venues": {},
                "reading": "il filo vivo non ha l'ora"}
    age_s = max(0.0, float(now_epoch) - float(ts))
    venues = {}
    for name, h in (snapshot.get("venues") or {}).items():
        venues[name] = {"state": h.get("state"),
                        "ticks": h.get("ticks"),
                        "reconnects": h.get("reconnects"),
                        "latency": (h.get("latency") or {}).get("p50_ms")}
    if age_s > HEALTH_ALIVE_S:
        return {"state": "sleeping", "age_s": round(age_s, 1),
                "symbols": {}, "venues": venues,
                "reading": f"il filo vivo dorme ({int(age_s / 60)} min)"}
    symbols = {}
    for sym, blk in (snapshot.get("symbols") or {}).items():
        if not isinstance(blk, dict) or blk.get("mid") is None:
            continue
        row = {"bid": blk.get("bid"), "ask": blk.get("ask"),
               "mid": blk.get("mid"), "unit": blk.get("unit"),
               "age_s": blk.get("age_s"), "ticks": blk.get("ticks")}
        motion = blk.get("motion")
        if isinstance(motion, dict):
            row["motion_per_min"] = motion.get("displacement_per_min")
            row["path_per_min"] = motion.get("path_per_min")
            row["velocity_per_min"] = motion.get("velocity_per_min")
            row["motion_span_min"] = motion.get("span_min")
        else:
            row["motion_per_min"] = None  # unmeasured below the min span, never 0.0
        symbols[sym] = row
    counts = snapshot.get("counts") or {}
    moving = counts.get("symbols_moving") or 0
    return {
        "state": "alive", "age_s": round(age_s, 1),
        "symbols": symbols, "venues": venues,
        "reading": (f"filo vivo: {len(symbols)} simboli visti, {moving} in moto "
                    f"(WS, cadenza ms)"),
    }


# THE MACRO RADAR (Law 9 instruments, finally SEEN live). Each maps a Yahoo symbol
# unless it names another wired reader: the ECB policy pair (ECB_MRO, ECB_DFR)
# comes from the ECB Data Portal (ecb_sdw), not Yahoo -- a reader that cannot
# serve an axis simply leaves it unseen (never a fabricated level).
MACRO_RADAR: tuple[dict, ...] = (
    {"name": "DXY", "yahoo": "DX-Y.NYB", "what": "the dollar index (the tide)"},
    {"name": "WTI", "yahoo": "CL=F", "what": "crude (the inflation pulse)"},
    {"name": "US10Y", "yahoo": "^TNX", "what": "the 10-year yield (the discount rate)"},
    {"name": "VIX", "yahoo": "^VIX", "what": "the fear gauge"},
    {"name": "ECB_MRO", "provider": "ecb_sdw",
     "what": "the ECB main refinancing rate (the price of money)"},
    {"name": "ECB_DFR", "provider": "ecb_sdw",
     "what": "the ECB deposit facility rate (the ceiling of rates)"},
)

# The four live regimes a pair can be in.
REGIMES: tuple[str, ...] = ("trending", "ranging", "volatile", "dead")

# The extraordinary readings that fire the siren.
SIREN_KINDS: tuple[str, ...] = ("volatility_burst", "flash_move",
                                "spread_anomaly", "macro_breakout")

# --- THE FALCON'S MEMORY (the readings history -- the honest motion) ---------


def merge_history(history: dict, prices: dict, *, now_epoch: float,
                  max_rows: int = HISTORY_MAX_ROWS,
                  max_age_s: float = HISTORY_MAX_AGE_S) -> dict:
    """Fold one reading pass into the per-pair price history (pure, bounded).

    ``history`` maps ``pair -> [{ts, price, source}, ...]`` in time order;
    ``prices`` is this pass's ``{pair: {"price", "source"?, ...}}``. Each pair's
    new point is APPENDED (a same-epoch point replaces its predecessor, so the
    turn's two samples stay two, not a stutter). Points older than ``max_age_s``
    are dropped and each pair keeps at most ``max_rows`` points. A pair absent
    from ``prices`` keeps its history (an absent reading is not a deletion); a
    pair with an empty history disappears (never a ghost row). Pure: no clocks,
    no sockets -- ``now_epoch`` is given.
    """
    out: dict = {}
    for pair, rows in (history or {}).items():
        kept = [r for r in (rows or [])
                if isinstance(r, dict) and isinstance(r.get("price"), (int, float))
                and float(now_epoch) - float(r.get("ts") or 0.0) <= max_age_s]
        if kept:
            out[pair] = kept[-max_rows:]
    for pair, r in (prices or {}).items():
        price = (r or {}).get("price")
        if not isinstance(price, (int, float)):
            continue
        point = {"ts": float(now_epoch), "price": float(price),
                 "source": (r or {}).get("source") or "unknown"}
        rows = out.setdefault(pair, [])
        if rows and rows[-1]["ts"] == point["ts"]:
            rows[-1] = point  # a same-epoch pass replaces, it does not stutter
        else:
            rows.append(point)
        out[pair] = rows[-max_rows:]
    return out


def window_motion(history: dict, *, now_epoch: float = 0.0,
                  min_span_s: float = MOTION_MIN_SPAN_S) -> dict:
    """The honest motion per pair, measured on the WHOLE remembered window.

    For each pair with at least two points spanning ``>= min_span_s``:

    * ``volatility_pips`` -- pips moved across the window, per minute
      (|last - first| / pip / minutes); a slow feed that ticks once every
      few passes finally shows its TRUE motion instead of a frozen 0.0;
    * ``tick_velocity`` -- DISTINCT prices seen per minute: the market's own
      update rhythm, not the sensor's sampling cadence (the old value was
      ``60/seconds`` -- identical for every pair by construction, a measure
      of the method, not of the market);
    * ``window_min`` / ``samples`` / ``source`` -- the window's honest size,
      how many points carried it, and which feed served the latest price.

    A pair with too short a window is ABSENT (unmeasured, never fabricated).
    Pure: the history is given, the clock is given.
    """
    out: dict = {}
    for pair, rows in (history or {}).items():
        pts = [r for r in (rows or [])
               if isinstance(r, dict) and isinstance(r.get("price"), (int, float))]
        if len(pts) < 2:
            continue
        first, last = pts[0], pts[-1]
        span = float(last["ts"]) - float(first["ts"])
        if span < float(min_span_s):
            continue
        minutes = max(span / 60.0, 1e-9)
        pips = abs(float(last["price"]) - float(first["price"])) / pip_size(pair)
        distinct = len({round(float(p["price"]), 10) for p in pts})
        out[pair] = {
            "volatility_pips": round(pips / minutes, 3),
            "tick_velocity": round(distinct / minutes, 4),
            "window_min": round(minutes, 1),
            "samples": len(pts),
            "source": last.get("source") or "unknown",
        }
    return out


# --- the per-source HEALTH MONITOR ------------------------------------------


def health_from_readings(source: dict, *, now_epoch: float) -> dict:
    """One source's health: alive / sleeping / unmeasured, from its last reading.

    ``source`` carries ``{name, last_ts_epoch, reliability}``. A source with no
    reading is ``non misurato`` (never assumed alive). A reading older than
    :data:`HEALTH_ALIVE_S` is SLEEPING -- "la fonte X dorme", never a false tick.
    """
    last = source.get("last_ts_epoch")
    rel = source.get("reliability")
    if last is None:
        state = "non misurato"
        age = None
    else:
        age = max(0.0, float(now_epoch) - float(last))
        state = "alive" if age <= HEALTH_ALIVE_S else "sleeping"
    wired = source.get("wired")
    if wired is None:
        wired = source.get("name") in WIRED_SOURCES
    return {"name": source.get("name"), "state": state, "age_s": age,
            "reliability": rel if isinstance(rel, (int, float)) else None,
            "wired": bool(wired)}


def source_health(readings: dict, *, now_epoch: float) -> dict:
    """The health of every configured source (honest, per-source).

    ``readings`` maps a source name to its last reading ``{last_ts_epoch,
    reliability, wired}``. A configured source with no reading is ``non
    misurato``. DEBT-064: a declared source that no reader ever feeds carries
    ``wired: False`` and is reported separately in ``not_wired`` -- an honest
    "declared but not wired" reading, distinct from a wired source that is merely
    silent (never a fabricated tick).
    """
    rows = [health_from_readings({"name": s["name"], **(readings.get(s["name"]) or {})},
                                 now_epoch=now_epoch)
            for s in SOURCES]
    alive = sum(1 for r in rows if r["state"] == "alive")
    sleeping = sum(1 for r in rows if r["state"] == "sleeping")
    unmeasured = sum(1 for r in rows if r["state"] == "non misurato")
    not_wired = [r["name"] for r in rows if r.get("wired") is False]
    return {"rows": rows, "alive": alive, "sleeping": sleeping,
            "unmeasured": unmeasured, "not_wired": not_wired, "n": len(rows)}


def source_health_report(readings: dict, *, now_epoch: float) -> dict:
    """The health reading: how many eyes are open, and which are sleeping."""
    h = source_health(readings, now_epoch=now_epoch)
    sleeping = [r["name"] for r in h["rows"] if r["state"] == "sleeping"]
    return {**h, "sleeping_sources": sleeping,
            "reading": (f"falco: {h['alive']}/{h['n']} fonti sveglie"
                        + (f", dormono: {', '.join(sleeping)}" if sleeping else "")
                        + (f", {h['unmeasured']} non misurate" if h["unmeasured"] else "")
                        + (f" ({len(h['not_wired'])} non cablate)"
                           if h["not_wired"] else ""))}


# --- THE MACRO RADAR ---------------------------------------------------------


def macro_radar(readings: dict) -> dict:
    """The macro radar: DXY, WTI, US10Y, VIX as LIVE sensors.

    ``readings`` maps a radar name to its latest ``{value, prev, ts}``. An axis with
    no reading is honest ``None`` -- the system says "non visto", never a fake level.
    """
    rows: list[dict] = []
    for m in MACRO_RADAR:
        r = readings.get(m["name"]) or {}
        val = r.get("value")
        prev = r.get("prev")
        change = (val - prev) if isinstance(val, (int, float)) and isinstance(prev, (int, float)) else None
        rows.append({"name": m["name"], "what": m["what"], "value": val if isinstance(val, (int, float)) else None,
                     "change": change, "ts": r.get("ts"), "seen": val is not None})
    seen = sum(1 for r in rows if r["seen"])
    return {"rows": rows, "seen": seen, "n": len(rows),
            "reading": (f"radar macro: {seen}/{len(rows)} strumenti visti"
                        + ("" if seen == len(rows) else " (il resto non visto)"))}


# --- PAIR SELECTION BY HEAT --------------------------------------------------


def pair_heat(reading: dict) -> float | None:
    """A pair's LIVE HEAT: tick velocity + volatility + orderflow energy, normalised.

    Returns ``None`` when the reading is unmeasured (no fabricated heat). The heat is
    a bounded 0..1 blend so no single axis dominates.
    """
    vel = reading.get("tick_velocity")
    vol = reading.get("volatility_pips")
    ofe = reading.get("orderflow_energy")
    if vel is None and vol is None and ofe is None:
        return None
    v = min(1.0, float(vel or 0.0) / 30.0)          # 30 ticks/min saturates
    s = min(1.0, float(vol or 0.0) / 20.0)          # 20 pips/min saturates
    o = min(1.0, abs(float(ofe or 0.0)) / 100.0)    # +-100 delta saturates
    return round(0.4 * v + 0.35 * s + 0.25 * o, 4)


def select_hot_pairs(readings: dict, *, n: int = 3, min_heat: float = 0.0) -> dict:
    """Rank the pairs by live heat and SELECT the hottest ``n`` (the hunt's prey).

    Honest: a pair whose heat is unmeasured is EXCLUDED (never selected on invented
    heat). Ties break by name for determinism.
    """
    scored = [(p, pair_heat(r)) for p, r in (readings or {}).items()]
    measured = [(p, h) for p, h in scored if h is not None and h >= min_heat]
    ranked = sorted(measured, key=lambda t: (-t[1], t[0]))
    chosen = [p for p, _ in ranked[:max(1, int(n))]]
    return {"chosen": chosen, "ranked": [{"pair": p, "heat": h} for p, h in ranked],
            "measured": len(measured), "n_pairs": len(readings or {}),
            "reading": (f"falco sceglie: {', '.join(chosen)}" if chosen
                        else "falco: nessuna coppia calda misurata")}


# --- REGIME FLAGGING ---------------------------------------------------------


def regime_flag(reading: dict) -> dict:
    """A pair's LIVE REGIME: trending / ranging / volatile / dead (or unmeasured).

    The rule (deterministic, from the MEASURED MOTION -- pips per minute -- never
    from the sensor's sampling cadence):
      * no measured motion (no volatility, no session delta) -> ``None`` (unmeasured);
      * a frozen pair (< 0.2 pips/min and no session delta) -> ``dead``;
      * a burst (>= 20 pips/min) -> ``volatile``;
      * a sustained one-sided push (>= 6 pips/min, or a big session delta) ->
        ``trending``;
      * otherwise (the quiet breathing of the majors) -> ``ranging``.

    ``tick_velocity`` is the SENSOR's cadence (samples per minute), not the
    market's motion: the old < 2.0 knife-edge sat exactly on the falcon's REST
    cadence (60/30.x ~ 1.97) and called every real reading "dead" for a rounding
    hair -- the cathedral collapsed on a lie (Law 10).
    """
    vol = reading.get("volatility_pips")
    delta = reading.get("session_delta")
    if vol is None and delta is None:
        return {"pair": reading.get("pair"), "regime": None,
                "reading": "regime non misurato"}
    vol = float(vol or 0.0)
    if vol < 0.2 and (delta is None or abs(float(delta)) < 40.0):
        regime = "dead"
    elif vol >= 20.0:
        regime = "volatile"
    elif vol >= 6.0 or (delta is not None and abs(float(delta)) >= 40.0):
        regime = "trending"
    else:
        regime = "ranging"
    return {"pair": reading.get("pair"), "regime": regime,
            "reading": f"{reading.get('pair')}: regime {regime}"}


def regime_flags(readings: dict) -> dict:
    """The live regime of every pair, with a count per regime (honest)."""
    rows = [regime_flag({"pair": p, **(r or {})}) for p, r in (readings or {}).items()]
    counts = {g: sum(1 for r in rows if r["regime"] == g) for g in REGIMES}
    unmeasured = sum(1 for r in rows if r["regime"] is None)
    return {"rows": rows, "counts": counts, "unmeasured": unmeasured,
            "reading": (", ".join(f"{g} {n}" for g, n in counts.items() if n)
                        or "nessun regime misurato")}


# --- THE OPPORTUNITY SIREN ---------------------------------------------------


def detect_siren(readings: dict, *, baseline: dict | None = None) -> dict | None:
    """Detect an extraordinary reading and return the siren (or ``None``).

    Fires on: a volatility burst, a flash move, a spread anomaly, or a macro asset
    breaking out. Honest: only a MEASURED breach fires; an unmeasured axis is silent.
    """
    baseline = baseline or {}
    for pair, r in (readings or {}).items():
        r = r or {}
        vol = r.get("volatility_pips")
        bvol = (baseline.get(pair) or {}).get("volatility_pips")
        if isinstance(vol, (int, float)) and isinstance(bvol, (int, float)) and bvol > 0 \
                and vol >= 3.0 * bvol:
            return {"kind": "volatility_burst", "pair": pair, "value": vol,
                    "baseline": bvol,
                    "reading": f"SIRENA: burst di volatilita su {pair} ({vol:.1f} vs {bvol:.1f})"}
        spread = r.get("spread_pips")
        bspread = (baseline.get(pair) or {}).get("spread_pips")
        if isinstance(spread, (int, float)) and isinstance(bspread, (int, float)) \
                and bspread > 0 and spread >= 3.0 * bspread:
            return {"kind": "spread_anomaly", "pair": pair, "value": spread,
                    "baseline": bspread,
                    "reading": f"SIRENA: spread anomalo su {pair} ({spread:.1f} vs {bspread:.1f})"}
    macro = readings.get("__macro__") or {}
    for name, m in macro.items():
        m = m or {}
        ch = m.get("change")
        base = m.get("value")
        if isinstance(ch, (int, float)) and isinstance(base, (int, float)) and base != 0 \
                and abs(ch) >= 0.02 * abs(base):
            return {"kind": "macro_breakout", "pair": name, "value": ch,
                    "baseline": base,
                    "reading": f"SIRENA: {name} rompe (variazione {ch:+.2f})"}
    return None


def fire_siren(state: dict, siren: dict, *, ts: str = "") -> dict:
    """Fire the siren into the interbrain (the Council may convene on it).

    Records the siren in the state and posts an ``IL MONDO DICE``-style alarm to the
    interbrain. It INFORMS; it does not command a session (the Council decides).
    """
    row = {"ts": ts, **siren}
    state.setdefault("sirens", []).append(row)
    del state["sirens"][:-200]
    state.setdefault("interbrain", []).append(
        {"author": "falcon", "idea": "SIRENA: " + str(siren.get("reading", "")),
         "kind": "discovery", "ts": ts, "status": "open",
         # R163 — THE DIGESTION: born with its closing condition written —
         # an idea without one is noise with good calligraphy.
         "closes_on": ("a newer shift on the same subject, the field's "
                       "verdict, or fourteen unanswered days (the silence "
                       "is the verdict)")})
    return row


# --- THE ORDERFLOW ENGINE ----------------------------------------------------


def aggression_pattern(ticks: list[dict]) -> dict:
    """Classify the AGGRESSION PATTERN from a tick sequence (who attacks whom).

    ``ticks`` is ``[{"side": "buy"|"sell", "size": n}, ...]`` in time order. Returns
    the pattern: buyers lifting offers, sellers hitting bids, or balanced -- with the
    dominant side's share. Honest: no ticks -> ``balanced`` with ``measured=False``.
    """
    buy = sum(float(t.get("size") or 0.0) for t in (ticks or []) if t.get("side") == "buy")
    sell = sum(float(t.get("size") or 0.0) for t in (ticks or []) if t.get("side") == "sell")
    total = buy + sell
    if total <= 0:
        return {"pattern": "balanced", "buy": buy, "sell": sell, "share": None,
                "measured": False, "reading": "aggressione non misurata"}
    share = buy / total
    if share >= 0.65:
        pat = "buyers_lifting"
    elif share <= 0.35:
        pat = "sellers_hitting"
    else:
        pat = "balanced"
    return {"pattern": pat, "buy": buy, "sell": sell, "share": round(share, 4),
            "measured": True,
            "reading": f"aggressione: {pat} ({share:.0%} compratori)"}


def cumulative_session_delta(ticks: list[dict], *, session: str = "") -> dict:
    """The CUMULATIVE SESSION DELTA: who has dominated this session.

    Sums signed size (buy +, sell -). Honest: no ticks -> ``None`` (unmeasured).
    """
    if not ticks:
        return {"session": session, "delta": None, "measured": False,
                "reading": "delta di sessione non misurato"}
    delta = sum((1.0 if t.get("side") == "buy" else -1.0) * float(t.get("size") or 0.0)
                for t in ticks)
    who = "compratori" if delta > 0 else ("venditori" if delta < 0 else "nessuno")
    return {"session": session, "delta": round(delta, 2), "measured": True,
            "reading": (f"delta di sessione ({session or 'n/d'}): {delta:+.0f}, "
                        f"dominano i {who}")}


def spread_compass(readings: dict) -> dict:
    """The SPREAD COMPASS: per-pair spread expansion/contraction (fear/greed).

    ``readings`` maps pair -> ``{spread_pips, spread_baseline}``. Honest: an
    unmeasured pair is skipped.
    """
    rows: list[dict] = []
    for pair, r in (readings or {}).items():
        r = r or {}
        s = r.get("spread_pips")
        b = r.get("spread_baseline")
        if not isinstance(s, (int, float)) or not isinstance(b, (int, float)) or b <= 0:
            continue
        ratio = s / b
        state = "expanding" if ratio >= 1.3 else ("contracting" if ratio <= 0.75 else "steady")
        rows.append({"pair": pair, "spread_pips": s, "ratio": round(ratio, 3),
                     "state": state})
    expanding = [r["pair"] for r in rows if r["state"] == "expanding"]
    return {"rows": rows, "expanding": expanding,
            "reading": (f"bussola spread: {len(rows)} coppie misurate"
                        + (f", in espansione: {', '.join(expanding)}" if expanding else ""))}


def detect_microstructure_events(readings: dict, *, baseline: dict | None = None) -> list[dict]:
    """Detect unusual microstructure events (spread blowout, tick burst, thin wall).

    Each event is a small dict ``{kind, pair, value, ts}``. Honest: only a MEASURED
    breach is logged; an unmeasured axis is silent.
    """
    baseline = baseline or {}
    events: list[dict] = []
    for pair, r in (readings or {}).items():
        r = r or {}
        b = baseline.get(pair) or {}
        s, bs = r.get("spread_pips"), b.get("spread_pips")
        if isinstance(s, (int, float)) and isinstance(bs, (int, float)) and bs > 0 and s >= 4.0 * bs:
            events.append({"kind": "spread_blowout", "pair": pair, "value": s,
                           "ts": r.get("ts")})
        v, bv = r.get("tick_velocity"), b.get("tick_velocity")
        if isinstance(v, (int, float)) and isinstance(bv, (int, float)) and bv > 0 and v >= 4.0 * bv:
            events.append({"kind": "tick_burst", "pair": pair, "value": v,
                           "ts": r.get("ts")})
        if r.get("dom_thin") is True:
            events.append({"kind": "liquidity_vacuum", "pair": pair, "value": None,
                           "ts": r.get("ts")})
    return events


def cross_reference_events(events: list[dict], subsequent: dict) -> list[dict]:
    """Cross-reference each micro event with WHAT FOLLOWED (the falcon LEARNS).

    ``subsequent`` maps ``(pair, kind)`` -> the observed outcome ``{move_pips, ...}``.
    Returns the events annotated with their outcome (or ``None`` if unseen yet).
    """
    out: list[dict] = []
    for e in (events or []):
        outcome = (subsequent or {}).get((e.get("pair"), e.get("kind")))
        out.append({**e, "outcome": outcome,
                    "learned": outcome is not None})
    return out


# --- THE FALCON'S MEMORY -----------------------------------------------------


def archive_tick(memory: list[dict], *, pair: str, ts: str, price: float | None,
                 velocity: float | None = None, session: str = "",
                 max_rows: int = 5000) -> dict:
    """Append one tick to the falcon's searchable memory (bounded)."""
    row = {"pair": str(pair), "ts": str(ts), "price": price,
           "velocity": velocity, "session": str(session)}
    memory.append(row)
    del memory[:-max_rows]
    return row


def search_memory(memory: list[dict], *, pair: str | None = None,
                  session: str | None = None, min_velocity: float | None = None) -> list[dict]:
    """Search the tick archive -- the déjà-vu for LIVE data.

    "When was the last time EURUSD moved this fast during London?" is
    ``search_memory(mem, pair="EURUSD", session="london", min_velocity=15)``.
    """
    hits = [r for r in (memory or [])
            if (pair is None or r.get("pair") == pair)
            and (session is None or r.get("session") == session)
            and (min_velocity is None or (isinstance(r.get("velocity"), (int, float))
                                          and r["velocity"] >= min_velocity))]
    return hits


# --- THE FALCON BLOCK (for the state artifact + the Letter) ------------------


def falcon_summary(state: dict, *, now_epoch: float = 0.0) -> dict:
    """The falcon's summary for the unified state artifact + the Letter.

    Reduces the falcon's live section (readings, macro, health, regimes) into the
    numbers the CEO asked for: ticks, sources active, regime flags.
    """
    f = (state or {}).get("falcon") or {}
    readings = f.get("readings") or {}
    health = source_health_report(f.get("sources") or {}, now_epoch=now_epoch)
    regimes = regime_flags(readings)
    macro = macro_radar(f.get("macro") or {})
    ticks = f.get("ticks")
    # D4 -- the honest motion census: how many pairs carry a MEASURED window
    # (volatility from the remembered history, not from one 30-second peek).
    motion_measured = sum(1 for r in readings.values()
                          if isinstance(r or {}, dict)
                          and isinstance((r or {}).get("volatility_pips"), (int, float)))
    return {
        "ticks": ticks if isinstance(ticks, (int, float)) else None,
        "sources_active": health["alive"],
        "sources_total": health["n"],
        "sleeping_sources": health["sleeping_sources"],
        "macro_seen": macro["seen"],
        "regimes": regimes["counts"],
        "regime_unmeasured": regimes["unmeasured"],
        "motion_measured": motion_measured,
        "reading": (f"falco: {ticks if ticks is not None else '--'} tick, "
                    f"{health['alive']}/{health['n']} fonti sveglie, "
                    f"{macro['seen']}/{macro['n']} strumenti macro"
                    + (f", {motion_measured} coppie col moto misurato"
                       if motion_measured else "")),
    }


def falcon_block(state: dict, *, now_epoch: float = 0.0) -> dict:
    """The falcon's block for the Letter: the summary + the radar + the diary."""
    f = (state or {}).get("falcon") or {}
    summary = falcon_summary(state, now_epoch=now_epoch)
    summary["macro"] = macro_radar(f.get("macro") or {})
    summary["regimes_detail"] = regime_flags(f.get("readings") or {})
    summary["hot_pairs"] = select_hot_pairs(f.get("readings") or {})
    diary = ((state or {}).get("market_diary") or {})
    summary["diary"] = diary.get("entries", [])[-1:] if isinstance(diary, dict) else []
    return summary
