"""R119 THE FORECASTER'S OATH -- the organism predicts its own yield.

Before this organ, the heart could evolve 720 agents yet say nothing
about what ITSELF would do next turn. The oath is self-knowledge made
honest: Laplace-smoothed base rates over the last shifts (never a
feeling), graded next turn in Brier scores (0 = prophet, 0.25 = coin,
1 = liar). The no-peeking law: the oath for turn N is a pure function
of ledger rows 0..N-1, computed before the turn's own row exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.factory import oath as oa


def _ledger_row(champ_out: int, migrants: int, seconds: float) -> str:
    return json.dumps({
        "date": "2026-10-21", "machine": "heart", "trials": 6000,
        "machine_seconds": seconds,
        "note": f"pairs=5 pop=240 seed=1401663 champ_in=3 champ_out={champ_out} "
                f"migrants={migrants} wx=calm dna=v2",
    })


def _write_ledger(path: Path, rows: list[tuple[int, int, float]]) -> None:
    path.write_text("".join(_ledger_row(c, m, s) + "\n" for c, m, s in rows))


class TestSpeak:
    def test_base_rates_are_laplace_smoothed(self):
        # 3 of 4 turns crowned a champion, 1 of 4 moved a migrant, all fast
        facts = [
            {"crowned": True, "migrants": False, "fast": True,
             "machine_seconds": 400.0},
            {"crowned": True, "migrants": False, "fast": True,
             "machine_seconds": 500.0},
            {"crowned": True, "migrants": True, "fast": True,
             "machine_seconds": 300.0},
            {"crowned": False, "migrants": False, "fast": True,
             "machine_seconds": 350.0},
        ]
        oath = oa.speak(facts)
        # Laplace: (3+1)/(4+2) = 0.667 crowned; (1+1)/6 = 0.333 migrants;
        # (4+1)/6 = 0.833 fast. Never 1.0 -- a prophet who says certainty
        # has never met a Monday.
        assert oath["fields"]["crowned"] == round(4 / 6, 3)
        assert oath["fields"]["migrants"] == round(2 / 6, 3)
        assert oath["fields"]["fast"] == round(5 / 6, 3)
        # the point estimate is the MEDIAN of recent seconds (400.0 here)
        assert oath["seconds_point"] == 400.0
        assert oath["base_n"] == 4

    def test_less_than_three_turns_is_honest_none(self):
        facts = [{"crowned": True, "migrants": False, "fast": True,
                  "machine_seconds": 100.0}] * 2
        assert oa.speak(facts) is None  # "I do not know myself yet"

    def test_the_window_forgets_old_regimes(self):
        # 30 slow turns, then 3 fast ones: the 25-window means the oath's
        # base is the RECENT regime, not the fossil one
        fossil = [{"crowned": True, "migrants": False, "fast": False,
                   "machine_seconds": 3000.0}] * 30
        recent = [{"crowned": True, "migrants": False, "fast": True,
                   "machine_seconds": 200.0}] * 3
        oath = oa.speak(fossil + recent)
        # usable = last 25 rows = 22 fossil + 3 recent -> fast 23/27
        assert oath["fields"]["fast"] == round((3 + 1) / 27, 3)
        assert oath["base_n"] == 25


class TestGrade:
    def test_brier_arithmetic(self):
        oath = {"v": 1, "fields": {"crowned": 0.8, "migrants": 0.2, "fast": 0.9},
                "seconds_point": 400.0}
        facts = {"crowned": True, "migrants": False, "fast": False,
                 "machine_seconds": 900.0}
        g = oa.grade(oath, facts)
        assert g["fields"]["crowned"]["brier"] == 0.04   # (0.8-1)^2
        assert g["fields"]["migrants"]["brier"] == 0.04  # (0.2-0)^2
        assert g["fields"]["fast"]["brier"] == 0.81      # (0.9-0)^2
        assert g["mean_brier"] == round((0.04 + 0.04 + 0.81) / 3, 4)
        assert g["seconds"]["err"] == 500.0

    def test_the_prophet_never_grades_his_own_sermon(self):
        facts = {"crowned": True, "migrants": False, "fast": True,
                 "machine_seconds": 100.0}
        assert oa.grade(None, facts) is None
        assert oa.grade({"fields": {}}, facts) is None

    def test_calibration_is_rolling_and_honest(self):
        assert oa.calibrate([]) is None
        assert oa.calibrate([{"mean_brier": 0.2}]) is None  # one grade is not a meter
        meter = oa.calibrate([{"mean_brier": 0.2}, {"mean_brier": 0.4}])
        assert meter == {"mean_brier": 0.3, "n": 2}


class TestCloseTurn:
    def test_the_oath_is_a_pure_function_of_past_rows(self, tmp_path):
        ledger = tmp_path / "factory_ledger.jsonl"
        _write_ledger(ledger, [(2, 0, 400.0), (1, 1, 300.0), (0, 0, 500.0)])
        # facts of the turn that just ENDED (its row is NOT in the ledger yet)
        facts = {"crowned": True, "migrants": False, "fast": True,
                 "machine_seconds": 350.0}
        row = oa.close_turn(str(ledger), str(tmp_path / "oath.jsonl"),
                            machine="heart", facts=facts)
        # the spoken oath derives from the THREE past rows only
        assert row["oath"] == oa.speak([
            {"crowned": True, "migrants": False, "fast": True,
             "machine_seconds": 400.0},
            {"crowned": True, "migrants": True, "fast": True,
             "machine_seconds": 300.0},
            {"crowned": False, "migrants": False, "fast": True,
             "machine_seconds": 500.0},
        ])
        # no previous oath exists -> the grade honestly says so
        assert row["grade"] is None
        assert row["facts"] == facts

    def test_the_next_turn_grades_the_previous_oath(self, tmp_path):
        ledger = tmp_path / "factory_ledger.jsonl"
        _write_ledger(ledger, [(2, 0, 400.0), (1, 1, 300.0), (0, 0, 500.0)])
        oath_path = tmp_path / "oath.jsonl"
        first = oa.close_turn(str(ledger), str(oath_path), machine="heart",
                              facts={"crowned": True, "migrants": False,
                                     "fast": True, "machine_seconds": 350.0})
        # the first turn's facts join the ledger (the caller appends its row)
        with ledger.open("a") as fh:
            fh.write(_ledger_row(1, 0, 350.0) + "\n")
        second = oa.close_turn(str(ledger), str(oath_path), machine="heart",
                               facts={"crowned": True, "migrants": True,
                                      "fast": False, "machine_seconds": 900.0})
        # the second row grades the FIRST row's oath with the SECOND facts
        assert second["grade"]["fields"]["crowned"]["p"] == first["oath"]["fields"]["crowned"]
        assert second["grade"]["fields"]["crowned"]["outcome"] == 1
        assert second["grade"]["fields"]["migrants"]["outcome"] == 1
        assert second["grade"]["fields"]["fast"]["outcome"] == 0
        # and the second oath grew up on four rows of history
        assert second["oath"]["base_n"] == 4

    def test_a_torn_oath_line_is_skipped_never_fatal(self, tmp_path):
        ledger = tmp_path / "factory_ledger.jsonl"
        _write_ledger(ledger, [(2, 0, 400.0), (1, 1, 300.0), (0, 0, 500.0)])
        oath_path = tmp_path / "oath.jsonl"
        oath_path.write_text("this line is torn\n")
        row = oa.close_turn(str(ledger), str(oath_path), machine="vault",
                            facts={"crowned": False, "migrants": False,
                                   "fast": True, "machine_seconds": 200.0})
        assert row["grade"] is None  # the torn predecessor had no oath

    def test_facts_from_ledger_row_reads_the_note_honestly(self):
        row = json.loads(_ledger_row(2, 0, 400.0))
        facts = oa.facts_from_ledger_row(row)
        assert facts == {"crowned": True, "migrants": False, "fast": True,
                         "machine_seconds": 400.0}
        # a row without champ_out/migrants in the note is unmeasurable -> None
        shy = {"machine": "heart", "machine_seconds": 100.0, "note": "seed=1"}
        assert oa.facts_from_ledger_row(shy) is None


class TestHeadline:
    def test_unmeasured_self_knowledge_is_spoken_aloud(self):
        assert oa.headline_note(None) == "oath=n/m"
        assert oa.headline_note({"fields": {"crowned": 0.72}}) == "oath=0.72"
        assert oa.headline_note({"fields": {}}) == "oath=n/m"
