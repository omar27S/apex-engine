"""R10 — THE DNA TRIBUNAL (evidence-adjusted search, no kill-lists).

The predecessor removed "bad" families with kill-lists. APEX does not. A family
with a census anomaly keeps its genes and its place; what changes is the SEARCH
AROUND IT — its gene bounds and its draw weight — and every change is written to
a TRIBUNAL LEDGER with the reason and the evidence that justified it.

This module is the single source for:

* :data:`DENSITY_DRAW_WEIGHT` — the base multiplier per census density class
  (firehose families are gate primitives: they must not drown the population;
  snipers are up-weighted for diversity).
* :func:`initial_weights_from_density` — turns a ``family -> density`` map into a
  weight table. The committed table ``family_weights.json`` is its output; it is
  DATA (loadable), regenerable from evidence, never hand-edited silently.
* :data:`FAMILY_BOUND_OVERRIDES` — per-family ``gene -> (low, high)`` widening.
  A widening may only ever be *at least* as wide as the sealed
  ``genome.GENE_BOUNDS`` (validated at import).
* :data:`FAMILY_GENE_BIAS` — per-family ``gene -> bias``: the draw samples
  ``low + (high-low) * u**bias`` so the gene is biased toward its floor without
  being fixed (the tournament still judges the family live).
* the append-only ledger (:data:`LEDGER_PATH`, gitignored) with
  :func:`record` / :func:`load_ledger`.

Build Mode: pure functions; file I/O happens only when a caller invokes the
ledger or the weight loader, never at import.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.quant import health as hp
from app.quant.genome import GENE_BOUNDS_BY_NAME

__all__ = [
    "DENSITY_DRAW_WEIGHT",
    "FAMILY_BOUND_OVERRIDES",
    "FAMILY_GENE_BIAS",
    "LEDGER_PATH",
    "WEIGHTS_PATH",
    "TRIBUNAL_DATE",
    "initial_weights_from_density",
    "load_family_weights",
    "record",
    "load_ledger",
    "effective_bounds",
    "gene_bias",
    "classify_pair",
    "HURST_REVERSION_TRIBUNAL_ENTRY",
    "survivability_findings",
    "autopsy_weight_delta",
]

# ---------------------------------------------------------------------------
# Draw weights (R10 + R9 density classes).
# ---------------------------------------------------------------------------
DENSITY_DRAW_WEIGHT: dict[str, float] = {
    "firehose": 0.3,   # a gate primitive, not a standalone signal
    "frequent": 0.7,
    "selective": 1.0,
    "sniper": 1.8,     # rare and specific: up-weight for diversity
}

WEIGHTS_PATH = "family_weights.json"  # committed, next to this module
LEDGER_PATH = "data/history/.tribunal.json"

TRIBUNAL_DATE = "2026-10-09"  # the first session's date (fixed, auditable)


def initial_weights_from_density(density_by_family: dict[str, str]) -> dict[str, float]:
    """Build the family draw-weight table from census density classes.

    Every family present in ``density_by_family`` gets its class's multiplier; a
    family with an unknown/missing class defaults to ``1.0`` (neutral) rather
    than being dropped. A weight is not a gate: a neutral weight keeps the family
    drawable while the anomaly is investigated.
    """
    weights: dict[str, float] = {}
    for family, density in density_by_family.items():
        weights[family] = float(DENSITY_DRAW_WEIGHT.get(density, 1.0))
    return weights


def load_family_weights(path: str | None = None) -> dict[str, float]:
    """Load the committed draw-weight table (DATA), falling back to neutral.

    A missing or unreadable table yields ``{}`` and every family then draws at
    neutral weight — never a permissive default value smuggled in as a constant.
    """
    target = Path(path) if path else Path(__file__).with_name(WEIGHTS_PATH)
    try:
        payload = json.loads(target.read_text())
    except (OSError, ValueError):
        return {}
    weights = payload.get("weights", {}) if isinstance(payload, dict) else {}
    return {str(k): float(v) for k, v in weights.items()}


# ---------------------------------------------------------------------------
# Per-family bound overlays (R10 widening). Absent gene means "sealed bound".
# ---------------------------------------------------------------------------
# The first tribunal session widens hurst_reversion_filtered's REVERSION ceiling
# (hurst_revert_max) from the sealed 0.50 up to 0.70, so the family can find the
# low-Hurst tape it needs. A widening may never *narrow* a sealed bound; checked
# by :func:`effective_bounds`.
FAMILY_BOUND_OVERRIDES: dict[str, dict[str, tuple[float, float]]] = {
    "hurst_reversion_filtered": {
        "hurst_revert_max": (0.0, 0.70),
    },
}

# Per-family draw bias toward the floor of a gene (``u**bias``). A bias of 1.0 is
# neutral; >1 pushes the sample toward ``low``. This keeps the gene unfixed (the
# tournament judges it live) while making the family's conflicting regime-gate
# genes land near their disabled floor often enough to be evaluable.
FAMILY_GENE_BIAS: dict[str, dict[str, float]] = {
    "hurst_reversion_filtered": {
        "regime_adx_min": 4.0,
        "regime_atr_rank_min": 4.0,
        "regime_hurst_min": 4.0,
    },
}


def effective_bounds(family: str, gene: str) -> tuple[float, float, bool]:
    """Return ``(low, high, is_int)`` for ``gene`` under ``family``'s overlay.

    The overlay may only widen: ``low <= sealed.low`` and ``high >= sealed.high``.
    A narrowing overlay is a bug, so it raises rather than silently shrinking the
    law's search space.
    """
    sealed = GENE_BOUNDS_BY_NAME[gene]
    overlay = FAMILY_BOUND_OVERRIDES.get(family, {}).get(gene)
    if overlay is None:
        return (sealed.low, sealed.high, sealed.is_int)
    low, high = float(overlay[0]), float(overlay[1])
    if low > sealed.low or high < sealed.high:
        raise ValueError(
            f"tribunal overlay for {family}.{gene} narrows the sealed bound "
            f"[{sealed.low}, {sealed.high}] to [{low}, {high}] — widening only"
        )
    return (low, high, sealed.is_int)


def gene_bias(family: str, gene: str) -> float:
    """The per-family draw bias for ``gene`` (1.0 = neutral)."""
    return float(FAMILY_GENE_BIAS.get(family, {}).get(gene, 1.0))


def classify_pair(raw: int, gated_by_profile: dict) -> dict:
    """R13: the tribunal consumes the SAME sealed classifier as the census.

    Thin wrapper so the tribunal has one vocabulary for health; it defers every
    decision to :func:`app.quant.health.family_health`. There is no tribunal-local
    GATED-ZERO flag any more (the 2.3a contradiction is deleted).
    """
    return hp.family_health(raw, gated_by_profile)


# ---------------------------------------------------------------------------
# The ledger (append-only; gitignored). One entry per ruling.
# ---------------------------------------------------------------------------
def record(entry: dict, path: str | None = None) -> None:
    """Append ``entry`` (JSON) to the tribunal ledger, creating it if absent."""
    target = Path(path) if path else Path(LEDGER_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(entry)
    payload.setdefault("date", TRIBUNAL_DATE)
    with open(target, "a") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def load_ledger(path: str | None = None) -> list[dict]:
    """Read the ledger, skipping any corrupt line rather than raising.

    A partially-written or hand-edited ledger must never take down an audit; a
    corrupt line is skipped and the readable rulings are returned.
    """
    target = Path(path) if path else Path(LEDGER_PATH)
    try:
        raw = target.read_text()
    except OSError:
        return []
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


# ---------------------------------------------------------------------------
# R39 (Phase 5) — TRIBUNAL EVIDENCE UPGRADE: autopsy-informed search adjustment.
# The first session's ruling follows, verbatim (evidence in, adjustment out).
# ---------------------------------------------------------------------------
# How many survivor autopsy losses a family must show before the tribunal acts.
AUTOPSY_MIN_LOSSES = 8
# The draw-weight multiplier applied to a family whose survivors systematically
# die a FIXABLE death (a stop-hunt/whipsaw victim). < 1 deprioritizes it in the
# draw so the search spends its budget elsewhere; it is NOT deleted (R10).
AUTOPSY_FIXABLE_WEIGHT = 0.5

_FIXABLE_CAUSES = ("stop_hunt_gap", "news_whipsaw")


def survivability_findings(certificates: list[dict]) -> dict:
    """R38/R39 — summarize RAMS survivability certificates for the tribunal.

    Returns per-family counts of certified vs failed genomes and the aggregated
    failed keys, so a family that systematically fails the adversary is visible.
    """
    by_family: dict[str, dict] = {}
    total = 0
    survived = 0
    for c in certificates:
        total += 1
        fam = str(c.get("family", "unknown"))
        box = by_family.setdefault(fam, {"certified": 0, "failed": 0,
                                          "failed_keys": {}})
        if c.get("survives", False):
            box["certified"] += 1
            survived += 1
        else:
            box["failed"] += 1
            for k in c.get("failed_keys", []) or []:
                box["failed_keys"][k] = box["failed_keys"].get(k, 0) + 1
    return {"total": total, "survived": survived, "failed": total - survived,
            "by_family": by_family}


def autopsy_weight_delta(autopsy_report: dict, *,
                         min_losses: int = AUTOPSY_MIN_LOSSES,
                         factor: float = AUTOPSY_FIXABLE_WEIGHT) -> dict:
    """R39 — evidence-keyed draw-weight adjustment from the autopsy.

    ``autopsy_report`` is :func:`app.quant.autopsy.distributions` output
    (``{"by_family": {...}, "total": {...}}``). A family whose survivors show at
    least ``min_losses`` total losses AND a majority of them a FIXABLE cause
    (stop-hunt/whipsaw — a death the adversary engineered rather than a broken
    edge) has its draw weight multiplied by ``factor``. The adjustment is
    EVIDENCE (reported + written to the ledger), never a kill-list (R10): the
    family stays registered and drawable, just sampled less until it adapts.
    """
    by_family = autopsy_report.get("by_family", {}) or {}
    weights: dict[str, float] = {}
    reasons: dict[str, dict] = {}
    for fam, causes in by_family.items():
        total = sum(int(v) for v in causes.values())
        fixable = sum(int(causes.get(c, 0)) for c in _FIXABLE_CAUSES)
        if total >= min_losses and fixable > (total - fixable):
            weights[fam] = float(factor)
            reasons[fam] = {"losses": total, "fixable": fixable,
                            "factor": float(factor),
                            "evidence": "majority fixable deaths under RAMS"}
    return {"weights": weights, "reasons": reasons,
            "doctrine": "R39 — autopsy-informed, evidence-keyed, never a kill-list"}


HURST_REVERSION_TRIBUNAL_ENTRY: dict = {
    "session": 1,
    "date": TRIBUNAL_DATE,
    "family": "hurst_reversion_filtered",
    "finding": "GATED-DEAD on 14/15 pairs: raw signals on every pair, but every "
               "active gate profile (trend + counter) returns zero final signals",
    "evidence": {
        # R13 single health definition. CADJPY (raw=49) is THIN, not GATED-DEAD;
        # the 2.3a GATED-ZERO/raw<50 contradiction is deleted.
        "health_by_pair": "14 GATED-DEAD, 1 THIN (CADJPY raw=49)",
        "gated_dead_pairs": 14,
        "thin_pairs": 1,
        "raw_min": 49,
        "raw_max": 73,
        "trend_final_nonzero_pairs": 0,
        "counter_final_nonzero_pairs": 0,
        "killing_gate": "after_activation",
        "probe": "grand census 44x15x3, EURUSD anchor",
    },
    "ruling": "WIDEN, not delete. The family stays registered and drawable. "
              "Root cause: its regime-activation genes require a HIGH regime "
              "(Hurst/ADX/ATR rank) while the family only trades LOW-Hurst "
              "reversion tape — a semantic conflict by construction. The "
              "tribunal therefore (a) widens the reversion ceiling "
              "hurst_revert_max 0.50 -> 0.70 and (b) adds a floor-bias (x4) on "
              "the three regime-gate genes so evolution can disable the "
              "conflicting gate when it helps, without fixing it.",
    "adjustments": {
        "bound_widen": {"hurst_revert_max": [0.0, 0.70]},
        "gene_bias": {"regime_adx_min": 4.0, "regime_atr_rank_min": 4.0,
                      "regime_hurst_min": 4.0},
        "draw_weight": "1.8 (sniper, unchanged)",
    },
    "decision": "JUDGE LIVE IN PHASE 2.3b — no deletion.",
}
