"""THE OUTCOME CORPUS — R27's veto school and R28's calibration pool (Phase 4a).

DEBT-014's root cause was simple and embarrassing: the meta-label veto trained on
the SURVIVOR pool alone — a set that is net-positive by construction (only genomes
that survived reality net-positive reach the brain). A gate trained only on
winners never learns what a loser looks like, so it vetoed nothing.

R27 fixes the school. The veto trains on ALL historical outcomes ever recorded by
the tournament/evaluator: every ranked row with its NET R, winners AND losers
alike. This module is the sealed loader that assembles that corpus. A test proves
it contains net-negative rows.

R28 adds calibration. The same pool's AOS values are binned into ten equal-width
AOS bins; each bin reports its observed net-win rate and sample count. The oracle
report carries this table and an ``uncalibrated`` flag that clears ONLY when every
bin has at least ``MIN_BIN_SAMPLES`` rows. While uncalibrated, god-tier decisions
(AOS >= ``GOD_TIER_AOS``) are quarantined: reported, never actionable.

FEATURE MAPPING (canonical, shared by corpus and live scoring so train and
inference match EXACTLY). Only PRE-OUTCOME descriptors enter the feature vector —
the label (NET R sign) is never a feature. The historical corpus records only
genome-level aggregates, so the mapping is genome-level:
  aos               -- the AOS where known (brain verdicts), else the neutral 0.5
  domain_agreement  -- a stable FAMILY bucket in [0,1] (family identity is known
                       before any trade; it is the strongest honest separator the
                       corpus offers)
  session           -- genome session id / 3, else 0.5
  regime_percentile -- Wilson LB (the genome's track-record lower bound)
  trust             -- 0.5 (not recorded historically)
  funnel_stage      -- the genome's realized win rate (track record, not the label)
  density_class     -- min(1, trades / 200)
  spread_state      -- 0.5 (not recorded historically)

HONEST SCOPE: win_rate and Wilson LB are outcome-DERIVED aggregates, so this is a
coarse, mildly self-referential meta-model (a genome with a better track record is
likelier to be net-positive). It cannot use per-trade features because the corpus
does not record them. Documented as DEBT-018; the label itself (net-R sign) is
never a feature.

Pure at import; the loader's only I/O is reading the JSON corpus files it is given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.pyramid.veto import VetoFeatures
from app.quant.genome import FAMILIES

__all__ = [
    "MIN_BIN_SAMPLES", "GOD_TIER_AOS", "CALIBRATION_BINS",
    "CLEAN_ERA", "RAM_ERA", "ERA_LABELS", "FEATURE_NAMES",
    "OutcomeRow", "CorpusSummary", "load_corpus", "calibration_table", "features_from",
    "rows_with_era", "era_counts", "feature_drift", "to_feature_row",
]

MIN_BIN_SAMPLES = 30    # R28: a bin is trustworthy only at/above this count
GOD_TIER_AOS = 0.95     # R28: quarantine threshold while uncalibrated
CALIBRATION_BINS = 10   # R28: ten equal-width bins

# R37 — CORPUS ERAS. Era 0 is CLEAN (the honest engine under a real book; the
# surrogate for "real" until the CEO's live tape arrives). Era 1 is RAMS (the
# adversarial frame). The veto trains on CLEAN rows ONLY; RAMS rows are EVIDENCE.
CLEAN_ERA = 0
RAM_ERA = 1
ERA_LABELS = {CLEAN_ERA: "clean", RAM_ERA: "rams"}

# The canonical feature order (must match VetoFeatures.vector()).
FEATURE_NAMES: tuple[str, ...] = (
    "aos", "domain_agreement", "session", "regime_percentile", "trust",
    "funnel_stage", "density_class", "spread_state",
)

# Stable family -> bucket in [0,1]. Sorted so the mapping never depends on dict order.
_FAMILY_ORDER = sorted(FAMILIES)
_FAMILY_INDEX = {f: i for i, f in enumerate(_FAMILY_ORDER)}


def _clamp01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def family_bucket(family: str) -> float:
    """A stable [0,1] bucket for a family name (0.5 for an unknown family)."""
    n = len(_FAMILY_ORDER)
    if n <= 1 or family not in _FAMILY_INDEX:
        return 0.5
    return _FAMILY_INDEX[family] / (n - 1)


@dataclass(frozen=True)
class OutcomeRow:
    """One historical evaluation: its features, its NET R, and its label."""

    features: VetoFeatures
    net_r: float
    family: str = ""
    source: str = ""
    era: int = 0

    @property
    def label(self) -> int:
        return 1 if self.net_r > 0.0 else 0

    @property
    def net_win(self) -> bool:
        return self.net_r > 0.0


@dataclass
class CorpusSummary:
    rows: int = 0
    positives: int = 0
    negatives: int = 0
    zeros: int = 0
    sources: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"rows": self.rows, "positives": self.positives,
                "negatives": self.negatives, "zeros": self.zeros,
                "sources": dict(self.sources)}


def features_from(
    *,
    family: str = "",
    aos: float | None = None,
    trades: int = 0,
    win_rate: float = 0.0,
    wilson_lb: float = 0.0,
    session_id: int | None = None,
) -> VetoFeatures:
    """Build the canonical veto feature vector from row numbers (train == infer).

    The label (net_r sign) is deliberately NOT read here — it is applied separately.
    """
    return VetoFeatures(
        aos=0.5 if aos is None else float(aos),
        domain_agreement=family_bucket(family),
        session=0.5 if session_id is None else min(1.0, int(session_id) / 3.0),
        regime_percentile=_clamp01(wilson_lb),
        trust=0.5,
        funnel_stage=_clamp01(win_rate),
        density_class=float(min(1.0, trades / 200.0)),
        spread_state=0.5,
    )


def _rows_from_brain(data: dict, source: str, era: int = CLEAN_ERA) -> list[OutcomeRow]:
    out = []
    for v in (data.get("brain", {}) or {}).get("verdicts", []) or []:
        fam = str(v.get("family", ""))
        out.append(OutcomeRow(
            features=features_from(
                family=fam, aos=v.get("aos"),
                trades=int(v.get("trades", 0)),
            ),
            net_r=float(v.get("net_r", 0.0)), family=fam,
            source=source, era=int(data.get("era", era)),
        ))
    return out


def _rows_from_tournament(data: dict, source: str, era: int = CLEAN_ERA) -> list[OutcomeRow]:
    out = []
    data_era = int(data.get("era", era))
    for key in ("final_population", "leaderboard", "test_leaderboard"):
        for row in data.get(key, []) or []:
            if not isinstance(row, dict) or "net_r" not in row:
                continue
            fam = str(row.get("family", ""))
            net_r = float(row.get("net_r", row.get("test_net_r", 0.0)))
            out.append(OutcomeRow(
                features=features_from(
                    family=fam, aos=None,
                    trades=int(row.get("trades", row.get("test_trades", 0))),
                    win_rate=float(row.get("win_rate", 0.0)),
                    wilson_lb=float(row.get("wilson_lb", row.get("test_wilson_lb", 0.0))),
                ),
                net_r=net_r, family=fam, source=source, era=data_era,
            ))
    return out


def load_corpus(paths, era: int = CLEAN_ERA) -> list[OutcomeRow]:
    """Load every outcome row from the JSON corpus files. Sealed, fail-soft per file.

    A file that is missing or unreadable is SKIPPED and counted in the caller's
    summary — never a silent crash, never a fabricated row. ``era`` is the DEFAULT
    stamp; a file carrying its own ``"era"`` key overrides it (R37 — a RAMS run
    writes its artifacts with ``era=RAM_ERA``).
    """
    rows: list[OutcomeRow] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        base = path.name
        if "brain" in data:
            rows.extend(_rows_from_brain(data, base, era))
        if isinstance(data, dict):
            rows.extend(_rows_from_tournament(data, base, era))
    # De-duplicate on (family, net_r, features.vector()) so the same row read from
    # two files with identical numbers is not double-counted.
    seen: set = set()
    unique: list[OutcomeRow] = []
    for r in rows:
        key = (r.family, round(r.net_r, 9), r.features.vector())
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def summarize(rows: list[OutcomeRow]) -> CorpusSummary:
    s = CorpusSummary(rows=len(rows))
    for r in rows:
        if r.net_r > 0:
            s.positives += 1
        elif r.net_r < 0:
            s.negatives += 1
        else:
            s.zeros += 1
        s.sources[r.source] = s.sources.get(r.source, 0) + 1
    return s


def calibration_table(rows: list[OutcomeRow],
                      bins: int = CALIBRATION_BINS,
                      min_samples: int = MIN_BIN_SAMPLES) -> dict:
    """R28 reliability bins over the corpus AOS values.

    Returns ``{"bins": [...], "uncalibrated": bool, "min_samples": int,
    "sample_total": int}``. A bin is ``[lo, hi)`` over [0,1]; the last bin is
    closed. ``uncalibrated`` is True unless EVERY bin has >= ``min_samples`` rows.
    """
    edges = [i / bins for i in range(bins + 1)]
    boxes = [{"lo": edges[i], "hi": edges[i + 1], "n": 0, "wins": 0,
              "net_win_rate": None} for i in range(bins)]
    for r in rows:
        a = float(r.features.aos)
        a = min(1.0, max(0.0, a))
        idx = min(bins - 1, int(a * bins))
        boxes[idx]["n"] += 1
        if r.net_win:
            boxes[idx]["wins"] += 1
    for b in boxes:
        b["net_win_rate"] = (b["wins"] / b["n"]) if b["n"] else None
    uncalibrated = any(b["n"] < min_samples for b in boxes) or not rows
    return {"bins": boxes, "uncalibrated": uncalibrated,
            "min_samples": min_samples, "sample_total": len(rows),
            "bins_with_samples": sum(1 for b in boxes if b["n"] > 0)}


def quarantine_decision(aos: float, calibration: dict) -> dict:
    """R28 structural quarantine: a god-tier AOS while uncalibrated is reported,
    never actionable."""
    god_tier = float(aos) >= GOD_TIER_AOS
    quarantined = bool(god_tier and calibration.get("uncalibrated", True))
    return {"aos": float(aos), "god_tier": god_tier, "quarantined": quarantined,
            "actionable": not quarantined}


# ---------------------------------------------------------------------------
# R37 — CORPUS ERAS: clean-vs-RAMS rows, clean-only training, feature drift.
# ---------------------------------------------------------------------------
def rows_with_era(rows: list[OutcomeRow], era: int) -> list[OutcomeRow]:
    """The subset of ``rows`` stamped with ``era`` (R37)."""
    return [r for r in rows if int(r.era) == era]


def era_counts(rows: list[OutcomeRow]) -> dict:
    """Count rows per era label (R37), including the zeros."""
    counts = {label: 0 for label in ERA_LABELS.values()}
    for r in rows:
        counts[ERA_LABELS.get(int(r.era), f"era_{r.era}")] = \
            counts.get(ERA_LABELS.get(int(r.era), f"era_{r.era}"), 0) + 1
    return counts


def to_feature_row(row: OutcomeRow) -> dict:
    """A named feature dict for one row (for drift and audit)."""
    vec = row.features.vector()
    return dict(zip(FEATURE_NAMES, (float(x) for x in vec)))


def feature_drift(clean: list[OutcomeRow], rams: list[OutcomeRow]) -> dict:
    """R37 — per-feature mean shift (RAMS minus CLEAN) and its stability.

    A feature whose RAMS mean moves far from its CLEAN mean is one the adversary
    perturbs; the drift table is REPORTED, never used to silently reweight the
    veto. Returns ``{"per_feature": {name: {clean, rams, delta, abs_delta}},
    "max_abs_delta": float, "drifted": [names]}``.
    """
    per_feature: dict[str, dict] = {}
    drifted: list[str] = []
    max_abs = 0.0
    for name in FEATURE_NAMES:
        cvals = [to_feature_row(r)[name] for r in clean]
        rvals = [to_feature_row(r)[name] for r in rams]
        cmean = float(sum(cvals) / len(cvals)) if cvals else 0.0
        rmean = float(sum(rvals) / len(rvals)) if rvals else 0.0
        delta = rmean - cmean
        # A shift above this is "drifted": a conservative, documented threshold.
        is_drifted = abs(delta) >= 0.05
        if is_drifted:
            drifted.append(name)
        max_abs = max(max_abs, abs(delta))
        per_feature[name] = {
            "clean": cmean, "rams": rmean, "delta": delta,
            "abs_delta": abs(delta), "drifted": is_drifted,
            "n_clean": len(cvals), "n_rams": len(rvals),
        }
    return {"per_feature": per_feature, "max_abs_delta": max_abs, "drifted": drifted}
