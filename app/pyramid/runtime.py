"""THE PYRAMID RUNTIME — one call musters the seven hundred (Phase 3.2).

:func:`run_pyramid` is the single entry point that wires the whole structure:

1. **THE TOURNAMENT** (Phase 2.3b) runs under the R20/R21 books — the CONSERVATIVE
   selection book ranks, and negative-net genomes are exiled to the death ledger
   (cause ``"friction"``). This is the honest judge; nothing bypasses it.
2. **SOLDIERS ARE MUSTERED** from the survivors' DNA — the pyramid's Rank 3 is
   staffed by genomes reality passed, never by declaration. Trust is seeded from
   each survivor's honest mean NET R (R17).
3. **THE AVANT-GARDE** (Rank 4) runs micro-tournaments on random contiguous slices
   of the same history, proposes mutants, and feeds candidates upward. They hold NO
   live vote; their findings flow through the standard evaluator.
4. **THE COUNCIL** (of Seven) convenes on the tournament result: promotion over the
   conservative bar, exile report (R21), and tribunal input (R10).

Build Mode: inert. This module does no I/O at import and starts no server, no
scheduler, and no unbounded loop. The only loop is a bounded micro-tournament count
the caller sets. Everything is deterministic under ``seed``; the main tournament is
resumable through its own checkpoint (same doctrine as Phase 2.3b).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from app.quant import costs, frames as fr
from app.quant import evaluator as ev
from app.quant import seeds as seed_mod
from app.quant.genome import StrategyGenome
from app.quant.signals import FAMILY_SIGNALS
from app.quant.tournament import (
    TournamentConfig,
    TournamentResult,
    run as run_tournament,
)
from app.pyramid import brain as brain_mod
from app.pyramid import council as council_mod
from app.pyramid import doctrine
from app.pyramid import roster as roster_mod
from app.pyramid import trust as trust_mod

__all__ = [
    "PyramidConfig",
    "PyramidResult",
    "run_pyramid",
]

PYRAMID_CHECKPOINT_PATH = "data/history/.pyramid_state.json"


@dataclass(frozen=True)
class PyramidConfig:
    """Everything a pyramid run needs to be reproducible and bounded."""

    pairs: tuple[str, ...]
    population: int = 240
    generations: int = 1
    elite: int = 40
    min_trades: int = 30
    streak_kill: int = 8
    train_frac: float = 0.7
    seed: int = 0
    max_wallclock_seconds: float = 1800.0
    top_n_test: int = 10
    mutation_rate: float = 0.25
    # R20/R21 books.
    use_costs: bool = True
    cost_model_hash: str | None = None
    # I/O.
    checkpoint_path: str | None = None
    tournament_checkpoint_path: str | None = None
    death_ledger_path: str | None = None
    # Avant-garde exploration budget (Rank 4).
    avant_garde_runs: int = 20
    avant_garde_population: int = 8
    avant_garde_generations: int = 1
    avant_garde_min_rows: int = 400
    avant_garde_max_seconds: float = 30.0
    # R24/R25 — trade-denominated slices and the exploration budget fraction.
    avant_garde_trade_target: int = doctrine.AVANT_GARDE_TRADE_TARGET
    avant_garde_budget_fraction: float = doctrine.AVANT_GARDE_BUDGET_FRACTION
    # Total genome-evaluations the run may spend (army + scouts split by R25).
    evaluation_budget: int = 20_000
    # R33 (Phase 4b) — THE SOVEREIGN PEN. When ``authored_bodies`` is non-empty,
    # the runtime runs each self-written body through the cage and feeds its
    # positive-net survivors to the council as evidence (never a rank). The
    # number of bodies is itself bounded by ``authored_bodies_budget``.
    authored_bodies: tuple[str, ...] = ()
    authored_bodies_budget: int = 0
    authored_min_net_r: float = 0.0
    authored_max_rows: int = 1500
    # R26 — muster generation counter for the reserve rotation schedule.
    rotation_step: int = 0
    # The veto's decision threshold (Phase 3.2).
    veto_threshold: float = 0.5
    # R38 (Phase 5) — RAMS survivability certification. When required, a council
    # seat needs a passing certificate supplied by the operator (keyed by
    # signature). Default False keeps the sealed 3.x crowning behavior.
    require_survivability_certificate: bool = False
    survivability_certificates: tuple = ()
    # R39 (Phase 6a) — DUAL SELECTION on the main army tournament. The scouts
    # (avant-garde micro-runs) stay clean-only: they are exploration, not crowns.
    dual_selection: bool = True
    # Soldier cap (Rank 3 headcount law).
    soldier_cap: int = roster_mod.RANK_COUNTS[roster_mod.SOLDIERS]

    def signature(self) -> str:
        """Identity of a pyramid run (stop conditions and I/O paths excluded)."""
        payload = asdict(self)
        for stop in (
            "max_wallclock_seconds", "generations", "checkpoint_path",
            "tournament_checkpoint_path", "death_ledger_path",
            "avant_garde_runs", "avant_garde_max_seconds",
            "evaluation_budget", "authored_bodies_budget",
        ):
            payload.pop(stop, None)
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class PyramidResult:
    """The full record of a pyramid run (persisted verbatim by the tool)."""

    config_hash: str
    config: dict
    seed: int
    tournament: dict                 # TournamentResult.to_dict()
    roster: dict                     # PyramidRoster.to_dict()
    council: dict                    # CouncilState.to_dict()
    trust: dict                      # scores + probation
    avant_garde: dict                # findings digest + candidate count
    brain: dict                      # oracle AOS distribution + veto audit (3.2)
    authored: dict                   # R33 self-written body evidence (4b)
    death_summary: dict
    empty_seats: int
    partial: bool
    stopped_reason: str
    wallclock_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)

    def muster_report(self) -> str:
        """The human muster report (council state, roster, trust, ledger, scouts)."""
        r = self.roster
        c = self.council
        lines: list[str] = []
        lines.append("=" * 72)
        lines.append("THE MUSTER — Phase 3.2 (the seven hundred + the Oracle)")
        lines.append("=" * 72)
        counts = r["counts"]
        struct = r["structural"]
        lines.append(
            f"RANKS   oracle={counts['oracle']}/{struct['The Oracle']}  "
            f"priests={counts['priests']}/{struct['High Priests']}  "
            f"generals={counts['generals']}/{struct['Generals']}  "
            f"soldiers={counts['soldiers']}/{struct['Soldiers']}  "
            f"avant-garde={counts['avant_garde']}/{struct['Avant-Garde']}  "
            f"spectres={counts['spectres']}/{struct['Spectre Researchers']}"
        )
        lines.append(
            f"SOLDIER VACANCIES: {r['soldier_vacancies']} "
            f"(seats reality did not fill — reported, never defaulted)"
        )
        lines.append(f"SOLDIERS BY DOMAIN: {r['soldiers_by_domain']}")
        lines.append(
            f"GENERALS: {len(r['active_generals'])} active (one per pair) + "
            f"{r['reserve_generals']} reserve"
        )
        lines.append("")
        lines.append(f"COUNCIL OF SEVEN — seats filled: {c['seats_filled']}/7, "
                     f"empty: {c['empty_seats']}")
        lines.append(f"  promotion bar: {c['promotion_bar']:.3f}  trials: {c['trials']}  "
                     f"book_ok: {c['book_ok']}")
        for seat in c["seats"]:
            if seat is None:
                lines.append("  seat: EMPTY")
            else:
                lines.append(
                    f"  seat {seat['seat']}: {seat['family']} LB={seat['wilson_lb']:.3f} "
                    f"netR={seat['net_r']:.1f} n={seat['trades']}"
                )
        for note in c["notes"]:
            lines.append(f"  note: {note}")
        lines.append("")
        lines.append(f"TRUST — scored: {len(self.trust['scores'])}, "
                     f"probation: {len(self.trust['probation'])}")
        if self.trust["probation"]:
            lines.append(f"  PROBATION LIST: {self.trust['probation']}")
        lines.append("")
        ag = self.avant_garde
        lines.append(f"AVANT-GARDE — micro-runs: {ag['runs_done']}, "
                     f"candidates fed upward: {ag['candidates']}, "
                     f"unfound slices: {ag.get('unfound_slices', 0)}")
        lines.append(f"  slice quota (R24): {ag.get('trade_target')} trades; "
                     f"scout evals spent: {ag.get('scout_evals_spent')} "
                     f"(budget {ag.get('scout_evals_budget')})")
        lines.append(f"  best glimpsed: {ag['best_family']} LB={ag['best_lb']:.3f}")
        lines.append("")
        br = self.brain
        lines.append("THE ORACLE + THE VETO — Phase 3.2")
        lines.append(f"  AOS scored: {br['scored']}  mean={br['aos_mean']:.3f}  "
                     f"min={br['aos_min']:.3f}  max={br['aos_max']:.3f}")
        lines.append(f"  acolyte misses: {br['missing_total']} (dropped, never faked)")
        lines.append(f"  UNCALIBRATED v1 — AOS is a ranking, not a probability "
                     f"(calibration -> Phase 3.3)")
        va = br["veto_audit"]
        lines.append(f"  VETO — threshold: {va['threshold']:.2f}  "
                     f"vetoed: {va['vetoed_total']}  passed: {va['passed_total']}")
        lines.append(f"  would-have-won-but-vetoed: {va['would_have_won_but_vetoed']}  "
                     f"would-have-lost-and-vetoed: {va['would_have_lost_and_vetoed']}")
        lines.append(f"  false-veto-rate: {va['false_veto_rate']:.3f}")
        if va["vetoed_by_family"]:
            lines.append(f"  vetoed by family: {va['vetoed_by_family']}")
        lines.append("")
        lines.append(f"DEATH LEDGER: {self.death_summary}")
        lines.append(f"partial={self.partial}  reason={self.stopped_reason}  "
                     f"wallclock={self.wallclock_seconds:.1f}s")
        return "\n".join(lines)


def _split(F: fr.Frames, frac: float) -> tuple[fr.Frames, fr.Frames]:
    n = len(F.m15)
    k = int(n * frac)
    train = fr.build_frames(F.m15.iloc[:k], F.pair, F.pip)
    test = fr.build_frames(F.m15.iloc[k:], F.pair, F.pip)
    return train, test


def _slice_frames(F: fr.Frames, start: int, rows: int) -> fr.Frames:
    return fr.build_frames(F.m15.iloc[start:start + rows], F.pair, F.pip)


def _find_signal_rows(F: fr.Frames, probe: StrategyGenome) -> list[int]:
    """The exec-bar indices where ``probe`` generates a raw signal opportunity.

    Reads the family's OWN raw call (the ``family_raw`` stage of the sealed
    switchboard) — before the shared gate stack. This is the honest measure of
    exploration OPPORTUNITY: a slice must span enough market action for a family to
    have something to trade, independent of any one genome's filters (the point of
    exploration is to discover WHICH filters work). The tournament still applies the
    full gate stack. Returns causal indices (ascending).
    """
    from app.quant.signals import FAMILY_SIGNALS as _REG  # local: sealed registry
    fn = _REG.get(probe.family)
    if fn is None:
        return []
    rl, rs = fn(probe, ev.SignalContext(F, F.pair, F.pip))
    ridx = np.flatnonzero(np.asarray(rl, dtype=bool) | np.asarray(rs, dtype=bool))
    return [int(i) for i in ridx]


def _assemble_trade_slice(
    F: fr.Frames, target: int
) -> "tuple[fr.Frames | None, int, str, bool]":
    """R24 — assemble a slice that reaches ``target`` trade opportunities.

    Scans the probe families and takes the one with the MOST RAW opportunities
    (the family's pre-gate call — independent of any one genome's filters):

    * ``best >= target`` -> a window ending at the LAST opportunity, spanning the
      most recent ``target`` opportunities PLUS the gate stack's warmup lead-in
      (without that lead-in the whole window sits inside warmup and trades
      nothing). ``met=True``.
    * ``0 < best < target`` -> the FULL available history: take every bar rather
      than skip, because a truncated stub is the very thing that starved
      exploration. ``met=False``, shortfall reported.
    * ``best == 0`` -> ``(None, 0, reason, False)``: genuinely UNFOUND (no probe
      fires here), reported loudly — never a silent skip.

    Returns ``(slice_frames, signals, reason, quota_met)``.
    """
    n = len(F)
    if n <= 1:
        return None, 0, "pair has too few exec bars to slice", False
    best_probe = None
    best_idx: list[int] = []
    for probe in seed_mod.build_seeds().values():
        idx = _find_signal_rows(F, probe)
        if len(idx) > len(best_idx):
            best_idx = idx
            best_probe = probe
    if not best_idx:
        return None, 0, "no probe family fires on this pair (unfound slice)", False
    # The gate stack suppresses every bar in the warmup horizon (~844 exec bars),
    # so a slice MUST carry that many lead-in bars or it can trade nothing at all.
    from app.quant.signals import required_warmup_bars
    warmup = required_warmup_bars(best_probe) if best_probe is not None else 0
    if len(best_idx) >= target:
        # Anchor on the most recent ``target`` raw opportunities and prepend the
        # warmup lead-in, so the slice is trade-denominated AND past the horizon.
        end_i = best_idx[-1]
        start_i = max(0, best_idx[len(best_idx) - target] - warmup)
        sub = _m15_window(F, start_i, end_i)
        if sub is not None and len(sub) >= 2:
            return fr.build_frames(sub, F.pair, F.pip), target, "found", True
    # Fewer signals than the quota: use the WHOLE series (never a truncated stub).
    reason = (
        f"quota {target} not reachable on this pair (best {len(best_idx)} signals); "
        f"exploring the full available history instead of a shortened slice"
    )
    return fr.build_frames(F.m15, F.pair, F.pip), len(best_idx), reason, False


def _m15_window(F: fr.Frames, start_i: int, end_i: int):
    """The native M15 rows between exec indices ``start_i`` and ``end_i`` (causal).

    Exec and M15 are different grids; the window is taken by TIMESTAMP so the slice
    is a true contiguous span of native bars, right-edge inclusive of the closing
    bar. Returns ``None`` if the span cannot be located.
    """
    ts = F.exec["ts"].to_numpy()
    if start_i < 0 or end_i >= len(ts):
        return None
    t0, t1 = int(ts[start_i]), int(ts[end_i])
    mts = F.m15["ts"].to_numpy()
    mask = (mts >= t0) & (mts <= t1)
    sub = F.m15.loc[mask]
    return sub if len(sub) >= 2 else None


def _run_avant_garde(
    universe: dict[str, fr.Frames],
    config: PyramidConfig,
    *,
    scout_evals: int | None = None,
) -> tuple[dict, list[StrategyGenome]]:
    """Rank 4: bounded micro-tournaments on TRADE-denominated slices (R24/R25).

    Deterministic: the slice assembly and the micro-tournament seeds derive from
    the pyramid seed and the scout's seat index, so the same run reproduces the
    same findings. Scouts have NO live vote — their survivors are returned as
    CANDIDATES for upward feeding, not as soldiers.

    R24: a slice is assembled to reach ``avant_garde_trade_target`` trade
    opportunities. The opportunity measure is the probe family's RAW call (before
    the shared gate stack) and the slice carries the warmup lead-in, so the slice
    is trade-denominated and actually tradeable; ``min_trades`` is untouched. An
    UNFOUND slice is reported (never silently shrunk).

    R25: the scouts consume at most ``scout_evals`` genome-evaluations, computed by
    the caller from the sealed budget fraction (default: unlimited when None).
    A micro-run costs ``population * generations`` evaluations.
    """
    pairs = sorted(universe)
    findings: list[dict] = []
    candidates: list[StrategyGenome] = []
    best_family = ""
    best_lb = 0.0
    runs_done = 0
    unfound = 0
    quota_short = 0
    evals_spent = 0
    cost_per_run = max(
        1, config.avant_garde_population * max(1, config.avant_garde_generations)
    )
    target = int(config.avant_garde_trade_target)

    for seat in range(max(0, config.avant_garde_runs)):
        if scout_evals is not None and evals_spent + cost_per_run > scout_evals:
            break  # R25 — the scouts never overrun their sealed budget
        pair = pairs[seat % len(pairs)]
        F = universe[pair]
        micro, found, reason, met = _assemble_trade_slice(F, target)
        if micro is None:
            unfound += 1
            findings.append({
                "seat": seat, "pair": pair, "unfound": True,
                "reason": reason, "signals": found,
            })
            continue
        quota_short += 0 if met else 1
        rng = random.Random((config.seed * 1_000_003) ^ (seat * 7919))
        micro_universe = {pair: micro}
        micro_cfg = TournamentConfig(
            pairs=(pair,),
            population=config.avant_garde_population,
            generations=config.avant_garde_generations,
            elite=max(1, config.avant_garde_population // 4),
            min_trades=1,
            streak_kill=config.streak_kill,
            train_frac=config.train_frac,
            seed=rng.randint(0, 10**9),
            max_wallclock_seconds=config.avant_garde_max_seconds,
            top_n_test=1,
            use_costs=config.use_costs,
            checkpoint_path=None,
            death_ledger_path=None,  # scouts do not pollute the main ledger
        )
        res = run_tournament(micro_cfg, micro_universe, test_frames=None, resume=False)
        runs_done += 1
        evals_spent += cost_per_run
        lead = res.leaderboard[0] if res.leaderboard else None
        if lead and lead["wilson_lb"] > best_lb:
            best_lb = lead["wilson_lb"]
            best_family = lead["family"]
        for g in res.final_population_genomes[:4]:
            candidates.append(StrategyGenome.from_dict(g))
        findings.append({
            "seat": seat, "pair": pair, "unfound": False,
            "trade_target": target, "quota_met": met, "signals": found,
            "reason": reason,
            "leaderboard": [
                {"family": r["family"], "wilson_lb": r["wilson_lb"],
                 "net_r": r["net_r"]}
                for r in res.leaderboard
            ],
            "trials": res.trials,
        })
    digest = {
        "runs_requested": config.avant_garde_runs,
        "runs_done": runs_done,
        "candidates": len(candidates),
        "unfound_slices": unfound,
        "quota_short_slices": quota_short,
        "trade_target": target,
        "scout_evals_budget": scout_evals,
        "scout_evals_spent": evals_spent,
        # A short signature sample proves the candidates are real DNA (fed upward),
        # not just a count. The full pool is available to the caller.
        "candidate_signatures": [g.signature() for g in candidates[:8]],
        "best_family": best_family,
        "best_lb": best_lb,
        "findings": findings,
    }
    return digest, candidates


def _run_authored(
    universe: dict[str, fr.Frames],
    config: PyramidConfig,
) -> dict:
    """R33 — run self-written bodies through the cage; report evidence only.

    Each body's source is validated, judged (static gate -> sandbox ->
    determinism -> the four causality modes -> honest engine), and its positive-
    net survivors are counted as EVIDENCE. A body never holds a rank and never
    enters the tournament: it is the 45th family, attended-only (R32).
    """
    from app.core.pairs import PAIR_PIP
    from app.pyramid.sandbox import judge_body
    from app.pyramid.sandbox.runner import SandboxConfig

    bodies = tuple(config.authored_bodies)
    budget = int(config.authored_bodies_budget)
    if budget <= 0:
        budget = len(bodies)
    judged: list[dict] = []
    by_cause: dict[str, int] = {}
    alive = 0
    positive = 0
    for i, source in enumerate(bodies[:budget]):
        pair = sorted(universe)[i % len(universe)]
        F = universe[pair]
        m15 = F.m15.iloc[-config.authored_max_rows:].reset_index(drop=True)
        try:
            verdict = judge_body(
                source, m15, pair, PAIR_PIP[pair],
                {"family": "trend_pullback"},
                config=SandboxConfig(timeout=config.avant_garde_max_seconds),
            )
        except Exception as e:  # a body that cannot even be judged is a death
            by_cause["judge_error"] = by_cause.get("judge_error", 0) + 1
            judged.append({"pair": pair, "alive": False, "causes": ["judge_error"],
                           "detail": str(e)})
            continue
        rec = verdict.to_dict()
        rec["pair"] = pair
        judged.append(rec)
        if verdict.alive:
            alive += 1
            net = float((verdict.performance or {}).get("net_r", 0.0))
            if net > config.authored_min_net_r:
                positive += 1
        else:
            for c in verdict.causes or ["unknown"]:
                by_cause[c] = by_cause.get(c, 0) + 1
    return {
        "bodies": judged,
        "judged": len(judged),
        "alive": alive,
        "net_positive": positive,
        "by_cause": by_cause,
        "budget": budget,
        "partial": len(bodies) > budget,
    }


def run_pyramid(
    universe: dict[str, fr.Frames],
    config: PyramidConfig,
    *,
    resume: bool = True,
    clock=None,
) -> PyramidResult:
    """Run the full pyramid on ``universe`` (full history; split internally)."""
    import time as _time

    clock = clock or _time.monotonic
    start = clock()
    config_hash = config.signature()

    # R20 — only a SELECTION book may judge. Fail-closed before any work.
    if config.use_costs:
        book = costs.require_selection_book(costs.SELECTION_COST_MODEL)
        cost_hash = costs.manifest_digest(book)
        if config.cost_model_hash is not None and config.cost_model_hash != cost_hash:
            raise ValueError(
                f"cost model hash mismatch: pyramid pins {config.cost_model_hash} "
                f"but the selection book digests to {cost_hash}"
            )
    else:
        cost_hash = "diagnostic_gross"

    # 1. Split and run the honest tournament (Phase 2.3b) under the selection book.
    train, test = {}, {}
    for pair, F in universe.items():
        train[pair], test[pair] = _split(F, config.train_frac)

    tcfg = TournamentConfig(
        pairs=tuple(sorted(universe)),
        population=config.population,
        generations=config.generations,
        elite=config.elite,
        min_trades=config.min_trades,
        streak_kill=config.streak_kill,
        train_frac=config.train_frac,
        seed=config.seed,
        max_wallclock_seconds=config.max_wallclock_seconds,
        top_n_test=config.top_n_test,
        mutation_rate=config.mutation_rate,
        checkpoint_path=config.tournament_checkpoint_path,
        death_ledger_path=config.death_ledger_path,
        use_costs=config.use_costs,
        cost_model_hash=config.cost_model_hash,
        dual_selection=config.dual_selection,
    )
    tresult: TournamentResult = run_tournament(tcfg, train, test, resume=resume, clock=clock)

    # R25 — split the sealed evaluation budget: the army takes the remainder,
    # the scouts take exactly the fraction. Both are reported so the split is
    # never silent.
    army_evals, scout_evals = doctrine.split_budget(
        config.evaluation_budget, config.avant_garde_budget_fraction
    )
    total_planned_evals = max(1, config.population * max(1, config.generations))
    realized_fraction = min(1.0, scout_evals / max(1, army_evals + scout_evals))

    # 2. Seed trust from the honest mean NET R of each NET-POSITIVE survivor
    #    (R17), then muster. R21: only survivors may hold a rank — a net-negative
    #    genome is exiled, never a soldier. R26: reserves rotate by generation.
    book_trust = trust_mod.TrustBook()
    final_gen = max((g.generation for g in tresult.generations), default=0)
    for row in tresult.survivor_population:
        trades = int(row.get("trades", 0))
        mean_r = (float(row.get("net_r", 0.0)) / trades) if trades else 0.0
        book_trust.observe(str(row.get("signature", "")), mean_r, final_gen)

    survivors = [StrategyGenome.from_dict(g) for g in tresult.survivor_genomes]
    scores = book_trust.scores(final_gen)
    ros = roster_mod.muster(survivors, scores, rotation_step=config.rotation_step)

    # 3. Avant-garde exploration (Rank 4) — R24 trade-denominated slices under the
    #    R25 budget; no live vote; candidates fed upward.
    avant_digest, _candidates = _run_avant_garde(
        universe, config, scout_evals=scout_evals
    )

    # 3a. THE SOVEREIGN PEN (R33, Phase 4b) — self-written bodies, judged through
    #     the cage; evidence only, never a rank. Empty config => zero work.
    authored = _run_authored(universe, config)

    # 3b. THE ORACLE + THE VETO (Phase 3.2). The soldiers' signals flow through the
    #     priests -> Oracle AOS -> veto gate. The council still crowns only over the
    #     conservative bar; the brain is evidence, not authority.
    domain_trust: dict[str, float] = {}
    seated_domains: set[str] = set()
    for s in ros.soldiers:
        domain_trust.setdefault(s.domain, 0.0)
        domain_trust[s.domain] = max(domain_trust[s.domain], float(s.trust))
        seated_domains.add(s.domain)
    covered_pairs = {g.pair for g in ros.generals}
    book = costs.SELECTION_COST_MODEL if config.use_costs else None
    brain_report, _veto_model = brain_mod.run_brain(
        survivors, train,
        eval_cfg=ev.EvaluationConfig(
            streak_kill=config.streak_kill, cost_model=book
        ),
        trust_scores=scores,
        domain_trust=domain_trust,
        seated_domains=seated_domains,
        covered_pairs=covered_pairs,
        rotation_step=config.rotation_step,
        min_trades=config.min_trades,
        veto_threshold=config.veto_threshold,
    )

    # 4. The council convenes on the honest result. R38 — when certification is
    #    required, only certificates supplied by the operator can crown a seat.
    if config.require_survivability_certificate and config.survivability_certificates:
        cert_map = {
            str(c.get("signature", "")): dict(c)
            for c in config.survivability_certificates
        }
        state = council_mod.convene(
            tresult, certificates=cert_map, require_certificate=True
        )
    else:
        state = council_mod.convene(
            tresult,
            require_certificate=bool(config.require_survivability_certificate),
        )

    partial = tresult.partial
    stopped = tresult.stopped_reason

    ros.defensiveness = realized_fraction
    result = PyramidResult(
        config_hash=config_hash,
        config=asdict(config),
        seed=config.seed,
        tournament=tresult.to_dict(),
        roster=ros.to_dict(),
        council=state.to_dict(),
        trust=book_trust.to_dict(final_gen),
        avant_garde=avant_digest,
        brain=brain_report.to_dict(),
        authored=authored,
        death_summary=dict(tresult.death_summary),
        empty_seats=state.empty_seats,
        partial=partial,
        stopped_reason=stopped,
        wallclock_seconds=clock() - start,
    )

    # Pyramid checkpoint: records identity so a mismatched resume is detectable.
    if config.checkpoint_path:
        target = Path(config.checkpoint_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(
            {"config_hash": config_hash, "seed": config.seed,
             "empty_seats": state.empty_seats, "trials": tresult.trials},
            default=str,
        ))
        tmp.replace(target)

    return result