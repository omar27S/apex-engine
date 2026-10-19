"""LAW OF LIFE 4 — BIRTH AND DEATH (the living population).

THE GARDEN (birth): the civilization generates new agents when it FEELS the need —
more explorers for an unexplored realm, more philosophers when theory lags
practice, more snipers when a realm shows promise. THE CEMETERY (death with
inheritance): the weak die (E4 — apoptosis with autopsy) and each leaves its
LEGACY to the network: its findings, its methods, its failures' lessons. Nothing
is lost. KING-CHILDREN take the seats of the dead (DNA + light mutation — royal
blood spreads). THE SCHOOL: newborn agents inherit the accumulated CULTURE, then
develop their own personality through early explorations guided by elders.

Pure at import (Scar #6): the population is data; the functions reduce. Births and
deaths are recorded as memorable rows with their REASON (the Council's WHY).
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "MAX_POPULATION",
    "GARDEN_NEEDS",
    "Populace",
    "birth_need",
    "retire",
    "spawn",
    "school_newborn",
    "query_archive",
    "office_hours",
    "census_report",
]

# A hard ceiling so the garden never becomes blind swarming (the machine's real
# resources bound the population; the Guardian advises, the Council decides).
MAX_POPULATION: int = 64

# The needs the garden answers. Each need names the role to spawn and WHY.
GARDEN_NEEDS: tuple[dict, ...] = (
    {"need": "unexplored_realm", "spawn": "explorers",
     "why": "an unexplored realm needs more eyes"},
    {"need": "theory_lags", "spawn": "philosophers",
     "why": "theory lags practice — state the doctrine"},
    {"need": "promising_realm", "spawn": "snipers",
     "why": "a realm shows promise — concentrate force"},
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tokens(text: str) -> set[str]:
    """Significant tokens of a text (lowercased alphanumeric words, len > 2)."""
    return {t for t in
            "".join(c.lower() if c.isalnum() else " " for c in str(text)).split()
            if len(t) > 2}


class Populace(dict):
    """The living population: agent rows plus the accumulated culture (LAW 4)."""

    __slots__ = ()


def birth_need(*, realm_coverage: dict[str, float], theory_lagging: bool = False,
               promising: list[str] | None = None) -> list[dict]:
    """What the civilization FEELS it needs — a list of garden needs to answer.

    Purely evidence-shaped: an unexplored realm (coverage near 0), theory lagging
    (a caller reading), or a promised realm (a caller reading). No need is invented.
    """
    needs: list[dict] = []
    unexplored = [r for r, c in realm_coverage.items() if float(c) < 0.15]
    if unexplored:
        needs.append({**GARDEN_NEEDS[0], "realm": sorted(unexplored)[0]})
    if theory_lagging:
        needs.append(dict(GARDEN_NEEDS[1]))
    if promising:
        needs.append({**GARDEN_NEEDS[2], "realm": sorted(promising)[0]})
    return needs


def retire(population: list[dict], *, signature: str, cause: str,
           lesson: str = "") -> dict:
    """The weak die: remove an agent and record its LEGACY (E4 autopsy).

    Nothing is lost — the legacy (findings/methods/failure's lesson) stays in the
    population's ``legacy`` list for the network to inherit.
    """
    victim = next((a for a in population if a.get("signature") == signature), None)
    if victim is None:
        raise KeyError(f"no agent with signature {signature!r} to retire")
    population.remove(victim)
    legacy = {
        "ts": victim.get("born") or _now(),
        "from": signature,
        "age_generations": victim.get("generations", 0),
        "cause": cause,
        "lesson": lesson or "(no lesson recorded)",
    }
    return legacy


def spawn(population: list[dict], *, signature: str, role: str, dna: dict | None = None,
          parents: list[str] | None = None, ts: str = "") -> dict:
    """The garden births an agent (bounded by MAX_POPULATION)."""
    if len(population) >= MAX_POPULATION:
        raise ValueError(f"population at ceiling {MAX_POPULATION}; the Council must retire first")
    agent = {
        "signature": signature,
        "role": role,
        "born": ts or _now(),
        "generations": 0,
        "dna": dict(dna or {}),
        "parents": list(parents or []),
        "culture": [],
        "contributions": 0,   # ideas authored / discoveries made (weakness is by record)
        "lived_cycles": 0,    # full deliberation cycles survived
    }
    population.append(agent)
    return agent


def school_newborn(agent: dict, *, culture: list[str]) -> dict:
    """THE SCHOOL: a newborn inherits the accumulated CULTURE (collective lessons)."""
    agent["culture"] = list(culture)
    return agent


def query_archive(legacy: list[dict], question: str, *, k: int = 3) -> dict:
    """D3 — THE CROSS-GENERATIONAL DIALOGUE: the newborn QUERIES the ancestors.

    Before attempting something, a newborn can ask the accumulated archive "has
    anyone tried this? what happened? what did they believe?" and receive the
    distilled answers WITH the ancestral context (the lesson and the cause of each
    retired mind). The dead teach the living through structured memory, not just DNA.

    Matching is by shared significant tokens (length > 3) between the question and
    each legacy's lesson/from/cause; the top ``k`` by overlap are returned, newest
    first on ties. Honest: no overlap -> no answer (``None``), never an invented one.
    """
    q = {t for t in _tokens(question) if len(t) > 3}
    scored: list[tuple[int, int, dict]] = []
    for i, leg in enumerate(legacy or []):
        text = " ".join(str(leg.get(f, "")) for f in ("lesson", "from", "cause"))
        overlap = q & {t for t in _tokens(text) if len(t) > 3}
        if overlap:
            scored.append((len(overlap), i, leg))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    answers = [{"from": s[2].get("from"), "lesson": s[2].get("lesson"),
                "cause": s[2].get("cause"), "overlap": sorted(
                    q & {t for t in _tokens(" ".join(
                        str(s[2].get(f, "")) for f in ("lesson", "from", "cause")))
                        if len(t) > 3})}
               for s in scored[:k]]
    return {
        "question": str(question),
        "answers": answers,
        "n": len(answers),
        "reading": (f"{len(answers)} risposta/e dagli antenati"
                    if answers else "nessun antenato ha tentato questo"),
    }


def office_hours(legacy: list[dict], question: str, *, k: int = 1) -> list[dict]:
    """D3 — THE SCHOOL'S OFFICE HOURS: the strongest retired minds are queryable.

    A retired mind with a RECORDED lesson is a mentor; office hours return the best
    matches as ``{mentor, answer}`` pairs. A mentor with no lesson is not offered
    (nothing to teach) — honest.
    """
    mentors = [leg for leg in (legacy or []) if str(leg.get("lesson", "")).strip()
               and leg.get("lesson") != "(no lesson recorded)"]
    q = query_archive(mentors, question, k=k)
    return [{"mentor": a["from"], "answer": a["lesson"], "cause": a["cause"]}
            for a in q["answers"]]


def weakest(population: list[dict], *, min_cycles: int = 2) -> list[str]:
    """The agents the DATA calls weak: no contributions after enough lived cycles.

    Weakness is by RECORD, never by mood: an agent that has survived ``min_cycles``
    full cycles and contributed nothing (no ideas, no discoveries) is weak. Kings
    (agents others descend from) are never returned — the line endures.
    """
    parents = {p for a in population for p in a.get("parents", [])}
    out: list[str] = []
    for a in population:
        if a.get("signature") in parents:
            continue
        if int(a.get("lived_cycles", 0)) >= min_cycles and int(a.get("contributions", 0)) == 0:
            out.append(a["signature"])
    return sorted(out)


def census_report(population: list[dict], legacy: list[dict]) -> dict:
    """The living census: size, roles, births' parents, the cemetery's inheritance."""
    by_role: dict[str, int] = {}
    for a in population:
        by_role[a.get("role", "?")] = by_role.get(a.get("role", "?"), 0) + 1
    king_children = sum(1 for a in population if a.get("parents"))
    return {
        "population": len(population),
        "by_role": dict(sorted(by_role.items())),
        "king_children": king_children,
        "cemetery": len(legacy),
        "reading": (f"{len(population)} agent(s) {by_role}; "
                    f"{king_children} king-child(ren); "
                    f"{len(legacy)} in the cemetery (legacy kept)"),
    }
