"""THE SIGNAL GENERATOR -- the bridge from thought to the PRESENT (Mega Phase 1, A1).

Until now the civilization THOUGHT: it evolved strategies on historical tape and
scored them, but no survivor ever asked the LIVE market "would you enter RIGHT NOW?".
This module is that bridge. Given the SURVIVING strategies and the REAL frames whose
last bar is the most recent CLOSED bar, it evaluates each strategy's own entry
conditions through :func:`app.quant.signals.dispatch` -- strictly CAUSALLY, on the last
closed bar only -- and, when a strategy WOULD enter, it births a SIGNAL CANDIDATE.

A candidate is NOT a trade: it is a question put to the Cathedral. Every candidate
(whether the Cathedral later accepts or rejects it) is logged in the CANDIDATE
REGISTRY with its full metadata and, once the market resolves, with what ACTUALLY
happened -- so even a refused signal becomes forward-test evidence.

Honesty is binding:
  * a strategy that does not fire on the last closed bar yields NO candidate (never a
    fabricated entry);
  * the geometry is DERIVED from the strategy's own genes (``sl_atr_mult`` x ATR(14),
    ``target_rr`` x risk) -- the same geometry the engine would book;
  * an unmeasured confidence is ``None`` (never an invented probability);
  * this module is PURE at import (Scar #6): the frames, the readings and the
    timestamp come from the caller; no wall clock, no I/O here.
"""

from __future__ import annotations

from app.quant.signals import SignalContext, dispatch

__all__ = [
    "CANDIDATE_VERSION",
    "build_candidate",
    "generate_candidates",
    "recover_genomes",
    "frames_from_tape",
    "signals",
    "record_candidate",
    "resolve_candidate",
    "candidate_block",
]

CANDIDATE_VERSION: int = 1

# The registry keeps at most this many candidates (bounded, honest).
REGISTRY_KEEP: int = 400


def signals(state: dict) -> dict:
    """The signal registry's persistent structures (created empty on first access)."""
    st = state if state is not None else {}
    return st.setdefault("signals", {
        "version": CANDIDATE_VERSION,
        "candidates": [],       # every candidate, accepted or rejected
        "last": None,           # the last generation block
        "next_id": 1,           # the monotone candidate id
    })


def _stop_geometry(genome, frames) -> tuple[float | None, float | None]:
    """The strategy's stop/target distances (in price) from its OWN genes.

    ``stop_distance = sl_atr_mult x ATR(14)`` (the law-letter M15 ATR, aligned to the
    execution bar); ``target_distance = target_rr x stop_distance``. Honest: a NaN or
    non-positive ATR yields ``(None, None)`` -- no fabricated geometry.
    """
    atr = getattr(frames, "atr", None)
    try:
        import numpy as np

        last_atr = float(np.asarray(atr)[-1]) if atr is not None and len(atr) else None
    except Exception:  # noqa: BLE001
        last_atr = None
    mult = getattr(genome, "sl_atr_mult", None)
    rr = getattr(genome, "target_rr", None)
    if not isinstance(last_atr, float) or last_atr <= 0 or not isinstance(mult, (int, float)):
        return None, None
    stop = float(mult) * last_atr
    target = (float(rr) * stop) if isinstance(rr, (int, float)) else None
    return (round(stop, 8) if stop > 0 else None,
            round(target, 8) if isinstance(target, float) and target > 0 else None)


def build_candidate(genome, frames, *, pair: str, ts: str = "",
                    score: float | None = None,
                    strategy_id: str | None = None,
                    statarb_z=None) -> dict | None:
    """Evaluate ONE strategy on the last CLOSED bar; return a candidate or ``None``.

    Strictly causal: the entry conditions are read at the final execution bar only
    (the frames end at the most recent closed bar by construction).
    """
    if frames is None or len(frames) == 0:
        return None
    ctx = SignalContext(frames, str(pair), getattr(frames, "pip", 1e-4),
                        statarb_z=statarb_z)
    long_m, short_m, _funnel = dispatch(genome, ctx)
    try:
        import numpy as np

        last_long = bool(long_m[-1]) if len(long_m) else False
        last_short = bool(short_m[-1]) if len(short_m) else False
    except Exception:  # noqa: BLE001
        return None
    if last_long == last_short:          # neither, or ambiguous -> no candidate
        return None
    direction = 1 if last_long else -1
    close = frames.exec["close"].to_numpy()
    entry = float(close[-1]) if len(close) else None
    stop_d, target_d = _stop_geometry(genome, frames)
    sig = strategy_id
    if not sig:
        try:
            sig = genome.signature()
        except Exception:  # noqa: BLE001
            sig = ""
    fam = getattr(genome, "family", None)
    return {
        "strategy_id": str(sig),
        "family": fam,
        "pair": str(pair),
        "direction": direction,
        "entry_price": entry,
        "stop_distance": stop_d,
        "target_distance": target_d,
        "timestamp": str(ts),
        "confidence_from_strategy": (float(score) if isinstance(score, (int, float))
                                     else None),
        "ts": str(ts),
    }


def generate_candidates(genomes, frames_by_pair, *, readings: dict | None = None,
                        ts: str = "", max_per_pair: int = 20) -> list[dict]:
    """Birth every candidate the surviving strategies imply on the LIVE tape.

    ``genomes`` is a list of ``StrategyGenome`` OR ``{genome, score}`` dicts (the
    survivors, best first). ``frames_by_pair`` maps a pair to its REAL
    :class:`~app.quant.frames.Frames`. A pair with no frames contributes nothing
    (honest blindness). Bounded to ``max_per_pair`` candidates per pair.
    """
    out: list[dict] = []
    pairs = list((frames_by_pair or {}).keys())
    counted: dict[str, int] = {}
    for g in (genomes or []):
        if isinstance(g, dict) and "genome" in g:
            genome, score = g.get("genome"), g.get("score")
        else:
            genome, score = g, None
        if genome is None:
            continue
        for pair in pairs:
            if counted.get(pair, 0) >= max_per_pair:
                continue
            cand = build_candidate(genome, frames_by_pair.get(pair), pair=pair,
                                   ts=ts, score=score)
            if cand is not None:
                out.append(cand)
                counted[pair] = counted.get(pair, 0) + 1
    return out


def recover_genomes(report: dict) -> tuple[list[dict], list[str], str]:
    """Reconstruct the strategies to evaluate from the report, HONEST about source.

    Preferred: the report's ``final_population_genomes`` (the survivor DNA the night
    committed). Then the committed leaderboard's signatures, matched against the SEED
    pool. When NO DNA is recoverable, the SEED POOL is returned as a PROVISIONAL
    standing set (``source='seed_fallback'``) so the live channel is operational
    tonight; the next tournament commits the survivor DNA and the generator then asks
    the REAL survivors. A leaderboard signature with no recoverable DNA is named in
    ``unrecovered`` -- never invented.

    Returns ``([{genome, score}], unrecovered, source)``.
    """
    from app.quant.genome import StrategyGenome

    out: list[dict] = []
    if report.get("final_population_genomes"):
        for g in report["final_population_genomes"]:
            try:
                out.append({"genome": StrategyGenome.from_dict(g), "score": None})
            except (ValueError, TypeError):
                continue
        if out:
            return out, [], "report_genomes"

    try:
        from app.quant import seeds as seeds_mod

        pool = seeds_mod.build_seeds()
    except Exception:  # noqa: BLE001
        pool = {}
    by_sig = {g.signature(): g for g in pool.values()}

    unrecovered: list[str] = []
    for r in (report.get("leaderboard") or []):
        sig = str(r.get("signature") or "")
        if not sig:
            continue
        g = by_sig.get(sig)
        if g is None:
            unrecovered.append(sig)
            continue
        score = r.get("adv_lb", r.get("wilson_lb"))
        out.append({"genome": g,
                    "score": float(score) if isinstance(score, (int, float)) else None})

    if out:
        return out, unrecovered, "leaderboard_seeds"

    fallback = [{"genome": g, "score": None} for g in pool.values()]
    return fallback, unrecovered, "seed_fallback"


def frames_from_tape(pair: str, *, data_dir: str = "data/history",
                     tail: int = 12000):
    """Build the live Frames for ``pair`` from the tape tail (``None`` when blind)."""
    from app.core import data as data_mod
    from app.quant import frames as frames_mod

    for cand in (f"{data_dir}/{pair}_M15.parquet", f"data/{pair}_M15.parquet"):
        try:
            df = data_mod.load_parquet(cand)
        except Exception:  # noqa: BLE001 - no tape -> honest blindness
            continue
        m15 = df.tail(tail).reset_index(drop=True)
        try:
            return frames_mod.build_frames(m15, pair, 1e-4)
        except Exception:  # noqa: BLE001
            return None
    return None


def _candidate_id(state: dict) -> int:
    s = signals(state)
    n = int(s.get("next_id") or 1)
    s["next_id"] = n + 1
    return n


def record_candidate(state: dict, candidate: dict, *, accepted: bool | None = None,
                     gate_class: str | None = None, ts: str = "") -> dict:
    """Log a candidate (accepted or rejected) in the registry, with its metadata.

    The registry is the FORWARD-TEST EVIDENCE BASE: every candidate is kept so that,
    once the market resolves, its hypothetical outcome can be attached. Honest: the
    entry stores only what was measured (``accepted``/``gate_class`` may be ``None``
    until the Cathedral has spoken).
    """
    s = signals(state)
    rec = {**dict(candidate or {}),
           "id": _candidate_id(state),
           "recorded_ts": str(ts),
           "accepted": (bool(accepted) if accepted is not None else None),
           "gate_class": gate_class,
           "resolved": False,
           "outcome_r": None,
           "direction_moved": None}
    s["candidates"].append(rec)
    del s["candidates"][:-REGISTRY_KEEP]
    return rec


def resolve_candidate(state: dict, candidate_id: int, *, outcome_r: float | None,
                      direction_moved: bool | None = None, ts: str = "") -> dict | None:
    """Attach what ACTUALLY happened to a candidate once the market resolved it.

    Honest: an unmeasured outcome leaves ``outcome_r`` ``None`` (never invented); the
    candidate is marked resolved only when a real outcome is supplied.
    """
    s = signals(state)
    for rec in s["candidates"]:
        if int(rec.get("id") or -1) == int(candidate_id):
            rec["resolved"] = isinstance(outcome_r, (int, float))
            rec["outcome_r"] = (float(outcome_r) if isinstance(outcome_r, (int, float))
                                else None)
            rec["direction_moved"] = direction_moved
            rec["resolved_ts"] = str(ts)
            return rec
    return None


def candidate_block(state: dict) -> dict:
    """The registry's block for the Letter: how many signals were evaluated TODAY.

    Renders the honest counts: total evaluated, accepted (CLASS A), rejected, and how
    many have a hypothetical (resolved) outcome so far.
    """
    s = signals(state)
    cands = s.get("candidates") or []
    total = len(cands)
    accepted = sum(1 for c in cands if c.get("accepted") is True)
    rejected = sum(1 for c in cands if c.get("accepted") is False)
    pending = sum(1 for c in cands if c.get("accepted") is None)
    resolved = sum(1 for c in cands if c.get("resolved"))
    hypothetical = sum(1 for c in cands if isinstance(c.get("outcome_r"), (int, float)))
    reading = (f"SEGNALI VALUTATI OGGI: {total} "
               f"({accepted} accettati, {rejected} rifiutati, {hypothetical} risultati "
               f"ipotetici)"
               if total else "SEGNALI VALUTATI OGGI: 0 (nessun candidato dal vivo)")
    return {"version": CANDIDATE_VERSION, "has_state": isinstance(state, dict),
            "total": total, "accepted": accepted, "rejected": rejected,
            "pending": pending, "resolved": resolved, "hypothetical": hypothetical,
            "candidates": cands[-20:], "reading": reading,
            "measured": total > 0}
