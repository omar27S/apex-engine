"""THE ANTI-BUG GUARDIAN -- the examiner that never sleeps.

The Boss ordered an anti-bug "that works always" (2026-10-20). A test suite is
a court that convenes on demand; the organism needs a PHYSICIAN who rounds the
wards every half hour, at every heartbeat, and at the Grand's dawn -- checking
the vital signs, healing what can be healed REVERSIBLY, and writing the visit
into a ledger of its own.

Twelve checks (one per law of the Director's DNA, in spirit):

* ledger_sealed   -- every recent factory row carries the dna seal (fail);
* ledger_alive    -- the heart appended at least one row today (warn: a young
                     day may simply not have beaten yet);
* seed_arithmetic -- the rotating seed advances by whole strides of 7919
                     (warn: a manual turn or a CI overlap can interleave;
                     a same-machine repeat is the SAME turn written twice,
                     and is named what it is -- an append whose push died
                     and a re-run that redrew the deterministic seed);
* pantry_honest   -- every pantry parses, digest-verifies and holds no ghost
                     (fail: Law 3 -- the pantry is the evolution's memory);
* pantry_tracked  -- every pantry is under git (fail: an untracked pantry is
                     one VM death away from amnesia -- the wound this guardian
                     was born from);
* state_parse     -- the civilization's state files parse as JSON (fail);
* falcon_fresh    -- the eye's reading is younger than nine missed beats (warn);
* disk_floor      -- the machine has room to breathe (fail at < 1 GiB);
* heart_scheduled -- the heart's timer is enabled (warn);
* letter_of_dawn  -- after the Grand's hour, today's letter exists (warn until
                     noon, fail after: the CEO must not read silence);
* dd_ledger_grown -- since the D3 law landed, the account's memory of pain
                     exists and grew each night (read THROUGH the dd_ledger
                     module's load_ledger contract -- the writer's true shape
                     is a JSON list, and a physician who re-parses the
                     patient with his own eyes calls healthy tissue a
                     tumour); warn through the first transition day, fail
                     after;
* hyperfeed_alive -- the live wire's snapshot is fresh (warn: the wire is the
                     FAST eye -- a quiet wire is a sleeping sensor, and the
                     systemd unit restarts it on its own; unborn until the
                     service's first install is SOFT, not a wound).
And the standing doctrine:

* quarantine_only -- the guardian NEVER touches the append-only factory ledger;
                     it heals pantries and state files only, by quarantine +
                     git-restore (reversible by design).

Fail-open doctrine: a sweep error is recorded, never raised -- the guardian
must round the wards again, not die on a gurney of its own. The one thing it
never does is stop the heart: sweeps are best-effort passengers, never gates.

CLI:  python -m app.factory.anti_bug [--backend DIR] [--json]
Exit code 1 only when a FAIL-severity check is wounded (and unhealed).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

__all__ = [
    "SCHEMA", "LEDGER_NAME", "LEDGER_MAX_ROWS", "DISK_FLOOR_MB",
    "FALCON_MAX_AGE_S", "GUARDIAN_START", "ISLANDS", "QUARANTINE_DIR",
    "sweep", "heal_pantry", "append_ledger", "load_ledger_tail", "main",
]

SCHEMA = 1
LEDGER_NAME = "anti_bug_ledger.jsonl"
LEDGER_MAX_ROWS = 500
DISK_FLOOR_MB = 1024
# The falcon timer beats every 5 minutes; nine missed beats (45 min) is a
# sleeping eye, not a blink (D4 taught the difference between cadence and life).
FALCON_MAX_AGE_S = 45 * 60
# THE LIVE WIRE (hyperfeed): the daemon snapshots every 20 s, so 15 minutes
# of silence is a wire gone quiet (three orders of magnitude beyond the
# falcon's patience -- the fast eye must answer fast).
HYPERFEED_MAX_AGE_S = 15 * 60
HYPERFEED_FILE = "hyperfeed.json"
# The day the live wire was born (2026-10-20). Before it the check is UNBORN
# (SOFT), mirroring the dd ledger's transition-day doctrine.
HYPERFEED_BIRTH = _dt.date(2026, 10, 20)
QUARANTINE_DIR = "quarantine"
# The day the D3 law was consecrated (2026-10-20); the dd ledger's first honest
# night is the Grand of 2026-10-21. Before that date the check is unborn.
GUARDIAN_START = _dt.date(2026, 10, 20)
# The Grand's letter hour (UTC). A missing letter is a sleepy dawn until noon,
# a wound after it.
LETTER_GRACE_UNTIL_HOUR = 12
ISLANDS: tuple[str, ...] = ("heart", "turbo", "vault")
STATE_FILES = ("civilization_state.json", "apex_state.json", "falcon.json")
SEED_STRIDE = 7919
SEED_SPAN = 1 << 30

VERDICT_CLEAN, VERDICT_WOUNDS, VERDICT_HEALED = "clean", "wounds", "healed"
# Check voices: a detail opening with WOUND: escalates its check to fail-severity
# no matter the registry (the dawn's silence past noon is not a watch-item);
# SOFT: demotes to warn (an unborn memory is emptiness, not a lie).
ESCALATE_WOUND, DEMOTE_SOFT = "WOUND:", "SOFT:"


# ---------------------------------------------------------------------------
# the runner: how the guardian asks the machine (injectable for the tests)
# ---------------------------------------------------------------------------
def _default_runner(cmd: list[str], cwd: Path | None = None):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=60)
    return proc.returncode, proc.stdout


def _no_runner(cmd: list[str], cwd: Path | None = None):
    return 127, ""


# ---------------------------------------------------------------------------
# honest readers
# ---------------------------------------------------------------------------
def _read_json(path: Path):
    try:
        return True, json.loads(path.read_text())
    except (OSError, ValueError):
        return False, None


def _ledger_rows(backend: Path) -> list[dict]:
    path = backend / "factory_ledger.jsonl"
    rows: list[dict] = []
    if not path.exists():
        return rows
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue  # a torn line is skipped, never guessed
    except OSError:
        pass
    return rows


def _seed_of(note: str) -> int | None:
    for chunk in str(note or "").split():
        if chunk.startswith("seed="):
            try:
                return int(chunk[5:])
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# the checks: each returns (ok, detail); severity lives in the registry
# ---------------------------------------------------------------------------
def _check_ledger_sealed(backend: Path, ctx: dict) -> tuple[bool, str]:
    rows = ctx["ledger_rows"]
    if not rows:
        return False, "the factory ledger is empty or absent"
    # The LAST FIVE rows are the ward's present -- they must carry the seal.
    # Older rows are history: the dna seal became law mid-morning 2026-10-20,
    # and the rows written before it are honest history, not unsigned words
    # (a physician reads the chart, not the museum).
    recent = rows[-5:]
    for row in recent:
        note = str(row.get("note") or "")
        machine = str(row.get("machine") or "")
        if "dna=" not in note:
            return False, (f"row of {row.get('date')} ({machine}) carries no "
                           f"dna seal -- an unsigned word")
        if machine and machine not in ISLANDS:
            return False, f"unknown island {machine!r} in the ledger"
    return True, f"{len(recent)} recent rows sealed"


def _check_ledger_alive(backend: Path, ctx: dict) -> tuple[bool, str]:
    today = str(ctx["now"].date())
    rows = [r for r in ctx["ledger_rows"]
            if str(r.get("date") or "") == today]
    if rows:
        return True, f"{len(rows)} shifts today"
    return False, "no shift appended today yet (the heart may not have beaten)"


def _check_seed_arithmetic(backend: Path, ctx: dict) -> tuple[bool, str]:
    # R132: the rows keep their full note so a repeat can be NAMED. Two rows
    # with the same seed are two different wounds: same machine = the SAME
    # turn written twice (an append whose push died, then a re-run redrew
    # the deterministic seed -- stride arithmetic makes every island's next
    # seed predictable, so a re-run from the same state redraws the same
    # evolution); different machines = two honest clock-siblings (the CI
    # twin and the VM body) interleaving turns. The guardian's job is to
    # say WHICH twin is crying, not to guess.
    rows = [(_seed_of(str(r.get("note") or "")), r.get("machine"))
            for r in ctx["ledger_rows"][-6:]]
    seeds = [(s, m) for s, m in rows if s is not None]
    if len(seeds) < 2:
        return True, "fewer than two seeded rows to judge (honest abstention)"
    bad = None
    for (prev, prev_machine), (nxt, machine) in zip(seeds, seeds[1:]):
        delta = (nxt - prev) % SEED_SPAN
        if delta == 0:
            if machine == prev_machine:
                bad = (f"seed {nxt} repeats on the same machine ({machine}) "
                       f"-- the same turn was written twice: an append whose "
                       f"push died, then a re-run redrew the deterministic "
                       f"seed")
            else:
                bad = (f"seed {nxt} repeats across machines ({prev_machine} "
                       f"-> {machine}) -- two turns drew the same evolution "
                       f"(concurrent CI + VM run?)")
            break
        if delta % SEED_STRIDE != 0:
            bad = (f"seed stride {delta} is not a whole multiple of "
                   f"{SEED_STRIDE} ({machine})")
            break
    if bad:
        return False, bad
    return True, f"{len(seeds)} seeded rows advance by whole strides"


def _check_pantry_honest(backend: Path, ctx: dict) -> tuple[bool, str]:
    from app.factory import dna as dna_mod
    from app.factory import islands as islands_mod

    found = 0
    for island in ISLANDS:
        path = backend / f"factory_champions_{island}.json"
        if not path.exists():
            continue
        found += 1
        ok, payload = _read_json(path)
        if not ok or not isinstance(payload, dict):
            return False, f"{path.name} does not parse -- the pantry is torn"
        try:
            islands_mod.verify_migration(payload)
        except Exception as exc:  # MigrationError and friends
            return False, f"{path.name} fails its own digest: {exc}"
        entries = payload.get("champions") or []
        keep, refused = dna_mod.honest_champions(entries)
        if refused:
            return False, (f"{path.name} holds {refused} ghost champion(s) "
                           f"-- unmeasured entries posing as memory")
        for entry in keep:
            wilson = entry.get("wilson_lb")
            try:
                wilson = float(wilson)
            except (TypeError, ValueError):
                return False, f"{path.name}: wilson_lb is not a number"
            if not -1.0 <= wilson <= 1.0:
                return False, (f"{path.name}: wilson_lb {wilson} outside "
                               f"[-1, 1] -- not a bound, an invention")
    if not found:
        return False, (f"{DEMOTE_SOFT} no pantry exists yet "
                       f"(the memory has not been written)")
    return True, f"{found} pantry/pantries honest"


def _check_pantry_tracked(backend: Path, ctx: dict) -> tuple[bool, str]:
    runner = ctx["runner"]
    for island in ISLANDS:
        name = f"factory_champions_{island}.json"
        path = backend / name
        if not path.exists():
            continue
        rc, _ = runner(["git", "ls-files", "--error-unmatch", name], cwd=backend)
        if rc != 0:
            return False, (f"{name} is not under git -- one VM death away "
                           f"from amnesia (publish the pantry, R101)")
    return True, "every existing pantry is tracked"


def _check_state_parse(backend: Path, ctx: dict) -> tuple[bool, str]:
    for name in STATE_FILES:
        path = backend / name
        if not path.exists():
            continue
        ok, payload = _read_json(path)
        if not ok or payload in (None, {}, []):
            return False, f"{name} is absent-minded (unparsable or empty)"
    return True, "state files parse"


def _check_falcon_fresh(backend: Path, ctx: dict) -> tuple[bool, str]:
    path = backend / "falcon.json"
    if not path.exists():
        return False, "falcon.json is absent -- the eye never wrote"
    try:
        age = ctx["now"].timestamp() - path.stat().st_mtime
    except OSError:
        return False, "falcon.json cannot be stat-ed"
    if age > FALCON_MAX_AGE_S:
        return False, (f"falcon.json is {int(age / 60)} min old "
                       f"(> {FALCON_MAX_AGE_S // 60} min) -- the eye sleeps")
    return True, f"the eye read {int(age / 60)} min ago"


def _check_disk_floor(backend: Path, ctx: dict) -> tuple[bool, str]:
    rc, out = ctx["runner"](["df", "-m", "--output=avail", str(backend)])
    if rc != 0:
        return False, "df refused to answer"
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    try:
        free_mb = int(lines[-1])
    except (ValueError, IndexError):
        return False, "df's answer was not a number"
    if free_mb < DISK_FLOOR_MB:
        return False, f"only {free_mb} MiB free (< {DISK_FLOOR_MB})"
    return True, f"{free_mb} MiB free"


def _check_heart_scheduled(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R109 -- THE ORGANS' CLOCKS, ALL OF THEM (not the heart alone).

    The 2026-10-20 lesson: a reconnaissance that looked only where it
    expected life (``systemctl --user`` while the organs live at SYSTEM
    level) nearly declared a healthy organism comatose. The inverse wound is
    worse: an organ's timer disabled or lost while its siblings beat on --
    the body lives, one sense dies silently. So the guardian asks EVERY
    organ's clock, one by one, and speaks each answer by name: the heart
    (the evolution's turns), the grand (the night's whole civilization), the
    guardian itself (the watcher watches the watcher), the falcon (the slow
    eye) -- and the live wire's service (the fast eye, always-on, not a
    timer). A missing unit file ('not-found') is the gravest answer: a
    clock that no longer exists cannot be re-enabled by hope.
    """
    runner = ctx["runner"]
    verdicts: list[str] = []
    wounded: list[str] = []
    for unit in ("apex-heart.timer", "apex-grand.timer",
                 "apex-guardian.timer", "apex-falcon.timer",
                 "apex-mouth.timer",
                 "apex-historian.timer"):
        rc, out = runner(["systemctl", "is-enabled", unit])
        state = out.strip().lower()
        if rc == 0 and state == "enabled":
            verdicts.append(f"{unit}: enabled")
        else:
            wounded.append(f"{unit} answers '{state or 'silence'}'")
    rc, out = runner(["systemctl", "is-active", "apex-hyperfeed.service"])
    state = out.strip().lower()
    if rc == 0 and state == "active":
        verdicts.append("apex-hyperfeed.service: active")
    else:
        wounded.append(f"apex-hyperfeed.service answers '{state or 'silence'}'")
    if wounded:
        return False, "; ".join(wounded)
    return True, "all seven organs' clocks answer: " + ", ".join(verdicts)


def _check_letter_of_dawn(backend: Path, ctx: dict) -> tuple[bool, str]:
    now = ctx["now"]
    if now.hour < 5:
        return True, "the Grand has not yet run (before 05:00 UTC)"
    root = backend.parent
    letter = root / "letters" / f"lettera_{now.date()}.md"
    if letter.exists():
        return True, f"{letter.name} waits on the CEO's desk"
    if now.hour < LETTER_GRACE_UNTIL_HOUR:
        return False, "today's letter has not been written yet (grace until noon)"
    return False, (f"{ESCALATE_WOUND} today's letter is MISSING past noon -- "
                   f"the CEO reads silence, which is the one lie the dawn "
                   f"cannot tell")


def _check_dd_ledger_grown(backend: Path, ctx: dict) -> tuple[bool, str]:
    now = ctx["now"]
    if now.date() <= GUARDIAN_START:
        return True, "the D3 law is unborn (consecrated 2026-10-20)"
    path = backend / "dd_ledger.json"
    if not path.exists():
        # The first honest night is the Grand of the 21st; until then, a warn.
        if now.date() <= GUARDIAN_START + _dt.timedelta(days=1):
            return False, ("SOFT: dd_ledger.json not yet written (first honest "
                           "night pending -- transition grace)")
        return False, (f"{ESCALATE_WOUND} dd_ledger.json is MISSING -- the "
                       f"account forgot its pain")
    # R132 -- THE CONTRACT, NOT A SECOND OPINION: this check once re-parsed
    # the ledger with its own eyes (``isinstance(payload, dict)`` + a
    # ``nights`` key) while the writer's TRUE shape -- what grand_night has
    # written since the first honest night -- is a JSON LIST, exactly what
    # load_ledger() has accepted from birth. For three hours the guardian
    # called healthy tissue "does not parse" while the account's memory
    # was perfectly whole. The writer and the reader share ONE contract
    # now: the guardian reads THROUGH the module, never past it, and the
    # verdict speaks the number the memory holds (the accumulated DD),
    # not just its row count.
    from app.state import dd_ledger as dd_mod
    nights = dd_mod.load_ledger(path)
    if not nights:
        ok, _payload = _read_json(path)
        if not ok:
            return False, (f"{ESCALATE_WOUND} dd_ledger.json is unreadable -- "
                           f"the pain is written in a language no organ "
                           f"shares")
        return False, "SOFT: dd_ledger.json holds no night yet (transition grace)"
    dd = dd_mod.accumulated_dd(nights)
    dd_voice = "unmeasured" if dd is None else f"{dd:.2f}R"
    return True, (f"{len(nights)} night(s) of pain remembered, accumulated "
                  f"drawdown {dd_voice}")


# (name, severity, fn) -- severity: "fail" wounds the verdict, "warn" records
def _check_hyperfeed_alive(backend: Path, ctx: dict) -> tuple[bool, str]:
    """The live wire's clock: is hyperfeed.json fresh?

    The daemon writes a snapshot every 20 seconds; the guardian reads the
    snapshot's OWN ``ts`` first (the machine's mtime lies when a file is
    copied) and falls back to the mtime when the clock is unreadable. The
    wire is new-born: before its first install the check is SOFT (an unborn
    sensor is emptiness, not a lie), and after that a quiet wire is a WARN
    -- the unit restarts itself, and the guardian's job is to SAY it, not
    to amputate what it has not studied.
    """
    path = backend / HYPERFEED_FILE
    if not path.exists():
        if ctx["now"].date() <= HYPERFEED_BIRTH:
            return True, "SOFT: the live wire is not installed yet (birth day)"
        return False, "hyperfeed.json is absent -- the wire never wrote"
    age = None
    try:
        data = json.loads(path.read_text())
        ts = (data or {}).get("ts")
        if isinstance(ts, (int, float)):
            age = ctx["now"].timestamp() - float(ts)
    except (OSError, ValueError, TypeError):
        pass
    if age is None:
        try:
            age = ctx["now"].timestamp() - path.stat().st_mtime
        except OSError:
            return False, "hyperfeed.json cannot be read or stat-ed"
    if age > HYPERFEED_MAX_AGE_S:
        return False, (f"the live wire went quiet {int(age / 60)} min ago "
                       f"(> {HYPERFEED_MAX_AGE_S // 60} min) -- the fast eye sleeps")
    return True, f"the live wire is fresh ({int(age)} s since its snapshot)"


MOUTH_FILE = "signal_live.json"
# R113's organ was born 2026-10-20 (the mouth's first live words, 23:04 UTC).
MOUTH_BIRTH = _dt.date(2026, 10, 20)
GENEALOGY_BIRTH = _dt.date(2026, 10, 21)   # R126: the genealogist is born
GENEALOGY_MAX_AGE_S = 12 * 3600            # four turns of the heart
# The mouth speaks every 15 minutes; three missed turns (45 min) is silence.
MOUTH_MAX_AGE_S = 45 * 60


def _check_mouth_alive(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R113's clock: did the mouth speak recently?

    The mouth writes ``signal_live.json`` EVERY turn -- speaking or honestly
    blind, the artifact is the organ's heartbeat (a blind turn still says
    "la bocca tace" with a fresh stamp). The guardian reads the artifact's
    OWN ``ts`` first (an ISO stamp, not epoch -- the mouth speaks ISO like
    every CLI organ) and falls back to the mtime. Quiet longer than three
    turns means the timer died or the organ hangs: a WARN, said aloud (the
    signal cadence the Boss ordered is the body's newest sense -- its death
    must never be silent). Birth-day softness like the wire's: an unborn
    sensor is emptiness, not a lie.
    """
    path = backend / MOUTH_FILE
    if not path.exists():
        if ctx["now"].date() <= MOUTH_BIRTH:
            return True, "SOFT: the mouth is not installed yet (birth day)"
        return False, "signal_live.json is absent -- the mouth never spoke"
    age = None
    try:
        data = json.loads(path.read_text())
        ts = (data or {}).get("ts")
        if isinstance(ts, str) and ts:
            stamp = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age = ctx["now"].timestamp() - stamp.timestamp()
    except (OSError, ValueError, TypeError):
        pass
    if age is None:
        try:
            age = ctx["now"].timestamp() - path.stat().st_mtime
        except OSError:
            return False, "signal_live.json cannot be read or stat-ed"
    if age > MOUTH_MAX_AGE_S:
        return False, (f"the mouth went quiet {int(age / 60)} min ago "
                       f"(> {MOUTH_MAX_AGE_S // 60} min) -- no live signal turns")
    return True, f"the mouth spoke recently ({int(age)} s since its turn)"


HISTORY_HEALTH_FILE = "history_health.json"
# R118's organ was born 2026-10-20 (the historian's first healing round).
HISTORIAN_BIRTH = _dt.date(2026, 10, 20)
# The healer speaks daily at 02:37 UTC; a voice older than 26h is a missed
# round. The FRAME may honestly age through a weekend (72h market closure
# plus the supply's lag): the organism is declared wounded at FIVE days.
HISTORY_ARTIFACT_MAX_AGE_S = 26 * 3600
HISTORY_EDGE_MAX_AGE_S = 120 * 3600


def _check_history_edge(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R118's clock: the deep frame's age, as the historian told it.

    The guardian reads the ORGAN'S OWN VOICE (history_health.json, spoken
    every healing round and committed with the state files) -- it never
    re-derives what an organ can simply tell it. Three questions, in order:
    (1) did the organ speak at all (a missing artifact on the birth day is
    emptiness, not a lie; after that it is silence); (2) is the VOICE fresh
    (a day-old health report guards nothing); (3) is the FRAME alive (the
    oldest pair's edge younger than five days -- past any weekend, past any
    single holiday, past the supply's own lag). One truth-probe rides along:
    the EURUSD parquet's REAL last ts must agree with the artifact's claim
    -- the guardian trusts, and verifies the easiest thing it can measure.
    """
    path = backend / HISTORY_HEALTH_FILE
    if not path.exists():
        if ctx["now"].date() <= HISTORIAN_BIRTH:
            return True, "SOFT: the historian is not installed yet (birth day)"
        return False, "history_health.json is absent -- the historian never spoke"
    try:
        health = json.loads(path.read_text())
    except (OSError, ValueError):
        return False, "history_health.json cannot be parsed -- a torn voice"
    ts = health.get("ts")
    if not isinstance(ts, str) or not ts:
        return False, "history_health.json carries no ts -- a voice without a clock"
    try:
        stamp = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False, f"history_health.json ts is not ISO: {ts!r}"
    voice_age = ctx["now"].timestamp() - stamp.timestamp()
    if voice_age > HISTORY_ARTIFACT_MAX_AGE_S:
        return False, (f"the historian's voice is {int(voice_age / 3600)}h old "
                       f"(> {HISTORY_ARTIFACT_MAX_AGE_S // 3600}h) -- the healing "
                       f"round is not running")
    pairs = health.get("pairs") or {}
    if not isinstance(pairs, dict) or not pairs:
        return False, "history_health.json speaks of no pairs -- an empty census"
    oldest_pair, oldest_age = None, -1
    for name, rep in pairs.items():
        if not isinstance(rep, dict):
            continue
        edge_age = rep.get("edge_age_s")
        if isinstance(edge_age, (int, float)) and edge_age > oldest_age:
            oldest_pair, oldest_age = name, edge_age
    if oldest_pair is None:
        return False, "no pair reports an edge age -- the census forgot to count"
    if oldest_age > HISTORY_EDGE_MAX_AGE_S:
        return False, (f"the deep frame is fossilizing: {oldest_pair}'s edge is "
                       f"{int(oldest_age / 3600)}h old (> "
                       f"{HISTORY_EDGE_MAX_AGE_S // 3600}h)")
    # the truth-probe: read the REAL parquet edge of one pair
    try:
        import pandas as _pd
        pq = backend / "data" / "history" / "EURUSD_M15.parquet"
        real_edge = int(_pd.read_parquet(pq, columns=["ts"])["ts"].iloc[-1])
        claimed = int((pairs.get("EURUSD") or {}).get("edge_ts", real_edge))
        if claimed != real_edge:
            return False, (f"the artifact claims EURUSD edge {claimed} but the "
                           f"parquet says {real_edge} -- a voice that disagrees "
                           f"with the body")
    except Exception:
        pass  # a probe that cannot run is not a lie; the voice was already read
    return True, (f"the deep frame lives: oldest edge {oldest_pair} at "
                  f"{int(oldest_age / 3600)}h, voice {int(voice_age / 3600)}h old")


def _check_scars_alive(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R121 -- THE SCAR TISSUE's pulse: the body remembers, and every
    memory still points at a living law.

    The registry (scars.json, committed with the state files) carries every
    wound the organism has ever suffered, each with a TRIPWIRE -- the name
    of the mechanism that must fire if the wound returns. The guardian
    verifies: the file parses, every scar is whole, every tripwire
    RESOLVES (a registered check, an existing test, a live timer). A scar
    whose tripwire has vanished is an alarm: a law was removed while the
    wound it guards still has a name. An ABSENT registry on the birth day
    is emptiness, not a lie; after that it is amnesia.
    """
    from app.factory.scars import census, verify_scars
    path = backend / "scars.json"
    if not path.exists():
        if ctx["now"].date() <= _dt.date(2026, 10, 21):
            return True, "SOFT: the scar tissue is not yet written (birth day)"
        return False, "scars.json is absent -- the organism forgot its wounds"
    names = {name for name, _sev, _fn in CHECKS}
    scars, complaints = verify_scars(backend, check_names=names)
    if not scars:
        return False, "scars.json is present but carries no scars (torn or empty)"
    if complaints:
        return False, "; ".join(complaints[:3])
    stats = census(scars)
    return True, (f"the body remembers {stats['guarding']} wounds and every "
                  f"tripwire resolves ({stats['retired']} retired with honour)")


def _check_memory_quarantine(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R133 -- THE FOSSILS OF TORN MEMORY: said aloud, never swept away.

    The civilization's state now saves atomically and keeps three known-good
    generations (``*.bak1/2/3.json``); a file that could not parse is
    quarantined as ``*.torn.<ts>.json`` -- EVIDENCE, not garbage. This check
    is the guardian's voice for those fossils: a fresh one (younger than a
    day) means an organ saved and did not finish -- a warn said aloud; an
    old one is a fossil kept honestly (the body survived it, the evidence
    stays).
    """
    now = ctx["now"]
    torn = sorted(backend.glob("*.torn.*.json"))
    if not torn:
        return True, ("no torn-memory fossils (the atomic save keeps the "
                      "body whole)")
    fresh = []
    for p in torn:
        try:
            age = (now - _dt.datetime.fromtimestamp(
                p.stat().st_mtime, _dt.timezone.utc)).total_seconds()
        except OSError:
            continue
        if age < 86400:
            fresh.append(p.name)
    if fresh:
        return False, (f"{len(fresh)} torn-memory fossil(s) in the last day "
                       f"({', '.join(fresh[:3])}) -- an organ saved and did "
                       f"not finish; the quarantine kept the evidence and "
                       f"the memory restored from its generations")
    names = ", ".join(p.name for p in torn[-3:])
    return True, (f"{len(torn)} old torn-memory fossil(s) kept as evidence "
                  f"({names})")


# R135 -- THE BODY SHALL NOT CARRY A DEAD PAST: every always-on service and
# the code roots it carries. A long-lived process is a body frozen at its
# start time; every organ born after that freeze is INVISIBLE to it until
# it is reborn (the 2026-10-21 confession: the council ran nine days past
# one_brain_cycle's birth, and the One Brain never thought once).
ORGAN_CODE_ROOTS: dict[str, tuple[str, ...]] = {
    "apex-council.service": ("app/civilization", "app/state", "app/core",
                             "tools/council_cycle.py"),
    "apex-hyperfeed.service": ("app/market",),
    "apex-queue.service": ("tools/queue_daemon.py",),
    "apex-hawk-eye.service": ("tools/hawk_eye.py",),
}


def _check_organs_reborn(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R135 -- every always-on organ was born after the code it carries.

    The guardian asks each always-on service WHEN IT WAS BORN
    (``systemctl show -p ActiveEnterTimestamp``) and compares with the
    newest file in the code roots that service carries. A process born
    before its own code is a body carrying a dead past: the organs that
    landed after its start (a new cycle block, a new state module) can
    never run inside it -- the deploy doctrine says CODE LANDS, THE
    ORGANS THAT CARRY IT ARE REBORN IN THE SAME WAVE. A machine that
    does not speak systemd abstains honestly.
    """
    runner = ctx["runner"]
    stale, voices, asked = [], [], 0
    for unit, roots in ORGAN_CODE_ROOTS.items():
        rc, out = runner(["systemctl", "show", unit,
                          "-p", "ActiveEnterTimestamp", "--value"])
        stamp = out.strip()
        if rc != 0 or not stamp:
            continue  # a machine (or a ward) that does not speak abstains
        asked += 1
        try:
            born = _dt.datetime.strptime(
                stamp.rsplit(" ", 1)[0], "%a %Y-%m-%d %H:%M:%S")
        except ValueError:
            continue  # an unreadable clock is not a verdict
        born = born.replace(tzinfo=_dt.timezone.utc)
        newest, newest_name = 0.0, ""
        for root in roots:
            rp = backend / root
            paths = (rp.rglob("*.py") if rp.is_dir()
                     else ([rp] if rp.exists() else []))
            for p in paths:
                if "__pycache__" in p.parts:
                    continue
                m = p.stat().st_mtime
                if m > newest:
                    newest, newest_name = m, str(p.relative_to(backend))
        if not newest_name:
            continue
        code_born = _dt.datetime.fromtimestamp(newest, _dt.timezone.utc)
        if born < code_born:
            stale.append(unit)
            voices.append(f"{unit} was born {stamp} but its code was "
                          f"reborn at {code_born:%Y-%m-%d %H:%M:%S} UTC "
                          f"({newest_name})")
    if stale:
        return False, ("; ".join(voices)
                       + " -- a process frozen before its organs' birth can "
                         "never see them: rebirth it")
    if not asked:
        return True, ("no always-on service speaks systemd here (honest "
                      "abstention)")
    return True, "every always-on organ was born after the code it carries"


def _check_genealogy_alive(backend: Path, ctx: dict) -> tuple[bool, str]:
    """R126 -- THE GENEALOGIST'S PULSE: the blood book breathes, the census
    speaks, and the brake fires when it must.

    For every wheel island the census artifact (factory_genealogy_) and the
    blood book (factory_blood_) must exist after the birth-day grace and be
    younger than four turns.  A census that counts no bodies is a census
    that forgot to count; a verdict of ``one-blood`` with a brake that
    never fired is an ALARM -- the medicine exists and did not run (a
    wiring wound, not a measurement).  The verdict itself is never a
    failure: one-blood with the brake engaged is the organism healing,
    and it is SPOKEN so the CEO hears it.
    """
    from app.factory.islands import ISLAND_WHEEL
    if ctx["now"].date() <= GENEALOGY_BIRTH:
        return True, "SOFT: the genealogist is being born (birth day)"
    readings = []
    for island in ISLAND_WHEEL:
        art_p = backend / f"factory_genealogy_{island}.json"
        book_p = backend / f"factory_blood_{island}.json"
        if not art_p.exists() or not book_p.exists():
            return False, (f"the genealogist is mute: {island} has no "
                           "census or no blood book")
        try:
            art = json.loads(art_p.read_text())
            json.loads(book_p.read_text())
        except (OSError, ValueError):
            return False, f"{island}'s genealogy artifact is torn"
        ts = (art or {}).get("ts")
        if not isinstance(ts, (int, float)):
            return False, f"{island}'s census carries no timestamp"
        age = ctx["now"].timestamp() - float(ts)
        if age > GENEALOGY_MAX_AGE_S:
            return False, (f"{island}'s census is {int(age / 3600)}h old "
                           f"(> {GENEALOGY_MAX_AGE_S // 3600}h)")
        bodies = (art or {}).get("bodies")
        if not isinstance(bodies, int) or bodies <= 0:
            return False, (f"{island}'s census counted no bodies -- the "
                           "counter forgot")
        verdict_v = str((art or {}).get("verdict") or "")
        brake = (art or {}).get("brake") or {}
        if verdict_v == "one-blood" and not brake.get("applied"):
            return False, (f"{island} is one-blood and the consanguineity "
                           "brake never fired -- the medicine did not run")
        readings.append(
            f"{island} {verdict_v} "
            f"(H={art.get('herfindahl')}, Ne={art.get('effective_population')}, "
            f"incesti {art.get('sibling_matings')}/{art.get('crossovers')}"
            + (", freno acceso)" if brake.get("applied") else ")"))
    return True, "il sangue: " + "; ".join(readings)


CHECKS: tuple[tuple[str, str, object], ...] = (
    ("ledger_sealed", "fail", _check_ledger_sealed),
    ("ledger_alive", "warn", _check_ledger_alive),
    ("seed_arithmetic", "warn", _check_seed_arithmetic),
    ("pantry_honest", "fail", _check_pantry_honest),
    ("pantry_tracked", "fail", _check_pantry_tracked),
    ("state_parse", "fail", _check_state_parse),
    ("falcon_fresh", "warn", _check_falcon_fresh),
    ("disk_floor", "fail", _check_disk_floor),
    ("heart_scheduled", "warn", _check_heart_scheduled),
    ("letter_of_dawn", "warn", _check_letter_of_dawn),
    ("dd_ledger_grown", "warn", _check_dd_ledger_grown),
    ("hyperfeed_alive", "warn", _check_hyperfeed_alive),
    ("mouth_alive", "warn", _check_mouth_alive),
    ("history_edge", "warn", _check_history_edge),
    ("scars_alive", "warn", _check_scars_alive),
    ("memory_quarantine", "warn", _check_memory_quarantine),
    ("organs_reborn", "warn", _check_organs_reborn),
    ("genealogy_alive", "warn", _check_genealogy_alive),
)


# ---------------------------------------------------------------------------
# the healing hand: quarantine + git-restore, reversible, pantry-only
# ---------------------------------------------------------------------------
def heal_pantry(backend: Path, name: str, runner=_default_runner) -> str:
    """Quarantine a wounded pantry and restore the last committed good one.

    The append-only factory ledger is NEVER touched (the quarantine's own
    doctrine). An untracked corrupt pantry is quarantined and left absent --
    an absent memory is an honest fresh start; a corrupt one is a lie.
    """
    path = backend / name
    if not path.exists():
        return ""
    quarantine = backend / QUARANTINE_DIR
    quarantine.mkdir(exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wounded = quarantine / f"{name}.{stamp}.bad"
    try:
        shutil.move(str(path), str(wounded))
    except OSError:
        return ""
    rc, _ = runner(["git", "checkout", "--", name], cwd=backend)
    if rc != 0:
        # no committed good copy: the pantry stays absent (honest emptiness)
        return f"quarantined {name} (no committed copy to restore)"
    return f"quarantined {name} -> {wounded.name}; restored the committed copy"


# ---------------------------------------------------------------------------
# the round of the wards
# ---------------------------------------------------------------------------
def sweep(backend_dir=".", *, now=None, runner=_default_runner,
          write=True) -> dict:
    """One guardian round: check, heal what is reversibly healable, record."""
    started = _dt.datetime.now(_dt.timezone.utc)
    # resolve() -- the heart calls the round from the backend's own cwd with
    # ".", and Path(".").parent would be "." again: the letter would be
    # sought beside the backend instead of at the APEX root (the false wound
    # the guardian's own first live round caught, 2026-10-20 14:56 UTC).
    backend = Path(backend_dir).resolve()
    now = now or started
    ctx = {"now": now, "runner": runner,
           "ledger_rows": _ledger_rows(backend)}
    checks: list[dict] = []
    failed: list[str] = []
    warned: list[str] = []
    healed: list[str] = []
    for name, severity, fn in CHECKS:
        try:
            ok, detail = fn(backend, ctx)
        except Exception as exc:  # fail-open: record, never crash
            ok, detail = False, f"check error: {exc}"
        detail = str(detail)
        if not ok and detail.startswith(ESCALATE_WOUND):
            severity = "fail"       # the check itself demands escalation
        elif not ok and detail.startswith(DEMOTE_SOFT):
            severity = "warn"       # emptiness, not a lie
        checks.append({"name": name, "severity": severity,
                       "ok": bool(ok), "detail": detail})
        if ok:
            continue
        (failed if severity == "fail" else warned).append(name)

    # THE HEALING HAND: a torn pantry is the one wound the guardian heals
    # alone (quarantine + restore). Every other finding is REPORTED to the
    # officer (the CEO, the letter, the journal) -- a physician does not
    # amputate what he has not studied.
    if "pantry_honest" in failed:
        for island in ISLANDS:
            name = f"factory_champions_{island}.json"
            path = backend / name
            if not path.exists():
                continue
            ok, _ = _read_json(path)
            if not ok:
                note = heal_pantry(backend, name, runner=runner)
                if note:
                    healed.append(note)
        # re-judge EVERY pantry check after the healing (honesty AND tracked:
        # a quarantined untracked pantry no longer exists to be untracked --
        # the wound list must speak of the PRESENT state, not the pre-op one)
        for name, _severity, fn in CHECKS:
            if name not in ("pantry_honest", "pantry_tracked"):
                continue
            try:
                ok, detail = fn(backend, ctx)
            except Exception:
                continue
            if ok and name in failed:
                failed.remove(name)
            if not ok and name not in failed:
                (failed if _severity == "fail" else warned).append(name)
            for row in checks:
                if row["name"] == name:
                    row["ok"], row["detail"] = ok, str(detail)

    verdict = VERDICT_CLEAN
    if healed:
        verdict = VERDICT_HEALED
    if failed:
        verdict = VERDICT_WOUNDS
    report = {
        "schema": SCHEMA,
        "ts": started.isoformat(timespec="seconds"),
        "verdict": verdict,
        "checks": checks,
        "failed": failed,
        "warned": warned,
        "healed": healed,
        "checks_run": len(checks),
        "duration_ms": int((_dt.datetime.now(_dt.timezone.utc)
                            - started).total_seconds() * 1000),
    }
    if write:
        try:
            append_ledger(backend, report)
        except OSError:
            pass  # the round is recorded in memory even if the pen fails
    return report


# ---------------------------------------------------------------------------
# the guardian's own ledger (bounded, append-only in spirit)
# ---------------------------------------------------------------------------
def append_ledger(backend: Path, report: dict, max_rows: int = LEDGER_MAX_ROWS):
    """Append one visit; trim the oldest beyond the bound (the recent truth)."""
    path = backend / LEDGER_NAME
    rows: list[str] = []
    if path.exists():
        rows = [ln for ln in path.read_text().splitlines() if ln.strip()]
    rows.append(json.dumps(report, default=str))
    rows = rows[-max_rows:]
    path.write_text("\n".join(rows) + "\n")


def load_ledger_tail(backend_dir=".", *, tail: int = 1) -> list[dict]:
    """The guardian's most recent visits, honestly (absent -> empty)."""
    path = Path(backend_dir) / LEDGER_NAME
    if not path.exists():
        return []
    try:
        rows = [json.loads(ln) for ln in path.read_text().splitlines()
                if ln.strip()]
    except (OSError, ValueError):
        return []
    return rows[-max(1, tail):]


# ---------------------------------------------------------------------------
# CLI (the systemd unit, the heart, the Grand and the Boss all call this)
# ---------------------------------------------------------------------------
def voice(report: dict) -> str:
    """One line for the journal, the turn, the letter: the wards' state."""
    if report["verdict"] == VERDICT_CLEAN and not report["warned"]:
        return (f"THE GUARDIAN: {report['checks_run']} checks, all green "
                f"(the wards are quiet)")
    bits = []
    if report["failed"]:
        bits.append(f"WOUNDED: {', '.join(report['failed'])}")
    if report["warned"]:
        bits.append(f"watching: {', '.join(report['warned'])}")
    if report["healed"]:
        bits.append(f"healed: {'; '.join(report['healed'])}")
    return f"THE GUARDIAN: {report['checks_run']} checks -- " + "; ".join(bits)


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="the anti-bug guardian's round")
    ap.add_argument("--backend", default=".")
    ap.add_argument("--json", action="store_true",
                    help="print the raw report instead of the voice")
    ap.add_argument("--no-write", action="store_true",
                    help="round without recording (a silent patrol)")
    args = ap.parse_args(argv)
    now = None
    if os.environ.get("APEX_GUARDIAN_NOW"):  # deterministic tests / reruns
        try:
            now = _dt.datetime.fromisoformat(os.environ["APEX_GUARDIAN_NOW"])
            if now.tzinfo is None:
                now = now.replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            now = None
    try:
        report = sweep(args.backend, now=now, write=not args.no_write)
    except Exception as exc:  # the guardian never dies on its own gurney
        print(f"THE GUARDIAN: sweep error (fail-open): {exc}", file=sys.stderr)
        return 0
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(voice(report))
        for row in report["checks"]:
            if not row["ok"]:
                print(f"  - {row['name']} ({row['severity']}): {row['detail']}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
