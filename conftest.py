"""Make `app` importable when running pytest from the backend directory."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# R8 — LOUD-SKIP DOCTRINE. A data-gated test must never vanish silently: an
# end-of-suite summary surfaces how many tests were skipped and why.
_SKIP_REASONS: dict[str, int] = {}


def pytest_runtest_logreport(report):
    if report.when == "setup" and report.skipped:
        reason = ""
        if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
            reason = report.longrepr[2]
        reason = reason.split(":", 1)[-1].strip() or "unspecified"
        _SKIP_REASONS[reason] = _SKIP_REASONS.get(reason, 0) + 1


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    total = sum(_SKIP_REASONS.values())
    if not total:
        return
    terminalreporter.write_sep("=", f"SKIP LOUD SUMMARY: {total} skipped")
    for reason, count in sorted(_SKIP_REASONS.items(), key=lambda kv: -kv[1]):
        terminalreporter.write_line(f"  {count:4d}  {reason}")
