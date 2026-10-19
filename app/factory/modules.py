"""THE MODULAR ARMY -- cooperative coevolution (Mega Phase 2, Section B, Lever 11).

Instead of evolving whole strategies, APEX evolves strategy PARTS: entry logics, exit
strategies, filters, and sizing approaches. Each kind lives in its own catalogue, each
module carries its OWN trust score and survival record, and the tournament periodically
ASSEMBLES the current best parts into composite strategies and tests them. This
decomposes a 15,000-combination space (20 entries x 10 exits x 15 filters x 5 risk)
into four independently-searchable spaces.

THE MARKETPLACE: a module that appears in winning assemblies gains reputation; one that
appears in losing assemblies loses it. The Council can ORDER a named combination.

Honesty is binding: an unmeasured module trust is ``None`` (never a fabricated score);
an assembly references only catalogued modules; the trust update reads REAL assembly
outcomes, never a guess. Pure at import (Scar #6): catalogue data + pure functions.
"""

from __future__ import annotations

import itertools

__all__ = [
    "MODULES_VERSION",
    "ENTRY_MODULES",
    "EXIT_MODULES",
    "FILTER_MODULES",
    "RISK_MODULES",
    "module_kinds",
    "assembly_space",
    "assemble",
    "marketplace",
    "update_reputation",
    "modules_block",
]

MODULES_VERSION: int = 1

# The four module kinds (the breeding axes).
ENTRY_MODULES: tuple[str, ...] = (
    "fvg_tap", "ob_reclaim", "sweep_reversal", "breakout_confirm",
    "pullback_continuation", "range_fade", "momentum_ignition",
    "bos_retest", "turtle_soup", "vwap_reclaim", "orb_break",
    "pin_rejection", "engulf_confirm", "choch_shift", "spring_reclaim",
    "divergence_tap", "squeeze_expand", "gap_fill", "session_open_push",
    "vol_spike_break",
)

EXIT_MODULES: tuple[str, ...] = (
    "structural_target", "trailing_swing", "time_based",
    "momentum_exhaustion", "fixed_rr", "atr_trail",
    "parachute_lock", "partial_scale", "fvg_target", "round_number_target",
)

FILTER_MODULES: tuple[str, ...] = (
    "regime_hurst", "regime_adx", "session_london", "session_ny",
    "session_asia", "macro_risk_on", "macro_risk_off", "sentiment_extreme",
    "spread_tight", "vol_band", "atr_rank", "structure_align",
    "mtf_confirm", "volume_confirm", "cooldown",
)

RISK_MODULES: tuple[str, ...] = (
    "fixed_1pct", "vol_adjusted", "kelly_informed", "atr_risk", "fixed_frac",
)


def module_kinds() -> dict:
    """The catalogue sizes, keyed by kind (the directive's 20/10/15/5)."""
    return {"entry": len(ENTRY_MODULES), "exit": len(EXIT_MODULES),
            "filter": len(FILTER_MODULES), "risk": len(RISK_MODULES)}


def assembly_space() -> int:
    """The total combinatorial space (20 x 10 x 15 x 5 = 15,000)."""
    k = module_kinds()
    return k["entry"] * k["exit"] * k["filter"] * k["risk"]


def _catalogue(kind: str) -> tuple[str, ...]:
    return {"entry": ENTRY_MODULES, "exit": EXIT_MODULES,
            "filter": FILTER_MODULES, "risk": RISK_MODULES}.get(kind, ())


def assemble(entry: str, exit_: str, filter_: str, risk: str) -> dict | None:
    """Assemble one composite strategy from four named modules (or ``None`` if invalid).

    Fail-closed: an unknown module id yields ``None`` -- an assembly is never built
    from a part that is not in the catalogue.
    """
    parts = {"entry": entry, "exit": exit_, "filter": filter_, "risk": risk}
    for kind, name in parts.items():
        if name not in _catalogue(kind):
            return None
    return {
        "entry": entry, "exit": exit_, "filter": filter_, "risk": risk,
        "id": f"{entry}|{exit_}|{filter_}|{risk}",
        "modules": parts,
    }


def best_assemblies(module_scores: dict, *, top: int = 3, per_kind: int | None = None) -> list[dict]:
    """Assemble the current BEST modules of each kind into composites.

    ``module_scores`` maps ``kind -> {module -> trust}`` (trust in [0,1] or ``None``).
    The highest-trust module of each kind is selected; ties/absences fall back to the
    catalogue order (honest: an unmeasured trust never wins on a fabricated score).
    Returns up to ``top`` distinct assemblies built from the top ``per_kind`` modules
    of each kind.
    """
    per_kind = int(per_kind or 1)
    picks: dict[str, list[str]] = {}
    for kind in ("entry", "exit", "filter", "risk"):
        scores = (module_scores or {}).get(kind) or {}
        ordered = sorted(_catalogue(kind),
                         key=lambda m: (-(scores.get(m) if isinstance(scores.get(m), (int, float)) else -1.0),))
        picks[kind] = ordered[:max(1, per_kind)]
    combos = list(itertools.product(picks["entry"], picks["exit"],
                                    picks["filter"], picks["risk"]))
    out: list[dict] = []
    for e, x, f, r in combos[:max(1, int(top))]:
        a = assemble(e, x, f, r)
        if a is not None:
            out.append(a)
    return out


def marketplace(module_scores: dict | None = None) -> dict:
    """The module marketplace: each kind's modules with their trust + survival record.

    Honest: a module never scored has trust ``None`` and ``measured=False``.
    """
    scores = module_scores or {}
    board: dict = {}
    for kind in ("entry", "exit", "filter", "risk"):
        ksc = scores.get(kind) or {}
        rows = []
        for m in _catalogue(kind):
            row = ksc.get(m) or {}
            trust = row.get("trust") if isinstance(row, dict) else None
            rows.append({"module": m, "trust": trust,
                         "wins": (row.get("wins") if isinstance(row, dict) else None),
                         "losses": (row.get("losses") if isinstance(row, dict) else None),
                         "measured": isinstance(trust, (int, float))})
        rows.sort(key=lambda r: (-(r["trust"] if isinstance(r["trust"], (int, float)) else -1.0),))
        board[kind] = rows
    measured = any(r["measured"] for rows in board.values() for r in rows)
    return {"version": MODULES_VERSION, "board": board, "measured": measured,
            "space": assembly_space(),
            "reading": (f"mercato dei moduli: spazio {assembly_space()} combinazioni"
                        if measured else "mercato dei moduli: nessun modulo ancora quotato")}


def update_reputation(module_scores: dict, assembly: dict, *,
                      won: bool, weight: float = 1.0) -> dict:
    """Update every module's trust from ONE assembly's REAL outcome (winner/loser).

    A winning assembly credits each of its parts (``wins += 1``); a losing one debits
    them (``losses += 1``). Trust is the Wilson-free ratio ``wins / (wins + losses)``
    (``None`` until at least one outcome is recorded). Mutates and returns the scores.
    """
    scores = module_scores if module_scores is not None else {}
    for kind, name in (assembly.get("modules") or {}).items():
        ksc = scores.setdefault(kind, {})
        row = ksc.setdefault(name, {"wins": 0, "losses": 0})
        if won:
            row["wins"] = int(row.get("wins", 0)) + 1
        else:
            row["losses"] = int(row.get("losses", 0)) + 1
        total = row["wins"] + row["losses"]
        row["trust"] = round(row["wins"] / total, 4) if total else None
    return scores


def modules_block(module_scores: dict | None = None, *, top: int = 3) -> dict:
    """The Letter block: the marketplace + the current best assemblies (honest)."""
    mp = marketplace(module_scores or {})
    assemblies = best_assemblies(module_scores or {}, top=top)
    return {**mp, "assemblies": assemblies,
            "n_assembled": len(assemblies),
            "reading": (f"ESERCITO MODULARE: {len(assemblies)} combinazioni montate "
                        f"su uno spazio di {assembly_space()}"
                        if mp.get("measured") else mp["reading"])}
