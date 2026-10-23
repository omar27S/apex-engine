"""R147 — THE ORGAN TRUTH RESOLVER (the standing cure for the dual-write plague).

The contract: the CI night shift and the VM's resident organs both write the
three contract files (``directed_mutations.json``, ``hawk_eye.json``,
``queue_state.json``) through the same shared repository. The plague: whenever
a shared-repo git operation (a pull with autostash, a runner checkout) meets
a dirty tree, git leaves the contract files UNMERGED (UU) -- and every organ
that afterwards touches git dies at the door ("Committing is not possible
because you have unmerged files"). On the night of 2026-10-23 the historian
died on that door at 02:39 while its healing was flawless (30 heals, 2797
bars); the flow's pushes had been refusing since 22:02 the evening before;
the Letter read the silence as an absent pulse ("BATTITO ASSENTE").

THE LAW (the organ owns its state):
1. Between two truths the FRESHER HEALTHY JSON wins. A sick JSON never wins,
   however fresh; a healthy one never loses to a sick one.
2. On equal freshness the WORKTREE wins (the living organ's own last write),
   then the incoming side, then the local HEAD.
3. When every side is sick the resolver REFUSES to guess: it reports, leaves
   the file untouched, and the organ's own next write is the cure.

What is resolved is written through the atomic pen (tmp sibling + fsync +
os.replace -- the same doctrine as :mod:`app.state.atomic`) and ``git add``-ed,
so the door reopens for the next organ. The resolver is pure diplomacy: it
resolves what it can prove and never invents a state.
"""
from __future__ import annotations

import json
import os
import subprocess as sp
from pathlib import Path

# The dual-write contract files, relative to the repository root.
CONTRACT_RELPATHS: tuple[str, ...] = (
    "APEX/backend/directed_mutations.json",
    "APEX/backend/hawk_eye.json",
    "APEX/backend/queue_state.json",
)

# The freshness keys an organ's truth may declare (max wins; ISO sorts as text).
_FRESHNESS_KEYS = ("generated_ts", "last_ts", "ts", "last_state_ts", "started_ts")

# Equal freshness preference: the living write, then the incoming, then HEAD.
_SIDE_ORDER = ("worktree", "incoming", "head")


def _has_conflict_markers(text: str) -> bool:
    """True when the text still wears git's conflict markers (line starts)."""
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("<<<<<<<") or s.startswith(">>>>>>>") or s == "=======":
            return True
    return False


def healthy_organ_json(text: str) -> dict | None:
    """A healthy organ truth: parses to a JSON object and carries no markers."""
    if not text or not text.strip() or _has_conflict_markers(text):
        return None
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return None
    return d if isinstance(d, dict) else None


def freshness(d: dict | None) -> str:
    """The freshest ISO timestamp the truth declares ("" when the organ is silent)."""
    if not isinstance(d, dict):
        return ""
    best = ""
    for key in _FRESHNESS_KEYS:
        v = str(d.get(key) or "").strip()
        if len(v) >= 10 and v > best:  # ISO-8601 sorts lexicographically
            best = v
    return best


def _pick_truth(sides: dict[str, dict | None]) -> tuple[str, dict] | None:
    """THE LAW applied: the freshest HEALTHY truth wins (the living write on a tie)."""
    ranked: list[tuple[str, int, str, dict]] = []
    for side in _SIDE_ORDER:
        d = sides.get(side)
        if d is None:
            continue
        ranked.append((freshness(d), -_SIDE_ORDER.index(side), side, d))
    if not ranked:
        return None
    _, _, side, d = max(ranked, key=lambda t: (t[0], t[1]))
    return side, d


def _git(repo: Path, *args: str) -> tuple[int, str]:
    r = sp.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def unmerged_paths(repo: Path) -> list[str]:
    """The paths git currently holds unmerged (the conflict states)."""
    rc, out = _git(repo, "status", "--porcelain")
    if rc != 0:
        return []
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) >= 3 and line[:2] in {"UU", "AA", "DU", "UD", "AU", "UA"}:
            paths.append(line[3:].strip().strip('"'))
    return paths


def _read_side(repo: Path, rel: str, stage: str) -> str:
    """One side of an unmerged file, as text ("" when the stage is absent)."""
    rc, out = _git(repo, "show", f":{stage}:{rel}")
    return out if rc == 0 else ""


def _atomic_write_text(path: Path, text: str) -> None:
    """The atomic pen (tmp sibling + fsync + os.replace) -- whole-or-old."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".orgtruth.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def resolve_organ_conflicts(repo: Path | str, *,
                            rel_paths: tuple[str, ...] = CONTRACT_RELPATHS) -> dict:
    """Resolve the unmerged CONTRACT FILES by organ truth; reopen git's door.

    Returns ``{"resolved": [...], "refused": [...], "detail": {...}}`` -- each
    resolution names the side that won and the freshness it declared. Idempotent
    and safe on a clean tree (nothing unmerged -> nothing to do, nothing said).
    """
    repo = Path(repo)
    report: dict = {"resolved": [], "refused": [], "detail": {}}
    unmerged = set(unmerged_paths(repo))
    if not unmerged:
        return report
    for rel in rel_paths:
        if rel not in unmerged:
            continue
        texts = {
            "head": _read_side(repo, rel, "2"),
            "incoming": _read_side(repo, rel, "3"),
            "worktree": ((repo / rel).read_text(encoding="utf-8", errors="replace")
                         if (repo / rel).exists() else ""),
        }
        sides = {k: healthy_organ_json(v) for k, v in texts.items()}
        picked = _pick_truth(sides)
        if picked is None:
            report["refused"].append(rel)
            report["detail"][rel] = ("every side sick -- the organ's own next "
                                     "write is the cure")
            continue
        side, _d = picked
        _atomic_write_text(repo / rel, texts[side])
        _git(repo, "add", "--", rel)
        report["resolved"].append(rel)
        report["detail"][rel] = (f"the {side} truth won "
                                 f"(freshness {freshness(_d) or 'silent'})")
    return report
