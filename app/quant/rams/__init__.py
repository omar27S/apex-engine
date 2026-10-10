"""RAMS — the Realistic Adversarial Market Simulator (Phase 5).

An army that has never met the enemy is a parade. RAMS is the enemy: it hunts
stops, fakes news, and charges real slippage, so a strategy that only survives a
clean tape never earns a promotion.

RAMS is a THIRD layer (R36). The two sealed cost books (R20: conservative = the
selection book, realistic = reporting) are UNTOUCHED and their SHA-256 pins are
unchanged. RAMS evaluation is the conservative book PLUS an adversarial slippage
layer, applied only inside this package.

WHAT LIVES HERE
* :mod:`config`  — the sealed, hash-pinned RAMS parameters (R18-style).
* :mod:`attacks` — four pure, deterministic attacks, each documented with its
  pessimism direction and returning a mutated frame plus an injection log.
* :mod:`report`  — ``rams_evaluate`` and the sealed survivability verdict.

PURITY: nothing here is live. No I/O at import, no server, no scheduler, no
unbounded loop. Every attack is deterministic under its seed.
"""

from __future__ import annotations

from app.quant.rams.config import (
    RAMSConfig,
    RAMSConfigError,
    DEFAULT_RAMS,
    manifest_digest,
)
from app.quant.rams.attacks import (
    InjectionEvent,
    AttackResult,
    micro_gaps,
    news_whipsaw,
    dynamic_slippage,
    slippage_pips,
    apply_adversarial_slippage,
    drawdown_decay,
)

__all__ = [
    "RAMSConfig",
    "RAMSConfigError",
    "DEFAULT_RAMS",
    "manifest_digest",
    "InjectionEvent",
    "AttackResult",
    "micro_gaps",
    "news_whipsaw",
    "dynamic_slippage",
    "slippage_pips",
    "apply_adversarial_slippage",
    "drawdown_decay",
]
