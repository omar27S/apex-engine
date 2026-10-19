"""E7 -- THE WORLD RADAR: the world's blood as a continuous sensor.

First Amendment, doctrine E7. The state follows the news of ALL currencies and
watches the orderflow of ALL pairs -- the world's blood as a continuous sensor.
The OBJECTIVE is fixed now; the realization grows with the data.

* RESEARCH phase (now): orderflow PROXIES (spread/volume imbalance from the tapes
  the state already holds) and the extended macro calendar. No live feed is
  invented; a proxy is named a proxy.
* LIVE phase (later): real feeds (news, tick orderflow) -- a data acquisition, not
  a code change here.

The radar is a READING surface, never a trade surface: it may inform context
(the study-pair firewall's permissive half), it may never place a trade.

Pure at import (Scar #6): the currency roster is DERIVED from the Constellation;
the calendar is data; the functions reduce the readings the caller supplies.
"""

from __future__ import annotations

from app.core.constellation import CONSTELLATION_PAIRS

__all__ = [
    "ALL_CURRENCIES",
    "MACRO_CALENDAR",
    "ORDERFLOW_PROXY_FEATURES",
    "PROXIES",
    "LIVE_SOURCES",
    "radar_plan",
    "orderflow_proxy",
    "world_radar_report",
]


def _currencies() -> tuple[str, ...]:
    """Every currency the state follows -- DERIVED from the Constellation.

    Never hand-listed (Scar #3): the roster grows with the pairs. This is the
    'news of all currencies' surface: 15 currencies across the 30 pairs.
    """
    seen: set[str] = set()
    for pair in CONSTELLATION_PAIRS:
        seen.add(pair[:3])
        seen.add(pair[3:])
    return tuple(sorted(seen))


ALL_CURRENCIES: tuple[str, ...] = _currencies()

# The extended macro calendar (research phase): the scheduled events that move the
# currencies the state follows. Data, not code -- extended as the calendar grows.
MACRO_CALENDAR: tuple[dict, ...] = (
    {"event": "central_bank_rate_decision", "currencies": ("USD", "EUR", "GBP", "JPY"),
     "impact": "high"},
    {"event": "cpi_inflation", "currencies": ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD"),
     "impact": "high"},
    {"event": "nonfarm_payrolls", "currencies": ("USD",), "impact": "high"},
    {"event": "gdp", "currencies": ("USD", "EUR", "GBP", "JPY", "CHF"), "impact": "medium"},
    {"event": "pmi", "currencies": ("EUR", "GBP", "SEK", "NOK"), "impact": "medium"},
)

# The orderflow PROXY features the research phase reads from the tapes already
# held (never a fabricated live feed): a proxy is named a proxy.
ORDERFLOW_PROXY_FEATURES: tuple[str, ...] = (
    "volume_imbalance", "spread_proxy", "range_to_volume", "tick_velocity_proxy",
)

# Where each radar surface stands: research (proxies) vs live (real feeds).
PROXIES: tuple[str, ...] = ("orderflow_proxy", "extended_macro_calendar")
LIVE_SOURCES: tuple[str, ...] = ("news_feed", "tick_orderflow")


def radar_plan() -> dict:
    """The World Radar's plan: the fixed objective and the growing realization."""
    return {
        "doctrine": "E7 the World Radar: news of all currencies + orderflow of all pairs",
        "objective": "the world's blood as a continuous sensor",
        "phase": "research",
        "research": {
            "orderflow_proxy_features": list(ORDERFLOW_PROXY_FEATURES),
            "macro_calendar_events": [e["event"] for e in MACRO_CALENDAR],
        },
        "live": {"planned_sources": list(LIVE_SOURCES)},
        "currencies_followed": list(ALL_CURRENCIES),
        "role": "READING surface only; may inform context, never place a trade",
    }


def orderflow_proxy(*, volume_imbalance: float, range_to_volume: float) -> dict:
    """A research-phase orderflow reading from tape-derived proxies (E7).

    This is explicitly a PROXY: it is derived from the volume/range the state
    already holds, not from a live tick feed. The reading is human-form (E5): a
    graded lean, not a hard buy/sell bit.
    """
    from app.state.human_logic import graded

    if range_to_volume < 0:
        raise ValueError("range_to_volume must be non-negative (fail-closed)")
    # A proxy lean: positive imbalance -> buying pressure. The gradient replaces a
    # hard threshold (E5).
    lean = graded(volume_imbalance, x0=0.0, k=2.0)
    return {
        "proxy": True,
        "volume_imbalance": float(volume_imbalance),
        "range_to_volume": float(range_to_volume),
        "lean_score": lean["score"],
        "lean_label": lean["label"],
        "reading": f"proxy lean: {lean['reading']}",
    }


def world_radar_report(*, readings: list[dict] | None = None) -> dict:
    """The World Radar's standing report (E7)."""
    readings = readings or []
    return {
        "doctrine": "E7 the World Radar",
        "currencies_followed": len(ALL_CURRENCIES),
        "macro_events": len(MACRO_CALENDAR),
        "proxy_features": len(ORDERFLOW_PROXY_FEATURES),
        "phase": "research",
        "live_sources_planned": len(LIVE_SOURCES),
        "readings_this_night": len(readings),
        "reading": (f"{len(ALL_CURRENCIES)} currencies, {len(MACRO_CALENDAR)} macro "
                    f"events, {len(ORDERFLOW_PROXY_FEATURES)} orderflow proxies "
                    f"(research phase; live feeds are a later acquisition)"),
    }
