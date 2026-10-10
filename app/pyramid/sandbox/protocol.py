"""THE BODY PROTOCOL — the ONLY interface a generated body may use (Phase 4a).

A *body* is a self-written strategy artifact. It never imports APEX code: it runs
as a naked subprocess and speaks to the cage through this file I/O contract alone.

DIRECTIONS OF TRAFFIC (all via files inside the run's temp dir):

  INPUT  (the cage writes, the body reads):
    * ``input.parquet`` — the execution-frame slice, exactly the columns the
      honest engine reads (``ts`` seconds UTC, ``open``/``high``/``low``/
      ``close``/``volume``).
    * ``genes.json``    — the genome genes as a flat JSON object (a body may read
      its own parameters here; every value is a scalar).

  OUTPUT (the body writes, the cage reads):
    * ``output.json``   — a STRICT envelope::

          {"long": [0, 1, 0, ...], "short": [0, 0, 1, ...], "meta": {...}}

      ``long``/``short`` are equal-length lists of 0/1 (or true/false), one entry
      per input row, in the SAME order. Anything else is a ``protocol_violation``.

The reference "hello" body (:data:`HELLO_BODY_SOURCE`) buys every Monday 08:00
UTC — deliberately dumb, deliberately legal — and is the pipeline proof. It is
also the template a generated body starts from.

Pure: this module builds strings and parses files. No I/O happens at import.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "PROTOCOL_VERSION",
    "INPUT_PARQUET",
    "INPUT_GENES",
    "OUTPUT_JSON",
    "HELLO_BODY_SOURCE",
    "envelope",
    "parse_output",
    "write_inputs",
]

PROTOCOL_VERSION = 1
INPUT_PARQUET = "input.parquet"
INPUT_GENES = "genes.json"
OUTPUT_JSON = "output.json"


def envelope(long_mask, short_mask, meta: dict | None = None) -> dict:
    """Build a protocol envelope from two equal-length sequences of 0/1."""
    return {
        "protocol": PROTOCOL_VERSION,
        "long": [int(bool(x)) for x in long_mask],
        "short": [int(bool(x)) for x in short_mask],
        "meta": dict(meta or {}),
    }


class ProtocolViolation(ValueError):
    """The body's output did not honor the envelope contract."""


def parse_output(objs, n_rows: int) -> tuple[list[int], list[int], dict]:
    """Validate a decoded envelope against ``n_rows``; fail-closed.

    Returns ``(long, short, meta)``. Every malformed case raises
    :class:`ProtocolViolation` with a plain reason — never a silent coercion.
    """
    if not isinstance(objs, dict):
        raise ProtocolViolation("output is not a JSON object")
    if "long" not in objs or "short" not in objs:
        raise ProtocolViolation("output missing 'long'/'short'")
    long_raw, short_raw = objs["long"], objs["short"]
    if not isinstance(long_raw, list) or not isinstance(short_raw, list):
        raise ProtocolViolation("'long'/'short' must be lists")
    if len(long_raw) != n_rows or len(short_raw) != n_rows:
        raise ProtocolViolation(
            f"mask length mismatch: got long={len(long_raw)} short={len(short_raw)} "
            f"expected {n_rows}"
        )
    long_out, short_out = [], []
    for i, v in enumerate(long_raw):
        if isinstance(v, float) or not isinstance(v, (bool, int)) or v not in (0, 1):
            raise ProtocolViolation(f"long[{i}] is not a 0/1 flag: {v!r}")
        long_out.append(1 if v else 0)
    for i, v in enumerate(short_raw):
        if isinstance(v, float) or not isinstance(v, (bool, int)) or v not in (0, 1):
            raise ProtocolViolation(f"short[{i}] is not a 0/1 flag: {v!r}")
        short_out.append(1 if v else 0)
    meta = objs.get("meta", {})
    if not isinstance(meta, dict):
        raise ProtocolViolation("'meta' must be an object when present")
    return long_out, short_out, meta


def write_inputs(tmp_dir: Path, frame, genes: dict) -> tuple[Path, Path]:
    """Write the two inputs into ``tmp_dir`` and return their paths.

    ``frame`` is a pandas DataFrame already carrying the canonical columns.
    """
    parquet = Path(tmp_dir) / INPUT_PARQUET
    genes_path = Path(tmp_dir) / INPUT_GENES
    frame.to_parquet(parquet, index=False)
    genes_path.write_text(json.dumps(dict(genes), default=str))
    return parquet, genes_path


# ---------------------------------------------------------------------------
# The reference body. Naked stdlib + (optional) pandas read of the parquet; no
# APEX import, no network, no writes outside its own temp dir.
# ---------------------------------------------------------------------------
HELLO_BODY_SOURCE = '''"""HELLO BODY — buys every Monday 08:00 UTC. Deliberately dumb, deliberately legal."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _read_rows():
    """Return the input ts list. Prefer pandas if present; else a tiny parquet shim."""
    path = os.path.join(HERE, "input.parquet")
    try:
        import pandas as pd  # noqa: PLC0415
        df = pd.read_parquet(path)
        return [int(t) for t in df["ts"].tolist()]
    except Exception:
        # A body is allowed to fail loudly; the sandbox turns this into a death.
        raise


def main():
    ts = _read_rows()
    long_mask = []
    for t in ts:
        # Monday == weekday 0 in UTC; 08:00 == 8*3600 seconds into the day.
        day = t - (t % 86400)
        weekday = (day // 86400 + 3) % 7  # 1970-01-01 was a Thursday (weekday 3)
        secs = t - day
        long_mask.append(1 if (weekday == 0 and 8 * 3600 <= secs < 8 * 3600 + 3600) else 0)
    out = {
        "protocol": 1,
        "long": long_mask,
        "short": [0] * len(ts),
        "meta": {"family": "generated_hello", "rule": "buy Monday 08:00 UTC"},
    }
    with open(os.path.join(HERE, "output.json"), "w") as fh:
        json.dump(out, fh)


if __name__ == "__main__":
    main()
'''
