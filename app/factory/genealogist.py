"""THE GENEALOGIST -- the evolution's memory of blood (R126).

For weeks the factory bred, selected and crowned without ever writing down
WHO BEGAT WHOM: the pantry's champions re-entered generation 0 every shift,
their children filled the pool, and nobody could tell whether the island's
240 bodies were 240 hunters or one founder's family reunion.  The genome's
``signature()`` has been documented as "a stable, compact lineage id" since
birth -- this module is the first organ that finally READS it as one.

Three ideas, all honest by construction:

* THE BLOOD BOOK (``factory_blood_{island}.json``, persisted beside the
  pantry): a map ``child-signature -> founder-signatures``.  A RANDOM
  newborn is its OWN founder (fresh blood, first of its line).  A MUTATED
  child inherits its parent's blood unchanged.  A CROSSOVER child carries
  the UNION of both parents' blood.  A signature met for the first time
  (a pantry or atlas entry older than the book) is a founder -- ancestry
  is never invented for the past (Law 3's spirit: no ghosts, and no
  fabricated grandfathers either).

* THE CENSUS (over the FINAL population): for every founder, the share of
  living bodies that carry its blood.  From the shares, the collision
  probability ``H = sum(share^2)`` -- the chance that two random bodies of
  the pool share a founder -- and the effective population ``Ne = 1/H``,
  the number of independent blood lines the search is really running.

* THE VERDICT (thresholds FIXED and DECLARED, never tuned to please):
  ``diverse``        H < 0.25   (Ne > 4 independent lines)
  ``concentrating``  0.25..0.50 (Ne 2..4 -- the pool is becoming a family)
  ``one-blood``      H >= 0.50  (Ne < 2 -- a family reunion wearing a
                                 population's clothes)

R127 -- THE CONSANGUINEITY BRAKE lives here as a pure chooser: when the
census says the blood is concentrating, the crossover's second parent is
drawn preferring a mate with DISJOINT blood (bounded tries, honest
fall-through when every candidate is a sibling), and under ``one-blood``
the next generation carries a bounded number of fresh IMMIGRANTS.  The
brake never touches the population size, the pair universe, or any
sizing rule -- it only widens the choice of mates inside the elites the
selection already made.  Observed, never obeyed: the census is spoken in
the report even when the verdict is quiet.

Build Mode: pure functions + a tiny persisted book; no I/O at import.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "BLOOD_SCHEMA",
    "VERDICT_THRESHOLDS",
    "BRAKE_TRIES",
    "BRAKE_IMMIGRANTS",
    "Birth",
    "BloodBook",
    "census",
    "herfindahl",
    "effective_population",
    "sibling_matings",
    "verdict",
    "choose_mate",
    "artifact",
]

BLOOD_SCHEMA = 1

# THE VERDICT'S FIXED THRESHOLDS (declared, never tuned to please):
# the collision probability of two random bodies' blood.
VERDICT_THRESHOLDS = {"concentrating": 0.25, "one_blood": 0.50}

# R127 -- the brake's bounds: how many draws the mate-chooser spends looking
# for unrelated blood, and how many fresh immigrants a one-blood generation
# may carry (a spice, not a takeover).
BRAKE_TRIES = 8
BRAKE_IMMIGRANTS = 4


# ---------------------------------------------------------------------------
# the book
# ---------------------------------------------------------------------------
@dataclass
class BloodBook:
    """The island's persistent memory of parentage, pruned by construction.

    ``blood`` maps a child signature to the frozenset of founder signatures
    its genome descends from.  The book is pruned on save to the signatures
    that still matter (the living population, the pantry, the bench, the
    atlas) -- memory of the LIVING, never an unbounded cemetery.
    """

    island: str = "heart"
    blood: dict[str, frozenset[str]] = field(default_factory=dict)
    founders_seen: int = 0

    # -- reading -----------------------------------------------------------
    def blood_of(self, sig: str) -> frozenset[str]:
        """The blood a signature carries; an unseen signature is EMPTY
        (the caller decides whether that makes it a founder)."""
        return self.blood.get(sig) or frozenset()

    def is_known(self, sig: str) -> bool:
        return sig in self.blood

    # -- writing -----------------------------------------------------------
    def record_founder(self, sig: str) -> None:
        """A random newborn (or a first sighting): its own founder."""
        if sig and sig not in self.blood:
            self.blood[sig] = frozenset((sig,))
            self.founders_seen += 1

    def record_child(self, sig: str, parents: tuple[str, ...]) -> frozenset[str]:
        """A bred child: the UNION of its parents' blood.  A parent absent
        from the book is a founder first (honest: its line starts now).
        Returns the child's blood."""
        acc: set[str] = set()
        for p in parents:
            if not p:
                continue
            pb = self.blood.get(p)
            if pb is None:
                self.record_founder(p)
                pb = self.blood[p]
            acc |= pb
        blood = frozenset(acc) if acc else frozenset((sig,))
        self.blood[sig] = blood
        return blood

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema": BLOOD_SCHEMA,
            "island": self.island,
            "founders_seen": self.founders_seen,
            "entries": len(self.blood),
            "blood": {k: sorted(v) for k, v in self.blood.items()},
        }

    def prune_to(self, alive: set[str]) -> None:
        """Keep only the blood of signatures that still matter.  The book
        remembers the living (and their pantry/bench/atlas futures), never
        the whole cemetery of every body ever born."""
        self.blood = {k: v for k, v in self.blood.items() if k in alive}

    @classmethod
    def load(cls, path: Path, *, island: str = "") -> "BloodBook":
        try:
            raw = json.loads(Path(path).read_text())
            blood = {str(k): frozenset(map(str, v or []))
                     for k, v in (raw.get("blood") or {}).items()}
            return cls(island=str(raw.get("island") or island),
                       blood=blood,
                       founders_seen=int(raw.get("founders_seen") or 0))
        except (OSError, ValueError, TypeError):
            return cls(island=island)  # a torn book is a fresh start, never a crash

    def save(self, path: Path) -> bool:
        try:
            Path(path).write_text(json.dumps(self.to_dict(), indent=1))
            return True
        except OSError:
            return False  # fail-open: the shift runs, the memory does not


@dataclass(frozen=True)
class Birth:
    """One honest birth record: who was born, how, and of whom."""

    child: str
    op: str                 # "random" | "mutate" | "crossover" | "seed"
    parents: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# the census (pure arithmetic over a signature->blood map)
# ---------------------------------------------------------------------------
def census(blood_map: dict[str, frozenset[str]]) -> dict[str, float]:
    """Founder -> share of living bodies carrying its blood.

    A crossover child carries BOTH founders, so shares may sum above 1.0 --
    that is not a bug, it is the arithmetic of ancestry (a body with two
    grandfathers counts for both, and the collision probability below is
    exactly the chance two bodies share at least one).
    """
    if not blood_map:
        return {}
    counts: dict[str, int] = {}
    for blood in blood_map.values():
        for founder in blood:
            counts[founder] = counts.get(founder, 0) + 1
    n = len(blood_map)
    return {f: c / n for f, c in counts.items()}


def herfindahl(census_map: dict[str, float]) -> float:
    """The blood-collision probability H = sum(share^2).

    H is the chance that two bodies drawn at random from the population
    share at least one founder's blood.  A pool of independent founders
    sits near 1/N; a family reunion sits near 1.0.
    """
    return sum(s * s for s in census_map.values())


def effective_population(herf: float) -> float:
    """Ne = 1/H -- how many independent blood lines the search runs."""
    return (1.0 / herf) if herf > 0.0 else float("inf")


def verdict(herf: float) -> str:
    """The declared reading of the sky's blood.  Thresholds are FIXED."""
    if herf >= VERDICT_THRESHOLDS["one_blood"]:
        return "one-blood"
    if herf >= VERDICT_THRESHOLDS["concentrating"]:
        return "concentrating"
    return "diverse"


def sibling_matings(matings: list[tuple[str, str]],
                    book: BloodBook) -> tuple[int, int]:
    """(shared, total): how many crossover pairs carry a common founder.

    An incest here is not a moral judgement -- it is the measurement that
    the crossover's two parents' blood INTERSECTS, which means the child's
    novel DNA is smaller than two independent lines would have given it.
    """
    shared = 0
    for a, b in matings:
        if book.blood_of(a) & book.blood_of(b):
            shared += 1
    return shared, len(matings)


# ---------------------------------------------------------------------------
# R127 -- the consanguineity brake (a pure chooser)
# ---------------------------------------------------------------------------
def choose_mate(candidates: list[str], first_parent: str, book: BloodBook,
                rng, *, max_tries: int = BRAKE_TRIES
                ) -> tuple[str, bool]:
    """Draw a crossover mate for ``first_parent``, preferring DISJOINT blood.

    Returns ``(mate_signature, avoided)`` where ``avoided`` is True when a
    sibling draw was rejected in favour of unrelated blood.  Bounded: after
    ``max_tries`` draws the last one rides anyway (an honest fall-through --
    when every candidate is family, the brake says so in the counters
    instead of inventing a stranger).  An empty candidate list returns the
    first parent itself (the caller's elites were already its family).
    """
    if not candidates:
        return first_parent, False
    fb = book.blood_of(first_parent)
    mate = None
    for _ in range(max(1, int(max_tries))):
        mate = candidates[int(rng.integers(len(candidates)))]
        if mate == first_parent:
            continue  # a genome crossing with itself is a clone, not a mating
        if not (fb & book.blood_of(mate)):
            return mate, True
    return (mate or first_parent), False


# ---------------------------------------------------------------------------
# the artifact
# ---------------------------------------------------------------------------
def artifact(*, island: str, blood_map: dict[str, frozenset[str]],
             births: list[Birth], book: BloodBook,
             brake: dict | None = None, ts: float | None = None) -> dict:
    """The spoken census: what the guardian reads and the letter may quote."""
    cns = census(blood_map)
    herf = herfindahl(cns)
    ne = effective_population(herf)
    top = sorted(cns.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    pairs = [(b.parents[0], b.parents[1]) for b in births
             if b.op == "crossover" and len(b.parents or ()) >= 2]
    shared, total = sibling_matings(pairs, book)
    return {
        "schema": BLOOD_SCHEMA,
        "island": island,
        "ts": float(ts if ts is not None else time.time()),
        "bodies": len(blood_map),
        "founders_alive": len(cns),
        "founders_seen_total": book.founders_seen,
        "herfindahl": round(herf, 4),
        "effective_population": round(ne, 2) if ne != float("inf") else None,
        "sibling_matings": shared,
        "crossovers": total,
        "verdict": verdict(herf),
        "thresholds": VERDICT_THRESHOLDS,
        "census_top": [{"founder": f[:12], "share": round(s, 4)}
                       for f, s in top],
        "brake": brake or {},
        "reading": (
            f"il sangue e' {verdict(herf)}: {len(cns)} linee vive su "
            f"{len(blood_map)} corpi (Ne={ne:.1f}, H={herf:.3f}, "
            f"incesti {shared}/{total})"
            if ne != float("inf")
            else f"il sangue e' {verdict(herf)} su nessun corpo misurato"),
    }
