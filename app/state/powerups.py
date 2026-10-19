"""THE THREE POWER-UPS -- one fold the night report and the bulletin both read.

The three enhancements are separate concerns, but the CEO reads them as ONE
block: what the scout shortlisted, what rhythm the machine earned, and whether
the two runners are alive. :func:`powerups_report` assembles that block (each
part optional and honestly carried as unmeasured when absent).

Pure at import (Scar #6).
"""

from __future__ import annotations

from . import adaptive_rhythm as ar
from . import runner_watchdog as rw
from . import scout as sc

__all__ = ["powerups_report"]


def powerups_report(*, scout_report: dict | None = None,
                    rhythm_report: dict | None = None,
                    watchdog_report: dict | None = None) -> dict:
    """Fold the three power-ups into the night block: scout, rhythm, watchdog."""
    blocks = {
        "scout": scout_report,
        "rhythm": rhythm_report,
        "watchdog": watchdog_report,
    }
    measured = [k for k, v in blocks.items() if v is not None]
    missing = [k for k, v in blocks.items() if v is None]
    return {
        "powerups": blocks,
        "measured_this_night": measured,
        "unmeasured_this_night": missing,
        "reading": (f"power-ups read: {', '.join(measured) or 'none'}"
                    + (f"; unmeasured: {', '.join(missing)}" if missing else "")),
    }
