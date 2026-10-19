"""THE BLOOD CIRCULATION -- the live candidates enter CORONATION (Part Seven, act 4).

The two live candidates the night found (net_r 5.22 and 4.13) enter coronation
NOW: a full dossier, the unseen gauntlet, and realm placement -- with progress
reported in EVERY Letter ("I RE DELLA NOTTE").

A candidate's coronation has honest PHASES, each gated on a MEASURED result -- never
on a calendar:

    dossier    -- the full per-pair dossier is built (net_r, friction multiple,
                  Wilson LB, mirror verdict)
    gauntlet   -- the R77 unseen gauntlet on drawn seeds (never memorisable)
    placement  -- the candidate is placed in its realms (coverage grows)
    crowned    -- it holds the throne: net-positive and gauntlet-clean

The progress percentage is the share of PHASES actually cleared (fail-closed: an
unmet gate never advances the crown).

Pure at import (Scar #6): a reduction over the report's leaderboard + gauntlet.
"""

from __future__ import annotations

__all__ = ["PHASES", "candidate_dossier", "coronation_report", "candidates_from_report"]

# The coronation phases, in order. A candidate must clear them IN ORDER.
PHASES: tuple[str, ...] = ("dossier", "gauntlet", "placement", "crowned")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def candidate_dossier(row: dict, *, gauntlet: dict | None = None,
                      realms: list[str] | None = None) -> dict:
    """One candidate's dossier + its honest coronation phase from measured facts."""
    r = row or {}
    g = gauntlet or {}
    net_r = _num(r.get("adv_net_r", r.get("net_r")))
    family = r.get("family") or "?"
    has_dossier = net_r is not None and _num(r.get("adv_trades")) is not None
    gauntlet_run = bool(g) and ("survives" in g or "failed_keys" in g)
    gauntlet_clean = bool(g.get("survives")) if gauntlet_run else False
    placed = bool(realms)

    phase = "dossier"
    if has_dossier:
        phase = "gauntlet" if not gauntlet_run else (
            "placement" if not gauntlet_clean else (
                "crowned" if placed else "placement"))
        if gauntlet_run and not gauntlet_clean:
            phase = "gauntlet"  # a failed gauntlet keeps it at the exam
    cleared = PHASES.index(phase) if phase in PHASES else 0
    progress = round(100.0 * cleared / (len(PHASES) - 1), 1)

    return {
        "family": family,
        "net_r": net_r,
        "trades": _num(r.get("adv_trades")),
        "resilience": _num(r.get("resilience")),
        "wilson_lb": _num(r.get("adv_lb")),
        "gauntlet_run": gauntlet_run,
        "gauntlet_clean": gauntlet_clean,
        "failed_keys": g.get("failed_keys") or [],
        "realms": realms or [],
        "phase": phase,
        "progress_pct": progress,
        "reading": (f"{family}: net_r {net_r}; corona {progress}% "
                    f"(fase {phase})"),
    }


def candidates_from_report(report: dict, *, min_net_r: float = 2.5) -> list[dict]:
    """Every leaderboard candidate with net_r above the floor, best first.

    The live candidates (net_r 5.22, 4.13) are exactly these rows; the floor keeps
    a losing body out of the coronation line.
    """
    r = report or {}
    lb = r.get("leaderboard") or []
    gaunt = {row.get("family"): row for row in (r.get("gauntlet") or [])}
    out = []
    for row in lb:
        net_r = _num(row.get("adv_net_r", row.get("net_r")))
        if net_r is None or net_r < min_net_r:
            continue
        fam = row.get("family")
        out.append(candidate_dossier(row, gauntlet=gaunt.get(fam)))
    out.sort(key=lambda c: (-(c["net_r"] or 0), str(c["family"])))
    return out


def coronation_report(report: dict, *, min_net_r: float = 2.5) -> dict:
    """The standing coronation reading for the Letter ('I RE DELLA NOTTE')."""
    cands = candidates_from_report(report, min_net_r=min_net_r)
    return {
        "candidates": cands,
        "count": len(cands),
        "reading": (f"{len(cands)} candidato/i in coronazione: "
                    + ", ".join(f"{c['family']} ({c['progress_pct']}%)"
                                for c in cands) if cands
                    else "nessun candidato sopra la soglia"),
    }
