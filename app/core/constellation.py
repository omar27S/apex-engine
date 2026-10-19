"""THE CONSTELLATION MEMBERSHIP — the single list of the 15 tradable pairs.

This module holds the *membership* only (no constants, no gates), so it sits at
the bottom of the import graph: ``pairs`` and ``rate_oracle`` both read it and
neither has to import the other. The sealed pip conventions stay in
``pairs.py``; the sealed laws stay in ``law.py``.
"""

from __future__ import annotations

MAJOR_PAIRS: tuple[str, ...] = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
)

CORE_CROSS_PAIRS: tuple[str, ...] = (
    "EURGBP",
    "EURJPY",
    "GBPJPY",
    "EURCHF",
    "EURAUD",
    "AUDJPY",
    "CADJPY",
    "NZDJPY",
)

# THE EXPANSION (Founding Charter, act 2 / R92 volume law). The state grows the
# Constellation from 15 to 30 pairs to reach 5 distinct trades/week worst-window.
# These are the 15 crosses from the Phase 7p roster study (scandies, EM exotics,
# and Antipodean crosses) — all non-JPY, so pip size follows the standard rule.
EXPANDED_CROSS_PAIRS: tuple[str, ...] = (
    "USDSEK",
    "USDNOK",
    "USDMXN",
    "USDZAR",
    "EURSEK",
    "EURNOK",
    "EURPLN",
    "EURHUF",
    "EURCZK",
    "GBPSEK",
    "AUDNZD",
    "AUDCAD",
    "AUDCHF",
    "NZDCAD",
    "NZDCHF",
)

PAIR_GALAXY: dict[str, tuple[str, ...]] = {
    "majors": MAJOR_PAIRS,
    "core_crosses": CORE_CROSS_PAIRS,
    "expanded_crosses": EXPANDED_CROSS_PAIRS,
}

# THE STUDY-PAIR FIREWALL (Founding Charter, CEO ruling): trades are proposed ONLY
# on the 15 operational pairs (majors + core crosses). The 15 expanded crosses are
# SENSORS ONLY — data sources, macro context, cross-confirmation. They are read,
# never traded, never evolution targets. The split is defined here, at the bottom
# of the import graph, so every gate reads ONE source. See app.state.firewall.
OPERATIONAL_PAIRS: tuple[str, ...] = MAJOR_PAIRS + CORE_CROSS_PAIRS
STUDY_PAIRS: tuple[str, ...] = EXPANDED_CROSS_PAIRS

# The full roster — every tape the state ACQUIRES and STUDIES (30).
CONSTELLATION_PAIRS: tuple[str, ...] = OPERATIONAL_PAIRS + STUDY_PAIRS
