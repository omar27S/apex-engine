"""THE CLOCK'S SEEDS — every day, and every hour, gets its OWN draw (Part One, Fix 1).

THE GROUNDHOG BUG: the night tournament ran with ``seed=0`` in the committed
config, so every night produced the SAME draw — the same population, the same
leaderboard, the same numbers, night after night. The seed was a constant, not a
clock.

This module derives the seed FROM THE CLOCK, deterministically and honestly:

* the NIGHT seed comes from the DATE (``YYYYMMDD``) — tonight's numbers differ from
  last night's by construction, and the date is recorded in the certificate so the
  difference is provable, not claimed;
* the MICRO-TOURNAMENT seed rotates with the DISPATCH TIMESTAMP (hourly slots);
* the BURST seed rotates with the dispatch timestamp AND the idea, so two bursts
  in the same hour are still distinct draws.

Pure at import (Scar #6): a reduction over a string, no I/O, no clock of its own.
The caller passes the date/timestamp; the module never reads the wall clock, so a
test (and the certificate) can name the exact draw.
"""

from __future__ import annotations

import hashlib

__all__ = [
    "SEED_MODULUS",
    "normalise_date",
    "seed_from_date",
    "micro_seed",
    "burst_seed",
    "seed_origin",
]

# Keep the seed a positive 31-bit integer: it fits a signed 32-bit C int (safe for
# numpy default_rng, which refuses a negative seed) and is stable across platforms.
SEED_MODULUS: int = 2 ** 31


def _digest_int(text: str) -> int:
    """A stable non-negative integer from a string (SHA-256, first 8 bytes)."""
    return int(hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16], 16)


def normalise_date(date: str) -> str:
    """``YYYY-MM-DD`` or ``YYYYMMDD`` -> ``YYYYMMDD`` (fail-closed on anything else)."""
    d = str(date).strip().replace("-", "")
    if len(d) != 8 or not d.isdigit():
        raise ValueError(f"date must be YYYYMMDD or YYYY-MM-DD, got {date!r}")
    return d


def seed_from_date(date: str) -> int:
    """The night's seed, DERIVED FROM THE DATE (the groundhog cure).

    The same date yields the same seed (reproducible); a different date yields a
    different seed (tonight's numbers differ from last night's).
    """
    return _digest_int("night:" + normalise_date(date)) % SEED_MODULUS


def micro_seed(*, dispatch_ts: str, slot: int = 0) -> int:
    """A micro-tournament's seed: the DISPATCH TIMESTAMP rotates it (hourly slots).

    ``slot`` distinguishes parallel micro-tournaments dispatched in the same second.
    """
    if not str(dispatch_ts).strip():
        raise ValueError("a micro-tournament needs its dispatch timestamp")
    return _digest_int(f"micro:{dispatch_ts}:{int(slot)}") % SEED_MODULUS


def burst_seed(*, idea: str, dispatch_ts: str) -> int:
    """A burst trial's seed: the dispatch timestamp AND the idea rotate it."""
    if not str(dispatch_ts).strip():
        raise ValueError("a burst needs its dispatch timestamp")
    return _digest_int(f"burst:{idea}:{dispatch_ts}") % SEED_MODULUS


def seed_origin(date: str, *, seed: int) -> dict:
    """The certificate's PROOF that the seed came from the clock, not a constant."""
    d = normalise_date(date)
    return {"date": d, "seed": int(seed), "derived_from": "date",
            "reading": f"seme della notte dal calendario {d}: {int(seed)}"}
