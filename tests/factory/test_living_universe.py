"""R120 THE LIVING UNIVERSE -- the factory evolves on the market's last
closed bar, not on a photograph.

The measured truth (2026-10-21 00:30 UTC): even after the historian's
healing, the deep parquet ages between healing rounds (daily 02:37) -- a
shift at 02:00 evolves on a frame up to a day old. The living stitch folds
the live M15 tape's bars BEYOND the parquet edge onto the universe, in
memory, read-only, at every shift: the heart reads its own wire. The
historian's Law 1 rides unchanged -- the parquet wins every collision, the
tape only extends BEYOND it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tools.factory.run_factory import _load_universe, _stitch_live_edge


GRID = 900
# every synthetic bar opens ON the M15 grid (the validator's own law)
START = (1790000000 // GRID + 1) * GRID


def _bars(start_ts: int = START, n: int = 1200, price: float = 1.1000) -> pd.DataFrame:
    rows = []
    for i in range(n):
        p = price + (i % 7) * 0.0003
        rows.append({"ts": start_ts + i * 900, "open": p, "high": p + 0.0004,
                     "low": p - 0.0004, "close": p + 0.0001, "volume": 10.0})
    return pd.DataFrame(rows)


def _tape_bar(ts: int, price: float = 1.1200, n: int = 20) -> dict:
    return {"ts": ts, "open": price, "high": price + 0.0005,
            "low": price - 0.0005, "close": price + 0.0002, "volume": float(n)}


class TestTheStitchAlone:
    def test_tape_bars_beyond_the_edge_are_folded(self):
        m15 = _bars(n=5)
        edge = int(m15["ts"].iloc[-1])
        tape = [_tape_bar(edge + 900), _tape_bar(edge + 1800)]
        stitched, added = _stitch_live_edge(m15, tape)
        assert added == 2
        assert len(stitched) == 7
        assert int(stitched["ts"].iloc[-1]) == edge + 1800
        # the fold is in memory: the source frame is untouched
        assert len(m15) == 5

    def test_the_parquet_wins_collisions(self):
        m15 = _bars(n=3)
        edge = int(m15["ts"].iloc[-1])
        # a tape bar CLAMING the edge's ts with a different price
        clash = _tape_bar(edge, price=9.99)
        fresh = _tape_bar(edge + 900)
        stitched, added = _stitch_live_edge(m15, [clash, fresh])
        assert added == 1                     # only the bar beyond rode
        row = stitched[stitched["ts"] == edge].iloc[0]
        assert abs(float(row["close"]) - 9.99) > 0.5  # the tape's lie refused

    def test_malformed_bars_are_refused_alone(self):
        m15 = _bars(n=3)
        edge = int(m15["ts"].iloc[-1])
        bad_geo = {"ts": edge + 900, "open": 1.0, "high": 1.0,
                   "low": 0.5, "close": 2.0, "volume": 3}   # high < max(o,c)
        off_grid = _tape_bar(edge + 901)                     # not on the M15 grid
        good = _tape_bar(edge + 1800)
        stitched, added = _stitch_live_edge(m15, [bad_geo, off_grid, good])
        assert added == 1

    def test_no_tape_is_the_fossil_frame(self):
        m15 = _bars(n=4)
        stitched, added = _stitch_live_edge(m15, None)
        assert added == 0 and len(stitched) == 4


class TestTheUniverseLoader:
    def test_the_universe_carries_the_wire(self, tmp_path, monkeypatch):
        data = tmp_path / "history"
        data.mkdir()
        m15 = _bars()
        m15.to_parquet(data / "EURUSD_M15.parquet", index=False)
        edge = int(m15["ts"].iloc[-1])
        tape = tmp_path / "tape.jsonl"
        tape.write_text(json.dumps({
            "kind": "m15_bar", "symbol": "EURUSD",
            "open_ms": (edge + 900) * 1000, "o": 1.15, "h": 1.1505,
            "l": 1.1495, "c": 1.1502, "n": 31, "source": "kraken"}) + "\n")
        universe = _load_universe(str(data), ["EURUSD"], 1000,
                                  tape_path=str(tape))
        assert "EURUSD" in universe
        # the built frames end on the TAPE's bar (the wire's own close)
        frames = universe["EURUSD"]
        ts_series = frames.m15["ts"] if hasattr(frames, "m15") else frames["m15"]["ts"]
        assert int(ts_series.iloc[-1]) == edge + 900

    def test_a_dead_tape_is_the_fossil_frame(self, tmp_path):
        data = tmp_path / "history"
        data.mkdir()
        m15 = _bars()
        m15.to_parquet(data / "EURUSD_M15.parquet", index=False)
        universe = _load_universe(str(data), ["EURUSD"], 1000,
                                  tape_path=str(tmp_path / "absent.jsonl"))
        assert "EURUSD" in universe          # fail-open: the shift ran anyway
