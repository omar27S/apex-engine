"""THE RAMS CONFIG — the sealed adversarial parameters (Phase 5, R18-style).

Every knob below is documented in place (its meaning, its pessimism DIRECTION,
and its date), and the whole frozen config is pinned by SHA-256 in
``tests/quant/test_rams.py``. Changing an intensity is a DELIBERATE commit: edit
the constant, recompute the manifest hash, and update the pin in the same commit.

R36 — THIS IS A THIRD LAYER. Nothing here edits the two sealed cost books
(``app/quant/costs.py``, R20): its SHA-256 pins are untouched. RAMS evaluation is
the CONSERVATIVE book plus the adversarial slippage layer defined here, applied
only inside ``app.quant.rams``.

PESSIMISM, EVERY KNOB:
* gap/intensity bigger  -> worse fills (more stop-hunt).
* news intensity bigger -> bigger fake impulses (more whipsaw deaths).
* slippage base/k bigger -> more erosion.
* decay cluster bigger  -> deeper worst-case drawdown.

Purity: a frozen dataclass and a digest function. No I/O, no services.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Mapping

from app.core.constellation import CONSTELLATION_PAIRS

__all__ = [
    "RAMSConfig",
    "RAMSConfigError",
    "DEFAULT_RAMS",
    "RAMS_AS_OF",
    "manifest_digest",
    "survivability_defaults",
]


class RAMSConfigError(ValueError):
    """A RAMS parameter violated a sealed invariant (fail-closed)."""


RAMS_AS_OF = "2026-10-09"

# Survivability thresholds (R38). Sealed defaults; each is pessimistic.
ADVERSARIAL_PF_MIN = 1.5          # adversarial profit factor must be at least this
P99_LOSS_FLOOR_R = -1.15          # the 99th-percentile loss may not be worse
CATASTROPHIC_TRADE_R = -1.3       # any single trade worse than this is an auto-fail
MAX_DECAYED_DD_R = 24.0           # worst-case decayed drawdown ceiling (R units)


def survivability_defaults() -> dict:
    """The sealed R38 survivability thresholds (one declaration)."""
    return {
        "adversarial_pf_min": ADVERSARIAL_PF_MIN,
        "p99_loss_floor_r": P99_LOSS_FLOOR_R,
        "catastrophic_trade_r": CATASTROPHIC_TRADE_R,
        "max_decayed_dd_r": MAX_DECAYED_DD_R,
    }


@dataclass(frozen=True)
class RAMSConfig:
    """The frozen RAMS parameters. All intensities are pessimistic in direction.

    ``spread_multiplier`` scales the conservative spread inside RAMS only (a
    wider book under attack). ``gap_intensity`` scales the injected micro-gap
    depth. ``news_intensity`` scales the fake-news impulse. ``slippage_base_pips``
    is the adversarial entry slip floor; ``slippage_vol_k`` / ``slippage_impact_k``
    scale it with volatility and lot-impact (R36). ``decay_cluster`` is the number
    of losers clustered into the worst plausible path (R36 drawdown_decay).
    """

    as_of: str
    seed: int
    spread_multiplier: float
    gap_intensity: float
    gap_atr_lower_pct: float          # low-liquidity = ATR percentile below this
    gap_min_pips: float
    gap_max_pips: float
    gap_buffer_pips: float            # buffer beyond the visible swing zone
    news_intensity: float
    news_slots_utc: tuple[tuple[int, int], ...]   # (hour, minute) UTC proxy slots
    news_candles: int                 # candles replaced per slot
    news_atr_mult: float              # fake impulse size in local ATR multiples
    slippage_base_pips: float
    slippage_vol_k: float
    slippage_impact_k: float
    decay_cluster: int

    def __post_init__(self):
        if self.spread_multiplier < 1.0:
            raise RAMSConfigError("spread_multiplier must be >= 1.0 (never gentler)")
        for name in ("gap_intensity", "news_intensity"):
            if float(getattr(self, name)) < 0.0:
                raise RAMSConfigError(f"{name} must be non-negative")
        if not (0.0 < self.gap_atr_lower_pct <= 1.0):
            raise RAMSConfigError("gap_atr_lower_pct must be in (0, 1]")
        if self.gap_min_pips <= 0.0 or self.gap_max_pips < self.gap_min_pips:
            raise RAMSConfigError("gap pip band invalid")
        if self.slippage_base_pips < 0.0 or self.slippage_vol_k < 0.0 \
                or self.slippage_impact_k < 0.0:
            raise RAMSConfigError("slippage terms must be non-negative")
        if self.news_candles < 1:
            raise RAMSConfigError("news_candles must be >= 1")
        if self.decay_cluster < 1:
            raise RAMSConfigError("decay_cluster must be >= 1")

    def to_manifest(self) -> dict:
        """Canonical, order-stable view for hashing and audit."""
        d = asdict(self)
        d["news_slots_utc"] = [list(s) for s in self.news_slots_utc]
        return d

    def digest(self) -> str:
        blob = json.dumps(self.to_manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------------------
# THE SEALED DEFAULTS. Change any number here -> update the pinned hash in
# tests/quant/test_rams.py in the SAME commit (R18 style).
# ---------------------------------------------------------------------------
DEFAULT_RAMS = RAMSConfig(
    as_of=RAMS_AS_OF,
    seed=0,
    spread_multiplier=1.35,
    gap_intensity=1.0,
    gap_atr_lower_pct=0.30,     # ATR in the bottom 30% = low-liquidity bar
    gap_min_pips=2.0,
    gap_max_pips=5.0,
    gap_buffer_pips=0.3,
    news_intensity=1.0,
    # SEALED PROXY CALENDAR: scheduled UTC slots on weekdays. 13:30 = US data
    # o'clock, 14:30 = the initial reaction. A REAL economic calendar is a NAMED
    # DEBT owned by Phase 6 (see AGENTS.md). Documented as a proxy, not a feed.
    news_slots_utc=((13, 30), (14, 30)),
    news_candles=3,
    news_atr_mult=1.1,
    slippage_base_pips=0.6,
    slippage_vol_k=1.5,
    slippage_impact_k=0.8,
    decay_cluster=5,
)

# Validate the sealed config covers the Constellation's spread keys (it consumes
# costs' table, whose keys are already validated, but assert the intent here).
if not CONSTELLATION_PAIRS:
    raise RAMSConfigError("the Constellation is empty — RAMS cannot run")


def manifest_digest(config: RAMSConfig | None = None) -> str:
    """Digest of ``config`` (default: the sealed DEFAULT_RAMS)."""
    return (config or DEFAULT_RAMS).digest()
