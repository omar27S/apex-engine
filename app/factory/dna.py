"""THE DIRECTOR'S DNA -- the twelve laws every agent is born under (v1),
and, from v2, the six faculties of THINKING sealed in the same helix.

The genome of every agent is numeric -- ema windows, rsi gates, atr multiples.
But the way agents are BORN, JUDGED, and REMEMBERED is not arithmetic: it is
law. This module is that law, transcribed once from the Director's method --
the same method that reanimated a heart dead four days, reopened a cathedral
collapsed on a rounding hair, and forbade the false receipt.

V2 (2026-10-20, the Boss's transplant order: "metti il tuo dna, cioe tutta
la tua struttura di pensare") adds the COGNITION to the CONDUCT: six
faculties transcribed in ``app.factory.zcognition`` -- perception declares
its darkness; decompose before deciding; hold many hypotheses; belief
follows evidence; attack the crown before wearing it; every prediction
scores itself. The laws say how an honest shift BEHAVES; the faculties say
how an honest mind THINKS. One seal covers both.

The DNA is not decoration. At every factory shift, on every island:

* the pantry's champions pass the HONEST INJECTION (Law 3): a champion that
  carries no measured score is a ghost and cannot re-enter generation 0 --
  counted and reported, never silently dropped;
* the shift's report carries the TRANSCRIPTION (``report["dna"]``), so the
  living body always knows which laws it evolved under;
* the ledger's note carries the SEAL (``dna=v2``), so a day's line can always
  be read as evidence of the law it was written under.

Read the laws aloud::

    python -m app.factory.dna
"""

from __future__ import annotations

import math
import sys

from app.factory import zcognition as _zcognition

__all__ = ["DNA_VERSION", "LAWS", "FACULTIES", "honest_champions", "seal",
           "transcribe", "main"]

DNA_VERSION = 2

LAWS: tuple[dict[str, str], ...] = (
    {
        "id": 1,
        "name": "measure before speech",
        "text": "No claim without a measurement behind it. A shift that "
                "measured nothing may not settle anything; a forged idea is "
                "carried to the next night, never buried by silence.",
        "guard": "cycle.py settle guard (R89); ledger.py fail-closed records",
    },
    {
        "id": 2,
        "name": "the dead must be proven",
        "text": "Never declare dead what was not measured. A quiet sensor is "
                "not a dead market; motion is judged in pips per minute, "
                "never by the sensor's sampling cadence.",
        "guard": "falcon.regime_flag -- the collapsed cathedral knife-edge",
    },
    {
        "id": 3,
        "name": "what is learned survives the shift",
        "text": "Champions persist and re-enter generation 0; a weak shift may "
                "not burn the pantry. And a champion that carries no measure "
                "is a ghost: it does not enter.",
        "guard": "factory_champions_{island}.json (R91) + honest_champions here",
    },
    {
        "id": 4,
        "name": "the seed is not destiny",
        "text": "The seed rotates with the ledger's length; no two shifts "
                "redraw the same evolution. Determinism per shift, never "
                "repetition across shifts.",
        "guard": "run_factory shift_seed (R92)",
    },
    {
        "id": 5,
        "name": "the receipt is evidence",
        "text": "Every record says who worked, how long, and what came of it "
                "-- or it is refused. The ledger is evidence, not decoration.",
        "guard": "ledger.FactoryRecord fail-closed (R66)",
    },
    {
        "id": 6,
        "name": "silence is not consent",
        "text": "A mute consultation cannot erase the day's word. What the "
                "Sage cannot say, the Sage cannot veto.",
        "guard": "sage_consult write-guard (R87)",
    },
    {
        "id": 7,
        "name": "every eye declares its darkness",
        "text": "A feed that cannot see says so, by name; exceptions are "
                "never swallowed by the gather.",
        "guard": "hawk_eye per-source audit errors",
    },
    {
        "id": 8,
        "name": "the wound is numbered, not hidden",
        "text": "Defects are counted, tracked and closed one by one. The scar "
                "is documentation; the autopsy is public.",
        "guard": "the numbered defects D1..D5 and their closure commits",
    },
    {
        "id": 9,
        "name": "the living state beats the typo",
        "text": "When the machine's blood and the paper disagree, the blood "
                "wins. The vault is merged around the living state.",
        "guard": "merge -X ours -- the VM's state is the truth (6b3b45a)",
    },
    {
        "id": 10,
        "name": "a system that cannot breathe alone is a walking corpse",
        "text": "The heart beats by timer, not by anyone pressing the button. "
                "Autonomy is not a feature; it is the pulse.",
        "guard": "apex-heart.timer -- one bounded shift every three hours",
    },
    {
        "id": 11,
        "name": "the proof is the real shift",
        "text": "A green test is necessary, never sufficient. The proof is the "
                "shift with real blood: the ledger line the heart wrote "
                "itself.",
        "guard": "the self-hosted runner turning every push into a live turn",
    },
    {
        "id": 12,
        "name": "what is written in the dark must be true in the morning",
        "text": "Every nightly commit must survive daylight. Fabricated "
                "heartbeats are forbidden -- four days of false 'heart:' "
                "commits taught the flatline's lesson.",
        "guard": "the flatline autopsy (2026-10-15 -> 2026-10-19)",
    },
)


# The six faculties of THINKING (DNA v2). Defined in app.factory.zcognition
# so the cognition module owns its own text; re-exported here because the
# seal is ONE: whoever reads the laws sees the faculties in the same breath.
FACULTIES = _zcognition.FACULTIES


def seal() -> str:
    """The ledger note's seal: one law-line every future row may carry."""
    return f"dna=v{DNA_VERSION}"


def honest_champions(entries) -> tuple[list, int]:
    """Law 3 applied to the pantry: only champions CARRYING A MEASURE re-enter.

    A measured ``wilson_lb`` of 0.0 is honest (the champion was re-scored and
    did not clear the rank floor); an absent, None, NaN or infinite score is a
    ghost -- refused and COUNTED (never silently dropped). A missing genome is
    a ghost too. Fail-open: a broken pantry cannot starve the shift.
    """
    keep: list = []
    refused = 0
    for entry in entries or []:
        if not isinstance(entry, dict):
            refused += 1
            continue
        genome = entry.get("genome")
        score = entry.get("wilson_lb")
        if not genome or score is None or not math.isfinite(float(score)):
            refused += 1
            continue
        keep.append(entry)
    return keep, refused


def transcribe(*, champions_refused: int = 0) -> dict:
    """The shift's transcription: which laws this evolution ran under."""
    return {
        "version": DNA_VERSION,
        "laws": len(LAWS),
        "faculties": len(FACULTIES),
        "seal": seal(),
        "champions_refused": int(champions_refused),
    }


def main() -> int:
    """Read the laws aloud -- for the Boss, for the diary, for anyone."""
    print(f"THE DIRECTOR'S DNA (v{DNA_VERSION}) -- the twelve laws,")
    print(f"and the six faculties of thinking (z-dna v2)")
    print()
    for law in LAWS:
        print(f"Law {law['id']}: {law['name']}")
        print(f"  {law['text']}")
        print(f"  guard: {law['guard']}")
    print()
    for f in FACULTIES:
        print(f"Faculty {f['id']}: {f['name']}")
        print(f"  {f['text']}")
        print(f"  guard: {f['guard']}")
    print()
    print(f"seal: {seal()}  ({len(LAWS)} laws + {len(FACULTIES)} faculties, "
          f"transcribed every shift)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
