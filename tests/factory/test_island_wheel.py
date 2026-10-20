"""R98 — THE ISLAND WHEEL: three real islands, one turn each.

The architecture always declared three islands (heart, turbo, vault -- 240
bodies x 3 = the 720 agents), but the shift config named ONE island forever,
so two islands never existed outside a diagram. The wheel makes the declared
architecture true: ``island: "auto"`` in the config rides heart -> turbo ->
vault, one island per ledger line -- the SAME honest key the rotating seed
(R92) uses -- so every island breeds on its own pantry and none is starved.
"""

from __future__ import annotations

from pathlib import Path

from tools.factory.run_factory import ISLAND_WHEEL, _resolve_island


def _ledger_with(n_lines: int, tmp_path: Path) -> Path:
    p = tmp_path / "wheel_ledger.jsonl"
    p.write_text("".join("{}\n" for _ in range(n_lines)))
    return p


def test_the_wheel_is_the_three_declared_islands():
    assert ISLAND_WHEEL == ("heart", "turbo", "vault")


def test_the_wheel_rotates_by_the_ledger(tmp_path):
    # 0 lines -> heart, 1 -> turbo, 2 -> vault, 3 -> heart again, 4 -> turbo:
    # the wheel advances one island per honest ledger line, forever.
    for n, expect in [(0, "heart"), (1, "turbo"), (2, "vault"),
                      (3, "heart"), (4, "turbo"), (6, "heart"), (8, "vault")]:
        ledger = _ledger_with(n, tmp_path)
        assert _resolve_island("auto", str(ledger)) == expect, n


def test_a_missing_ledger_starts_at_heart(tmp_path):
    assert _resolve_island("auto", str(tmp_path / "nope.jsonl")) == "heart"


def test_a_named_island_is_the_callers_word(tmp_path):
    ledger = _ledger_with(5, tmp_path)      # would be turbo on the wheel
    assert _resolve_island("heart", str(ledger)) == "heart"
    assert _resolve_island("vault", str(ledger)) == "vault"


def test_the_word_is_normalized_never_mangled(tmp_path):
    ledger = _ledger_with(0, tmp_path)
    assert _resolve_island("  AUTO  ", str(ledger)) == "heart"
    assert _resolve_island("", str(ledger)) == "heart"
    assert _resolve_island("mars", str(ledger)) == "mars"
