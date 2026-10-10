"""THE RAMS REPORT — clean vs adversarial, and the survivability verdict (Phase 5).

``rams_evaluate(genome, frames, config)`` judges one strategy in two worlds:

* the CLEAN world — the honest engine under the sealed CONSERVATIVE book (the
  same judge a tournament uses, R20);
* the ADVERSARIAL world — the same engine on a frame RAMS has wounded (micro
  gaps + news whipsaw) under the CONSERVATIVE book scaled by
  ``config.spread_multiplier`` PLUS the R36 dynamic-slippage layer.

The delta report carries PF/WR/net-R in both worlds, gap-loss count and rate,
whipsaw deaths, slippage erosion in R, and the decayed worst-case drawdown. It
ends with the sealed SURVIVABILITY VERDICT (R38): a strategy survives only if
ALL hold — adversarial PF >= ``ADVERSARIAL_PF_MIN``, the 99th-percentile loss is
no worse than ``P99_LOSS_FLOOR_R``, no single trade is worse than
``CATASTROPHIC_TRADE_R`` (a catastrophic gap is an automatic fail), and the
decayed worst-case drawdown is within ``MAX_DECAYED_DD_R``.

R36: the two sealed cost books are NEVER edited — RAMS layers a multiplier and a
slippage charge on a COPY. Pure; the only "I/O" is in-memory evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.quant import costs, evaluator as ev
from app.quant import frames as fr
from app.quant import indicators
from app.quant.engine import EXIT_GAP_STOP
from app.quant.genome import StrategyGenome
from app.quant.rams import attacks as atk
from app.quant.rams.config import (
    DEFAULT_RAMS,
    RAMSConfig,
    survivability_defaults,
)

__all__ = [
    "RAMSReport",
    "MultiSeedVerdict",
    "rams_evaluate",
    "adversarial_frames",
    "survivability_verdict",
    "survivability_verdict_multi",
    "majority_needed",
    "p99_loss_r",
    "GAP_ATTR_BARS",
]

# How many execution bars after an injected M15 event a trade's entry may sit and
# still be attributed to it (an entry engine-side lands on the next exec open).
GAP_ATTR_BARS = 2


def _net_rs(trades) -> np.ndarray:
    return np.asarray(
        [float(t.r_multiple if t.net_r is None else t.net_r) for t in trades],
        dtype="float64",
    )


def _statarb_map(genome: StrategyGenome, frames: dict) -> dict:
    """The relative-value family needs its cross-pair z, exactly as the tournament
    supplies it (R17/R19). Omitting it silently yields ZERO trades — a fail-open
    the adversary pass would inherit. Fail-closed: only the statarb family gets a
    map; every other family legitimately needs none."""
    if genome.family not in {"cointegration_statarb"}:
        return {}
    from app.quant import statarb
    return statarb.statarb_z_map(genome, frames)


def _zero_trade_report(genome, clean_report, adv_report, config) -> "RAMSReport":
    """R38 fail-closed: a strategy that never traded cannot claim to survive.

    ``survives=False`` with ``failed_keys=["no_trades"]`` — the honest verdict is
    "not enough evidence", never a vacuous pass.
    """
    verdict = {
        "survives": False,
        "failed_keys": ["no_trades"],
        "checks": {},
        "thresholds": survivability_defaults(),
        "note": "clean or adversarial run produced ZERO trades — not enough "
                "evidence to claim survivability (fail-closed)",
    }
    return RAMSReport(
        pair="",
        signature=genome.signature(),
        family=genome.family,
        config_hash=config.digest(),
        clean=_timeline_metrics(clean_report),
        adversarial=_timeline_metrics(adv_report),
        delta={"net_r": 0.0, "win_rate": 0.0, "profit_factor": None, "trades": 0},
        verdict=verdict,
        injections={},
    )


def _timeline_metrics(report) -> dict:
    m = report.metrics
    pf = getattr(m, "profit_factor", None)
    return {
        "trades": int(m.trades), "net_r": float(m.net_r),
        "win_rate": float(m.win_rate),
        "profit_factor": (None if pf is None or pf != pf else float(pf)),
    }


def p99_loss_r(net_rs: np.ndarray) -> float:
    """The 99th-percentile LOSS: the 1st percentile of the net-R distribution.

    Returns 0.0 for an empty stream. This is the "how bad is the bad tail" figure
    the survivability floor is compared against (more negative = worse).
    """
    if net_rs.size == 0:
        return 0.0
    return float(np.quantile(net_rs, 0.01))


def adversarial_frames(
    universe: dict[str, fr.Frames],
    config: RAMSConfig = DEFAULT_RAMS,
    *,
    seed: int | None = None,
) -> tuple[dict[str, fr.Frames], dict[str, list[atk.InjectionEvent]]]:
    """Wound every pair's native M15 with gaps + whipsaw; rebuild the triad.

    Returns ``(adversarial_frames, injection_log_by_pair)``. Each mutated frame
    has already passed ``app.core.data.validate`` inside the attacks (an invalid
    adversarial frame is a RAMS bug, not a kill).
    """
    out: dict[str, fr.Frames] = {}
    logs: dict[str, list[atk.InjectionEvent]] = {}
    for pair, F in universe.items():
        base_seed = config.seed if seed is None else seed
        gaps = atk.micro_gaps(F.m15, config.gap_intensity, pip=F.pip, config=config,
                              seed=base_seed)
        whip = atk.news_whipsaw(gaps.frame, config.news_slots_utc, config.news_intensity,
                                pip=F.pip, config=config, seed=base_seed + 1)
        out[pair] = fr.build_frames(whip.frame, pair, F.pip)
        logs[pair] = list(gaps.log) + list(whip.log)
    return out, logs


def _vol_percentile_by_entry(F: fr.Frames, trades) -> dict[int, float]:
    """Entry-time ATR percentile (causal) for each trade's ``entry_index``.

    A missing/NaN read is priced at the pessimistic 1.0 (maximum volatility).
    """
    atr = np.asarray(F.atr, dtype="float64")
    rank = indicators.rolling_percentile_rank(atr, window=min(200, max(2, len(atr))))
    out: dict[int, float] = {}
    for t in trades:
        i = int(t.entry_index)
        v = float(rank[i]) if 0 <= i < len(rank) else np.nan
        out[i] = v if np.isfinite(v) else 1.0
    return out


def _injection_ts_by_kind(logs: list[atk.InjectionEvent], m15_ts) -> dict[str, list[int]]:
    by_kind: dict[str, list[int]] = {}
    for e in logs:
        if 0 <= e.bar_index < len(m15_ts):
            by_kind.setdefault(e.kind, []).append(int(m15_ts[e.bar_index]))
    return by_kind


def _count_attributed(trades, inj_ts: list[int], exec_ts, *, bars: int) -> int:
    """Trades whose entry ts sits within ``bars`` exec bars after an injection."""
    if not inj_ts or not len(trades):
        return 0
    exec_ts = np.asarray(exec_ts)
    count = 0
    for t in trades:
        ets = int(t.entry_ts)
        for its in inj_ts:
            if ets < its:
                continue
            # number of exec bars between the injection and the entry
            gap = int(np.searchsorted(exec_ts, ets) - np.searchsorted(exec_ts, its))
            if 0 <= gap <= bars:
                count += 1
                break
    return count


@dataclass
class RAMSReport:
    """The full clean-vs-adversarial record plus the survivability verdict."""

    pair: str
    signature: str
    family: str
    clean: dict
    adversarial: dict
    delta: dict
    verdict: dict
    injections: dict = field(default_factory=dict)
    config_hash: str = ""

    @property
    def survives(self) -> bool:
        return bool(self.verdict.get("survives", False))

    def to_dict(self) -> dict:
        return {
            "pair": self.pair, "signature": self.signature, "family": self.family,
            "clean": dict(self.clean), "adversarial": dict(self.adversarial),
            "delta": dict(self.delta), "verdict": dict(self.verdict),
            "injections": dict(self.injections), "config_hash": self.config_hash,
        }


def survivability_verdict(
    adv_metrics,
    decay: dict,
    *,
    config: RAMSConfig = DEFAULT_RAMS,
    thresholds: dict | None = None,
    gap_rate: float = 0.0,
) -> dict:
    """R38 — the sealed survivability gate. Fails closed on ANY missing reading.

    A gate that is unresolved (e.g. PF undefined with no losing trades) is
    reported honestly: ``profit_factor`` None is treated as unlimited (a strategy
    with no losses cannot fail on PF) but is flagged. Any single trade worse than
    ``catastrophic_trade_r`` is an automatic fail.
    """
    th = thresholds or survivability_defaults()
    net_rs = np.asarray(
        [float(x) for x in adv_metrics.get("net_rs", [])], dtype="float64"
    )
    pf = adv_metrics.get("profit_factor")
    worst_trade = float(net_rs.min()) if net_rs.size else 0.0
    p99 = p99_loss_r(net_rs)
    dd = float(decay.get("max_drawdown_r", 0.0))

    checks = {
        "profit_factor": {
            "value": pf, "min": th["adversarial_pf_min"],
            "ok": (pf is None) or (float(pf) >= float(th["adversarial_pf_min"])),
            "note": "no losing trades -> PF undefined (treated as passing)",
            "unresolved": pf is None,
        },
        "p99_loss_r": {
            "value": p99, "floor": th["p99_loss_floor_r"],
            "ok": p99 >= float(th["p99_loss_floor_r"]),
            "unresolved": False,
        },
        "catastrophic_trade_r": {
            "value": worst_trade, "floor": th["catastrophic_trade_r"],
            "ok": worst_trade >= float(th["catastrophic_trade_r"]),
            "unresolved": False,
        },
        "decayed_dd_r": {
            "value": dd, "max": th["max_decayed_dd_r"],
            "ok": dd <= float(th["max_decayed_dd_r"]),
            "unresolved": False,
        },
    }
    failed = [k for k, c in checks.items() if not c["ok"]]
    return {
        "survives": len(failed) == 0,
        "failed_keys": failed,
        "checks": checks,
        "gap_loss_rate": float(gap_rate),
        "thresholds": dict(th),
    }


def rams_evaluate(
    genome: StrategyGenome,
    frames: dict[str, fr.Frames],
    config: RAMSConfig = DEFAULT_RAMS,
    *,
    eval_config=None,
    seed: int | None = None,
    adversarial: tuple | None = None,
) -> RAMSReport:
    """Judge ``genome`` clean and adversarial; return the delta and the verdict.

    ``frames`` maps pair -> :class:`app.quant.frames.Frames`. The clean pass uses
    the sealed CONSERVATIVE book; the adversarial pass wounds each native M15
    frame (gaps + whipsaw), widens the book by ``config.spread_multiplier``, and
    layers the R36 dynamic slippage. ``adversarial`` may be a precomputed
    ``(adv_universe, logs)`` from :func:`adversarial_frames` so a batch run wounds
    the tape ONCE and reuses it. Fail-closed on an empty universe.
    """
    if not frames:
        raise ValueError("rams_evaluate needs a non-empty universe (fail-closed)")

    clean_cfg = eval_config or ev.EvaluationConfig()
    adv_cfg = ev.EvaluationConfig(
        streak_kill=clean_cfg.streak_kill,
        trail=clean_cfg.trail,
        enforce_min_atr=clean_cfg.enforce_min_atr,
        cost_model=costs.SELECTION_COST_MODEL,
        adversarial_spread_mult=config.spread_multiplier,
    )

    clean_report = ev.evaluate(
        genome, frames, clean_cfg, statarb_z_by_pair=_statarb_map(genome, frames)
    )
    if adversarial is not None:
        adv_universe, logs = adversarial
    else:
        adv_universe, logs = adversarial_frames(frames, config, seed=seed)
    adv_report = ev.evaluate(
        genome, adv_universe, adv_cfg,
        statarb_z_by_pair=_statarb_map(genome, adv_universe),
    )
    # Fail-closed R38: zero trades in EITHER world is not a survivability claim.
    # (The relative-value family needs its cross-pair z, supplied above; a
    # zero-trade adversary pass would otherwise be a silent fail-open.)
    if clean_report.metrics.trades == 0 or adv_report.metrics.trades == 0:
        return _zero_trade_report(genome, clean_report, adv_report, config)

    # R36 slippage layer: per-pair, price the extra slip from the pair's own
    # entry-time volatility percentile (causal), then restamp. Kept per-pair so
    # whipsaw attribution can name the pair.
    ram_by_pair: dict[str, list] = {}
    adv_trades: list = []
    all_clean: list = []
    for pair in sorted(frames):
        Fadv = adv_universe[pair]
        pair_trades = list(adv_report.per_pair[pair].trades)
        vp = _vol_percentile_by_entry(Fadv, pair_trades)
        rammed = atk.dynamic_slippage(pair_trades, vol_percentile_by_entry=vp,
                                      config=config)
        ram_by_pair[pair] = rammed
        adv_trades.extend(rammed)
        all_clean.extend(clean_report.per_pair[pair].trades)

    adv_net = _net_rs(adv_trades)
    adv_metrics = {
        "trades": int(len(adv_trades)),
        "net_r": float(adv_net.sum()) if adv_net.size else 0.0,
        "win_rate": float((adv_net > 0).mean()) if adv_net.size else 0.0,
        "profit_factor": _pf(adv_net),
    }
    # net_rs is passed to the verdict but not serialized (kept out of adv_out).
    adv_for_verdict = dict(adv_metrics, net_rs=[float(x) for x in adv_net])
    clean_net = _net_rs(all_clean)
    clean_metrics = {
        "trades": int(clean_report.metrics.trades),
        "net_r": float(clean_report.metrics.net_r),
        "win_rate": float(clean_report.metrics.win_rate),
        "profit_factor": clean_report.metrics.profit_factor,
    }

    # Slippage erosion: total extra R the adversary charged.
    erosion = float(sum(float(getattr(t, "ram_slippage_r", 0.0)) for t in adv_trades))

    # Gap damage: adversarial stop fills that gapped (EXIT_GAP_STOP).
    gap_losses = sum(1 for t in adv_trades if t.exit_reason == EXIT_GAP_STOP)
    gap_rate = (gap_losses / len(adv_trades)) if adv_trades else 0.0

    # Whipsaw deaths: adversarial losses attributed to a news injection on the
    # SAME pair, within GAP_ATTR_BARS execution bars of the injection.
    whip_deaths = 0
    for pair, trs in ram_by_pair.items():
        m15_ts = frames[pair].m15["ts"].to_numpy()
        exec_ts = frames[pair].exec["ts"].to_numpy()
        pair_whip = _injection_ts_by_kind(
            [e for e in logs[pair] if e.kind == "news_whipsaw"], m15_ts
        ).get("news_whipsaw", [])
        losses = [t for t in trs
                  if float(t.r_multiple if t.net_r is None else t.net_r) < 0]
        whip_deaths += _count_attributed(losses, pair_whip, exec_ts, bars=GAP_ATTR_BARS)

    decay = atk.drawdown_decay(adv_trades, config=config)
    verdict = survivability_verdict(adv_for_verdict, decay, config=config, gap_rate=gap_rate)

    delta = {
        "net_r": adv_metrics["net_r"] - clean_metrics["net_r"],
        "win_rate": adv_metrics["win_rate"] - clean_metrics["win_rate"],
        "profit_factor": (
            None if (adv_metrics["profit_factor"] is None
                     or clean_metrics["profit_factor"] is None)
            else float(adv_metrics["profit_factor"]) - float(clean_metrics["profit_factor"])
        ),
        "trades": adv_metrics["trades"] - clean_metrics["trades"],
    }
    adv_out = dict(adv_metrics)
    adv_out["slippage_erosion_r"] = erosion
    adv_out["gap_losses"] = gap_losses
    adv_out["gap_loss_rate"] = gap_rate
    adv_out["whipsaw_deaths"] = whip_deaths
    adv_out["decayed_max_dd_r"] = decay["max_drawdown_r"]
    # R37 — the era stamp (config hash) so a multi-era corpus can later separate a
    # clean evaluation from this RAMS one even on identical genome numbers.
    adv_out["rams_config_hash"] = config.digest()
    injections = {p: [e.to_dict() for e in evs] for p, evs in logs.items()}
    return RAMSReport(
        pair=genome.pair if hasattr(genome, "pair") else "",
        signature=genome.signature(),
        family=genome.family,
        clean=clean_metrics,
        adversarial=adv_out,
        delta=delta,
        verdict=verdict,
        injections=injections,
        config_hash=config.digest(),
    )


def _pf(net_rs: np.ndarray) -> float | None:
    if net_rs.size == 0:
        return None
    gains = float(net_rs[net_rs > 0].sum())
    losses = float(-net_rs[net_rs < 0].sum())
    if losses == 0.0:
        return None
    return gains / losses


# ---------------------------------------------------------------------------
# R40 (Phase 6a) — THE THREE-FACED ENEMY: a verdict over multiple seeds.
# ---------------------------------------------------------------------------
def majority_needed(seeds) -> int:
    """R40 — the number of seeds a genome must survive for a majority verdict.

    A strict majority: ``floor(n/2) + 1``. For the sealed three seeds that is 2.
    """
    n = len(tuple(seeds))
    if n <= 0:
        raise ValueError("majority_needed requires at least one seed (fail-closed)")
    return n // 2 + 1


@dataclass
class MultiSeedVerdict:
    """R40 — the survivability verdict across an ensemble of adversarial seeds.

    ``survives`` is the MAJORITY ruling AND the catastrophe veto: a genome must
    survive at least ``majority_needed`` seeds AND have NO catastrophic trade on
    ANY seed (one −1.3R gap on a single draw is a fail, however good the rest).
    ``worst_seed`` is the seed with the deepest catastrophic/p99 exposure, named so
    the exposure is never hidden. ``per_seed`` is the full per-seed key table.
    """

    seeds: tuple[int, ...]
    per_seed: dict[int, dict]
    survived_seeds: tuple[int, ...]
    failed_seeds: tuple[int, ...]
    majority_needed: int
    worst_seed: int | None
    catastrophic_seeds: tuple[int, ...]
    survives: bool
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "seeds": list(self.seeds),
            "per_seed": {str(k): dict(v) for k, v in self.per_seed.items()},
            "survived_seeds": list(self.survived_seeds),
            "failed_seeds": list(self.failed_seeds),
            "majority_needed": int(self.majority_needed),
            "worst_seed": self.worst_seed,
            "catastrophic_seeds": list(self.catastrophic_seeds),
            "survives": bool(self.survives),
            "note": self.note,
        }


def _cert_verdict(v: "MultiSeedVerdict") -> dict:
    """The council-facing shape: the R38 keys + the R40 majority exposure."""
    failed_keys = set()
    for seed, row in v.per_seed.items():
        for k in row.get("failed_keys", []):
            failed_keys.add(k)
    return {
        "survives": bool(v.survives),
        "failed_keys": sorted(failed_keys),
        "thresholds": survivability_defaults(),
        "majority": {
            "needed": int(v.majority_needed),
            "survived": len(v.survived_seeds),
            "seeds": list(v.seeds),
        },
        "worst_seed": v.worst_seed,
        "catastrophic_seeds": list(v.catastrophic_seeds),
        "per_seed": {str(k): dict(row) for k, row in v.per_seed.items()},
        "note": v.note,
    }


def survivability_verdict_multi(
    genome: StrategyGenome,
    frames: dict[str, fr.Frames],
    config: RAMSConfig = DEFAULT_RAMS,
    *,
    seeds: tuple[int, ...] = (0, 1, 2),
    eval_config=None,
) -> MultiSeedVerdict:
    """R40 — run the adversarial world once PER SEED and rule by majority.

    The clean world is evaluated ONCE (it is seed-independent); each seed wounds
    the tape differently and produces its own adversarial verdict. A genome:

    * SURVIVES iff it passes >= ``majority_needed(seeds)`` seeds, AND
    * has NO ``catastrophic_trade_r`` failure on ANY seed (the catastrophe veto),
    * and no seed produced ZERO trades (fail-closed — see ``rams_evaluate``).

    ``worst_seed`` names the seed with the lowest p99 loss (the deepest tail), so
    the ugliest draw is reported rather than averaged away.
    """
    seeds = tuple(int(s) for s in seeds)
    if not seeds:
        raise ValueError("survivability_verdict_multi needs at least one seed")

    per_seed: dict[int, dict] = {}
    survived: list[int] = []
    failed: list[int] = []
    catastrophic: list[int] = []
    worst_seed: int | None = None
    worst_p99 = float("inf")

    for s in seeds:
        rep = rams_evaluate(genome, frames, config, eval_config=eval_config, seed=s)
        v = rep.verdict
        keys = list(v.get("failed_keys", []))
        # `no_trades` is a fail-closed non-survival, not a pass.
        cat = "catastrophic_trade_r" in keys
        p99 = float(v.get("checks", {}).get("p99_loss_r", {}).get("value", 0.0))
        per_seed[s] = {
            "survives": bool(v.get("survives", False)),
            "failed_keys": keys,
            "p99_loss_r": p99,
            "catastrophic_trade_r": cat,
            "adv_net_r": float(rep.adversarial.get("net_r", 0.0)),
            "adv_trades": int(rep.adversarial.get("trades", 0)),
        }
        if v.get("survives", False):
            survived.append(s)
        else:
            failed.append(s)
        if cat or "no_trades" in keys:
            catastrophic.append(s)
        if p99 < worst_p99:
            worst_p99 = p99
            worst_seed = s

    need = majority_needed(seeds)
    majority_ok = len(survived) >= need
    catastrophe_ok = len(catastrophic) == 0
    survives = bool(majority_ok and catastrophe_ok)

    if not majority_ok and not catastrophe_ok:
        note = (f"failed majority ({len(survived)}/{len(seeds)} < {need}) AND "
                f"catastrophic/no-trade on seeds {catastrophic}")
    elif not majority_ok:
        note = f"failed majority ({len(survived)}/{len(seeds)} < {need})"
    elif not catastrophe_ok:
        note = (f"majority passed but CATASTROPHIC/no-trade on seeds {catastrophic} "
                f"(R40 veto)")
    else:
        note = f"survived majority ({len(survived)}/{len(seeds)} >= {need})"

    v = MultiSeedVerdict(
        seeds=seeds,
        per_seed=per_seed,
        survived_seeds=tuple(survived),
        failed_seeds=tuple(failed),
        majority_needed=need,
        worst_seed=worst_seed,
        catastrophic_seeds=tuple(catastrophic),
        survives=survives,
        note=note,
    )
    return v


def survivability_verdict_multi_cert(
    genome: StrategyGenome,
    frames: dict[str, fr.Frames],
    config: RAMSConfig = DEFAULT_RAMS,
    *,
    seeds: tuple[int, ...] = (0, 1, 2),
    eval_config=None,
) -> dict:
    """R40 — the multi-seed verdict in the council-certificate shape."""
    return _cert_verdict(survivability_verdict_multi(
        genome, frames, config, seeds=seeds, eval_config=eval_config
    ))


def gauntlet_row(
    genome: StrategyGenome,
    frames: dict[str, fr.Frames],
    config: RAMSConfig = DEFAULT_RAMS,
    *,
    seen_seeds: tuple[int, ...] = (0, 1, 2),
    unseen_seeds: tuple[int, ...] = (7, 11, 13),
    eval_config=None,
) -> dict:
    """R45+R46 (Phase 6b/6c) — one finalist's FULL-GAUNTLET row.

    R46 THE UNSEEN GAUNTLET — the CROWN verdict is the UNSEEN verdict: a finalist
    ``survives`` iff it clears the majority on the UNSEEN seeds AND has no
    catastrophic/no-trade face on ANY unseen seed. The seen-seed verdict is kept
    as a DIAGNOSTIC (side by side), so a genome that passes seen but dies unseen is
    visible and is NOT crowned.

    Every finalist (no top-N cap) gets: both seed-tuple verdicts, the seed-by-seed
    keys, the worst-seed exposure, the catastrophic-seed list, and the aggregate
    adversarial net R/trades. ``survives``/``passed_seeds``/``worst_seed``/etc.
    mirror the UNSEEN verdict (the crown gate).
    """
    seen = survivability_verdict_multi(
        genome, frames, config, seeds=seen_seeds, eval_config=eval_config)
    unseen = survivability_verdict_multi(
        genome, frames, config, seeds=unseen_seeds, eval_config=eval_config)
    net_rs = [float(r.get("adv_net_r", 0.0)) for r in unseen.per_seed.values()]
    trades = [int(r.get("adv_trades", 0)) for r in unseen.per_seed.values()]
    failed_keys = sorted({k for r in unseen.per_seed.values()
                          for k in r.get("failed_keys", [])})
    note = unseen.note
    if seen.survives and not unseen.survives:
        note = f"SEEN survives but UNSEEN fails — {unseen.note}"
    return {
        "signature": genome.signature(),
        "family": genome.family,
        # R46 — the crown gate is the UNSEEN verdict.
        "survives": bool(unseen.survives),
        "seeds": list(unseen.seeds),
        "seen_seeds": list(seen.seeds),
        "unseen_seeds": list(unseen.seeds),
        "seen_survives": bool(seen.survives),
        "passed_seeds": list(unseen.survived_seeds),
        "failed_seeds": list(unseen.failed_seeds),
        "majority_needed": int(unseen.majority_needed),
        "worst_seed": unseen.worst_seed,
        "catastrophic_seeds": list(unseen.catastrophic_seeds),
        "per_seed": {str(k): dict(r) for k, r in unseen.per_seed.items()},
        "seen": seen.to_dict(),
        "unseen": unseen.to_dict(),
        "per_seed_failed_keys": {
            str(k): list(r.get("failed_keys", [])) for k, r in unseen.per_seed.items()
        },
        "failed_keys": failed_keys,
        "adv_net_r_mean": (sum(net_rs) / len(net_rs)) if net_rs else 0.0,
        "adv_trades_mean": (sum(trades) / len(trades)) if trades else 0.0,
        "note": note,
    }


def gauntlet_cert_row(gauntlet: dict) -> dict:
    """R45+R46 — the council-certificate shape from a full-gauntlet row.

    ``survives`` and ``majority``/``worst_seed``/``catastrophic_seeds`` mirror the
    UNSEEN verdict (the crown gate); the full ``seen`` and ``unseen`` verdicts ride
    along SIDE BY SIDE so the council can name the failing face without any
    re-evaluation (a seat is never billed twice for the same genome)."""
    unseen = gauntlet.get("unseen", {}) or {}
    return {
        "survives": bool(gauntlet.get("survives", False)),
        "failed_keys": list(gauntlet.get("failed_keys", [])),
        "majority": {
            "needed": int(gauntlet.get("majority_needed", 0)),
            "survived": len(gauntlet.get("passed_seeds", [])),
            "seeds": list(gauntlet.get("seeds", [])),
        },
        "worst_seed": gauntlet.get("worst_seed"),
        "catastrophic_seeds": list(gauntlet.get("catastrophic_seeds", [])),
        "per_seed": dict(gauntlet.get("per_seed", {})),
        "seen": dict(gauntlet.get("seen", {}) or {}),
        "unseen": dict(unseen),
        "note": gauntlet.get("note", ""),
    }
