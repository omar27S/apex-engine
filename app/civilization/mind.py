"""THE INDIVIDUAL MINDS — every agent thinks completely (the One Brain, Part One).

This module gives a single agent the faculties a human trader actually uses, each
one HONEST and MEASURED — nothing is claimed that is not derived from real history:

  * FACULTY 1 — SYSTEM 2 (the deliberate mind): the inner monologue
    (``thought_record``), the personal theory (``theory`` / ``score_theory``), and
    the nightly revisitation (``revisitation`` + the belief ledger).
  * FACULTY 2 — SYSTEM 1 (the intuitive mind): the pattern memory
    (``remember_pattern`` / ``recognise``) with a tracked hit-rate.
  * FACULTY 3 — THE EMOTIONAL MIND (Damasio's somatic markers, honest version):
    the four calibrated affects (``affect``) and their calibration
    (``emotion_is_calibrated``), aggregating into the collective mood
    (``collective_mood``).
  * FACULTY 4 — MENTAL SIMULATION (Klein): one vivid imagined path with its
    fragile points (``simulate``) and its tracked accuracy (``simulation_accuracy``).
  * FACULTY 5 — THE ANTIBIAS SHIELD: the named computational biases
    (``BIASES``), regime-balanced evaluation (``regime_balanced_score``), and the
    monthly bias audit (``bias_audit``).

Pure at import (Scar #6): every function is a reduction over the caller's data. No
I/O, no clock, no RNG. Honest measurement (R47): an unmeasured quantity is ``None``
— never a flattering default.
"""

from __future__ import annotations

import hashlib

__all__ = [
    "AFFECTS",
    "BIASES",
    "thought_record",
    "theory",
    "score_theory",
    "revisitation",
    "belief_entry",
    "belief_day_counts",
    "belief_vitality",
    "remember_pattern",
    "recognise",
    "intuition_confidence",
    "affect",
    "emotion_is_calibrated",
    "collective_mood",
    "simulate",
    "simulation_accuracy",
    "regime_balanced_score",
    "bias_audit",
    "cognitive_dna",
    "thinking_weight",
    "generation_archive",
]


def _frac(*parts: str) -> float:
    """A deterministic value in [0, 1) from the parts (no RNG, no clock)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:4], "big") / 0x100000000


# --- FACULTY 1 — SYSTEM 2: the deliberate mind -----------------------------

def thought_record(*, agent: str, hypothesis: str, mechanism: str,
                   falsifier: str, prediction: str, ts: str = "") -> dict:
    """One auditable THOUGHT RECORD (the inner monologue, logged like a trade).

    The deliberate mind never acts without the four-part scratch: the HYPOTHESIS
    (what it believes), the MECHANISM (why it should be true), the FALSIFIER (what
    would prove it false), and the PREDICTION (what it expects to see). A thought
    with no falsifier is not a thought — it is a wish, and is refused.
    """
    if not str(falsifier).strip():
        raise ValueError("a thought with no falsifier is a wish, not a thought")
    return {"ts": ts, "agent": str(agent), "hypothesis": str(hypothesis),
            "mechanism": str(mechanism), "falsifier": str(falsifier),
            "prediction": str(prediction)}


def theory(*, agent: str, claim: str, rationale: str, ts: str = "") -> dict:
    """An agent's PERSONAL THEORY of why its edge exists (a living object).

    The theory is tested nightly (``score_theory``) and evolved by the agent; a
    dead theory triggers a pivot BEFORE capital is lost.
    """
    return {"agent": str(agent), "claim": str(claim), "rationale": str(rationale),
            "status": "untested", "ts": ts, "checks": 0}


def score_theory(t: dict, *, supported: int, weakening: int, falsified: int) -> dict:
    """Score a theory from the night's real evidence and set its status.

    supported > 0 with no falsification -> ``supported``; any falsification ->
    ``falsified`` (a theory that made a wrong prediction is dead, by data);
    otherwise, checks that neither confirmed nor killed it -> ``weakening`` when
    there is any evidence, else ``untested``. Honest: with zero checks it stays
    untested (no invented verdict).
    """
    checks = int(supported) + int(weakening) + int(falsified)
    t["checks"] = checks
    t["supported"] = int(supported)
    t["weakening"] = int(weakening)
    t["falsified"] = int(falsified)
    if falsified > 0:
        t["status"] = "falsified"
    elif supported > 0:
        t["status"] = "supported"
    elif checks > 0:
        t["status"] = "weakening"
    else:
        t["status"] = "untested"
    return t


def retire_theories(theories: list[dict], retired: list[dict],
                    *, keep: int = 12, retired_keep: int = 24) -> list[dict]:
    """THE FORGETTING (R137): a theory killed by data leaves working memory.

    ``score_theory`` kills by data, but nothing ever carried the dead out
    -- a falsified theory stayed in the working list forever (the live
    state carried exactly that: one theory, falsified, still standing in
    the council's eyes night after night). CoALA's frontier: forgetting
    is a FUNCTION, not an accident -- a memory that remembers everything
    remembers nothing useful. The falsified retire to ``retired``
    (bounded, kept with honor like the scars' retired rows); the working
    list stays small (the oldest beyond ``keep`` retire too -- whatever
    their status, the freshest claims deserve the council's eyes).
    Returns the freshly retired entries.
    """
    out = [t for t in theories if t.get("status") == "falsified"]
    staying = [t for t in theories if t.get("status") != "falsified"]
    while len(staying) > keep:
        out.append(staying.pop(0))          # the oldest retire first
    if out:
        retired.extend(out)
        if retired_keep > 0:
            del retired[:-retired_keep]     # even the grave forgets, bounded
        theories[:] = staying
    return out


def belief_entry(*, agent: str, before: str, after: str, reason: str,
                 ts: str = "") -> dict:
    """One BELIEF LEDGER row: what the agent believed, what it believes now, why.

    A belief change with no reason is not a change of mind — it is noise; refused.
    """
    if not str(reason).strip():
        raise ValueError("a belief change with no reason is noise, not a revision")
    return {"ts": ts, "agent": str(agent), "before": str(before),
            "after": str(after), "reason": str(reason)}


def belief_day_counts(rows: list[dict], *, day: str) -> dict:
    """R147 — THE HONEST MIRROR: births, reversals and retractions among
    TODAY's belief rows (and ONLY today's).

    The wound the Dragon named in the letter of 2026-10-23: the reading layer
    counted a BIRTH (``before='(none)'`` — the mind newly believes) as a
    REVERSAL, and when nothing happened today it fell back to the WHOLE history
    and reported stale rows as today's ("today: 0" beside "reversals_today: 8").
    A metric that only counts the overthrown never counts the born trains the
    civilization toward agnosticism and calls it rigour.

    A BIRTH carries ``before='(none)'``; a RETRACTION carries
    ``after='(retracted)'``; every other changed row is a REVERSAL. Yesterday's
    rows are context, never today's counts.
    """
    out = {"rows_today": 0, "births_today": 0,
           "reversals_today": 0, "retractions_today": 0}
    # The day accepts YYYY-MM-DD or YYYYMMDD (the report carries both forms
    # across its writers); the rows' timestamps always carry the dashed form.
    day = str(day or "").strip()
    if len(day) == 8 and day.isdigit():
        day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    for b in rows or []:
        if day and not str(b.get("ts") or "").startswith(day):
            continue
        out["rows_today"] += 1
        if str(b.get("before")) == "(none)":
            out["births_today"] += 1
        elif str(b.get("after")) == "(retracted)":
            out["retractions_today"] += 1
        else:
            out["reversals_today"] += 1
    return out


def belief_vitality(counts: dict) -> float | None:
    """The birth/reversal ratio — does the mind GENERATE, or only overturn?

    ``births / (reversals + retractions)``: a civilization that only reverses
    is agnostic by reward; one that births while revising is alive. ``None``
    when nothing was overturned (nothing to divide by — an all-birth day is
    not a ratio, and an empty day is not a verdict; both stay honest).
    """
    try:
        births = int((counts or {}).get("births_today") or 0)
        over = (int((counts or {}).get("reversals_today") or 0)
                + int((counts or {}).get("retractions_today") or 0))
    except (TypeError, ValueError):
        return None
    if over <= 0:
        return None
    return round(births / over, 4)


def revisitation(agent: str, *, yesterday: dict, today: dict) -> list[dict]:
    """The nightly revisitation: what did I believe yesterday that today contradicts?

    Compares two belief snapshots (``{belief_key: value}``). A key whose value
    changed is a revision; a key that VANISHED is a retraction (believed yesterday,
    absent today). Returns the belief-ledger rows — each with an honest reason.
    """
    out: list[dict] = []
    for key in sorted(set(yesterday) | set(today)):
        before, after = yesterday.get(key), today.get(key)
        if before == after:
            continue
        if after is None:
            out.append(belief_entry(agent=agent, before=str(before), after="(retracted)",
                                    reason=f"today's data no longer carries {key}"))
        elif before is None:
            out.append(belief_entry(agent=agent, before="(none)", after=str(after),
                                    reason=f"today's data newly carries {key}"))
        else:
            out.append(belief_entry(agent=agent, before=str(before), after=str(after),
                                    reason=f"{key} moved from {before} to {after}"))
    return out


def family_transitions(yesterday: list[str], today: list[str],
                       *, condemned: list[str] | None = None) -> dict:
    """R153 — THE THREE VERBS: the world's families are born, die and return.

    The belief ledger once knew a single verb for the world's families —
    "move" — so a set that replaced three quarters of its members read as one
    string that moved (the Dragon's fourth black hole: an unregistered
    resurrection is more dangerous than an unregistered death, because it
    inflates confidence — yesterday's "4 families" and today's look like ONE
    story while they are two different worlds). Now every family transition
    carries its verb and its cause, and the two honest numbers ride beside:

    * ``vitality = births / (births + deaths + resurrections)`` — None when
      the night measured no transition at all (an honest silence, never a
      fake 1.0);
    * ``continuity = |S_t & S_{t-1}| / |S_t | S_{t-1}|`` — the Jaccard of
      the two worlds (None only when both sides are empty; a world born
      tonight carries an honest 0.0, never a None that hides the birth).
    """
    y = [str(f) for f in (yesterday or [])]
    t = [str(f) for f in (today or [])]
    dead_pool = {str(f) for f in (condemned or [])}
    rows: list[dict] = []
    for fam in sorted(set(t) - set(y)):
        if fam in dead_pool:
            row = belief_entry(
                agent="council", before="(condemned)", after=fam,
                reason=(f"{fam} re-enters the running rows after E4 condemned "
                        "it — the dead walked back in while the gravedigger "
                        "wrote (the factory still carries the condemned)"))
            row["verb"] = "resurrezione"
        else:
            row = belief_entry(
                agent="council", before="(none)", after=fam,
                reason=(f"{fam} enters the running rows — a family the world "
                        "had not measured yesterday"))
            row["verb"] = "nascita"
        row["family"] = fam
        rows.append(row)
    for fam in sorted(set(y) - set(t)):
        row = belief_entry(
            agent="council", before=fam, after="(retracted)",
            reason=(f"{fam} left the running rows — no body of this family "
                    "was measured tonight"))
        row["verb"] = "morte"
        row["family"] = fam
        rows.append(row)
    births = sum(1 for r in rows if r.get("verb") == "nascita")
    deaths = sum(1 for r in rows if r.get("verb") == "morte")
    resurrections = sum(1 for r in rows if r.get("verb") == "resurrezione")
    denom = births + deaths + resurrections
    vitality = round(births / denom, 4) if denom else None
    union = set(y) | set(t)
    continuity = round(len(set(y) & set(t)) / len(union), 4) if union else None
    return {"rows": rows, "births": births, "deaths": deaths,
            "resurrections": resurrections, "vitality": vitality,
            "continuity": continuity}


# --- FACULTY 2 — SYSTEM 1: the intuitive mind ------------------------------

def remember_pattern(library: list[dict], *, agent: str, shape: str,
                     resolved_up: bool, ts: str = "") -> dict:
    """Add one recognised pattern (a situation seen before + its outcome).

    The library is keyed by (agent, shape); a repeat increments the count and, on
    an up-resolution, the up-count. This is the learned gut, built from experience.
    """
    key = (str(agent), str(shape))
    for rec in library:
        if (rec.get("agent"), rec.get("shape")) == key:
            rec["seen"] = int(rec.get("seen", 0)) + 1
            if resolved_up:
                rec["up"] = int(rec.get("up", 0)) + 1
            rec["last_ts"] = ts
            return rec
    rec = {"agent": str(agent), "shape": str(shape), "seen": 1,
           "up": 1 if resolved_up else 0, "last_ts": ts}
    library.append(rec)
    return rec


def recognise(library: list[dict], *, agent: str, shape: str) -> dict | None:
    """Scan the pattern memory INSTANTLY for this shape ("I have seen this before").

    Returns the pattern record with its confidence, or ``None`` when the shape was
    never seen (an honest silence — the weak intuition says nothing).
    """
    for rec in library:
        if rec.get("agent") == str(agent) and rec.get("shape") == str(shape):
            return dict(rec, confidence=intuition_confidence(rec))
    return None


def intuition_confidence(rec: dict) -> float | None:
    """The strength of a recognised pattern: how often it resolved the same way.

    ``|2*up/seen - 1|`` in [0, 1] — the conviction of the gut, scaled by how many
    times it was seen (a 1-of-1 guess is weak; a 34-of-47 run is strong). ``None``
    when the pattern was never seen (nothing to be confident about).
    """
    seen = int(rec.get("seen", 0))
    if seen <= 0:
        return None
    up = int(rec.get("up", 0))
    balance = abs(2.0 * (up / seen) - 1.0)
    weight = min(1.0, seen / 10.0)          # a gut needs reps to be trusted
    return round(balance * weight, 6)


# --- FACULTY 3 — THE EMOTIONAL MIND (honest somatic markers) ----------------

AFFECTS: tuple[str, ...] = ("fear", "excitement", "disgust", "calm")


def affect(*, losing_streak: int, drawdown: float, opportunity_rich: bool,
           regime_poison: bool) -> str:
    """The agent's calibrated affective state, derived from its REAL history.

    FEAR — bleeding (a losing streak with drawdown); EXCITEMENT — the setup is
    everywhere; DISGUST — the tape is poison to this style; CALM — nothing here.
    Precedence: fear (survival first), then disgust, then excitement, then calm.
    """
    if int(losing_streak) >= 3 and float(drawdown) > 0.0:
        return "fear"
    if regime_poison:
        return "disgust"
    if opportunity_rich:
        return "excitement"
    return "calm"


def emotion_is_calibrated(*, signal_fires: int, losses_after: int,
                          baseline: float) -> float | None:
    """Does this agent's emotion PREDICT its losses? (the calibration of a feeling).

    Lift = P(loss | emotion) / P(loss | baseline). > 1 means the feeling is
    informative (its fires precede its worst losses); ~1 means it is noise.
    ``None`` when the emotion never fired (unmeasured — no invented weight).
    """
    fires = int(signal_fires)
    if fires <= 0 or baseline <= 0.0:
        return None
    return round((int(losses_after) / fires) / float(baseline), 6)


def collective_mood(agents: list[dict]) -> dict:
    """The population's emotional weather (the COLLECTIVE MOOD, reported nightly).

    Counts each affect across the agents, names the dominant state, and — honest —
    leaves the reading "no mood measured" when the population is empty.
    """
    counts = {a: 0 for a in AFFECTS}
    for ag in agents:
        state = ag.get("affect")
        if state in counts:
            counts[state] += 1
    total = sum(counts.values())
    if total == 0:
        return {"counts": counts, "dominant": None, "population": 0,
                "reading": "nessun umore misurato (popolazione vuota)"}
    dominant = max(AFFECTS, key=lambda a: counts[a])
    return {"counts": counts, "dominant": dominant, "population": total,
            "reading": f"umore dominante: {dominant} ({counts[dominant]}/{total})"}


# --- FACULTY 4 — MENTAL SIMULATION (Klein's naturalistic decision) ----------

def simulate(*, agent: str, entry: str, path: str, danger: str, exit: str,
             fragile_points: list[str], ts: str = "") -> dict:
    """ONE vivid imagined path — lived mentally before the trade is committed.

    Not five analyses: one story, with the moments of maximum danger and the
    FRAGILE POINTS (where the story feels thin). Each fragile point becomes an
    explicit condition ("if this happens, my story is wrong"). A simulation with no
    fragile point is overconfidence, and is refused.
    """
    frag = [str(p) for p in fragile_points if str(p).strip()]
    if not frag:
        raise ValueError("a simulation with no fragile point is overconfidence")
    return {"ts": ts, "agent": str(agent), "entry": str(entry), "path": str(path),
            "danger": str(danger), "exit": str(exit), "fragile_points": frag,
            "conditions": [f"se accade: {p}" for p in frag]}


def simulation_accuracy(sim: dict, *, real_path: list[float]) -> float | None:
    """Did the real path resemble the imagined one? (accuracy in [0, 1]).

    Compares the SIMULATED direction (up/down, from entry to exit) with the realized
    direction of ``real_path`` (a list of prices). Returns 1.0 when the sign matched,
    0.0 when it did not, ``None`` when either side is unmeasured (honest).
    """
    if len(real_path) < 2:
        return None
    try:
        entry = float(sim.get("entry"))
        exit_ = float(sim.get("exit"))
    except (TypeError, ValueError):
        return None
    imagined = exit_ - entry
    realized = float(real_path[-1]) - float(real_path[0])
    if imagined == 0.0 or realized == 0.0:
        return None
    return 1.0 if (imagined > 0) == (realized > 0) else 0.0


# --- FACULTY 5 — THE ANTIBIAS SHIELD ---------------------------------------

BIASES: tuple[dict, ...] = (
    {"name": "overfitting", "human_cousin": "overconfidence",
     "defense": "the unseen gauntlet (law)", "measured_by": "adv_lb vs train_lb"},
    {"name": "curve_fitting", "human_cousin": "confirmation bias",
     "defense": "the mirror window (law)", "measured_by": "mirror delta"},
    {"name": "survivorship", "human_cousin": "selective memory",
     "defense": "the death ledger with autopsies (law)", "measured_by": "autopsy coverage"},
    {"name": "recency", "human_cousin": "chasing the last regime",
     "defense": "regime-balanced evaluation", "measured_by": "regimes scored per candidate"},
    {"name": "anchoring", "human_cousin": "fixation on old parameters",
     "defense": "the revisitation ritual", "measured_by": "belief-ledger revisions"},
)


def regime_balanced_score(*, per_regime: dict, floor: float = 0.0) -> dict:
    """Score a candidate across ALL regimes, not just the current one (anti-recency).

    Returns the mean across the regimes the report actually measured and the WORST
    regime (the honest weak spot). ``mean`` is ``None`` when no regime was measured —
    a candidate is never flattered by a missing regime.
    """
    vals = {str(r): float(v) for r, v in (per_regime or {}).items()
            if v is not None}
    if not vals:
        return {"mean": None, "worst_regime": None, "worst": None, "regimes": 0,
                "reading": "nessun regime misurato — candidato non valutabile"}
    worst_regime = min(vals, key=lambda r: vals[r])
    return {"mean": round(sum(vals.values()) / len(vals), 6),
            "worst_regime": worst_regime, "worst": round(vals[worst_regime], 6),
            "regimes": len(vals),
            "reading": f"media {round(sum(vals.values())/len(vals), 3)} su {len(vals)} regimi; "
                       f"peggiore: {worst_regime} ({round(vals[worst_regime], 3)})"}


def bias_audit(decisions: list[dict], *, sample: int = 20) -> dict:
    """The monthly BIAS AUDIT: which named bias could have produced these decisions?

    Heuristic, honest naming over the most recent ``sample`` decisions. A decision
    whose evidence leans on a single recent window is flagged ``recency``; one whose
    theory was never re-checked is flagged ``anchoring``; one resting on a single
    surviving case is flagged ``survivorship``. Returns the counts and the named
    patterns (empty when the sample carries none — the civilization knows its vices,
    but does not invent them).
    """
    counts: dict[str, int] = {}
    recent = decisions[-sample:] if sample > 0 else list(decisions)
    for d in recent:
        ev = str(d.get("evidence", "")).lower()
        why = str(d.get("why", "")).lower()
        if "last" in ev or "recent" in ev or "yesterday" in ev:
            counts["recency"] = counts.get("recency", 0) + 1
        if "never" in why or "always" in why or "as before" in why:
            counts["anchoring"] = counts.get("anchoring", 0) + 1
        if "only survivor" in ev or "the winner" in ev:
            counts["survivorship"] = counts.get("survivorship", 0) + 1
    return {"audited": len(recent), "counts": dict(sorted(counts.items())),
            "reading": (f"{len(recent)} decisioni auditate; "
                        f"vizi nominati: {dict(sorted(counts.items())) or 'nessuno'}")}


# --- THE RETRO-CHANNEL: culture -> genes (cognitive DNA) --------------------

def cognitive_dna(parent: dict) -> dict:
    """The COGNITIVE DNA a king-child inherits from its parent (dual inheritance).

    Culture (which reasoning patterns worked, which emotions predicted, which
    simulations saw true) flows back into the gene pool: the child inherits the
    parent's calibration tendency, intuition strength, emotional sensitivity,
    simulation vividness, EMOTION CALIBRATION and SIMULATION ACCURACY — each a
    MEASURED trait, defaulting to the honest midpoint when the parent never
    exhibited it. The last two are the C2 heritable traits: how well the parent's
    feelings predicted its losses, and how well its imagined paths matched reality.
    """
    p = parent or {}
    def _g(key: str, default: float) -> float:
        v = p.get(key)
        return round(float(v), 6) if isinstance(v, (int, float)) else default
    return {
        "calibration": _g("calibration", 0.5),
        "intuition_strength": _g("intuition_strength", 0.5),
        "emotional_sensitivity": _g("emotional_sensitivity", 0.5),
        "simulation_vividness": _g("simulation_vividness", 0.5),
        "emotion_calibration": _g("emotion_calibration", 0.5),
        "simulation_accuracy": _g("simulation_accuracy", 0.5),
        # THE GAZE (visual DNA): the child inherits the parent's EYE -- its visual
        # hit-rate and its scanning rhythm. A king-child sees like its father, with
        # mutation (the values are carried, not copied verbatim by the caller).
        "visual_hit_rate": _g("visual_hit_rate", 0.5),
        "scan_rhythm": _g("scan_rhythm", 0.5),
    }


def thinking_weight(*, calibration: float | None, simulation_accuracy: float | None,
                    intuition_hit_rate: float | None, theory_survival: float | None,
                    emotional_calibration: float | None) -> float | None:
    """The WEIGHING FIELD weight: how much this mind's thinking should count.

    The mean of the RELIABILITY axes that were actually MEASURED (calibration,
    simulation accuracy, intuition hit-rate, theory survival, emotional
    calibration). Minds that think well matter more — the meritocracy of cognition.
    ``None`` when no axis was measured: an unmeasured mind is not trusted (and is
    never flattered to a default weight).
    """
    axes = [a for a in (calibration, simulation_accuracy, intuition_hit_rate,
                        theory_survival, emotional_calibration) if a is not None]
    if not axes:
        return None
    return round(sum(float(a) for a in axes) / len(axes), 6)


# --- C2 — THE GENERATION ARCHIVE (each generation's patterns -> the School) --

def generation_archive(*, generation: int, minds: dict, weights: dict,
                       survivors: list[str] | None = None) -> dict:
    """Distill ONE generation's best reasoning patterns into the School's curriculum.

    The E1 loop's archive: which minds reasoned well (their measured weights) and
    which of them SURVIVED — distilled into ``lessons`` a newborn can inherit. A
    generation whose minds were never weighed teaches nothing (``lessons`` empty,
    honest), never an invented curriculum.
    """
    surv = set(survivors or [])
    ranked: list[tuple[str, float]] = []
    for agent, w in (weights or {}).items():
        if isinstance(w, (int, float)):
            ranked.append((str(agent), float(w)))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    lessons: list[str] = []
    for agent, w in ranked[:3]:
        mark = " (sopravvissuto)" if agent in surv else ""
        lessons.append(f"la mente {agent} pensava bene (peso {round(w, 3)}){mark}")
    return {
        "generation": int(generation),
        "minds": len(weights or {}),
        "ranked": [{"agent": a, "weight": round(w, 6)} for a, w in ranked],
        "survivors": sorted(surv),
        "lessons": lessons,
        "reading": (f"generazione {generation}: {len(lessons)} lezione/i distillate"
                    if lessons else
                    f"generazione {generation}: nessuna lezione (menti non pesate)"),
    }
