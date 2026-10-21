"""THE DIRECTOR'S COGNITION -- DNA v2: not the laws, the THINKING (R104).

The twelve laws (``app.factory.dna``, v1) are the Director's CONDUCT -- how
an honest shift behaves. The Boss then ordered the deeper transplant: "metti
il tuo dna, cioe tutta la tua struttura di pensare a tutti gli agenti" --
put your entire structure of THINKING into every agent (2026-10-20). This
module is that structure, transcribed as six faculties and two living
instruments. Every faculty is already GUARDED somewhere in the organism --
the cognition did not arrive as decoration; it arrived as a name for work
that was already law, plus the two instruments that were missing.

THE SIX FACULTIES (how the Director actually thinks, and now how the
evolution thinks):

1. PERCEPTION DECLARES ITS DARKNESS. Before reasoning about what is seen,
   say what is NOT seen. A feed that cannot see says so by name. Guard: the
   falcon's per-source audit + the hyperfeed's per-venue health.
2. DECOMPOSE BEFORE DECIDING. The whole is judged through its parts: life
   apart from merit, one pair apart from the union, tonight apart from the
   trend. Never one verdict where several honest ones fit. Guard: the
   living funnel R97, the slices, the probation window R100.
3. HOLD MANY HYPOTHESES. One explanation is a monopoly, and monopolies rot.
   The search keeps 48 families, 36 behavioral niches, and a measured
   entropy rate; the moment diversity falls, mutation rises. Guard: the
   behavioral atlas R103 + entropy R72.
4. BELIEF FOLLOWS EVIDENCE. Quantity (trades -> Wilson lower bound),
   independence (slice agreement -- does it win on EVERY slice or ride one?),
   recency (the probation window). Belief is never set by hope. Guard: the
   Wilson bound + :func:`slice_agreement` (this module).
5. ATTACK THE CROWN BEFORE WEARING IT. Before a body is crowned, it is
   attacked: is it a couch? one-pair lucky? a clone? a fit of the distant
   past? The champion that survives its own prosecution is the only one
   that enters the pantry. Guard: R97 + R100 + honest injection + dedup.
6. EVERY PREDICTION SCORES ITSELF. When the probation says "confirmed",
   that word is a PREDICTION, and the next shift's measurement is its
   GRADE. The :class:`CalibrationLedger` keeps the score; an organism that
   measures its own honesty stops lying by accident. Guard: this module.

THE TWO INSTRUMENTS:

* :func:`slice_agreement` -- the independence a champion's evidence carries
  (the fraction of the deterministic slices on which the body is net
  profitable). Two champions with the same Wilson bound are NOT equally
  believable when one wins on every slice and the other rides one.

* :class:`CalibrationLedger` -- the bounded memory of the probation's own
  predictions and their grades. ``record`` files a verdict; ``score``
  grades yesterday's verdict against today's measurement; ``accuracy``
  speaks the hit-rate (and never invents a score where none was graded).

Pure module (no I/O in the class, no app imports): the factory wires it,
the tests prove it, the heart commits its file with the ledger.

CLI:  python -m app.factory.zcognition
"""

from __future__ import annotations

import json
import sys

__all__ = [
    "COGNITION_VERSION", "FACULTIES", "slice_agreement",
    "CalibrationLedger", "zcognition_block", "main",
]

COGNITION_VERSION = 2

FACULTIES: tuple[dict[str, str], ...] = (
    {
        "id": 1,
        "name": "perception declares its darkness",
        "text": "Before reasoning about what is seen, say what is not. A "
                "feed that cannot see says so by name; the darkness is "
                "data, and the honest map includes its own blind spots.",
        "guard": "falcon per-source audit + hyperfeed per-venue health",
    },
    {
        "id": 2,
        "name": "decompose before deciding",
        "text": "The whole is judged through its parts: life apart from "
                "merit, one pair apart from the union, tonight apart from "
                "the trend. Never one verdict where several honest ones fit.",
        "guard": "the living funnel R97 + the slices + the probation R100",
    },
    {
        "id": 3,
        "name": "hold many hypotheses",
        "text": "One explanation is a monopoly, and monopolies rot. Keep "
                "48 families, 36 behavioral niches and a measured entropy; "
                "when diversity falls, mutation rises. Diversity is "
                "preparation for the regime that has not arrived yet.",
        "guard": "the behavioral atlas R103 + entropy R72",
    },
    {
        "id": 4,
        "name": "belief follows evidence",
        "text": "Quantity of evidence, independence of evidence, recency "
                "of evidence -- in that order, and never hope. The Wilson "
                "bound prices the sample; slice agreement prices the "
                "independence; the probation prices the morning.",
        "guard": "wilson_lb + slice_agreement (this module) + R100",
    },
    {
        "id": 5,
        "name": "attack the crown before wearing it",
        "text": "Before a body is crowned, it is prosecuted: is it a couch, "
                "one-pair lucky, a clone, a fit of the distant past? The "
                "champion that survives its own trial is the only one the "
                "pantry remembers.",
        "guard": "R97 couch law + R100 fire + honest injection + dedup",
    },
    {
        "id": 6,
        "name": "every prediction scores itself",
        "text": "A label is a prediction; the next measurement is its "
                "grade. The ledger of calibration keeps the score, so the "
                "organism stops lying by accident and starts being right "
                "on purpose.",
        "guard": "the calibration ledger (this module)",
    },
)


def slice_agreement(slice_net_rs) -> float | None:
    """The independence of a champion's evidence (Faculty 4).

    ``slice_net_rs`` is the iterable of net-R the SAME body measured on each
    deterministic slice of the universe. The agreement is the fraction of
    slices on which the body was net profitable. An empty iterable carries
    no evidence: ``None`` (unmeasured, never a 0.0 -- the couch lesson,
    applied to independence itself).
    """
    rows = [float(r) for r in (slice_net_rs or [])
            if isinstance(r, (int, float)) and float(r) == float(r)]
    if not rows:
        return None
    return sum(1 for r in rows if r > 0.0) / float(len(rows))


class CalibrationLedger:
    """The bounded memory of the probation's predictions and their grades.

    ``record`` files a verdict for a champion signature (once per shift;
    the ledger is idempotent on ``(shift_id, signature)``). ``score`` takes
    the NEXT shift's measured Wilson for that signature and grades the old
    verdict: a "confirmed" that measured ranked again AGREED; a "couch"
    that woke up DISAGREED (and the disagreement is exactly as interesting
    -- it prices the label). ``accuracy`` speaks the hit-rate over the
    graded rows only, with the counts beside it; nothing is invented.
    """

    def __init__(self, rows: list[dict] | None = None, *, max_rows: int = 400):
        self.max_rows = int(max_rows)
        self.rows: list[dict] = list(rows or [])[-self.max_rows:]

    def record(self, *, shift_id: str, signature: str, verdict: str,
               wilson_lb: float, family: str = "") -> bool:
        """File one verdict (idempotent per (shift, signature))."""
        if not signature or not verdict:
            return False
        key = (str(shift_id), str(signature))
        for r in self.rows:
            if (r.get("shift_id"), r.get("signature")) == key:
                return False  # a shift files its word once, then owns it
        self.rows.append({
            "shift_id": str(shift_id), "signature": str(signature),
            "verdict": str(verdict), "family": str(family or ""),
            "wilson_lb": round(float(wilson_lb or 0.0), 4), "graded": False,
        })
        self.rows = self.rows[-self.max_rows:]
        return True

    def score(self, *, signature: str, wilson_lb: float, ranked: bool) -> int:
        """Grade the UNGRADED rows of one signature against a new measure.

        Returns how many rows were graded (0 when the signature never filed
        -- an honest zero, never a fabricated agreement).
        """
        graded = 0
        for r in self.rows:
            if r.get("signature") != str(signature) or r.get("graded"):
                continue
            verdict = str(r.get("verdict"))
            if verdict == "confirmed":
                agreed = bool(ranked) and float(wilson_lb) >= 0.20
            elif verdict == "couch":
                # a couch that stays quiet AGREED; a couch that trades disagreed
                agreed = not (bool(ranked) and float(wilson_lb) >= 0.20)
            else:  # probation / unmeasured: a weaker word, graded leniently
                agreed = bool(ranked)
            r["graded"] = True
            r["next_wilson_lb"] = round(float(wilson_lb or 0.0), 4)
            r["next_ranked"] = bool(ranked)
            r["agreed"] = bool(agreed)
            graded += 1
        return graded

    def accuracy(self) -> dict:
        """The hit-rate over graded rows (and the counts that price it)."""
        graded = [r for r in self.rows if r.get("graded")]
        agreed = [r for r in graded if r.get("agreed")]
        return {
            "filed": len(self.rows),
            "graded": len(graded),
            "agreed": len(agreed),
            "disagreed": len(graded) - len(agreed),
            "hit_rate": (round(len(agreed) / len(graded), 4)
                         if graded else None),
            "note": "graded rows only; an ungraded label is not a score",
        }

    def ungraded(self) -> list[dict]:
        """The rows still waiting for their grade (the next shift's fuel)."""
        return [r for r in self.rows if not r.get("graded")]

    def to_dict(self) -> dict:
        return {"schema": 1, "kind": "calibration_ledger",
                "max_rows": self.max_rows, "rows": self.rows}

    @classmethod
    def from_dict(cls, data) -> "CalibrationLedger":
        """A torn file is a fresh ledger (fail-open), never a crash."""
        if not isinstance(data, dict):
            return cls()
        rows = data.get("rows")
        if not isinstance(rows, list):
            rows = []
        return cls([dict(r) for r in rows if isinstance(r, dict)])


def load_calibration(path) -> CalibrationLedger:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return CalibrationLedger.from_dict(json.load(fh))
    except (OSError, ValueError):
        return CalibrationLedger()


def save_calibration(ledger: CalibrationLedger, path) -> bool:
    try:
        # R136: the calibration ledger lands through THE ATOMIC PEN.
        from app.state import atomic  # noqa: E402
        atomic.write_json(path, ledger.to_dict())
        return True
    except (OSError, TypeError, ValueError):
        return False


def zcognition_block(*, qd_coverage: float | None = None,
                     calibration: dict | None = None,
                     slice_agreements=None,
                     champions: list[dict] | None = None) -> dict:
    """The shift's cognition receipt: the faculties, measured.

    ``slice_agreements`` is the list of the champions' agreement values
    (each 0..1, or None when unmeasured); ``champions`` the pantry-bound
    rows carrying ``slice_agreement`` beside their measure. The block is
    honest arithmetic over what is given -- no field is invented here.
    """
    agrees = [a for a in (slice_agreements or [])
              if isinstance(a, (int, float))]
    return {
        "version": COGNITION_VERSION,
        "faculties": len(FACULTIES),
        "seal": f"z-dna v2: {len(FACULTIES)} faculties over 12 laws",
        "qd_coverage": (round(float(qd_coverage), 4)
                        if isinstance(qd_coverage, (int, float)) else None),
        "calibration": calibration or {"filed": 0, "graded": 0,
                                       "agreed": 0, "disagreed": 0,
                                       "hit_rate": None,
                                       "note": "no calibration this shift"},
        "slice_agreement": {
            "measured": len(agrees),
            "unmeasured": len(slice_agreements or []) - len(agrees),
            "mean": (round(sum(agrees) / len(agrees), 4) if agrees else None),
            "perfect": sum(1 for a in agrees if a >= 0.999),
        },
        "champions": [
            {"signature": c.get("signature"),
             "slice_agreement": c.get("slice_agreement")}
            for c in (champions or [])
        ],
    }


def main() -> int:
    """Read the faculties aloud -- for the Boss, for the diary, for anyone."""
    print(f"THE DIRECTOR'S COGNITION (v{COGNITION_VERSION}) -- the six faculties")
    print("(the twelve laws of conduct live in app.factory.dna; these are the")
    print(" laws of THINKING, sealed in the same DNA)")
    print()
    for f in FACULTIES:
        print(f"Faculty {f['id']}: {f['name']}")
        print(f"  {f['text']}")
        print(f"  guard: {f['guard']}")
    print()
    print("instruments: slice_agreement (independence of evidence)")
    print("             calibration ledger (a label is a prediction, graded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
