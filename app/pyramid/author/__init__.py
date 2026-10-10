"""THE AUTHOR — genetic programming over a typed grammar (Phase 4b).

The 45th family is not hand-written and not free-typed: the Author composes
strategy BODIES from a typed AST of causal primitives and emits real Python that
must still pass the full Phase-4a cage (static gate -> sandbox -> determinism ->
causality -> honest engine -> costs).

* :mod:`grammar` — the typed primitives, the :class:`Program`, and
  :func:`emit_python`.
* :mod:`synth`   — ``random_body`` / ``mutate_body`` / ``crossover_body``
  (deterministic under seed; every product validates).
* :mod:`registry` — R34 body-on-disk registry keyed by source SHA-256.

Purity: importing this package does no I/O and starts nothing. Build Mode.
"""

from __future__ import annotations

from app.pyramid.author.grammar import (
    Program,
    GrammarError,
    emit_python,
    node,
)
from app.pyramid.author.registry import (
    FAMILY_GENERATED_BODY,
    CONSTITUTION_BODY_HASH,
    body_hash,
)
from app.pyramid.author.search import AuthorConfig, AuthorResult, run_author

__all__ = [
    "Program",
    "GrammarError",
    "emit_python",
    "node",
    "AuthorConfig",
    "AuthorResult",
    "run_author",
    "FAMILY_GENERATED_BODY",
    "CONSTITUTION_BODY_HASH",
    "body_hash",
]
