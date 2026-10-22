"""THE EVALUATOR — a genome meets real history.

One job: given a genome and a universe of pre-built :class:`frames.Frames`, walk
its signals through the Phase-1 honest engine on every pair and pool the trades
into one report. The engine itself enforces the Constitution (VNSB stop band,
1:2.5 R:R floor, the Parachute lock) — the evaluator never re-implements a law.

SCOPE / DEBT (stated, not hidden):
- R17 NET-R DOCTRINE: the report's ranking fields are NET R (after the sealed
  ``costs`` model). Gross R survives only as a diagnostic (``metrics.gross_r``,
  ``metrics.gross_win_rate``). Costs are ON by default; ``cost_model=None`` is the
  DIAGNOSTIC gross mode and its report is stamped "DIAGNOSTIC — NOT FOR RANKING".
- DEBT-010: the cost model is a conservative STATIC proxy (the tape is bid-only);
  Phase 6 broker specs replace it, never silently patch it. See ``costs``.
- Trailing is computed causally (close +/- ``trail_atr_mult`` x ATR) and handed to
  the engine, which clamps it to the parachute lock via ``law.effective_stop``. The
  evaluator never lets a stop violate the lock.

EARLY STOPPING IS PER-PAIR (Scar #3). A losing-streak kill ends THAT pair's walk
only; the streak counter never crosses pairs. Trades are pooled afterwards.

Levels come from the genome's ``level_source_id`` (an interval id into
:data:`LEVEL_SOURCES`), the same registry the causality tests cover.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

import numpy as np

from app.quant import usd_eye as _usd_eye

from app.core import law
from app.quant import costs, engine, levels, fitness
from app.quant.frames import Frames
from app.quant.genome import StrategyGenome
from app.quant.signals import SignalContext, dispatch
from app.quant.metrics import MetricsReport, aggregate

__all__ = [
    "LEVEL_SOURCES",
    "EvaluationConfig",
    "PairReport",
    "EvaluationReport",
    "DualEvaluationReport",
    "evaluate_pair",
    "evaluate",
    "evaluate_adversarial",
    "evaluate_dual",
    "adversarial_fixable_deaths",
]

DIAGNOSTIC_STAMP = "DIAGNOSTIC — NOT FOR RANKING"

# Interval id -> structural level source. The genome's ``level_source_id`` gene is
# an int in [0, len(LEVEL_SOURCES) - 1]; ``source_for`` clamps defensively.
LEVEL_SOURCES = ("swing", "donchian", "equal_hl", "fvg", "round")


def source_for(genome: StrategyGenome) -> str:
    """The structural level source named by the genome (clamped, fail-closed)."""
    try:
        idx = int(getattr(genome, "level_source_id", 0))
    except (TypeError, ValueError):
        return LEVEL_SOURCES[0]
    if idx < 0 or idx >= len(LEVEL_SOURCES):
        return LEVEL_SOURCES[0]
    return LEVEL_SOURCES[idx]


def _compute_levels(
    F: Frames, genome: StrategyGenome
) -> levels.LevelSet:
    """Build the genome's :class:`LevelSet` from its named source. Pure."""
    high = F.exec["high"].to_numpy(dtype="float64")
    low = F.exec["low"].to_numpy(dtype="float64")
    close = F.exec["close"].to_numpy(dtype="float64")
    source = source_for(genome)
    if source == "swing":
        return levels.swing_levels(high, low, int(genome.sl_lookback))
    if source == "donchian":
        return levels.donchian_levels(high, low, int(genome.sl_lookback))
    if source == "equal_hl":
        return levels.equal_hl_levels(high, low, F.pip, window=int(genome.smc_pool_window))
    if source == "fvg":
        return levels.fvg_levels(high, low)
    return levels.round_levels(close, F.pip, step_pips=int(genome.smc_turtle_lookback))


@dataclass(frozen=True)
class EvaluationConfig:
    """Knobs the tournament passes; the evaluator itself is slice-agnostic.

    ``cost_model`` defaults to the sealed R18 instance, so **costs are ON by
    default** — the parameter exists for diagnostics only. Passing ``None`` runs
    the friction-less mode and stamps the report ``DIAGNOSTIC — NOT FOR RANKING``;
    it must never feed ranking (R17).
    """

    streak_kill: int | None = None      # per-pair consecutive-loss kill; None = off
    trail: bool = True                  # hand causal trailing to the engine
    enforce_min_atr: bool = True        # reject signals below the genome's floor
    cost_model: "costs.CostModel | None" = costs.DEFAULT_COST_MODEL
    # R36 (Phase 5) — RAMS hooks, used ONLY by app.quant.rams. A multiplier on the
    # sealed spread inside an adversarial evaluation (>1 widens the book). The
    # clean path keeps the default 1.0 and is byte-identical.
    adversarial_spread_mult: float = 1.0

    def __post_init__(self):
        if self.adversarial_spread_mult < 1.0:
            raise ValueError("adversarial_spread_mult must be >= 1.0 (never gentler)")

    @property
    def costs_on(self) -> bool:
        return self.cost_model is not None

    @property
    def diagnostic(self) -> bool:
        """Gross mode is DIAGNOSTIC ONLY (R17) and is stamped as such in reports."""
        return not self.costs_on


@dataclass(frozen=True)
class PairReport:
    """One pair's honest slice of the evaluation."""

    pair: str
    metrics: MetricsReport
    trades: list
    streak_killed: bool
    funnel: dict
    rejected: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationReport:
    """The union report (the Champion's verdict) plus per-pair sub-reports."""

    signature: str
    family: str
    metrics: MetricsReport                 # pooled across pairs; NET R (R17)
    per_pair: dict[str, PairReport]
    universe: tuple[str, ...]
    funnel: dict                           # summed across pairs
    streak_kills: int
    diagnostic: bool = False               # gross mode (R17 stamp)
    stamp: str = ""                        # set to DIAGNOSTIC_STAMP in gross mode


def _early_stop(trades: list, streak_kill: int | None) -> tuple[list, bool]:
    """Apply a per-pair losing-streak kill to one pair's trade list.

    Trades arrive in chronological (entry_index) order from the engine. Consecutive
    losses increment a counter; any non-loss (win or tie) resets it. Once the
    counter reaches ``streak_kill`` the pair stops taking trades. The counter is
    local to this call, so it can never cross pairs (Scar #3).

    R17: a loss is judged on NET R. Trades must be cost-stamped (``net_r``) before
    this runs, so a gross winner that inverts under costs counts as the loss it
    really is.
    """
    if not streak_kill or streak_kill <= 0:
        return list(trades), False
    kept: list = []
    streak = 0
    for t in trades:
        if streak >= streak_kill:
            return kept, True
        kept.append(t)
        net = t.r_multiple if getattr(t, "net_r", None) is None else t.net_r
        streak = streak + 1 if net < 0 else 0
    return kept, False


def _scaled_model(model, mult: float):
    """R36 — return ``model`` with every spread scaled by ``mult`` (must be >= 1).

    Used ONLY by RAMS to widen the book under attack. Never called with a
    selection book in the clean path (mult==1.0 short-circuits), so the sealed
    books and their hashes are untouched.
    """
    if mult == 1.0 or model is None:
        return model
    from types import MappingProxyType

    scaled = MappingProxyType(
        {k: float(v) * float(mult) for k, v in model.spread_pips.items()}
    )
    return replace(model, name=f"{model.name}_rams_x{mult:g}", spread_pips=scaled)


def _stamp_costs(trades: list, pair: str, model: "costs.CostModel | None") -> list:
    """Return the trades with ``pair``/``cost_r``/``net_r`` stamped (R17).

    When ``model`` is ``None`` (diagnostic gross mode) the pair is stamped but
    costs stay at zero, so ``net_r == r_multiple``. That mode is DIAGNOSTIC ONLY
    and must never feed ranking.
    """
    if model is None:
        return [replace(t, pair=pair, cost_r=0.0, net_r=t.r_multiple) for t in trades]
    out = []
    for t in trades:
        c = costs.round_trip_cost_r(replace(t, pair=pair), model)
        out.append(replace(t, pair=pair, cost_r=c, net_r=t.r_multiple - c))
    return out


def _stop_target_arrays(
    F: Frames,
    genome: StrategyGenome,
    long_signals: np.ndarray,
    short_signals: np.ndarray,
    lv: levels.LevelSet,
) -> tuple[np.ndarray, np.ndarray]:
    """Stop/target price arrays aligned to the frame, NaN where undefined.

    The stop ANCHOR is the genome's STRUCTURAL level source (``level_source_id``):
    the last-confirmed swing low (long) / high (short). Its DISTANCE is then clamped
    into the VNSB band ``[sl_atr_mult x ATR + buffer, law.VNSB_ATR_MULT_MAX x ATR]``.
    So ``sl_atr_mult`` is a law-bounded MINIMUM stop, structure may widen it up to
    the band maximum (and no farther), and a level source that puts its swing
    farther away therefore changes both the risk unit and the target — the
    ``level_source_id`` gene is load-bearing, not decoration. The clamp guarantees
    the stop is in-band BY CONSTRUCTION; the target is ``target_rr`` x risk.

    The engine re-derives risk from the actual next-bar open and its own VNSB/RR
    gates still run, so a proxy that drifted is rejected there, never accepted
    silently. NaN ATR -> no trade (fail-closed).
    """
    n = len(F.exec)
    close = F.exec["close"].to_numpy(dtype="float64")
    atr = np.asarray(F.atr, dtype="float64")
    stop = np.full(n, np.nan)
    target = np.full(n, np.nan)
    buffer = float(genome.sl_buffer_pips) * F.pip
    min_dist = float(genome.sl_atr_mult) * atr + buffer
    hi_dist = law.VNSB_ATR_MULT_MAX * atr
    rr = float(genome.target_rr)

    for mask, is_long in ((long_signals, True), (short_signals, False)):
        idx = np.nonzero(mask)[0]
        if idx.size == 0:
            continue
        ref = np.asarray(
            lv.swing_low if is_long else lv.swing_high, dtype="float64"
        )[idx]
        c = close[idx]
        raw = (c - ref) if is_long else (ref - c)
        raw = np.where(np.isfinite(raw), raw, min_dist[idx])
        dist = np.clip(raw, min_dist[idx], hi_dist[idx])
        if is_long:
            s = c - dist
            t = c + rr * dist
        else:
            s = c + dist
            t = c - rr * dist
        stop[idx] = s
        target[idx] = t
    return stop, target


def _trailing_array(
    F: Frames, genome: StrategyGenome, long_signals: np.ndarray, short_signals: np.ndarray
) -> np.ndarray:
    """Causal trailing candidates: close -/+ ``trail_atr_mult`` x ATR.

    The engine applies :func:`law.effective_stop`, so these can never push a stop
    past the parachute lock. NaN where ATR is unavailable (engine ignores NaN).
    """
    n = len(F.exec)
    close = F.exec["close"].to_numpy(dtype="float64")
    atr = F.atr
    mult = float(genome.trail_atr_mult)
    candidate = np.full(n, np.nan)
    long_idx = np.nonzero(long_signals)[0]
    short_idx = np.nonzero(short_signals)[0]
    candidate[long_idx] = close[long_idx] - mult * atr[long_idx]
    candidate[short_idx] = close[short_idx] + mult * atr[short_idx]
    return candidate


def evaluate_pair(
    genome: StrategyGenome,
    F: Frames,
    config: EvaluationConfig,
    statarb_z: np.ndarray | None = None,
    signals: tuple[np.ndarray, np.ndarray, dict] | None = None,
    vote_cache=None,
    world_seed: int = 0,
    usd_eye=None,
) -> PairReport:
    """Evaluate one genome on one pair (one pre-sliced frame).

    ``signals`` (optional) injects ``(long, short, funnel_counts)`` directly,
    bypassing ``dispatch``. This is the seam the CAGE uses to judge a
    self-written body's masks through the SAME engine, stop geometry, costs and
    aggregation as any genome — no discounts for being artificial (Phase 4a).

    R59 — ``vote_cache``/``world_seed`` are threaded into the signal context so an
    ensemble's members are read through the member vote cache (free when warm).
    """
    ctx = SignalContext(F, F.pair, F.pip, statarb_z=statarb_z,
                        vote_cache=vote_cache, world_seed=int(world_seed))
    if signals is None:
        long_s, short_s, funnel = dispatch(genome, ctx)
        funnel_counts = funnel.counts
    else:
        long_s, short_s, funnel_counts = signals
    long_s = np.array(long_s, dtype=bool)
    short_s = np.array(short_s, dtype=bool)

    # R36 — the adversary is free to widen the book; the clean path keeps mult 1.0
    # (and the sealed model object is never mutated, only copied by _scaled_model).
    model = _scaled_model(config.cost_model, config.adversarial_spread_mult)

    atr = np.asarray(F.atr, dtype="float64")
    if config.enforce_min_atr:
        floor = float(genome.min_atr_pips) * F.pip
        # Fail-closed: an unavailable ATR (NaN) or a sub-floor ATR rejects the signal.
        ok_atr = np.isfinite(atr) & (atr >= floor)
        long_s = long_s & ok_atr
        short_s = short_s & ok_atr

    # R140 -- THE DOLLAR EYE: an entry that fights a dollar move beyond the
    # genome's threshold is refused BEFORE simulation (the ATR floor's idiom:
    # the eye can only refuse, never invent). Crosses carry no USD leg and a
    # stale USD tape is a blind bar -- never a fabricated verdict.
    _eye_blocked = 0
    if usd_eye is not None and _usd_eye.usd_leg(F.pair) != 0:
        _ok_long, _ok_short = _usd_eye.entry_masks(
            F, usd_eye, float(genome.usd_eye_strength))
        _eye_blocked = int((long_s & ~_ok_long).sum()
                           + (short_s & ~_ok_short).sum())
        long_s = long_s & _ok_long
        short_s = short_s & _ok_short

    lv = _compute_levels(F, genome)
    stop, target = _stop_target_arrays(F, genome, long_s, short_s, lv)

    trailing = None
    if config.trail:
        trailing = _trailing_array(F, genome, long_s, short_s)

    policy = engine.ExitPolicy(
        max_bars_hold=int(genome.max_bars_hold),
        trail_after_arm=config.trail,
    )
    sim = engine.simulate(
        F.exec, long_s, short_s, atr, stop, target, policy,
        pip=F.pip, trailing_levels=trailing,
    )
    # R17: stamp the friction cost on every fill BEFORE the streak kill, so a
    # gross winner that inverts under costs counts as the loss it really is.
    stamped = _stamp_costs(sim.trades, F.pair, model)
    trades, killed = _early_stop(stamped, config.streak_kill)
    _rejected = dict(sim.rejected)
    if _eye_blocked:
        _rejected["usd_eye"] = _eye_blocked   # R140: the refused entries, said aloud
    metrics = aggregate(trades, sim.rejected)
    return PairReport(
        pair=F.pair,
        metrics=metrics,
        trades=trades,
        streak_killed=killed,
        funnel=funnel_counts,
        rejected=_rejected,
    )


def _sum_funnels(pairs: Mapping[str, PairReport]) -> dict:
    """Sum per-stage long/short counts across pairs (same stage keys everywhere)."""
    total: dict[str, dict[str, int]] = {}
    for rep in pairs.values():
        for stage, counts in rep.funnel.items():
            bucket = total.setdefault(stage, {"long": 0, "short": 0})
            for side in ("long", "short"):
                bucket[side] = bucket.get(side, 0) + int(counts.get(side, 0))
    return total


def evaluate(
    genome: StrategyGenome,
    universe_frames: Mapping[str, Frames],
    config: EvaluationConfig | None = None,
    statarb_z_by_pair: Mapping[str, np.ndarray | None] | None = None,
    signals_by_pair: Mapping[str, tuple[np.ndarray, np.ndarray, dict]] | None = None,
    vote_cache=None,
    world_seed: int = 0,
) -> EvaluationReport:
    """Evaluate ``genome`` over a universe of frames and pool the trades.

    ``universe_frames`` maps pair -> :class:`Frames` (already sliced to train or
    test by the caller; this function is slice-agnostic). A genome is judged on
    the UNION of trades, while every per-pair sub-report is preserved.
    ``statarb_z_by_pair`` (optional) supplies the relative-value family its
    cross-pair z; a missing entry leaves that family's statarb slice unavailable
    (counted, fail-closed — never a fabricated z). ``signals_by_pair`` (optional)
    injects masks per pair — the CAGE's path for judging a self-written body
    through the identical engine (Phase 4a).
    """
    config = config or EvaluationConfig()
    # R140 -- THE DOLLAR EYE: built once per evaluation, only when the genome
    # grew one (mode=1). The universe the evaluator already carries is the
    # eye's retina: the USD pairs' own tapes, strictly causal, sign-corrected.
    _usd_index = (_usd_eye.build_usd_index(universe_frames)
                  if _usd_eye.eye_open(genome) else None)
    statarb_z_by_pair = statarb_z_by_pair or {}
    signals_by_pair = signals_by_pair or {}
    per_pair: dict[str, PairReport] = {}
    pooled: list = []
    all_rejected: dict[str, int] = {}
    streak_kills = 0
    for pair in sorted(universe_frames):
        rep = evaluate_pair(
            genome, universe_frames[pair], config,
            statarb_z=statarb_z_by_pair.get(pair),
            signals=signals_by_pair.get(pair),
            vote_cache=vote_cache, world_seed=world_seed,
            usd_eye=_usd_index,
        )
        per_pair[pair] = rep
        pooled.extend(rep.trades)
        streak_kills += int(rep.streak_killed)
        for gate, count in rep.rejected.items():
            all_rejected[gate] = all_rejected.get(gate, 0) + int(count)

    pooled_metrics = aggregate(pooled, all_rejected)
    return EvaluationReport(
        signature=genome.signature(),
        family=genome.family,
        metrics=pooled_metrics,
        per_pair=per_pair,
        universe=tuple(sorted(universe_frames)),
        funnel=_sum_funnels(per_pair),
        streak_kills=streak_kills,
        diagnostic=config.diagnostic,
        stamp=DIAGNOSTIC_STAMP if config.diagnostic else "",
    )


@dataclass(frozen=True)
class DualEvaluationReport:
    """R39 (Phase 6a) — one genome judged in BOTH worlds.

    ``adversarial`` is the RANKING world (primary key); ``clean`` is a DIAGNOSTIC
    carried alongside. ``shared_signals`` records that the two worlds reused the
    genome's signal computation for the SAME pair masks (the clean masks are the
    reference; see :func:`evaluate_dual`). ``fixable_deaths`` is the R39 autopsy
    count over the adversarial world (0 when no autopsy was requested).
    """

    signature: str
    family: str
    clean: EvaluationReport
    adversarial: EvaluationReport
    fixable_deaths: int = 0
    autopsy_by_cause: dict = field(default_factory=dict)

    @property
    def diagnostic_clean(self) -> EvaluationReport:
        """The clean world is DIAGNOSTIC ONLY once dual selection is on (R39)."""
        return self.clean

    def to_dict(self) -> dict:
        return {
            "signature": self.signature,
            "family": self.family,
            "clean_net_r": float(self.clean.metrics.net_r),
            "clean_win_rate": float(self.clean.metrics.win_rate),
            "clean_trades": int(self.clean.metrics.trades),
            "adv_net_r": float(self.adversarial.metrics.net_r),
            "adv_win_rate": float(self.adversarial.metrics.win_rate),
            "adv_trades": int(self.adversarial.metrics.trades),
            "fixable_deaths": int(self.fixable_deaths),
            "autopsy_by_cause": dict(self.autopsy_by_cause),
        }


def adversarial_fixable_deaths(genome, adv_report, adv_universe, logs) -> tuple[int, dict]:
    """R39/R43 public seam: fixable adversarial deaths for one genome.

    Thin wrapper over the sealed autopsy attribution so callers (the tournament
    ranking path) need not reach into a private name.
    """
    return _autopsy_adversarial_deaths(genome, adv_report, adv_universe, logs or {})


def _autopsy_adversarial_deaths(genome, adv_report, adv_universe, injection_logs):
    """R39 — count adversarial losses by an engineered (fixable) cause.

    Uses the sealed autopsy taxonomy. A loss is attributable only when a RAMS
    injection window can be timestamped near its entry (see ``autopsy``); an
    unattributable loss is classified structural and thus NOT fixable. Returns
    ``(fixable_count, by_cause)``. Fail-open to ZERO only when the autopsy itself
    cannot run (no exec frame); a genuine loss is never silently dropped.
    """
    from app.quant import autopsy as autopsy_mod

    by_cause: dict[str, int] = {}
    fixable = 0
    for pair, pair_rep in adv_report.per_pair.items():
        Fadv = adv_universe.get(pair)
        if Fadv is None:
            continue
        losses = [
            t for t in pair_rep.trades
            if float(t.r_multiple if getattr(t, "net_r", None) is None else t.net_r) < 0.0
        ]
        if not losses:
            continue
        logs = injection_logs.get(pair, []) if injection_logs else []
        m15_ts = Fadv.m15["ts"].to_numpy()
        inj: dict[str, list[int]] = {}
        for e in logs:
            if 0 <= int(e.bar_index) < len(m15_ts):
                inj.setdefault(e.kind, []).append(int(m15_ts[int(e.bar_index)]))
        ctx = autopsy_mod.AutopsyContext(
            exec_ts=Fadv.exec["ts"].to_numpy(), injection_ts=inj,
        )
        rep = autopsy_mod.autopsy(
            losses, Fadv.exec, signature=genome.signature(),
            family=genome.family, domain=pair, context=ctx,
        )
        for cause, n in rep.causes.items():
            if n:
                by_cause[cause] = by_cause.get(cause, 0) + int(n)
                if cause in fitness.FIXABLE_CAUSES:
                    fixable += int(n)
    return fixable, by_cause


def _apply_rams_slippage(genome, adv_report, adv_universe, rams_config):
    """R36 — restamp the adversarial pool with the dynamic-slippage layer.

    Returns a NEW :class:`EvaluationReport` whose trades carry ``ram_slippage_r``
    and whose ``net_r`` already reflects the extra slip (costs only worsen). The
    per-pair geometry is untouched; only the cost stamp changes. Local import to
    keep ``evaluator`` free of a cycle with ``rams.report``.
    """
    from app.quant.rams import attacks as atk
    from app.quant.rams import report as rams_report

    new_per_pair: dict[str, PairReport] = {}
    pooled: list = []
    all_rejected: dict[str, int] = {}
    streak_kills = 0
    for pair in sorted(adv_universe):
        pair_rep = adv_report.per_pair.get(pair)
        if pair_rep is None:
            continue
        Fadv = adv_universe[pair]
        trades = list(pair_rep.trades)
        vp = rams_report._vol_percentile_by_entry(Fadv, trades)
        rammed = atk.dynamic_slippage(trades, vol_percentile_by_entry=vp,
                                      config=rams_config)
        merged = dict(pair_rep.rejected)
        new_per_pair[pair] = PairReport(
            pair=pair,
            metrics=aggregate(rammed, merged),
            trades=rammed,
            streak_killed=pair_rep.streak_killed,
            funnel=pair_rep.funnel,
            rejected=merged,
        )
        pooled.extend(rammed)
        streak_kills += int(pair_rep.streak_killed)
        for gate, count in merged.items():
            all_rejected[gate] = all_rejected.get(gate, 0) + int(count)

    return EvaluationReport(
        signature=genome.signature(),
        family=genome.family,
        metrics=aggregate(pooled, all_rejected),
        per_pair=new_per_pair,
        universe=tuple(sorted(new_per_pair)),
        funnel=_sum_funnels(new_per_pair),
        streak_kills=streak_kills,
    )


def evaluate_adversarial(
    genome: StrategyGenome,
    adversarial_frames: Mapping[str, Frames],
    adversarial_config: EvaluationConfig | None = None,
    *,
    statarb_z_by_pair_adv: Mapping | None = None,
    rams_config=None,
    vote_cache=None,
    world_seed: int = 0,
) -> EvaluationReport:
    """R43 (Phase 6b) — judge ``genome`` on the ADVERSARIAL tape ONLY.

    The in-generation ranking path under clean demotion: the clean world is NOT
    evaluated here (it is billed for the elite set alone, see ``evaluate_dual``).
    The R36 dynamic-slippage layer is applied when ``rams_config`` is supplied, so
    this is the same ranking world the R39 dual path ranks on. Fail-closed on an
    empty universe.

    R59 — ``vote_cache``/``world_seed`` thread the member vote cache so an
    ensemble's members are computed once per ``(member, pair, seed, slice)``.
    """
    if not adversarial_frames:
        raise ValueError(
            "evaluate_adversarial needs a non-empty adversarial universe (fail-closed)"
        )
    adv_cfg = adversarial_config or EvaluationConfig()
    adv = evaluate(
        genome, adversarial_frames, adv_cfg,
        statarb_z_by_pair=statarb_z_by_pair_adv,
        vote_cache=vote_cache, world_seed=world_seed,
    )
    if rams_config is not None:
        adv = _apply_rams_slippage(genome, adv, adversarial_frames, rams_config)
    return adv


def evaluate_dual(
    genome: StrategyGenome,
    frames: Mapping[str, Frames],
    clean_config: EvaluationConfig | None = None,
    adversarial_frames: Mapping[str, Frames] | None = None,
    adversarial_config: EvaluationConfig | None = None,
    *,
    adversarial_logs: Mapping | None = None,
    statarb_z_by_pair: Mapping | None = None,
    statarb_z_by_pair_adv: Mapping | None = None,
    autopsy_deaths: bool = True,
    rams_config=None,
    vote_cache=None,
    world_seed: int = 0,
) -> DualEvaluationReport:
    """R39 (Phase 6a) — judge ``genome`` on the CLEAN and the ADVERSARIAL tape.

    The two worlds share ONE computation of the genome's signal masks per pair for
    the CLEAN world (the reference); the adversarial world is the same genome run
    against the wounded frames, where each family's indicators legitimately change
    because the tape changed, but the genome's PARAMETERS and the whole gate stack
    are identical (no per-world re-parameterisation — that is the shared-signal
    invariant the tests pin).

    ``adversarial_frames`` (wounded tape) and ``adversarial_logs`` (RAMS injection
    log) are supplied by the caller, normally from ``rams.adversarial_frames`` so a
    batch run wounds the tape ONCE. ``adversarial_config`` carries the R36 spread
    multiplier; when ``rams_config`` is supplied the R36 dynamic-slippage layer is
    ALSO applied to the adversarial pool, so the ranking world is the full RAMS
    adversary (spread + slip). Fail-closed on an empty universe.

    ``statarb_z_by_pair`` / ``statarb_z_by_pair_adv`` supply the relative-value
    family its cross-pair z per world (R17/R19).
    """
    if not frames:
        raise ValueError("evaluate_dual needs a non-empty clean universe (fail-closed)")

    clean_cfg = clean_config or EvaluationConfig()
    adv_cfg = adversarial_config or EvaluationConfig(
        streak_kill=clean_cfg.streak_kill,
        trail=clean_cfg.trail,
        enforce_min_atr=clean_cfg.enforce_min_atr,
    )

    statarb_z_by_pair = statarb_z_by_pair or {}
    if statarb_z_by_pair_adv is None and adversarial_frames is not None:
        statarb_z_by_pair_adv = {
            p: statarb_z_by_pair.get(p) for p in sorted(adversarial_frames)
        }
    statarb_z_by_pair_adv = statarb_z_by_pair_adv or {}

    clean = evaluate(genome, frames, clean_cfg, statarb_z_by_pair=statarb_z_by_pair,
                     vote_cache=vote_cache, world_seed=world_seed)

    if adversarial_frames is None:
        # Fail-closed: without a wounded tape there is no adversarial evidence.
        adv = evaluate(genome, {}, adv_cfg)
    else:
        adv = evaluate(
            genome, adversarial_frames, adv_cfg,
            statarb_z_by_pair=statarb_z_by_pair_adv,
            vote_cache=vote_cache, world_seed=world_seed,
        )
        if rams_config is not None:
            adv = _apply_rams_slippage(genome, adv, adversarial_frames, rams_config)

    fixable = 0
    by_cause: dict[str, int] = {}
    if autopsy_deaths and adversarial_frames is not None and adv.metrics.trades > 0:
        fixable, by_cause = _autopsy_adversarial_deaths(
            genome, adv, adversarial_frames, adversarial_logs or {}
        )

    return DualEvaluationReport(
        signature=genome.signature(),
        family=genome.family,
        clean=clean,
        adversarial=adv,
        fixable_deaths=fixable,
        autopsy_by_cause=by_cause,
    )
