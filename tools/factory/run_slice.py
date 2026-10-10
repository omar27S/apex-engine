"""THE SLICE RUN — one slice of a sliced tournament (Phase 7e, R67, TURBO).

Runs the factory over ONE slice's pair-subset and emits a slice artifact (a JSON
with the slice identity and its leaderboard rows). The burst workflow fires N of
these in parallel; the collector fuses them into ONE certificate.

Determinism: the slice identity is derived from ``(seed, index, pairs, salt)`` —
byte-identical to the coordinator's slice-set, so a collector can map an artifact
back to its slice.

Build Mode: inert offline batch.

Run::

    python -m tools.factory.run_slice --config configs/burst.json --index 0 --count 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.data import load_parquet  # noqa: E402
from app.core.pairs import PAIR_PIP  # noqa: E402
from app.factory import slices as slices_mod  # noqa: E402
from app.factory.factory import FactoryConfig, run_factory  # noqa: E402
from app.quant import frames as fr  # noqa: E402


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    obj = json.loads(Path(path).read_text())
    if not isinstance(obj, dict):
        raise ValueError(f"burst config {path!r} must be a JSON object")
    return obj


def _load_universe(data_dir: str, pairs, rows: int) -> dict:
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

    ap = argparse.ArgumentParser(description="Phase 7e slice run (R67)")
    ap.add_argument("--config", default=known.config)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--data", default=cfg.get("data", "data/history"))
    ap.add_argument("--pairs", default=cfg.get(
        "pairs", "EURUSD,GBPUSD,USDJPY,EURGBP,AUDJPY,CADJPY"))
    ap.add_argument("--population", type=int, default=int(cfg.get("population", 240)))
    ap.add_argument("--generations", type=int, default=int(cfg.get("generations", 3)))
    ap.add_argument("--elite", type=int, default=int(cfg.get("elite", 40)))
    ap.add_argument("--min-trades", type=int, default=int(cfg.get("min_trades", 30)))
    ap.add_argument("--seed", type=int, default=int(cfg.get("seed", 0)))
    ap.add_argument("--rows", type=int, default=int(cfg.get("rows", 20000)))
    ap.add_argument("--slice-salt", default=cfg.get("slice_salt", ""))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    all_pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    slice_set = slices_mod.make_slices(all_pairs, args.count, args.seed, args.slice_salt)
    if not (0 <= args.index < len(slice_set)):
        print(f"slice index {args.index} out of range (count {args.count})",
              file=sys.stderr)
        return 1
    spec = slice_set[args.index]
    universe = _load_universe(args.data, spec.pairs, args.rows)
    if not universe:
        print(f"slice {args.index} has no data — nothing to run", file=sys.stderr)
        return 1

    cfg_obj = FactoryConfig(
        pairs=tuple(sorted(universe)),
        population=args.population, generations=args.generations, elite=args.elite,
        min_trades=args.min_trades, seed=spec.seed, n_slices=1,
        slice_salt=args.slice_salt, island=f"turbo-slice{args.index}",
        screen_pair=sorted(universe)[0],
    )
    report = run_factory(universe, cfg_obj)
    out = args.out or f"slice_{args.index:02d}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "slice": spec.to_dict(),
        "config_hash": report["config_hash"],
        "trials": report["trials"],
        "population": args.population,
        "leaderboard": report["leaderboard_top"],
        "realms": report["realms"],
        "result_memory": report["result_memory"],
    }
    Path(out).write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({"slice_index": spec.index, "pairs": list(spec.pairs),
                      "trials": report["trials"],
                      "rows": len(payload["leaderboard"]),
                      "out": out}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
