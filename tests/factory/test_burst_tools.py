"""Tests for the R67/R75 burst tools: slice fusion (fail-closed) and the budget
gate on the split engine.

These exercise the REAL tool entry points (the files are the contract), with tiny
synthetic slice artifacts — no market data, no sandbox.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.factory import budget as budget_mod          # noqa: E402
from app.factory import slices as slices_mod           # noqa: E402
from tools.factory import fuse_slices                   # noqa: E402
from tools.factory import split_engine                  # noqa: E402

PAIRS = "EURUSD,GBPUSD,USDJPY,EURGBP"


def _write_artifacts(directory: Path, count: int, seed: int, *, drop: int | None = None):
    spec_set = slices_mod.make_slices(PAIRS.split(","), count, seed, "")
    for spec in spec_set:
        if drop is not None and spec.index == drop:
            continue
        rows = [{"signature": f"s{spec.index}a", "family": "breakout",
                 "wilson_lb": 0.3 + spec.index * 0.01, "net_r": 1.0},
                {"signature": f"shared", "family": "mean_reversion",
                 "wilson_lb": 0.2 + spec.index * 0.01, "net_r": 0.5}]
        payload = {"slice": spec.to_dict(), "trials": 100 + spec.index,
                   "population": 50, "leaderboard": rows}
        (directory / f"slice_{spec.index:02d}.json").write_text(json.dumps(payload))
    return spec_set


def test_fuse_signs_one_certificate_when_all_slices_present(tmp_path):
    art_dir = tmp_path / "slices"
    art_dir.mkdir()
    _write_artifacts(art_dir, 2, 0)
    cert_dir = tmp_path / "certs"
    out = tmp_path / "fused.json"
    rc = fuse_slices.main([
        "--dir", str(art_dir), "--count", "2", "--seed", "0", "--pairs", PAIRS,
        "--cert-dir", str(cert_dir), "--out", str(out)])
    assert rc == 0
    report = json.loads(out.read_text())
    assert report["fused_size"] == 3          # s0a, s1a, and 'shared' (deduped)
    certs = list(cert_dir.glob("*.json"))
    assert len(certs) == 1
    # The certificate is signed and carries the slice-set digest.
    cert = json.loads(certs[0].read_text())
    assert cert.get("chain_index") == 0


def test_fuse_refuses_a_missing_slice(tmp_path):
    art_dir = tmp_path / "slices"
    art_dir.mkdir()
    _write_artifacts(art_dir, 3, 0, drop=1)   # slice 1 absent
    with pytest.raises(SystemExit) as exc:
        fuse_slices.main([
            "--dir", str(art_dir), "--count", "3", "--seed", "0", "--pairs", PAIRS,
            "--cert-dir", str(tmp_path / "certs"), "--out", str(tmp_path / "o.json")])
    assert "missing" in str(exc.value)


def test_fuse_refuses_a_foreign_seed_artifact(tmp_path):
    art_dir = tmp_path / "slices"
    art_dir.mkdir()
    _write_artifacts(art_dir, 2, 0)
    # Corrupt one artifact's slice seed so it no longer matches the slice-set.
    f = sorted(art_dir.glob("*.json"))[0]
    obj = json.loads(f.read_text())
    obj["slice"]["seed"] = 12345
    f.write_text(json.dumps(obj))
    with pytest.raises(SystemExit) as exc:
        fuse_slices.main([
            "--dir", str(art_dir), "--count", "2", "--seed", "0", "--pairs", PAIRS,
            "--cert-dir", str(tmp_path / "certs"), "--out", str(tmp_path / "o.json")])
    assert "mismatch" in str(exc.value)


def test_fuse_binds_the_certificate_to_the_head(tmp_path):
    art_dir = tmp_path / "slices"
    art_dir.mkdir()
    spec_set = slices_mod.make_slices(PAIRS.split(","), 2, 0, "")
    for spec in spec_set:
        payload = {"slice": spec.to_dict(), "trials": 10,
                   "head": "deadbeef", "leaderboard": [
                       {"signature": f"x{spec.index}", "family": "breakout",
                        "wilson_lb": 0.3, "net_r": 1.0}]}
        (art_dir / f"slice_{spec.index:02d}.json").write_text(json.dumps(payload))
    cert_dir = tmp_path / "certs"
    rc = fuse_slices.main([
        "--dir", str(art_dir), "--count", "2", "--seed", "0", "--pairs", PAIRS,
        "--head", "deadbeef", "--cert-dir", str(cert_dir),
        "--out", str(tmp_path / "o.json")])
    assert rc == 0
    cert = json.loads(next(cert_dir.glob("*.json")).read_text())
    assert cert["head"] == "deadbeef"     # DEBT-043: bound to the right commit


def test_fuse_refuses_slices_from_a_different_head(tmp_path):
    art_dir = tmp_path / "slices"
    art_dir.mkdir()
    spec_set = slices_mod.make_slices(PAIRS.split(","), 2, 0, "")
    for spec in spec_set:
        payload = {"slice": spec.to_dict(), "trials": 10, "head": "deadbeef",
                   "leaderboard": []}
        (art_dir / f"slice_{spec.index:02d}.json").write_text(json.dumps(payload))
    with pytest.raises(SystemExit) as exc:
        fuse_slices.main([
            "--dir", str(art_dir), "--count", "2", "--seed", "0", "--pairs", PAIRS,
            "--head", "WRONGHEAD", "--cert-dir", str(tmp_path / "certs"),
            "--out", str(tmp_path / "o.json")])
    assert "different head" in str(exc.value)


def test_split_engine_emits_slice_artifacts_with_the_head(tmp_path, monkeypatch):
    """DEBT-043: a burst stamps each slice artifact with the head it ran on, so
    the collector can bind and verify the certificate."""
    # Fake the heavy per-slice work and the pool: we assert the artifact contract.
    monkeypatch.setattr(split_engine, "_run_one",
                        lambda i, pairs, seed: {"slice_index": i, "pairs": list(pairs),
                                                "seed": seed, "head": "H",
                                                "trials": 5, "leaderboard": [],
                                                "realms": {"occupied": 0}})
    art = tmp_path / "arts"
    # A single-process pool keeps the test cheap.
    rc = split_engine.main(["--pairs", PAIRS, "--count", "2", "--jobs", "1",
                            "--head", "H", "--artifacts-dir", str(art),
                            "--population", "4", "--generations", "1",
                            "--out", str(tmp_path / "burst.json")])
    assert rc == 0
    files = sorted(art.glob("slice_*.json"))
    assert len(files) == 2
    assert all(json.loads(f.read_text())["head"] == "H" for f in files)


def test_split_engine_refuses_jobs_over_the_budget():
    over = budget_mod.TURBO_BUDGET.max_concurrent_jobs + 1
    rc = split_engine.main(["--pairs", PAIRS, "--count", "2", "--jobs", str(over),
                            "--out", "/tmp/should-not-write.json"])
    assert rc == 1


def test_split_engine_refuses_slices_over_the_budget():
    over = budget_mod.TURBO_BUDGET.max_concurrent_jobs + 1
    rc = split_engine.main(["--pairs", PAIRS, "--count", str(over), "--jobs", "1",
                            "--out", "/tmp/should-not-write.json"])
    assert rc == 1
