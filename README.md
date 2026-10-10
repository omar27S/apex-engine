# APEX ENGINE — the public turbo

This repository is the **public compute face** of APEX: it holds the engine code
that burns GitHub's free runner minutes on **sliced** factory bursts. Nothing
here is a strategy, a result, or market data.

## What this IS

- The APEX engine subset needed to run a **sliced factory burst**:
  `app/core` (the Constitution, pairs, tick value, data pipeline),
  `app/quant`, `app/pyramid` (grammar, judge, oracle), `app/factory` (the levers
  R66–R73/R75), and the `tools/factory` runners (`split_engine`, `fuse_slices`,
  `run_factory`, `run_slice`, `render_ledger`).
- A single GitHub Actions workflow, **`slams.yml`**, that splits the pair
  universe into disjoint slices, runs them in parallel within ONE job (bounded by
  the R75 budget: ≤20 concurrent and ≤3 bursts/day), fuses the slice
  leaderboards, and signs ONE `sliced_tournament` certificate bound to the running
  commit.
- A deterministic **synthetic tape** generator (`tools/synthetic_tape.py`) so the
  pipeline can be proven on a public runner with **no private data**.

## What this IS NOT

- **Not the strategy.** No genome, no champion, no edge lives here. The bursts
  run over synthetic tapes and validate the MACHINE, never a tradeable signal.
- **Not the data.** The private market tapes live only in the private `apex`
  repo, transported as a verified release asset. No `.parquet` of real market
  history is ever committed here.
- **Not the certificates.** Signed certificates and the factory ledger are
  produced by the collector on the private side (the vault). This repo emits
  *slice artifacts* (leaderboard rows only) as CI artifacts; it does not store
  results.
- **Not live.** Build Mode: no server, no scheduler, no broker link. A workflow
  is an external, human-triggered job. HUMAN_EXECUTION_ONLY and
  FUNDED_STEALTH_MODE hold: the machine advises; the CEO executes.

## The sliced burst (R67 / R75)

```
                    apex-engine (public, free minutes)
   pairs ──► make_slices ──► [slice 0..N-1]  (disjoint, deterministic)
                                   │
                    run_factory per slice (parallel in-job)
                                   │
                        slice artifacts (leaderboards)
                                   │
             fuse_slices ──► ONE certificate (bound to --head)
```

Budget law (R75): at most **3 bursts/day**, each **≤2h**, at most **20 concurrent
jobs**. `tools/factory/split_engine.py` refuses any burst that breaches the cap
(fail-closed), and the collector refuses to sign a partial or mixed-head burst.

## Prove it locally

```bash
python -m tools.synthetic_tape --out data/history --pairs EURUSD,GBPUSD,USDJPY,EURGBP --rows 30000
python -m tools.factory.split_engine --pairs EURUSD,GBPUSD,USDJPY,EURGBP \
    --count 2 --jobs 2 --artifacts-dir slices --head "$(git rev-parse HEAD)" \
    --out burst_report.json
python -m tools.factory.fuse_slices --dir slices --count 2 --seed 0 \
    --pairs EURUSD,GBPUSD,USDJPY,EURGBP --head "$(git rev-parse HEAD)" \
    --cert-dir certificates --out fused_report.json
```

## Laws referenced

R66 (ledger), R67 (sliced parallel tournament), R75 (turbo budget). The engine
here is copied verbatim from the private vault's sealed engine at a given commit;
the vault is the source of truth.
