"""THE SWITCHBOARD — signal dispatch, the shared gate stack, and the funnel.

A strategy genome names a ``family``; :func:`dispatch` routes it through
:data:`FAMILY_SIGNALS` to a pure ``(genome, ctx) -> (long, short)`` callable, then
applies the SHARED GATE STACK in a fixed order:

    family_raw -> session -> trend -> regime -> confluence -> activation -> warmup -> final

Every gate can only remove signals, so the funnel counts are monotonic
non-increasing — a mute strategy is immediately diagnosable: we always know
exactly which door killed the signals. No silent zero-signal path (Scar #8).

WARMUP SUPPRESSION. Signals are suppressed where the signals' own primitives are
NaN (the family already yields False there), where a REQUIRED higher-timeframe
context is NaN, and for a genome-derived warmup horizon covering the slowest
referenced indicator (so a D1 EMA that needs 30 days cannot leak a signal in its
first weeks).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np

from app.quant.frames import Frames
from app.quant.genome import RELATIVE_VALUE_FAMILIES as _RELATIVE_VALUE_FAMILIES

__all__ = [
    "SignalContext",
    "FunnelReport",
    "FAMILY_SIGNALS",
    "PENDING_FAMILIES",
    "dispatch",
    "required_warmup_bars",
    "register_family",
]


@dataclass
class SignalContext:
    """Everything a family or gate may read, in one carrier.

    ``statarb_z`` is declared now for the relative-value families of Phase 2.2b
    and is unused until then. ``frames``/``pair``/``pip`` are always present.
    """

    frames: Frames
    pair: str
    pip: float
    statarb_z: np.ndarray | None = None
    # Per-dispatch side channel for counted diagnostics (statarb_unavailable,
    # ensemble member fire counts). Cleared by ``dispatch`` before each call.
    family_extra: dict[str, int] = field(default_factory=dict)
    # R59 (Phase 7c) — the member vote cache and the world seed that names which
    # adversary (or the clean world) is being read. Both are OPTIONAL: absent, an
    # ensemble recomputes every member (correct, just slower).
    vote_cache: object | None = None
    world_seed: int = 0


@dataclass(frozen=True)
class FunnelReport:
    """Survivor counts after each gate — monotone non-increasing by construction.

    ``extra`` carries non-pipeline diagnostics that are *counted, never silent* —
    e.g. ``statarb_unavailable`` for the relative-value family, or the ensemble's
    member-level fire counts.
    """

    pair: str
    family: str
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    extra: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> dict[str, int]:
        """Combined long+short survivor count at each stage."""
        return {stage: v["long"] + v["short"] for stage, v in self.counts.items()}

    def as_rows(self) -> list[tuple[str, int, int]]:
        """``(stage, long, short)`` in gate order, for tabling."""
        return [(stage, v["long"], v["short"]) for stage, v in self.counts.items()]


# ---------------------------------------------------------------------------
# Family registry.
# ---------------------------------------------------------------------------
FAMILY_SIGNALS: dict[str, object] = {}

# R32 — ATTENDED-ONLY. The 45th family ``generated_body`` has no place in
# FAMILY_SIGNALS: a self-written body is NEVER auto-routed through the ordinary
# broadcast gate stack. It enters the pyramid only through the attended Author,
# whose bodies run in the Phase-4a cage (subprocess) and whose signals are fed
# straight to the honest evaluator — never through this dispatch table.
ATTENDED_ONLY_FAMILIES: frozenset[str] = frozenset({"generated_body"})


def assert_attended_ok(unattended: bool, families=()) -> None:
    """R47 (Phase 6c) — UNATTENDED RUNS BAN GENERATED BODIES.

    Fail-closed: an unattended run (a cloud/night-shift run with no human in the
    room) may NOT admit the ATTENDED-ONLY ``generated_body`` family. Bodies evolve
    only in attended sessions (R32). Raises ``ValueError`` when the two collide,
    so a mis-scheduled workflow aborts at config construction, never silently
    trains self-written code unsupervised.
    """
    if not unattended:
        return
    named = {str(f) for f in families}
    clash = named & set(ATTENDED_ONLY_FAMILIES)
    if clash:
        raise ValueError(
            f"R47: an unattended run may not admit {sorted(clash)} — the "
            f"generated_body family evolves ONLY in attended sessions (R32)"
        )


def register_family(name: str, fn) -> None:
    """Wire a family name to its pure ``(genome, ctx)`` callable.

    Fail-closed (R32): an ATTENDED-ONLY family can never be registered here.
    """
    if name in ATTENDED_ONLY_FAMILIES:
        raise ValueError(
            f"family {name!r} is ATTENDED-ONLY (R32): it must never be routed "
            f"through the broadcast dispatch"
        )
    if name in FAMILY_SIGNALS:
        raise ValueError(f"family {name!r} already registered")
    FAMILY_SIGNALS[name] = fn


CLASSIC_FAMILIES: tuple[str, ...] = (
    "trend_pullback",
    "mean_reversion",
    "breakout",
    "macd_momentum",
    "keltner_expansion",
    "rsi_reversal",
)

SMC_FAMILIES: tuple[str, ...] = (
    "wyckoff_spring",
    "order_block",
    "volume_delta",
    "ob_atr_rank",
    "liq_sweep_ote",
    "choch_fvg",
    "bos_premium_discount",
    "fvg_momentum",
    "silver_bullet",
    "asian_range_sweep",
    "eqhl_tap",
    "judas_swing",
    "ict_2022_model",
    "dealing_range",
    "turtle_soup",
)

QUANT_FAMILIES: tuple[str, ...] = (
    "bb_keltner_squeeze",
    "atr_squeeze_breakout",
    "vcp_breakout",
    "momentum_ignition",
    "london_orb",
    "ny_orb",
    "vwap_reversion",
    "zscore_reversion",
    "hurst_regime",
    "hurst_reversion_filtered",
    "keltner_pullback",
    "volume_profile_v",
)

PATTERN_FAMILIES: tuple[str, ...] = (
    "pin_bar",
    "engulfing_liquidity",
    "hikkake",
    "fib_confluence",
    "harmonic_proxy",
    "rsi_divergence",
    "mtf_divergence",
    "fib_ote_confluence",
    "time_based_reversal",
)


def _load_classic() -> None:
    """Register the Phase 2.2a classical families (import-time wiring)."""
    from app.quant import signal_classic as sc

    for name in CLASSIC_FAMILIES:
        if name not in FAMILY_SIGNALS:
            register_family(name, getattr(sc, name))


def _load_smc() -> None:
    """Register the Phase 2.2b SMC/ICT families (import-time wiring)."""
    from app.quant import signal_smc as sm

    for name in SMC_FAMILIES:
        if name not in FAMILY_SIGNALS:
            register_family(name, getattr(sm, name))


def _load_quant() -> None:
    """Register the Phase 2.2c statistical/volatility families."""
    from app.quant import signal_quant as sq

    for name in QUANT_FAMILIES:
        if name not in FAMILY_SIGNALS:
            register_family(name, getattr(sq, name))


def _load_pattern() -> None:
    """Register the Phase 2.2c pattern/confluence families."""
    from app.quant import signal_pattern as sp

    for name in PATTERN_FAMILIES:
        if name not in FAMILY_SIGNALS:
            register_family(name, getattr(sp, name))


def _load_relative_value() -> None:
    """Register the relative-value family (reads ``ctx.statarb_z``)."""
    from app.quant import statarb

    if "cointegration_statarb" not in FAMILY_SIGNALS:
        register_family("cointegration_statarb", statarb.cointegration_statarb)


def _ensemble_family(genome, ctx):
    """Ensemble family: quorum over concrete members, member counts recorded.

    An ensemble whose ``ensemble_members`` is not yet a valid quorum (fewer than
    two concrete members) is an UNCONFIGURED probe, not a failure: it emits
    all-False and records ``ensemble_unconfigured`` so the mute is explicit.
    A nested ensemble is a constitutional violation and raises loudly (R3).
    """
    from app.quant.ensemble import EnsembleStrategy

    long_z, short_z = _zero(len(ctx.frames))
    members = getattr(genome, "ensemble_members", ()) or ()
    if len(members) < 2:
        ctx.family_extra["ensemble_unconfigured"] = 1
        return long_z, short_z
    strategy = EnsembleStrategy.from_genome(genome)
    long_m, short_m, counts = strategy.signals(genome, ctx)
    ctx.family_extra.update(counts)
    return long_m, short_m


def _load_ensemble() -> None:
    """Register the ensemble family (quorum over concrete members)."""
    if "ensemble" not in FAMILY_SIGNALS:
        register_family("ensemble", _ensemble_family)


_load_classic()
_load_smc()
_load_quant()
_load_pattern()
_load_relative_value()
_load_ensemble()


def _n(values) -> np.ndarray:
    return np.asarray(values, dtype="float64")


def _zero(n: int) -> tuple[np.ndarray, np.ndarray]:
    return np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)


# ---------------------------------------------------------------------------
# Warmup horizon (genome-derived).
# ---------------------------------------------------------------------------
TREND_EMA_SLOW_PERIOD = 30  # must match the D1 EMA period built in frames.py


def required_warmup_bars(genome) -> int:
    """Execution bars to suppress at the start, from the slowest gene reference.

    The horizon is the number of TREND (D1) bars the slowest moving average
    needs, converted to execution (H1) bars via 24 H1 bars per day, plus the
    slowest execution-side indicator. A generous, documented over-estimate is
    intentional: a warmup gate may only suppress, never admit.
    """
    base = max(
        getattr(genome, "ema_slow", 21),
        getattr(genome, "bb_period", 20),
        getattr(genome, "keltner_period", 20),
        getattr(genome, "hurst_window", 100),
        getattr(genome, "target_lookback", 20),
        getattr(genome, "sl_lookback", 20),
        getattr(genome, "zscore_period", 20),
        getattr(genome, "smc_range_lookback", 0),
        getattr(genome, "smc_pool_window", 0),
        getattr(genome, "statarb_window", 0),
    )
    days = TREND_EMA_SLOW_PERIOD + 1  # D1 EMA warmup + first closed bar
    return int(base + days * 24)


# ---------------------------------------------------------------------------
# Individual gates. Each returns a mask that may only remove signals.
# ---------------------------------------------------------------------------
def _session_mask(genome, ctx) -> np.ndarray:
    from app.quant import indicators as ind

    ts = ctx.frames.exec["ts"].to_numpy()
    masks = ind.session_masks(ts)
    sid = int(getattr(genome, "session_id", 0))
    if sid == 0:
        return np.ones(len(ts), dtype=bool)
    names = ["asia", "london", "newyork"]
    return masks[names[min(max(sid, 1), 3) - 1]]


def _trend_mask(genome, ctx) -> np.ndarray:
    f = ctx.frames
    mode = int(getattr(genome, "trend_align", 1))
    if mode == 0:
        return np.ones(len(f), dtype=bool)
    up = f.trend_ema_fast > f.trend_ema_slow
    down = f.trend_ema_fast < f.trend_ema_slow
    if mode == 1:
        # context must be readable AND agree; NaN context => reject
        return up | down
    return np.isfinite(f.trend_ema_fast) & np.isfinite(f.trend_ema_slow)


def _regime_mask(genome, ctx) -> np.ndarray:
    f = ctx.frames
    return _n(f.atr_pips) >= float(getattr(genome, "min_atr_pips", 0.0))


def _confluence_mask(genome, ctx, long_raw, short_raw) -> np.ndarray:
    """Keep raw signals that carry enough independent confirmations.

    Confirmations counted per bar (0..3): H1 close on the H4 structure side;
    H4 structure EMA fast/slow agreement; D1 trend EMA agreement. A threshold of
    0/1 passes everything. Direction-agnostic: the count is attached to a bar
    where either a long or a short is live.
    """
    need = int(getattr(genome, "min_confluence", 0))
    if need <= 1:
        return np.ones(len(ctx.frames), dtype=bool)
    f = ctx.frames
    active = long_raw | short_raw
    long_side = long_raw
    h1_side = np.where(f.exec["close"].to_numpy() >= f.structure_close, 1, -1)
    h4_side = np.where(f.structure_ema_fast >= f.structure_ema_slow, 1, -1)
    d1_side = np.where(f.trend_ema_fast >= f.trend_ema_slow, 1, -1)
    want = np.where(long_side, 1, -1)
    count = (
        (h1_side == want).astype(int)
        + (h4_side == want).astype(int)
        + (d1_side == want).astype(int)
    )
    finite = (
        np.isfinite(f.structure_close)
        & np.isfinite(f.structure_ema_fast)
        & np.isfinite(f.structure_ema_slow)
        & np.isfinite(f.trend_ema_fast)
        & np.isfinite(f.trend_ema_slow)
    )
    return (count >= need) & finite | ~active


ACTIVATION_RANK_WINDOW = 500  # execution bars for the self-relative rank

# The regime gate's Hurst reading uses a SEALED observation window, not the
# genome's ``hurst_window`` gene. The gene configures the family's own signal; the
# gate is a shared sensor, and a percentile computed on different windows would
# not be comparable across genomes. Sealing it also lets the expensive R/S Hurst
# be computed ONCE per frame and reused by every genome swept over it.
REGIME_HURST_WINDOW = 100


def _rolling_percentile_rank(values: np.ndarray, window: int) -> np.ndarray:
    """Self-relative percentile rank (single source: ``indicators``).

    Kept as a thin alias so existing callers stay put; the implementation and its
    causality registration live in :func:`indicators.rolling_percentile_rank`.
    """
    from app.quant import indicators as ind

    return ind.rolling_percentile_rank(values, window)


def _activation_mask(genome, ctx) -> np.ndarray:
    """Regime-activation gate: the regime the strategy wants must be present.

    Two independent, self-calibrating regime signals are available:

    * **D1 trend separation rank** — ``|ema_fast - ema_slow| / close`` ranked
      within its own trailing window. ``regime_adx_min`` sets the required rank.
    * **ATR-expansion rank** — the execution ATR ranked within its own trailing
      window. ``regime_atr_rank_min`` sets the required rank.

    HURST PERCENTILE DOCTRINE (R2): a regime that needs a Hurst reading uses the
    rolling PERCENTILE of the (biased) R/S Hurst, never an absolute threshold;
    ``regime_hurst_min`` is a required percentile in 0..1. The absolute-biased
    R/S value never enters a comparison.

    With every activation threshold at its floor the gate passes all bars.
    """
    f = ctx.frames
    n = len(f)
    ok = np.ones(n, dtype=bool)

    from app.quant import indicators as ind

    adx_min = float(getattr(genome, "regime_adx_min", 0.0))
    if adx_min > 0.0:
        adx_exec = _cached_adx(f, int(getattr(genome, "adx_period", 14)))
        ok &= np.isfinite(adx_exec) & (adx_exec >= adx_min)

    atr_min = float(getattr(genome, "regime_atr_rank_min", 0.0))
    if atr_min > 0.0:
        atr_rank = _cached_rank(f, "atr", _n(f.atr_pips), ACTIVATION_RANK_WINDOW)
        ok &= np.isfinite(atr_rank) & (atr_rank >= atr_min)

    hurst_min = float(getattr(genome, "regime_hurst_min", 0.0))
    if hurst_min > 0.0:
        # Sealed gate window (not the genome's own gene) — one reading per frame.
        raw_hurst = _cached_hurst(f, REGIME_HURST_WINDOW)
        rank = _cached_rank(f, "hurst", raw_hurst, ACTIVATION_RANK_WINDOW)
        ok &= np.isfinite(rank) & (rank >= hurst_min)
    return ok


# Expensive regime inputs are memoized per (frame identity, parameter) so a
# genome swept over one frame (the census, a GA) pays each cost once. The entry
# holds a STRONG reference to the frame, so its id cannot be recycled while the
# entry lives; the identity is re-checked on hit. LRU-bounded.
_ACTIVATION_CACHE: "OrderedDict[tuple, tuple[object, np.ndarray]]" = OrderedDict()
_ACTIVATION_CACHE_MAX = 32


def clear_activation_cache() -> None:
    """Empty the memoized activation-input cache (adx / hurst / ranks)."""
    _ACTIVATION_CACHE.clear()


def _cached(f, key: tuple, build) -> np.ndarray:
    full = (id(f), *key)
    entry = _ACTIVATION_CACHE.get(full)
    if entry is not None and entry[0] is f:
        _ACTIVATION_CACHE.move_to_end(full)
        return entry[1]
    value = build()
    _ACTIVATION_CACHE[full] = (f, value)
    _ACTIVATION_CACHE.move_to_end(full)
    while len(_ACTIVATION_CACHE) > _ACTIVATION_CACHE_MAX:
        _ACTIVATION_CACHE.popitem(last=False)
    return value


def _cached_adx(f, period: int) -> np.ndarray:
    from app.quant import indicators as ind

    ex = f.exec
    return _cached(
        f, ("adx", int(period)),
        lambda: ind.adx(
            ex["high"].to_numpy(), ex["low"].to_numpy(), ex["close"].to_numpy(), int(period)
        ),
    )


def _cached_hurst(f, window: int) -> np.ndarray:
    from app.quant import indicators as ind

    close = f.exec["close"].to_numpy()
    return _cached(f, ("hurst", int(window)), lambda: ind.hurst(close, int(window)))


def _cached_rank(f, kind: str, values: np.ndarray, window: int) -> np.ndarray:
    return _cached(f, (f"rank.{kind}", int(window)),
                   lambda: _rolling_percentile_rank(values, window))


def _warmup_mask(genome, ctx, required: tuple[bool, bool]) -> np.ndarray:
    """Suppress the running start and any bar missing required HTF context."""
    n = len(ctx.frames)
    horizon = min(required_warmup_bars(genome), n)
    mask = np.zeros(n, dtype=bool)
    mask[horizon:] = True
    need_trend, need_struct = required
    if need_trend:
        mask &= np.isfinite(ctx.frames.trend_ema_slow) & np.isfinite(ctx.frames.trend_close)
    if need_struct:
        mask &= np.isfinite(ctx.frames.structure_close)
    return mask


# ---------------------------------------------------------------------------
# Dispatch.
# ---------------------------------------------------------------------------
def dispatch(genome, ctx: SignalContext):
    """Route a genome through the gate stack. Returns ``(long, short, funnel)``.

    Gate order is fixed: session -> trend -> regime -> confluence -> activation
    -> warmup. An UNKNOWN family returns all-False masks with a funnel that makes
    the mute state explicit (never a silent zero). Every family in ``FAMILIES``
    is registered as of Phase 2.2c — there is no pending set.
    """
    n = len(ctx.frames)
    family = getattr(genome, "family", None)
    counts: dict[str, dict[str, int]] = {}
    ctx.family_extra = {}

    def record(stage: str, long_m, short_m):
        counts[stage] = {
            "long": int(np.count_nonzero(long_m)),
            "short": int(np.count_nonzero(short_m)),
        }

    if family not in FAMILY_SIGNALS:
        long_out, short_out = _zero(n)
        record("family_raw", long_out, short_out)
        for stage in ("after_sessions", "after_trend", "after_regime",
                      "after_confluence", "after_activation", "final"):
            record(stage, long_out, short_out)
        return long_out, short_out, FunnelReport(ctx.pair, str(family), counts)

    # Relative-value families read the caller-attached, shifted spread z. If it is
    # absent or the wrong length, record statarb_unavailable (counted, not silent).
    if family in _RELATIVE_VALUE_FAMILIES and ctx.statarb_z is None:
        ctx.family_extra["statarb_unavailable"] = 1

    fn = FAMILY_SIGNALS[family]
    long_raw, short_raw = fn(genome, ctx)
    long_raw = np.asarray(long_raw, dtype=bool)
    short_raw = np.asarray(short_raw, dtype=bool)
    record("family_raw", long_raw, short_raw)

    session = _session_mask(genome, ctx)
    long_s, short_s = long_raw & session, short_raw & session
    record("after_sessions", long_s, short_s)

    trend = _trend_mask(genome, ctx)
    # trend gate is direction-aware: "with trend" allows only the agreeing side.
    mode = int(getattr(genome, "trend_align", 1))
    if mode == 1:
        f = ctx.frames
        long_t = long_s & (f.trend_ema_fast > f.trend_ema_slow)
        short_t = short_s & (f.trend_ema_fast < f.trend_ema_slow)
    elif mode == 2:
        f = ctx.frames
        long_t = long_s & (f.trend_ema_fast < f.trend_ema_slow)
        short_t = short_s & (f.trend_ema_fast > f.trend_ema_slow)
    else:
        long_t, short_t = long_s & trend, short_s & trend
    # require_h1_align: H1 close must agree with the H4 structure side.
    if int(getattr(genome, "require_h1_align", 0)) == 1:
        f = ctx.frames
        h1 = f.exec["close"].to_numpy()
        struct = f.structure_close
        long_t &= np.isfinite(struct) & (h1 >= struct)
        short_t &= np.isfinite(struct) & (h1 < struct)
    record("after_trend", long_t, short_t)

    regime = _regime_mask(genome, ctx)
    long_r, short_r = long_t & regime, short_t & regime
    record("after_regime", long_r, short_r)

    confluence = _confluence_mask(genome, ctx, long_r, short_r)
    long_c, short_c = long_r & confluence, short_r & confluence
    record("after_confluence", long_c, short_c)

    activation = _activation_mask(genome, ctx)
    long_a, short_a = long_c & activation, short_c & activation
    record("after_activation", long_a, short_a)

    required = (
        int(getattr(genome, "trend_align", 1)) != 0,
        int(getattr(genome, "require_h1_align", 0)) == 1,
    )
    warm = _warmup_mask(genome, ctx, required)
    long_f, short_f = long_a & warm, short_a & warm
    record("final", long_f, short_f)

    return long_f, short_f, FunnelReport(
        ctx.pair, str(family), counts, dict(ctx.family_extra)
    )
