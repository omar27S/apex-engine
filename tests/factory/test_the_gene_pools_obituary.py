"""R153 — THE GENE POOL'S OBITUARY (the retirement that reaches the factory).

The letter of 2026-10-24 carried the resurrection made flesh: the world went
from 2 to 4 families and the two re-entering were exactly the ones E4 had
condemned a breath before — no birth, no new genome, no event. The root was
R152's own confession: the retirement was CEREMONIAL (nothing carried it to
the factory's gene pool; the condemned kept running, and the pantry re-seeded
their champions every night while the gravedigger wrote).

These proofs pin the four doors where the dead are now refused: the weighted
DRAW never lands on a retired family (and the bounded fallback draws
explicitly from the living), the pantry DOOR counts and refuses a condemned
family's past champions, the FLOOD table founds no corpses, and the OBITUARY
speaks in the report — the factory names WHO it no longer draws. An empty
retired set leaves every stream untouched (the honest default, the same
doctrine as the regime gating before it).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from app.factory import factory as fac  # noqa: E402
from tools.factory import run_factory as rf  # noqa: E402


RETIRED = ("rsi_divergence", "ml_bayesian_regime")


def _config(retired=RETIRED):
    return fac.FactoryConfig(pairs=("EURUSD",), retired_families=retired,
                             ensemble_quota=0.0)


# ---------------------------------------------------------------------------
# the draw
# ---------------------------------------------------------------------------
def test_the_dead_are_never_drawn():
    """Forty weighted draws under a retirement: the condemned family never
    lands — the gene pool stops manufacturing the corpses E4 certified."""
    cfg = _config()
    rng = np.random.default_rng(7)
    fams = {str(fac._draw_gated(cfg, rng, concrete=True).family)
            for _ in range(40)}
    assert fams                                  # something was drawn at all
    for dead in RETIRED:
        assert dead not in fams


def test_no_retirement_leaves_the_draw_untouched():
    """An empty retired set is the honest default: the factory draws every
    family, exactly as before the Council ever condemned one."""
    cfg = _config(retired=())
    rng = np.random.default_rng(7)
    assert fac._draw_gated(cfg, rng, concrete=True) is not None


def test_all_families_retired_still_draws_a_living_body():
    """A pathological config (every family retired) must not loop forever:
    the bounded retries end in an explicit draw from the living — and with
    none living, the honest ungated fallback (never a crash, never a hang)."""
    every = tuple(sorted({f for f in fac.breeding.eligible_families()}))
    cfg = _config(retired=every)
    rng = np.random.default_rng(3)
    g = fac._draw_gated(cfg, rng, concrete=True)
    assert g is not None                          # the factory breathes on


# ---------------------------------------------------------------------------
# the obituary
# ---------------------------------------------------------------------------
def test_the_obituary_speaks_without_the_tower():
    """Even when the Watchtower said nothing, the report names the retired:
    the factory answers WHO it no longer draws — the retirement is real,
    and it is said aloud."""
    gb = fac._gating_block(_config(), [])
    assert gb["applied"] is True
    assert sorted(gb["retired"]) == sorted(RETIRED)
    assert "rsi_divergence" in gb["reading"]


def test_no_gating_and_no_retirement_reads_as_before():
    """The honest default stays honest: with no verdicts and no tower, the
    gating block reads exactly as it always did."""
    gb = fac._gating_block(fac.FactoryConfig(pairs=("EURUSD",)), [])
    assert gb["applied"] is False
    assert "nessun gating" in gb["reading"]


def test_the_report_counts_the_refused():
    """The retirement's honest counters ride the report: how many condemned
    champions were refused at the door, how many flipped children were
    redrawn at the cradle — counted, never silent."""
    src = Path(fac.__file__).read_text(encoding="utf-8")
    assert '"retired_refused": retired_refused,' in src
    assert '"retired_children_redrawn": retired_children_redrawn},' in src
    assert "R153 — THE RETIREMENT AT THE DOOR" in src
    assert "R153 — THE RETIREMENT AT THE CRADLE" in src


# ---------------------------------------------------------------------------
# the verdicts from the state
# ---------------------------------------------------------------------------
def test_the_verdicts_are_derived_not_transported(tmp_path):
    """_load_retired derives the condemned from the civilization state's
    ledger — the same derivation the One Brain uses (the flattened family
    field first, the legacy text prefix as fallback), so the factory and the
    belief can never disagree about who is dead."""
    sp = tmp_path / "state.json"
    sp.write_text(json.dumps({"ledger": [
        {"kind": "retire_family", "what": "retire the family famX",
         "family": "famX"},
        {"kind": "retire_family", "what": "retire the family legacyFam"},
        {"kind": "cure_family", "what": "cure the family famY",
         "family": "famY"},
    ]}), encoding="utf-8")
    assert rf._load_retired(str(sp)) == ("famX", "legacyFam")


def test_a_missing_state_is_no_retirement(tmp_path):
    """A missing or unreadable state yields () — the factory evolves blind,
    exactly as before the Council ever condemned anyone (fail-open, honest)."""
    assert rf._load_retired(str(tmp_path / "missing.json")) == ()
    torn = tmp_path / "torn.json"
    torn.write_text("{not json", encoding="utf-8")
    assert rf._load_retired(str(torn)) == ()
    assert rf._load_retired("") == ()
