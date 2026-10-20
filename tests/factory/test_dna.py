"""THE DIRECTOR'S DNA -- the twelve laws and the honest injection (v1)."""
import math

from app.factory import dna


def test_twelve_laws_complete_and_unique():
    ids = [law["id"] for law in dna.LAWS]
    assert ids == list(range(1, 13))


def test_every_law_names_its_guard():
    for law in dna.LAWS:
        assert law["name"] and law["text"] and law["guard"]


def test_the_seal():
    # v2 (2026-10-20): the twelve laws of conduct are joined in the SAME
    # seal by the six faculties of thinking (app.factory.zcognition)
    assert dna.DNA_VERSION == 2
    assert dna.seal() == "dna=v2"
    assert len(dna.FACULTIES) == 6


def test_transcription_is_honest():
    t = dna.transcribe(champions_refused=2)
    assert t == {"version": 2, "laws": 12, "faculties": 6,
                 "seal": "dna=v2", "champions_refused": 2}


def test_measured_zero_is_honest_a_ghost_is_not():
    pool = [
        {"genome": {"family": "a"}, "wilson_lb": 0.0},    # honest zero: measured
        {"genome": {"family": "b"}, "wilson_lb": None},   # ghost: no measure
        {"genome": {"family": "c"}},                      # ghost: no score at all
        {"wilson_lb": 1.0},                               # ghost: no genome
        {"genome": {"family": "d"}, "wilson_lb": 0.31},   # a true champion
        {"genome": {"family": "e"}, "wilson_lb": float("nan")},
    ]
    keep, refused = dna.honest_champions(pool)
    assert [m["genome"]["family"] for m in keep] == ["a", "d"]
    assert refused == 4


def test_broken_pantry_is_fail_open():
    assert dna.honest_champions([]) == ([], 0)
    assert dna.honest_champions(None) == ([], 0)
    keep, refused = dna.honest_champions(
        [{"genome": {"family": "z"}, "wilson_lb": float("inf")}, "junk"])
    assert keep == [] and refused == 2


def test_the_dna_reads_aloud(capsys):
    rc = dna.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "THE DIRECTOR'S DNA" in out
    assert "Law 1:" in out and "Law 12:" in out
