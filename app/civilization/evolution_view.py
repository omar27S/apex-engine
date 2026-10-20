"""THE EVOLUTION VIEW -- the One Brain reads the factory's pantry (the bridge).

For days the two minds did not speak: the heart evolved 240 agents per island
every three hours and set champions aside, while the One Brain decided the
night's funding without ever seeing the evolution's harvest. This module is
the bridge: an honest read of the champions' pantry (one file per island)
and the factory ledger, shaped for the collective's block.

Honesty (Law 1): a missing pantry is an absent island -- never invented; a
champion is MEASURED only when its wilson_lb is a finite number (a measured
0.0 is honest: re-scored, under the floor); above-floor means wilson_lb > 0.
The ledger's dna seal is READ from the notes, never assumed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

__all__ = ["evolution_view", "pantry_voice"]

ISLANDS: tuple[str, ...] = ("heart", "turbo", "vault")


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_pantry(backend: Path, island: str) -> dict:
    """One island's pantry, honestly: absent file -> present: False."""
    path = backend / f"factory_champions_{island}.json"
    if not path.exists():
        return {"present": False}
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"present": False}
    entries = payload.get("champions") or []
    families: dict[str, int] = {}
    measured = under = above = 0
    top: dict | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fam = str(entry.get("family") or "unknown")
        families[fam] = families.get(fam, 0) + 1
        wilson = _finite(entry.get("wilson_lb"))
        if wilson is None:
            continue  # unmeasured: neither above nor below any floor
        measured += 1
        if wilson > 0.0:
            above += 1
        else:
            under += 1
        if top is None or wilson > top["wilson_lb"]:
            top = {"family": fam, "wilson_lb": wilson}
    return {
        "present": True,
        "champions": len(entries),
        "generation": payload.get("generation"),
        "families": families,
        "measured": measured,
        "under_floor": under,
        "above_floor": above,
        "top": top,
    }


def _read_ledger(backend: Path, *, tail: int = 5) -> dict:
    """The factory ledger's honest tail: recent rows, today's work, the seal."""
    path = backend / "factory_ledger.jsonl"
    rows: list[dict] = []
    if path.exists():
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue  # a torn line is skipped, never guessed
        except OSError:
            rows = []
    recent = rows[-max(1, tail):]
    # today is the ledger's LATEST date, never the last line's -- the order of
    # the rows is history's shape, not truth's (an out-of-order line must not
    # steal the day).
    today = max((str(r.get("date") or "") for r in rows), default="") or None
    trials_today = sum(int(r.get("trials") or 0) for r in rows
                       if today and r.get("date") == today)
    machines_today = sorted({str(r.get("machine")) for r in rows
                             if today and r.get("date") == today
                             and r.get("machine")})
    seal = None
    for row in reversed(rows):  # the most recent sealed note wins
        note = str(row.get("note") or "")
        if "dna=" in note:
            seal = note.split("dna=")[-1].split()[0]
            break
    return {
        "rows": len(rows),
        "recent": [{"date": r.get("date"), "machine": r.get("machine"),
                    "trials": r.get("trials"), "note": r.get("note")}
                   for r in recent],
        "trials_today": trials_today,
        "machines_today": machines_today,
        "dna_seal": seal,
    }


def pantry_voice(view: dict) -> str:
    """One honest sentence: what the evolution has, and what it lacks."""
    islands = view.get("islands") or {}
    present = [i for i, v in islands.items() if isinstance(v, dict) and v.get("present")]
    champions = sum(int(islands[i].get("champions") or 0) for i in present)
    measured = sum(int(islands[i].get("measured") or 0) for i in present)
    above = sum(int(islands[i].get("above_floor") or 0) for i in present)
    generations = [islands[i].get("generation") for i in present
                   if isinstance(islands[i].get("generation"), int)]
    ledger = view.get("ledger") or {}
    trials = ledger.get("trials_today") or 0
    shifts = len(ledger.get("recent") or [])
    seal = ledger.get("dna_seal")
    parts = [f"{champions} champions in the pantry "
             f"({', '.join(present) if present else 'no island'})"]
    parts.append(f"{measured} measured, {above} above the floor")
    if generations:
        parts.append(f"generation {max(generations)}")
    if trials:
        seal_note = f" ({seal})" if seal else ""
        parts.append(f"the heart ran {shifts} shifts and "
                     f"{trials:,} trials today{seal_note}")
    else:
        parts.append("no measured shift today")
    parts.append("the evolution is still searching"
                 if above == 0 else "the evolution found floor-clearers")
    return "; ".join(str(p) for p in parts) + "."


def evolution_view(backend_dir=".", *, islands: tuple[str, ...] = ISLANDS,
                   ledger_tail: int = 5) -> dict:
    """The bridge's view: the pantries + the ledger, honestly read."""
    backend = Path(backend_dir)
    view = {
        "schema": 1,
        "islands": {island: _read_pantry(backend, island)
                    for island in islands},
        "ledger": _read_ledger(backend, tail=ledger_tail),
        "seat_policy": ("distinct realms, best-first; empty seats stay empty "
                        "(no placeholder)"),
    }
    view["voice"] = pantry_voice(view)
    return view
