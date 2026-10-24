"""LAW 1 (Physical Might) -- THE INFINITE QUEUE (zero dead minutes, forever).

The Council decides WHAT to think; the body must always have something to DO. This
module is the work queue: a continuous list of jobs the machine drains one after
another with a near-zero gap, refilled by (a) the Council's decisions (a funded
idea becomes a burst job) and (b) a STANDING WORK MENU that the Guardians top up
whenever the queue runs low -- so the queue NEVER runs dry.

The menu (heavy -> light): a tournament shift, an evaluation batch, an author
micro-session (the Author works 24/7 too), result-memory pre-heat, a backfill
harvest, and heartbeat/maintenance. Work is armor: a busy box is a box Oracle
never reclaims. Idle is existential risk.

Pure at import (Scar #6): the queue is a list the caller owns; these functions
append, order, pop and digest. No I/O, no clock beyond the timestamps passed in.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "WORK_KINDS",
    "HEAVY_KINDS",
    "LIGHT_KINDS",
    "MENU",
    "TARGET_DEPTH",
    "LANES",
    "lane_of",
    "work_item",
    "enqueue",
    "from_council",
    "spontaneous_item",
    "fuel_pump",
    "realm_scout_items",
    "refill",
    "cognitive_balance",
    "refill_balanced",
    "pick_next",
    "pick_next_dual",
    "gaps_seconds",
    "queue_report",
]

# The standing work menu: (kind, what, weight, why). Heavier work has a lower
# weight so it is drained first while the machine is cool. MORE BUZZ (Part Four):
# more author slots, more backfill, more evaluation batches -- the body kept at its
# true measured maximum.
MENU: tuple[tuple[str, str, int, str], ...] = (
    ("tournament_shift", "run a bounded tournament shift over the resident tapes",
     0, "the private road runs hot: shifts are the civilization's heavy work"),
    ("evaluation_batch", "evaluate a batch of pending candidates", 1,
     "pending evaluations must not accumulate"),
    ("backfill_harvest", "re-judge historical near-misses (2.5-2.9x) under the "
     "realistic cost book", 2, "harvest what the old cost book wrongly rejected"),
    ("author_micro", "author + judge 2-3 fresh bodies through the full cage", 3,
     "the Author works 24/7 too: light slots always invent"),
    ("realm_scout", "send scouts into an unknown realm (coverage < 0.15)", 3,
     "darkness becomes territory: the realm hunter colonizes the unknown"),
    ("library_hunt", "hunt + spoliate a public document into testable hypotheses", 3,
     "the giants' wisdom is free to read: bring it into the cage"),
    ("cache_preheat", "pre-heat result-memory before the next shift", 4,
     "a warm cache makes the next shift cheaper"),
    ("vision", "render a requested market view for an agent (on-demand seeing)", 3,
     "the market as photograph: any mind may ask to SEE (THE GAZE)"),
    ("heartbeat_maintenance", "heartbeat + maintenance", 5,
     "the pulse is measured; the body is kept healthy"),
)

WORK_KINDS: tuple[str, ...] = tuple(k for k, *_ in MENU)
HEAVY_KINDS: frozenset[str] = frozenset({"tournament_shift", "evaluation_batch"})
LIGHT_KINDS: frozenset[str] = frozenset({"author_micro", "realm_scout",
                                         "library_hunt", "cache_preheat",
                                         "vision",
                                         "heartbeat_maintenance"})
# Keep at least this many jobs queued so the machine never waits for work.
TARGET_DEPTH: int = 6

# THE DOUBLE TRACK (Part Four): evolution (improve what exists) and exploration
# (scout the unknown) run ALWAYS in parallel -- two lanes, never alternating. Every
# menu kind belongs to exactly one lane.
LANES: tuple[str, ...] = ("evolution", "exploration")
_LANE_OF: dict[str, str] = {
    "tournament_shift": "evolution",
    "evaluation_batch": "evolution",
    "backfill_harvest": "evolution",
    "cache_preheat": "evolution",
    "vision": "exploration",
    "heartbeat_maintenance": "evolution",
    "author_micro": "exploration",
    "realm_scout": "exploration",
    "library_hunt": "exploration",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def work_item(kind: str, *, what: str, why: str, weight: int = 3,
              source: str = "menu", ts: str = "", extra: dict | None = None) -> dict:
    """One queued job, WITH its reason (the queue is fed by decisions, not whims)."""
    if kind not in WORK_KINDS and kind != "council_burst":
        raise ValueError(f"unknown work kind {kind!r}; known: {WORK_KINDS}")
    if not str(why).strip():
        raise ValueError("a queued job without a reason is noise -- the WHY is mandatory")
    item = {"kind": kind, "what": what, "why": why, "weight": int(weight),
            "source": source, "ts": ts or _now()}
    if extra:
        item.update(extra)
    return item


def lane_of(kind: str) -> str:
    """The lane a work kind belongs to (evolution or exploration)."""
    return _LANE_OF.get(kind, "evolution")


# THE FREEDOM DOCTRINE (Part Three, item 11): ANY agent, at ANY moment, may ask for
# work -- a thought, a vision, an idea, a dream, a challenge. No permission, no
# slot. A spontaneous request names its ACT and its WHY; the queue accepts it from
# any mind at any time. The act decides which kind of work it becomes.
SPONTANEOUS_ACTS: dict[str, str] = {
    "think": "author_micro",       # a thought / a written body
    "vision": "vision",            # a request to SEE
    "idea": "author_micro",        # a proposed idea (forged like a micro-session)
    "dream": "cache_preheat",      # a dream / consolidation
    "challenge": "evaluation_batch",  # challenge a belief -> re-evaluate
    "explore": "realm_scout",      # enter the unknown
}


def spontaneous_item(*, agent: str, act: str, why: str, ts: str = "") -> dict:
    """A SPONTANEOUS act by a free agent -> a queue item (Part Three, item 11).

    Fail-closed on an unknown act (the freedom is bounded by the real menu, never a
    fabricated job). The item carries ``spontaneous=True`` and its ``agent`` so the
    engagement metric can tell voluntary work from assigned work.
    """
    if act not in SPONTANEOUS_ACTS:
        raise ValueError(f"unknown spontaneous act {act!r}; known: "
                         f"{sorted(SPONTANEOUS_ACTS)}")
    if not str(why).strip():
        raise ValueError("a spontaneous act without a WHY is noise -- the reason "
                         "is mandatory (freedom is not whim)")
    kind = SPONTANEOUS_ACTS[act]
    return work_item(kind, what=f"spontaneous {act} by {agent}", why=str(why),
                     source="spontaneous", ts=ts,
                     extra={"spontaneous": True, "agent": str(agent), "act": act})


def fuel_pump(queue: list[dict], *, idea: str, why: str, trials: int | None = None,
              ts: str = "") -> dict:
    """THE FUEL PUMP (Part Four): a market-funded idea fires its burst IMMEDIATELY.

    Zero delay between decision and execution: the funded idea becomes a queued
    burst with the TOP priority (weight -2, ahead of the heaviest shift), so the
    next drain runs it first. The WHY is mandatory (a burst with no reason is noise).
    """
    item = work_item("council_burst", what=f"burst for: {idea}", why=why,
                     weight=-2, source="market", ts=ts,
                     extra={"trials": trials, "idea": idea})
    enqueue(queue, item)
    return item


def realm_scout_items(unknown_realms: list[str], *, ts: str = "") -> list[dict]:
    """THE REALM HUNTER (Part Four): scout every realm with coverage < 0.15."""
    out = []
    for r in unknown_realms:
        out.append(work_item(
            "realm_scout", what=f"scout the unknown realm {r}",
            why=f"coverage of {r} is below the empty threshold 0.15 -- "
                f"darkness becomes territory", weight=3, source="realm_hunter",
            ts=ts, extra={"realm": r, "lane": "exploration"}))
    return out


def enqueue(queue: list[dict], item: dict) -> dict:
    """Append a job to the queue."""
    queue.append(item)
    return item


def from_council(decisions: list[dict], *, ts: str = "") -> list[dict]:
    """Turn the Council's decisions into queued work (bursts as inspiration).

    A ``forge_burst`` decision becomes a burst job sized by the Council; a
    ``cure_family`` decision becomes its TREATMENT (R147: a targeted burst on the
    sick family's own space — the cure was once a ledger line that changed
    nothing, ceremony without treatment; now every cure buys the family a real,
    bounded look, and the course counts these receipts). The other decision kinds
    are captured by the Council's own ledger and do not enqueue work here (they
    change the world, not the queue). A MARKET-funded idea takes the separate
    ``fuel_pump`` path (top priority), so this one keeps its Council origin.
    """
    out: list[dict] = []
    for d in decisions or []:
        if d.get("kind") == "forge_burst":
            trials = d.get("trials")
            out.append(work_item(
                "council_burst", what=d.get("what", "council burst"),
                why=d.get("why", "the Council decided"), weight=-1,
                source="council", ts=(d.get("ts") or ts),
                extra={"trials": trials, "idea": d.get("idea")}))
        elif d.get("kind") == "cure_family":
            # R147 — the treatment burst: a cure that never touches the queue
            # cured nothing. Bounded (the hunch's look, 200 trials) and deduped
            # by the daemon's whole-item check while it stays pending.
            out.append(work_item(
                "council_burst",
                what=f"treatment for the family {d.get('family', '?')}",
                why=str(d.get("why") or "the Council decided"),
                weight=-1, source="council", ts=(d.get("ts") or ts),
                extra={"trials": int(d.get("trials") or 200),
                       "idea": f"treatment for the family {d.get('family', '?')}",
                       "family": d.get("family"), "course": d.get("course"),
                       "treatment": True}))
    return out


def refill(queue: list[dict], *, ts: str = "",
           kinds: set[str] | None = None) -> list[dict]:
    """Top the queue up to ``TARGET_DEPTH`` from the standing menu.

    Only menu kinds not already pending are added, so a refill never floods the
    queue with duplicates. Returns the jobs added. This is the Guardians'
    guarantee: the queue NEVER runs dry.

    ``kinds`` restricts the refill to a caller's allowed set (the night shift's
    safe maintenance kinds). Without it, a body restricted to kinds that sit past
    ``TARGET_DEPTH`` in the MENU would refill only kinds it must then drop, and
    spin with nothing to do.
    """
    allowed = set(kinds) if kinds else None
    pending = {i.get("kind") for i in queue}
    added: list[dict] = []
    for kind, what, weight, why in MENU:
        if allowed is not None and kind not in allowed:
            continue
        if len(queue) + len(added) >= TARGET_DEPTH:
            break
        if kind in pending:
            continue
        added.append(work_item(kind, what=what, why=why, weight=weight,
                               source="menu", ts=ts,
                               extra={"lane": lane_of(kind)}))
    queue.extend(added)
    return added


def pick_next(queue: list[dict], *, hot: bool = False) -> dict | None:
    """Take the next job: heaviest first when cool, LIGHTEST first when hot.

    A hot machine is asked only for light work (the rhythm bends to the box); a cool
    machine drains the heavy work first. Ties break by enqueue order (stable).
    """
    if not queue:
        return None
    if hot:
        lights = [i for i in queue if i.get("kind") in LIGHT_KINDS]
        pool = lights or queue
    else:
        pool = queue
    best = min(range(len(pool)), key=lambda i: (pool[i].get("weight", 3), i))
    return queue.pop(queue.index(pool[best]))


def pick_next_dual(queue: list[dict], *, hot: bool = False,
                   prefer_lane: str | None = None) -> dict | None:
    """THE DOUBLE TRACK: take the next job from BOTH lanes, never alternating.

    Evolution and exploration run in PARALLEL (two lanes in the queue). This picker
    returns the best job of the lane that has been served LESS recently, so neither
    lane starves. ``prefer_lane`` forces a lane (for a test or a deliberate push);
    the default balances by the pending count. Falls back to the plain picker when
    a lane is empty.
    """
    if not queue:
        return None
    if prefer_lane in LANES:
        pool = [i for i in queue if lane_of(i.get("kind")) == prefer_lane]
        if pool:
            best = min(range(len(pool)), key=lambda i: (pool[i].get("weight", 3), i))
            return queue.pop(queue.index(pool[best]))
    counts = {lane: sum(1 for i in queue if lane_of(i.get("kind")) == lane)
              for lane in LANES}
    if all(counts[l] == 0 for l in LANES):
        return pick_next(queue, hot=hot)
    # serve the lane with MORE pending work (the busier lane is the bottleneck),
    # so both lanes keep moving; ties prefer exploration (the frontier).
    lane = max(LANES, key=lambda l: (counts[l], l == "exploration"))
    if counts[lane] == 0:
        lane = next(l for l in LANES if counts[l] > 0)
    return _pick_from(queue, lane, hot=hot)


def _pick_from(queue: list[dict], lane: str, *, hot: bool) -> dict | None:
    pool = [i for i in queue if lane_of(i.get("kind")) == lane]
    if not pool:
        return pick_next(queue, hot=hot)
    if hot:
        lights = [i for i in pool if i.get("kind") in LIGHT_KINDS]
        pool = lights or pool
    best = min(range(len(pool)), key=lambda i: (pool[i].get("weight", 3), i))
    return queue.pop(queue.index(pool[best]))


def gaps_seconds(journal: list[dict]) -> list[float]:
    """The inter-job gaps (seconds) from a run journal of ``{start,end}`` records.

    Zero dead minutes means these gaps are ~zero: one job ends, the next starts.
    """
    from datetime import datetime as _dt

    def _parse(ts):
        try:
            return _dt.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            return None

    gaps: list[float] = []
    for prev, nxt in zip(journal, journal[1:]):
        a, b = _parse(prev.get("end")), _parse(nxt.get("start"))
        if a and b:
            gaps.append(max(0.0, (b - a).total_seconds()))
    return gaps


def queue_report(queue: list[dict], journal: list[dict]) -> dict:
    """The queue's honest reading: depth, the jobs done, and the inter-job gaps."""
    gaps = gaps_seconds(journal)
    done = len(journal)
    avg_gap = round(sum(gaps) / len(gaps), 3) if gaps else None
    lanes = {lane: sum(1 for i in queue if lane_of(i.get("kind")) == lane)
             for lane in LANES}
    return {
        "depth": len(queue),
        "pending_kinds": [i.get("kind") for i in queue],
        "lanes": lanes,
        "jobs_done": done,
        "avg_gap_s": avg_gap,
        "max_gap_s": round(max(gaps), 3) if gaps else None,
        "reading": (f"queue depth {len(queue)} "
                    f"(evolution {lanes['evolution']}/exploration "
                    f"{lanes['exploration']}); {done} job(s) done; "
                    f"avg gap {avg_gap if avg_gap is not None else 'non misurato'}s"),
    }


# --- C8 — THE QUEUE'S COGNITIVE BALANCE ------------------------------------
# The Guardians' cognitive readings steer the STANDING MENU: a mind starved of
# novelty gets more PLAY; a rigid mind gets more REFLECTION; a confused mind gets
# more DREAMING. The balance is a bounded preference, never a rewrite of the menu.

# The novelty-bearing kinds (play/exploration) and the reflection kinds.
NOVELTY_KINDS: frozenset[str] = frozenset({"realm_scout", "library_hunt",
                                           "author_micro"})
REFLECTION_KINDS: frozenset[str] = frozenset({"evaluation_batch", "backfill_harvest",
                                              "cache_preheat"})


def cognitive_balance(*, echo_alarm: bool = False, novelty_starved: bool = False,
                      rigid: bool = False, confused: bool = False) -> dict:
    """The menu's rebalance from the Guardians' readings (C8), honest and bounded.

    * novelty-starved -> more PLAY (exploration weight lifted);
    * rigid -> more REFLECTION (the mind must revisit);
    * confused -> more DREAMING (consolidate before acting);
    * echo alarm -> a deliberate devil's-advocate session is injected.

    Returns the biases as data (kinds -> weight adjustment) so the refill can honour
    them without any hidden state. No reading -> an empty bias (the menu stands).
    """
    bias: dict[str, int] = {}
    if novelty_starved:
        for k in NOVELTY_KINDS:
            bias[k] = bias.get(k, 0) - 1     # lower weight -> drained sooner
    if rigid:
        for k in REFLECTION_KINDS:
            bias[k] = bias.get(k, 0) - 1
    if confused:
        bias["cache_preheat"] = bias.get("cache_preheat", 0) - 1   # reflection/dream
    inject = []
    if echo_alarm:
        inject.append("devils_advocate")
    reading = (f"bilanciamento: novelty_starved={novelty_starved}, rigid={rigid}, "
               f"confused={confused}, echo_alarm={echo_alarm}")
    return {"bias": bias, "inject": inject, "reading": reading}


def refill_balanced(queue: list[dict], *, balance: dict | None = None,
                    ts: str = "", kinds: set[str] | None = None) -> list[dict]:
    """Refill the queue, then apply the cognitive balance's weight biases (C8).

    The balance only re-weights PENDING menu jobs (it never invents work); an empty
    balance leaves the queue exactly as :func:`refill` built it. Bounded and honest.
    """
    added = refill(queue, ts=ts, kinds=kinds)
    bias = (balance or {}).get("bias") or {}
    if bias:
        for item in queue:
            k = item.get("kind")
            if k in bias and item.get("source") == "menu":
                item["weight"] = int(item.get("weight", 3)) + int(bias[k])
                item["balanced"] = True
    return added
