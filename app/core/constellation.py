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

PAIR_GALAXY: dict[str, tuple[str, ...]] = {
    "majors": MAJOR_PAIRS,
    "core_crosses": CORE_CROSS_PAIRS,
}

CONSTELLATION_PAIRS: tuple[str, ...] = MAJOR_PAIRS + CORE_CROSS_PAIRS
