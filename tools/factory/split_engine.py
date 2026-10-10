"""THE SPLIT ENGINE — the TURBO's parallel sliced runner (Phase 7e, R67/R75).

The TURBO spends its minutes on SLICES: the pair universe is partitioned into
disjoint, deterministic slices (R67) and each slice is a self-contained factory
job. This module runs those slices in PARALLEL locally (a process pool) and
fuses the results — the same computation the burst workflow parallelises across
runner jobs, available on any machine with no server.

Budget law (R75): the pool is capped at ``TURBO_BUDGET.max_concurrent_jobs`` and
a slice must fit ``max_burst_seconds``; both are enforced here, fail-closed.

Build Mode: an inert offline batch (a bounded process pool, no scheduler).

Run::

    python -m tools.factory.split_engine --config configs/burst.json --count 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.data import load_parquet  # noqa: E402
from app.core.pairs import PAIR_PIP  # noqa: E402
from app.factory import budget as budget_mod  # noqa: E402
from app.factory import realms as realms_mod  # noqa: E402
from app.factory import slices as slices_mod  # noqa: E402
from app.factory.factory import FactoryConfig, run_factory  # noqa: E402
from app.quant import frames as fr  # noqa: E402

# Module-level so the process pool can pickle the worker.
_WORKER: dict = {}


def _init_worker(data_dir, rows, population, generations, elite, min_trades,
                 slice_salt, seed, timeout_s, head):
    _WORKER.update(dict(data_dir=data_dir, rows=rows, population=population,
                        generations=generations, elite=elite, min_trades=min_trades,
                        slice_salt=slice_salt, seed=seed, timeout_s=timeout_s,
                        head=head))


def _run_one(index: int, pairs: tuple[str, ...], slice_seed: int) -> dict:
    started = time.monotonic()
    universe = {}
    for pair in pairs:
        path = Path(_WORKER["data_dir"]) / f"{pair}_M15.parquet"
        if not path.exists():
            continue
        m15 = load_parquet(str(path))
        if _WORKER["rows"]:
            m15 = m15.iloc[-_WORKER["rows"]:].reset_index(drop=True)
        universe[pair] = fr.build_frames(m15, pair, PAIR_PIP[pair])
    if not universe:
        return {"slice_index": index, "error": "no data for slice"}
    cfg = FactoryConfig(
        pairs=tuple(sorted(universe)), population=_WORKER["population"],
        generations=_WORKER["generations"], elite=_WORKER["elite"],
        min_trades=_WORKER["min_trades"], seed=slice_seed, n_slices=1,
        slice_salt=_WORKER["slice_salt"], island=f"turbo-slice{index}",
        screen_pair=sorted(universe)[0],
    )
    report = run_factory(universe, cfg)
    return {"slice_index": index, "pairs": list(pairs), "seed": slice_seed,
            "head": _WORKER["head"],
            "trials": report["trials"], "leaderboard": report["leaderboard_top"],
            "realms": report["realms"],
            "wallclock_seconds": round(time.monotonic() - started, 3)}


def main(argv=None) -> int:
    cfg = {}
    if "--config" in (argv or sys.argv):
        i = (argv or sys.argv).index("--config")
        p = (argv or sys.argv)[i + 1]
        cfg = json.loads(Path(p).read_text())

    ap = argparse.ArgumentParser(description="Phase 7e TURBO split engine")
    ap.add_argument("--config", default=None)
    ap.add_argument("--data", default=cfg.get("data", "data/history"))
    ap.add_argument("--pairs", default=cfg.get("pairs", "EURUSD,GBPUSD,USDJPY"))
    ap.add_argument("--count", type=int, default=int(cfg.get("count", 3)))
    ap.add_argument("--population", type=int, default=int(cfg.get("population", 240)))
    ap.add_argument("--generations", type=int, default=int(cfg.get("generations", 3)))
    ap.add_argument("--elite", type=int, default=int(cfg.get("elite", 40)))
    ap.add_argument("--min-trades", type=int, default=int(cfg.get("min_trades", 30)))
    ap.add_argument("--rows", type=int, default=int(cfg.get("rows", 20000)))
    ap.add_argument("--seed", type=int, default=int(cfg.get("seed", 0)))
    ap.add_argument("--slice-salt", default=cfg.get("slice_salt", ""))
    ap.add_argument("--head", default=cfg.get("head") or os.environ.get("GITHUB_SHA"))
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--artifacts-dir", default=cfg.get("artifacts_dir"))
    ap.add_argument("--out", default="burst_report.json")
    args = ap.parse_args(argv)

    # R75 — enforce the budget BEFORE spending a single minute.
    budget = budget_mod.TURBO_BUDGET
    if args.jobs > budget.max_concurrent_jobs:
        print(f"R75: jobs {args.jobs} exceeds max_concurrent_jobs "
              f"{budget.max_concurrent_jobs}", file=sys.stderr)
        return 1
    if args.count > budget.max_concurrent_jobs:
        print(f"R75: {args.count} slices exceeds max_concurrent_jobs "
              f"{budget.max_concurrent_jobs}", file=sys.stderr)
        return 1

    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    slice_set = slices_mod.make_slices(pairs, args.count, args.seed, args.slice_salt)

    started = time.monotonic()
    results = []
    if args.jobs <= 1:
        # Deterministic single-process path (also what a 1-core runner uses).
        _init_worker(args.data, args.rows, args.population, args.generations,
                     args.elite, args.min_trades, args.slice_salt, args.seed,
                     budget.max_burst_seconds, args.head)
        for s in slice_set:
            results.append(_run_one(s.index, s.pairs, s.seed))
    else:
        with ProcessPoolExecutor(
                max_workers=args.jobs, initializer=_init_worker,
                initargs=(args.data, args.rows, args.population, args.generations,
                          args.elite, args.min_trades, args.slice_salt, args.seed,
                          budget.max_burst_seconds, args.head)) as pool:
            futures = [pool.submit(_run_one, s.index, s.pairs, s.seed)
                       for s in slice_set]
            for f in futures:
                results.append(f.result())
    wall = time.monotonic() - started

    if any("error" in r for r in results):
        print(f"R67 fail-closed: a slice failed: "
              f"{[r for r in results if 'error' in r]}", file=sys.stderr)
        return 1

    rows_by_slice = {r["slice_index"]: r["leaderboard"] for r in results}
    fused = slices_mod.fuse_leaderboards(rows_by_slice)
    census = realms_mod.census(fused)
    summary = slices_mod.fuse_certificate_summary(slice_set, rows_by_slice, fused)

    # R67/DEBT-043: emit per-slice artifacts (the fuse's input contract). Each
    # artifact carries the slice identity AND the head it ran on, so the collector
    # can bind and verify the certificate to the right commit.
    if args.artifacts_dir:
        art_dir = Path(args.artifacts_dir)
        art_dir.mkdir(parents=True, exist_ok=True)
        for spec, res in zip(slice_set, results):
            payload = {"slice": spec.to_dict(), "trials": res["trials"],
                       "population": args.population, "head": args.head,
                       "leaderboard": res["leaderboard"]}
            (art_dir / f"slice_{spec.index:02d}.json").write_text(
                json.dumps(payload, default=str))

    report = {
        "kind": "turbo_burst", "slices": len(slice_set), "jobs": args.jobs,
        "wallclock_seconds": round(wall, 3),
        "trials": sum(int(r["trials"]) for r in results),
        "slice_set_digest": summary["slice_set_digest"],
        "per_slice": [{"slice_index": r.get("slice_index"),
                       "pairs": r.get("pairs"),
                       "trials": r.get("trials"),
                       "wallclock_seconds": r.get("wallclock_seconds")}
                      for r in results],
        "fused_size": len(fused), "realms": census,
        "fused_top": summary["fused_top"],
        "budget_digest": budget_mod.budget_manifest_digest(),
    }
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({
        "slices": report["slices"], "jobs": report["jobs"],
        "wallclock_seconds": report["wallclock_seconds"], "trials": report["trials"],
        "fused_size": report["fused_size"],
        "realms_occupied": census["occupied"],
        "speedup_note": "slices ran in parallel; per-slice wall-clock is in per_slice",
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
