"""THE FACTORY RUN — one bounded factory job (Phase 7e, R66-R73).

Runs the twelve-lever factory over a pair universe, writes the honest report,
appends one factory-ledger record (R66), and (optionally) seals the run into a
certificate. Config-driven, deterministic under ``--seed``.

Build Mode: an inert offline batch — no server, no scheduler, no loop beyond the
bounded population x generations.

Run::

    python -m tools.factory.run_factory --config configs/factory_shift.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.data import load_parquet  # noqa: E402
from app.core.pairs import PAIR_PIP  # noqa: E402
from app.factory import ledger as ledger_mod  # noqa: E402
from app.factory.factory import FactoryConfig, run_factory  # noqa: E402
from app.quant import frames as fr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    obj = json.loads(Path(path).read_text())
    if not isinstance(obj, dict):
        raise ValueError(f"factory config {path!r} must be a JSON object")
    return obj


def _load_universe(data_dir: str, pairs: list[str], rows: int) -> dict:
    universe = {}
    for pair in pairs:
        path = Path(data_dir) / f"{pair}_M15.parquet"
        if not path.exists():
            print(f"  !! no tape for {pair}", file=sys.stderr)
            continue
        m15 = load_parquet(str(path))
        if rows:
            m15 = m15.iloc[-rows:].reset_index(drop=True)
        universe[pair] = fr.build_frames(m15, pair, PAIR_PIP[pair])
    return universe


def main(argv=None) -> int:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    known, _ = pre.parse_known_args(argv)
    cfg = _load_config(known.config) if known.config else {}

    ap = argparse.ArgumentParser(description="Phase 7e factory run")
    ap.add_argument("--config", default=known.config)
    ap.add_argument("--data", default=cfg.get("data", "data/history"))
    ap.add_argument("--pairs", default=cfg.get("pairs", "EURUSD,GBPUSD,USDJPY"))
    ap.add_argument("--population", type=int, default=int(cfg.get("population", 240)))
    ap.add_argument("--generations", type=int, default=int(cfg.get("generations", 3)))
    ap.add_argument("--elite", type=int, default=int(cfg.get("elite", 40)))
    ap.add_argument("--min-trades", type=int, default=int(cfg.get("min_trades", 30)))
    ap.add_argument("--seed", type=int, default=int(cfg.get("seed", 0)))
    ap.add_argument("--rows", type=int, default=int(cfg.get("rows", 20000)))
    ap.add_argument("--n-slices", type=int, default=int(cfg.get("n_slices", 3)))
    ap.add_argument("--slice-salt", default=cfg.get("slice_salt", ""))
    ap.add_argument("--ensemble-quota", type=float,
                    default=float(cfg.get("ensemble_quota", 0.25)))
    ap.add_argument("--island", default=cfg.get("island", "heart"))
    ap.add_argument("--screen-pair", default=cfg.get("screen_pair", ""))
    ap.add_argument("--out", default=cfg.get("out", "data/history/.factory_run.json"))
    ap.add_argument("--ledger", default=cfg.get("ledger", "factory_ledger.jsonl"))
    ap.add_argument("--no-polish", dest="polish", action="store_false",
                    default=bool(cfg.get("polish", True)))
    ap.add_argument("--no-cma", dest="cma", action="store_false",
                    default=bool(cfg.get("cma", True)))
    ap.add_argument("--no-staircase", dest="staircase", action="store_false",
                    default=bool(cfg.get("staircase", True)))
    args = ap.parse_args(argv)

    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    universe = _load_universe(args.data, pairs, args.rows)
    if not universe:
        print("no data — nothing to run", file=sys.stderr)
        return 1

    cfg_obj = FactoryConfig(
        pairs=tuple(sorted(universe)),
        population=args.population, generations=args.generations, elite=args.elite,
        min_trades=args.min_trades, seed=args.seed,
        ensemble_quota=args.ensemble_quota, n_slices=args.n_slices,
        slice_salt=args.slice_salt, polish=bool(args.polish), cma=bool(args.cma),
        staircase=bool(args.staircase), screen_pair=args.screen_pair,
        island=args.island,
    )
    report = run_factory(universe, cfg_obj)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))

    # R66 — append the honest factory-ledger record.
    date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    rec = ledger_mod.FactoryRecord(
        date=date, machine=args.island, job=cfg.get("job", "factory-run"),
        trials=int(report["trials"]),
        machine_seconds=float(report["wallclock_seconds"]),
        cache_hits=int(report["result_memory"]["hits"]),
        cache_misses=int(report["result_memory"]["misses"]),
        realms_occupied=int(report["realms"]["occupied"]),
        note=f"pairs={len(universe)} pop={args.population}",
    )
    ledger_mod.append([], rec, args.ledger)

    print(json.dumps({
        "machine": args.island, "trials": report["trials"],
        "genomes_scored": report["genomes_scored"],
        "wallclock_seconds": report["wallclock_seconds"],
        "staircase": report["staircase"],
        "result_memory": report["result_memory"],
        "polish": report["polish"],
        "cma_refined": report["cma"]["refined"],
        "entropy_trend": report["entropy_trend"],
        "realms": {"occupied": report["realms"]["occupied"],
                   "by_family_group": report["realms"]["by_family_group"]},
        "champions": len(report["champions"]),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
