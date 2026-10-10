"""THE ORACLE CONTEXT — everything an acolyte may read, and nothing more.

An :class:`OracleContext` is the immutable snapshot of ONE candidate signal at the
moment the Oracle judges it. It is assembled by the runtime from three honest
sources and nothing else:

* the **genome** (family, risk geometry, filters) — the DNA that fired;
* the **evaluation report** (net R, trades, funnel stages, trust) — the honest
  judge's own evidence (R17);
* the **frames** (ATR, trend, regime, session) — the market state at signal time.

Every field is optional (``None``). A field left ``None`` means the feature was
NOT available; acolytes must return ``None`` (missing) for a REQUIRED feature and a
neutral ``0.5`` only for genuinely optional context. There is no magic default that
pretends a missing ATR is "normal" — fail-closed is the house rule.

CAUSALITY. The context carries only values knowable at the closed bar of the
signal. It never carries future bars, and it never carries the OUTCOME (net R of
the trade it will take) — that would leak the label into the scorer. The outcome
is used by the veto's TRAINING data (separately, R17/R22), never by the Oracle's
per-signal features.

Build Mode: a pure frozen dataclass. No I/O, no clock, no services.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["OracleContext", "CONTEXT_FIELDS"]


@dataclass(frozen=True)
class OracleContext:
    """The immutable feature snapshot for one candidate signal."""

    # -- identity -----------------------------------------------------------
    pair: str = ""
    family: str = ""
    domain: str = ""
    is_long: bool = True

    # -- market geometry (from frames, at signal close) ---------------------
    structure_ema_fast: float | None = None
    structure_ema_slow: float | None = None
    structure_slope: float | None = None   # normalized [-1, 1]
    momentum_pct: float | None = None      # normalized [-1, 1]
    atr_pips: float | None = None
    min_atr_pips: float | None = None
    atr_ratio: float | None = None         # current ATR / reference ATR
    regime_percentile: float | None = None
    session_id: int | None = None
    range_pos: float | None = None         # [0,1] position in recent range
    body_ratio: float | None = None        # [0,1]
    excursion_pct: float | None = None     # [0,1]
    htf_agrees: bool | None = None

    # -- signal/funnel evidence (from the evaluation report) ----------------
    domain_vote: float | None = None       # [0,1]
    priest_vote: float | None = None       # [0,1]
    family_density: float | None = None    # [0,1] (fires per bar, capped)
    family_agreement: float | None = None  # [0,1] multi-family agreement
    family_size: int | None = None
    confluence: int | None = None
    funnel_raw: int | None = None
    funnel_final: int | None = None
    signal_rate: float | None = None       # [0,1]
    long_share: float | None = None        # [0,1] of raw fires
    divergence: bool | None = None
    bars_since_signal: int | None = None
    warmup_ok: bool | None = None
    activation_state: float | None = None  # [0,1]

    # -- risk geometry (from the genome) ------------------------------------
    sl_atr_mult: float | None = None
    atr_mult_min: float | None = None
    atr_mult_max: float | None = None
    target_rr: float | None = None
    min_rr: float | None = None
    spread_pips: float | None = None
    max_spread_pips: float | None = None
    cost_r: float | None = None
    risk: float | None = None
    risk_pct: float | None = None
    titanium_floor_pct: float | None = None
    payoff: float | None = None
    max_bars_hold: int | None = None
    parachute_armed: bool | None = None

    # -- trust / sample / command context -----------------------------------
    trust: float | None = None
    trust_spread: float | None = None
    trades: int | None = None
    min_trades: int | None = None
    prize: float | None = None
    priest_seated: bool | None = None
    pair_covered: bool | None = None
    rotation_step: int | None = None

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


CONTEXT_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(OracleContext)
)
