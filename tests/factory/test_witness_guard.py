"""R108 THE WITNESS, NOT A RIVAL -- the turn that already ran is witnessed,
never re-run as a deterministic copy of itself.

The measured truth this guard was born from (2026-10-20 17:16 UTC): the CI
push that followed the heart's beat derived the SAME wheel position (same
ledger line count -> same island, same seed) and burned another 8-minute
turn writing a duplicate-seed row the guardian then had to declare. Same
island + same derived seed + same date in the ledger's LAST line is the
wheel saying "I already turned today" -- the honest answer is a clean exit
with the reason spoken, not a second copy of the same evidence.

Under test:
* the derived seed mirrors the factory's own arithmetic (ledger lines -> seed);
* the guard recognises the turn that already ran (LAST line, today, same
  island+seed) and nothing else;
* yesterday's turn, another island's turn, a different seed, an older
  duplicate deeper in the ledger: all honestly not this turn;
* a torn or missing ledger is honest emptiness (the guard never blocks).
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.factory.run_factory import _derived_seed, _wheel_already_turned


def _line(machine: str, date: str, note: str) -> str:
    return json.dumps({"machine": machine, "date": date, "note": note})


class TestDerivedSeed:
    def test_the_wheel_arithmetic_mirrors_the_factory(self, tmp_path):
        led = tmp_path / "factory_ledger.jsonl"
        assert _derived_seed(0, led) == 7919               # empty: n=0
        led.write_text(_line("heart", "2026-10-21", "seed=7919") + "\n")
        assert _derived_seed(0, led) == 15838              # one line: n=1
        assert _derived_seed(100, led) == 100 + 7919 * 2   # the base rides

    def test_a_torn_ledger_counts_its_lines_like_the_factory_does(self, tmp_path):
        led = tmp_path / "torn.jsonl"
        led.write_text("not json at all\n")
        # the factory counts RAW LINES (its own arithmetic); one garbage
        # line is still one turn of the wheel -- the mirror must agree
        assert _derived_seed(0, led) == 15838


class TestTheWitness:
    def test_the_turn_that_already_ran_is_recognised(self, tmp_path):
        led = tmp_path / "factory_ledger.jsonl"
        seed = 7919
        led.write_text(
            _line("turbo", "2026-10-20", "seed=15838 dna=v2") + "\n" +
            _line("heart", "2026-10-21",
                  f"pairs=5 pop=240 seed={seed} champ_in=8 dna=v2") + "\n")
        turned, reason = _wheel_already_turned(
            str(led), island="heart", seed=seed, date="2026-10-21")
        assert turned is True
        assert "already turned" in reason
        assert f"seed={seed}" in reason

    def test_yesterday_is_not_today(self, tmp_path):
        led = tmp_path / "factory_ledger.jsonl"
        led.write_text(_line("heart", "2026-10-20",
                             "seed=7919 dna=v2") + "\n")
        turned, _ = _wheel_already_turned(
            str(led), island="heart", seed=7919, date="2026-10-21")
        assert turned is False

    def test_another_island_is_not_this_turn(self, tmp_path):
        led = tmp_path / "factory_ledger.jsonl"
        led.write_text(_line("turbo", "2026-10-21",
                             "seed=7919 dna=v2") + "\n")
        turned, _ = _wheel_already_turned(
            str(led), island="heart", seed=7919, date="2026-10-21")
        assert turned is False

    def test_an_older_duplicate_deeper_in_the_ledger_does_not_block(
            self, tmp_path):
        led = tmp_path / "factory_ledger.jsonl"
        led.write_text(
            _line("heart", "2026-10-21", "seed=7919 dna=v2") + "\n" +
            _line("vault", "2026-10-21", "seed=23757 dna=v2") + "\n")
        # the duplicate heart/7919 exists but is NOT the last line: history,
        # never a gate (the wheel has moved on)
        turned, _ = _wheel_already_turned(
            str(led), island="heart", seed=7919, date="2026-10-21")
        assert turned is False

    def test_a_different_seed_is_a_different_turn(self, tmp_path):
        led = tmp_path / "factory_ledger.jsonl"
        led.write_text(_line("heart", "2026-10-21",
                             "seed=7919 dna=v2") + "\n")
        turned, _ = _wheel_already_turned(
            str(led), island="heart", seed=15838, date="2026-10-21")
        assert turned is False

    def test_missing_or_torn_never_blocks(self, tmp_path):
        assert _wheel_already_turned(
            str(tmp_path / "absent.jsonl"), island="heart", seed=1,
            date="2026-10-21") == (False, "")
        torn = tmp_path / "torn.jsonl"
        torn.write_text("{{{{not json\n")
        assert _wheel_already_turned(
            str(torn), island="heart", seed=1, date="2026-10-21")[0] is False
