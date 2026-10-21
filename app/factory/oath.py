"""R119 -- THE FORECASTER'S OATH (il giuramento dell'indovino).

An organism that evolves 720 agents but cannot say what IT will do next
is a savant that cannot find its own door. The oath is the organism's
self-knowledge, made honest by arithmetic:

BEFORE a shift turns, the forecaster speaks -- in probabilities, the only
language an honest prophet has -- what the shift will yield: will at least
one champion be crowned? will the diaspora carry a migrant? will the turn
finish fast? Each probability is the Laplace-smoothed base rate of the
LAST shifts that actually ran (never a feeling; a measurement). AFTER the
shift, the same organ grades the PREVIOUS oath against the facts that
came to pass, in Brier scores (0 = prophet, 0.25 = coin, 1 = liar).

The no-peeking law: the oath for turn N is a PURE function of ledger rows
0..N-1. It is computed before the shift's own row is appended, so it
cannot see the outcome it predicts -- the same determinism the witness
(R108) guarantees for the wheel.

Honesty laws:
* fewer than 3 usable turns of history -> the oath is None (an organism
  that has turned twice does not know itself yet; pretending otherwise
  would be the exact lie the calibration ledger exists to catch);
* a torn oath line is skipped, never fatal (append-only history, honest
  emptiness);
* the grade is written by the turn that FOLLOWS the oath, never by the
  oath itself (a prophet never grades their own sermon).

The oath ledger (``factory_oath.jsonl``, backend root, committed with the
state files) carries one line per turn:
``{"v", "ts", "machine", "oath", "facts", "grade"}`` where ``oath`` is the
prediction for THIS turn (from past rows only), and ``grade`` is the
verdict on the PREVIOUS turn's oath (Brier per field + mean). The ledger
row's note carries the headline (``oath=0.72``) for the CEO's phone.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

OATH_VERSION = 1
# The probability fields: each is a YES/NO question about THIS turn.
OATH_FIELDS: tuple[str, ...] = ("crowned", "migrants", "fast")
# The point-estimate field (a number, graded by absolute error).
# A turn is "fast" when it finishes under this many seconds.
FAST_S = 600.0
# Self-knowledge needs history: fewer usable turns than this -> oath None.
MIN_HISTORY = 3
# The base rate window: the last N turns that ran (regime changes make
# older turns lie about today -- the window keeps the memory honest).
WINDOW = 25

_CHAMP_RE = re.compile(r"champ_out=(\d+)")
_MIGR_RE = re.compile(r"migrants=(\d+)")


def facts_from_ledger_row(row: dict) -> dict | None:
    """Read one ledger row's turn facts (champ_out, migrants, seconds).

    Returns None when the row cannot speak all three -- an unmeasurable
    turn is never guessed into the calibration.
    """
    if not isinstance(row, dict):
        return None
    note = str(row.get("note") or "")
    m_champ = _CHAMP_RE.search(note)
    m_migr = _MIGR_RE.search(note)
    seconds = row.get("machine_seconds")
    if m_champ is None or m_migr is None:
        return None
    try:
        return {
            "crowned": int(m_champ.group(1)) >= 1,
            "migrants": int(m_migr.group(1)) >= 1,
            "fast": float(seconds) < FAST_S,
            "machine_seconds": float(seconds),
        }
    except (TypeError, ValueError):
        return None


def outcome_of(field: str, facts: dict) -> int:
    """The yes/no fact as 0/1 (unmeasured fields are absent -- KeyError is
    a caller bug, and bugs must be loud)."""
    return 1 if facts[field] else 0


def speak(past_facts: list[dict]) -> dict | None:
    """The oath for the NEXT turn, from the past turns' facts alone.

    Laplace smoothing (+1 success / +2 turns) keeps a 3-of-3 streak from
    becoming certainty -- a prophet who says 1.0 has never met a Monday.
    """
    usable = [f for f in past_facts[-WINDOW:]
              if all(k in f for k in ("crowned", "migrants", "fast"))]
    if len(usable) < MIN_HISTORY:
        return None
    n = len(usable)
    fields = {}
    for name in OATH_FIELDS:
        wins = sum(1 for f in usable if f[name])
        fields[name] = round((wins + 1) / (n + 2), 3)
    trials = [f.get("machine_seconds") for f in usable]
    trials = [t for t in trials if t is not None]
    point = round(sorted(trials)[len(trials) // 2], 1) if trials else None
    return {"v": OATH_VERSION, "fields": fields,
            "seconds_point": point, "base_n": n}


def grade(oath: dict | None, facts: dict) -> dict | None:
    """The verdict on one oath, spoken by the turn that followed it."""
    if not isinstance(oath, dict) or not oath.get("fields"):
        return None
    graded = {}
    briers = []
    for name, p in oath["fields"].items():
        if name not in facts:
            return None
        outcome = outcome_of(name, facts)
        brier = round((float(p) - outcome) ** 2, 4)
        graded[name] = {"p": p, "outcome": outcome, "brier": brier}
        briers.append(brier)
    seconds_verdict = None
    if oath.get("seconds_point") is not None and "machine_seconds" in facts:
        point = float(oath["seconds_point"])
        actual = float(facts["machine_seconds"])
        seconds_verdict = {"point": point, "actual": actual,
                           "err": round(abs(point - actual), 1)}
    return {"v": OATH_VERSION, "fields": graded,
            "mean_brier": round(sum(briers) / len(briers), 4),
            "seconds": seconds_verdict}


def calibrate(graded: list[dict], window: int = 20) -> dict | None:
    """The rolling self-knowledge meter: mean Brier over recent grades.

    0 = the organism knows itself; 0.25 = it is a coin; 1 = it inverts
    itself. Fewer than two graded oaths -> None (never a fabricated
    self-portrait).
    """
    means = [g["mean_brier"] for g in graded[-window:]
             if isinstance(g, dict) and isinstance(g.get("mean_brier"), (int, float))]
    if len(means) < 2:
        return None
    return {"mean_brier": round(sum(means) / len(means), 4), "n": len(means)}


# ---------------------------------------------------------------------------
# the turn's close: speak the next oath, grade the previous one, append both
# ---------------------------------------------------------------------------
def load_oath_rows(path: str | Path) -> list[dict]:
    """The oath ledger's rows; torn lines are skipped (never fatal)."""
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if isinstance(d, dict):
                rows.append(d)
        except json.JSONDecodeError:
            continue
    return rows


def past_facts_from_ledger(ledger_path: str | Path) -> list[dict]:
    """Every ledger row's facts, in order, holes honestly skipped."""
    p = Path(ledger_path)
    if not p.exists():
        return []
    facts: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            facts.append(facts_from_ledger_row(json.loads(line)))  # type: ignore[arg-type]
        except (json.JSONDecodeError, TypeError):
            continue
    return [f for f in facts if f is not None]


def close_turn(ledger_path: str | Path, oath_path: str | Path,
               *, machine: str, facts: dict,
               now: _dt.datetime | None = None) -> dict:
    """Speak the NEXT turn's oath, grade the PREVIOUS oath, append one line.

    The oath is a pure function of ledger rows BEFORE this turn (the
    ledger's own row for this turn has not been appended yet -- the caller
    holds it). The grade judges the previous oath with THIS turn's facts.
    Returns the row that was appended.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    oath = speak(past_facts_from_ledger(ledger_path))
    rows = load_oath_rows(oath_path)
    previous = rows[-1] if rows else None
    grade_verdict = grade(previous.get("oath") if previous else None, facts)
    row = {
        "v": OATH_VERSION,
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": machine,
        "oath": oath,                      # for the turn that ENDED
        "facts": facts,
        "grade": grade_verdict,            # for the PREVIOUS oath
    }
    p = Path(oath_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def headline_note(oath: dict | None) -> str:
    """The note fragment for the CEO's phone (``oath=0.72`` or ``oath=n/m``).

    Unmeasured self-knowledge is said aloud, never invented.
    """
    if not oath:
        return "oath=n/m"
    p = (oath.get("fields") or {}).get("crowned")
    return f"oath={p:.2f}" if isinstance(p, (int, float)) else "oath=n/m"
