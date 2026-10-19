"""E1 (Cure 4) -- THE GENERATIVITY LEDGER: a durable memory of how we learn.

E1's original wound was amnesia: ``meta_learning_audit`` compared the current
generativity against the SAME baseline every night, so it could only ever print
"steady". This module gives E1 a MEMORY: each night's per-mechanism generativity
reading is computed from the night's REAL report fields and APPENDED to a durable,
committed history. E1 then compares tonight against the stored prior, so it can
finally detect improvement, stalls, and regressions -- and print a TREND.

Generativity is the degree to which a learning mechanism's output DRIVES A
BEHAVIOUR CHANGE (0 = records and changes nothing, 1 = every reading moves the
search). Each mechanism's reading is a reduction over the report the caller hands
it; a mechanism the report cannot measure is left absent (never assumed).

Pure at import (Scar #6): the history is data; the functions reduce. The caller
owns the file I/O (:func:`load_history` / :func:`append_history`).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.state import failure_law as _failure

__all__ = [
    "HISTORY_VERSION",
    "reading_from_report",
    "trend",
    "load_history",
    "append_history",
    "latest_prior",
]

HISTORY_VERSION: int = 1


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def reading_from_report(report: dict, *, failures: list[dict] | None = None) -> dict[str, float]:
    """Each learning mechanism's generativity TONIGHT, from the REAL report (E1).

    Every reading is derived from a concrete, measured report field -- never a
    constant:

    * ``autopsy``   -- the mean autopsy resilience of the finalists (how sharply
      the autopsy signal separates clean deaths from fixable ones);
    * ``tribunal``  -- majority survivors / trials (the share of the field the
      tribunal certified);
    * ``eda``       -- 1 - Pareto coverage (the novelty the search still holds);
    * ``surrogate`` -- the surrogate flight's hit rate (the share of its skips that
      were true negatives);
    * ``probation`` -- 1.0 when a probation ruling actually cut the quota (it
      changed behaviour), else 0.0;
    * ``bootstrap`` -- 1 - bugs/registered (the share of failures that changed
      behaviour, the E2 reading made continuous).

    A mechanism the report cannot measure is OMITTED (unmeasured, never assumed).
    """
    r = report or {}
    out: dict[str, float] = {}

    rows = r.get("final_population") or r.get("leaderboard") or []
    res = [float(x["resilience"]) for x in rows
           if isinstance(x, dict) and _num(x.get("resilience")) is not None]
    if res:
        out["autopsy"] = round(sum(res) / len(res), 6)

    trials = _num(r.get("trials"))
    ranked = _num(r.get("majority_survivors"))
    if trials and trials > 0 and ranked is not None:
        out["tribunal"] = round(min(1.0, ranked / trials), 6)

    meas = (r.get("measurements") or {}).get("R80_pareto") or {}
    occupied = meas.get("occupied")
    total = meas.get("corners_total")
    if _num(occupied) is not None and _num(total):
        out["eda"] = round(max(0.0, 1.0 - float(occupied) / float(total)), 6)

    sf = r.get("surrogate_flight") or {}
    if isinstance(sf, dict) and _num(sf.get("hit_rate")) is not None:
        out["surrogate"] = round(min(1.0, max(0.0, float(sf["hit_rate"]))), 6)

    prob = r.get("probation") or {}
    if isinstance(prob, dict) and prob.get("ruling"):
        # Generativity = the ruling CHANGED behaviour (it cut the quota), not merely
        # that it was computed. A pending ruling changed nothing (0.0).
        out["probation"] = 1.0 if prob["ruling"].get("triggered") else 0.0

    if failures is not None:
        e2 = _failure.failure_law_report(failures)
    else:
        e2 = ((r.get("amendment") or {}).get("E2_failure_law") or {})
    reg = _num(e2.get("failures_registered"))
    changed = _num(e2.get("failures_that_changed_behaviour"))
    if reg and reg > 0 and changed is not None:
        out["bootstrap"] = round(changed / reg, 6)

    return out


def trend(history: list[dict], *, mechanism: str | None = None) -> dict:
    """The generativity TREND over the stored history (E1, Cure 4).

    Compares the most recent reading against the earliest stored reading. With a
    ``mechanism`` it trends that one; without it, it trends the MEAN of every
    mechanism present in both ends. Fewer than two measured points is honestly
    ``"non misurato"`` (there is no trend yet), never a fabricated zero.
    """
    readings: list[dict] = []
    for entry in history or []:
        r = entry.get("reading") if isinstance(entry, dict) else None
        if isinstance(r, dict) and r:
            readings.append(r)
    if len(readings) < 2:
        return {"mechanism": mechanism, "prior": None, "current": None,
                "delta": None, "direction": "non misurato",
                "reading": "trend non misurato (servono >= 2 notti)"}

    def _val(rd: dict):
        if mechanism is not None:
            return rd.get(mechanism)
        vals = [v for v in rd.values() if _num(v) is not None]
        return round(sum(vals) / len(vals), 6) if vals else None

    prior = _val(readings[0])
    current = _val(readings[-1])
    if prior is None or current is None:
        return {"mechanism": mechanism, "prior": prior, "current": current,
                "delta": None, "direction": "non misurato",
                "reading": "trend non misurato (il meccanismo manca a un estremo)"}
    delta = round(current - prior, 6)
    if delta > 0.01:
        direction = "in salita"
    elif delta < -0.01:
        direction = "in calo"
    else:
        direction = "piatto"
    return {
        "mechanism": mechanism, "prior": prior, "current": current, "delta": delta,
        "direction": direction,
        "reading": f"generativita' {direction} {delta:+.3f}",
    }


def load_history(path: str | Path) -> list[dict]:
    """Read the committed generativity history (a JSON list); corrupt -> empty."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("nights") or []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def append_history(path: str | Path, reading: dict, *, date: str = "",
                   cap: int = 400) -> list[dict]:
    """Append tonight's reading to the history (append-only, bounded).

    The last ``cap`` nights are kept so the file never grows without bound; the
    reading is stored verbatim so a future audit can re-derive every trend.
    """
    history = load_history(path)
    history.append({"version": HISTORY_VERSION, "date": date,
                    "reading": {k: float(v) for k, v in (reading or {}).items()}})
    history = history[-cap:]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(history, indent=2) + "\n")
    return history


def latest_prior(path: str | Path) -> dict | None:
    """The most recent stored reading -- the PRIOR E1 compares tonight against."""
    history = load_history(path)
    if not history:
        return None
    r = history[-1].get("reading")
    return {k: float(v) for k, v in r.items()} if isinstance(r, dict) else None
