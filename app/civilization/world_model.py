"""THE PREDICTIVE WORLD MODEL — Section B of MEGA PHASE 4 (seeing forward).

The market model (v1, in ``one_brain``) DESCRIBES the world as it is. This module
adds the missing axis: a PROBABILISTIC FORECAST for the next hours, a SCENARIO TREE
with an expected value per candidate, and a PROPHECY LEDGER that tracks every
forecast against the reality that followed -- so the civilization learns HOW GOOD
its own predictions are (calibration over time).

Honesty (the founding rule): a probability is only emitted when the evidence for it
exists. The ``basis`` field names exactly which inputs were read; a missing input
narrows the basis and is never silently invented. Probabilities are transparent
heuristics over measured inputs -- labelled as such, never a black-box oracle.

Pure at import (Scar #6): the readings are data; the functions reduce. No I/O, no
clock, no RNG.
"""

from __future__ import annotations

__all__ = [
    "forecast",
    "scenario_tree",
    "prophecy_entry",
    "score_prophecy",
    "calibration",
    "PROPHECY_HORIZON_H",
]

# The CEO's ruled horizon for the hourly forecast.
PROPHECY_HORIZON_H: int = 4


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _falcon_readings(falcon: dict | None) -> dict:
    f = (falcon or {}).get("falcon") or falcon or {}
    return f.get("readings") or {}


def _falcon_macro(falcon: dict | None) -> dict:
    f = (falcon or {}).get("falcon") or falcon or {}
    return f.get("macro") or {}


def _regime_counts(civilization: dict | None) -> dict:
    return ((civilization or {}).get("regime") or {}).get("regimes") or {}


def forecast(*, falcon: dict | None, civilization: dict | None,
             horizon_h: int = PROPHECY_HORIZON_H, ts: str = "") -> dict:
    """A 4h probabilistic forecast: P(trend up), P(regime shift), P(major move).

    Built ONLY from present evidence: the falcon's per-pair velocity (a directional
    push), the regime census (how much of the field is dead/ranging -- a shift is
    likelier when the field is unstable), and the macro DXY (a directional push).
    Every input actually read is named in ``basis``; with no evidence the forecast
    is honest zeros + ``measured=False``.
    """
    readings = _falcon_readings(falcon)
    macro = _falcon_macro(falcon)
    counts = _regime_counts(civilization)
    basis: list[str] = []

    # Directional momentum: the mean tick velocity sign across pairs.
    velocities = []
    for pair, r in readings.items():
        if isinstance(r, dict) and r.get("tick_velocity") is not None:
            velocities.append(float(r["tick_velocity"]))
    dxy_dir = None
    dxy = macro.get("DXY") if isinstance(macro, dict) else None
    if isinstance(dxy, dict) and dxy.get("value") is not None and dxy.get("prev") is not None:
        try:
            dxy_dir = 1 if float(dxy["value"]) > float(dxy["prev"]) else (
                -1 if float(dxy["value"]) < float(dxy["prev"]) else 0)
        except (TypeError, ValueError):
            dxy_dir = None

    if velocities:
        basis.append("falcon.velocity")
    if dxy_dir is not None:
        basis.append("macro.DXY")
    if counts:
        basis.append("regime.census")

    measured = bool(basis)
    if not measured:
        return {"horizon_h": horizon_h, "p_trend_up": None, "p_regime_shift": None,
                "p_major_move": None, "basis": [], "measured": False, "ts": ts,
                "reading": "previsione non misurata: nessuna prova disponibile"}

    # P(trend up): a positive net push (velocity + DXY) raises it above 0.5.
    push = 0.0
    if velocities:
        mean_v = sum(velocities) / len(velocities)
        push += _clamp(mean_v / 4.0, -1.0, 1.0)          # velocity ~[0,4] typical
    if dxy_dir is not None:
        push += 0.4 * dxy_dir
    p_up = _clamp(0.5 + 0.15 * push, 0.05, 0.95)

    # P(regime shift): the fraction of the field that is dead or ranging.
    unstable = 0
    total = 0
    for k, v in counts.items():
        total += int(v or 0)
        if k in ("dead", "ranging", "volatile", "choppy", "chop"):
            unstable += int(v or 0)
    frac_unstable = (unstable / total) if total else 0.0
    p_shift = _clamp(0.15 + 0.5 * frac_unstable, 0.02, 0.9)

    # P(major move > 1 ATR): the mean pair volatility, normalized.
    vols = [float(r.get("volatility_pips") or 0.0)
            for r in readings.values() if isinstance(r, dict)]
    mean_vol = (sum(vols) / len(vols)) if vols else 0.0
    p_major = _clamp(0.2 + mean_vol / 20.0, 0.05, 0.9)

    return {
        "horizon_h": horizon_h,
        "p_trend_up": round(p_up, 3),
        "p_regime_shift": round(p_shift, 3),
        "p_major_move": round(p_major, 3),
        "basis": basis,
        "measured": True,
        "ts": ts,
        "reading": (f"4h: P(trend up)={p_up:.2f}, P(cambio regime)={p_shift:.2f}, "
                    f"P(mossa >1 ATR)={p_major:.2f} [{'+'.join(basis)}]"),
    }


def scenario_tree(*, candidate: dict, forecast_: dict,
                  win_rate: float | None = None, ts: str = "") -> dict:
    """A 3-branch scenario tree for one candidate, with its expected value.

    Branch A -- price continues to target  -> +target/stop R
    Branch B -- price reverses at 1R       -> -1 R
    Branch C -- price consolidates (time exit) -> +0.3 R

    The branch probabilities come from the forecast (P(trend up) and P(regime shift))
    and the strategy's measured win rate when available; honest ``None`` EV when the
    candidate carries no stop/target (nothing to compute).
    """
    stop = candidate.get("stop_distance")
    target = candidate.get("target_distance")
    if not stop or not target:
        return {"branches": [], "ev_r": None, "measured": False, "ts": ts,
                "reading": "albero di scenario non misurato: stop/target assenti"}

    rr = abs(float(target) / float(stop)) if float(stop) else None
    p_up = forecast_.get("p_trend_up")
    p_shift = forecast_.get("p_regime_shift")
    # Fall back to the strategy's measured win rate when the forecast is blind.
    p_cont = p_up if p_up is not None else win_rate
    if p_cont is None:
        return {"branches": [], "ev_r": None, "measured": False, "ts": ts,
                "reading": "albero di scenario non misurato: nessuna probabilita'"}
    p_cont = _clamp(0.5 * p_cont + 0.5 * (win_rate if win_rate is not None else p_cont))
    p_rev = _clamp(0.35 + 0.4 * (p_shift or 0.0))
    p_cons = _clamp(1.0 - p_cont - p_rev, 0.0, 1.0)
    # Renormalize so the three branches sum to 1 (honest: a partition).
    s = p_cont + p_rev + p_cons
    p_cont, p_rev, p_cons = (p_cont / s, p_rev / s, p_cons / s) if s else (0, 0, 1)

    branches = [
        {"branch": "A", "what": "prezzo verso il target", "p": round(p_cont, 3),
         "r": round(rr, 3) if rr is not None else None},
        {"branch": "B", "what": "prezzo inverte a 1R", "p": round(p_rev, 3), "r": -1.0},
        {"branch": "C", "what": "consolidamento (uscita a tempo)", "p": round(p_cons, 3),
         "r": 0.3},
    ]
    ev = sum(b["p"] * (b["r"] or 0.0) for b in branches)
    return {"branches": branches, "ev_r": round(ev, 3), "measured": True, "ts": ts,
            "reading": f"EV atteso {ev:+.2f}R su 3 rami"}


def prophecy_entry(*, forecast_: dict, ts: str = "", key: str = "") -> dict:
    """One logged prophecy (a forecast awaiting its verdict)."""
    return {"ts": ts, "key": key, "horizon_h": forecast_.get("horizon_h"),
            "p_trend_up": forecast_.get("p_trend_up"),
            "p_regime_shift": forecast_.get("p_regime_shift"),
            "p_major_move": forecast_.get("p_major_move"),
            "basis": forecast_.get("basis") or [],
            "realized": None, "verdict": None}


def score_prophecy(entry: dict, *, realized: dict | None) -> dict:
    """Attach the realized outcome to a prophecy and mark the verdict.

    ``realized`` may carry ``trend_up`` (bool), ``regime_shift`` (bool), and
    ``major_move`` (bool). The verdict credits each branch that called it correctly
    (a probability >= 0.5 that matched, or < 0.5 that did not happen).

    R117 -- THE PROPHECY'S MIRROR: the verdict alone is a coin's honesty (a
    0.51 that came true and a 0.99 that came true both "hit"); the BRIER
    score is the probability's honesty -- the mean squared gap between each
    spoken probability and the 0/1 that happened (0 = a prophet, 0.25 = a
    coin, worse = confidence without sight). Both ride the entry: the
    verdict for the ear, the Brier for the truth.
    """
    if not realized:
        return entry
    hits: list[bool] = []
    sq: list[float] = []
    checks = (("p_trend_up", "trend_up"), ("p_regime_shift", "regime_shift"),
              ("p_major_move", "major_move"))
    for pkey, rkey in checks:
        p = entry.get(pkey)
        r = realized.get(rkey)
        if p is None or r is None:
            continue
        hits.append((p >= 0.5) == bool(r))
        sq.append((float(p) - (1.0 if r else 0.0)) ** 2)
    entry["realized"] = realized
    entry["verdict"] = (round(sum(hits) / len(hits), 3) if hits else None)
    entry["brier"] = (round(sum(sq) / len(sq), 4) if sq else None)
    return entry


def calibration(entries: list[dict]) -> dict:
    """Aggregate the prophecy ledger into a calibration reading.

    Honest: only SCORED prophecies count; with none, the hit rate is None (never a
    fabricated 0% or 100%). R117: the mean Brier rides beside the hit rate --
    the hit rate says how often the coin landed, the Brier says how much the
    probabilities deserved to be believed.
    """
    scored = [e for e in entries if e.get("verdict") is not None]
    if not scored:
        return {"n": 0, "hit_rate": None, "mean_brier": None,
                "reading": "calibrazione non misurata"}
    hit = sum(float(e["verdict"]) for e in scored) / len(scored)
    briers = [float(e["brier"]) for e in scored
              if isinstance(e.get("brier"), (int, float))]
    mean_brier = (round(sum(briers) / len(briers), 4) if briers else None)
    reading = (f"profezie: {len(scored)} giudicate, accuratezza {hit:.0%}"
               + (f", Brier {mean_brier:.3f} (0 profeta / 0.25 moneta)"
                  if mean_brier is not None else ""))
    return {"n": len(scored), "hit_rate": round(hit, 3),
            "mean_brier": mean_brier, "reading": reading}
