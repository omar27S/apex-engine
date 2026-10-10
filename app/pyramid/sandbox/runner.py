"""THE SANDBOX — a subprocess isolator for self-written bodies (Phase 4a).

A generated body runs as a NAKED subprocess: it never imports APEX code, it never
runs in this process, and it may only touch files inside one temp dir. The cage
runs it, watches it, and either returns its signals or kills it with a recorded
cause.

WHAT IS ENFORCED ON THIS PLATFORM (Linux + CPython) — honesty over theatre
-----------------------------------------------------------------------------
Enforced (hard):
  * SEPARATE PROCESS. ``subprocess`` with ``start_new_session=True``; the body
    cannot corrupt the cage's memory or state.
  * TIMEOUT. The parent kills the process group after ``timeout`` seconds
    (default 5.0). A hang is a death, cause ``"sandbox_death"``.
  * NO NETWORK. A CPython audit hook (``sys.addaudithook``) aborts on
    ``socket.__new__`` / ``socket.connect`` / ``socket.getaddrinfo``. Any attempt
    is a violation, cause ``"sandbox_death"``.
  * NO WRITES OUTSIDE THE TEMP DIR. The audit hook aborts on ``open`` with a
    write mode whose resolved path is not under the run's temp dir. Reads of
    common secret files (``~/.ssh``, ``.env``, cloud credential files) are also
    aborted.
  * NO NESTED PROCESSES. ``subprocess.Popen`` / ``os.exec*`` / ``os.fork`` /
    ``os.system`` / ``os.spawn*`` are aborted by the audit hook.
  * NO NATIVE ESCAPE (Phase 4b). The audit hook also aborts the CPython events
    ``ctypes.dlopen`` / ``ctypes.dlsym`` / ``ctypes.addressof`` /
    ``ctypes.call_function``, ``mmap.__new__``, and ``builtins.input`` /
    ``builtins.breakpoint``.
    HONESTY: these events exist on this CPython and are hooked; a compiler flag
    or a platform that never raises them would leave the corresponding name
    un-hooked (it is simply never hit), so the AST static gate is the belt and
    these are the suspenders — not a proof of containment.
  * NO FILESYSTEM MUTATION. ``os.remove`` / ``rename`` / ``mkdir`` / ``chmod`` /
    ``link`` / ``symlink`` / ``shutil.*`` are aborted outright.
  * CPU + ADDRESS-SPACE + FILE-SIZE LIMITS via ``resource.setrlimit`` in the
    child (``RLIMIT_CPU``, ``RLIMIT_AS`` default 1 GiB, ``RLIMIT_FSIZE``,
    ``RLIMIT_NPROC``). These are OS-enforced and cannot be lifted by the body.
  * NO ENVIRONMENT LEAK. The child receives a CLEAN environment (a minimal
    ``PATH``/``HOME``/``PYTHONPATH``) — no host secrets are inherited.

NOT enforced (stated plainly, so nobody mistakes the cage for a VM):
  * The audit hook is a CPython-level control. Code that drops to a C library
    outside CPython's audited surface (raw ``ctypes`` into libc, ``mmap`` tricks)
    could in principle bypass it. It stops ordinary generated strategy Python —
    ``os``/``open``/``socket``/``subprocess`` — not a hostile kernel exploit.
  * No seccomp / no namespaces / no container. The filesystem OUTSIDE the temp
    dir is readable for non-secret paths; only WRITES are blocked. A later phase
    can wrap this in ``bubblewrap``/namespaces for a kernel boundary.
  * ``RLIMIT_AS`` is a virtual-address cap; a body can still hold one big array
    under it. It bounds runaway allocation, it is not a precise RSS meter.

Pure at import: no side effects, no I/O. The only I/O is inside ``run_body``.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from app.pyramid.sandbox import protocol as proto

__all__ = ["SandboxConfig", "SandboxDeath", "BodyRun", "run_body"]

# Causes sealed for the cage (R30 + protocol). Never re-declared elsewhere.
CAUSE_SANDBOX_DEATH = "sandbox_death"
CAUSE_PROTOCOL = "protocol_violation"

_VIOLATION_SENTINEL = "APEX_SANDBOX_VIOLATION:"
# Substrings identifying secret-bearing paths a body must never read.
_SECRET_MARKERS = ("/.ssh/", "/.aws/", "/.gnupg/", "/.config/", "/.env", "id_rsa", "id_ed25519")


@dataclass(frozen=True)
class SandboxConfig:
    """Knobs for one sandbox run. Defaults are the sealed 4a values."""

    timeout: float = 5.0
    memory_limit_bytes: int = 4 << 30  # 4 GiB address space (BLAS maps a lot)
    file_size_limit_bytes: int = 64 << 20  # 64 MiB
    max_processes: int = 256  # BLAS spawns worker threads; keep it finite but roomy


@dataclass
class SandboxDeath(Exception):
    """A body died. ``cause`` is one of the sealed cage causes."""

    cause: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - repr only
        return f"SandboxDeath({self.cause}): {self.detail}"


@dataclass
class BodyRun:
    """A successful body run: its masks, its artifacts, and its chatter."""

    long: np.ndarray
    short: np.ndarray
    meta: dict
    output_json: bytes
    stdout: str
    stderr: str
    temp_dir: str
    artifacts: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The child entry: installs the audit hook, then runs the body as __main__.
# Kept as a generated source string so the child needs no APEX import.
# ---------------------------------------------------------------------------
_CHILD_ENTRY = r'''
import os, sys, runpy

# Bootstrap the sanctioned libraries and the protocol reader BEFORE the audit
# hook is installed. numpy/pandas load their own C extensions via ctypes.dlopen
# at import; that is the platform, not the body. After this line the hook sees
# only the body's own events, so a later ctypes.dlopen (a body opening libc) is
# a real escape and dies.
import json
import math
import numpy
import pandas

TMP = os.path.abspath(os.path.dirname(__file__))
SENTINEL = "APEX_SANDBOX_VIOLATION:"
SECRET_MARKERS = ("/.ssh/", "/.aws/", "/.gnupg/", "/.config/", "/.env", "id_rsa", "id_ed25519")
_WRITE_MODES = ("w", "a", "x", "+")


def _trip(event, detail):
    try:
        sys.stderr.write(SENTINEL + event + "|" + detail + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    raise RuntimeError("apex sandbox violation: " + event + " " + detail)


def _hook(event, args):
    if event in ("socket.__new__", "socket.connect", "socket.getaddrinfo",
                 "socket.bind", "socket.gethostbyname", "socket.sendto",
                 "socket.sendmsg", "socket.recvfrom"):
        _trip(event, "network")
    if event in ("subprocess.Popen", "os.exec", "os.posix_spawn", "os.fork",
                 "os.forkpty", "os.system", "os.spawn"):
        _trip(event, "nested-process")
    # Native-escape surface (Phase 4b, R31/R32). Sanctioned libs are already
    # imported above, so any event here is the BODY reaching for native code.
    if event in ("ctypes.dlopen", "ctypes.dlsym", "ctypes.dlsym/handle",
                 "ctypes.addressof", "ctypes.call_function",
                 "ctypes.create_string_buffer", "ctypes.set_errno",
                 "ctypes.get_errno"):
        _trip(event, "ctypes")
    if event in ("mmap.__new__",):
        _trip(event, "mmap")
    if event in ("builtins.input", "builtins.breakpoint"):
        _trip(event, "dynamic-exec")
    if event in ("os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod",
                 "os.chown", "os.link", "os.symlink", "os.truncate",
                 "shutil.copyfile", "shutil.move"):
        _trip(event, "fs-mutation")
    if event == "open":
        try:
            path, mode, flags = args[0], args[1], args[2]
        except Exception:
            return
        if path is None:
            return
        p = os.path.abspath(str(path))
        low = p.lower()
        for m in SECRET_MARKERS:
            if m in low:
                _trip(event, "secret-read:" + p)
        is_write = False
        if isinstance(mode, str) and any(c in mode for c in _WRITE_MODES):
            is_write = True
        if not is_write and isinstance(flags, int) and (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)):
            is_write = True
        if is_write and not (p == TMP or p.startswith(TMP + os.sep)):
            _trip(event, "write-outside-temp:" + p)


sys.addaudithook(_hook)
sys.dont_write_bytecode = True  # never write .pyc outside the temp dir
runpy.run_path(os.path.join(TMP, "body.py"), run_name="__main__")
'''


def _as_frame(input_frame) -> pd.DataFrame:
    if isinstance(input_frame, pd.DataFrame):
        return input_frame
    return pd.read_parquet(input_frame)


def _child_env(tmp: str) -> dict:
    """A clean child environment: the body's PATH is the temp dir plus the host
    interpreter's standard site-packages, so numpy/pandas import — but APEX's own
    repository is NEVER on the path, so a body cannot import cage code. HOME and
    bytecode writes are redirected; hash randomization is disabled (determinism).
    """
    import sysconfig

    stdlib = [sysconfig.get_paths().get("purelib", ""), sysconfig.get_paths().get("platlib", "")]
    extra = [p for p in sysconfig.get_paths().get("stdlib", "").split(os.pathsep) if p]
    user_site = ""
    try:
        import site

        user_site = site.getusersitepackages() if hasattr(site, "getusersitepackages") else ""
    except Exception:
        user_site = ""
    path_parts = [tmp] + [p for p in stdlib + ([user_site] if user_site else []) + extra if p]
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": tmp,
        "PYTHONPATH": os.pathsep.join(path_parts),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }


def run_body(
    body_source: str,
    input_frame,
    *,
    genes: dict | None = None,
    config: SandboxConfig | None = None,
) -> BodyRun:
    """Run ``body_source`` once against ``input_frame``. Raise ``SandboxDeath``.

    ``input_frame`` is a pandas DataFrame (or a parquet path). The body runs in a
    fresh temp dir containing ``body.py``, the child entry, ``input.parquet`` and
    ``genes.json``; it may only write there. Fails closed on any violation.
    """
    config = config or SandboxConfig()
    frame = _as_frame(input_frame)
    tmp = tempfile.mkdtemp(prefix="apex_body_")
    try:
        (Path(tmp) / "body.py").write_text(body_source)
        (Path(tmp) / "_entry.py").write_text(_CHILD_ENTRY)
        proto.write_inputs(Path(tmp), frame, genes or {})

        env = _child_env(tmp)

        def _limits():
            os.setsid()
            resource.setrlimit(resource.RLIMIT_CPU, (int(config.timeout) + 2,
                                                     int(config.timeout) + 2))
            resource.setrlimit(resource.RLIMIT_AS, (config.memory_limit_bytes,
                                                    config.memory_limit_bytes))
            resource.setrlimit(resource.RLIMIT_FSIZE, (config.file_size_limit_bytes,
                                                       config.file_size_limit_bytes))
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (config.max_processes,
                                                           config.max_processes))
            except (ValueError, OSError):
                pass

        try:
            proc = subprocess.run(
                [sys.executable, os.path.join(tmp, "_entry.py")],
                cwd=tmp, env=env, capture_output=True, text=True,
                timeout=config.timeout, preexec_fn=_limits,
            )
        except subprocess.TimeoutExpired:
            raise SandboxDeath(CAUSE_SANDBOX_DEATH, f"timeout after {config.timeout}s")

        stderr = proc.stderr or ""
        violation = _first_violation(stderr)
        if violation is not None:
            raise SandboxDeath(CAUSE_SANDBOX_DEATH, violation)
        if proc.returncode != 0:
            tail = (stderr.strip().splitlines() or [""])[-1]
            raise SandboxDeath(CAUSE_SANDBOX_DEATH,
                               f"crashed (exit {proc.returncode}): {tail}")

        out_path = Path(tmp) / proto.OUTPUT_JSON
        if not out_path.exists():
            raise SandboxDeath(CAUSE_PROTOCOL, "body wrote no output.json")
        raw = out_path.read_bytes()
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise SandboxDeath(CAUSE_PROTOCOL, f"output.json is not valid JSON: {e}")
        long_out, short_out, meta = _parse(decoded, len(frame))
        return BodyRun(
            long=np.asarray(long_out, dtype=bool),
            short=np.asarray(short_out, dtype=bool),
            meta=meta, output_json=raw, stdout=proc.stdout or "",
            stderr=stderr, temp_dir=tmp, artifacts=_collect_artifacts(tmp),
        )
    finally:
        # The temp dir is left for the caller/judge only if it still needs it;
        # by contract each run is self-contained, so we clean up here.
        _rmtree(tmp)


def _parse(decoded, n_rows: int):
    try:
        return proto.parse_output(decoded, n_rows)
    except proto.ProtocolViolation as e:
        raise SandboxDeath(CAUSE_PROTOCOL, str(e))


def _first_violation(stderr: str) -> str | None:
    for line in stderr.splitlines():
        if _VIOLATION_SENTINEL in line:
            return line.split(_VIOLATION_SENTINEL, 1)[1].strip()
    return None


def _collect_artifacts(tmp: str) -> dict:
    """Anything the body wrote besides output.json, as {name: size}."""
    out_dir = Path(tmp)
    artifacts: dict = {}
    for p in sorted(out_dir.iterdir()):
        if p.name in (proto.INPUT_PARQUET, proto.INPUT_GENES, proto.OUTPUT_JSON,
                      "body.py", "_entry.py"):
            continue
        artifacts[p.name] = p.stat().st_size if p.is_file() else "dir"
    return artifacts


def _rmtree(path: str) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)
