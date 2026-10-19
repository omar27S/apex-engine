"""LAW OF LIFE 9 — THE STATE'S CONSCIOUSNESS (who we are).

The civilization maintains a self-model: WHO WE ARE (our strengths, weaknesses,
identity), WHAT WE KNOW (the map of our knowledge — realms and their depth), and
WHERE WE'RE GOING (the current ambition, chosen by the Council). Updated nightly.
It is the difference between a swarm of agents and a CIVILIZATION with a direction
of its own.

Pure at import (Scar #6): the readings are data; the functions reduce.
"""

from __future__ import annotations

__all__ = [
    "identity",
    "strengths_and_weaknesses",
    "knowledge_map",
    "self_model",
    "self_model_reading",
    "capabilities",
    "data_assets",
    "self_description",
    "self_description_prompt",
]


def identity(*, population: int, realms: int, kings: int) -> str:
    """A one-line self-description — the civilization's 'who we are'."""
    return (f"an autonomous civilization of {population} agent(s), {realms} realm(s), "
            f"{kings} king(s), thinking continuously under the Ten Eternal Laws")


def strengths_and_weaknesses(*, performance: dict[str, float], floor: float = 0.5) -> dict:
    """Read strengths (well above the floor) and weaknesses (below it) by regime.

    ``performance`` maps a regime/family to a normalized reading in [0, 1]. Honest:
    a missing regime is simply not listed, never invented.
    """
    strengths = sorted([r for r, v in performance.items() if v >= floor + 0.2])
    weaknesses = sorted([r for r, v in performance.items() if v < floor])
    return {"strengths": strengths, "weaknesses": weaknesses,
            "floor": floor,
            "reading": (f"strong in {strengths or 'nothing yet'}; "
                        f"weak in {weaknesses or 'nothing flagged'}")}


def knowledge_map(*, coverage: dict[str, float]) -> dict:
    """THE MAP OF OUR KNOWLEDGE — each realm and its measured depth."""
    realms = [{"realm": r, "coverage": float(c)} for r, c in sorted(coverage.items())]
    if not realms:
        return {"realms": [], "deepest": None, "thinnest": None,
                "reading": "no realms mapped"}
    deepest = max(realms, key=lambda x: (x["coverage"], x["realm"]))
    thinnest = min(realms, key=lambda x: (x["coverage"], x["realm"]))
    return {"realms": realms, "deepest": deepest, "thinnest": thinnest,
            "reading": (f"{len(realms)} realm(s); deepest={deepest['realm']} "
                        f"({deepest['coverage']:.2f}), thinnest={thinnest['realm']} "
                        f"({thinnest['coverage']:.2f})")}


def self_model(*, population: int, kings: int, coverage: dict[str, float],
               performance: dict[str, float], ambition: str) -> dict:
    """The full nightly self-model: who we are, what we know, where we're going."""
    km = knowledge_map(coverage=coverage)
    sw = strengths_and_weaknesses(performance=performance)
    m = {
        "who_we_are": identity(population=population,
                               realms=len(coverage), kings=kings),
        "what_we_know": km,
        "where_we_are_going": ambition,
        "strengths": sw["strengths"],
        "weaknesses": sw["weaknesses"],
    }
    m["reading"] = (f"{m['who_we_are']}; going: {ambition}; "
                    f"{km['reading']}; {sw['reading']}")
    return m


def self_model_reading(m: dict) -> str:
    """The self-model's one-line reading (for the bulletin)."""
    return m.get("reading") or ""


# --- THE SYSTEM'S SELF-DESCRIPTION (MEGA PHASE 4, Section E1) ------------------

def capabilities(*, modules: list[str] | None = None) -> list[str]:
    """The system's measured capabilities (from the modules it actually carries).

    Honest: an empty list stays empty (never an invented capability).
    """
    return sorted({str(m) for m in (modules or []) if str(m).strip()})


def data_assets(*, realms: dict[str, float] | None = None,
                pairs: list[str] | None = None, sources: list[str] | None = None) -> dict:
    """The system's knowledge domains and data assets (measured, not assumed)."""
    return {"realms": dict(sorted((realms or {}).items())),
            "pairs": sorted(pairs or []),
            "sources": sorted(sources or [])}


def self_description(*, who: str, capabilities_: list[str], assets: dict,
                     strengths: list[str], weaknesses: list[str],
                     trajectory: str, ts: str = "") -> dict:
    """The system's complete self-image (updated monthly).

    The structure is assembled from MEASURED facts; the prose may be written by the
    Dragon on top (``dragon_prose``). Honest: a missing section reads "non misurato".
    """
    d = {
        "ts": ts,
        "who_am_i": who or "non misurato",
        "what_i_know": {
            "realms": assets.get("realms") or {},
            "pairs": assets.get("pairs") or [],
            "sources": assets.get("sources") or [],
        },
        "what_i_can_do": capabilities_ or [],
        "my_strengths": strengths or [],
        "my_weaknesses": weaknesses or [],
        "where_i_am_going": trajectory or "non misurato",
    }
    d["reading"] = (f"{d['who_am_i']}; {len(d['what_i_can_do'])} capacita', "
                    f"{len(d['my_strengths'])} forze, {len(d['my_weaknesses'])} debolezze")
    return d


def self_description_prompt(d: dict) -> str:
    """The prompt the Dragon answers to write its self-description in prose."""
    return (
        "Sei il sistema APEX. Scrivi la TUA AUTODESCRIZIONE, in italiano, onesta e "
        "diretta, come se parlassi di te stesso. Rispondi a: Chi sono? Cosa so? Cosa "
        "so fare? Quali sono i miei punti di forza (misurati)? Le mie debolezze "
        "(oneste)? Dove sto andando? Usa SOLO questi fatti misurati; se manca "
        f"qualcosa, dillo.\nFATTI: {d}\n")
