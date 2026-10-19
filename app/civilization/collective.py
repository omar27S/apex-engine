"""THE COLLECTIVE MODEL -- JUMP 2: from 700 minds to ONE mind.

The civilization had 700 agents thinking individually -- opinions weighed and voted.
That is an ARMY, not an ORGANISM. This module makes the One Brain truly one:

  * THE SHARED BELIEF STATE (the collective unconscious) -- individual agents'
    theories/intuitions STOP being private opinions and become CONTRIBUTIONS to a
    SHARED belief state: the collective's current model of the market (what regime,
    what works, what is dangerous, where edge lives). It is a probabilistic map --
    "the collective believes EURUSD trending (0.7 confidence, based on 12 agents'
    pattern recognition + 3's intuition + the falcon's regime flag)". When an agent
    learns something, the SHARED state updates, not just the agent's private mind;
  * THE EXPERIENCE COMMONS -- every agent's experience (trade outcomes, simulation
    accuracy, emotional calibration) feeds a COMMON pool, so pattern memory becomes
    COLLECTIVE: "we have seen this shape 340 times (across all agents)", not "I have
    seen it 47 times". The déjà-vu engine draws from the commons;
  * THE COHERENCE METRIC -- nightly, the DIVERGENCE between individual beliefs and the
    shared state is measured: high divergence = still an army, low = becoming an
    organism. The metric trends in the Letter ("coerenza collettiva: 73% (in crescita)").

Honesty is binding. An unmeasured contribution changes nothing; a coherence with no
individual beliefs is ``None`` (never a fabricated unity); the commons never invents a
recognition it did not observe. Pure at import (Scar #6): the caller supplies the
timestamp; this module never reads the wall clock.
"""

from __future__ import annotations

__all__ = [
    "COLLECTIVE_VERSION",
    "SHARED_BELIEF_MIN_CONTRIB",
    "collective",
    "belief_state",
    "contribute_belief",
    "shared_belief",
    "belief_map",
    "independent_from_series",
    "experience_commons",
    "contribute_experience",
    "commons_recognition",
    "coherence",
    "coherence_trend",
    "collective_block",
]

COLLECTIVE_VERSION: int = 1

# A shared belief needs at least this many contributing agents to be a COLLECTIVE
# belief (below it the map honestly reports the support as thin).
SHARED_BELIEF_MIN_CONTRIB: int = 3


def collective(state: dict) -> dict:
    """The collective's shared structures (created empty on first access)."""
    st = state if state is not None else {}
    return st.setdefault("collective", {
        "version": COLLECTIVE_VERSION,
        "beliefs": {},
        "commons": [],
        "coherence_history": [],
    })


def belief_state(state: dict) -> dict:
    """The SHARED belief state -- the collective's current model of the market."""
    return collective(state).setdefault("beliefs", {})


def contribute_belief(state: dict, *, pair: str, regime: str | None,
                      confidence: float | None, agent: str = "", source: str = "",
                      ts: str = "") -> dict:
    """An agent CONTRIBUTES its belief to the shared state (the collective updates).

    The shared entry for a pair blends every contribution: the regime with the most
    weighted support wins, and the confidence is the MEAN of the measured
    contributions (never invented). Honest: an unmeasured regime or confidence is
    recorded as a contribution with no number -- it does not move the blend.
    """
    p = str(pair or "").strip()
    if not p:
        return {}
    bs = belief_state(state)
    entry = bs.setdefault(p, {"contributions": [], "regime": None,
                              "confidence": None, "support": 0})
    entry["contributions"].append({
        "agent": str(agent), "source": str(source), "regime": regime,
        "confidence": (round(float(confidence), 4)
                       if isinstance(confidence, (int, float)) else None),
        "ts": str(ts),
    })
    del entry["contributions"][:-200]
    _recompute_belief(entry)
    return {"pair": p, **{k: entry[k] for k in ("regime", "confidence", "support")},
            "reading": _belief_reading(p, entry)}


def _recompute_belief(entry: dict) -> None:
    """Re-blend a shared belief from its contributions (weighted by confidence)."""
    contribs = entry.get("contributions") or []
    votes: dict[str, float] = {}
    confs: list[float] = []
    for c in contribs:
        reg = c.get("regime")
        if reg is None:
            continue
        w = c.get("confidence")
        w = float(w) if isinstance(w, (int, float)) else 1.0
        votes[str(reg)] = votes.get(str(reg), 0.0) + w
        if isinstance(c.get("confidence"), (int, float)):
            confs.append(float(c["confidence"]))
    if votes:
        entry["regime"] = max(sorted(votes), key=lambda k: votes[k])
        entry["support"] = len([c for c in contribs if c.get("regime") is not None])
    entry["confidence"] = round(sum(confs) / len(confs), 4) if confs else None


def shared_belief(state: dict, pair: str) -> dict:
    """The collective's belief for one pair (honest: absent -> unmeasured)."""
    entry = belief_state(state).get(str(pair))
    if not entry:
        return {"pair": str(pair), "regime": None, "confidence": None,
                "support": 0, "measured": False,
                "reading": f"{pair}: la collettivita' non ha una convinzione"}
    return {"pair": str(pair), "regime": entry.get("regime"),
            "confidence": entry.get("confidence"), "support": entry.get("support", 0),
            "measured": bool(entry.get("regime") is not None),
            "reading": _belief_reading(str(pair), entry)}


def _belief_reading(pair: str, entry: dict) -> str:
    reg = entry.get("regime")
    conf = entry.get("confidence")
    sup = entry.get("support", 0)
    if reg is None:
        return f"{pair}: la collettivita' non ha una convinzione"
    return (f"la collettivita' crede {pair} {reg} "
            + (f"(confidenza {conf:.0%})" if isinstance(conf, (int, float))
               else "(confidenza non misurata)")
            + f", su {sup} contributi")


def belief_map(state: dict) -> dict:
    """The collective's whole probabilistic map + its measured support."""
    bs = belief_state(state)
    rows = [{"pair": p, "regime": e.get("regime"),
             "confidence": e.get("confidence"), "support": e.get("support", 0)}
            for p, e in sorted(bs.items())]
    measured = [r for r in rows if r["regime"] is not None]
    return {"rows": rows, "n_pairs": len(rows), "n_measured": len(measured),
            "reading": (f"credo collettivo: {len(measured)} convinzioni misurate "
                        f"su {len(rows)} coppie")}


def independent_from_series(series: dict, *,
                            corr_max: float = 0.3) -> dict:
    """DEBT-062: MEASURED independence for the Cathedral's CONSENSUS column.

    The CONSENSUS column (3+ UNCORRELATED strategies agree) once accepted a bare
    ``independent: True`` claim. This computes independence from the REAL return
    series: assets whose pairwise correlation stays below ``corr_max`` are
    mutually independent; the largest such group is the ``n_independent``.
    Honest: fewer than two assets with enough aligned observations -> ``n`` is
    ``None`` (unmeasured), never a fabricated count.
    """
    from app.civilization import cascade_map as cm_mod

    s = {k: v for k, v in (series or {}).items() if isinstance(v, (list, tuple))}
    if len(s) < 2:
        return {"n": None, "assets": sorted(s), "measured": False,
                "reading": (f"consenso: indipendenza non misurata "
                            f"({len(s)} serie con dati)")}
    cm = cm_mod.correlation_matrix(s)
    assets = cm["assets"]
    matrix = cm["matrix"]
    if len(assets) < 2:
        return {"n": None, "assets": assets, "measured": False,
                "reading": "consenso: indipendenza non misurata (correlazioni assenti)"}
    # Greedy: the largest set where every pair is independent (corr below floor).
    best: list[str] = []
    for seed in assets:
        group = [seed]
        for cand in assets:
            if cand in group:
                continue
            if all((matrix[cand].get(m) is not None
                    and abs(matrix[cand][m]) < corr_max)
                   for m in group):
                group.append(cand)
        if len(group) > len(best):
            best = group
    return {"n": len(best), "assets": sorted(best), "measured": True,
            "corr_max": corr_max,
            "reading": (f"consenso: {len(best)} asset indipendenti "
                        f"(corr<{corr_max}) su {len(assets)}")}


# --- THE EXPERIENCE COMMONS ------------------------------------------------

def experience_commons(state: dict) -> list[dict]:
    """The COMMON experience pool (every agent's experience, pooled)."""
    return collective(state).setdefault("commons", [])


def contribute_experience(state: dict, *, agent: str, kind: str, shape: str = "",
                          outcome_r: float | None = None, ts: str = "") -> dict:
    """An agent's experience feeds the COMMON pool (pattern memory becomes collective).

    Honest: an unmeasured outcome is pooled as ``None`` (counted, never scored as 0R).
    """
    row = {"agent": str(agent), "kind": str(kind), "shape": str(shape),
           "outcome_r": (float(outcome_r) if isinstance(outcome_r, (int, float))
                         else None), "ts": str(ts)}
    commons = experience_commons(state)
    commons.append(row)
    del commons[:-5000]
    return row


def commons_recognition(state: dict, shape: str) -> dict:
    """The collective's recognition of a shape: "we have seen this N times".

    Honest: a shape the collective has never seen reports ``0`` occurrences (and the
    reading says so) -- never an invented familiarity.
    """
    s = str(shape or "").strip()
    if not s:
        return {"shape": "", "count": 0, "measured": False,
                "reading": "nessuna forma da riconoscere"}
    rows = [r for r in experience_commons(state) if str(r.get("shape")) == s]
    known = [r["outcome_r"] for r in rows
             if isinstance(r.get("outcome_r"), (int, float))]
    mean = round(sum(known) / len(known), 4) if known else None
    return {"shape": s, "count": len(rows), "scored": len(known), "mean_r": mean,
            "measured": bool(rows),
            "reading": (f"la civilta' ha visto questa forma {len(rows)} volte "
                        f"(su {len(set(str(r['agent']) for r in rows))} agenti)"
                        if rows else "la civilta' non ha mai visto questa forma")}


# --- THE COHERENCE METRIC --------------------------------------------------

def coherence(state: dict, individual_beliefs: list[dict] | None = None) -> dict:
    """The COHERENCE METRIC: how far individual beliefs are from the shared state.

    ``individual_beliefs`` is a list of ``{pair, regime}`` rows (one per agent's
    belief). Coherence is the share of individual beliefs that AGREE with the shared
    state, weighted equally. Honest: no individual beliefs (or no shared belief for
    the pairs they name) -> ``None`` (an unmeasured unity is never fabricated).
    """
    beliefs = list(individual_beliefs or [])
    if not beliefs:
        return {"coherence": None, "measured": False, "n": 0,
                "reading": "coerenza collettiva non misurata (nessuna convinzione individuale)"}
    bs = belief_state(state)
    agree = total = 0
    for b in beliefs:
        pair = str(b.get("pair") or "")
        reg = b.get("regime")
        shared = (bs.get(pair) or {}).get("regime")
        if reg is None or shared is None:
            continue
        total += 1
        if str(reg) == str(shared):
            agree += 1
    if not total:
        return {"coherence": None, "measured": False, "n": 0,
                "reading": "coerenza collettiva non misurata (nessun confronto possibile)"}
    coh = round(agree / total, 4)
    return {"coherence": coh, "measured": True, "n": total, "agree": agree,
            "reading": (f"coerenza collettiva: {coh:.0%} "
                        f"({agree}/{total} convinzioni allineate)")}


def coherence_trend(state: dict, *, ts: str = "") -> dict:
    """Record tonight's coherence and report the trend vs the previous night.

    Honest: a first reading has no trend (``delta`` is ``None``); an unmeasured
    coherence is not recorded at all (never a fabricated point).
    """
    hist = collective(state).setdefault("coherence_history", [])
    if not hist:
        return {"coherence": None, "delta": None, "measured": False,
                "reading": "coerenza: nessuna storia ancora"}
    latest = hist[-1]
    prev = hist[-2] if len(hist) >= 2 else None
    delta = None
    if prev and isinstance(latest.get("coherence"), (int, float)) \
            and isinstance(prev.get("coherence"), (int, float)):
        delta = round(float(latest["coherence"]) - float(prev["coherence"]), 4)
    direction = ("in crescita" if (delta or 0) > 0
                 else "in calo" if (delta or 0) < 0 else "stabile")
    return {"coherence": latest.get("coherence"), "delta": delta,
            "measured": latest.get("coherence") is not None,
            "reading": (f"coerenza collettiva: {latest['coherence']:.0%} "
                        f"({direction})" if isinstance(latest.get("coherence"),
                                                       (int, float))
                        else "coerenza collettiva non misurata")}


def collective_block(state: dict, individual_beliefs: list[dict] | None = None,
                     *, ts: str = "") -> dict:
    """The collective's block for the artifact + the Letter (honest, bounded).

    Runs a coherence reading, records it, and returns the map + the metric + the
    commons size. Honest: an unmeasured coherence is reported as such and is NOT
    appended to the history.
    """
    coh = coherence(state, individual_beliefs)
    if coh["measured"]:
        hist = collective(state).setdefault("coherence_history", [])
        hist.append({"ts": str(ts), "coherence": coh["coherence"]})
        del hist[:-400]
    trend = coherence_trend(state, ts=ts)
    bm = belief_map(state)
    commons = experience_commons(state)
    block = {
        "belief_map": bm,
        "coherence": coh["coherence"],
        "coherence_measured": coh["measured"],
        "trend": trend,
        "commons_size": len(commons),
        "measured": bm["n_measured"] > 0 or coh["measured"],
        "reading": (f"{bm['reading']}; {trend['reading']}"),
    }
    state["collective_summary"] = block
    return block
