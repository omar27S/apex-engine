"""RENDER THE FACTORY LEDGER — the CEO's phone view (Phase 7e, R66).

Reads the ledger JSONL, writes the per-day aggregate, and prints the last N days.
Build Mode: inert, read-only + one aggregate write.

Run::

    python -m tools.factory.render_ledger --ledger factory_ledger.jsonl --days 7
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.factory import ledger as ledger_mod  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 7e factory ledger render (R66)")
    ap.add_argument("--ledger", default="factory_ledger.jsonl")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--daily-out", default="factory_ledger_daily.json")
    ap.add_argument("--json", action="store_true", help="print the aggregate as JSON")
    args = ap.parse_args(argv)

    records = ledger_mod.load(args.ledger)
    days = ledger_mod.write_daily(records, args.daily_out)
    if args.json:
        print(json.dumps(days, indent=2, sort_keys=True))
    else:
        print(ledger_mod.render_last_days(records, args.days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
