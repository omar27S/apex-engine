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
    """A recording runner: git is real (a true mini repo), df/systemctl talk.

    R109 made the guardian ask EVERY organ's clock (four timers is-enabled +
    the live wire's service is-active); the mock answers each question with
    its own dial: ``timer`` for the timers, ``service`` for the always-on
    wire (default healthy: 'active').
    """

    def __init__(self, *, free_mb="99999", timer="enabled", service="active",
                 born=None):
        self.free_mb = free_mb
        self.timer = timer
        self.service = service
        # R135: the rebirth dial -- "show <unit> -p ActiveEnterTimestamp"
        # answers. None = fresh (born an hour from now, after any file); a
        # dict maps units to stamps; "MUTE" silences systemd (abstention).
        self.born = born if born is not None else {}

    def _birth_stamp(self, unit: str) -> str:
        import datetime as _d
        stamp = self.born.get(unit)
        if stamp == "MUTE":
            return "", 1
        if stamp is None:
            when = (_d.datetime.now(_d.timezone.utc)
                    + _d.timedelta(hours=1))   # fresher than any ward file
            return when.strftime("%a %Y-%m-%d %H:%M:%S UTC"), 0
        return stamp, 0

    def __call__(self, cmd, cwd=None):
        head = cmd[0]
        if head == "df":
            return 0, f"Avail\n{self.free_mb}\n"
        if head == "systemctl":
            if "show" in cmd and "ActiveEnterTimestamp" in cmd:
                unit = cmd[2] if len(cmd) > 2 else ""
                stamp, rc = self._birth_stamp(unit)
                return rc, (stamp + "\n") if stamp else ""
            if "is-active" in cmd:
                if self.service == "active":
                    return 0, "active\n"
                return 3, f"inactive\n"
            if self.timer == "enabled":
                return 0, "enabled\n"
            return 1, f"Failed to enable unit: {self.timer}\n"
        if head == "git":
            # R149: git speaks its REAL stdout here (the guardian's 19th eye
            # reads 'git ls-files' output; before, every git answer was muted
            # to its bare return code -- rc-only callers are unaffected).
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True,
                                  text=True, timeout=60)
            return proc.returncode, proc.stdout
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
    # R132: the ward's pain ledger now carries the WRITER's true shape --
    # the JSON list grand_night has written since the first honest night
    # (the guardian once re-parsed this file with its own eyes and called
    # this exact healthy shape "does not parse" for three live hours).
    (backend / "dd_ledger.json").write_text(json.dumps(
        [{"version": 1, "date": "20261020", "seed": 1233420331,
          "basis": "finalists", "net_r": 1.5, "dd_tonight": 0.5,
          "dd_basis": "finalists", "equity_after": 1.5,
          "peak_after": 1.5, "dd_after": 0.0}]))
    # THE LIVE WIRE (check 12, born 2026-10-20): a healthy ward carries the
    # fast eye's FRESH snapshot, stamped at the injected now exactly like the
    # falcon's reading -- one synthetic clock, two eyes, the same arithmetic.
    (backend / "hyperfeed.json").write_text(json.dumps(
        {"schema": 1, "kind": "hyperfeed", "ts": _stamp,
         "venues": {}, "symbols": {}, "counts": {}}))
    # THE MOUTH (check 14, born 2026-10-20): a healthy ward carries the
    # organ's fresh artifact -- the mouth writes it EVERY turn, speaking or
    # honestly blind, and the guardian reads its own ISO stamp.
    (backend / "signal_live.json").write_text(json.dumps(
        {"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")}))
    # THE SCAR TISSUE (R121's organ, born 2026-10-21): the body remembers
    # its wounds and every tripwire resolves inside the synthetic ward.
    (backend / "scars.json").write_text(json.dumps({
        "version": 1,
        "scars": [{
            "id": "S-TEST", "born": "2026-10-21", "organ": "ward",
            "wound": "the synthetic ward's own scar (a rehearsal, not a wound)",
            "guard": "R121 the scar tissue",
            "tripwire": {"kind": "check", "name": "history_edge"},
        }],
    }))
    # THE HISTORIAN'S VOICE (R118's organ, born 2026-10-20): the deep frame's
    # health artifact, spoken at the injected now with a fresh edge -- the
    # organ's own word for the guardian to read (never re-derived).
    (backend / "history_health.json").write_text(json.dumps({
        "version": 1, "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": "healthy", "heals": 30, "bars_healed": 900,
        "pairs": {"EURUSD": {"edge_ts": int(now.timestamp()) - 3600,
                             "edge_age_s": 3600, "verdict": "fresh"}},
    }))
    # THE GENEALOGIST (R126's organ, born 2026-10-21): the census and the
    # blood book for every wheel island, fresh like every organ -- the
    # guardian reads the organ's own word (never re-derived).
    for _isle in ("heart", "turbo", "vault"):
        (backend / f"factory_genealogy_{_isle}.json").write_text(json.dumps({
            "schema": 1, "island": _isle, "ts": int(now.timestamp()),
            "bodies": 240, "founders_alive": 40, "herfindahl": 0.031,
            "effective_population": 32.25, "sibling_matings": 0,
            "crossovers": 100, "verdict": "diverse",
            "brake": {"applied": False},
        }))
        (backend / f"factory_blood_{_isle}.json").write_text(json.dumps({
            "schema": 1, "island": _isle, "founders_seen": 40,
            "entries": 0, "blood": {},
        }))
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


# --- R132: THE CONTRACT-BLIND PHYSICIAN ------------------------------------
# The guardian re-parsed the pain ledger with its own eyes (dict + nights)
# while the writer's true shape is the list load_ledger() has accepted from
# birth -- three live hours of "does not parse" against healthy tissue.
# These five proofs nail the contract to the reader's chest.

def test_the_pain_ledger_is_read_through_the_contract():
    # the WRITER's true shape: the JSON list the Grand has written since its
    # first honest night -- the guardian must count the night AND speak the
    # accumulated number the memory holds, never "does not parse"
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "dd_ledger.json").write_text(json.dumps([
        {"version": 1, "date": "20261020", "seed": 1, "basis": "finalists",
         "net_r": 72.7, "dd_tonight": 0.0, "dd_basis": "finalists",
         "equity_after": 72.7, "peak_after": 72.7, "dd_after": 0.0},
        {"version": 1, "date": "20261021", "seed": 2, "basis": "finalists",
         "net_r": -9.0, "dd_tonight": 9.0, "dd_basis": "finalists",
         "equity_after": 63.7, "peak_after": 72.7, "dd_after": 9.0},
    ]))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "dd_ledger_grown")
    assert check["ok"], check["detail"]
    assert "2 night" in check["detail"], check["detail"]
    assert "9.00R" in check["detail"], check["detail"]
    assert "parse" not in check["detail"], check["detail"]


def test_the_legacy_dict_pain_shape_is_still_graced():
    # load_ledger() accepts the older {"nights": [...]} dict with equal
    # grace (its documented retro-compat) -- the contract serves both
    # generations of writers, and the reader follows the contract
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "dd_ledger.json").write_text(json.dumps(
        {"nights": [{"date": "20261020", "net_r": 1.5}]}))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "dd_ledger_grown")
    assert check["ok"], check["detail"]
    assert "1 night" in check["detail"], check["detail"]


def test_a_torn_pain_ledger_escalates_with_the_truth():
    # unreadable bytes are a wound ESCALATED and NAMED -- not the lazy
    # "does not parse" that once covered a healthy list
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "dd_ledger.json").write_text("{not json at all")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "dd_ledger_grown")
    assert not check["ok"]
    assert check["severity"] == "fail", check["detail"]
    assert "unreadable" in check["detail"], check["detail"]


def test_the_same_turn_written_twice_is_named_what_it_is():
    # R132's second wound: two identical (seed, machine) rows are the SAME
    # turn written twice -- an append whose push died and a re-run that
    # redrew the deterministic seed. The guardian says THIS, not the lazy
    # CI-twin guess (the live wound of 2026-10-21 15:30 UTC).
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_ledger.jsonl").write_text("\n".join([
        _ledger_row(str(now.date()), "pairs=5 seed=1639233 champ_in=3 dna=v1",
                    machine="vault"),
        _ledger_row(str(now.date()), "pairs=5 seed=1647152 champ_in=8 dna=v1",
                    machine="heart"),
        _ledger_row(str(now.date()), "pairs=5 seed=1647152 champ_in=8 dna=v1",
                    machine="heart"),
    ]) + "\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "seed_arithmetic")
    assert not check["ok"]
    assert "written twice" in check["detail"], check["detail"]
    assert "CI + VM" not in check["detail"], check["detail"]


def test_the_ci_twin_seed_overlap_keeps_its_old_name():
    # the same seed on DIFFERENT machines is still the honest clock-sibling
    # overlap (the CI twin and the VM body interleaving turns) -- the
    # guardian kept the old diagnosis for the old wound
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_ledger.jsonl").write_text("\n".join([
        _ledger_row(str(now.date()), "pairs=5 seed=1647152 champ_in=8 dna=v1",
                    machine="heart"),
        _ledger_row(str(now.date()), "pairs=5 seed=1647152 champ_in=8 dna=v1",
                    machine="atlantis"),
    ]) + "\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "seed_arithmetic")
    assert not check["ok"]
    assert "CI + VM" in check["detail"], check["detail"]
    assert "written twice" not in check["detail"], check["detail"]


# --- R133: THE FOSSILS OF TORN MEMORY (the guardian's voice for the
# civilization state's quarantine evidence) ---------------------------------

def test_fresh_torn_memory_fossils_are_watched():
    # a torn-memory fossil younger than a day means an organ saved and did
    # not finish -- a warn said aloud, the evidence kept
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "civilization_state.torn.1790000000.json").write_text("{ torn")
    os.utime(backend / "civilization_state.torn.1790000000.json",
             (now.timestamp(), now.timestamp()))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "memory_quarantine" in report["warned"]
    assert "memory_quarantine" not in report["failed"]
    check = next(c for c in report["checks"]
                 if c["name"] == "memory_quarantine")
    assert "did not finish" in check["detail"], check["detail"]


def test_old_torn_memory_fossils_are_evidence_not_wounds():
    # a fossil older than a day is history the body survived: the evidence
    # stays, the verdict is clean, the voice names it
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    fossil = backend / "civilization_state.torn.1690000000.json"
    fossil.write_text("{ torn long ago")
    old = (now - dt.timedelta(days=3)).timestamp()
    os.utime(fossil, (old, old))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"]
                 if c["name"] == "memory_quarantine")
    assert check["ok"], check["detail"]
    assert "evidence" in check["detail"], check["detail"]


# --- R135: THE BODY SHALL NOT CARRY A DEAD PAST (a process frozen before
# its organs' birth can never see them -- the nine-day one_brain wound) -----

def test_a_process_frozen_before_its_organs_birth_is_watched():
    # the 2026-10-21 wound, replayed: the council born Oct 12, the One
    # Brain's cycle code born NOW -- nine days of a semantic memory that
    # never thought once, because the process could not see the organ
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "app" / "civilization").mkdir(parents=True)
    (backend / "app" / "civilization" / "one_brain_cycle.py").write_text(
        "# born tonight\n")
    report = ab.sweep(backend, now=now, runner=Machine(born={
        "apex-council.service": "Mon 2026-10-12 09:00:00 UTC",
    }), write=False)
    assert "organs_reborn" in report["warned"]
    check = next(c for c in report["checks"] if c["name"] == "organs_reborn")
    assert "apex-council.service" in check["detail"], check["detail"]
    assert "one_brain_cycle.py" in check["detail"], check["detail"]


def test_a_reborn_process_meets_its_organs():
    # born an hour from now (Machine's fresh dial): the body meets every
    # organ its code has grown
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "app" / "civilization").mkdir(parents=True)
    (backend / "app" / "civilization" / "one_brain_cycle.py").write_text(
        "# born tonight\n")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "organs_reborn")
    assert check["ok"], check["detail"]
    assert "born after the code it carries" in check["detail"]


def test_a_machine_that_does_not_speak_systemd_abstains():
    # the ward's systemd is silent: honesty is an abstention, never a guess
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now,
                      runner=Machine(born={"apex-council.service": "MUTE",
                                           "apex-hyperfeed.service": "MUTE",
                                           "apex-queue.service": "MUTE",
                                           "apex-hawk-eye.service": "MUTE"}),
                      write=False)
    check = next(c for c in report["checks"] if c["name"] == "organs_reborn")
    assert check["ok"], check["detail"]
    assert "abstention" in check["detail"], check["detail"]


def test_only_the_service_own_code_counts():
    # precision: the market's rebirth (hyperfeed) does not stale the
    # council -- each organ answers only for the roots it carries
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "app" / "market").mkdir(parents=True)
    (backend / "app" / "market" / "hyperfeed.py").write_text("# reborn\n")
    report = ab.sweep(backend, now=now, runner=Machine(born={
        "apex-council.service": "Mon 2026-10-12 09:00:00 UTC",
        "apex-hyperfeed.service": "Mon 2026-10-12 09:00:00 UTC",
    }), write=False)
    check = next(c for c in report["checks"] if c["name"] == "organs_reborn")
    assert not check["ok"]
    assert "apex-hyperfeed.service" in check["detail"], check["detail"]
    assert "apex-council.service" not in check["detail"], check["detail"]


def test_a_disabled_heart_timer_is_watched():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now,
                      runner=Machine(timer="mask"), write=False)
    assert "heart_scheduled" in report["warned"]


def test_the_mouth_that_went_silent_is_watched():
    # R113's clock: an artifact older than three turns (45 min) is silence
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    stale = now - dt.timedelta(minutes=90)
    (backend / "signal_live.json").write_text(json.dumps(
        {"ts": stale.strftime("%Y-%m-%dT%H:%M:%SZ")}))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "mouth_alive" in report["warned"]
    assert "mouth_alive" not in report["failed"]   # a warn, said aloud


def test_the_unborn_mouth_is_graced_on_its_birth_day():
    now = dt.datetime(2026, 10, 20, 23, 30, tzinfo=dt.timezone.utc)
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "signal_live.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "mouth_alive")
    assert check["ok"] is True          # SOFT: an unborn sensor is emptiness


def test_the_mouth_joins_the_roll_of_clocks():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    check = next(c for c in report["checks"] if c["name"] == "heart_scheduled")
    assert check["ok"] is True
    # R113 put the mouth on the roll; R118 put the historian on it (seven)
    assert "seven organs" in check["detail"]


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


# ---------------------------------------------------------------------------
# R118 -- THE HISTORIAN'S CLOCK (the deep frame's age, as the organ told it)
# ---------------------------------------------------------------------------
def _health(backend: Path, now: dt.datetime, **over):
    doc = {
        "version": 1, "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": "healthy",
        "pairs": {"EURUSD": {"edge_ts": int(now.timestamp()) - 3600,
                             "edge_age_s": 3600, "verdict": "fresh"}},
    }
    doc.update(over)
    (backend / "history_health.json").write_text(json.dumps(doc))


def test_a_silent_historian_is_a_watch_after_its_birth():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "history_health.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "history_edge" in report["warned"]


def test_a_stale_voice_is_a_watch():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _health(backend, now - dt.timedelta(days=3))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "history_edge" in report["warned"]


def test_a_fossilizing_edge_is_a_watch():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _health(backend, now, pairs={"EURUSD": {
        "edge_ts": int(now.timestamp()) - 200 * 3600,
        "edge_age_s": 200 * 3600, "verdict": "stale"}})
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "history_edge" in report["warned"]


def test_a_voice_that_lies_about_the_body_is_a_watch():
    import pandas as pd
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    # the REAL parquet edge disagrees with the artifact's claim
    pq_dir = backend / "data" / "history"
    pq_dir.mkdir(parents=True)
    real_edge = int(now.timestamp()) - 7200
    pd.DataFrame({"ts": [real_edge], "open": [1.1], "high": [1.11],
                  "low": [1.09], "close": [1.1], "volume": [5.0]}
                 ).to_parquet(pq_dir / "EURUSD_M15.parquet", index=False)
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "history_edge" in report["warned"]


def test_seven_organ_clocks_are_asked_by_name():
    """R118: the historian's timer joins the organs' census."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "heart_scheduled" not in report["warned"]
    # the spoken diagnosis names all seven clocks, the historian included
    msg = [c["detail"] for c in report["checks"] if c["name"] == "heart_scheduled"][0]
    assert "seven organs" in msg
    assert "apex-historian.timer: enabled" in msg


# ---------------------------------------------------------------------------
# R121 -- THE SCAR TISSUE (the body remembers, the tripwires resolve)
# ---------------------------------------------------------------------------
def test_a_silent_registry_is_amnesia_after_the_birth():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "scars.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "scars_alive" in report["warned"]


def test_a_torn_registry_is_spoken():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "scars.json").write_text("{torn json")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "scars_alive" in report["warned"]


def test_a_scar_whose_tripwire_vanished_is_an_alarm():
    """A law removed while the wound it guards still has a name."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "scars.json").write_text(json.dumps({
        "version": 1,
        "scars": [{
            "id": "S-GHOST", "born": "2026-10-21", "organ": "ward",
            "wound": "a scar guarded by a law that no longer exists",
            "guard": "a removed revolution",
            "tripwire": {"kind": "check", "name": "a_check_that_was_deleted"},
        }],
    }))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "scars_alive" in report["warned"]


def test_a_retired_scar_rests_with_honour():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "scars.json").write_text(json.dumps({
        "version": 1,
        "scars": [{
            "id": "S-OLD", "born": "2026-10-21", "organ": "ward",
            "wound": "a wound long healed",
            "guard": "a revolution that became the body itself",
            "tripwire": {"kind": "check", "name": "a_check_that_was_deleted"},
            "retired": "2026-10-22",
        }],
    }))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "scars_alive" not in report["warned"]
    msg = [c["detail"] for c in report["checks"] if c["name"] == "scars_alive"][0]
    assert "remembers 0 wounds" in msg and "1 retired with honour" in msg


# ---------------------------------------------------------------------------
# R126 -- THE GENEALOGIST (the blood book breathes, the census speaks)
# ---------------------------------------------------------------------------
def test_a_mute_genealogist_is_spoken_after_the_birth():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_genealogy_heart.json").unlink()
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "genealogy_alive" in report["warned"]


def test_a_torn_census_is_spoken():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "factory_genealogy_turbo.json").write_text("{torn json")
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "genealogy_alive" in report["warned"]


def test_a_one_blood_census_without_the_brake_is_an_alarm():
    """The measurement is honest... but the medicine never ran: a wiring
    wound, not a verdict."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _art = json.loads((backend / "factory_genealogy_heart.json").read_text())
    _art["verdict"] = "one-blood"
    _art["brake"] = {"applied": False}
    (backend / "factory_genealogy_heart.json").write_text(json.dumps(_art))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "genealogy_alive" in report["warned"]
    msg = [c["detail"] for c in report["checks"]
           if c["name"] == "genealogy_alive"][0]
    assert "brake never fired" in msg


def test_a_one_blood_census_with_the_brake_engaged_is_healing_not_failure():
    """One-blood WITH the brake is the organism healing -- spoken aloud,
    never a failure (the verdict is a measurement, not a sin)."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _art = json.loads((backend / "factory_genealogy_heart.json").read_text())
    _art["verdict"] = "one-blood"
    _art["brake"] = {"applied": True, "sibling_mates_avoided": 12,
                     "immigrants": 4}
    (backend / "factory_genealogy_heart.json").write_text(json.dumps(_art))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "genealogy_alive" not in report["warned"]
    msg = [c["detail"] for c in report["checks"]
           if c["name"] == "genealogy_alive"][0]
    assert "il sangue" in msg and "freno acceso" in msg


def test_a_stale_census_is_spoken():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _art = json.loads((backend / "factory_genealogy_vault.json").read_text())
    _art["ts"] = int(now.timestamp()) - 13 * 3600   # older than four turns
    (backend / "factory_genealogy_vault.json").write_text(json.dumps(_art))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "genealogy_alive" in report["warned"]


def test_an_empty_census_is_a_counter_that_forgot():
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    _art = json.loads((backend / "factory_genealogy_heart.json").read_text())
    _art["bodies"] = 0
    (backend / "factory_genealogy_heart.json").write_text(json.dumps(_art))
    report = ab.sweep(backend, now=now, runner=Machine(), write=False)
    assert "genealogy_alive" in report["warned"]


def test_the_real_registry_on_the_real_tree():
    """The committed scars.json itself: every wound whole, every tripwire
    resolving against the REAL check names and the REAL test files.

    The public engine mirror (a DERIVED artifact) does not carry the
    organism's biography -- in that environment this proof skips, exactly
    like the data-manifest proof skips without tapes. A scar registry that
    is absent is not a lie; it is another body's bookshelf."""
    from app.factory.scars import verify_scars
    backend = Path(__file__).resolve().parents[2]
    if not (backend / "scars.json").exists():
        pytest.skip("the scar registry is not present in this environment")
    names = {name for name, _sev, _fn in ab.CHECKS}
    scars, complaints = verify_scars(backend, check_names=names)
    assert len(scars) >= 10, "the organism's biography must be present"
    assert complaints == [], complaints


# ---------------------------------------------------------------------------
# R149 — THE VAULT'S HYGIENE (the guardian's 19th eye: backups are not
# history, keys are not cargo, and a standing key house must have its lock)
# ---------------------------------------------------------------------------

def test_a_tracked_backup_generation_wounds():
    """The heart's rotating *.bakN.json tracked in the vault: not history."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "civilization_state.bak1.json").write_text("{}")
    subprocess.run(["git", "add", "-A"], cwd=backend, check=True)
    subprocess.run(["git", "commit", "-qm", "bak enters"], cwd=backend,
                   check=True)
    ok, detail = ab._check_vault_hygienic(backend, {"runner": Machine()})
    assert not ok and "backup" in detail, detail


def test_a_tracked_key_file_wounds():
    """sage.env tracked in the vault: a live credential is a leak one push
    away -- the vault must never carry it, whatever the pipes do."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "sage.env").write_text("SAGE_API_KEY=sk-never-printed\n")
    subprocess.run(["git", "add", "-A"], cwd=backend, check=True)
    subprocess.run(["git", "commit", "-qm", "key enters"], cwd=backend,
                   check=True)
    ok, detail = ab._check_vault_hygienic(backend, {"runner": Machine()})
    assert not ok and "key" in detail, detail


def test_a_standing_key_house_without_its_lock_wounds():
    """The near-miss of 2026-10-23, made impossible: the key's house on disk
    (untracked) while the vault's .gitignore does not name it -- one careless
    'git add -A' swallows a live key into history."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "sage.env").write_text("SAGE_API_KEY=sk-never-printed\n")
    ok, detail = ab._check_vault_hygienic(backend, {"runner": Machine()})
    assert not ok and "gitignore" in detail, detail


def test_a_locked_key_house_rounds_clean():
    """The same standing house, now named in the lock: hygiene is whole."""
    now = _now()
    backend = _healthy_ward(_tmp(), now=now)
    (backend / "sage.env").write_text("SAGE_API_KEY=sk-never-printed\n")
    (backend / ".gitignore").write_text("sage.env\n")
    ok, detail = ab._check_vault_hygienic(backend, {"runner": Machine()})
    assert ok, detail


def test_hygiene_abstains_when_git_is_silent():
    """No vault, no verdict: outside git the eye abstains honestly (the
    seed-check's own doctrine -- a judge who cannot see cannot condemn)."""
    def deaf(cmd, cwd=None):
        return 1, ""
    ok, detail = ab._check_vault_hygienic(Path("/tmp"), {"runner": deaf})
    assert ok and "abstains" in detail, detail
