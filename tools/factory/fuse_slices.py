"""THE FUSE — merge slice artifacts into ONE certificate (Phase 7e, R67).

The collector job runs on the VAULT (private). It reads every slice artifact the
TURBO jobs produced, verifies each slice's identity against the deterministic
slice-set, fuses the leaderboards (dedup by signature, keep the best), computes
the realm census, and signs ONE certificate appended to the chain (R44).

Fail-closed: a missing slice, an artifact whose slice identity does not match the
expected slice-set, or an artifact from a foreign seed is REFUSED — a partial
burst never silently signs a certificate that pretends to be complete.

Build Mode: inert offline batch.

Run::

    python -m tools.factory.fuse_slices --dir slices/ --count 3 --seed 0 \
        --pairs EURUSD,GBPUSD,... --cert-dir certificates
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core import certificates as certs  # noqa: E402
from app.factory import realms as realms_mod  # noqa: E402
from app.factory import slices as slices_mod  # noqa: E402


def _read_artifacts(directory: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            obj = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        idx = obj.get("slice", {}).get("index")
        if idx is None:
            continue
        out[int(idx)] = obj
    return out


def main(argv=None) -> int:
    cfg = {}
    if "--config" in (argv or sys.argv):
        i = (argv or sys.argv).index("--config")
        cfg = json.loads(Path((argv or sys.argv)[i + 1]).read_text())

    ap = argparse.ArgumentParser(description="Phase 7e slice fusion (R67)")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--config", default=None,
                    help="share the burst config so salt/seed/pairs match exactly")
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--seed", type=int, default=int(cfg.get("seed", 0)))
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--slice-salt", default=cfg.get("slice_salt", ""))
    ap.add_argument("--cert-dir", default="certificates")
    ap.add_argument("--head", default=None)
    ap.add_argument("--out", default="fused_report.json")
    args = ap.parse_args(argv)

    all_pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    expected = slices_mod.make_slices(all_pairs, args.count, args.seed, args.slice_salt)
    expected_by_index = {s.index: s for s in expected}

    artifacts = _read_artifacts(Path(args.dir))
    missing = [s.index for s in expected if s.index not in artifacts]
    if missing:
        raise SystemExit(
            f"R67 fail-closed: slices {missing} are missing — refusing to sign a "
            f"partial certificate"
        )
    for idx, art in artifacts.items():
        spec = expected_by_index.get(idx)
        if spec is None:
            raise SystemExit(f"R67 fail-closed: unexpected slice index {idx}")
        got_pairs = tuple(sorted(art.get("slice", {}).get("pairs", [])))
        if got_pairs != tuple(sorted(spec.pairs)) or int(art.get("slice", {}).get("seed")) != spec.seed:
            raise SystemExit(
                f"R67 fail-closed: slice {idx} identity mismatch "
                f"(got pairs={got_pairs} seed={art.get('slice',{}).get('seed')}, "
                f"expected pairs={spec.pairs} seed={spec.seed})"
            )

    # DEBT-043: bind the certificate to the RIGHT commit. Every slice must have
    # run on the same head; a mismatch (or a missing head when one is claimed) is
    # refused — a burst from two different commits never signs one certificate.
    if args.head is not None:
        heads = {idx: art.get("head") for idx, art in artifacts.items()}
        offenders = {i: h for i, h in heads.items() if h != args.head}
        if offenders:
            raise SystemExit(
                f"R67/DEBT-043 fail-closed: slices ran on a different head than "
                f"{args.head!r}: {offenders} — refusing to sign"
            )

    rows_by_slice = {idx: artifacts[idx].get("leaderboard", []) for idx in artifacts}
    fused = slices_mod.fuse_leaderboards(rows_by_slice)
    census = realms_mod.census(fused)
    summary = slices_mod.fuse_certificate_summary(expected, rows_by_slice, fused)

    cert_dir = Path(args.cert_dir)
    chain_index, prev_hash = certs.chain_next(cert_dir)
    cert = certs.build_certificate(
        kind="sliced_tournament",
        phase=7,
        digests={
            "slice_set": summary["slice_set_digest"],
        },
        summary={
            "slices": len(expected),
            "fused_size": len(fused),
            "realms_occupied": census["occupied"],
            "trials": sum(int(a.get("trials", 0)) for a in artifacts.values()),
            "population": artifacts.get(0, {}).get("population"),
        },
        survivors=[{
            "signature": r.get("signature", ""), "family": r.get("family", ""),
            "wilson_lb": r.get("wilson_lb"), "net_r": r.get("net_r"),
            "trades": r.get("trades"),
        } for r in fused],
        runner="tools/factory/fuse_slices.py",
        chain_index=chain_index, prev_hash=prev_hash, head=args.head,
    )
    cert_path = cert_dir / f"rotation_night_{chain_index:03d}.json"
    digest = certs.write_certificate(cert, cert_path)

    report = {
        "kind": "sliced_tournament",
        "slices": summary,
        "fused_size": len(fused),
        "realms": census,
        "fused_top": summary["fused_top"],
        "trials": sum(int(a.get("trials", 0)) for a in artifacts.values()),
        "certificate": str(cert_path),
        "certificate_digest": digest,
        "chain_index": chain_index,
        "chain_prev_hash": prev_hash,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({
        "slices": len(expected), "fused_size": len(fused),
        "realms_occupied": census["occupied"], "trials": report["trials"],
        "certificate": str(cert_path), "chain_index": chain_index,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
