"""THE DELIBERATION CYCLE — one turn of the civilization's continuous thought.

The honest architecture note (printed in AGENTS.md): "continuous thinking" is a
frequent LIGHT deliberation cycle. This module is that cycle, wired to a persistent
STORE so the civilization's memory (bus, interbrain, ledger, reputation, ideas,
population, dreams, culture, self-model) survives between turns and lives 24/7.

The cycle is deterministic and idempotent in spirit: it reads the night's report
and the power-ups, assembles a WORLD snapshot, has the Council deliberate, records
the minutes WITH reasoning, seeds/broadcasts on the network, lets the market fund
ideas, dreams when quiet, updates the self-model, and (when the world asks) changes
the census — every change with its WHY.

Pure at import (Scar #6). The only I/O is :class:`Store` (load/save JSON), called
explicitly by the caller, never at import.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.civilization import census, council, curiosity, deep_improvements as deep_mod
from app.civilization import dreams, economy, falcon as falcon_mod
from app.civilization import flow as flow_mod
from app.civilization import forward_test as forward_mod
from app.civilization import regime_watch as regime_mod
from app.civilization import stress_test as stress_mod
from app.civilization import autobiography as auto_mod
from app.civilization import collective as collective_mod
from app.civilization import dragon_mind as mind_mod
from app.civilization import cathedral as cathedral_mod
from app.civilization import cascade_map as cascade_mod
from app.civilization import hunters as hunters_mod
from app.civilization import red_council as red_mod
from app.civilization import ticket as ticket_mod
from app.civilization import ledger, network, pipe as pipe_mod
from app.civilization import web_watch as webwatch_mod
from app.civilization import dragon as dragon_mod
from app.civilization import gaze as gaze_mod
from app.civilization import living as living_mod
from app.civilization import mind
from app.civilization import navigator as navigator_mod
from app.civilization import one_brain_cycle as obc
from app.civilization import playground
from app.civilization import sage as sage_mod
from app.civilization import sage_presence as presence_mod
from app.civilization import self_model as sm
from app.civilization import tongue
from app.civilization import work_queue as wq

__all__ = [
    "Store",
    "empty_state",
    "backfill_state",
    "world_from",
    "run_cycle",
]

# A small standing culture — the collective lessons every newborn inherits (LAW 4).
CULTURE: tuple[str, ...] = (
    "RR floor is 1:2.5; ambition climbs only on evidence",
    "friction must be paid many times over before a candidate is worth a round",
    "the weak die with an autopsy; nothing is lost",
    "bursts are born of thought, sized by conviction — never by a timer",
    "measure first; never assume a resource, a coverage, or a result",
)


class Store:
    """The civilization's persistent memory, as a single JSON document.

    R133 -- THE MEMORY THAT CANNOT FORGET: this file IS the council's whole
    memory (cycles of reputations, ledger rows, dreams, the one-brain's
    theories), and it used to live behind two quiet accidents: ``save``
    wrote the file IN PLACE (a crash mid-write tore it) and ``load`` turned
    a torn file into a newborn (silent amnesia -- the next ``save`` would
    then erase the last whole generation too). The cure has four organs:

    * ATOMIC SAVE -- the payload lands on a tmp sibling, fsyncs, then
      renames over the target (the kernel's whole-or-old guarantee); a
      crash mid-save can no longer produce a torn file;
    * THREE GENERATIONS -- every save rotates the known-good line
      (``*.bak1.json`` newest .. ``*.bak3.json`` oldest): a load that
      cannot parse the present falls back one generation at a time;
    * QUARANTINE, NEVER DELETION -- a torn file is renamed
      ``*.torn.<unix-ts>.json`` and kept as evidence forever (the
      guardian watches these fossils and says them aloud);
    * AMNESIA IS AN EVENT, NEVER A MOOD -- when nothing whole survives,
      the state is an honest newborn and ``memory_note`` says AMNESIA
      out loud, so the caller can journal it. A first breath (no file
      at all) is innocence, and is named innocence.
    """

    KEEP_GENERATIONS: int = 3

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.state: dict = empty_state()
        self.memory_note: str = ""

    def _backup(self, gen: int) -> Path:
        return self.path.parent / f"{self.path.stem}.bak{gen}{self.path.suffix}"

    def _quarantine(self, torn: Path) -> Path:
        dst = torn.parent / f"{torn.stem}.torn.{int(time.time())}{torn.suffix}"
        try:
            torn.rename(dst)
        except OSError:
            pass  # a sibling organ already carried the evidence aside
        return dst

    def load(self) -> dict:
        notes: list[str] = []
        survivors = 0
        candidates = [self.path] + [self._backup(g)
                                     for g in range(1, self.KEEP_GENERATIONS + 1)]
        for gen, cand in enumerate(candidates):
            if not cand.exists():
                continue
            survivors += 1
            try:
                self.state = backfill_state(json.loads(cand.read_text()))
                if gen > 0:
                    notes.append(f"the state was torn; the memory restored "
                                 f"from {cand.name}")
                break
            except (OSError, json.JSONDecodeError):
                if gen == 0:
                    kept = self._quarantine(cand)
                    notes.append(f"the state was torn and quarantined as "
                                 f"{kept.name} (the evidence is kept)")
                else:
                    notes.append(f"{cand.name} was unreadable and skipped")
        else:
            self.state = empty_state()
            if survivors:
                notes.append(f"AMNESIA, said aloud: no whole memory survived "
                             f"({survivors} torn/unreadable generation(s)); "
                             f"the civilization is newborn")
            else:
                notes.append("no memory file yet (a newborn civilization's "
                             "first breath)")
        self.memory_note = "; ".join(notes)
        return self.state

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.parent / f".{self.path.name}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(self.state, indent=2, default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            # rotate the known-good line BEFORE the atomic landing (deep
            # first: bak2->bak3, bak1->bak2, current->bak1)
            for gen in range(self.KEEP_GENERATIONS, 1, -1):
                older, newer = self._backup(gen), self._backup(gen - 1)
                if newer.exists():
                    os.replace(newer, older)
            if self.path.exists():
                os.replace(self.path, self._backup(1))
            os.replace(tmp, self.path)  # whole-or-old, never torn
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)  # a failed landing leaves no ghost


def empty_state() -> dict:
    """A newborn civilization: empty memory, one unit of attention each."""
    return {
        "bus": [],
        "interbrain": [],
        "ledger": [],
        "reputations": {},
        "ideas": [],
        "population": [],
        "legacy": [],
        "dreams": [],
        "episodes": [],
        "culture": list(CULTURE),
        "self_model": {},
        "exchanges": [],
        "cycles": 0,
        "one_brain": {"version": 0, "history": [], "belief_ledger": [],
                      "theories": [], "patterns": [], "generations": [],
                      "refusals": [], "archive": [], "retired_theories": []},
        # THE GAZE: the civilization's eyes and their memory (Part Four). The
        # monitors are what it is watching, the visual library is the shapes it has
        # SEEN, the archive is the photographs of key moments, the flow slots are
        # the purposeless-seeing sessions, the patrols are the visual watches over
        # the world, and the déjà-vu log is what a present scene reminded it of.
        "gaze": {"monitors": [], "visual_library": [], "archive": [],
                 "flow": [], "intuitions": [], "patrols": [], "deja_vu": [],
                 "sightings": []},
        # THE CONTINUOUS LIFE (Parts Two-Three): the day's activity log (the pulse's
        # source), the shared sensor buffer (the hawk's readings), the per-agent
        # activity stamps (the Idleness Guardian's source), the stored pulse history
        # (the trend's prior), the stream ticks (the orchestrator's vital signs), the
        # Sage's throne (its insights + accountability), and the spontaneous work the
        # free agents have asked for.
        "activity": [],
        "sensor_buffer": [],
        "agent_activity": {},
        "pulse_history": {},
        "streams": {},
        "sage": {"insights": [], "ledger": [], "backend": "stub",
                 "spontaneous": [], "costs": [], "office_hours": [],
                 "ceo_notes": [], "council_questions": [], "last_daily_ts": ""},
        # THE DRAGON (the dominant intelligence, six roles): its perpetual thoughts,
        # directed hypotheses, judgments (with dissent), architectural proposals, the
        # analyses + letters for the CEO, the training it gave, and its own cadence.
        "dragon": {"thoughts": [], "hypotheses": [], "judgments": [], "proposals": [],
                   "analyses": [], "letters": [], "dossiers": [], "training": [],
                   "paths": [], "last_thought_ts": "", "last_analysis_ts": ""},
        "spontaneous_work": [],
        # THE PERPETUAL MOTION (Parts One-Three): the falcon's live eyes + macro
        # radar + regime flags + sirens + searchable tick memory; the living web
        # watch (the rotation, the pulse, the event horizon, the social ear); the
        # pipe (the unified state artifact's last write + the VM's last push); the
        # continuous flow (the day's dispatches + the survivors pooled); and the deep
        # improvements (the counter-factual ledger, the market diary, the generation
        # wisdom). Every axis starts empty -- honest, never pre-filled.
        "falcon": {"readings": {}, "sources": {}, "macro": {}, "ticks": None,
                   "sirens": [], "events": [], "memory": []},
        "falcon_summary": None,
        "web_watch": {"pulse": None, "events": [], "fear_greed": None,
                      "reddit": None, "stocktwits": None, "sources": []},
        "pipe": {"last_push_ts": "", "last_state_ts": ""},
        "flow_dispatches": [],
        "survivors_pooled": None,
        "counterfactual": [],
        "market_diary": {"entries": []},
        "generation_wisdom": [],
        "contagion": None,
        # THE FIRST ASCENSION (Jumps 4, 3, 6): the regime watchtower (the last regime
        # map, the gating per pair, the "IL MONDO CAMBIA" events, the Guardian's
        # alarm), the forward-test chamber (the enrolled strategies + their windows),
        # and the present saboteur (the stress-test ledger). Every axis starts empty.
        "regime": {"last": {}, "gating": {}, "events": [], "last_map": None,
                   "last_alarm": None},
        "regime_summary": None,
        "forward_test": {"enrolled": [], "windows": {}},
        "forward_test_summary": None,
        "stress_test": {"ledger": []},
        "stress_test_summary": None,
        # THE SECOND ASCENSION (Jumps 1, 5, 2): the Dragon's continuous mind (its
        # persistent context + Theory of the Hunt), the autobiography (the chapter
        # narrative + the identity trajectory), and the collective (the shared belief
        # state + the experience commons + the coherence history). Every axis empty.
        "dragon_mind": {"version": 1, "thoughts": [], "observations": [],
                        "theory": None, "theory_history": []},
        "autobiography": {"version": 1, "chapters": [], "generation_summaries": []},
        "collective": {"version": 1, "beliefs": {}, "commons": [],
                       "coherence_history": []},
        "collective_summary": None,
        "autobiography_summary": None,
        # THE REAL HUNT (Parts One-Six): the Cathedral of Confluence (the seven
        # columns + the confidence cascade + the adaptive weights), the three
        # Specialist Hunters, the Red Council (the devil's advocate), the cascade map
        # (the intermarket correlation + the lead-lag) and the trade tickets. Every
        # structure empty; every axis unmeasured until a real observation feeds it.
        "cathedral": {"version": 1, "accuracy": {}, "history": [], "last": None},
        "hunters": {"version": 1, "results": {}, "last": None},
        "red_council": {"version": 1, "challenges": [], "anti_reports": [],
                        "cassandra": {"hits": 0, "n": 0}, "last": None},
        "cascade": {"version": 1, "last": None},
        "tickets": [],
        "cathedral_summary": None,
        "hunters_summary": None,
        "red_council_summary": None,
        "cascade_summary": None,
    }


def backfill_state(state: dict | None) -> dict:
    """Fill a loaded state with any schema key added since it was last written.

    THE FINAL INTEGRATION bug: ``Store.load`` replaced the in-memory newborn
    (:func:`empty_state`) with the loaded document wholesale, so a committed
    ``civilization_state.json`` written BEFORE a new block existed (``regime``,
    ``forward_test``, ``stress_test``, ``spontaneous_work``, ...) left
    ``run_cycle`` to read a missing key and raise ``KeyError``. On CI the night's
    ``council_cycle ... || true`` SWALLOWED that crash, so the civilization never
    advanced and the Letter never carried the new sections -- the exact silent
    failure the Grand-on-the-VM phase exposes. Backfilling each missing top-level
    key from a fresh :func:`empty_state` makes a new schema self-healing: a
    persisted value always WINS (an empty list written after real work is a real
    state), and only a MISSING key is seeded. Pure; the input dict is mutated and
    returned.
    """
    st = state if state is not None else {}
    for key, default in empty_state().items():
        if key not in st:
            st[key] = default
    return st


def _epoch(ts: str) -> float:
    """Unix epoch seconds from an ISO timestamp (0.0 when unparseable, honest)."""
    v = str(ts or "").strip().replace("Z", "+00:00")
    if not v:
        return 0.0
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        return 0.0
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def _speak_in_tongue(state: dict, *, session: dict, cmap: dict, ts: str) -> list[dict]:
    """Record the Council's decisions in the APEX TONGUE, on the right channel.

    The WISE SILENCE rule (Part Six) decides whether to speak: a decision that
    changes work (a cure, a raid, a burst) is RELEVANT and is recorded in the
    tongue; a quiet cycle says nothing (SILENCE is the default, not a message).
    Returns the utterances added.
    """
    spoken: list[dict] = []
    for d in session.get("decisions") or []:
        kind = d.get("kind")
        word = {"cure_family": "cure", "populate_realm": "raid",
                "forge_burst": "seed", "focus_research": "nov"}.get(kind)
        danger = False
        channel = tongue.classify(changes_work=True, danger=danger, useful_to="*")
        if word is None or channel == tongue.SILENCE:
            continue
        u = tongue.utterance(sender="council", word=word, body=str(d.get("what") or ""),
                             channel=channel, to="*", ts=ts,
                             steps=[f"decisione: {d.get('what')}",
                                    f"perche': {d.get('why')}",
                                    f"effetto: {d.get('expected_effect')}"])
        state.setdefault("exchanges", []).append(u)
        spoken.append(u)
    return spoken


def _ceo_requests(state: dict, cmap: dict) -> tuple[list[str], list[str]]:
    """The felt needs + raids the garden surfaces, split into FRESH requests and those
    a standing CEO directive ALREADY covers.

    The directive register precedes the question: a granted order is recorded, never
    re-asked (the CEO-request loop fix). Returning both lets the cycle ASK the fresh
    ones on the bus and ANSWER the granted ones from the register.
    """
    requests: list[str] = []
    granted: list[str] = []
    for r in cmap.get("raids", []):
        req = (f"organize a raid on the unknown zone {r['zone']} "
               f"(pull {r['pull']:.2f})")
        (granted if council.request_is_granted(req) else requests).append(req)
    thin = (cmap.get("thinnest") or {}).get("zone")
    if thin and not cmap.get("raids"):
        req = f"authorize a small exploration of {thin} (thinnest knowledge)"
        (granted if council.request_is_granted(req) else requests).append(req)
    return requests, granted


def _realm_coverage(night_report: dict) -> dict:
    """Realm coverage from the report's real signals; empty when unmeasured.

    Honest: coverage is READ, never invented. Preferred source is a measured
    ``realms.by_family_group`` block; failing that, the Pareto occupation
    (``measurements.R80_pareto`` occupied / corners_total) is the honest reading of
    how much of the known search space we actually occupy. If neither is present the
    map is EMPTY — the Council is told nothing rather than a flattering default.
    """
    realms = (night_report.get("realms") or {})
    by_family = realms.get("by_family_group") or {}
    if by_family:
        return {str(k): float(v) for k, v in by_family.items()}
    pareto = ((night_report.get("measurements") or {}).get("R80_pareto") or {})
    occupied = pareto.get("occupied")
    corners = pareto.get("corners_total")
    if occupied is not None and corners:
        return {"pareto_space": round(float(occupied) / float(corners), 6)}
    return {}


def _family_health(night_report: dict, *, bar: float = 0.45) -> dict:
    """Per-family health from the REAL leaderboard: adversary score vs the bar.

    A family the adversary tested whose leaderboard score is below the bar has no
    certified survivor — it is SICK by data. A family at or above the bar has one.
    Honest: only families the report actually carries appear.
    """
    health: dict[str, dict] = {}
    for row in (night_report.get("leaderboard") or []):
        fam = row.get("family")
        if not fam:
            continue
        lb = float(row.get("adv_lb") or 0.0)
        trades = int(row.get("adv_trades") or 0)
        survivors = 1 if lb >= bar else 0
        health[str(fam)] = {"failures": trades if survivors == 0 else 0,
                            "survivors": survivors, "adv_lb": lb}
    return health


def _performance(night_report: dict, cov: dict) -> dict:
    """Normalized performance per regime: leaderboard resilience, else depth (1-cov)."""
    perf: dict[str, float] = {}
    for row in (night_report.get("leaderboard") or []):
        fam = row.get("family")
        if fam and row.get("resilience") is not None:
            perf[str(fam)] = float(row["resilience"])
    if not perf:
        perf = {r: round(1.0 - c, 6) for r, c in cov.items()}
    return perf


def world_from(night_report: dict, powerups: dict, state: dict,
               *, capacity_trials: int | None = None) -> dict:
    """Assemble the WORLD snapshot the Council deliberates over (pure)."""
    cov = _realm_coverage(night_report)
    funded = [i for i in state.get("ideas", []) if economy.funded(i)]
    prior_model = state.get("self_model") or {}
    strengths_weaknesses = {
        "strengths": prior_model.get("strengths", []),
        "weaknesses": prior_model.get("weaknesses", []),
    }
    return {
        "realm_coverage": cov,
        "family_health": _family_health(night_report),
        "funded_ideas": funded,
        "strengths_weaknesses": strengths_weaknesses,
        "meta_learning": (powerups.get("meta_learning") if powerups else None) or {},
        "capacity_trials": capacity_trials,
        "had_self_model": bool(prior_model),
    }


def _seed_ideas(state: dict, *, curiosity_map: dict, self_model: dict) -> None:
    """Seed the Market of Ideas from the thinnest knowledge and the weaknesses.

    The civilization's first ideas are its own unknowns — no invented agenda.
    """
    if state["ideas"]:
        return
    thin = (curiosity_map.get("thinnest") or {}).get("zone")
    if thin:
        network.post_idea(state["interbrain"], author="council",
                          idea=f"send scouts into the unknown realm {thin}")
    for w in (self_model.get("weaknesses") or [])[:2]:
        network.post_idea(state["interbrain"], author="council",
                          idea=f"find an edge in the weak regime {w}")
    for idx, node in enumerate(state["interbrain"]):
        state["ideas"].append({"idea": node["idea"], "author": node["author"],
                               "attention": 0.0, "backers": [],
                               "status": "open", "parents": node.get("parents", []),
                               # The flagship idea (the thinnest-zone scout) is the
                               # civilization's COLLECTIVE bet; the rest are the
                               # individual bets that differentiate the market.
                               "primary": idx == 0})


def _conviction(agent: str, idea: str) -> float:
    """A deterministic per-(agent, idea) conviction in [0, 1] (no RNG, no clock).

    Agents do not bet identically: each has its own reading of an idea's promise.
    This spreads the bets across ideas, so a settled outcome differentiates the
    market -- the backers of a winner gain, the backers of a loser gain nothing.
    """
    import hashlib

    h = hashlib.sha256(f"{agent}|{idea}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


def _back(state: dict, *, agents: list[str]) -> dict[str, float]:
    """Agents spend attention on the open ideas THEY find promising (their bets).

    Each agent backs only the ideas its own conviction favors (``_conviction``),
    so the market is heterogeneous: some agents stake a winning idea, some a losing
    one. Returns the attention each agent SPENT this cycle (the stake at risk), so
    the replenishment can modulate a losing agent's allowance down (Cure 1).
    """
    spent: dict[str, float] = {a: 0.0 for a in agents}
    for a in agents:
        state["reputations"].setdefault(a, economy.START_REPUTATION)
    for idea in state["ideas"]:
        if idea.get("status") != "open":
            continue
        for a in agents:
            # The flagship idea draws the whole civilization's first bet (a shared
            # conviction); the secondary ideas draw each agent's OWN bet only when
            # its conviction favors them -- that is what differentiates the market.
            if not idea.get("primary") and _conviction(a, str(idea.get("idea"))) < 0.5:
                continue
            if state["reputations"].get(a, 0.0) >= 0.25:
                economy.back(state["reputations"], idea, agent=a, weight=0.25)
                spent[a] = round(spent[a] + 0.25, 6)
    return spent


def _market_outcome(night_report: dict) -> float | None:
    """The night's realized market value: the best surviving NET R, or ``None``.

    The market's bets are on IDEAS; an idea that was forged into a burst is PAID
    when the burst delivered a surviving strategy. This is the honest proxy the
    cycle settles from (Law 10 names the source): the best NET R of the night's
    net-positive survivors. No survivor measured => ``None`` (the ideas settle at
    zero: the backers' stake is spent and returns nothing -- they LOSE).
    """
    rows = night_report.get("final_population") or night_report.get("leaderboard") or []
    vals = [float(r.get("net_r")) for r in rows
            if isinstance(r.get("net_r"), (int, float)) and float(r.get("net_r")) > 0.0]
    return round(max(vals), 6) if vals else None


def _settle_and_replenish(state: dict, *, night_report: dict,
                          agents: list[str], spent: dict[str, float],
                          ts: str = "") -> dict:
    """Settle the forged ideas from real outcomes, then grant the allowance (Cure 1).

    Every idea the Council FORGED into a burst in an earlier cycle settles now: its
    backers are PAID from the measured outcome (``earned``) when it delivered, or
    gain nothing (``lost``) when it did not. Then every agent receives its per-cycle
    allowance, modulated by what it earned and lost -- the Market of Ideas stays
    alive instead of freezing on the first cycle.
    """
    outcome = _market_outcome(night_report)
    # R89 -- did this night actually MEASURE anything? (No rows == no run.)
    ran_measured = bool(night_report.get("final_population")
                        or night_report.get("leaderboard"))
    carried_over: list[str] = []
    earned: dict[str, float] = {a: 0.0 for a in agents}
    lost: dict[str, float] = {a: 0.0 for a in agents}
    settles: list[dict] = []
    for idea in state["ideas"]:
        status = idea.get("status")
        # A FORGED idea (the Council funded it into a burst) settles from the
        # measured outcome: its backers are PAID when the burst delivered.
        # An idea that stayed OPEN with backers but never earned funding STARVES:
        # its backers staked attention and got nothing back -- they LOSE the stake.
        if status == "forged":
            if not ran_measured:
                # R89 -- HONEST RECEIPTS (Law 10): a night that measured nothing
                # settles NOTHING. The forged idea carries over -- never a fake
                # "no_survivor" receipt for a burst that never flew (the 4-day
                # heart flatline settled 20k-trial bursts at +0.000R, unexecuted).
                carried_over.append(str(idea.get("idea"))[:80])
                continue
            value = float(outcome) if outcome is not None else 0.0
            outcome_kind = "delivered" if value > 0.0 else "no_survivor"
        elif status == "open" and idea.get("backers"):
            value = 0.0
            outcome_kind = "starved"
        else:
            continue
        economy.settle(state["reputations"], idea, realized_value=value, ts=ts)
        pays = {p["agent"]: p["reputation_gained"] for p in idea.get("payouts", [])}
        for b in idea.get("backers", []):
            a = b["agent"]
            earned[a] = round(earned.get(a, 0.0) + pays.get(a, 0.0), 6)
            if value <= 0.0:
                lost[a] = round(lost.get(a, 0.0) + float(b.get("weight", 0.0)), 6)
        settles.append({"idea": idea.get("idea"), "realized_value": value,
                        "outcome_kind": outcome_kind,
                        "payouts": idea.get("payouts", []),
                        "backers": [b["agent"] for b in idea.get("backers", [])]})
    granted = economy.replenish(state["reputations"], agents=agents,
                                earned=earned, lost=lost, base=economy.REPLENISH_BASE)
    return {"settles": settles, "granted": granted, "earned": earned, "lost": lost,
            "outcome": outcome}


def _forge_ideas(state: dict, *, session: dict, ts: str) -> None:
    """Mark the ideas the Council forged into bursts (so they settle next cycle)."""
    forged = {b.get("idea") for b in (session.get("bursts") or [])}
    for idea in state["ideas"]:
        if idea.get("idea") in forged and idea.get("status") == "open":
            idea["status"] = "forged"
            idea["forged_ts"] = ts


def _spontaneous_work(state: dict, *, agents: list[str], ts: str) -> list[dict]:
    """THE FREEDOM DOCTRINE (Part Three, item 11): free agents ask for work.

    The civilization's free minds — the play slots (Vygotsky) and the Council's
    kings — may, at ANY moment, ask for work with no permission and no slot. This
    turns the cycle's open play and any recorded spontaneous request into queue
    items. Bounded (never more than a handful per cycle) and honest: a request
    without a WHY is refused by the queue itself.
    """
    items: list[dict] = []
    for it in (state.get("play_queue") or [])[-2:]:
        try:
            items.append(wq.spontaneous_item(
                agent=str(it.get("agent") or "play"),
                act="think",
                why=str(it.get("why") or "the play slot asked to think freely"),
                ts=ts))
        except ValueError:
            continue
    for req in (state.get("spontaneous_requests") or [])[-2:]:
        try:
            items.append(wq.spontaneous_item(
                agent=str(req.get("agent") or "agent"),
                act=str(req.get("act") or "think"),
                why=str(req.get("why") or "a free agent asked"),
                ts=ts))
        except ValueError:
            continue
    return items


def _sage_within(state: dict, *, night_report: dict, ts: str,
                 pro: bool = False) -> dict:
    """THE SAGE WITHIN (Part Four): consult the throne over the civilization.

    Builds the Sage's context from the state + the night report, asks for guidance
    (the sealed entry point), and returns the block. Its insights carry the mode
    "IL SAGGIO DICE" and are logged in ``state['sage']`` for their outcome track
    record. The Council stays sovereign: the Sage ADVISES. Fail-open: a fault in
    the throne never costs the cycle's other work (an honest empty block).

    THE BUDGET DOCTRINE (the CEO's order): the reading runs on the cheap Flash head by
    default; ``pro=True`` is passed ONLY when the Council explicitly requests an
    extraordinary Pro session. An ordinary Council consultation never spends on Pro.
    """
    try:
        context = sage_mod.sage_context(
            state, report=night_report, agents_digest=_culture_digest(state),
            letter_history=state.get("letter_history"),
            events=state.get("ledger", [])[-20:])
        block = sage_mod.guidance(context, pro=pro, state=state)
        # The Sage's insights enter the interbrain as ADVICE (the highest mode).
        for ins in block.get("insights") or []:
            network.post_idea(state["interbrain"], author="sage",
                              idea=f"[{sage_mod.SAGE_MODE}] {ins.get('text')}")
        return block
    except Exception:  # noqa: BLE001 — the throne must never break the cycle
        return {"backend": "stub", "deep": False, "insights": [], "n": 0,
                "mode": sage_mod.SAGE_MODE,
                "reading": f"{sage_mod.RESTING_LINE} (fault tollerato, onesto)"}


def _culture_digest(state: dict) -> str:
    """A short digest of the civilization's culture for the Sage's context."""
    return " | ".join(str(c) for c in (state.get("culture") or [])[:8])


def _extraordinary_dragon(state: dict, *, regime_block: dict, stress_block: dict,
                          dragon_mod, ts: str) -> dict | None:
    """Trigger the Dragon's EXTRAORDINARY briefing on a regime shift or a survival alarm.

    The Dragon redirects the next micro's directed mutations toward the NEW regime's
    families and recommends defensive actions. Honest: no trigger -> no briefing (the
    Dragon is not summoned for nothing); no key -> the Dragon rests.
    """
    shifts = (regime_block or {}).get("shifts") or []
    alarm = (stress_block or {}).get("alarm")
    if not shifts and not alarm:
        return None
    if shifts:
        reason = ("cambio di regime: "
                  + ", ".join(s.get("reading", "") for s in shifts[:3]))
    else:
        reason = "allarme di sopravvivenza: " + str((alarm or {}).get("reading"))
    context = {"regime": regime_block, "stress": stress_block}
    try:
        beat = dragon_mod.extraordinary_briefing(state, reason=reason, context=context,
                                                 ts=ts)
    except Exception:  # noqa: BLE001 -- the Dragon must never break the cycle
        beat = {"ok": False, "text": "", "error": "fault tollerato", "ts": ts,
                "tag": "BRIEFING STRAORDINARIO"}
    return beat


def _collective_model(state: dict, *, regime_block: dict, forward_block: dict,
                      stress_block: dict, ts: str) -> dict:
    """JUMP 2 — THE COLLECTIVE MODEL: fold the agents' private beliefs into one.

    Each agent's own regime read (from the Watchtower's gating) becomes a shared
    belief; the civilization's coherence is then measured (how much the individuals
    agree). Honest: no gating (the Watchtower reconfigured nothing) -> no belief is
    contributed and the block reports zero coherence; a failed read is caught so the
    collective never breaks the cycle.
    """
    try:
        gating = (regime_block or {}).get("gating") or {}
        for pair, g in gating.items():
            regime = (g or {}).get("regime")
            if not regime:
                continue
            for a in state.get("population") or []:
                sig = str(a.get("signature") or "")
                if not sig:
                    continue
                # the individual's confidence is its OWN realized net_r on the last
                # judged window (unmeasured -> None, never a fabricated confidence).
                contrib = collective_mod.contribute_belief(
                    state, pair=str(pair), regime=str(regime),
                    confidence=_agent_confidence(a, forward_block), agent=sig,
                    source="regime_watch", ts=ts)
                del contrib
        # the individual beliefs ARE the contributions just made (pair + regime per
        # agent); coherence measures how far they are from the blended shared state.
        individual = [{"pair": p, "regime": c.get("regime")}
                      for p, e in collective_mod.belief_state(state).items()
                      for c in (e.get("contributions") or [])]
        collective_mod.coherence_trend(state, ts=ts)
        block = collective_mod.collective_block(state, individual_beliefs=individual,
                                                ts=ts)
        state["collective_summary"] = block
        return block
    except Exception:  # noqa: BLE001 -- the collective must never break the cycle
        return {"coherence": {"measured": False}, "n_beliefs": 0,
                "reading": "modello collettivo: fault tollerato (onesto)"}


def _agent_confidence(agent: dict, forward_block: dict) -> float | None:
    """An agent's OWN measured confidence: its realized net_r on the last window."""
    sig = str(agent.get("signature") or "")
    windows = ((forward_block or {}).get("windows") or {})
    rows = windows.get(sig) or []
    if not rows:
        return None
    last = rows[-1]
    v = last.get("outcome_r") if isinstance(last, dict) else None
    return float(v) if isinstance(v, (int, float)) else None


def _autobiography(state: dict, *, night_report: dict, session: dict, ts: str) -> dict:
    """JUMP 5 — THE AUTOBIOGRAPHY: write the day's chapter from the real events.

    The chapter is composed from the day's SIGNIFICANT events (the Council's
    decisions, the births and deaths, the Dragon's thought) with the identity
    trajectory (the beliefs before -> now). Honest: a day with no significant event
    writes no chapter (the book does not invent days); a fault is caught.
    """
    try:
        day = str(ts)[:10]
        events: list[dict] = []
        for d in session.get("decisions") or []:
            events.append({"kind": str(d.get("kind") or "decision"),
                           "reading": str(d.get("reason") or d.get("kind") or ""),
                           "ts": ts})
        thoughts = list(((state.get("dragon") or {}).get("thoughts") or []))
        if thoughts:
            events.append({"kind": "thought",
                           "reading": str(thoughts[-1].get("text") or ""), "ts": ts})
        # the identity trajectory: the shared beliefs BEFORE this chapter (the last
        # chapter's snapshot) and NOW (the collective's current belief map).
        prev = auto_mod.chapters(state)
        beliefs_before = list((prev[-1].get("beliefs_now") if prev else []) or [])
        beliefs_now = [str(p) for p in (state.get("collective", {})
                                        .get("beliefs") or {})]
        write = auto_mod.write_chapter(
            state, date=day, events=events,
            mood=str((state.get("self_model") or {}).get("mood") or ""),
            lessons=list(session.get("minutes", {}).get("by_kind", {}).keys()),
            beliefs_now=beliefs_now, beliefs_before=beliefs_before, ts=ts)
        auto_mod.distill_generation(state, label=day, ts=ts)
        block = auto_mod.autobiography_block(state)
        state["autobiography_summary"] = block
        return {**block, "written": bool(write)}
    except Exception:  # noqa: BLE001 -- the book must never break the cycle
        return {"chapters": 0, "written": False,
                "reading": "autobiografia: fault tollerato (onesto)"}


def _flow_dragon_awareness(state: dict, *, flow_block: dict, ts: str) -> dict:
    """JUMP 1 — feed the day's flow (the micros' survivors) into the Dragon's mind.

    The Dragon learns which families produced survivors. Honest: an unmeasured
    survivor count (``--``) feeds nothing.
    """
    try:
        today = (flow_block or {}).get("today") or {}
        survivors = (state.get("survivors_pooled"))
        families = today.get("families") or None
        if survivors is None and not families:
            return {"observed": False}
        return mind_mod.flow_awareness(state, ts=ts, survivors=survivors,
                                       families=families,
                                       note=str(today.get("reading") or ""))
    except Exception:  # noqa: BLE001
        return {"observed": False}


def _cathedral_context(store_state: dict, *, readings: dict, regime_block: dict,
                       forward_block: dict, ts: str, pair_override: str = "",
                       direction_override: int | None = None) -> dict:
    """Assemble the Cathedral's live context from the REAL readings (honest).

    Each column reads only what was MEASURED: the falcon's regime flags, the level
    proximity, the confirmed momentum, the circadian window, the macro radar, the
    collective's independent agreement and the forward chamber's live scores. A
    missing observation yields an UNMEASURED column (``None``) -- never a guess.

    ``pair_override`` / ``direction_override`` let the SIGNAL GENERATOR evaluate a
    CANDIDATE's own pair + direction (Mega Phase 1, A3) with the same honest columns.
    """
    from app.civilization import circadian as circ_mod
    from app.quant import levels as levels_mod
    from app.civilization import collective as coll_mod

    hot = store_state.get("hot_pairs") or {}
    pair = str(pair_override or "") or str((hot.get("chosen") or [None])[0] or "") or next(
        iter(readings or {}), "") or ""
    reading = dict(readings.get(pair) or {}) if pair else {}

    # COLUMN 1 -- REGIME: the pair's live regime flag (the falcon's kingdom).
    rf = falcon_mod.regime_flag({"pair": pair, **reading}) if pair else {
        "pair": None, "regime": None}
    regime_ev = {"regime": rf.get("regime"),
                 "transitioning": bool((regime_block or {}).get("shifts"))}

    # COLUMN 2 -- STRUCTURE: price at a structural level (the SMC levels).
    structure_ev = {"at_level": None, "kind": None, "tests": None}
    try:
        frames_by_pair = store_state.get("frames") or {}
        fr = frames_by_pair.get(pair)
        if fr is not None:
            ex = fr.exec
            ls = levels_mod.swing_levels(ex["high"].to_numpy(), ex["low"].to_numpy())
            close = ex["close"].to_numpy()
            near = bool(len(close)) and bool(
                (np.abs(close - ls.swing_low) <= 1e-6).any()
                or (np.abs(close - ls.swing_high) <= 1e-6).any())
            structure_ev = {"at_level": near, "kind": "swing", "tests": None}
    except Exception:  # noqa: BLE001
        structure_ev = {"at_level": None, "kind": None, "tests": None}

    # COLUMN 3 -- MOMENTUM: is price ALREADY moving our way (confirmation).
    # For a CANDIDATE the direction is the strategy's own; momentum confirms only when
    # the measured flow AGREES with it (Mega Phase 1, A3).
    delta = reading.get("session_delta")
    vel = reading.get("tick_velocity")
    cand_dir = direction_override if direction_override in (1, -1) else None
    momentum_ev = {"confirmed": None, "direction": cand_dir}
    if isinstance(delta, (int, float)) and isinstance(vel, (int, float)):
        d = 1 if delta > 0 else (-1 if delta < 0 else 0)
        agrees = (d == cand_dir) if cand_dir is not None else True
        momentum_ev = {"confirmed": bool(agrees and abs(float(delta)) >= 20.0
                                         and float(vel) >= 5.0),
                       "direction": cand_dir or d}

    # COLUMN 4 -- TIMING: the right window (the circadian phase + the event horizon).
    phase = circ_mod.phase_at(ts)
    in_window = phase in ("london_alert", "ny_peak") if phase else None
    timing_ev = {"in_window": in_window, "window": phase}

    # COLUMN 5 -- MACRO: the intermarket context (the DXY cascade).
    macro = cascade_mod.macro_support(store_state.get("macro_readings") or {},
                                      pair=pair, direction=(momentum_ev.get("direction") or 1))
    macro_ev = {"support": macro.get("support"), "reason": macro.get("reason")}

    # COLUMN 6 -- CONSENSUS: 3+ UNCORRELATED strategies agree (the collective).
    # DEBT-062: independence is MEASURED from the real return series (the largest
    # mutually-uncorrelated group), not a bare claim. No series -> unmeasured.
    beliefs = coll_mod.belief_map(store_state)
    rows = beliefs.get("rows") or []
    indep = coll_mod.independent_from_series(store_state.get("series") or {})
    if indep["measured"]:
        consensus_ev = {"n_independent": indep["n"], "independent": True,
                        "independence_measured": True,
                        "independence_reading": indep["reading"]}
    else:
        n_ind = (sum(1 for r in rows if r.get("regime")) if rows else None)
        consensus_ev = {"n_independent": n_ind, "independent": None,
                        "independence_measured": False,
                        "independence_reading": indep["reading"]}

    # COLUMN 7 -- EVIDENCE: does this setup work NOW (the forward chamber's live).
    lb = forward_block.get("top") or []
    live = lb[0].get("live") if lb else None
    evidence_ev = {"live_score": live, "n": (lb[0].get("live_n") if lb else None)}

    return {"pair": pair, "regime": regime_ev, "structure": structure_ev,
            "momentum": momentum_ev, "timing": timing_ev, "macro": macro_ev,
            "consensus": consensus_ev, "evidence": evidence_ev}


def _run_the_hunt(store_state: dict, *, regime_block: dict, forward_block: dict,
                  readings: dict, ts: str) -> dict:
    """THE REAL HUNT (Parts One-Six): the Cathedral, the hunters, the Red Council.

    Evaluates the seven columns, runs the confidence cascade and the gate; evaluates
    the three hunters WITHIN the Cathedral; attacks a CLASS A case with the Red
    Council and -- only if the case SURVIVES -- issues the trade ticket. All fail-open
    and all honest: an unmeasured column never confirms, a hunter without all its
    confirmations PREPARES, and no ticket is issued below CLASS A.
    """
    ctx = _cathedral_context(store_state, readings=readings,
                             regime_block=regime_block, forward_block=forward_block,
                             ts=ts)
    cat = cathedral_mod.cathedral_block(store_state, ctx, ts=ts)
    store_state["cathedral_summary"] = cat

    # the Red Council attacks the Cathedral's case BEFORE anything fires.
    challenge = red_mod.devil_advocate(store_state, {
        "gate": cat.get("gate"), "columns": cat.get("columns"),
        "accuracies": cat.get("accuracies"),
        "dragon_objection": None}, ts=ts)

    # the three hunters, evaluated within the Cathedral. DEBT-063: the context is
    # built from the REAL live readings (micro-events, the hot pair's velocity/delta,
    # the web-watch event, the circadian boundary) -- not an empty dict.
    hunter_ctx = hunters_mod.hunter_context(
        store_state, gate=cat.get("gate"), ts=ts)
    hunters_block = hunters_mod.hunter_block(store_state, hunter_ctx, ts=ts)
    store_state["hunters_summary"] = hunters_block

    # a CLASS A case that SURVIVES the Red Council becomes a trade ticket.
    ticket = {"ok": False, "reason": "gate non A"}
    if cat.get("gate", {}).get("class") == "A" and challenge.get("survives"):
        pair = ctx.get("pair")
        r = dict(readings.get(pair) or {})
        entry = r.get("value")
        d = ctx.get("momentum", {}).get("direction") or 1
        rr = 2.5
        sl = (entry - d * 0.0010) if isinstance(entry, (int, float)) else None
        tp = (entry + d * 0.0010 * rr) if isinstance(entry, (int, float)) else None
        ticket = ticket_mod.build_ticket(
            pair=pair, direction=d, entry=entry, sl=sl, tp=tp,
            gate=cat.get("gate"), columns=cat.get("columns"),
            hunter=next((h for h in hunters_block["hunters"] if h.get("fire")), None),
            dragon="", red_council=challenge, ts=ts,
            confidence=cat.get("gate", {}).get("confidence"))
        if ticket.get("ok"):
            ticket_mod.tickets(store_state).append(ticket["ticket"])
            del ticket_mod.tickets(store_state)[:-100]

    rc_block = red_mod.red_council_block(store_state)
    store_state["red_council_summary"] = rc_block

    # the intermarket cascade map (the falcon's multi-asset view -> Column 5).
    series = store_state.get("series") or {}
    cascade = cascade_mod.cascade_block(store_state, series=series)
    store_state["cascade_summary"] = cascade

    return {"cathedral": cat, "hunters": hunters_block, "red_council": rc_block,
            "cascade": cascade, "challenge": challenge, "ticket": ticket}


def _signal_generator_block(store_state: dict, *, night_report: dict, readings: dict,
                            regime_block: dict, forward_block: dict, ts: str) -> dict:
    """THE SIGNAL GENERATOR (Mega Phase 1, A1-A3): the civilization's FIRST ACT.

    Until now the Cathedral only ever saw the single HOT pair it chose itself. This
    asks the SURVIVING strategies, on the REAL live tape, "would you enter RIGHT NOW?"
    for EVERY operational pair -- birthing the candidates the Cathedral then JUDGES
    (A3). Every candidate, accepted or rejected, is logged in the registry with its
    metadata so even a refusal becomes forward-test evidence.

    Honest and fail-open: a pair with no tape contributes no candidate; the survivor
    DNA is read from the committed report (a PROVISIONAL seed set is used, labelled,
    until the first night commits the DNA); a fault never breaks the cycle.
    """
    try:
        from app.quant import signal_generator as sg_mod
    except Exception:  # noqa: BLE001
        return {"measured": False, "reading": "generatore di segnali non disponibile",
                "candidates": [], "n_candidates": 0, "n_accepted": 0}

    # the SURVIVING strategies and their live scores (the report's real signatures).
    genomes: list[dict] = []
    for row in (night_report.get("leaderboard") or []):
        sid = str(row.get("signature") or "")
        if not sid:
            continue
        score = row.get("adv_lb", row.get("wilson_lb"))
        genomes.append({"signature": sid,
                        "score": float(score) if isinstance(score, (int, float)) else None})
    recovered, unrecovered, source = sg_mod.recover_genomes(night_report)
    # prefer the DNA-carrying recovery (same order); else the leaderboard rows alone.
    if recovered:
        genomes = recovered

    # the operational pairs: the report's volume-law pairs, else the falcon's readings,
    # else the constellation's default majors (a pair with no tape contributes nothing).
    DEFAULT_PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "EURGBP", "AUDJPY")
    pairs = [str(p) for p in ((night_report.get("volume_law") or {}).get("pairs") or [])]
    if not pairs:
        pairs = list((readings or {}).keys())
    if not pairs:
        pairs = list(DEFAULT_PAIRS)
    frames_by_pair: dict = {}
    for p in pairs:
        F = sg_mod.frames_from_tape(p)
        if F is not None:
            frames_by_pair[p] = F

    candidates = sg_mod.generate_candidates(genomes, frames_by_pair, ts=ts)

    # A3 -- the Cathedral JUDGES each candidate on its OWN pair + direction.
    accepted: list[dict] = []
    for cand in candidates:
        try:
            ctx = _cathedral_context(
                store_state, readings=readings, regime_block=regime_block,
                forward_block=forward_block, ts=ts,
                pair_override=cand.get("pair") or "",
                direction_override=cand.get("direction"))
            cat = cathedral_mod.cathedral_block(store_state, ctx, ts=ts)
            challenge = red_mod.devil_advocate(store_state, {
                "gate": cat.get("gate"), "columns": cat.get("columns"),
                "accuracies": cat.get("accuracies"), "dragon_objection": None}, ts=ts)
            gate_class = (cat.get("gate") or {}).get("class")
            is_accepted = bool(gate_class == "A" and challenge.get("survives"))
            rec = sg_mod.record_candidate(store_state, cand, accepted=is_accepted,
                                          gate_class=gate_class, ts=ts)
            if is_accepted:
                accepted.append(rec)
        except Exception:  # noqa: BLE001 - a fault on one candidate never stops the rest
            continue

    block = {"version": sg_mod.CANDIDATE_VERSION,
             "strategy_source": source, "n_strategies": len(genomes),
             "unrecovered": unrecovered,
             "pairs": pairs, "pairs_with_tape": sorted(frames_by_pair.keys()),
             "n_candidates": len(candidates), "n_accepted": len(accepted),
             "candidates": candidates,
             "accepted": accepted,
             "measured": len(candidates) > 0,
             "reading": (f"LA CATTEDRALE HA VALUTATO {len(candidates)} opportunita' "
                         f"({len(accepted)} accettate; fonte {source})"
                         if candidates else
                         "LA CATTEDRALE HA VALUTATO 0 opportunita' "
                         "(nessun candidato dal vivo)")}
    store_state["signal_generation"] = block
    store_state["signal_generation_summary"] = sg_mod.candidate_block(store_state)
    return block


def _full_arsenal_block(store_state: dict, *, night_report: dict, readings: dict,
                        ts: str) -> dict:
    """THE FULL ARSENAL (Mega Phase 2) -- every remaining lever, wired and honest.

    One block that runs the newly-activated weapons on the LIVE tape and the REAL report
    and returns their measured readings for the Letter:

      * A  the World Cloner (Lever 14): synthetic tapes + the KS/ACF/Hurst quality gate;
      * B  the Modular Army (Lever 11): the module marketplace + the best assemblies;
      * C  Self-Play (Lever 18): a sparring session across the survivors + the ladder;
      * D  the ML Families (Lever 4): the learned families' live fire counts;
      * E  the Echo State Network (Lever 22): the live prediction + pattern recognition;
      * F  the Diplomat (Lever 16): this round's operator decision and its reasoning;
      * G  the Anima (Lever 17): the current situation's historical analogues;
      * H  the Grok Sensor (Section H): X sentiment (honest when no key) + news pulse;
      * I  the Kelly Sizing (Section I): the position-size suggestion + anti-ruin;
      * J  the Second Sage (Section J): the local always-present model's availability.

    Fail-open per lever: a fault in one weapon never breaks the cycle -- that lever
    reports itself unavailable and the rest continue. Honest: every unmeasured axis is
    ``None``, never invented.
    """
    block: dict = {"version": 2, "measured": False, "levers": {}}

    # -- the live frames: a couple of operational pairs with real tape. -----------
    DEFAULT_PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "EURGBP", "AUDJPY")
    pairs = [str(p) for p in ((night_report.get("volume_law") or {}).get("pairs") or [])]
    if not pairs:
        pairs = list((readings or {}).keys())
    if not pairs:
        pairs = list(DEFAULT_PAIRS)
    frames_by_pair: dict = {}
    try:
        from app.quant import signal_generator as sg_mod

        for p in pairs[:5]:
            F = sg_mod.frames_from_tape(p)
            if F is not None:
                frames_by_pair[p] = F
    except Exception:  # noqa: BLE001
        frames_by_pair = {}
    lead_pair = next(iter(frames_by_pair), None)
    lead_F = frames_by_pair.get(lead_pair) if lead_pair else None
    block["pairs_with_tape"] = sorted(frames_by_pair.keys())

    # -- Section A: the world cloner. ------------------------------------------
    try:
        from app.core.data import load_parquet
        from app.quant import world_generator as wg

        real = {}
        for p in list(frames_by_pair.keys())[:3]:
            try:
                real[p] = load_parquet(f"data/history/{p}_M15.parquet").tail(3000).reset_index(drop=True)
            except Exception:  # noqa: BLE001
                continue
        block["levers"]["world_cloner"] = wg.world_block(real, seed=7) if real else {
            "measured": False, "reading": "clonatore di mondi: nessun tape reale"}
    except Exception as exc:  # noqa: BLE001
        block["levers"]["world_cloner"] = {"measured": False,
                                           "reading": f"clonatore di mondi: errore {type(exc).__name__}"}

    # -- Section B: the modular army. ------------------------------------------
    try:
        from app.factory import modules as modules_mod

        block["levers"]["modular_army"] = modules_mod.modules_block(
            store_state.get("module_scores") or {}, top=5)
    except Exception as exc:  # noqa: BLE001
        block["levers"]["modular_army"] = {"measured": False,
                                           "reading": f"esercito modulare: errore {type(exc).__name__}"}

    # -- Section C: self-play. -------------------------------------------------
    try:
        from app.factory import self_play as sp_mod
        from app.quant import signal_generator as sg_mod

        recovered, _unrec, _src = sg_mod.recover_genomes(night_report)
        pop = [{"genome": r.get("genome"), "signature": r["genome"].signature()}
               for r in recovered if r.get("genome") is not None]
        universe = ({lead_pair: lead_F} if lead_F is not None else {})
        block["levers"]["self_play"] = sp_mod.self_play_block(
            pop, universe=universe,
            survival_records=store_state.get("self_play_records") or {})
    except Exception as exc:  # noqa: BLE001
        block["levers"]["self_play"] = {"measured": False,
                                        "reading": f"self-play: errore {type(exc).__name__}"}

    # -- Section D: the ML families (live fire counts). ------------------------
    try:
        from app.quant import ml_models as ml
        from app.quant import seeds as seeds_mod
        from app.quant import signals as sg_signals

        rows = {}
        if lead_F is not None:
            for fam in ("ml_gradient_boosting", "ml_lstm_pattern", "ml_bayesian_regime"):
                g = seeds_mod.seed_for(fam)
                long_m, short_m = ml.walk_forward_masks(lead_F, g)
                rows[fam] = {"long": int(long_m.sum()), "short": int(short_m.sum())}
        fired = sum(v["long"] + v["short"] for v in rows.values())
        block["levers"]["ml_families"] = {
            "families": rows, "n_fired": fired, "pair": lead_pair,
            "measured": bool(rows),
            "reading": (f"famiglie ML: {fired} segnali appresi su {lead_pair}"
                        if rows else "famiglie ML: nessun tape"),
        }
    except Exception as exc:  # noqa: BLE001
        block["levers"]["ml_families"] = {"measured": False,
                                          "reading": f"famiglie ML: errore {type(exc).__name__}"}

    # -- Section E: the echo state network. ------------------------------------
    try:
        from app.quant import echo_network as esn_mod

        block["levers"]["echo_network"] = (esn_mod.echo_block(lead_F)
                                           if lead_F is not None else
                                           {"measured": False, "reading": "esn: nessun tape"})
    except Exception as exc:  # noqa: BLE001
        block["levers"]["echo_network"] = {"measured": False,
                                           "reading": f"esn: errore {type(exc).__name__}"}

    # -- Section F: the diplomat. ----------------------------------------------
    try:
        from app.factory import diplomat as dip_mod

        pop_rows = [{"family": r.get("family"),
                     "net_r": r.get("net_r", r.get("adv_net_r"))}
                    for r in (night_report.get("final_population") or [])]
        block["levers"]["diplomat"] = dip_mod.diplomat_block(
            pop_rows,
            performance_history=store_state.get("diplomat_performance_history") or [],
            operator_history=store_state.get("diplomat_operator_history") or [])
    except Exception as exc:  # noqa: BLE001
        block["levers"]["diplomat"] = {"measured": False,
                                       "reading": f"diplomato: errore {type(exc).__name__}"}

    # -- Section G: the anima. -------------------------------------------------
    try:
        from app.quant import anima as anima_mod

        other_F = None
        for p, F in frames_by_pair.items():
            if p != lead_pair:
                other_F = F
                break
        block["levers"]["anima"] = (anima_mod.anima_block(lead_F, other_F=other_F)
                                    if lead_F is not None else
                                    {"measured": False, "reading": "anima: nessun tape"})
    except Exception as exc:  # noqa: BLE001
        block["levers"]["anima"] = {"measured": False,
                                    "reading": f"anima: errore {type(exc).__name__}"}

    # -- Section H: the Grok sensor. -------------------------------------------
    try:
        from app.quant import sentiment as sent_mod

        ear = ((store_state.get("web_watch") or {}).get("ear")
               or webwatch_mod.social_ear(
                   (store_state.get("web_watch") or {}).get("fear_greed"),
                   (store_state.get("web_watch") or {}).get("reddit"),
                   (store_state.get("web_watch") or {}).get("stocktwits")))
        block["levers"]["grok_sensor"] = sent_mod.sentiment_block(
            pair=(lead_pair or "EURUSD"), ear=ear)
    except Exception as exc:  # noqa: BLE001
        block["levers"]["grok_sensor"] = {"measured": False,
                                          "reading": f"Grok: errore {type(exc).__name__}"}

    # -- Section I: the Kelly sizing. ------------------------------------------
    try:
        from app.core import kelly as kelly_mod
        from app.quant import evaluator as ev, costs as costs_mod
        from app.quant.metrics import trade_net_r

        win_prob = None
        payoff = None
        returns_r: list[float] = []
        best = None
        for r in (night_report.get("leaderboard") or []):
            wr = r.get("adv_win_rate", r.get("win_rate"))
            if isinstance(wr, (int, float)):
                best = r
                win_prob = float(wr)
                payoff = float(r.get("target_rr") or 0.0) or None
                break
        if lead_F is not None and best is not None:
            recovered, _u, _s = sg_mod.recover_genomes(night_report)
            genome = next((x.get("genome") for x in recovered
                           if x.get("genome") is not None
                           and x["genome"].signature() == best.get("signature")), None)
            if genome is not None:
                rep = ev.evaluate(genome, {lead_pair: lead_F},
                                  ev.EvaluationConfig(cost_model=costs_mod.SELECTION_COST_MODEL))
                for t in rep.per_pair[lead_pair].trades:
                    returns_r.append(float(trade_net_r(t)))
        block["levers"]["kelly"] = kelly_mod.kelly_block(
            store_state, returns_r=returns_r or None,
            win_prob=win_prob, payoff=payoff,
            risk_pct=(1.0 if win_prob is not None else None))
    except Exception as exc:  # noqa: BLE001
        block["levers"]["kelly"] = {"measured": False,
                                    "reading": f"Kelly: errore {type(exc).__name__}"}

    # -- Section J: the Sage decision. The LOCAL model is CANCELLED (the CEO's
    # ruling): the lever now reports the DeepSeek-only configuration honestly. ----
    try:
        local = sage_mod.LocalSageBackend()
        block["levers"]["local_sage"] = {
            "available": bool(local.available()),
            "cancelled": bool(sage_mod.SAGE_LOCAL_CANCELLED),
            "backend": None,
            "measured": bool(local.available()),
            "reading": ("Saggio: DeepSeek soltanto (Flash orario + Pro profondo); "
                        "il modello locale e' cancellato"),
        }
    except Exception as exc:  # noqa: BLE001
        block["levers"]["local_sage"] = {"measured": False,
                                         "reading": f"Saggio locale: errore {type(exc).__name__}"}

    measured = [k for k, v in block["levers"].items() if (v or {}).get("measured")]
    block["measured"] = bool(measured)
    block["levers_measured"] = measured
    block["n_levers"] = len(block["levers"])
    block["reading"] = (f"ARSENALE COMPLETO: {len(measured)}/{len(block['levers'])} leve "
                        f"misurate dal vivo")
    store_state["full_arsenal"] = block
    return block


def run_cycle(store_state: dict, *, night_report: dict | None = None,
              powerups: dict | None = None, capacity_trials: int | None = None,
              patrol: bool = False, ts: str = "", pro: bool = False) -> dict:
    """Run ONE deliberation cycle; mutate ``store_state`` in place; return the block.

    The block is what the night bulletin prints: the Council's decisions (with
    reasoning), the network's exchanges, the market, the census, the dreams, and
    the self-model. Nothing is invented; a missing reading stays missing.

    ``pro`` is the Council's explicit request for an extraordinary Pro session (THE
    BUDGET DOCTRINE: Pro is the exception). It defaults False, so an ordinary cycle
    consults the cheap Flash head.
    """
    night_report = night_report or {}
    powerups = powerups or {}
    agents = ["king-trend", "king-range", "philosopher-1", "explorer-1", "sniper-1"]
    # A state loaded from an older commit may predate a block this cycle reads;
    # seed the missing keys so a schema addition never crashes the cycle (the bug
    # ``council_cycle ... || true`` used to swallow on CI).
    backfill_state(store_state)

    # 0. THE EPISODIC PALACE (E6): fold tonight's REAL trade narratives into the
    #    persistent state, so creative sleep (step 5) has episodes to consolidate
    #    and reconnect. Bounded to the most recent tail (the palace, not a hoard).
    #    Without this the palace was always empty and every dream was silent (BUG-7).
    episodes = night_report.get("episodes") or []
    if episodes:
        store_state["episodes"] = (list(store_state.get("episodes") or []) +
                                   list(episodes))[-500:]

    # 1. curiosity + self-model first (they shape the ideas and the world).
    cov = _realm_coverage(night_report)
    #    THE COLLECTIVE PULL (LAW 7): curiosity is SUMMED over the civilization's
    #    agents, so a thin zone's pull scales with how many minds point at it. The
    #    cycle once built ONE instinct per zone (pull <= 1.0), which can never clear
    #    the RAID_THRESHOLD (1.5) — the raid channel was dead. Every agent now points
    #    at every zone (strength 1.0), the honest reading of "collective curiosity".
    n_agents = len(store_state["population"]) or len(agents)
    instincts = [curiosity.curiosity_instinct(zone=r, coverage=c, strength=1.0)
                 for r, c in cov.items() for _ in range(n_agents)]
    cmap = curiosity.curiosity_map(instincts)

    perf = _performance(night_report, cov)
    selfm = sm.self_model(population=len(store_state["population"]) or len(agents),
                          kings=2, coverage=cov, performance=perf,
                          ambition="climb the RR curve toward 1:6, on evidence")

    # 2. THE MARKET OF IDEAS (LAW 5, Cure 1): settle the ideas forged last cycle
    #    from the night's REAL outcome (backers of a winner gain, backers of a
    #    loser gain nothing), then grant every agent its per-cycle allowance --
    #    modulated by what it earned and lost -- so nobody starves to zero. Only
    #    THEN do agents back the open ideas with the attention they now hold.
    economy_block = _settle_and_replenish(
        store_state, night_report=night_report, agents=agents, spent={}, ts=ts)
    _seed_ideas(store_state, curiosity_map=cmap, self_model=selfm)
    spent = _back(store_state, agents=agents)

    # 3. the Council deliberates over the world and records its minutes.
    world = world_from(night_report, powerups, store_state,
                       capacity_trials=capacity_trials)
    session = council.council_session(world, ts=ts)
    store_state["ledger"].extend(session["ledger"])
    # The ideas the Council forged into bursts are marked, so NEXT cycle they
    # settle from that burst's measured outcome (the value flow, Cure 1).
    _forge_ideas(store_state, session=session, ts=ts)

    # 3b. THE ONE BRAIN (the collective that decides): integrate every faculty over
    #     the SAME night, weigh the minds by measured reliability, and record the
    #     decisions with their soul, the vetoes, the world model, the collective
    #     mood, the synergy score, and the play. Honest: an unmeasured axis stays
    #     None — the One Brain says "nothing" rather than forcing a trade.
    try:
        one_brain_block = obc.run_one_brain(store_state, night_report=night_report,
                                            agents=agents, ts=ts)
    except Exception:  # noqa: BLE001 — fail-open: the mind is new; a fault in it
        # must never cost the cycle's other work. The refusal is honest (no mind
        # measured this cycle), never a fabricated verdict.
        one_brain_block = {"version": 0, "reading": "One Brain: nessuna lettura "
                           "questa notte (fault tollerato, onesto)", "decisions": [],
                           "play_items": [], "mood": {}, "model": {},
                           "model_change": {}, "theories": [], "belief_ledger": [],
                           "play": {}, "synergy": None, "generation": {},
                           "bias_audit": {}, "minds": {}, "weights": {},
                           "affects": {}, "packages_detail": [], "vetoes": [],
                           "kelly": [], "packages": 0}
    # The playground's play slots (Vygotsky: try a role with NO capital at risk)
    # join the queue so the body actually plays them. Bounded: the play item carries
    # its ``ts``, so dedup alone never fires across nights — an unbounded queue
    # would grow forever (state drift, BUG-3b). Keep only the most recent plays.
    store_state.setdefault("play_queue", [])
    for it in one_brain_block.get("play_items") or []:
        if it not in store_state["play_queue"]:
            store_state["play_queue"].append(it)
        store_state["play_queue"] = store_state["play_queue"][-12:]
        # The play is a recorded decision (with its reason): the minutes carry what
        # the civilization tried for novelty's sake (Vygotsky's play).
        store_state["ledger"].append(ledger.decision_entry(
            kind="play", what=f"play: {it['shape']} ({it['agent']})",
            why=it["why"], evidence=f"shape={it['shape']}, risk=0",
            expected_effect="novelty flows to the Market of Ideas"))

    # The One Brain's OWN decisions ride the minutes with their soul (which minds
    # supported, which opposed, the mood, the simulation's fears) — a trade, or its
    # honest refusal, is auditable forever.
    for d in one_brain_block.get("decisions") or []:
        prop = d.get("proposal") or {}
        if d.get("decided"):
            soul = d.get("soul") or {}
            store_state["ledger"].append(ledger.decision_entry(
                kind="one_brain", what=f"decide: {prop.get('idea')}",
                why=("the integrated field cleared: analysis sound, intuitions "
                     "agree, mood calm, simulation's fragile points covered, "
                     "theory alive — the One Brain decides"),
                evidence=(f"field={d.get('field', {}).get('score')}, "
                          f"supporters={soul.get('supporters')}, "
                          f"opposers={soul.get('opposers')}, mood={soul.get('mood')}"),
                expected_effect="a decision with a soul enters the record"))
        else:
            store_state["ledger"].append(ledger.decision_entry(
                kind="one_brain", what=f"refuse: {prop.get('idea')}",
                why=("the integrated field did not clear — the One Brain says "
                     "nothing rather than forcing a trade: "
                     + "; ".join(d.get("reasons") or [])),
                evidence=f"field={d.get('field', {}).get('score')}",
                expected_effect="no trade; the honest refusal is recorded"))

    # The economy's audit trail: every settle and every allowance rides the STATE
    # LEDGER with its WHY, so the market's value flow is provable, not implied.
    for s in economy_block["settles"]:
        store_state["ledger"].append(ledger.decision_entry(
            kind="settle_idea",
            what=f"settle the idea ({s['outcome_kind']}): {s['idea']}",
            why=(f"the idea resolved '{s['outcome_kind']}' with a measured outcome "
                 f"{s['realized_value']:+.3f} net R — its backers are paid "
                 f"reputation from the REAL result, or gain nothing (LAW 5, Cure 1)"),
            evidence=f"realized_value={s['realized_value']}, backers={s['backers']}",
            expected_effect="backers of winners gain attention; backers of losers gain none"))
    store_state["ledger"].append(ledger.decision_entry(
        kind="replenish_attention",
        what="grant every agent its per-cycle attention allowance",
        why=("the market must never freeze: each cycle every agent is refilled "
             "(bounded), modulated by what it earned and lost — attention is "
             "earned, not printed without limit"),
        evidence=f"outcome={economy_block['outcome']}, granted={economy_block['granted']}",
        expected_effect="agents who lost their stake can bet again; the market stays alive"))

    # 4. the network speaks: broadcast the decisions, ask the open questions.
    for d in session["decisions"]:
        network.record_exchange(store_state["bus"], sender="council",
                                kind="decision", body=f"{d['kind']}: {d['what']}")
    for b in session["bursts"]:
        network.broadcast(store_state["bus"], sender="council",
                          body=f"FORGING a {b['trials']}-trial burst: {b['idea']}")
        network.post_idea(store_state["interbrain"], author="council",
                          idea=b["idea"], parents=[b["idea"]])

    # 4b. THE APEX TONGUE (Part Six): the Council's decisions are also recorded in
    #     the civilization's OWN language, on their channel. The WISE SILENCE rule
    #     decides whether the mouth opens at all: a decision that CHANGES work is
    #     RELEVANT; an empty cycle stays SILENT (the work's flow is the default).
    _speak_in_tongue(store_state, session=session, cmap=cmap, ts=ts)

    # 4b'. THE QUESTION->ANSWER PIPE (D1/D5): a felt need with no standing directive
    #      is ASKED on the bus; a need the register already covers is ANSWERED from
    #      it. This revives the dead question channel: the civilization asks, and it
    #      answers what the CEO has already ruled on -- questions do not rot silent.
    fresh_reqs, granted_reqs = _ceo_requests(store_state, cmap)
    for req in fresh_reqs:
        network.ask(store_state["bus"], sender="council", body=req, ts=ts)
    for req in granted_reqs:
        # the register already covers it: the standing order is BROADCAST, not re-asked
        network.broadcast(store_state["bus"], sender="ceo-directive",
                          body=f"direttiva permanente: {req}", ts=ts)
    store_state["standing_orders"] = list(granted_reqs)

    # 4c. THE DELIBERATION CEREMONY (D2) + THE NETWORK'S HEALTH (D5): the Council's
    #     deliberation is recorded with its tension named (only on a real conflict)
    #     and its minorities kept; the night's conversation is measured (including
    #     the UNANSWERED questions), and a collapsed diversity of opinion (the ECHO
    #     ALARM) triggers an assigned devil's advocate. Honest: an empty cycle
    #     records an honest empty deliberation, never a fabricated debate.
    voices = [{"who": str(d.get("author") or "council"), "stance": "for",
               "mode": tongue.KNOW, "why": d.get("why")}
              for d in session["decisions"]]
    question = (str(session["decisions"][0]["what"]) if session["decisions"]
                else "what should the civilization do next?")
    deliberation = network.deliberation(
        question=question, voices=voices,
        resolution=f"{len(session['decisions'])} decisione/i registrate", ts=ts)
    conv = network.conversation_metrics(
        store_state["bus"], exchanges=store_state.get("exchanges", []))
    echo = network.echo_alarm(
        [{"position": e.get("word") or e.get("body")}
         for e in store_state.get("exchanges", [])])
    conv["echo"] = echo
    if echo["alarm"]:
        da = network.devils_advocate(consensus=question, assignee="philosopher", ts=ts)
        store_state.setdefault("devils_advocate", []).append(da)
        network.record_exchange(store_state["bus"], sender="guardian",
                                kind="decision", body=da["reading"])

    # 5. creative sleep when the room is quiet (LAW 8) -> dream-born ideas enter.
    if dreams.is_quiet(store_state["bus"]):
        d = dreams.dream(store_state.get("episodes", []), bus=store_state["bus"], ts=ts)
        store_state["dreams"].append(d)
        for born in d["born_ideas"]:
            network.post_idea(store_state["interbrain"], author="dream",
                              idea=born["idea"])
            store_state["ideas"].append({"idea": born["idea"], "author": "dream",
                                         "attention": 0.0, "backers": [],
                                         "status": "open", "parents": []})

    # 6. THE GAZE (the civilization opens its EYES). After the night's mind has
    #    dreamed, it SEES: the market rendered as a multi-timeframe chart (built
    #    from the REAL tape, when the runner published one), the day's heat map, the
    #    tape ribbon, and the visual watch over the world (read-only). What it sees
    #    enters the VISUAL MEMORY (a shape recognised, a scene archived, a déjà-vu),
    #    the FLOW slots (purposeless seeing, where intuition is born), and the
    #    sighting broadcasts. The eyes INFORM — they never trade and never override
    #    the Law. Honest: a market with no tape published renders blind, and a page
    #    that will not open is reported, never faked.
    gaze_block = _gaze(store_state, night_report=night_report, agents=agents, ts=ts,
                       patrol=patrol)

    # 6b. the census (LAW 4): the weak die (by record), then the garden answers felt
    #    needs — every birth and death recorded in the minutes WITH its reason.
    deaths: list[dict] = []
    for sig in census.weakest(store_state["population"]):
        victim = next(a for a in store_state["population"] if a["signature"] == sig)
        reason = (f"{victim['signature']} lived {victim.get('lived_cycles', 0)} "
                  f"cycle(s) and contributed nothing — weak by record, not by mood")
        legacy = census.retire(store_state["population"], signature=sig,
                               cause="apoptosis",
                               lesson=f"no contribution in {victim.get('lived_cycles', 0)} cycles")
        store_state["legacy"].append(legacy)
        store_state["ledger"].append(ledger.decision_entry(
            kind="death", what=f"retire {sig} (apoptosis)",
            why=reason, evidence=f"contributions={victim.get('contributions', 0)}",
            expected_effect="the seat frees for a child of the King; the lesson stays"))
        deaths.append({"signature": sig, "why": reason})

    births: list[dict] = []
    needs = census.birth_need(realm_coverage=cov)
    # THE RETRO-CHANNEL (dual inheritance): the culture's measured cognitive traits
    # flow back into the gene pool. A king-child inherits the parent's COGNITIVE DNA
    # (calibration, intuition strength, emotional sensitivity, simulation vividness)
    # alongside its strategy DNA.
    parent_axes = (store_state.get("one_brain") or {}).get("weights") or {}
    parent = next(iter(parent_axes), "king-trend")
    cog_dna = mind.cognitive_dna({
        "calibration": parent_axes.get(parent),
        "intuition_strength": parent_axes.get(parent),
        "emotional_sensitivity": parent_axes.get(parent),
        "simulation_vividness": parent_axes.get(parent)})
    for n in needs:
        sig = f"{n['spawn']}-{len(store_state['population']) + 1}"
        if len(store_state["population"]) < census.MAX_POPULATION:
            ag = census.spawn(store_state["population"], signature=sig,
                              role=n["spawn"], parents=["king-trend"],
                              dna={"cognitive": cog_dna})
            census.school_newborn(ag, culture=store_state["culture"])
            store_state["ledger"].append(ledger.decision_entry(
                kind="birth", what=f"birth {sig} ({n['spawn']})",
                why=n["why"], evidence=f"need={n['need']}, cognitive_dna={cog_dna}",
                expected_effect="the population answers a felt need, with culture and cognitive DNA"))
            births.append({"signature": sig, "role": n["spawn"], "why": n["why"],
                           "cognitive_dna": cog_dna})

    # 6b. THE CROSS-GENERATIONAL DIALOGUE (D3): each newborn, before it acts, puts a
    #     real question to the ancestors ("has anyone tried this? what happened?")
    #     and the retired minds with a recorded lesson answer from OFFICE HOURS. The
    #     dead teach the living through structured memory, not only DNA. Honest: no
    #     overlap -> no answer; a civilization with no legacy asks into the silence.
    ancestry: list[dict] = []
    for b in births:
        question = f"what happened to the {b['role']} family in this regime?"
        hours = census.office_hours(store_state["legacy"], question, k=1)
        mentor = hours[0] if hours else None
        if mentor:
            network.answer(store_state["bus"], sender=str(mentor.get("mentor") or "ancestor"),
                           body=f"per {b['signature']}: {mentor.get('answer')}", ts=ts)
        ancestry.append({"newborn": b["signature"], "question": question,
                         "mentor": (mentor or {}).get("mentor"),
                         "answer": (mentor or {}).get("answer"),
                         "reading": (f"{b['signature']} ha interrogato gli antenati: "
                                     + (f"{mentor.get('mentor')} risponde"
                                        if mentor else "nessuno risponde (silenzio)"))})

    # 6c. THE LIVING DAY (Parts Two-Three). First the FREEDOM: any free agent may,
    #     at any moment, ask for work — the cycle accepts the spontaneous requests
    #     its play slots and its free minds imply (bounded), records them, and the
    #     queue accepts them (no permission, no slot). Then the cycle records its
    #     REAL acts (a thought per deliberating mind, a vision when the eyes opened,
    #     an invention per body forged) and reads the day: the Idleness Guardian's
    #     dormienti, the collective pulse and its trend, the engagement
    #     (voluntary/assigned), the Balance Law's advice, the circadian phase, and
    #     the streams' vital signs. Honest: an axis with no data stays "non misurato".
    spontaneous_items = _spontaneous_work(store_state, agents=agents, ts=ts)
    for it in spontaneous_items:
        if it not in store_state["spontaneous_work"]:
            store_state["spontaneous_work"].append(it)
    store_state["spontaneous_work"] = store_state["spontaneous_work"][-30:]
    acts = living_mod.record_life(
        store_state, agents=agents, ts=ts,
        thought_agents=[str(d.get("author") or "council") for d in session["decisions"]],
        vision=bool(gaze_block.get("sightings") or gaze_block.get("ascii")),
        inventions=len(births), spontaneous=len(spontaneous_items))
    life = living_mod.living_block(
        store_state, agents=agents, ts=ts, vision=acts["vision"] > 0,
        inventions=acts["invention"], spontaneous=acts["spontaneous"])

    # 6d. THE SAGE WITHIN (Part Four): the throne consults over the civilization's
    #     full vertical. The insights carry the mode "IL SAGGIO DICE" and enter the
    #     interbrain as ADVICE, weighed like any other voice; the Council stays
    #     sovereign. A missing model is honest: the stub provokes structurally and
    #     says the throne awaits its king. Every insight is logged for its outcome
    #     track record (the Sage EARNS its weight).
    sage_block = _sage_within(store_state, night_report=night_report, ts=ts, pro=pro)

    # 6e. THE SAGE'S PRESENCE (THE FULL VOICE, Part Two): the throne is no longer
    #     only summoned -- it WATCHES the living feed and, within its daily budget,
    #     may SPEAK UNPROMPTED (tagged SPONTANEO, the Flash head). Its words flow
    #     into the interbrain like any free voice; the reading (what it sees, the
    #     alerts, the cost) rides the block. Fail-open: the presence never breaks
    #     the cycle, and the Sage still never commands.
    presence_block = presence_mod.presence_block(store_state, report=night_report, ts=ts)
    spontaneous = presence_mod.spontaneous_cycle(store_state, ts=ts,
                                                 report=night_report)
    presence_block["spontaneous"] = spontaneous
    sage_block["presence"] = presence_block

    # 6f. THE DRAGON (the dominant intelligence, six roles): the strongest mind
    #     THINKS perpetually, DIRECTS the research, JUDGES the biggest calls, WRITES
    #     the CEO's analysis, and TRAINS the agents -- all under the laws (it advises,
    #     the Council is sovereign) and all transparently measured. The Dragon's own
    #     thought enters the interbrain with the highest earned weight and is
    #     SELF-FUNDED in the market (the founding bonus). Fail-open: the Dragon
    #     rests honestly ("il Drago riposa") and never breaks the cycle.
    dragon_beat = dragon_mod.dragon_cycle(
        store_state, ts=ts, report=night_report, decisions=session["decisions"],
        agents=store_state.get("population"), mode="think")
    dragon_block = dragon_mod.dragon_block(store_state, report=night_report, ts=ts,
                                           decisions=session["decisions"])
    dragon_block["beat"] = dragon_beat
    sage_block["dragon"] = dragon_block

    # 6g. THE FALCON + THE PIPE + THE WEB WATCH (THE PERPETUAL MOTION, Parts One-Three):
    #     the falcon reduces its live eyes into the summary the state artifact + the
    #     Letter read; the web watch reports the standing guard, the news pulse, the
    #     event horizon and the social ear; the pipe folds the VM's vital signs into
    #     the UNIFIED STATE ARTIFACT so GitHub always holds the current numbers. All
    #     fail-open and all honest: an unmeasured axis stays None ("non misurato").
    falcon_block = falcon_mod.falcon_block(store_state, now_epoch=_epoch(ts))
    store_state["falcon_summary"] = falcon_block
    web_block = webwatch_mod.web_watch_block(store_state, now=ts)
    store_state.setdefault("pipe", {})
    store_state["pipe"]["last_state_ts"] = ts
    state_artifact = pipe_mod.apex_state_artifact(store_state, ts=ts)
    store_state["apex_state"] = state_artifact
    pipe_block = pipe_mod.pipe_block(
        store_state, last_push_ts=store_state["pipe"].get("last_push_ts", ""),
        now_ts=ts)
    flow_block = flow_mod.flow_report(store_state, ts=ts)

    # 6h. THE FIRST ASCENSION (Jumps 4, 3, 6): the system stops living in the past and
    #     starts living in the PRESENT. The REGIME WATCHTOWER detects a pair's regime
    #     shift, fires "IL MONDO CAMBIA", and reconfigures (pause the old families,
    #     boost the new). The FORWARD-TEST CHAMBER enrolls the survivors and scores them
    #     on the last hour's REAL data (the dual score weighs the present more). The
    #     PRESENT SABOTEUR attacks the active portfolio with what could happen NOW
    #     (flash crash / spread explosion / news shock) and alarms past the threshold.
    #     All fail-open and all honest: an unmeasured axis stays None.
    readings = (store_state.get("falcon") or {}).get("readings") or {}
    regime_block = regime_mod.regime_watch_block(store_state, readings=readings, ts=ts)

    lb = night_report.get("leaderboard") or []
    backtest_scores = {}
    for row in lb:
        sid = str(row.get("signature") or row.get("family") or "")
        score = row.get("adv_lb", row.get("wilson_lb"))
        if sid and isinstance(score, (int, float)):
            backtest_scores[sid] = float(score)
            forward_mod.enroll(store_state, sid)
    for row in lb:
        sid = str(row.get("signature") or row.get("family") or "")
        if not sid:
            continue
        # a REAL forward window: the strategy's realized R on the last hour's judged
        # rows. Honest: no measured net_r -> no window (never a fabricated outcome).
        net_r = row.get("adv_net_r", row.get("net_r"))
        if isinstance(net_r, (int, float)) and forward_mod.is_enrolled(store_state, sid):
            forward_mod.record_window(store_state, sid, ts=ts, outcome_r=net_r)
    forward_block = forward_mod.forward_test_block(store_state, backtest_scores)

    portfolio = stress_mod.portfolio_from_leaderboard(lb)
    stress_block = stress_mod.stress_test_block(
        store_state, portfolio=portfolio, reading=readings, ts=ts)
    # the DRAGON'S REDIRECT + defensive advice: a regime shift or a survival alarm
    # triggers an EXTRAORDINARY Dragon briefing (Flash, immediate).
    extraordinary = _extraordinary_dragon(
        store_state, regime_block=regime_block, stress_block=stress_block,
        dragon_mod=dragon_mod, ts=ts)
    dragon_block["extraordinary"] = extraordinary

    # 6i. THE SECOND ASCENSION (Jumps 2 + 5 + 1): the COLLECTIVE MODEL folds the
    #     agents' private beliefs into one shared belief state and measures the
    #     civilization's coherence; the AUTOBIOGRAPHY writes the day's chapter from the
    #     real events (with the identity trajectory); the Dragon's flow-awareness learns
    #     what the micro-tournaments taught. All fail-open and all honest: an
    #     unmeasured axis stays None.
    collective_block = _collective_model(
        store_state, regime_block=regime_block, forward_block=forward_block,
        stress_block=stress_block, ts=ts)
    autobiography_block = _autobiography(
        store_state, night_report=night_report, session=session, ts=ts)
    flow_dragon = _flow_dragon_awareness(store_state, flow_block=flow_block, ts=ts)

    # 6j. THE REAL HUNT (Parts One-Six): the system stops being a thinker that
    #     occasionally trades and becomes a PREDATOR. The CATHEDRAL evaluates the seven
    #     columns, runs the confidence cascade and the gate (7/7 CLASS A, 6/7 CLASS B);
    #     the three HUNTERS are evaluated WITHIN the Cathedral; the RED COUNCIL attacks
    #     a CLASS A case (the signal fires only if it SURVIVES) and, on survival, the
    #     TRADE TICKET is issued with the full WHY. All fail-open, all honest.
    # DEBT-063: publish the live readings + the detected microstructure events under
    # the keys the hunter context reads (they are the raw material for Alpha's sweep,
    # Bravo's reaction and Charlie's signature).
    store_state["falcon_readings"] = readings
    hot = falcon_mod.select_hot_pairs(readings)
    store_state["hot_pairs"] = hot
    store_state["micro_events"] = falcon_mod.detect_microstructure_events(
        readings, baseline=store_state.get("micro_baseline") or {})
    store_state["micro_baseline"] = {
        p: {"spread_pips": (rr or {}).get("spread_pips"),
            "tick_velocity": (rr or {}).get("tick_velocity")}
        for p, rr in (readings or {}).items()}
    hunt = _run_the_hunt(store_state, regime_block=regime_block,
                         forward_block=forward_block, readings=readings, ts=ts)
    cathedral_block = hunt["cathedral"]
    hunters_block = hunt["hunters"]
    red_council_block = hunt["red_council"]
    cascade_block = hunt["cascade"]
    # THE FIRST ACT (Mega Phase 1): the surviving strategies are asked, on the LIVE
    # tape, whether they would enter NOW -- every operational pair, every candidate
    # judged by the Cathedral. This is the bridge from thought to action.
    signal_block = _signal_generator_block(
        store_state, night_report=night_report, readings=readings,
        regime_block=regime_block, forward_block=forward_block, ts=ts)
    # THE FULL ARSENAL (Mega Phase 2): every remaining lever -- the world cloner, the
    # modular army, self-play, the ML families, the echo network, the diplomat, the
    # anima, the Grok sensor, the Kelly sizing, and the second (local) sage. Fail-open
    # per lever; every unmeasured axis stays None.
    arsenal_block = _full_arsenal_block(
        store_state, night_report=night_report, readings=readings, ts=ts)

    # every agent ages one cycle; the cycle's ideas credit their authors (the record
    # weakness is judged on).
    for a in store_state["population"]:
        a["lived_cycles"] = int(a.get("lived_cycles", 0)) + 1
    for idea in store_state["ideas"]:
        for a in store_state["population"]:
            if idea.get("author") == a["signature"]:
                a["contributions"] = int(a.get("contributions", 0)) + 1

    # 7. update the self-model and the cycle counter.
    store_state["self_model"] = selfm
    store_state["cycles"] += 1

    # 8. assemble the diary block the night bulletin (v3) prints.
    diary = _diary(night_report, store_state, selfm, cmap, session, agents)
    diary["births"] = births
    diary["deaths"] = deaths
    diary["one_brain"] = one_brain_block
    diary["deliberation"] = deliberation
    diary["conversation"] = conv
    diary["ancestry"] = ancestry
    diary["standing_orders"] = list(store_state.get("standing_orders") or [])
    diary["gaze"] = gaze_block
    diary["life"] = life
    diary["sage"] = sage_block
    diary["dragon"] = dragon_block
    diary["falcon"] = falcon_block
    diary["web_watch"] = web_block
    diary["pipe"] = pipe_block
    diary["flow"] = flow_block
    diary["regime"] = regime_block
    diary["forward_test"] = forward_block
    diary["stress_test"] = stress_block
    diary["spontaneous_work"] = store_state["spontaneous_work"]
    diary["collective"] = collective_block
    diary["autobiography"] = autobiography_block
    diary["dragon_mind"] = dragon_block.get("mind")
    diary["cathedral"] = cathedral_block
    diary["hunters"] = hunters_block
    diary["red_council"] = red_council_block
    diary["cascade"] = cascade_block
    diary["signal_generation"] = signal_block
    diary["full_arsenal"] = arsenal_block

    return {
        "cycle_ts": ts,
        "cycles": store_state["cycles"],
        "decisions": session["decisions"],
        "bursts": session["bursts"],
        "one_brain": one_brain_block,
        "network": network.network_digest(store_state["bus"], store_state["interbrain"]),
        "deliberation": deliberation,
        "conversation": conv,
        "ancestry": ancestry,
        "gaze": gaze_block,
        "life": life,
        "sage": sage_block,
        "dragon": dragon_block,
        "falcon": falcon_block,
        "web_watch": web_block,
        "pipe": pipe_block,
        "flow": flow_block,
        "regime": regime_block,
        "forward_test": forward_block,
        "stress_test": stress_block,
        "collective": collective_block,
        "autobiography": autobiography_block,
        "dragon_flow": flow_dragon,
        "cathedral": cathedral_block,
        "hunters": hunters_block,
        "red_council": red_council_block,
        "cascade": cascade_block,
        "signal_generation": signal_block,
        "full_arsenal": arsenal_block,
        "ticket": hunt["ticket"],
        "tongue": {
            "exchanges": store_state.get("exchanges", [])[-6:],
            "polyphony": tongue.polyphony_weights(store_state.get("exchanges", [])),
            "compressed": tongue.compress(
                usage={w: sum(1 for u in store_state.get("exchanges", [])
                              if u.get("word") == w) for w in tongue.VOCAB}),
        },
        "market": economy.market_digest(store_state["ideas"], store_state["reputations"]),
        "economy": {"outcome": economy_block["outcome"],
                    "settled": economy_block["settles"],
                    "granted": economy_block["granted"],
                    "earned": economy_block["earned"],
                    "lost": economy_block["lost"],
                    "spent": spent},
        "census": census.census_report(store_state["population"], store_state["legacy"]),
        "dreams": dreams.dream_report(store_state["dreams"]),
        "self_model": selfm,
        "curiosity": cmap,
        "minutes": ledger.minutes_digest(store_state["ledger"], last=6),
        "diary": diary,
    }


def _resample_tape(bars: list[dict], tf: str) -> list[dict]:
    """Resample base candles to ``tf`` (right-closed buckets) — pure, no pandas.

    A bucket is emitted only when it is complete (its span is fully covered by the
    base bars handed in), so the render is causal by construction: no bucket ever
    contains a bar that had not closed.
    """
    minutes = {"M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}.get(tf.upper())
    if not minutes:
        return []
    span = minutes * 60
    buckets: dict[int, list[dict]] = {}
    for b in bars:
        edge = (int(b["ts"]) // span + 1) * span      # right edge of the bucket
        buckets.setdefault(edge, []).append(b)
    out: list[dict] = []
    for edge in sorted(buckets):
        grp = buckets[edge]
        if len(grp) < max(1, minutes // 15):          # incomplete bucket -> not drawn
            continue
        out.append({"o": grp[0]["o"], "h": max(g["h"] for g in grp),
                    "l": min(g["l"] for g in grp), "c": grp[-1]["c"],
                    "v": sum(g.get("v") or 0.0 for g in grp)})
    return out


def _load_tape(pair: str, *, rows: int = 120) -> list[dict]:
    """Read the REAL tape tail for ``pair`` (empty when the tape is absent).

    The tapes are gitignored (they arrive via the release transport); when they are
    not on disk the eyes render BLIND — never a fabricated candle.
    """
    from app.core import data as data_mod
    for cand in (f"data/history/{pair}_M15.parquet", f"data/{pair}_M15.parquet"):
        try:
            df = data_mod.load_parquet(cand)
        except Exception:  # noqa: BLE001 — no tape -> honest blindness
            continue
        tail = df.tail(rows).to_dict("records")
        return [{"ts": int(r["ts"]), "o": float(r["open"]), "h": float(r["high"]),
                 "l": float(r["low"]), "c": float(r["close"]),
                 "v": float(r.get("volume") or 0.0)} for r in tail]
    return []


def _gaze(state: dict, *, night_report: dict, agents: list[str], ts: str,
          patrol: bool = False) -> dict:
    """The cycle's EYES: render the market, watch the world, absorb, remember.

    Returns the gaze block the diary and the Letter print. Everything is honest:
    a missing tape renders blind, a refused page is reported, an unmeasured heat
    map cell stays neutral. The eyes inform; they never trade.
    """
    g = state.setdefault("gaze", {"monitors": [], "visual_library": [], "archive": [],
                                  "flow": [], "intuitions": [], "patrols": [],
                                  "deja_vu": [], "sightings": []})
    for key, default in (("monitors", []), ("visual_library", []), ("archive", []),
                         ("flow", []), ("intuitions", []), ("patrols", []),
                         ("deja_vu", []), ("sightings", [])):
        g.setdefault(key, default)
    sightings: list[dict] = []

    # --- the primary pair: the first REAL currency pair the report names ---------
    lb = night_report.get("leaderboard") or []
    pairs = [str(p) for p in ((night_report.get("volume_law") or {}).get("pairs") or [])]
    pair = pairs[0] if pairs else (str(lb[0].get("family")) if lb else "EURUSD")
    bars = _load_tape(pair)
    eyes_open = bool(bars)
    image_shas: dict[str, str] = {}
    ascii_preview = None
    if eyes_open:
        base = bars[-90:]
        frames_by_tf = {"M15": {"pair": pair, "tf": "M15", "candles": base}}
        for tf in ("H1", "H4", "D1"):
            rs = _resample_tape(bars, tf)
            if rs:
                frames_by_tf[tf] = {"pair": pair, "tf": tf, "candles": rs}
        image_shas["multi_timeframe"] = hashlib.sha256(
            gaze_mod.render_multi_timeframe(pair, frames_by_tf)).hexdigest()
        image_shas["tape_flow"] = hashlib.sha256(
            gaze_mod.render_tape([b["c"] for b in bars])).hexdigest()
        # the DOM wall is built from the REAL last bar's range (a stand-in for depth:
        # the tape has no book, so the wall is the honest range, not an invented book)
        last = bars[-1]
        image_shas["dom_wall"] = hashlib.sha256(
            gaze_mod.render_dom_wall([(last["l"], last["h"] - last["l"])],
                                     [(last["h"], last["h"] - last["l"])])).hexdigest()
        ascii_preview = gaze_mod.ascii_chart(bars[-60:])
    # the heat map: every operational PAIR as a cell, red->green by its REAL 24h
    # change (the whole battlefield in one glance). An unreadable pair is neutral.
    heat_cells: list[dict] = []
    for p in pairs:
        pb = _load_tape(p, rows=96)
        ch_v = None
        if len(pb) >= 2 and pb[0]["o"]:
            ch_v = (pb[-1]["c"] - pb[0]["o"]) / pb[0]["o"]
        heat_cells.append({"pair": p, "change": ch_v})
    image_shas["heatmap"] = hashlib.sha256(gaze_mod.render_heatmap(heat_cells)).hexdigest()
    for view, sha in image_shas.items():
        g["monitors"].append({"view": view, "pair": pair, "sha256": sha, "ts": ts})
    g["monitors"] = g["monitors"][-24:]

    # --- the VISUAL MEMORY: recognise the shape, archive the moment --------------
    signature = gaze_mod.visual_signature(bars[-60:]) if eyes_open else None
    recognition = gaze_mod.visual_recognise(g["visual_library"], signature)
    deja = gaze_mod.deja_vu(g["archive"], signature)
    if deja:
        g["deja_vu"].append({**deja, "ts_seen": ts})
        g["deja_vu"] = g["deja_vu"][-12:]
        sightings.append({"mode": "VEDO", "what": f"déjà-vu: {deja['reading']}",
                          "agent": "council"})
    if signature:
        gaze_mod.remember_visual(g["visual_library"], signature=signature,
                                 label=f"scene-{pair}", resolved_up=bool(
                                     isinstance(lb[0].get("adv_lb"), (int, float))
                                     and float(lb[0]["adv_lb"]) >= 0.45) if lb else False,
                                 ts=ts)
        outcome = "su" if (lb and isinstance(lb[0].get("adv_lb"), (int, float))
                           and float(lb[0]["adv_lb"]) >= 0.45) else "giu'"
        gaze_mod.archive_scene(g["archive"], scene_id=f"{pair}@{ts or 'now'}", pair=pair,
                               tf="M15", signature=signature, outcome=outcome, ts=ts,
                               note=recognition.get("reading", ""))
        g["archive"] = g["archive"][-60:]
        g["visual_library"] = g["visual_library"][-60:]
        if eyes_open:
            sightings.append({"mode": "VEDO",
                              "what": f"{pair}: {recognition['reading']}",
                              "agent": "council"})

    # --- the VISUAL WATCH over the world (read-only) ----------------------------
    if patrol:
        p = navigator_mod.patrol(agents=agents, ts=ts)
        g["patrols"].append({"ts": ts, "ok_count": p["ok_count"],
                             "sightings": p["sightings"]})
        g["patrols"] = g["patrols"][-12:]
        for s in p["sightings"]:
            if s["ok"]:
                sightings.append({"mode": "VEDO",
                                  "what": f"vedetta {s['target']}: {s['title']}",
                                  "agent": s["agent"]})
            else:
                sightings.append({"mode": "SUSPECT",
                                  "what": f"vedetta {s['target']}: non visto "
                                          f"({s['error']})", "agent": s["agent"]})
        patrol_reading = p["reading"]
    else:
        patrol_reading = "vedetta: nessun turno questa notte (patrol disattivato)"

    # --- THE FLOW SLOTS: purposeless seeing (where intuition is born) ------------
    base_flow = gaze_mod.flow_budget(starving=(len(g["intuitions"]) == 0), base=2)
    for i in range(base_flow):
        agent = agents[i % len(agents)] if agents else "watcher"
        g["flow"].append(gaze_mod.flow_slot(agent=agent, pair=pair, ts=ts))
    g["flow"] = g["flow"][-12:]
    # the voluntary harvest: after watching, something MAY surface. Honest: the
    # text is drawn from what was actually seen (the recognition), never invented.
    if eyes_open and recognition.get("recognised"):
        h = gaze_mod.harvest_intuition(
            agent=agents[0] if agents else "watcher",
            text=f"dopo aver guardato {pair}, la forma mi ricorda "
                 f"{recognition.get('label')}", ts=ts)
        g["intuitions"].append(h)
        g["intuitions"] = g["intuitions"][-12:]
        sightings.append({"mode": "FLOW", "what": h["reading"], "agent": h["agent"]})

    # --- the sighting broadcasts: the eyes feed the interbrain ("I SEE") --------
    for s in sightings:
        network.broadcast(state["bus"], sender=str(s["agent"]),
                          body=f"[{s['mode']}] {s['what']}", ts=ts)
    g["sightings"] = (g["sightings"] + sightings)[-24:]

    return {
        "eyes_open": eyes_open,
        "pair": pair,
        "monitors": [m["view"] for m in g["monitors"][-4:]],
        "image_shas": image_shas,
        "ascii": ascii_preview,
        "recognition": recognition,
        "deja_vu": deja,
        "sightings": sightings,
        "patrol": patrol_reading,
        "flow_slots": base_flow,
        "intuitions": len(g["intuitions"]),
        "report": gaze_mod.gaze_report(state),
        "reading": (f"gli occhi: {'aperti' if eyes_open else 'ciechi (nessuna tape)'} "
                    f"su {pair}; {recognition.get('reading')}; {patrol_reading}"),
    }


def _diary(night_report: dict, state: dict, selfm: dict, cmap: dict,
           session: dict, agents: list[str]) -> dict:
    """Assemble the civilization's diary sections (stats, learned, guardians, ...).

    Honest: a reading the night did not produce is ``None`` (printed "non
    misurato"), never a flattering default.
    """
    lb = night_report.get("leaderboard") or []
    trades = sum(int(r.get("adv_trades") or 0) for r in lb) or None
    census_block = census.census_report(state["population"], state["legacy"])

    # The diary's own statistics: the SAME honest aggregation the bulletin uses
    # (bulletin.statistics_from), so the diary block can never disagree with the
    # page. Resilience is NEVER mislabelled as a win rate (the CEO's audit).
    try:
        from app.civilization import bulletin as _bulletin
        stats = _bulletin.statistics_from(night_report)
    except Exception:  # noqa: BLE001
        stats = {}
    stats["population"] = (night_report.get("population")
                           or census_block["population"])
    stats["kings"] = 2
    stats["volume"] = trades

    # what we learned: the E2 reading (when the report carries one) + the Council's
    # own minutes count (a cycle that decided something DID learn something).
    learned: list[str] = []
    am = night_report.get("amendment") or {}
    for k in sorted(am):
        if k.startswith("E2_") and isinstance(am[k], dict) and am[k].get("reading"):
            learned.append(str(am[k]["reading"]))
    minutes = session.get("minutes") or {}
    if minutes.get("by_kind"):
        learned.append(f"the Council recorded {minutes['decisions']} "
                       f"reasoned decision(s) this cycle")

    # the best interbrain exchanges: the distinct open ideas (deduped, newest first).
    exchanges: list[str] = []
    seen: set[str] = set()
    for node in reversed(state["interbrain"]):
        line = f"{node.get('author')}: {node.get('idea')}"
        if line not in seen:
            seen.add(line)
            exchanges.append(line)
        if len(exchanges) >= 3:
            break

    # requests to the CEO: the felt needs the garden answered + raids on ignorance.
    # CONSULT THE DIRECTIVE REGISTER FIRST: a realm the CEO has ALREADY authorized is
    # not re-asked -- the record precedes the question, so a granted order is never
    # mistaken for a fresh need (the CEO-request loop fix).
    requests, granted = _ceo_requests(state, cmap)

    return {
        "stats": stats,
        "learned": learned,
        "guardians": {
            "machine": ((night_report.get("measurements") or {})
                        .get("R76_heartbeat", {}) or {}).get("reason"),
            "account": None,
            "terms": None,
        },
        "decisions": session.get("decisions") or [],
        "curiosity": cmap,
        "exchanges": exchanges,
        "requests": requests,
        # the requests the directive register already covers: recorded, not re-asked.
        "granted": granted,
    }
