"""THE CAGE — constitutional security for self-written code (Phase 4a).

Rank 4's Avant-Garde may one day WRITE its own strategy bodies (the 45th family,
``generated_body``). Before any of that, this package builds the prison:

* :mod:`protocol` — the sole interface a body may use (parquet + genes in, a
  strict JSON envelope out).
* :mod:`runner`   — the subprocess isolator (clean env, audit hook: no network,
  no nested process, no writes outside one temp dir; CPU/AS/FSIZE/NPROC limits;
  hard timeout). See its docstring for what IS and IS NOT enforced here.
* :mod:`judge`    — the four R30 gates (sandbox, determinism, causality, honest
  evaluation) and the resulting :class:`BodyVerdict`.

The cage writes nothing at import. Nothing here is live.
"""

from __future__ import annotations

from app.pyramid.sandbox.judge import BodyVerdict, judge_body
from app.pyramid.sandbox.protocol import HELLO_BODY_SOURCE
from app.pyramid.sandbox.runner import BodyRun, SandboxConfig, SandboxDeath, run_body

__all__ = [
    "BodyRun",
    "SandboxConfig",
    "SandboxDeath",
    "run_body",
    "BodyVerdict",
    "judge_body",
    "HELLO_BODY_SOURCE",
]
