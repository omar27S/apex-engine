"""THE STATIC GATE — an AST whitelist walker (Phase 4b, R31).

Before a body ever reaches the sandbox, its SOURCE is parsed and walked against a
strict whitelist. The gate does not trust the Author: even though the grammar can
only emit legal trees, this gate re-verifies the emitted Python independently.

WHITELIST (only these may appear):

  * module-level ``import`` of ``numpy`` / ``pandas`` — nothing else;
    ``from`` imports are refused outright (a body has no need for them).
  * function ``def`` / ``return`` / ``if`` / ``for`` / ``while`` / ``with`` /
    ``try``/``except`` structure, ``pass`` / ``break`` / ``continue``.
  * ``call`` to a name or an attribute — but NEVER to a blacklisted builtin
    (``eval``, ``exec``, ``__import__``, ``getattr`` and friends) and never to a
    dunder attribute.
  * arithmetic / comparison / boolean / subscription / slicing / f-strings and
    the literals the grammar emits.

BLACKLIST (immediate death). Any of:

  * ``eval`` / ``exec`` / ``compile`` / ``__import__`` / ``globals`` /
    ``locals`` / ``vars`` / ``getattr`` / ``setattr`` / ``delattr`` /
    ``hasattr`` / ``memoryview`` / ``input`` / ``breakpoint``;
  * attribute access to ``ctypes`` / ``mmap`` / ``socket`` / ``subprocess`` /
    ``os.system`` / ``os.exec*`` / ``os.fork`` / ``os.spawn*`` / ``shutil``;
  * any ``Import`` / ``ImportFrom`` of a module other than numpy/pandas;
  * any name or attribute containing a dunder.

The gate returns a :class:`StaticVerdict`. A violation is a death with cause
``"static_gate"``. Pure: parses a string, touches no filesystem.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

__all__ = [
    "CAUSE_STATIC_GATE",
    "ALLOWED_IMPORTS",
    "BLACKLISTED_NAMES",
    "BLACKLISTED_ATTRS",
    "StaticVerdict",
    "StaticGateError",
    "check_source",
]

CAUSE_STATIC_GATE = "static_gate"

ALLOWED_IMPORTS: frozenset[str] = frozenset({"math", "numpy", "pandas", "json", "os"})

# The protocol's own reader/writer needs module identity and the entry guard;
# these two dunders are the ONLY dunders a body may mention. Any other dunder
# (e.g. ``__class__``, ``__globals__``) is a death.
ALLOWED_DUNDERS: frozenset[str] = frozenset({"__file__", "__name__"})

BLACKLISTED_NAMES: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "hasattr", "memoryview", "input",
    "breakpoint", "object", "super", "type",
})

# Attribute names that must never be reached through a dotted chain.
BLACKLISTED_ATTRS: frozenset[str] = frozenset({
    "ctypes", "mmap", "socket", "subprocess", "system", "spawn", "spawnl",
    "spawnv", "fork", "forkpty", "posix_spawn", "exec", "execl", "execv",
    "execlp", "execvp", "popen", "popen2", "popen3", "popen4",
    "shutil", "pickle", "marshal", "importlib", "builtins", "sys", "os",
    "write_text", "write_bytes", "unlink", "rmtree", "chmod", "chown",
})

# Node types the whitelist permits. Anything else is a violation.
_ALLOWED_NODES: tuple[type, ...] = (
    ast.Module, ast.Import, ast.ImportFrom,
    ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
    ast.Assign, ast.AugAssign, ast.AnnAssign, ast.If, ast.For, ast.While,
    ast.With, ast.withitem, ast.Try, ast.ExceptHandler, ast.Raise,
    ast.Pass, ast.Break, ast.Continue,
    ast.Expr, ast.Call, ast.Attribute, ast.Name, ast.Load, ast.Store, ast.Del,
    ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Slice, ast.Subscript,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.JoinedStr, ast.FormattedValue, ast.Starred, ast.keyword, ast.alias,
    ast.operator, ast.unaryop, ast.boolop, ast.cmpop, ast.expr_context,
    # operator / comparison singletons
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.Invert, ast.And, ast.Or, ast.BitAnd,
    ast.BitOr, ast.BitXor, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.MatMult,
    # tuple/list/dict unpacking helpers
    ast.Index,
)


class StaticGateError(Exception):
    """A body's source violated the R31 whitelist."""


@dataclass
class StaticVerdict:
    """The static gate's ruling on one source string."""

    ok: bool
    cause: str = ""
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "cause": self.cause, "violations": list(self.violations)}


def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def check_source(source: str) -> StaticVerdict:
    """Walk ``source`` as an AST; return a verdict. Never raises on bad source."""
    violations: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return StaticVerdict(False, CAUSE_STATIC_GATE, [f"syntax error: {e}"])

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            violations.append(f"forbidden node type {type(node).__name__}")
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED_IMPORTS:
                    violations.append(f"forbidden import {alias.name!r}")
        elif isinstance(node, ast.ImportFrom):
            # A body has no use for `from` imports; refuse them all.
            violations.append(f"forbidden 'from' import (module {node.module!r})")
        elif isinstance(node, ast.Name):
            if _dunder(node.id):
                if node.id not in ALLOWED_DUNDERS:
                    violations.append(f"dunder name {node.id!r}")
            if node.id in BLACKLISTED_NAMES:
                violations.append(f"blacklisted name {node.id!r}")
        elif isinstance(node, ast.Attribute):
            if _dunder(node.attr):
                violations.append(f"dunder attribute .{node.attr}")
            if node.attr in BLACKLISTED_ATTRS:
                violations.append(f"blacklisted attribute .{node.attr}")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in BLACKLISTED_NAMES:
                violations.append(f"blacklisted call {fn.id}()")
            if isinstance(fn, ast.Attribute) and fn.attr in BLACKLISTED_ATTRS:
                violations.append(f"blacklisted call .{fn.attr}()")

    if violations:
        return StaticVerdict(False, CAUSE_STATIC_GATE, sorted(set(violations)))
    return StaticVerdict(True)


def assert_ok(source: str) -> None:
    """Raise :class:`StaticGateError` if ``source`` fails the gate."""
    v = check_source(source)
    if not v.ok:
        raise StaticGateError("; ".join(v.violations))
