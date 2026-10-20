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
from app.factory import dna as dna_mod  # noqa: E402
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


def _load_directed(path: str | None) -> tuple:
    """Load the Dragon's directed-mutation hypotheses (honest: absent -> empty).

    The artifact is committed by the night shift (``directed_mutations.json``); a
    missing or unreadable file yields ``()`` so the factory evolves blind as before.
    """
    if not path:
        return ()
    p = Path(path)
    if not p.exists():
        return ()
    try:
        payload = json.loads(p.read_text())
    except (OSError, ValueError):
        return ()
    hyps = payload.get("hypotheses") if isinstance(payload, dict) else None
    return tuple(hyps or ())


def _load_gating(state_path: str | None) -> dict:
    """DEBT-060 — read the Watchtower's regime gating from the civilization state.

    The state's ``regime.gating`` is ``pair -> {"paused": [group], "active": [group]}``.
    Honest: a missing/unreadable state (or no gating) yields ``{}`` so the factory
    evolves ungated -- exactly as before the Watchtower reconfigured anything.
    """
    if not state_path:
        return {}
    p = Path(state_path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text())
    except (OSError, ValueError):
        return {}
    gating = ((payload.get("regime") or {}).get("gating")
              if isinstance(payload, dict) else None)
    return dict(gating) if isinstance(gating, dict) else {}


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
    ap.add_argument("--no-polish", dest="polish", action="store_false",
                    default=bool(cfg.get("polish", True)))
    ap.add_argument("--no-cma", dest="cma", action="store_false",
                    default=bool(cfg.get("cma", True)))
    ap.add_argument("--no-staircase", dest="staircase", action="store_false",
                    default=bool(cfg.get("staircase", True)))
    ap.add_argument("--directed", default=cfg.get("directed", "directed_mutations.json"),
                    help="THE DRAGON's directed-mutation hypotheses (absent -> blind)")
    ap.add_argument("--state", default=cfg.get("state", "civilization_state.json"),
                    help="DEBT-060: the state whose regime.gating the factory honours")
    ap.add_argument("--layers-quota", type=float,
                    default=float(cfg.get("layers_quota", 0.0)),
                    help="JUMP 7: the multi-layer population share")
    ap.add_argument("--ledger", default=cfg.get("ledger", "factory_ledger.jsonl"),
                    help="R66: the honest band ledger this run appends to")
    args = ap.parse_args(argv)

    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    universe = _load_universe(args.data, pairs, args.rows)
    if not universe:
        print("no data — nothing to run", file=sys.stderr)
        return 1

    cfg_obj = FactoryConfig(
        pairs=tuple(sorted(universe)),
        directed=_load_directed(args.directed),
        regime_gating=_load_gating(args.state),
        layers_quota=args.layers_quota,
        population=args.population, generations=args.generations, elite=args.elite,
        min_trades=args.min_trades, seed=args.seed,
        ensemble_quota=args.ensemble_quota, n_slices=args.n_slices,
        slice_salt=args.slice_salt, polish=bool(args.polish), cma=bool(args.cma),
        staircase=bool(args.staircase), screen_pair=args.screen_pair,
        island=args.island,
        rotate_seed=bool(cfg.get("rotate_seed", False)),
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
        note=(f"pairs={len(universe)} pop={args.population}"
              f" seed={report.get('seed')}"
              f" champ={report.get('champions_injected', 0)}"
              f" {report.get('dna', {}).get('seal') or dna_mod.seal()}"),
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
        "directed": report.get("directed"),
        "regime_gating": report.get("regime_gating"),
        "entropy_trend": report["entropy_trend"],
        "realms": {"occupied": report["realms"]["occupied"],
                   "by_family_group": report["realms"]["by_family_group"]},
        "champions": len(report["champions"]),
        "dna": report.get("dna"),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
