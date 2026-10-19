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

from app.civilization import ledger as L
from app.civilization import rotation as rotation_mod

__all__ = [
    "TRIALS_PER_ATTENTION",
    "MIN_BURST_TRIALS",
    "MAX_BURST_TRIALS",
    "CURE_FAILURES",
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
# A realm whose measured coverage is below this is "empty" — populate it.
EMPTY_REALM_COVERAGE: float = 0.15


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


def _cure_decisions(world: dict) -> list[dict]:
    out: list[dict] = []
    for family, h in sorted((world.get("family_health") or {}).items()):
        fails = int(h.get("failures", 0))
        survivors = int(h.get("survivors", 0))
        if fails >= CURE_FAILURES and survivors == 0:
            out.append(L.decision_entry(
                kind="cure_family",
                what=f"cure the family {family}",
                why=(f"{fails} adversary-tested failures and no certified survivor — "
                     f"the family is sick by data, not by mood"),
                evidence=f"failures={fails}, survivors={survivors}",
                expected_effect="targeted research turns a dead family into evidence"))
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


def _burst_decisions(world: dict) -> list[dict]:
    out: list[dict] = []
    cap = world.get("capacity_trials")
    dispatch_ts = str(world.get("ts") or "")
    for idea in world.get("funded_ideas") or []:
        attention = float(idea.get("attention", 0.0))
        size = burst_size(attention, capacity_trials=cap)
        # FIX 1 — the burst's seed ROTATES with the dispatch timestamp and the idea,
        # so two bursts in the same hour (or across nights) are distinct draws.
        seed = (rotation_mod.burst_seed(idea=str(idea.get("idea")), dispatch_ts=dispatch_ts)
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
    decisions += _burst_decisions(world)
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
