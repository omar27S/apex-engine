"""E3 -- SELF-BUILDING: the state builds tools that increase its own intelligence.

First Amendment, doctrine E3. The state may construct systems and technologies --
however advanced -- that help it think, remember, search, and create better. The
registry records what the state built FOR ITSELF, and enforces the one hard rule:
anything EXECUTABLE runs inside the safety cage (``app.pyramid.sandbox``), never in
the state's own process.

Pure at import (Scar #6): the catalogue is data; the functions classify what the
caller registers.
"""

from __future__ import annotations

__all__ = [
    "BUILD_CLASSES",
    "SELF_BUILT",
    "register_tool",
    "may_run_untrusted",
    "self_build_report",
]

# The classes of tool the state builds for its own intelligence.
BUILD_CLASSES: tuple[str, ...] = ("think", "remember", "search", "create")

# The tools the state has built (or commissioned) for itself. ``executable`` means
# the tool runs code; ``cage`` names the sandbox it must run in when it does.
# A ``purpose`` in BUILD_CLASSES says which intelligence it amplifies.
SELF_BUILT: tuple[dict, ...] = (
    {"name": "episodic_palace", "purpose": "remember", "executable": False,
     "cage": None, "note": "E6 memory; a data structure, not code"},
    {"name": "world_radar", "purpose": "search", "executable": False,
     "cage": None, "note": "E7 sensors; reads feeds, runs no foreign code"},
    {"name": "orchestra", "purpose": "think", "executable": False,
     "cage": None, "note": "E9 consensus; pure combination logic"},
    {"name": "generated_bodies", "purpose": "create", "executable": True,
     "cage": "app.pyramid.sandbox", "note": "R32/R33; self-written code runs caged"},
)


def may_run_untrusted(tool: dict) -> bool:
    """An EXECUTABLE tool may run only if it names a cage (E3, fail-closed).

    A tool that executes code without a cage is refused: self-building must never
    become a hole in the state's own process.
    """
    if not tool.get("executable"):
        return True  # a pure data tool runs anywhere
    return bool(tool.get("cage"))


def register_tool(name: str, *, purpose: str, executable: bool,
                  cage: str | None = None, note: str = "") -> dict:
    """Register a self-built tool. Refuses an uncaged executable (E3)."""
    if purpose not in BUILD_CLASSES:
        raise ValueError(f"purpose must be one of {BUILD_CLASSES}, got {purpose!r}")
    tool = {"name": str(name), "purpose": str(purpose),
            "executable": bool(executable), "cage": cage, "note": str(note)}
    if not may_run_untrusted(tool):
        raise ValueError(
            f"tool {name!r} is executable but names no cage; executable tools MUST "
            f"run inside the safety cage (E3)"
        )
    return tool


def self_build_report(tools: tuple[dict, ...] = SELF_BUILT) -> dict:
    """The self-building report: what the state built, and how it is contained."""
    by_purpose: dict[str, list[str]] = {c: [] for c in BUILD_CLASSES}
    uncaged: list[str] = []
    for t in tools:
        by_purpose.setdefault(t.get("purpose", "?"), []).append(t.get("name", "?"))
        if not may_run_untrusted(t):
            uncaged.append(t.get("name", "?"))
    return {
        "doctrine": "E3 self-building: the state builds tools for its own intelligence",
        "n_tools": len(tools),
        "by_purpose": by_purpose,
        "executable": [t["name"] for t in tools if t.get("executable")],
        "uncaged_executables": uncaged,
        "reading": (f"{len(tools)} self-built tools; "
                    f"{len([t for t in tools if t.get('executable')])} executable, "
                    f"all caged" if not uncaged else
                    f"{len(uncaged)} uncaged executable(s): {uncaged}"),
    }
