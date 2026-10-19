"""THE FIRST AMENDMENT -- the nine doctrines, as one executable document.

The verbatim CEO amendment lives in ``APEX/AGENTS.md`` ("The First Amendment");
this package is its executable counterpart. Nine doctrines, all binding:

    E1 meta-learning   -- the state improves its own way of learning
    E2 failure law     -- every failure must produce a behaviour change
    E3 self-building   -- the state builds tools for its own intelligence (caged)
    E4 cycle of the weak -- apoptosis by data; children of the King
    E5 human logic     -- gradients, not dead binary
    E6 episodic memory -- every trade a narrative, recalled by similarity
    E7 world radar     -- news of all currencies, orderflow of all pairs
    E8 collaborative world -- all is shared; the work converges
    E9 the orchestra   -- a consensus of experts, never one master

:func:`amendment_status` folds them into ONE section for the nightly STATE REPORT,
so every night proves the amendment is alive, not just recorded.

Pure at import (Scar #6): each doctrine module is a reduction; this one composes
their standing reports.
"""

from __future__ import annotations

from app.state import collaboration as _collab
from app.state import failure_law as _failure
from app.state import generativity as _gen
from app.state import human_logic as _logic
from app.state import meta_learning as _meta
from app.state import orchestra as _orchestra
from app.state import self_build as _build
from app.state import world_radar as _radar

__all__ = ["DOCTRINES", "amendment_status"]

# The nine doctrines, each with the module that implements it.
DOCTRINES: tuple[dict, ...] = (
    {"id": "E1", "name": "meta-learning", "module": "app.state.meta_learning",
     "law": "the state improves its own way of learning"},
    {"id": "E2", "name": "the failure law", "module": "app.state.failure_law",
     "law": "every failure must produce an autonomous behaviour change"},
    {"id": "E3", "name": "self-building", "module": "app.state.self_build",
     "law": "the state builds tools for its own intelligence; executables are caged"},
    {"id": "E4", "name": "the cycle of the weak", "module": "app.state.apoptosis",
     "law": "retire the weak by data; replace with the King's children (light mutation)"},
    {"id": "E5", "name": "human logic", "module": "app.state.human_logic",
     "law": "gradients, not dead binary; every logic is a permanent evolution subject"},
    {"id": "E6", "name": "episodic memory", "module": "app.state.episodic",
     "law": "every trade is a narrative, recalled by similarity before a proposal"},
    {"id": "E7", "name": "the world radar", "module": "app.state.world_radar",
     "law": "news of all currencies + orderflow of all pairs, a continuous sensor"},
    {"id": "E8", "name": "the collaborative world", "module": "app.state.collaboration",
     "law": "all is shared; the work converges, it is not a sum"},
    {"id": "E9", "name": "the orchestra", "module": "app.state.orchestra",
     "law": "a consensus of experts, never one master; the veto can refuse"},
)


def amendment_status(*, failures: list[dict] | None = None,
                     episodes: list[dict] | None = None,
                     common_memory: list[dict] | None = None,
                     prior_generativity: dict[str, float] | None = None,
                     current_generativity: dict[str, float] | None = None,
                     generativity_history: list[dict] | None = None) -> dict:
    """The nine doctrines' standing report, folded into one night-report section.

    Live sections read the caller's data (failures, episodes, common memory,
    generativity); the rest report their standing state. An absent input is honest:
    the section says what it measured and never invents a reading (E5/E2).

    E1 (Cure 4): when ``current_generativity`` is given, it becomes the audit's
    current reading and ``prior_generativity`` the stored prior, so E1 reports a
    real DELTA (improved / stalled / regressed) instead of an eternal "steady". A
    ``generativity_history`` additionally yields the multi-night TREND.
    """
    audit = _meta.meta_learning_audit(prior=prior_generativity,
                                      current=current_generativity)
    audit["trend"] = _gen.trend(generativity_history or [])
    return {
        "amendment": "THE FIRST AMENDMENT (nine doctrines, binding)",
        "n_doctrines": len(DOCTRINES),
        "doctrines": [{"id": d["id"], "name": d["name"], "law": d["law"]}
                      for d in DOCTRINES],
        "E1_meta_learning": audit,
        "E2_failure_law": _failure.failure_law_report(failures or []),
        "E3_self_building": _build.self_build_report(),
        "E4_cycle_of_the_weak": {
            "doctrine": "E4 the Cycle of the Weak",
            "rule": ("weakness is decided by survivability DATA (0 certified, all "
                     "tested died); the freed seats take light mutations of the King"),
            "reading": ("apoptosis retires the weak by data; the King's children "
                        "(light mutation, never clones) fill the seats"),
        },
        "E5_human_logic": {
            "doctrine": "E5 the Human Logic Doctrine",
            "gradient_labels": list(_logic.GRADIENT_LABELS),
            "evolution_targets": list(_logic.LOGIC_EVOLUTION_TARGETS),
            "reading": ("gradients replace hard thresholds; every logic is a "
                        "permanent evolution subject"),
        },
        "E6_episodic_memory": _episodic_report(episodes or []),
        "E7_world_radar": _radar.world_radar_report(),
        "E8_collaborative_world": _collab.collaboration_report(common_memory or []),
        "E9_orchestra": _orchestra.orchestra_report(),
    }


def _episodic_report(episodes: list[dict]) -> dict:
    from app.state import episodic

    return episodic.episodic_report(episodes)
