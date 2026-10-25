"""LAW OF LIFE 1 & 2 — THE PERPETUAL COUNCIL and THE BURST AS INSPIRATION.

The Council of Kings sits in CONTINUOUS session. It discusses, decides, delegates
— no fixed schedule, no cron decisions. The Council IS the brain. It decides
things like "this family is sick — cure it", "this realm is empty — populate it",
"this idea is promising — FORGE IT (a burst)", "we are strong in trend, weak in
range — focus research there". Every decision is recorded in the STATE LEDGER with
its REASONING.

Bursts are born from THOUGHT, not timers. When an idea is worth testing NOW, the
civilization fires a burst SIZED BY ITS OWN JUDGMENT of the idea's promise (a
small burst for a hunch, a massive burst for a conviction). The Machine Guardian
ADVISES the Council ("we can sustain X right now"); it does not dictate. NO fixed
burst schedules — the queue is fed by decisions.

Pure at import (Scar #6): the WORLD is a snapshot dict the caller assembles; the
Council is a pure reduction over it. No I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.civilization import ledger as L
from app.civilization import rotation as rotation_mod

__all__ = [
    "TRIALS_PER_ATTENTION",
    "MIN_BURST_TRIALS",
    "MAX_BURST_TRIALS",
    "CURE_FAILURES",
    "CURE_COURSE",
    "REFUSAL_COOLDOWN_HOURS",
    "REFUSAL_REOPEN_ATTENTION",
    "EMPTY_REALM_COVERAGE",
    "CEO_DIRECTIVES",
    "granted_realms",
    "request_is_granted",
    "burst_size",
    "deliberate",
    "council_session",
]

# Burst sizing (LAW 2): the civilization's own judgment of an idea's promise.
TRIALS_PER_ATTENTION: float = 5000.0   # trials per unit of collective attention
MIN_BURST_TRIALS: int = 200            # a hunch is still worth a real look
MAX_BURST_TRIALS: int = 20000          # a conviction, bounded by the Guardian

# A family with at least this many adversary-tested failures and no survivor is
# "sick" — the Council chooses to cure it (research focus), by evidence.
CURE_FAILURES: int = 3
# R147 — THE CURE'S COURSE (the Dragon's third denuncia): a cure that never
# changes when the patient changes, repeated forever, is not research — it is
# ostinazione con la contabilita' in ordine. A family gets at most CURE_COURSE
# cure attempts; after the course is exhausted with no survivor, the E4 verdict
# takes the seat (retire the weak by data, a king-child in light mutation fills it).
CURE_COURSE: int = 2
# R153 — THE FRICTION-PROPORTIONAL COURSE (the Sage's provoke: rsi_divergence
# retired with 179 failures and 2 cures, ml_gradient_boosting with 47 failures
# and 12 — the cure budget was never proportional to the friction it was
# asked to heal; haste with E4's handwriting, the debt cancelled not paid).
# Every FRICTION_PER_CURE adversary-tested failures buy one more cure, so
# the family with the RICHEST evidence of sickness earns the LONGEST course.
FRICTION_PER_CURE: int = 40
CURE_COURSE_MAX: int = 6
# R147 — THE HONORED VETO (the Sage's warning): a refusal by the One Brain is
# E9 WORKING — a measurement of the field, not an obstacle to force. An idea the
# field refused is NOT re-forged into the same burst for this long; only NEW
# evidence (the attention grew by at least this much since the refusal) or a
# veto proven wrong (was_right is False) reopens the question.
REFUSAL_COOLDOWN_HOURS: float = 48.0
REFUSAL_REOPEN_ATTENTION: float = 1.0
# A realm whose measured coverage is below this is "empty" — populate it.
EMPTY_REALM_COVERAGE: float = 0.15


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


def burst_size(attention: float, *, capacity_trials: int | None = None) -> int:
    """The size of the burst the civilization CHOOSES for an idea of this promise.

    Proportional to collective attention (the market's price), floored at a real
    look and capped at the Guardian's advised capacity — the Council decides, the
    Guardian protects the machine from self-harm.
    """
    a = float(attention)
    if a != a or a < 0.0:
        raise ValueError(f"attention must be a finite non-negative number, got {attention!r}")
    trials = int(round(a * TRIALS_PER_ATTENTION))
    trials = max(MIN_BURST_TRIALS, min(MAX_BURST_TRIALS, trials))
    if capacity_trials is not None:
        cap = int(capacity_trials)
        if cap < 0:
            raise ValueError("capacity_trials must be non-negative")
        trials = min(trials, max(0, cap))
    return trials


def course_for_failures(fails: int) -> int:
    """R153 — the friction-proportional course: bounded, monotone, honest.

    Two cures for the barely-sick (the historical floor), one more for every
    forty adversary-tested failures, six at most — a course that scales with
    the evidence and never forgets to end.
    """
    fails = max(0, int(fails or 0))
    return max(CURE_COURSE, min(CURE_COURSE_MAX,
                                CURE_COURSE + fails // FRICTION_PER_CURE))


def _regime_context(world: dict) -> str:
    """R160 — THE REGIME'S VOICE: the census as the verdict's context (or '').

    A verdict sealed without its court is a number pretending to be a judgment:
    181 failures counted in a world where 15 of 18 pairs were dead is a different
    case than the same 181 in a living one. The context rides the EVIDENCE (the
    sealed part of the decision), so the Dragon can weigh the court, not just the
    count. No census measured: an honest empty string (the verdict stands as it
    always stood).
    """
    c = world.get("regime_census") or {}
    if not isinstance(c, dict):
        return ""
    measured = int(c.get("pairs_measured") or 0)
    dead = int((c.get("counts") or {}).get("dead") or 0)
    if not measured:
        return ""
    share = c.get("dead_share")
    pct = f" ({share:.0%})" if isinstance(share, (int, float)) else ""
    return f", world_context: {dead}/{measured} pair dead{pct}"


def _cure_decisions(world: dict) -> list[dict]:
    """Cure the sick — with a COURSE, then retire them (E4). R147.

    The wound (the Dragon's dissent, the Sage's synthesize): the cure decision
    repeated identically every cycle, changing nothing, curing nothing — a
    rename of the patient, not a treatment. Now: each cure carries its course
    number and names the deadline (the WHY changes with the patient), and when
    the course is exhausted with no survivor the family is RETIRED by data —
    the E4 verdict, a big call the Dragon will weigh.
    """
    out: list[dict] = []
    cures = world.get("family_cures") or {}
    # R160 — THE REGIME'S VOICE: every E4 verdict is sealed WITH its context —
    # the court that judged it (the world's live regime census).
    ctx = _regime_context(world)
    for family, h in sorted((world.get("family_health") or {}).items()):
        fails = int(h.get("failures", 0))
        survivors = int(h.get("survivors", 0))
        if not (fails >= CURE_FAILURES and survivors == 0):
            continue
        n = int(cures.get(family) or 0)
        # R153 — the course scales with the measured friction: the
        # patient with the most defeats earns the most treatment, never
        # the least (the Sage's provoke, healed).
        course = course_for_failures(fails)
        if n < course:
            out.append(L.decision_entry(
                kind="cure_family",
                what=f"cure the family {family}",
                why=(f"{fails} adversary-tested failures and no certified survivor — "
                     f"cure {n + 1} of {course} for this family (the course scales "
                     f"with the friction: {fails} failures earn {course} cures): "
                     "the treatment "
                     f"changes with the patient, and a course that ends without a "
                     f"survivor retires the family (E4), it never restarts"),
                evidence=(f"failures={fails}, survivors={survivors}, "
                          f"course={n + 1}/{course}{ctx}"),
                expected_effect="a targeted treatment burst measures whether this "
                                "family can still produce a survivor",
                extra={"family": family, "course": n + 1, "trials": MIN_BURST_TRIALS}))
        else:
            out.append(L.decision_entry(
                kind="retire_family",
                what=f"retire the family {family}",
                why=(f"{fails} adversary-tested failures, 0 survivors and a full "
                     f"course of {n} cure(s) — friction-proportional, {fails} "
                     f"failures earned {course} — that changed nothing — E4: retire the "
                     f"weak by data and give the seat to a king-child in light "
                     f"mutation; reanimating a certified death is not research, it "
                     f"is the {fails + 1}st defeat disguised as hope"),
                evidence=(f"failures={fails}, survivors={survivors}, "
                          f"cures_tried={n}{ctx}"),
                expected_effect="the freed seat goes to a child of the King (light "
                                "mutation) — the dead become evidence, not a patient",
                extra={"family": family, "cures_tried": n, "e4": True}))
    return out


def _populate_decisions(world: dict) -> list[dict]:
    out: list[dict] = []
    for realm, cov in sorted((world.get("realm_coverage") or {}).items()):
        c = float(cov)
        if c < EMPTY_REALM_COVERAGE:
            out.append(L.decision_entry(
                kind="populate_realm",
                what=f"populate the realm {realm}",
                why=(f"coverage {c:.2f} is below the empty threshold "
                     f"{EMPTY_REALM_COVERAGE:.2f} — an unexplored realm needs eyes"),
                evidence=f"coverage={c:.2f}",
                expected_effect="explorers thin the unknown in this realm"))
    return out


def _burst_decisions(world: dict, *, ts: str = "") -> list[dict]:
    """Forge the funded ideas — honoring the One Brain's refusals. R147.

    The theater the Sage named ("un burst forgiato senza seed e' un timer
    travestito da convinzione"): the same refused idea re-forged every cycle
    while the One Brain keeps refusing it burns attention on a loop. An idea the
    field refused within REFUSAL_COOLDOWN_HOURS is NOT re-forged: the refusal is
    honored and recorded (E9 read as measurement). Only new evidence reopens
    the question — the attention grew by at least REFUSAL_REOPEN_ATTENTION since
    the refusal, or the veto was proven wrong (was_right is False).
    """
    out: list[dict] = []
    cap = world.get("capacity_trials")
    dispatch_ts = str(world.get("ts") or "")
    now = _epoch(ts)
    for idea in world.get("funded_ideas") or []:
        attention = float(idea.get("attention", 0.0))
        text = str(idea.get("idea") or "")
        refusal = _recent_refusal(world.get("refused_ideas") or [], idea=text,
                                  now=now, attention=attention)
        if refusal is not None:
            out.append(L.decision_entry(
                kind="honor_refusal",
                what=f"honor the refusal of: {text}",
                why=(f"the integrated field refused this idea (field score "
                     f"{refusal.get('field_score')}) within the cooldown of "
                     f"{REFUSAL_COOLDOWN_HOURS:.0f}h and the attention has not grown "
                     f"since — E9: the refusal is a measurement of the field, not an "
                     f"obstacle to force; the Council does not re-forge what the "
                     f"field already refused"),
                evidence=(f"refused_ts={refusal.get('ts')}, "
                          f"field_score={refusal.get('field_score')}, "
                          f"attention_then={refusal.get('attention')}, "
                          f"attention_now={round(attention, 4)}"),
                expected_effect="the saved burst is spent where the field can still "
                                "say yes; the refusal's memory keeps learning",
                extra={"idea": text, "refused_ts": refusal.get("ts")}))
            continue
        size = burst_size(attention, capacity_trials=cap)
        # FIX 1 — the burst's seed ROTATES with the dispatch timestamp and the idea,
        # so two bursts in the same hour (or across nights) are distinct draws.
        seed = (rotation_mod.burst_seed(idea=text, dispatch_ts=dispatch_ts)
                if dispatch_ts else None)
        out.append(L.decision_entry(
            kind="forge_burst",
            what=f"forge a burst of {size} trials for: {idea.get('idea')}",
            why=(f"the market funded this idea with attention {attention:.2f} "
                 f"(>= the funding threshold) — a promising idea is tested NOW"),
            evidence=(f"attention={attention:.2f}, "
                      f"backers={len(idea.get('backers', []))}"
                      + (f", seed={seed} (dal dispatch {dispatch_ts})" if seed is not None
                         else ", seed non misurato (nessun dispatch)")),
            expected_effect="an inspiration-born burst measures the idea's promise",
            extra={"burst_trials": size, "idea": idea.get("idea"),
                   "attention": round(attention, 6), "burst_seed": seed}))
    return out


def _recent_refusal(refused: list[dict], *, idea: str, now: float,
                    attention: float) -> dict | None:
    """The refusal that still binds this idea, if any (the most recent one).

    A refusal binds when its veto was not proven wrong AND it is within the
    cooldown AND the attention has not grown by the reopen margin since. An
    unparseable or absent ts is treated as BINDING (fail-closed against the
    theater: the benefit of the doubt goes to the veto, never to the loop).
    """
    text = str(idea or "")
    best: dict | None = None
    for r in refused or []:
        if str(r.get("idea") or "") != text:
            continue
        if best is None or str(r.get("ts") or "") >= str(best.get("ts") or ""):
            best = r
    if best is None:
        return None
    if best.get("was_right") is False:
        return None          # the veto was proven wrong — the door reopens
    ts_epoch = _epoch(str(best.get("ts") or ""))
    if ts_epoch > 0.0 and now > 0.0:
        age_h = (now - ts_epoch) / 3600.0
        if age_h > REFUSAL_COOLDOWN_HOURS:
            return None      # the cooldown expired — the question may be asked again
    att_then = best.get("attention")
    if (isinstance(att_then, (int, float))
            and (float(attention) - float(att_then)) >= REFUSAL_REOPEN_ATTENTION):
        return None          # new evidence: the attention grew since the refusal
    return best


def _focus_decisions(world: dict) -> list[dict]:
    sw = world.get("strengths_weaknesses") or {}
    weak = sw.get("weaknesses") or []
    strong = sw.get("strengths") or []
    out: list[dict] = []
    for regime in weak:
        out.append(L.decision_entry(
            kind="focus_research",
            what=f"focus research on the weak regime {regime}",
            why=(f"the self-model reads {regime} as weak "
                 f"(strong: {strong or 'nothing yet'}) — the gap is the work"),
            evidence=f"weakness={regime}",
            expected_effect="research narrows the weakest regime"))
    return out


def _meta_decisions(world: dict) -> list[dict]:
    audit = world.get("meta_learning") or {}
    stalled = audit.get("stalled") or []
    out: list[dict] = []
    if stalled:
        out.append(L.decision_entry(
            kind="meta_learning",
            what=f"evolve the stalled learning mechanism(s): {', '.join(stalled)}",
            why="these mechanisms stopped producing behaviour change — the way we "
                "learn is itself an evolution target (LAW 6)",
            evidence=f"stalled={stalled}",
            expected_effect="the civilization gets better at getting better"))
    return out


# The CEO directives the civilization records in the minutes WITH their reasoning.
# A directive is a decision taken OUTSIDE the Council (by the CEO); the kind
# ``authorize`` carries it. Kept here (not invented from a data file) because a
# standing CEO order is part of the sealed record, like the doctrines.
CEO_DIRECTIVES: tuple[dict, ...] = (
    {
        "kind": "authorize",
        "what": "authorize a bounded exploration of the realm pareto_space",
        "why": ("the CEO, replying to the first NIGHT BULLETIN, AUTHORIZED the "
                "Council's request to explore pareto_space: the realm's coverage "
                "(0.12) sits below the empty threshold (0.15) and the frontier's "
                "corners are nearly empty (2 of 16 occupied), so the unknown is "
                "where the next edge must come from — the CEO grants the eyes"),
        "evidence": ("CEO directive (night bulletin reply): pareto_space authorized; "
                     "coverage 0.12 < 0.15; pareto_front_corners 2/16"),
        "expected_effect": ("scouts measure the empty realm; coverage rises and the "
                            "Pareto front's corners fill with evidence, not guesses"),
        "extra": {"source": "ceo", "realm": "pareto_space", "bounded": True},
    },
)


def granted_realms() -> set[str]:
    """The realms the CEO has ALREADY authorized (the standing directive register).

    A directive is granted when it carries ``extra.realm``; this is the ONE place
    the civilization consults before it asks the CEO again.
    """
    out: set[str] = set()
    for d in CEO_DIRECTIVES:
        realm = (d.get("extra") or {}).get("realm")
        if realm:
            out.add(str(realm))
    return out


def request_is_granted(text: str) -> bool:
    """True when a CEO request is already covered by a standing directive.

    A request to ``authorize``/``explore``/``populate``/``scout``/``raid`` a realm
    the CEO already granted is NOT re-asked: the record precedes the question (the
    loop fix), so a granted order is never mistaken for a fresh need.
    """
    t = str(text or "").lower()
    realm = next((r for r in granted_realms() if r.lower() in t), None)
    if realm is None:
        return False
    return any(verb in t for verb in ("authorize", "explore", "exploration",
                                      "populate", "scout", "raid"))


def deliberate(world: dict) -> list[dict]:
    """ONE deliberation: reduce the WORLD snapshot to reasoned decisions.

    The order is the Council's standing agenda: cure the sick, populate the empty,
    focus the weak, evolve the stalled way of learning, then forge the funded
    ideas into bursts. A world with nothing to say yields no decisions (honest).
    """
    decisions: list[dict] = []
    # The CEO's standing authorizations ride first (an OUTSIDE order the Council
    # records with its reasoning, never silently).
    for d in CEO_DIRECTIVES:
        decisions.append(L.decision_entry(
            kind=d["kind"], what=d["what"], why=d["why"], evidence=d["evidence"],
            expected_effect=d["expected_effect"], extra=d.get("extra")))
    decisions += _cure_decisions(world)
    decisions += _populate_decisions(world)
    decisions += _focus_decisions(world)
    decisions += _meta_decisions(world)
    decisions += _burst_decisions(world, ts=str(world.get("ts") or ""))
    return decisions


def council_session(world: dict, *, ts: str = "") -> dict:
    """A full Council session: deliberate, record the minutes, announce the bursts.

    Returns the decisions (each with its WHY), the ledger rows, and the bursts the
    civilization chose to fire — the raw material of the night's bulletin.
    """
    decisions = deliberate(world)
    base = {"ts", "kind", "what", "why", "evidence", "expected_effect"}
    ledger = [L.record([], kind=d["kind"], what=d["what"], why=d["why"],
                       evidence=d["evidence"], expected_effect=d["expected_effect"],
                       ts=ts, extra={k: v for k, v in d.items() if k not in base})
              for d in decisions]
    bursts = [{"trials": d["burst_trials"], "idea": d["idea"]}
              for d in decisions if d["kind"] == "forge_burst"]
    return {
        "session_ts": ts,
        "decisions": decisions,
        "ledger": ledger,
        "bursts": bursts,
        "minutes": L.minutes_digest(ledger, last=len(ledger)),
    }
