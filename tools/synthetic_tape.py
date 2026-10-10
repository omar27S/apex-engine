"""A DETERMINISTIC SYNTHETIC TAPE — so the public engine can prove its wiring
(Phase 7f).

The PUBLIC repo (``apex-engine``) must never carry the private market tapes. But
the sliced burst pipeline still needs *some* schema-valid OHLC to run end to end
on a public runner. This tool writes a deterministic (seeded), reproducible M15
tape that satisfies ``app.core.data``'s validator exactly — so the burst can be
proven without a single byte of private data crossing the boundary.

It is honest about what it is: a sine-plus-noise walk with no edge. A burst over
this tape proves the MACHINE, never a strategy.

Run::

    python -m tools.synthetic_tape --out data/history --pairs EURUSD,GBPUSD --rows 30000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def make_tape(pair: str, rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # M15 bars: 900 seconds apart, ending "now" is irrelevant — deterministic.
    ts = np.arange(rows, dtype=np.int64) * 900 + 1_600_000_000
    phase = (sum(map(ord, pair)) % 97) / 97.0
    drift = np.sin(np.linspace(0, 40 * np.pi, rows) + phase) * 0.0015
    noise = rng.normal(0.0, 0.0006, rows)
    close = 1.0 + np.cumsum(drift + noise)
    close = np.maximum(close, 0.01)
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0.0, 0.0004, rows))
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    volume = np.abs(rng.normal(100.0, 20.0, rows))
    return pd.DataFrame({
        "ts": ts, "open": open_.astype(float), "high": high.astype(float),
        "low": low.astype(float), "close": close.astype(float),
        "volume": volume.astype(float),
    })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deterministic synthetic M15 tape")
    ap.add_argument("--out", default="data/history")
    ap.add_argument("--pairs", default="EURUSD,GBPUSD,USDJPY,EURGBP")
    ap.add_argument("--rows", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, pair in enumerate(p for p in args.pairs.split(",") if p.strip()):
        df = make_tape(pair.strip(), args.rows, args.seed + i)
        df.to_parquet(out / f"{pair.strip()}_M15.parquet", index=False)
        print(f"wrote {pair.strip()}_M15.parquet rows={len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
