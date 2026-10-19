"""THE MODULAR ARMY (Mega Phase 2, Section B) -- catalogue, assembly, marketplace.

Friction contract: let ``assemble`` accept an unknown module id and the fail-closed
test FAILS; make ``update_reputation`` never set trust and the marketplace test FAILS.
"""

from __future__ import annotations

from app.factory import modules as mod


def test_catalogue_sizes_are_the_directive_numbers():
    k = mod.module_kinds()
    assert k == {"entry": 20, "exit": 10, "filter": 15, "risk": 5}
    assert mod.assembly_space() == 20 * 10 * 15 * 5 == 15000


def test_assemble_builds_a_valid_composite():
    a = mod.assemble("fvg_tap", "structural_target", "regime_hurst", "fixed_1pct")
    assert a is not None
    assert a["id"] == "fvg_tap|structural_target|regime_hurst|fixed_1pct"


def test_assemble_fails_closed_on_an_unknown_module():
    assert mod.assemble("nope", "structural_target", "regime_hurst", "fixed_1pct") is None


def test_reputation_updates_from_real_outcomes():
    scores: dict = {}
    a = mod.assemble("fvg_tap", "fixed_rr", "session_london", "vol_adjusted")
    mod.update_reputation(scores, a, won=True)
    mod.update_reputation(scores, a, won=True)
    mod.update_reputation(scores, a, won=False)
    assert scores["entry"]["fvg_tap"]["trust"] == round(2 / 3, 4)


def test_marketplace_is_honest_with_no_scores():
    mp = mod.marketplace({})
    assert mp["measured"] is False
    rows = mp["board"]["entry"]
    assert all(r["trust"] is None for r in rows)


def test_best_assemblies_prefers_measured_winners():
    scores = {"entry": {"fvg_tap": 0.9}, "exit": {"fixed_rr": 0.8},
              "filter": {"regime_hurst": 0.7}, "risk": {"vol_adjusted": 0.6}}
    best = mod.best_assemblies(scores, top=1)
    assert len(best) == 1
    assert best[0]["entry"] == "fvg_tap"
    assert best[0]["exit"] == "fixed_rr"
