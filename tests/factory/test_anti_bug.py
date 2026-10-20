"""THE ANTI-BUG GUARDIAN'S PROOFS -- every wound, caught before the night.

The Boss ordered an anti-bug "that works always" (2026-10-20). These tests pin
the guardian's twelve checks on synthetic wards: a healthy tree rounds green;
each individual wound (unsigned ledger row, ghost champion, torn pantry,
untracked pantry, sleeping eye, starved disk, missing letter past noon,
forgotten pain) is caught with the right severity; the healing hand quarantines
and restores reversibly; the guardian's own ledger is bounded.

Time is INJECTED (``now=`` / ``APEX_GUARDIAN_NOW``) -- a test must never depend
on the hour it happens to run. The machine (git/df/systemctl) is a recording
runner where reality would be environment-dependent.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.factory import anti_bug as ab  # noqa: E402
from app.factory import islands as islands_mod  # noqa: E402


# ---------------------------------------------------------------------------
# the synthetic ward: a healthy tree, one file per sign
# ---------------------------------------------------------------------------
class Machine:
    """A recording runner: git is real (a true mini repo), df/systemctl talk."""

    def __init__(self, *, free_mb="99999", timer="enabled"):
        self.free_mb = free_mb
        self.timer = timer

    def __call__(self, cmd, cwd=None):
        head = cmd[0]
        if head == "df":
            return 0, f"Avail\n{self.free_mb}\n"
        if head == "systemctl":
            if self.timer == "enabled":
                return 0, "enabled\n"
            return 1, f"Failed to enable unit: {self.timer}\n"
        return subprocess.run(cmd, cwd=cwd, capture_output=True,
                              text=True, timeout=60).returncode, ""


def _champion(wilson=0.55, family="trend", recency=None):
    entry = {"genome": {"sl_atr_mult": 1.5, "target_rr": 2.0},
             "family": family, "wilson_lb": wilson, "net_r": 4.2}
    if recency is not None:
        entry["recency"] = recency
    return entry


def _pantry(island="heart", champions=None) -> dict:
    return islands_mod.build_migration(
        island, 3, champions or [_champion()]).to_dict()


def _write_pantry(backend: Path, island="heart", champions=None):
    (backend / f"factory_champions_{island}.json").write_text(
        json.dumps(_pantry(island, champions), indent=2))


def _ledger_row(date, note, machine="heart") -> str:
    return json.dumps({"date": date, "machine": machine, "trials": 4000,
                       "note": note})


def _healthy_ward(tmp_path: Path, *, now: dt.datetime,
                  island="heart") -> Path:
    backend = tmp_path / "backend"
    backend.mkdir()
    root = tmp_path
    (root / "letters").mkdir()
    (root / "letters" / f"lettera_{now.date()}.md").write_text("# Lettera\n")
    (backend / "factory_ledger.jsonl").write_text("\n".join([
        _ledger_row(str(now.date()), "pairs=5 seed=1000 champ_in=1 dna=v1"),
        _ledger_row(str(now.date()), "pairs=5 seed=8919 champ_in=1 dna=v1"),
    ]) + "\n")
    _write_pantry(backend, island)
    for name in ab.STATE_FILES:
        (backend / name).write_text(json.dumps({"alive": True}))
    # the synthetic clock is the ward's truth: the eye's reading is stamped
    # AT the injected now (a future-dated clock would see a real-mtime file
    # as ancient -- the same honest arithmetic the live guardian uses)
    _stamp = now.timestamp()
    os.utime(backend / "falcon.json", (_stamp, _stamp))
    (backend / "dd_ledger.json").write_text(json.dumps(
        {"nights": [{"date": str(now.date()), "dd_r": 1.5}]}))
    # THE LIVE WIRE (check 12, born 2026-10-20): a healthy ward carries the
    # fast eye's FRESH snapshot, stamped at the injected now exactly like the
    # falcon's reading -- one synthetic clock, two eyes, the same arithmetic.
    (backend / "hyperfeed.json").write_text(json.dumps(
        {"schema": 1, "kind": "hyperfeed", "ts": _stamp,
         "venues": {}, "symbols": {}, "counts": {}}))
    # a real repo so git answers like on the VM
    subprocess.run(["git", "init", "-q"], cwd=backend, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=backend,
                   check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=backend, check=True)
    subprocess.run(["git", "add", "-A"], cwd=backend, check=True)
    subprocess.run(["git", "commit", "-qm", "ward"], cwd=backend, check=True)
    return backend


def _now():
    return dt.datetime(2026, 10, 22, 14, 0, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# the healthy round
# ---------------------------------------------------------------------------
def test_a_healthy_ward_rounds_green():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert report["verdict"] == ab.VERDICT_CLEAN, report
    assert report["failed"] == []
    assert not [c for c in report["checks"] if not c["ok"]], report["checks"]
    assert report["checks_run"] == len(ab.CHECKS)


def test_the_round_is_recorded_in_the_guardians_own_ledger():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    ab.sweep(backend, now=now, runner=Machine(), write=True)
    tail = ab.load_ledger_tail(backend)
    assert len(tail) == 1
    assert tail[0]["verdict"] == ab.VERDICT_CLEAN
    assert (backend / ab.LEDGER_NAME).exists()


def test_the_guardians_ledger_is_bounded():
    backend = _tmp()
    for i in range(ab.LEDGER_MAX_ROWS + 120):
        ab.append_ledger(backend, {"i": i, "verdict": "clean"})
    rows = (backend / ab.LEDGER_NAME).read_text().splitlines()
    assert len(rows) == ab.LEDGER_MAX_ROWS
    assert json.loads(rows[-1])["i"] == ab.LEDGER_MAX_ROWS + 119  # newest kept


# ---------------------------------------------------------------------------
# the wounds, one by one
# ---------------------------------------------------------------------------
def test_an_unsigned_row_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_ledger.jsonl").write_text(
        _ledger_row(str(now.date()), "pairs=5 seed=1000 (no seal)") + "\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "ledger_sealed" in report["failed"]
    assert report["verdict"] == ab.VERDICT_WOUNDS


def test_a_foreign_island_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_ledger.jsonl").write_text(
        _ledger_row(str(now.date()), "seed=1000 dna=v1", machine="atlantis")
        + "\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "ledger_sealed" in report["failed"]


def test_a_seed_short_of_its_stride_is_watched():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_ledger.jsonl").write_text("\n".join([
        _ledger_row(str(now.date()), "seed=1000 dna=v1"),
        _ledger_row(str(now.date()), "seed=1042 dna=v1"),
    ]) + "\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "seed_arithmetic" in report["warned"]
    assert report["verdict"] == ab.VERDICT_CLEAN  # watched, not wounded


def test_a_repeated_seed_is_watched():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_ledger.jsonl").write_text("\n".join([
        _ledger_row(str(now.date()), "seed=1000 dna=v1"),
        _ledger_row(str(now.date()), "seed=1000 dna=v1"),
    ]) + "\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "seed_arithmetic" in report["warned"]


def test_a_ghost_champion_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    ghosts = [_champion(), {"genome": {"x": 1}, "wilson_lb": None}]
    _write_pantry(backend, champions=ghosts)
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "pantry_honest" in report["failed"]


def test_a_broken_digest_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    payload = _pantry()
    payload["digest"] = "0" * 16  # a forged seal
    (backend / "factory_champions_heart.json").write_text(json.dumps(payload))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "pantry_honest" in report["failed"]


def test_an_invented_wilson_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _write_pantry(backend, champions=[_champion(wilson=7.5)])
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "pantry_honest" in report["failed"]


def test_an_untracked_pantry_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _write_pantry(backend, "turbo")  # existing on disk, never committed
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "pantry_tracked" in report["failed"]


def test_an_absent_pantry_is_soft_emptiness_not_a_wound():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    for island in ab.ISLANDS:
        p = backend / f"factory_champions_{island}.json"
        if p.exists():
            p.unlink()
    subprocess.run(["git", "add", "-A"], cwd=backend, check=True)
    subprocess.run(["git", "-C", str(backend), "commit", "-qm", "gone"],
                   check=True)
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "pantry_honest" not in report["failed"]
    assert "pantry_honest" in report["warned"]


def test_a_sleeping_eye_is_watched_not_wounded():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    falcon = backend / "falcon.json"
    old = now.timestamp() - (ab.FALCON_MAX_AGE_S + 600)
    os.utime(falcon, (old, old))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "falcon_fresh" in report["warned"]
    assert report["verdict"] == ab.VERDICT_CLEAN


def test_a_starved_disk_wounds():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now,
                      runner=Machine(free_mb="42"), write=False)
    assert "disk_floor" in report["failed"]


def test_a_missing_letter_past_noon_wounds():
    now = _now()  # 14:00 UTC -- past the grace
    backend = _healthy_ward(_tmp(), now=now)
    (backend.parent / "letters" / f"lettera_{now.date()}.md").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "letter_of_dawn" in report["failed"]


def test_a_missing_letter_in_the_morning_is_only_watched():
    now = dt.datetime(2026, 10, 22, 7, 0, tzinfo=dt.timezone.utc)
    backend = _healthy_ward(_tmp(), now=now)
    (backend.parent / "letters" / f"lettera_{now.date()}.md").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "letter_of_dawn" in report["warned"]
    assert "letter_of_dawn" not in report["failed"]


def test_forgotten_pain_wounds_after_the_grace():
    now = dt.datetime(2026, 10, 25, 14, 0, tzinfo=dt.timezone.utc)
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "dd_ledger.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "dd_ledger_grown" in report["failed"]


def test_the_unborn_pain_is_graced_on_transition_day():
    now = dt.datetime(2026, 10, 21, 14, 0, tzinfo=dt.timezone.utc)
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "dd_ledger.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "dd_ledger_grown" in report["warned"]
    assert "dd_ledger_grown" not in report["failed"]


def test_a_disabled_heart_timer_is_watched():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now,
                      runner=Machine(timer="mask"), write=False)
    assert "heart_scheduled" in report["warned"]


# ---------------------------------------------------------------------------
# the healing hand
# ---------------------------------------------------------------------------
def test_a_torn_pantry_is_quarantined_and_the_committed_copy_restored():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    good = (backend / "factory_champions_heart.json").read_text()
    (backend / "factory_champions_heart.json").write_text("{torn json")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert report["verdict"] == ab.VERDICT_HEALED
    assert report["healed"], report
    assert "pantry_honest" not in report["failed"]  # re-judged after healing
    assert (backend / "factory_champions_heart.json").read_text() == good
    quarantined = list((backend / ab.QUARANTINE_DIR).glob("*.bad"))
    assert len(quarantined) == 1


def test_an_untracked_torn_pantry_is_quarantined_to_honest_absence():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_champions_turbo.json").write_text("{torn")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    # torn -> healed by quarantine; absent and untracked -> honest emptiness
    assert not (backend / "factory_champions_turbo.json").exists()
    assert report["healed"]
    assert report["verdict"] == ab.VERDICT_HEALED
    assert "pantry_honest" not in report["failed"]
    assert list((backend / ab.QUARANTINE_DIR).glob("*.bad"))


def test_the_factory_ledger_is_never_healed_only_reported():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    before = (backend / "factory_ledger.jsonl").read_text()
    (backend / "factory_ledger.jsonl").write_text("torn beyond json\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert (backend / "factory_ledger.jsonl").read_text() == "torn beyond json\n"
    assert not report["healed"]  # the ledger is append-only; the physician
    # reports, he does not rewrite history
    assert before  # sanity


# ---------------------------------------------------------------------------
# the CLI (what systemd calls every half hour)
# ---------------------------------------------------------------------------
def test_the_cli_exits_zero_on_a_healthy_ward_and_one_on_a_wound():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    os.environ["APEX_GUARDIAN_NOW"] = now.isoformat()
    try:
        rc_clean = ab.main(["--backend", str(backend)])
        (backend / "factory_ledger.jsonl").write_text(
            _ledger_row(str(now.date()), "no seal here") + "\n")
        rc_wound = ab.main(["--backend", str(backend)])
    finally:
        os.environ.pop("APEX_GUARDIAN_NOW", None)
    assert rc_clean == 0
    assert rc_wound == 1


def test_the_guardian_never_dies_on_its_own_gurney():
    # a sweep over a missing directory is recorded fail-open, never raised
    report = ab.sweep(_tmp() / "nowhere", runner=_no_machine, write=False)
    assert report["verdict"] in (ab.VERDICT_CLEAN, ab.VERDICT_WOUNDS)
    assert report["checks_run"] == len(ab.CHECKS)


# ---------------------------------------------------------------------------
# THE LIVE WIRE (check 12) -- the fast eye's vital sign
# ---------------------------------------------------------------------------
def test_a_quiet_live_wire_is_a_warning_never_a_wound():
    now = _now()  # 2026-10-22: past the wire's birth, the wire is expected
    backend = _healthy_ward(_tmp(), now=now)
    # the wire went quiet 30 minutes ago (its own ts says so)
    stale = now.timestamp() - 30 * 60
    (backend / "hyperfeed.json").write_text(json.dumps(
        {"schema": 1, "ts": stale}))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "hyperfeed_alive")
    assert not check["ok"]
    assert check["severity"] == "warn"   # a sleeping sensor, not a lie
    assert "hyperfeed_alive" in report["warned"]
    assert "hyperfeed_alive" not in report["failed"]
    assert report["verdict"] == ab.VERDICT_CLEAN  # warnings do not wound


def test_a_fresh_live_wire_rounds_green_and_declares_it():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "hyperfeed.json").write_text(json.dumps(
        {"schema": 1, "ts": now.timestamp() - 42.0}))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "hyperfeed_alive")
    assert check["ok"]
    assert "42" in check["detail"]
    assert report["verdict"] == ab.VERDICT_CLEAN


def test_the_unborn_wire_on_its_birth_day_is_soft():
    # on 2026-10-20 itself the service may not be installed yet: emptiness,
    # not a lie (the dd ledger's transition-day doctrine, applied to the eye)
    now = dt.datetime(2026, 10, 20, 14, 0, tzinfo=dt.timezone.utc)
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "hyperfeed.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "hyperfeed_alive")
    assert check["ok"] is True or check["severity"] == "warn"
    assert "hyperfeed_alive" not in report["failed"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _tmp() -> Path:
    import tempfile
    return Path(tempfile.mkdtemp())


def _no_machine(cmd, cwd=None):
    return 127, ""
