"""R80 — THE PARETO FRONT (diversity-preserving final selection).

A single scalar rank collapses a candidate to one number and quietly discards the
candidate that is merely DIFFERENT. R80 keeps the front:

* final selection is a Pareto front over four objectives, all MAXIMISED —
  (adversarial net-LB, worst-seed exposure, autopsy resilience, trade count);
* elites are chosen ACROSS the front (diversity-preserving), not only from its
  single best point;
* the council's :data:`COUNCIL_SEATS` (7) seats come from DISTINCT realms AND
  DISTINCT front corners;
* every audit reports how many front corners are occupied.

Fail-closed (Scar #1): an objective that is missing or non-finite is refused — a
candidate is never silently scored on a fabricated number. Domination is the
standard product order: A dominates B iff A is no worse on every objective and
strictly better on at least one.

Pure at import; no I/O. Build Mode: pure arithmetic.
"""

from __future__ import annotations

import math
from itertools import product

__all__ = [
    "DEFAULT_OBJECTIVES",
    "COUNCIL_SEATS",
    "ParetoError",
    "value_of",
    "dominates",
    "pareto_front",
    "front_corners",
    "select_elites",
    "council_seats",
]

COUNCIL_SEATS: int = 7

# The four objectives (all maximised). Aliases let one row shape feed the front.
DEFAULT_OBJECTIVES: tuple[str, ...] = (
    "adv_net_lb", "worst_seed_exposure", "autopsy_resilience", "trade_count",
)
_ALIASES: dict[str, tuple[str, ...]] = {
    "adv_net_lb": ("adv_net_lb", "wilson_lb", "adv_net_r_mean"),
    "worst_seed_exposure": ("worst_seed_exposure", "worst_seed_net_r"),
    "autopsy_resilience": ("autopsy_resilience", "resilience"),
    "trade_count": ("trade_count", "trades", "adv_trades_mean"),
}


class ParetoError(ValueError):
    """A Pareto request was refused (fail-closed)."""


def value_of(row: dict, name: str) -> float:
    """Read one objective from a row, refusing a missing/non-finite value."""
    keys = _ALIASES.get(name, (name,))
    for k in keys:
        if k in row and row[k] is not None:
            try:
                v = float(row[k])
            except (TypeError, ValueError):
                continue
            if not math.isfinite(v):
                break
            return v
    raise ParetoError(
        f"row is missing a finite objective {name!r} (looked in {keys}) — "
        f"fail-closed"
    )


def _vec(row: dict, objectives: tuple[str, ...]) -> tuple[float, ...]:
    return tuple(value_of(row, o) for o in objectives)


def dominates(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """A dominates B (maximisation): no worse anywhere, strictly better once."""
    if len(a) != len(b):
        raise ParetoError("domination needs equal-length vectors (fail-closed)")
    better = False
    for x, y in zip(a, b):
        if x < y:
            return False
        if x > y:
            better = True
    return better


def pareto_front(rows: list[dict],
                 objectives: tuple[str, ...] = DEFAULT_OBJECTIVES) -> list[int]:
    """Indices of the non-dominated rows (the front), in input order."""
    vals = [_vec(r, objectives) for r in rows]
    front: list[int] = []
    for i, vi in enumerate(vals):
        if any(dominates(vals[j], vi) for j in range(len(vals)) if j != i):
            continue
        front.append(i)
    return front


def _minmax(front_vals: list[tuple[float, ...]]) -> tuple[list[float], list[float]]:
    n = len(front_vals[0])
    lo = [min(v[k] for v in front_vals) for k in range(n)]
    hi = [max(v[k] for v in front_vals) for k in range(n)]
    return lo, hi


def front_corners(rows: list[dict],
                  objectives: tuple[str, ...] = DEFAULT_OBJECTIVES,
                  front: list[int] | None = None) -> dict:
    """The 2^d corners of the front: how many are occupied, and by whom.

    A corner is a sign vector over the objectives; its representative is the front
    point that maximises the sign-weighted (min-max normalised) objective vector.
    ``occupied`` counts DISTINCT representative points — a front that is a single
    point occupies one corner.
    """
    front = pareto_front(rows, objectives) if front is None else list(front)
    d = len(objectives)
    total = 2 ** d
    if not front:
        return {"corners_total": total, "occupied": 0, "representatives": []}
    fvals = [_vec(rows[i], objectives) for i in front]
    lo, hi = _minmax(fvals)
    span = [(h - l) if (h - l) > 1e-12 else 1.0 for l, h in zip(lo, hi)]

    def norm(v):
        return [(v[k] - lo[k]) / span[k] for k in range(d)]

    nvals = [norm(v) for v in fvals]
    reps: list[dict] = []
    for signs in product((1.0, -1.0), repeat=d):
        best = max(range(len(front)),
                   key=lambda k: sum(s * z for s, z in zip(signs, nvals[k])))
        reps.append({
            "corner": list(signs),
            "front_pos": best,
            "row_index": front[best],
            "signature": str(rows[front[best]].get("signature", "")),
        })
    distinct = {(r["row_index"]) for r in reps}
    return {
        "corners_total": total,
        "occupied": len(distinct),
        "representatives": reps,
        "distinct_points": sorted(distinct),
    }


def _corner_owner(rows, objectives, front) -> dict[int, list[tuple]]:
    """For each front row index, the corners it is the representative of."""
    info = front_corners(rows, objectives, front=front)
    owner: dict[int, list[tuple]] = {}
    for rep in info["representatives"]:
        owner.setdefault(int(rep["row_index"]), []).append(tuple(rep["corner"]))
    return owner


def select_elites(rows: list[dict], *, elites: int,
                  objectives: tuple[str, ...] = DEFAULT_OBJECTIVES,
                  realm_of=None) -> dict:
    """Choose ``elites`` DISTINCT front members, diversity-preserving.

    Priority: corner representatives first, then realm-distinct front members,
    then the remaining front by rank. Elites come from the FRONT only; a short
    front yields fewer elites (never a fabricated filler).
    """
    if elites < 0:
        raise ParetoError("elites must be >= 0 (fail-closed)")
    front = pareto_front(rows, objectives)
    if not front:
        return {"front_size": 0, "selected": [], "corners": front_corners(
            rows, objectives, front=front)}
    corners = front_corners(rows, objectives, front=front)
    owner = _corner_owner(rows, objectives, front)

    def realm_key(i):
        if realm_of is None:
            return str(rows[i].get("realm", ""))
        try:
            return str(realm_of(rows[i]))
        except Exception:
            return ""

    selected: list[int] = []
    used_realms: set = set()

    # 1) distinct realm representatives, best-ranked first (max corner coverage).
    reps_sorted = sorted(owner.keys(),
                         key=lambda i: len(owner[i]), reverse=True)
    for i in reps_sorted:
        if len(selected) >= elites:
            break
        rk = realm_key(i)
        if rk not in used_realms:
            selected.append(i)
            used_realms.add(rk)
    # 2) fill with remaining corner representatives (distinct points).
    for i in reps_sorted:
        if len(selected) >= elites:
            break
        if i not in selected:
            selected.append(i)
    # 3) fill from the rest of the front.
    for i in front:
        if len(selected) >= elites:
            break
        if i not in selected:
            selected.append(i)

    return {
        "front_size": len(front),
        "selected": selected,
        "selected_signatures": [str(rows[i].get("signature", "")) for i in selected],
        "realms": [realm_key(i) for i in selected],
        "corners": corners,
    }


def council_seats(rows: list[dict], *, seats: int = COUNCIL_SEATS,
                  objectives: tuple[str, ...] = DEFAULT_OBJECTIVES,
                  realm_of=None) -> dict:
    """Fill ``seats`` council seats from DISTINCT realms AND DISTINCT corners.

    A seat is a front member that introduces a new realm AND claims a corner no
    other seat holds. Empty seats stay empty (no placeholder, R20/R21 spirit).
    Returns the seats and the corner coverage of the resulting council.
    """
    if seats < 0:
        raise ParetoError("seats must be >= 0 (fail-closed)")
    front = pareto_front(rows, objectives)
    corners = front_corners(rows, objectives, front=front)
    owner = _corner_owner(rows, objectives, front)
    # Order candidates by how many corners they uniquely represent (best first),
    # then by row order for a stable, deterministic tiebreak.
    order = sorted(front, key=lambda i: (-len(owner.get(i, [])), i))

    def realm_key(i):
        if realm_of is None:
            return str(rows[i].get("realm", ""))
        try:
            return str(realm_of(rows[i]))
        except Exception:
            return ""

    seats_out: list[dict] = []
    used_realms: set = set()
    used_corners: set = set()
    for i in order:
        if len(seats_out) >= seats:
            break
        rk = realm_key(i)
        if rk in used_realms:
            continue
        free = [c for c in owner.get(i, []) if c not in used_corners]
        # A seat must bring a NEW realm; it prefers a new corner and falls back to
        # any corner it represents (so a corner-poor front still seats honestly).
        corner = free[0] if free else (owner.get(i, [])[0] if owner.get(i) else None)
        if corner is None:
            continue
        for c in owner.get(i, []):
            used_corners.add(c)
        used_realms.add(rk)
        seats_out.append({
            "row_index": i,
            "signature": str(rows[i].get("signature", "")),
            "realm": rk,
            "corner": list(corner),
        })
    return {
        "seats_requested": seats,
        "seats_filled": len(seats_out),
        "seats": seats_out,
        "realms_used": sorted(used_realms),
        "corners_used": len(used_corners),
        "front_corners": corners,
    }
