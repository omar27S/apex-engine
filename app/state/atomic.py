"""THE ATOMIC PEN (R134) -- one discipline for every throat the body writes.

Four private implementations of tmp+fsync+replace already lived in the body
(hyperfeed's snapshot, the certificates, the author's registry, and R133's
``cycle.Store``) -- the discipline existed but was COPIED, not shared, while
a dozen writers still landed their artifacts IN PLACE (the Grand's folds,
the mouth's signal, the flow's artifacts): a crash mid-write left a torn
file behind a multi-reader door, exactly the wound that made R133
necessary. The pen makes the discipline ONE thing:

    write_json(path, payload)  -- tmp sibling + fsync + atomic rename

Whole-or-old, never torn, no ghost tmp left behind. The READERS keep their
own contracts (R132's law: read through the OWNING module -- the
civilization's state is read through ``cycle.Store``, the pain ledger
through ``dd_ledger.load_ledger``); the pen only WRITES, and the writers
that own a contract (the Store, the dd_ledger) keep writing through it --
the pen is for the artifacts whose reader is the world.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

__all__ = ["write_json"]


def write_json(path: str | Path, payload: Any, *,
               indent: int = 2, default=str) -> Path:
    """Land a JSON document atomically: whole-or-old, never torn.

    The payload lands on a hidden tmp sibling in the SAME directory (the
    rename must not cross a filesystem), fsyncs, then renames over the
    target -- the kernel's whole-or-old guarantee. A crash mid-write can
    no longer tear the file, and a failed landing leaves no ghost.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=indent, default=default) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)  # whole-or-old, never torn
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)  # a failed landing leaves no ghost
    return target
