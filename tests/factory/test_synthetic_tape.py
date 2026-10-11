"""The synthetic tape (Phase 7f) — deterministic, schema-valid, no private data."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.data import load_parquet  # noqa: E402
from tools import synthetic_tape as st  # noqa: E402


def test_synthetic_tape_is_deterministic():
    a = st.make_tape("EURUSD", 200, 3)
    b = st.make_tape("EURUSD", 200, 3)
    assert a.equals(b)


def test_synthetic_tape_passes_the_validator(tmp_path):
    st.main(["--out", str(tmp_path), "--pairs", "EURUSD,USDJPY", "--rows", "500"])
    for pair in ("EURUSD", "USDJPY"):
        df = load_parquet(str(tmp_path / f"{pair}_M15.parquet"))  # fail-closed OK
        assert len(df) == 500
        assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
        assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
        assert (df[["open", "high", "low", "close"]] > 0).all().all()


def test_synthetic_tape_differs_by_seed_and_by_pair():
    a = st.make_tape("EURUSD", 200, 0)
    b = st.make_tape("EURUSD", 200, 1)
    c = st.make_tape("GBPUSD", 200, 0)
    assert not a["close"].equals(b["close"])
    assert not a["close"].equals(c["close"])
