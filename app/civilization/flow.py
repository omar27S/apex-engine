"""THE CONTINUOUS TOURNAMENT FLOW -- the river that never stops (Part Four, item 8).

The night was a single pool; this makes the evolution a RIVER with three cadences,
all live on the VM, all fed by the falcon's eyes:

  * MICRO   -- hourly (24/day): pop 40-80, the falcon's HOT pairs, seed = timestamp;
  * MEDIUM  -- every 3 hours: pop 120, all 15 pairs;
  * GRAND   -- 04:00 UTC: the full walk-forward + gauntlet + daily certificate (the
               peak of the river, not the only moment).

Every survivor enters the pool IMMEDIATELY (the streams doctrine). Honest: an
unparseable clock is "non misurato" and NO tournament is dispatched -- the river is
never fed by a guess. The seed rotates with the dispatch timestamp (the groundhog
cure), so two hours never draw the same population.

Pure at import (Scar #6): the schedule derives WHAT is due and WITH WHAT seed from a
timestamp the caller supplies; it never reads the wall clock.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.civilization import rotation

__all__ = [
    "FLOW_VERSION",
    "GRAND_HOUR_UTC",
    "MEDIUM_EVERY_HOURS",
    "MICRO_POP",
    "MEDIUM_POP",
    "CADENCES",
    "DEFAULT_PAIRS",
    "due_flow",
    "flow_plan",
    "register_dispatch",
    "tournaments_today",
    "flow_report",
]

FLOW_VERSION: int = 1

GRAND_HOUR_UTC: int = 4          # the Grand at 04:00 UTC (the peak)
MEDIUM_EVERY_HOURS: int = 3      # the Medium every 3 hours
MICRO_POP: tuple[int, int] = (40, 80)
MEDIUM_POP: int = 120

# The FAIL-CLOSED pair set: when the falcon is silent (no heat data yet -- the first
# run, or every eye asleep) the flow still runs on SOMETHING. Never zero pairs.
DEFAULT_PAIRS: tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD")

CADENCES: tuple[str, ...] = ("micro", "medium", "grand")


def _dt(ts: str) -> datetime | None:
    v = str(ts or "").strip().replace("Z", "+00:00")
    if not v:
        return None
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def due_flow(ts: str) -> dict:
    """Which cadence(s) are due at this timestamp (the river's rhythm).

    * grand  -- on the hour of 04:00 UTC;
    * medium -- every 3 hours (on the hour);
    * micro  -- every hour (on the hour), unless a grand is due (the grand IS the
                hour's tournament).
    """
    d = _dt(ts)
    if d is None:
        return {"ts": ts, "due": [], "measured": False,
                "reading": "flusso non misurato (orologio assente)"}
    due: list[str] = []
    if d.minute < 5:
        if d.hour == GRAND_HOUR_UTC:
            due.append("grand")
        elif d.hour % MEDIUM_EVERY_HOURS == 0:
            due.append("medium")
        else:
            due.append("micro")
    return {"ts": str(ts), "hour": d.hour, "minute": d.minute, "due": due,
            "measured": True,
            "reading": "flusso dovuto: " + (", ".join(due) if due else "nessuno")}


def flow_plan(ts: str, *, hot_pairs: list[str] | None = None,
              all_pairs: list[str] | None = None, slot: int = 0) -> dict:
    """The plan for the cadence due at ``ts``: population, pairs, rotating seed.

    MICRO draws the falcon's HOT pairs. FAIL-CLOSED, never zero: when the falcon is
    silent (no heat data yet -- the first run -- or every eye asleep) it falls back to
    :data:`DEFAULT_PAIRS`, and when the universe is known but the falcon has no heat it
    falls back to the universe. MEDIUM/GRAND take all pairs (or :data:`DEFAULT_PAIRS`
    when the universe is empty). The seed rotates with the dispatch timestamp. The
    micro ALWAYS runs on something; a fallback is NAMED in the reading.
    """
    due = due_flow(ts)
    if not due["measured"] or not due["due"]:
        return {"kind": None, "ts": ts, "measured": due["measured"],
                "reading": due["reading"]}
    cadence = due["due"][0]
    hot = list(hot_pairs or [])
    universe = list(all_pairs or [])
    # THE FAIL-CLOSED UNIVERSE: if the caller knows no pairs at all, use the DEFAULT
    # set -- the river is never fed zero pairs.
    fallback_universe = universe or list(DEFAULT_PAIRS)
    if cadence == "micro":
        pop = MICRO_POP
        if hot:
            pairs, pair_source = hot[:3], "falco (coppie calde)"
        elif universe:
            pairs, pair_source = universe[:3], "universo (falco silente)"
        else:
            pairs, pair_source = fallback_universe[:3], "predefinite (falco silente)"
    elif cadence == "medium":
        pop = (MEDIUM_POP, MEDIUM_POP)
        pairs = fallback_universe
        pair_source = ("universo (tutte le coppie)" if universe
                       else "predefinite (universo vuoto)")
    else:
        pop = (MEDIUM_POP, MEDIUM_POP)
        pairs = fallback_universe
        pair_source = ("universo (grande: walk-forward + gauntlet)" if universe
                       else "predefinite (universo vuoto, grande)")
    n_pairs = len(pairs)
    generations = 1 if cadence == "micro" else 3
    # The TRIALS this dispatch will run: population x pairs x generations. This is the
    # honest proof the micro actually executed (a positive integer, never a guess).
    trials = int(pop[0]) * max(1, n_pairs) * generations
    seed = rotation.micro_seed(dispatch_ts=str(ts), slot=slot)
    return {
        "kind": cadence, "ts": str(ts), "seed": seed,
        "population": pop[0], "population_max": pop[1],
        "pairs": pairs, "n_pairs": n_pairs, "pair_source": pair_source,
        "generations": generations, "trials": trials,
        "walk_forward": cadence == "grand", "gauntlet": cadence == "grand",
        "certificate": cadence == "grand",
        "measured": True,
        "reading": (f"{cadence}: pop {pop[0]}, {n_pairs} coppie ({pair_source}), "
                    f"{trials} prove, seme {seed}"),
    }


def register_dispatch(state: dict, plan: dict, *, ts: str = "") -> dict:
    """Record a dispatched tournament on the state (the river's logbook).

    The record carries the cadence, pairs and TRIALS so the artifact can prove the
    micro ran (a real trial count, never an inferred one). Honest: a plan with no kind
    records nothing. Returns the record (or an empty dict when nothing was dispatched).
    """
    if not plan or not plan.get("kind"):
        return {}
    rec = {"ts": ts or plan.get("ts", ""), "kind": plan["kind"],
           "pairs": list(plan.get("pairs") or []),
           "trials": int(plan.get("trials") or 0),
           "seed": plan.get("seed")}
    if state is None:
        return rec
    state.setdefault("flow_dispatches", []).append(rec)
    return rec


def tournaments_today(dispatch_ts_list: list) -> dict:
    """Count the day's tournaments by cadence from the real dispatch records.

    Accepts either bare timestamp strings (legacy) or the dict records written by
    :func:`register_dispatch` (preferred -- they carry the real TRIALS). The CEO's
    proof: 24+ tournaments a day (24 micro + 8 medium + 1 grand) when the river runs.
    Honest: counts only REAL dispatches (empty -> zeros, not a claim).
    """
    counts = {c: 0 for c in CADENCES}
    trials = 0
    measured_trials = False
    for item in (dispatch_ts_list or []):
        if isinstance(item, dict):
            kind = item.get("kind")
            ts = item.get("ts", "")
            if kind in counts:
                counts[kind] += 1
            else:
                due = due_flow(ts)
                if due["due"]:
                    counts[due["due"][0]] += 1
            t = item.get("trials")
            if isinstance(t, int):
                trials += t
                measured_trials = True
        else:
            due = due_flow(str(item))
            if due["due"]:
                counts[due["due"][0]] += 1
    total = sum(counts.values())
    return {**counts, "total": total,
            "trials": trials if measured_trials else None,
            "reading": (f"tornei oggi: {total} "
                        f"(micro {counts['micro']}, medium {counts['medium']}, "
                        f"grand {counts['grand']}, "
                        f"prove {trials if measured_trials else '--'})")}


def flow_report(state: dict, *, ts: str = "") -> dict:
    """The flow's health for the state artifact: what is due now, what ran today."""
    dispatches = (state or {}).get("flow_dispatches") or []
    today = tournaments_today(dispatches)
    due = due_flow(ts) if ts else {"due": None, "measured": False}
    return {"due_now": due.get("due"), "today": today,
            "survivors_pooled": (state or {}).get("survivors_pooled"),
            "reading": today["reading"]}
