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

from app.state import atomic  # noqa: E402
from app.core.data import load_parquet  # noqa: E402
from app.core.pairs import PAIR_PIP  # noqa: E402
from app.factory import ledger as ledger_mod  # noqa: E402
from app.factory import oath as oath_mod  # noqa: E402
from app.factory import dna as dna_mod  # noqa: E402
from app.factory.factory import FactoryConfig, run_factory  # noqa: E402
from app.factory.islands import ISLAND_WHEEL  # noqa: E402
from app.quant import frames as fr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# R98 — THE ISLAND WHEEL. The architecture declares three islands (heart, turbo,
# vault -- 240 bodies x 3 = the 720 the Boss was promised); the shift config
# now says "auto" and the wheel takes its turn per shift: every island breeds
# on its own pantry, no island starved, the migration (R68) carries genes
# across, and the diaspora (R99) feeds each island with the others' best. The
# rotation key is the ledger's honest line count -- the SAME key the rotating
# seed (R92) uses, so island and seed never disagree about which shift this is.
# (The tuple itself is canonical in app.factory.islands; the name stays
# importable here for the wheel's own tests.)


def _derived_seed(base_seed: int, ledger_path: str) -> int:
    """The wheel's own arithmetic, mirrored BEFORE the run (R108).

    ``run_factory`` derives ``shift_seed = (base + 7919 * (n + 1)) % 2^30``
    from the ledger's line count; the witness guard must derive the SAME
    number to recognise a turn that already happened. The formula lives in
    one spirit, two places -- a comment here binds them (the day they
    disagree, the test that feeds both the same ledger will catch it).
    """
    try:
        p = Path(ledger_path)
        n = sum(1 for _ in p.open()) if p.exists() else 0
    except OSError:
        n = 0
    return (int(base_seed) + 7919 * (n + 1)) % (1 << 30)


def _wheel_already_turned(ledger_path: str, *, island: str, seed: int,
                          date: str) -> tuple[bool, str]:
    """R108 -- THE WITNESS, NOT A RIVAL: has this exact turn already run?

    The wound this guard closes (2026-10-20, 17:16 UTC): a CI push and the
    heart's timer both derived the same wheel position (same line count ->
    same island, same seed) and ran the SAME 8-minute turn twice, writing
    two identical-seed rows the guardian then had to declare. Same island +
    same seed + same date in the ledger's LAST line means the wheel has
    already turned TODAY -- a re-run would be deterministic déjà vu, not
    new evidence. The honest answer is to WITNESS (exit clean, speak the
    reason), never to burn the machine on a copy of itself.

    Only the LAST line is consulted: an older duplicate is history the
    append-only ledger keeps forever, never rewrites.
    """
    try:
        p = Path(ledger_path)
        if not p.exists():
            return False, ""
        with p.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            window = bytearray()
            step = 4096
            while end > 0 and window.count(b"\n") < 3:
                start = max(0, end - step)
                fh.seek(start)
                window = bytearray(fh.read(end - start)) + window
                end = start
            lines = [ln for ln in window.decode("utf-8", "replace").splitlines()
                     if ln.strip()]
            if not lines:
                return False, ""
            last = json.loads(lines[-1])
        note = str(last.get("note") or "")
        if (str(last.get("machine") or "") == str(island)
                and str(last.get("date") or "") == str(date)
                and f"seed={seed}" in note):
            return True, (f"the wheel already turned today: island={island} "
                          f"seed={seed} date={date} (ledger line: "
                          f"{note[:120]})")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False, ""
    return False, ""


def _resolve_island(spec: str, ledger_path: str) -> str:
    """Resolve the shift's island: 'auto' rides the wheel, a name is the law.

    Deterministic and measurable: the wheel advances one island per ledger
    line (a missing ledger starts at heart). An unknown island name passes
    through untouched -- the caller's word is law (the ledger's validator
    remains the gatekeeper of the known world).
    """
    spec = str(spec or "heart").strip().lower()
    if spec != "auto":
        return spec
    try:
        p = Path(ledger_path)
        n = sum(1 for _ in p.open()) if p.exists() else 0
    except OSError:
        n = 0
    return ISLAND_WHEEL[n % len(ISLAND_WHEEL)]


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


def _stitch_live_edge(m15, tape_rows: list[dict] | None):
    """R120 -- THE LIVING UNIVERSE: fold the tape's bars beyond the parquet
    edge onto the frame, in memory (no writes, no contention with the
    historian). The tape only rides BEYOND the deep edge -- the parquet
    always wins a collision (the historian's own Law 1). Malformed bars are
    refused alone, never fatal. Returns (frame, bars_added)."""
    if not tape_rows:
        return m15, 0
    edge = int(m15["ts"].iloc[-1]) if len(m15) else 0
    from app.data_supply.historian import _valid_apex_bar
    fresh = [b for b in tape_rows
             if _valid_apex_bar(b) and int(b["ts"]) > edge]
    if not fresh:
        return m15, 0
    import pandas as _pd
    stitched = _pd.concat([m15, _pd.DataFrame(fresh)], ignore_index=True)
    stitched = stitched.sort_values("ts", kind="stable").reset_index(drop=True)
    return stitched, len(fresh)


def _load_universe(data_dir: str, pairs: list[str], rows: int, *,
                   tape_path: str | None = None) -> dict:
    """The factory's universe: the deep parquet tail, and -- when the live
    tape is offered (R120) -- the tape's bars beyond it, so every shift
    evolves on the market through the LAST CLOSED BAR. Read-only by law:
    the parquet itself is healed only by the historian, never by a shift."""
    tape_bars: dict[str, list[dict]] = {}
    if tape_path:
        try:
            from app.data_supply.historian import read_tape
            per_symbol, _torn, _non_bar = read_tape(tape_path)
            tape_bars = per_symbol
        except Exception as _exc:  # fail-open: a dead tape is a fossil frame
            print(f"  [stitch] tape unreadable, evolving on the deep frame "
                  f"alone (fail-open): {_exc}", file=sys.stderr)
    universe = {}
    stitched_total = 0
    for pair in pairs:
        path = Path(data_dir) / f"{pair}_M15.parquet"
        if not path.exists():
            print(f"  !! no tape for {pair}", file=sys.stderr)
            continue
        m15 = load_parquet(str(path))
        if rows:
            m15 = m15.iloc[-rows:].reset_index(drop=True)
        if pair in tape_bars:
            m15, added = _stitch_live_edge(m15, tape_bars[pair])
            stitched_total += added
        universe[pair] = fr.build_frames(m15, pair, PAIR_PIP[pair])
    if tape_bars:
        print(f"  [stitch] {stitched_total} live bars folded onto the deep "
              f"frame across {len(universe)} pairs")
    return universe


def main(argv=None) -> int:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    known, _ = pre.parse_known_args(argv)
    cfg = _load_config(known.config) if known.config else {}

    # THE ANTI-BUG GUARDIAN (R102) -- the round of the wards BEFORE the turn:
    # a sick state is healed (quarantine + restore, reversibly) before the
    # evolution leans on it. Best-effort BY LAW: the guardian is a passenger,
    # never a gate -- its failures are recorded and the turn goes on (a
    # physician who stops the heart to take a pulse is not a physician).
    try:
        from app.factory import anti_bug as guardian
        _round = guardian.sweep(".", write=True)
        print("[guardian] " + guardian.voice(_round), flush=True)
    except Exception as _exc:  # fail-open: the turn never waits for its doctor
        print(f"[guardian] round skipped (fail-open): {_exc}", flush=True)

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
    ap.add_argument("--island", default=cfg.get("island", "heart"),
                    help="the breeding island this shift -- a name, or 'auto' "
                         "to ride the R98 island wheel (heart -> turbo -> "
                         "vault, one island per ledger line)")
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
    ap.add_argument("--champion-seats", type=int,
                    default=int(cfg.get("champion_seats", 9)),
                    help="R96: the pantry's breadth -- distinct-realm "
                         "champions per shift")
    ap.add_argument("--screen-survival", type=float,
                    default=float(cfg.get("screen_survival", 0.6)),
                    help="R97: the living funnel -- the share of the pool round "
                         "one lets through to the full judgement (0, 1]")
    ap.add_argument("--ledger", default=cfg.get("ledger", "factory_ledger.jsonl"),
                    help="R66: the honest band ledger this run appends to")
    ap.add_argument("--tape", default=cfg.get("tape", "data/live/tape_m15.jsonl"),
                    help="R120: the live M15 tape stitched onto the deep "
                         "frame (empty string = the fossil frame, CI-honest)")
    ap.add_argument("--probation-rows", type=int,
                    default=int(cfg.get("probation_rows", 0)),
                    help="R100: the most recent rows every pantry champion is "
                         "re-measured on before the pantry remembers it "
                         "(0 = no probation this shift)")
    ap.add_argument("--force-turn", dest="force_turn", action="store_true",
                    default=False,
                    help="R108: run even when the wheel already turned this "
                         "island+seed today (manual interventions only; the "
                         "honest default is to witness, not to rival)")
    args = ap.parse_args(argv)

    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]

    # R98 — the island wheel: 'auto' becomes a real island before anything else.
    island = _resolve_island(args.island, args.ledger)

    # R108 -- THE WITNESS GUARD: before the machine burns a single second on
    # data it will re-derive identically, ask the ledger whether THIS turn
    # (island + derived seed + today) already ran. The CI push that lands
    # minutes after the heart's beat used to re-run the same 8-minute turn
    # and write a duplicate-seed row; now it WITNESSES -- clean exit, spoken
    # reason, zero new evidence pretended. --force-turn escapes (a manual
    # intervention is the operator's word, and the operator's word is law).
    if not args.force_turn:
        _witness_seed = _derived_seed(args.seed, args.ledger)
        _today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
        _turned, _reason = _wheel_already_turned(
            args.ledger, island=island, seed=_witness_seed, date=_today)
        if _turned:
            print(json.dumps({
                "skipped": True, "law": "R108 -- the witness, not a rival",
                "machine": island, "seed": _witness_seed,
                "date": _today, "reason": _reason,
            }, indent=2, default=str))
            return 0

    # R100 — THE RECENCY PROBATION'S WINDOW: the most recent rows, loaded with
    # the same honest reader (the tail of the same tapes -- the closest thing
    # to tomorrow morning). 0 rows = no probation (the report says so).
    probation_universe = None
    if args.probation_rows > 0:
        probation_universe = _load_universe(args.data, pairs,
                                            args.probation_rows,
                                            tape_path=args.tape or None)
        if not probation_universe:
            probation_universe = None  # an absent window is unmeasured, never guessed

    universe = _load_universe(args.data, pairs, args.rows,
                               tape_path=args.tape or None)
    if not universe:
        print("no data — nothing to run", file=sys.stderr)
        return 1

    cfg_obj = FactoryConfig(
        pairs=tuple(sorted(universe)),
        directed=_load_directed(args.directed),
        regime_gating=_load_gating(args.state),
        layers_quota=args.layers_quota,
        champion_seats=args.champion_seats,
        screen_survival=args.screen_survival,
        population=args.population, generations=args.generations, elite=args.elite,
        min_trades=args.min_trades, seed=args.seed,
        ensemble_quota=args.ensemble_quota, n_slices=args.n_slices,
        slice_salt=args.slice_salt, polish=bool(args.polish), cma=bool(args.cma),
        staircase=bool(args.staircase), screen_pair=args.screen_pair,
        island=island,
        rotate_seed=bool(cfg.get("rotate_seed", False)),
    )
    report = run_factory(universe, cfg_obj,
                         probation_universe=probation_universe)
    # R136: the NIGHT REPORT lands through THE ATOMIC PEN -- the most-read
    # door in the body (the letter, the dragon, the sage, the one-brain).
    atomic.write_json(args.out, report)

    # R119 — THE FORECASTER'S OATH: the shift's own prediction, spoken from
    # PAST ledger rows only (this row has not been appended yet -- the oath
    # cannot peek at the outcome it predicts), and the Brier verdict on the
    # PREVIOUS shift's oath. Fail-open by law: a wounded oracle never blocks
    # the one commit that must always land.
    _oath_note = ""
    try:
        _oath_row = oath_mod.close_turn(
            args.ledger, "factory_oath.jsonl", machine=island, facts={
                "crowned": len(report.get("champions") or []) >= 1,
                "migrants": int((report.get("diaspora") or {})
                                .get("injected", 0)) >= 1,
                "fast": float(report["wallclock_seconds"]) < oath_mod.FAST_S,
                "machine_seconds": float(report["wallclock_seconds"]),
            })
        _oath_note = " " + oath_mod.headline_note(_oath_row.get("oath"))
    except Exception as _oath_exc:  # noqa: BLE001 - fail-open, spoken
        print(f"[oath] fail-open: {type(_oath_exc).__name__}: {_oath_exc}")

    # R126 -- THE BLOOD'S HEADLINE: one honest word for the CEO's phone
    # (verdict, collision probability, effective population, the brake's
    # mark).  Fail-open and spoken, like the weather before it.
    _blood_note = "n/m"
    try:
        _gene = report.get("genealogy") or {}
        _brk = ":brake" if (_gene.get("brake") or {}).get("applied") else ""
        _blood_note = (f"{_gene.get('verdict') or 'n/m'}"
                       f":H{_gene.get('herfindahl')}"
                       f":Ne{_gene.get('effective_population')}{_brk}")
    except Exception:  # noqa: BLE001 - fail-open, spoken
        _blood_note = "n/m"

    # R66 — append the honest factory-ledger record.
    date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    rec = ledger_mod.FactoryRecord(
        date=date, machine=island, job=cfg.get("job", "factory-run"),
        trials=int(report["trials"]),
        machine_seconds=float(report["wallclock_seconds"]),
        cache_hits=int(report["result_memory"]["hits"]),
        cache_misses=int(report["result_memory"]["misses"]),
        realms_occupied=int(report["realms"]["occupied"]),
        note=(f"pairs={len(universe)} pop={args.population}"
              f" seed={report.get('seed')}"
              f" champ_in={report.get('champions_injected', 0)}"
              f" champ_out={len(report.get('champions') or [])}"
              f" migrants={report.get('diaspora', {}).get('injected', 0)}"
              f" wx={(report.get('weather') or {}).get('label') or 'n/m'}"
              f" blood={_blood_note}"
              f"{_oath_note}"
              f" {report.get('dna', {}).get('seal') or dna_mod.seal()}"),
    )
    ledger_mod.append([], rec, args.ledger)

    print(json.dumps({
        "machine": island, "trials": report["trials"],
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
        "diaspora": report.get("diaspora"),
        "probation": report.get("probation"),
        "dna": report.get("dna"),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
