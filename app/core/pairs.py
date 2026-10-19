"""THE CONSTELLATION — the only 15 pairs APEX will ever trade.

Membership and normalization are delegated to :func:`law.normalize_pair`; this
module only defines the universe. Nothing outside the Constellation is tradable.

Pip sizes are computed from a single convention constant, never a hard-coded
per-pair table.
"""

from __future__ import annotations

from app.core.constellation import (
    CONSTELLATION_PAIRS,
    CORE_CROSS_PAIRS,
    EXPANDED_CROSS_PAIRS,
    MAJOR_PAIRS,
    PAIR_GALAXY as _MEMBERSHIP_GALAXY,
)
from app.core.law import normalize_pair

# Re-exported for callers; membership is defined once in app.core.constellation.
MAJORS = MAJOR_PAIRS
CORE_CROSSES = CORE_CROSS_PAIRS
EXPANDED_CROSSES = EXPANDED_CROSS_PAIRS

# Single pip convention: JPY quotes use two decimals, everything else four.
PIP_STANDARD = 0.0001
PIP_JPY = 0.01


def is_jpy_pair(pair: str) -> bool:
    """True iff the canonical pair has JPY as its quote currency."""
    canonical = normalize_pair(pair)
    return canonical is not None and canonical.endswith("JPY")


# Galaxy label per pair — membership is the inverse of constellation.PAIR_GALAXY.
PAIR_GALAXY: dict[str, str] = {
    pair: galaxy
    for galaxy, members in _MEMBERSHIP_GALAXY.items()
    for pair in members
}

# Pip size per pair — computed from the JPY convention, never a fixed table.
PAIR_PIP: dict[str, float] = {
    pair: (PIP_JPY if is_jpy_pair(pair) else PIP_STANDARD)
    for pair in CONSTELLATION_PAIRS
}


def is_constellation_pair(symbol: str) -> bool:
    """Gate: canonicalize via the Law, then check Constellation membership."""
    canonical = normalize_pair(symbol)
    return canonical is not None and canonical in CONSTELLATION_PAIRS


def pip_size(pair: str) -> float | None:
    """Return the pip size for a canonical pair, or ``None`` if not canonical."""
    canonical = normalize_pair(pair)
    if canonical is None:
        return None
    return PAIR_PIP.get(canonical)
