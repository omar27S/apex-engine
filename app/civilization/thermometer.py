"""THE STATE THERMOMETER -- one health index (0-100), computed from real readings.

Part Three of the Ascension. The civilization needs ONE number that says how
healthy it is, and a breakdown that shows WHY. The index is a WEIGHTED COMPOSITE
of six axes, each read from a real artifact the caller hands in -- never invented:

    paying      -- the share of strategies that are net-positive (the edge is real)
    learning    -- the E1 generativity trend (are we getting better at learning?)
    network     -- the conversation quality (signal vs noise; helpful exchanges)
    coverage    -- exploration coverage (realms actually colonized)
    body        -- the body's utilization (is the machine working, or idle?)
    economy     -- the economy's vitality (is reputation actually flowing?)

The weights are themselves EVOLVABLE: :func:`evolve_weights` nudges them toward the
axes that moved the index most, so the state learns what health MEANS to it. An
axis the artifacts cannot measure is DROPPED from the composite (its weight is
redistributed) and named in the breakdown -- never assumed to be 0 or 1.

Pure at import (Scar #6): a reduction over the caller's blocks.
"""

from __future__ import annotations

__all__ = [
    "AXES",
    "DEFAULT_WEIGHTS",
    "health_index",
    "thermometer",
    "evolve_weights",
    "band",
]

# The six axes (id -> human label). Frozen order: the Letter prints them in it.
AXES: tuple[tuple[str, str], ...] = (
    ("paying", "strategie paganti (net-positive)"),
    ("learning", "velocita' di apprendimento (E1)"),
    ("network", "qualita' della conversazione (rete)"),
    ("coverage", "copertura dell'esplorazione (regni)"),
    ("body", "utilizzazione del corpo"),
    ("economy", "vitalita' dell'economia"),
)

# The standing weights (sum to 1.0). Evolvable -- see :func:`evolve_weights`.
DEFAULT_WEIGHTS: dict[str, float] = {
    "paying": 0.30,
    "learning": 0.20,
    "network": 0.10,
    "coverage": 0.15,
    "body": 0.15,
    "economy": 0.10,
}


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _clamp01(v):
    return max(0.0, min(1.0, float(v)))


def band(index: float | None) -> str:
    """The honest band of an index in [0, 100]."""
    if index is None:
        return "non misurato"
    if index >= 80:
        return "fiorente"
    if index >= 60:
        return "in salute"
    if index >= 40:
        return "in crescita"
    if index >= 20:
        return "fragile"
    return "critico"


def _axes_from(report: dict, *, civilization: dict, body: dict,
               queue: dict) -> dict[str, tuple[float | None, str]]:
    """Each axis in [0,1] (or None) WITH the evidence it rests on."""
    r = report or {}
    civ = civilization or {}
    b = body or {}
    q = queue or {}
    d = civ.get("diary") if isinstance(civ.get("diary"), dict) else {}

    out: dict[str, tuple[float | None, str]] = {}

    # paying: share of leaderboard rows that are net-positive.
    lb = r.get("leaderboard") or []
    nets = [x.get("adv_net_r", x.get("net_r")) for x in lb]
    nets = [n for n in nets if isinstance(n, (int, float))]
    if nets:
        out["paying"] = (sum(1 for n in nets if n > 0) / len(nets),
                         f"{sum(1 for n in nets if n > 0)}/{len(nets)} net-positive")
    else:
        out["paying"] = (None, "nessun leaderboard nel report")

    # learning: the E1 generativity trend (0=stalled, 1=improved, 0.5=steady).
    e1 = ((r.get("amendment") or {}).get("E1_meta_learning") or {})
    trend = str(e1.get("trend") or e1.get("reading") or "").lower()
    if "improved" in trend or "salita" in trend:
        out["learning"] = (1.0, f"E1: {e1.get('reading') or 'improved'}")
    elif "stall" in trend or "fermo" in trend:
        out["learning"] = (0.2, f"E1: {e1.get('reading') or 'stalled'}")
    elif "regress" in trend or "calo" in trend:
        out["learning"] = (0.0, f"E1: {e1.get('reading') or 'regressed'}")
    elif trend:
        out["learning"] = (0.5, f"E1: {e1.get('reading') or trend}")
    else:
        out["learning"] = (None, "il report non porta l'amendment E1")

    # network: signal vs noise -- the share of exchanges that are RELEVANT/URGENT.
    net = civ.get("network") or {}
    messages = _num(net.get("messages"))
    if messages is None and isinstance(net.get("by_kind"), dict):
        messages = sum(int(v) for v in net["by_kind"].values())
    useful = 0
    if isinstance(net.get("by_kind"), dict):
        useful = sum(int(net["by_kind"].get(k, 0))
                     for k in ("decision", "answer", "help"))
    if messages:
        out["network"] = (useful / messages,
                          f"{useful}/{messages} scambi utili (decisione/risposta/aiuto)")
    else:
        out["network"] = (None, "la rete non ha scambi misurati")

    # coverage: the realm coverage (mean), from the curiosity map or the report.
    cmap = civ.get("curiosity") or d.get("curiosity") or {}
    realms = cmap.get("realms") or cmap.get("instincts") or []
    covs = [c.get("coverage") for c in realms if isinstance(c.get("coverage"), (int, float))]
    if covs:
        out["coverage"] = (_clamp01(sum(covs) / len(covs)),
                           f"copertura media {round(sum(covs)/len(covs), 3)} "
                           f"su {len(covs)} regni")
    else:
        pareto = ((r.get("measurements") or {}).get("R80_pareto") or {})
        occ, tot = pareto.get("occupied"), pareto.get("corners_total")
        if isinstance(occ, (int, float)) and isinstance(tot, (int, float)) and tot:
            out["coverage"] = (_clamp01(occ / tot), f"pareto {occ}/{tot}")
        else:
            out["coverage"] = (None, "nessuna mappa dei regni")

    # body: utilization (fraction).
    util = _num(b.get("util_pct"))
    if util is None:
        out["body"] = (None, "il corpo non ha misurato l'utilizzazione")
    else:
        out["body"] = (_clamp01(util / 100.0), f"utilizzazione {util}%")

    # economy: reputation actually flowing -- the attention granted + earned this cycle.
    econ = civ.get("economy") or {}
    granted = econ.get("granted")
    earned = econ.get("earned")
    if isinstance(granted, dict) and granted:
        total = sum(float(v) for v in granted.values() if isinstance(v, (int, float)))
        e = sum(float(v) for v in (earned or {}).values()
                if isinstance(v, (int, float)))
        # full health when the flow is non-trivial; scale the flow against a
        # reasonable per-cycle ceiling (the number of agents x the max allowance).
        ceiling = max(1.0, len(granted) * 1.0)
        out["economy"] = (_clamp01((total + e) / ceiling),
                          f"attenzione concessa {round(total,2)}, guadagnata {round(e,2)}")
    else:
        out["economy"] = (None, "l'economia non ha concesso attenzione questo ciclo")

    return out


def thermometer(report: dict, *, civilization: dict | None = None,
                body: dict | None = None, queue: dict | None = None,
                weights: dict[str, float] | None = None) -> dict:
    """The health index (0-100) + its full breakdown, from the real readings."""
    w = dict(weights or DEFAULT_WEIGHTS)
    axes = _axes_from(report, civilization=civilization or {}, body=body or {},
                      queue=queue or {})
    measured = {k: v for k, v in axes.items() if v[0] is not None}
    breakdown = []
    total_w = sum(w.get(k, 0.0) for k in measured)
    index = None
    if measured and total_w > 0:
        acc = 0.0
        for k, (val, why) in axes.items():
            if val is None:
                breakdown.append({"axis": _label(k), "id": k, "value": None,
                                  "weight": 0.0, "contribution": None,
                                  "why": why})
                continue
            eff_w = w.get(k, 0.0) / total_w
            contrib = eff_w * val
            acc += contrib
            breakdown.append({"axis": _label(k), "id": k, "value": round(val, 3),
                              "weight": round(eff_w, 3),
                              "contribution": round(contrib * 100.0, 2),
                              "why": why})
        index = round(acc * 100.0, 1)
    reading = (f"indice {index}/100 ({band(index)}); "
               f"{len(measured)}/{len(AXES)} assi misurati")
    return {
        "index": index,
        "band": band(index),
        "breakdown": breakdown,
        "weights": {k: round(w.get(k, 0.0), 3) for k in w},
        "measured_axes": sorted(measured),
        "reading": reading,
        "why": (None if index is not None
                else "nessun asse misurabile: il report non porta leaderboard, "
                     "amendment, rete, regni, corpo o economia"),
    }


def _label(axis_id: str) -> str:
    for k, label in AXES:
        if k == axis_id:
            return label
    return axis_id


def evolve_weights(weights: dict[str, float], *, breakdown: list[dict],
                   learning_rate: float = 0.05) -> dict[str, float]:
    """Nudge the weights toward the axes that contributed most (the state learns).

    The axes with the highest contribution gain weight; the weakest lose it. The
    result is re-normalized to sum to 1.0. Bounded (``learning_rate``) so the
    meaning of health cannot lurch in one night.
    """
    contribs = {b["id"]: b.get("contribution") for b in breakdown
                if b.get("contribution") is not None}
    if not contribs:
        return dict(weights)
    hi = max(contribs.values())
    lo = min(contribs.values())
    span = (hi - lo) or 1.0
    out = {}
    for k, v in weights.items():
        if k in contribs:
            norm = (contribs[k] - lo) / span  # 0..1
            out[k] = v * (1.0 + learning_rate * (norm - 0.5) * 2.0)
        else:
            out[k] = v
    s = sum(out.values()) or 1.0
    return {k: round(v / s, 6) for k, v in out.items()}


def health_index(report: dict, **kw) -> float | None:
    """Convenience: just the index (for a quick reading)."""
    return thermometer(report, **kw).get("index")
