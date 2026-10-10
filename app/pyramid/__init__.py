"""THE PYRAMID — seven hundred roles, one law, one judge (Phase 3.1).

The predecessor staffed its pyramid with individuals and then lost track of who
was alive. APEX staffs it with ROLES: each rank has a fixed, sealed headcount, and
the people (genomes) who fill a role are drawn from the honest tournament — never
declared, always earned.

The ranks (:mod:`app.pyramid.roster`):

* RANK 0 — THE ORACLE (1)            final confidence per candidate (AOS)
* RANK 1 — HIGH PRIESTS (4)          one per domain, aggregate their soldiers
* RANK 2 — GENERALS (80)             pair-domain commanders (15 active + 65 reserve)
* RANK 3 — SOLDIERS (210)            one live genome each
* RANK 4 — AVANT-GARDE (300)         exploration swarm (no live vote)
* RANK 5 — SPECTRE RESEARCHERS (105) free-thinking corps (notes only)

``1 + 4 + 80 + 210 + 300 + 105 = 700``. The number 700 is law; the arithmetic is
sealed in :data:`app.pyramid.roster.RANK_COUNTS` and pinned by test.

Supporting authorities:

* :mod:`app.pyramid.council` — THE COUNCIL OF SEVEN (the crown authority).
* :mod:`app.pyramid.trust`   — live per-genome reliability (trust scores).
* :mod:`app.pyramid.runtime` — the single ``run_pyramid`` entry point.

Build Mode: pure definitions and pure constructors; no I/O, no servers, no loops.
The one obeying loop (a tournament) lives in the tools and is invoked explicitly.
"""

from __future__ import annotations

__all__ = ["roster", "council", "trust", "runtime"]