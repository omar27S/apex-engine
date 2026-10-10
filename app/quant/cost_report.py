"""R19 — THE COST-SENSITIVITY REPORT: the reality invoice, in one place.

Two tournaments, same seed and config, differ in exactly one way — one judged on
GROSS R (era v1), one on NET R after the sealed cost model (era v2). This module
takes both :class:`~app.quant.tournament.TournamentResult` records (or their
persisted dicts) and publishes the divergence. THE DIVERGENCE IS THE REPORT: it
shows which genomes and families died only because reality invoiced them.

Three questions, answered plainly:

1. **The two leaderboards**, side by side — gross-era vs net-era, per family.
2. **Per-family survival** — how many members of each family are still standing
   (ranked) at the end of each era. A family can be a gross-era hero and a
   net-era corpse.
3. **The reality invoice** — total gross R vs total net R of the final
   population (the friction the market charged), and the list of genomes that
   died ONLY because of costs (ranked in v1, unranked/gone in v2).

R23 — KINSHIP MATCHING. Era comparison and death-matching use a coarse kinship
key (``family`` + rounded key genes; see :func:`kinship_key`), not the exact
signature, so a mutated near-twin is not double-counted as a separate "killed by
costs" casualty.

Pure aggregation over plain dicts: no I/O, no services, no engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

__all__ = [
    "FamilySurvival",
    "EraComparison",
    "compare_eras",
    "kinship_key",
    "kinship_duplicates",
]

# R23 — the "key genes" that define a coarse kinship. Two genomes that agree on
# family + these rounded genes are near-twins for era/death matching, so a mutated
# clone is not double-counted as a separate "killed by costs" casualty. The set is
# deliberately small and READ-ONLY here (declared, never re-derived ad hoc): it
# names the genes that most shape a strategy's trade behaviour.
KINSHIP_GENES: tuple[str, ...] = (
    "target_rr",
    "sl_atr_mult",
    "level_source_id",
    "trend_align",
    "min_confluence",
)
# Rounding grid for continuous key genes (integers are used verbatim).
KINSHIP_ROUND = 2


def kinship_key(subject) -> str:
    """A coarse kinship id (R23): ``family`` + the rounded key genes.

    ``subject`` is a :class:`~app.quant.genome.StrategyGenome` or a mapping of gene
    values. Continuous key genes are rounded to :data:`KINSHIP_ROUND`; integers are
    used verbatim. The key is stable and coarse on purpose: a mutated near-twin
    shares it, so era comparison and death-matching do not double-count one lineage
    as many "killed by costs" casualties.
    """
    if isinstance(subject, Mapping):
        get = lambda name, default=None: subject.get(name, default)  # noqa: E731
        family = str(get("family", ""))
    else:
        get = lambda name, default=None: getattr(subject, name, default)  # noqa: E731
        family = str(getattr(subject, "family", ""))
    parts = [family]
    for name in KINSHIP_GENES:
        value = get(name, None)
        if isinstance(value, bool):
            value = int(value)
        if isinstance(value, int):
            parts.append(f"{name}={value}")
        elif isinstance(value, float):
            parts.append(f"{name}={round(value, KINSHIP_ROUND)}")
        else:
            parts.append(f"{name}={value}")
    return "|".join(parts)


def kinship_duplicates(rows: list[dict]) -> dict[str, int]:
    """How many rows share each kinship key (for the audit's double-count check).

    A key with a count > 1 means the row set contains near-twins — exactly the case
    R23 exists to keep from inflating the "killed by costs" tally.
    """
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r.get("kinship") or kinship_key(r))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _rows(result) -> list[dict]:
    """Accept a TournamentResult, its to_dict(), or a plain dict; return rows."""
    if isinstance(result, Mapping):
        rows = result.get("final_population") or result.get("leaderboard") or []
    else:
        rows = getattr(result, "final_population", None)
        if not rows:
            rows = getattr(result, "leaderboard", []) or []
    return [dict(r) for r in rows]


def _by_family(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(str(r.get("family", "")), []).append(r)
    return out


def _key(row: dict) -> str:
    """The matching key for a tournament row (R23).

    Prefer an explicit ``kinship`` (stamped by the tournament); else derive one
    from the gene fields the row carries; else fall back to the exact
    ``signature`` (a row with no genes is itself). This keeps era matching coarse
    where gene data exists and exact where it does not.
    """
    if row.get("kinship"):
        return str(row["kinship"])
    if any(g in row for g in KINSHIP_GENES):
        return kinship_key(row)
    return "sig:" + str(row.get("signature", ""))


@dataclass(frozen=True)
class FamilySurvival:
    """One family's standing in both eras (ranked members are 'alive')."""

    family: str
    v1_alive: int                  # ranked (surviving) members in the gross era
    v2_alive: int                  # ranked (surviving) members in the net era
    v2_net_r: float                # total net R of the family's v2 survivors
    killed_by_costs: int           # members alive in v1 but dead in v2

    @property
    def survives_costs(self) -> bool:
        return self.v2_alive > 0


@dataclass(frozen=True)
class EraComparison:
    """The full R19 divergence between the gross era and the net era."""

    v1_label: str
    v2_label: str
    v1_rows: list[dict]
    v2_rows: list[dict]
    families: list[FamilySurvival]
    genomes_killed_by_costs: list[dict]
    total_gross_r_v2: float        # friction diagnostic: the v2 population's gross
    total_net_r_v2: float          # ... and what survived the invoice
    friction_invoice_r: float      # gross - net of the v2 population

    def format(self) -> str:
        """A plain, no-celebration text rendering (the report body)."""
        lines = [
            f"COST-SENSITIVITY REPORT (R19)  [{self.v1_label} vs {self.v2_label}]",
            "",
            "PER-FAMILY SURVIVAL (ranked members standing at end of era):",
            f"  {'family':<26} {'v1':>4} {'v2':>4} {'v2_netR':>10} {'killed_by_costs':>16}",
        ]
        for f in sorted(self.families, key=lambda x: (-x.v1_alive, x.family)):
            lines.append(
                f"  {f.family:<26} {f.v1_alive:>4} {f.v2_alive:>4} "
                f"{f.v2_net_r:>10.1f} {f.killed_by_costs:>16}"
            )
        lines += [
            "",
            "REALITY INVOICE (v2 final population):",
            f"  total gross R : {self.total_gross_r_v2:>10.2f}",
            f"  total net R   : {self.total_net_r_v2:>10.2f}",
            f"  friction      : {self.friction_invoice_r:>10.2f}",
            "",
            f"GENOMES KILLED ONLY BY COSTS: {len(self.genomes_killed_by_costs)}",
        ]
        for g in self.genomes_killed_by_costs:
            net = g["net_r"]
            net_s = "n/a" if net is None else f"{net:>8.2f}"
            lines.append(
                f"  {g['family']:<26} gross_r={g['gross_r']:>8.2f} "
                f"net_r={net_s} n={g['trades']}"
            )
        return "\n".join(lines)


def compare_eras(v1_result, v2_result, *, v1_label="v1 GROSS", v2_label="v2 NET") -> EraComparison:
    """Build the R19 divergence from a gross-era and a net-era result.

    Rows are matched by genome ``signature``. A genome that is present and ranked
    in v1 but absent from v2's ranked rows is one that costs killed. The v2 rows
    carry both ``gross_r`` (diagnostic) and ``net_r`` (ranked), so the invoice is
    computed directly.
    """
    v1_rows = _rows(v1_result)
    v2_rows = _rows(v2_result)
    v1_fam = _by_family(v1_rows)
    v2_fam = _by_family(v2_rows)
    # R23 — match by KINSHIP, not exact signature: a mutated near-twin that shares
    # the survivor's coarse key counts as the SAME lineage, so one line is never
    # double-counted as many "killed by costs" casualties.
    v2_keys = {_key(r) for r in v2_rows}

    families: list[FamilySurvival] = []
    for family in sorted(set(v1_fam) | set(v2_fam)):
        fam2 = v2_fam.get(family, [])
        alive_keys = {_key(r) for r in fam2}
        killed = sum(1 for r in v1_fam.get(family, []) if _key(r) not in alive_keys)
        families.append(
            FamilySurvival(
                family=family,
                v1_alive=len(v1_fam.get(family, [])),
                v2_alive=len(fam2),
                v2_net_r=sum(float(r.get("net_r", 0.0)) for r in fam2),
                killed_by_costs=killed,
            )
        )

    # One entry per killed KINSHIP (R23): dedupe near-twins so a single lineage that
    # vanished is reported once, not once per mutant.
    killed_by_costs: list[dict] = []
    seen_killed: set[str] = set()
    for r in v1_rows:
        key = _key(r)
        if key in v2_keys or key in seen_killed:
            continue
        seen_killed.add(key)
        killed_by_costs.append(
            {
                "kinship": key,
                "signature": str(r.get("signature", "")),
                "family": str(r.get("family", "")),
                "gross_r": float(r.get("gross_r", 0.0)),
                # v1 never computed a net R (it ran cost-free); do NOT print its
                # gross_r as if it were a net. The absence IS the finding: this
                # genome was never invoiced, and the moment it was, it vanished.
                "net_r": None,
                "trades": int(r.get("trades", 0)),
            }
        )

    total_gross = sum(float(r.get("gross_r", 0.0)) for r in v2_rows)
    total_net = sum(float(r.get("net_r", 0.0)) for r in v2_rows)

    return EraComparison(
        v1_label=v1_label,
        v2_label=v2_label,
        v1_rows=v1_rows,
        v2_rows=v2_rows,
        families=families,
        genomes_killed_by_costs=killed_by_costs,
        total_gross_r_v2=total_gross,
        total_net_r_v2=total_net,
        friction_invoice_r=total_gross - total_net,
    )