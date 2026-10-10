"""THE SIGNED CERTIFICATES — the stress artefact becomes a sealed record (Phase 6a, R41).

Phase 5 wrote the RAMS stress artefact into ``data/history/`` (gitignored: a
regenerable scratch file, not an auditable record). R41 moves the verdict OUT of
scratch and INTO the repo: ``certificates/`` holds a SIGNED summary JSON — a
canonical form over the config digests, the survivor table, the verdicts, the
autopsy distribution, the run date and the git HEAD — plus its SHA-256. A verifier
recomputes the digest and validates the artefact in-suite.

WHAT IS SIGNED, AND WHAT THAT MEANS. There is no private key here and none is
pretended: the "signature" is a content-addressed SHA-256 over a canonical JSON
form. It proves the artefact has not been TAMPERED WITH and that it binds a
specific HEAD, not that a human authored it. Signing is therefore about
DETECTION, not authentication — and the honest name for it is a SEAL.

CANONICAL FORM (the ONLY thing hashed — this ordering is law):
    {
      "kind": str, "phase": int, "created_utc": str,
      "head": str, "runner": str,
      "digests": {...}, "summary": {...}, "survivors": [...],
      "autopsy": {...}, "verdicts": [...]
    }
Every list is sorted by a stable key before hashing, so the digest is
order-independent and reproducible on any machine.

Purity: pure functions + small file helpers. No I/O at import, no services.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "CERT_DIR",
    "canonical_bytes",
    "certificate_digest",
    "build_certificate",
    "sign_certificate",
    "write_certificate",
    "load_certificate",
    "verify_certificate",
    "head_hash",
    "ChainCheck",
    "verify_chain",
    "load_chain",
    "chain_next",
    "UNVERIFIED_HEAD",
    "CertificateError",
]


class CertificateError(ValueError):
    """A certificate failed verification (tampered, malformed, or HEAD-mismatched)."""


# Committed certificate directory, relative to the backend package root (the
# parent of ``app/``) — i.e. ``APEX/backend/certificates/``. The tools run with
# the backend root as their working directory, so this is the default they use.
CERT_DIR = "certificates"

# R44 (Phase 6b) — the loud sentinel for a certificate built outside a git
# checkout. Named so verifiers can flag it, never a silent "unknown".
UNVERIFIED_HEAD = "unverified-head"


def head_hash(repo: str | Path | None = None) -> str:
    """The current git HEAD (full sha) of the repo, or ``UNVERIFIED_HEAD``.

    R44 (Phase 6b) — FAIL-CLOSED. Outside a git checkout (or when git is
    unavailable) this returns the LOUD sentinel ``"unverified-head"`` instead of a
    silent ``"unknown"``. The certificate may still be BUILT (so an offline run is
    possible), but verifiers report the unverified state loudly.
    """
    cwd = str(repo) if repo is not None else None
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10, check=True,
        )
        head = out.stdout.strip()
        return head or UNVERIFIED_HEAD
    except (OSError, subprocess.SubprocessError):
        return UNVERIFIED_HEAD


def _canonical_view(cert: dict) -> dict:
    """The canonical, order-stable view that is actually HASHED.

    The ``signature`` field is EXCLUDED (it is the hash of everything else), and
    every list is sorted by a stable key so the digest does not depend on dict or
    list ordering.
    """
    def _sorted(rows, keys):
        return sorted(
            (dict(r) for r in rows),
            key=lambda r: tuple(str(r.get(k, "")) for k in keys),
        )

    return {
        "kind": str(cert.get("kind", "")),
        "phase": int(cert.get("phase", 0)),
        "chain_index": int(cert.get("chain_index", 0)),  # R44
        "prev_hash": str(cert.get("prev_hash", "")),      # R44
        "migrated_from": str(cert.get("migrated_from", "")),  # R44 provenance
        "created_utc": str(cert.get("created_utc", "")),
        "head": str(cert.get("head", "")),
        "runner": str(cert.get("runner", "")),
        "digests": dict(sorted((cert.get("digests", {}) or {}).items())),
        "summary": dict(sorted((cert.get("summary", {}) or {}).items())),
        "survivors": _sorted(cert.get("survivors", []) or [], ("signature",)),
        "autopsy": _sorted(cert.get("autopsy", []) or [], ("cause",)),
        "verdicts": _sorted(cert.get("verdicts", []) or [], ("signature",)),
        **({"ensemble_survival": _sorted(
            cert.get("ensemble_survival", []) or [], ("arm",))}
           if cert.get("ensemble_survival") else {}),
    }


def canonical_bytes(cert: dict) -> bytes:
    """The exact bytes hashed: canonical JSON, sorted keys, no whitespace."""
    return json.dumps(
        _canonical_view(cert), sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def certificate_digest(cert: dict) -> str:
    """SHA-256 over the canonical form (the certificate's SEAL)."""
    return hashlib.sha256(canonical_bytes(cert)).hexdigest()


def build_certificate(
    *,
    kind: str,
    phase: int,
    digests: dict,
    summary: dict,
    survivors: list | None = None,
    autopsy: list | None = None,
    verdicts: list | None = None,
    ensemble_survival: list | None = None,
    runner: str = "",
    repo: str | Path | None = None,
    created_utc: str | None = None,
    chain_index: int = 0,
    prev_hash: str = "",
    head: str | None = None,
) -> dict:
    """Assemble (and sign) a certificate. ``created_utc`` is injectable for tests.

    R44 (Phase 6b) — CHAIN. ``chain_index`` orders the certificate; ``prev_hash`` is
    the SEAL (``signature``) of the previous certificate in the chain (``""`` for
    the genesis at index 0). Both are INSIDE the canonical form, so tampering with
    certificate k invalidates k..N (each later seal folds in the previous).

    ``head`` overrides the git HEAD lookup (tests inject a fixed 40-hex sha so the
    seal is hermetic; production leaves it ``None``).
    """
    cert = {
        "kind": str(kind),
        "phase": int(phase),
        "chain_index": int(chain_index),
        "prev_hash": str(prev_hash),
        "created_utc": created_utc or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "head": head if head is not None else head_hash(repo),
        "runner": str(runner),
        "digests": dict(digests or {}),
        "summary": dict(summary or {}),
        "survivors": list(survivors or []),
        "autopsy": list(autopsy or []),
        "verdicts": list(verdicts or []),
    }
    if ensemble_survival:  # R55 — only emitted when present (chain migration safety)
        cert["ensemble_survival"] = [dict(r) for r in ensemble_survival]
    return sign_certificate(cert)


def sign_certificate(cert: dict) -> dict:
    """Attach/replace the ``signature`` (SHA-256 over the canonical form)."""
    out = dict(cert)
    out["signature"] = certificate_digest(out)
    return out


def write_certificate(cert: dict, path: str | Path) -> str:
    """Write a signed certificate to ``path`` (atomic) and return the digest.

    The certificate must already carry a valid signature; writing an unsigned (or
    tampered) certificate is a caller bug — fail-closed.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if "signature" not in cert:
        raise CertificateError("refusing to write an unsigned certificate")
    expected = certificate_digest(cert)
    if cert["signature"] != expected:
        raise CertificateError(
            f"refusing to write a tampered certificate: signature {cert['signature'][:16]}… "
            f"!= recomputed {expected[:16]}…"
        )
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(cert, indent=2, sort_keys=True, default=str) + "\n")
    tmp.replace(target)
    return expected


def load_certificate(path: str | Path) -> dict:
    """Read a certificate JSON; raises on a missing/unreadable/malformed file."""
    target = Path(path)
    if not target.exists():
        raise CertificateError(f"certificate not found: {target}")
    try:
        return json.loads(target.read_text())
    except (OSError, ValueError) as exc:
        raise CertificateError(f"unreadable certificate {target}: {exc}") from exc


@dataclass(frozen=True)
class CertificateCheck:
    ok: bool
    digest: str
    reasons: tuple[str, ...] = ()
    head_ok: bool = True
    unverified_head: bool = False

    def to_dict(self) -> dict:
        return {"ok": self.ok, "digest": self.digest,
                "reasons": list(self.reasons), "head_ok": self.head_ok,
                "unverified_head": self.unverified_head}


def verify_certificate(
    cert: dict,
    *,
    expect_head: str | None = None,
    repo: str | Path | None = None,
) -> CertificateCheck:
    """Recompute the seal and bind it to a HEAD (R41+R44).

    Fails (``ok=False`` with reasons) if the signature is missing or does not match
    the recomputed digest, if ``expect_head`` is supplied and the certificate's
    recorded HEAD differs, or — R44 fail-closed — if the certificate was built
    outside a git checkout (head is the ``UNVERIFIED_HEAD`` sentinel) and the caller
    did not explicitly accept that sentinel via ``expect_head``. A mismatch is a
    loud, listed reason — never a silent False.
    """
    reasons: list[str] = []
    sig = cert.get("signature")
    if not sig:
        reasons.append("missing signature")
        recomputed = certificate_digest(cert)
        return CertificateCheck(ok=False, digest=recomputed, reasons=tuple(reasons))

    recomputed = certificate_digest(cert)
    if sig != recomputed:
        reasons.append(
            f"signature mismatch: recorded {str(sig)[:16]}… != recomputed "
            f"{recomputed[:16]}… (tampered)"
        )

    found = str(cert.get("head", ""))
    head_ok = True
    unverified = False
    if expect_head is not None:
        if found != str(expect_head):
            head_ok = False
            reasons.append(
                f"HEAD mismatch: certificate binds {found[:12]}… but expected "
                f"{str(expect_head)[:12]}…"
            )
    elif found == UNVERIFIED_HEAD:
        # R44 — fail closed: an unverified HEAD is a loud state, never a silent pass.
        head_ok = False
        unverified = True
        reasons.append(
            "unverified-head: certificate was built outside a git checkout "
            "(no HEAD bound) — pass expect_head to accept it explicitly"
        )

    return CertificateCheck(
        ok=not reasons, digest=recomputed, reasons=tuple(reasons),
        head_ok=head_ok, unverified_head=unverified,
    )


@dataclass(frozen=True)
class ChainCheck:
    """R44 — the verdict of walking a whole certificate chain."""

    ok: bool
    length: int
    reasons: tuple[str, ...] = ()
    broken_at: tuple[int, ...] = ()
    digests: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"ok": self.ok, "length": self.length,
                "reasons": list(self.reasons), "broken_at": list(self.broken_at),
                "digests": list(self.digests)}


def verify_chain(
    certs: list[dict],
    *,
    expected_index: bool = True,
) -> ChainCheck:
    """R44 — verify a whole certificate chain, genesis first.

    Each certificate must (a) carry a valid seal, (b) carry ``chain_index`` equal to
    its position (when ``expected_index``), and (c) record the SEAL of its
    predecessor as ``prev_hash`` (``""`` at index 0). A break at position k is
    reported LOUDLY and invalidates every certificate from k onward (``broken_at``
    lists all of them), so tampering with certificate k breaks k..N.
    """
    reasons: list[str] = []
    broken_at: list[int] = []
    digests: list[str] = []
    prev_seal = None
    for i, cert in enumerate(certs):
        digests.append(str(cert.get("signature", "")))
        local: list[str] = []
        check = verify_certificate(cert)
        if not check.ok:
            local.extend(check.reasons)
        if expected_index and int(cert.get("chain_index", -1)) != i:
            local.append(
                f"chain index {cert.get('chain_index')} != position {i}"
            )
        if i == 0:
            if str(cert.get("prev_hash", "")) not in ("",):
                local.append("genesis must have an empty prev_hash")
        elif str(cert.get("prev_hash", "")) != str(prev_seal):
            local.append(
                f"prev_hash {str(cert.get('prev_hash',''))[:16]}… does not match "
                f"certificate {i-1}'s seal {str(prev_seal)[:16]}…"
            )
        if local:
            broken_at.append(i)
            reasons.extend(f"cert[{i}]: {r}" for r in local)
        prev_seal = cert.get("signature")

    if broken_at:
        # R44 — a break at k invalidates k..N: name them all.
        tail = [j for j in range(len(certs)) if j >= broken_at[0]]
        broken_at = sorted(set(broken_at) | set(tail))
    return ChainCheck(ok=not reasons, length=len(certs),
                      reasons=tuple(reasons), broken_at=tuple(broken_at),
                      digests=tuple(digests))


def load_chain(directory: str | Path = CERT_DIR) -> list[dict]:
    """Load every ``*.json`` certificate in ``directory`` ordered by ``chain_index``.

    Files are read, then sorted by ``(chain_index, filename)`` so an out-of-order
    write still verifies. A malformed file raises ``CertificateError`` (fail-closed).
    """
    root = Path(directory)
    if not root.exists():
        return []
    loaded = []
    for path in sorted(root.glob("*.json")):
        cert = load_certificate(path)
        cert.setdefault("_path", str(path))
        loaded.append(cert)
    loaded.sort(key=lambda c: (int(c.get("chain_index", 0)), str(c.get("_path", ""))))
    return loaded


def chain_next(directory: str | Path = CERT_DIR) -> tuple[int, str]:
    """The ``(chain_index, prev_hash)`` a NEW certificate should carry (R44).

    Reads the existing chain (empty -> genesis at index 0 with an empty prev_hash).
    """
    chain = load_chain(directory)
    if not chain:
        return 0, ""
    return len(chain), str(chain[-1].get("signature", ""))
