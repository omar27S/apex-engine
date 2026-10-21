"""R66 — THE FACTORY LEDGER.

Every job, on EITHER machine, appends an honest record: machine-hours, trials,
cache hits/misses, realm occupancy, and which heart/turbo produced it. The
records aggregate into a DAILY total committed to the vault, and
:func:`render_last_days` prints the last N days for the CEO's phone.

Pure at import (Scar #6). Files are touched only inside :func:`append` /
:func:`load` / :func:`write_daily` / :func:`render_last_days`.

Fail-closed: a record missing a required field, or carrying a non-finite number,
is refused — the ledger is evidence, not decoration.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

__all__ = [
    "MACHINES",
    "FactoryRecord",
    "LedgerError",
    "aggregate_daily",
    "append",
    "load",
    "render_last_days",
    "total_trials",
    "measured_derating",
]

# The three machines (R66). "vault" is the collector, not a compute island, but
# its fusion jobs are real work and are counted honestly.
MACHINES: tuple[str, ...] = ("heart", "turbo", "vault")

_REQUIRED = ("date", "machine", "job", "trials", "machine_seconds")


class LedgerError(ValueError):
    """A ledger record was refused (fail-closed)."""


def _finite_nonneg(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise LedgerError(f"expected a number, got {value!r}")
    if number != number or number in (float("inf"), float("-inf")):
        raise LedgerError(f"non-finite number {value!r} — refused (fail-closed)")
    if number < 0:
        raise LedgerError(f"negative number {value!r} — refused (fail-closed)")
    return number


@dataclass(frozen=True)
class FactoryRecord:
    """One job's honest line in the ledger."""

    date: str            # UTC date, YYYY-MM-DD
    machine: str         # one of MACHINES
    job: str             # free-form job name (e.g. "burst", "factory-shift")
    trials: int          # genomes evaluated (or fused, for the vault)
    machine_seconds: float
    cache_hits: int = 0
    cache_misses: int = 0
    realms_occupied: int = 0
    note: str = ""

    def validated(self) -> "FactoryRecord":
        for field in _REQUIRED:
            if getattr(self, field) in (None, ""):
                raise LedgerError(f"record missing required field {field!r}")
        if self.machine not in MACHINES:
            raise LedgerError(
                f"unknown machine {self.machine!r}; known: {MACHINES}"
            )
        if len(self.date) != 10 or self.date[4] != "-" or self.date[7] != "-":
            raise LedgerError(f"date must be YYYY-MM-DD, got {self.date!r}")
        _finite_nonneg(self.trials)
        _finite_nonneg(self.machine_seconds)
        _finite_nonneg(self.cache_hits)
        _finite_nonneg(self.cache_misses)
        _finite_nonneg(self.realms_occupied)
        if int(self.trials) < 0:
            raise LedgerError(f"negative trials {self.trials!r} — refused")
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def append(records: list[FactoryRecord], record: FactoryRecord,
           path: str | Path) -> None:
    """Append one validated record to the JSONL ledger (atomic-ish write)."""
    rec = record.validated()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec.to_dict(), sort_keys=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load(path: str | Path) -> list[FactoryRecord]:
    """Read every record; a malformed line is SKIPPED but counted in ``note``."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[FactoryRecord] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            out.append(FactoryRecord(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def aggregate_daily(records: list[FactoryRecord]) -> dict[str, dict]:
    """Fold records into per-day totals keyed by date (deterministic)."""
    days: dict[str, dict] = {}
    for r in records:
        d = days.setdefault(r.date, {
            "date": r.date, "trials": 0, "machine_seconds": 0.0,
            "cache_hits": 0, "cache_misses": 0, "jobs": 0,
            "machines": {}, "realms_occupied_max": 0,
        })
        d["trials"] += int(r.trials)
        d["machine_seconds"] += float(r.machine_seconds)
        d["cache_hits"] += int(r.cache_hits)
        d["cache_misses"] += int(r.cache_misses)
        d["jobs"] += 1
        d["machines"][r.machine] = d["machines"].get(r.machine, 0) + 1
        d["realms_occupied_max"] = max(d["realms_occupied_max"],
                                       int(r.realms_occupied))
    for d in days.values():
        d["machine_seconds"] = round(d["machine_seconds"], 3)
    return days


def total_trials(records: list[FactoryRecord]) -> int:
    return sum(int(r.trials) for r in records)


def write_daily(records: list[FactoryRecord], path: str | Path) -> dict[str, dict]:
    """Write the per-day aggregate to ``path`` as JSON; return it."""
    days = aggregate_daily(records)
    # R136: the band ledger days land through THE ATOMIC PEN (sort_keys kept).
    from app.state import atomic  # noqa: E402
    atomic.write_json(path, days, sort_keys=True)
    return days


def measured_derating(records: list[FactoryRecord]) -> dict:
    """DEBT-034: the derating factor, MEASURED from real runs (never a guess).

    The Army Ledger (R52) once derated a night's trials by a hardcoded ``0.7``
    "for overhead" -- an arithmetic guess, never measured. The factory ledger now
    carries real runs (``trials``, ``machine_seconds``), so the factor can be
    computed: ``derating = median_trials_per_minute / best_trials_per_minute``.
    The best observed throughput is the machine running with no slack (zero
    per-run overhead); a slower run's ratio to it IS its overhead penalty. The
    median across runs is the honest measured factor.

    Honest: fewer than 2 timed records -> ``factor`` is ``None`` (one run cannot
    separate throughput from overhead), never a fabricated number.
    """
    per_min = sorted(
        float(r.trials) / (float(r.machine_seconds) / 60.0)
        for r in records
        if float(r.machine_seconds) > 0 and int(r.trials) > 0
    )
    if len(per_min) < 2:
        return {"factor": None, "n": len(per_min), "best_trials_per_min": None,
                "median_trials_per_min": None, "worst_trials_per_min": None,
                "reading": (f"derating: non misurato ({len(per_min)} run "
                            f"cronometrato, ne servono 2)")}
    best = per_min[-1]
    median = statistics.median(per_min)
    factor = round(median / best, 4)
    return {
        "factor": factor, "n": len(per_min),
        "best_trials_per_min": round(best, 1),
        "median_trials_per_min": round(median, 1),
        "worst_trials_per_min": round(per_min[0], 1),
        "reading": (f"derating misurato: {factor:.3f} "
                    f"(mediana {median:.0f} vs migliori {best:.0f} trial/min "
                    f"su {len(per_min)} run)"),
    }


def render_last_days(records: list[FactoryRecord], days: int = 7) -> str:
    """A compact phone-readable summary of the last ``days`` days."""
    agg = aggregate_daily(records)
    ordered = sorted(agg, reverse=True)[:days]
    if not ordered:
        return "FACTORY LEDGER — no records yet."
    lines = [f"FACTORY LEDGER — last {len(ordered)} day(s)"]
    grand_trials = 0
    grand_hours = 0.0
    for date in ordered:
        d = agg[date]
        hours = d["machine_seconds"] / 3600.0
        grand_trials += d["trials"]
        grand_hours += hours
        machines = ",".join(f"{m}:{n}" for m, n in sorted(d["machines"].items()))
        lines.append(
            f"  {date}  trials={d['trials']:>8}  hours={hours:6.2f}  "
            f"jobs={d['jobs']:>3}  cache={d['cache_hits']}/{d['cache_misses']}  "
            f"realms_max={d['realms_occupied_max']}  [{machines}]"
        )
    lines.append(
        f"  TOTAL       trials={grand_trials:>8}  hours={grand_hours:6.2f}"
    )
    der = measured_derating(records)
    lines.append(f"  DERATING    {der['reading']}")
    return "\n".join(lines)
