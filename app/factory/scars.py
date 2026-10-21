"""R121 -- THE SCAR TISSUE (il tessuto cicatriziale).

An organism that forgets its wounds heals them twice. The worklog is the
DIRECTOR's memory; the scar registry is the ORGANISM's -- a permanent,
machine-readable, committed file (``scars.json``) where every wound the
body has ever suffered is written once, with the law that guards it and a
TRIPWIRE: the name of the live mechanism that must fire if the wound ever
returns.

A tripwire is one of three kinds, and each is verifiable by the guardian:
* ``check``  -- a registered guardian check by name (CHECKS in anti_bug);
* ``test``   -- a pytest node id (file::test) that must exist in the tree;
* ``timer``  -- a systemd unit the guardian can ask for by name.

The guardian's ``scars_alive`` check (the 15th) reads the registry every
round: it must parse, every scar must be whole (id, born, organ, wound,
guard, tripwire), and every tripwire must RESOLVE to a live mechanism. A
scar whose tripwire has vanished is an alarm -- a law was removed while
the wound it guards still has a name. Removing a check without either
healing its scars or retiring them deliberately is now impossible to do
silently.

The registry is append-only in spirit: a scar may be retired only by
writing ``"retired": "YYYY-MM-DD"`` with the reason -- never deleted. The
past is not a draft (the historian's Law 1, applied to the body's own
biography).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCARS_VERSION = 1
SCARS_FILE = "scars.json"
TRIPWIRE_KINDS: tuple[str, ...] = ("check", "test", "timer")
_REQUIRED_FIELDS: tuple[str, ...] = ("id", "born", "organ", "wound",
                                     "guard")   # tripwire is a dict, its own law


def load_scars(path: str | Path) -> list[dict]:
    """The registry's scars; a missing or torn file is empty (honest,
    never fatal -- the guardian speaks the emptiness by name)."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(doc, dict) or not isinstance(doc.get("scars"), list):
        return []
    return [s for s in doc["scars"] if isinstance(s, dict)]


def _check_resolves(tripwire: dict, check_names: set[str],
                    backend: Path) -> str | None:
    """One tripwire's resolution, or the spoken complaint."""
    kind = tripwire.get("kind")
    name = tripwire.get("name")
    if kind not in TRIPWIRE_KINDS:
        return f"unknown tripwire kind {kind!r}"
    if not isinstance(name, str) or not name:
        return "tripwire without a name"
    if kind == "check":
        return None if name in check_names else f"check {name!r} is not registered"
    if kind == "test":
        if "::" not in name:
            return f"test tripwire {name!r} is not a node id (file::test)"
        rel, test_name = name.split("::", 1)
        f = backend / rel
        if not f.exists():
            return f"test file {rel!r} is gone"
        try:
            if re.search(rf"def {re.escape(test_name)}\b", f.read_text(encoding="utf-8")):
                return None
        except OSError:
            pass
        return f"test {test_name!r} is gone from {rel!r}"
    # timer: the guardian asks the machine -- resolution is 'ask', the
    # caller verifies with systemctl (the runner is not always a shell)
    return None


def verify_scars(backend: Path, *, check_names: set[str],
                 scars_path: str | Path | None = None) -> tuple[list[dict], list[str]]:
    """Every scar, whole; every tripwire, resolving.

    Returns (scars, complaints). A complaint is a spoken sentence -- the
    guardian speaks them verbatim; it never paraphrases a wound away.
    """
    path = Path(scars_path) if scars_path else (backend / SCARS_FILE)
    scars = load_scars(path)
    complaints: list[str] = []
    seen_ids: set[str] = set()
    for s in scars:
        sid = s.get("id")
        if sid in seen_ids:
            complaints.append(f"scar {sid!r} is written twice")
        seen_ids.add(sid)
        for field in _REQUIRED_FIELDS:
            if not isinstance(s.get(field), str) or not s.get(field):
                complaints.append(f"scar {sid!r} is missing {field!r}")
        tripwire = s.get("tripwire")
        if not isinstance(tripwire, dict):
            complaints.append(f"scar {sid!r} has no tripwire")
            continue
        if s.get("retired"):
            continue  # a retired scar's tripwire may rest with its law
        problem = _check_resolves(tripwire, check_names, backend)
        if problem:
            complaints.append(f"scar {sid!r}: {problem}")
    return scars, complaints


def census(scars: list[dict]) -> dict:
    """The spoken census: how many scars, how many still guarding."""
    active = [s for s in scars if not s.get("retired")]
    return {"total": len(scars), "guarding": len(active),
            "retired": len(scars) - len(active)}
