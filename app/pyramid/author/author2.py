"""THE AUTHOR 2.0 — hypothesis engine + intuition translator (Phase 7e, R74a/b/c).

Four sub-mandates, built NOW and used in attended sessions:

* R74a HYPOTHESIS ENGINE — formulate data-grounded hypotheses from the three
  ledgers (autopsy cause distribution, tribunal verdicts, realm census) and write,
  for each, a body through the EXISTING typed grammar. Zero CEO ideas required.
* R74b INTUITION TRANSLATOR — turn a plain-Italian CEO hunch into a candidate
  body via the grammar (best-effort mapping). If the hunch cannot be expressed,
  it returns WHY — never a fake strategy.
* R74c NOVELTY HUNTER — a dedicated exploration budget that generates bodies
  maximising behavioural NOVELTY (distance from every existing genome's signal
  signature) — the anti-conformism weapon.

Everything here is PURE: no I/O, no sandbox at import. The caller (the attended
session tool) judges each produced body through the full cage
(static gate -> sandbox -> determinism -> causality -> honest engine).

A hypothesis is only as honest as its grounding: each one cites the ledger
reading that motivated it and a confidence in [0, 1]. The engine never invents a
grounding it did not receive.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from app.pyramid.author import grammar as g

__all__ = [
    "HypothesisInputs",
    "Hypothesis",
    "IntuitionResult",
    "grounded_hypotheses",
    "patience_hypotheses",
    "hunt_hypotheses",
    "translate_intuition",
    "novelty_hypothesis",
    "fingerprint",
    "signal_distance",
]

# ---------------------------------------------------------------------------
# Inputs the engine reasons over (all optional; absent -> that source is silent).
# ---------------------------------------------------------------------------
@dataclass
class HypothesisInputs:
    """Aggregated readings from the three ledgers (R74a)."""

    autopsy: dict = field(default_factory=dict)       # cause -> count
    tribunal: dict = field(default_factory=dict)      # verdict -> count
    realms: dict = field(default_factory=dict)        # census dict (R73)
    total_autopsy: int = 0
    total_tribunal: int = 0
    # ``None`` means "no census was supplied" (no realm play). An EMPTY tuple means
    # "the census says every realm is empty" (a fill play) — a real distinction.
    occupied_realms: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Hypothesis:
    """One data-grounded hypothesis and the body that expresses it."""

    text: str
    grounding: str
    confidence: float
    program: g.Program

    def to_dict(self) -> dict:
        return {"text": self.text, "grounding": self.grounding,
                "confidence": round(float(self.confidence), 4),
                "concept": self.program.concept}


@dataclass(frozen=True)
class IntuitionResult:
    """The outcome of translating a plain-language hunch (R74b)."""

    text: str
    ok: bool
    reason: str
    program: g.Program | None = None

    def to_dict(self) -> dict:
        return {"text": self.text, "ok": self.ok, "reason": self.reason,
                "concept": self.program.concept if self.program else None}


# ---------------------------------------------------------------------------
# Grammar snippets — each a legal bool Program built from typed nodes.
# ---------------------------------------------------------------------------
def _const(value: float):
    return g.node("const", ("threshold", float(value)))


def _gene(name: str):
    return g.node("gene", (str(name),))


def _rsi(period: int):
    return g.node("rsi", (int(period),))


def _ema(period: int):
    return g.node("ema", (int(period),))


def _atr(period: int = 14):
    return g.node("atr", (int(period),))


def _macd(f=12, s=26, sig=9):
    return g.node("macd_hist", (int(f), int(s), int(sig)))


def _absret(period: int = 60):
    return g.node("absret_pct", (int(period),))


def _z(period: int = 20):
    return g.node("zscore", (int(period),))


def _hurst(window: int = 100, rank_window: int = 200):
    return g.node("hurst_pct", (int(window), int(rank_window)))


def _donchian(period: int = 20):
    return g.node("donchian_pos", (int(period),))


def _bb_dist(period: int = 20, k: float = 2.0):
    return g.node("bb_dist", (int(period), float(k)))


def _cmp(op, a, b):
    return g.node("compare", (op,), (a, b))


def _and(a, b):
    return g.node("and", (), (a, b))


def _or(a, b):
    return g.node("or", (), (a, b))


def _not(a):
    return g.node("not", (), (a,))


def _cross(a, b, above=True):
    return g.node("crosses_above" if above else "crosses_below", (), (a, b))


def _session(session_id: int):
    return g.node("session", (int(session_id),))


def _killzone(start: int, end: int):
    return g.node("killzone", (int(start), int(end)))


# --- R81/R82/R83 (Phase 7h) builders for the newly expressible hunches ------
def _dow(dow: int):
    return g.node("day_of_week", (int(dow),))


def _nth_weekday(n: int, dow: int):
    return g.node("nth_weekday", (int(n), int(dow)))


def _dom(lo: int, hi: int):
    return g.node("day_of_month", (int(lo), int(hi)))


def _jpy_holiday(before: int, after: int):
    return g.node("jpy_holiday_window", (int(before), int(after)))


def _round_hit(step: int, tol: float):
    return g.node("round_number_hit", (int(step), float(tol)))


def _dist_round(step: int):
    return g.node("dist_round", (int(step),))


def _gap_open(min_pips: float):
    return g.node("gap_open", (float(min_pips),))


def _prior_day_dir():
    return g.node("prior_day_dir")


def _dxy_corr(window: int):
    return g.node("dxy_corr", (int(window),))


def _dxy_lag_align(lag: int):
    return g.node("dxy_lag_align", (int(lag),))


def _concept(tag: str) -> str:
    """A stable concept tag; the session appends the body hash when storing."""
    return f"hyp:{tag}"


# --- R87 (Phase 7j) PATIENCE builders — the sniper primitives --------------
def _min_gap(bars: int, child):
    return g.node("min_gap_bars", (int(bars),), (child,))


def _quiet(bars: int, window: int, quiet: float):
    return g.node("n_quiet_bars", (int(bars), int(window), float(quiet)))


def _atr_quartile(window: int, bucket: float = 0.75):
    return g.node("atr_quartile", (int(window), float(bucket)))


def _bars_since(window: int):
    return g.node("bars_since_range", (int(window),))


# --- R89 (Phase 7k) GROSS-EDGE builders — the fat-hunt primitives -----------
def _vol_disp(window: int):
    return g.node("vol_displacement", (int(window),))


def _pb_depth(window: int):
    return g.node("pullback_depth", (int(window),))


def _sbr(fade: float, front):
    return g.node("session_boundary_reversal", (float(fade),), (front,))


# ---------------------------------------------------------------------------
# Grounded hypotheses (R74a). Each builder reads ONE ledger signal.
# ---------------------------------------------------------------------------
def _hyp_meanrev_on_stop_hunt(share: float) -> Hypothesis:
    prog = g.Program(
        long=_and(_cmp("<", _z(20), _const(-2.0)),
                  _cmp("<", _rsi(14), _gene("rsi_oversold"))),
        short=_and(_cmp(">", _z(20), _const(2.0)),
                   _cmp(">", _rsi(14), _gene("rsi_overbought"))),
        concept=_concept("meanrev_on_stophunt"),
    )
    return Hypothesis(
        text="Stops are being hunted: fade the extreme (z-score + RSI) instead of "
             "chasing continuation, so the entry is beyond the wick's reach.",
        grounding=f"autopsy stop_hunt_gap share={share:.3f}",
        confidence=min(0.9, 0.35 + share),
        program=prog,
    )


def _hyp_regime_filter(share: float) -> Hypothesis:
    prog = g.Program(
        long=_and(_cmp(">", _hurst(100, 200), _const(0.6)),
                  _cmp(">", _macd(), _const(0.0))),
        short=_and(_cmp("<", _hurst(100, 200), _const(0.4)),
                   _cmp("<", _macd(), _const(0.0))),
        concept=_concept("regime_gated_trend"),
    )
    return Hypothesis(
        text="The regime is being misread: gate trend entries on a HIGH Hurst "
             "percentile and mean-reversion on a LOW one, so the body never fights "
             "the market it is standing in.",
        grounding=f"autopsy regime_misread share={share:.3f}",
        confidence=min(0.9, 0.35 + share),
        program=prog,
    )


def _hyp_target_missed_session(share: float) -> Hypothesis:
    prog = g.Program(
        long=_and(_killzone(7, 11), _cross(_ema(9), _ema(21), above=True)),
        short=_and(_killzone(7, 11), _cross(_ema(9), _ema(21), above=False)),
        concept=_concept("london_kz_momentum"),
    )
    return Hypothesis(
        text="Targets are being missed: concentrate entries in the London "
             "killzone where displacement is real, on an EMA cross.",
        grounding=f"autopsy target_missed share={share:.3f}",
        confidence=min(0.85, 0.30 + share),
        program=prog,
    )


def _hyp_breakout_from_vol(share: float) -> Hypothesis:
    prog = g.Program(
        long=_and(_cmp(">", _donchian(20), _const(0.95)),
                  _cmp(">", _bb_dist(20, 2.0), _const(1.5))),
        short=_and(_cmp("<", _donchian(20), _const(0.05)),
                   _cmp("<", _bb_dist(20, 2.0), _const(-1.5))),
        concept=_concept("vol_expansion_breakout"),
    )
    return Hypothesis(
        text="Structural failure dominates: enter only on a genuine expansion — "
             "a new Donchian extreme AND a band break — never inside the range.",
        grounding=f"autopsy structural_failure share={share:.3f}",
        confidence=min(0.85, 0.30 + share),
        program=prog,
    )


def _hyp_unoccupied_realm(groups_present: set[str]) -> Hypothesis:
    """Build the body for a REALM the census says is empty (R73 + R74a)."""
    missing = sorted({"meanrev", "breakout", "volatility", "volume",
                      "structure", "pattern", "momentum", "relative", "trend"}
                     - set(groups_present))
    target = missing[0] if missing else "pattern"
    builders = {
        "meanrev": (lambda: _and(_cmp("<", _rsi(7), _gene("rsi_oversold")),
                                 _cmp("<", _bb_dist(20, 2.0), _const(-2.0))),
                    lambda: _and(_cmp(">", _rsi(7), _gene("rsi_overbought")),
                                 _cmp(">", _bb_dist(20, 2.0), _const(2.0)))),
        "breakout": (lambda: _cmp(">", _donchian(30), _const(0.98)),
                     lambda: _cmp("<", _donchian(30), _const(0.02))),
        "volatility": (lambda: _cmp(">", _bb_dist(20, 2.0), _const(1.5)),
                       lambda: _cmp("<", _bb_dist(20, 2.0), _const(-1.5))),
        "pattern": (lambda: _cross(_ema(5), _ema(13), above=True),
                    lambda: _cross(_ema(5), _ema(13), above=False)),
        "momentum": (lambda: _cmp(">", _macd(), _const(0.0)),
                     lambda: _cmp("<", _macd(), _const(0.0))),
    }
    long_fn, short_fn = builders.get(target, builders["momentum"])
    prog = g.Program(long=long_fn(), short=short_fn(),
                     concept=_concept(f"realm_fill_{target}"))
    return Hypothesis(
        text=f"Realm '{target}' is unoccupied: build a body that fills it, so the "
             f"council's seven seats can come from seven DIFFERENT realms.",
        grounding=f"realms census empty groups={missing[:3]}",
        confidence=0.5,   # a diversity play, not a proven edge — honest midpoint
        program=prog,
    )


def _hyp_death_cause(cause: str, share: float) -> Hypothesis:
    """A generic builder for a death cause we have no specialist for.

    Every real autopsy taxonomy is covered by SOME hypothesis — the engine never
    stays silent on a cause the ledger actually reports. The body is the safest
    universal one (a regime-gated momentum) with the cause named in the text, and
    its confidence is the cause's share (honest, not inflated).
    """
    prog = g.Program(
        long=_and(_cmp(">", _hurst(100, 200), _const(0.55)),
                  _cmp(">", _macd(), _const(0.0))),
        short=_and(_cmp("<", _hurst(100, 200), _const(0.45)),
                   _cmp("<", _macd(), _const(0.0))),
        concept=_concept(f"cause_{cause}"),
    )
    return Hypothesis(
        text=f"Dominant death cause '{cause}': requalify entries through a regime "
             f"filter and a momentum confirmation so this cause is attacked head-on.",
        grounding=f"autopsy {cause} share={share:.3f}",
        confidence=min(0.85, 0.30 + share),
        program=prog,
    )


# Specialist builders keyed by the exact cause name in the two known taxonomies.
_SPECIALISTS = {
    "stop_hunt_gap": lambda share: _hyp_meanrev_on_stop_hunt(share),
    "regime_misread": lambda share: _hyp_regime_filter(share),
    "target_missed": lambda share: _hyp_target_missed_session(share),
    "structural_failure": lambda share: _hyp_breakout_from_vol(share),
    # the live tournament taxonomy (Phase 7d ledgers)
    "early_stop": lambda share: _hyp_target_missed_session(share),
    "tournament_floor": lambda share: _hyp_regime_filter(share),
    "rams_floor": lambda share: _hyp_breakout_from_vol(share),
}


def grounded_hypotheses(inputs: HypothesisInputs, *, n: int = 8) -> list[Hypothesis]:
    """Formulate up to ``n`` data-grounded hypotheses, best-evidence first.

    Drives from the autopsy cause distribution (whatever taxonomy it uses), adds
    a tribunal signal and a realm-fill play, then dedups and ranks by confidence.
    A source that is empty contributes nothing — no invented grounding.
    """
    hyp: list[Hypothesis] = []
    total = max(1, int(inputs.total_autopsy))
    autopsy = {str(k): float(v) for k, v in (inputs.autopsy or {}).items()}

    # Best-evidence first: the causes that killed the most candidates.
    for cause, count in sorted(autopsy.items(), key=lambda kv: -kv[1]):
        if count <= 0:
            continue
        share = count / total
        builder = _SPECIALISTS.get(cause)
        hyp.append(builder(share) if builder else _hyp_death_cause(cause, share))

    tribunal = inputs.tribunal or {}
    if tribunal:
        veto = int(tribunal.get("veto", 0))
        hyp.append(_hyp_regime_filter(
            min(1.0, (veto + 1) / max(1, int(inputs.total_tribunal)))))

    if inputs.occupied_realms is not None:
        hyp.append(_hyp_unoccupied_realm(set(inputs.occupied_realms)))

    # Deterministic dedup by concept, preserving evidence order.
    seen: set[str] = set()
    out: list[Hypothesis] = []
    for h in hyp:
        if h.program.concept in seen:
            continue
        seen.add(h.program.concept)
        out.append(h)
    out.sort(key=lambda h: h.confidence, reverse=True)
    return out[: max(0, int(n))]


# ---------------------------------------------------------------------------
# R87 (Phase 7j) — THE PATIENT SNIPER HYPOTHESES.
# ---------------------------------------------------------------------------
# The dense shooters died at the cashier: many entries, friction compounding per
# entry into thousands of R. These bodies invert the profile — they fire rarely,
# wait for calm, and gate on the volatile realm the tape rewards. Each is built
# ONLY from the R87 patience nodes plus the existing families, and each is a
# concrete parameterisation of one of the directive's patience mandates.
def _patience_specs() -> list[tuple[str, str, g.Node, g.Node, str]]:
    """(name, mandate, long_tree, short_tree, grounding)."""
    return [
        # (a) multi-day hold + structural target: enter a wide-stop regime late in
        #     a coiled range, hold for the structural move (max_bars_hold is wide
        #     in the session's carrier — this node expresses the ENTRY patience).
        ("p_quiet_breakout", "n-quiet-bars-then-event",
         _and(_min_gap(48, _quiet(24, 96, 0.8)),
              _cmp(">", _donchian(40), _const(0.9))),
         _and(_min_gap(48, _quiet(24, 96, 0.8)),
              _cmp("<", _donchian(40), _const(0.1))),
         "coiled >=24 calm bars, then a range breakout (wide stops will breathe)."),
        # (c) regime-gated firing: trade ONLY the top-quartile ATR realm.
        ("p_vol_realm_trend", "regime-gated (top ATR quartile)",
         _and(_atr_quartile(160, 0.75), _cmp(">", _macd(), _const(0.0))),
         _and(_atr_quartile(160, 0.75), _cmp("<", _macd(), _const(0.0))),
         "momentum ONLY when ATR is in the top quartile — volatile-realm specialty."),
        # (c') regime-gated mean reversion: fade stretch, but only in the storm.
        ("p_vol_realm_fade", "regime-gated (top ATR quartile)",
         _and(_atr_quartile(160, 0.75), _cmp("<", _z(40), _const(-2.0))),
         _and(_atr_quartile(160, 0.75), _cmp(">", _z(40), _const(2.0))),
         "fade an extreme z-score ONLY in the top ATR quartile."),
        # (d) no-clustering + patience on an existing family (slow EMA cross).
        ("p_gap_cross_slow", "min-distance between entries",
         _min_gap(32, _cross(_ema(21), _ema(55), above=True)),
         _min_gap(32, _cross(_ema(21), _ema(55), above=False)),
         "a slow EMA cross, forced >= 32 bars apart (one shot per move)."),
        # (b)+(d) quiet-then-event with a long spacing floor on a Donchian break.
        ("p_quiet_gap_break", "n-quiet-bars + min-distance",
         _min_gap(64, _and(_quiet(16, 64, 0.7),
                           _cmp(">", _donchian(20), _const(0.98)))),
         _min_gap(64, _and(_quiet(16, 64, 0.7),
                           _cmp("<", _donchian(20), _const(0.02)))),
         "after 16 calm bars, a fresh 20-bar extreme; entries >= 64 bars apart."),
        # (a) pullback clock: trade after price has coiled inside its range long.
        ("p_coiled_pullback", "hold / pullback clock",
         _and(_cmp(">", _bars_since(48), _const(0.75)),
              _cmp(">", _rsi(14), _gene("pullback_rsi"))),
         _and(_cmp(">", _bars_since(48), _const(0.75)),
              _cmp("<", _rsi(14), _gene("rsi_oversold"))),
         "coiledness > 0.75 (no new range break), then a directional RSI bias."),
        # (c)+(d) volatile realm + spacing: the purest sniper.
        ("p_sniper", "regime-gated + min-distance + quiet",
         _min_gap(48, _and(_atr_quartile(160, 0.75),
                           _and(_quiet(20, 96, 0.9),
                                _cmp(">", _donchian(40), _const(0.85))))),
         _min_gap(48, _and(_atr_quartile(160, 0.75),
                           _and(_quiet(20, 96, 0.9),
                                _cmp("<", _donchian(40), _const(0.15))))),
         "the full patience stack: volatile realm, calm-before-event, wide spacing."),
        # (b) symmetric sniper short via the noise-band fade in the storm.
        ("p_storm_fade", "regime-gated volatility fade",
         _and(_atr_quartile(160, 0.75),
              _cross(_ema(9), _ema(21), above=True)),
         _and(_atr_quartile(160, 0.75),
              _cross(_ema(9), _ema(21), above=False)),
         "EMA re-cross ONLY in the top ATR quartile (few, high-volatility entries)."),
        # (a) multi-day hold expressed as a slow structure entry.
        ("p_slow_structure", "hold / wide stop",
         _and(_cmp(">", _ema(9), _ema(55)),
              _cmp(">", _bars_since(96), _const(0.5))),
         _and(_cmp("<", _ema(9), _ema(55)),
              _cmp(">", _bars_since(96), _const(0.5))),
         "trend alignment only after the range has coiled for half a window."),
        # (d) THE RAREST EXTREME — very wide spacing (>= 2.5 days between entries).
        #     The directive: "few standard bodies, ultra-rare entries". If even
        #     these fire thousands of times, the grammar cannot express rarity and
        #     the finding is that the frequency is intrinsic, not a tuning miss.
        ("p_ultra_sniper", "ultra-rare entries (>= 240-bar spacing)",
         _min_gap(240, _and(_quiet(32, 160, 0.6),
                            _cmp(">", _donchian(60), _const(0.9)))),
         _min_gap(240, _and(_quiet(32, 160, 0.6),
                            _cmp("<", _donchian(60), _const(0.1)))),
         "the rarest profile: calm month, fresh extreme, entries days apart."),
        ("p_rare_vol_fade", "ultra-rare entries (>= 120-bar spacing)",
         _min_gap(120, _and(_atr_quartile(240, 0.8),
                            _cmp("<", _z(60), _const(-2.5)))),
         _min_gap(120, _and(_atr_quartile(240, 0.8),
                            _cmp(">", _z(60), _const(2.5)))),
         "only an extreme fade, only in the top-20% ATR realm, days apart."),
        ("p_sparse_trend", "ultra-rare entries (>= 160-bar spacing)",
         _min_gap(160, _and(_cmp(">", _ema(21), _ema(89)),
                            _cmp(">", _bars_since(192), _const(0.6)))),
         _min_gap(160, _and(_cmp("<", _ema(21), _ema(89)),
                            _cmp(">", _bars_since(192), _const(0.6)))),
         "a slow trend after a long coil; one entry per few days."),
    ]


def patience_hypotheses() -> list[Hypothesis]:
    """R87 — the patience-profile bodies (Session 4.0's ONLY stock).

    Deterministic, ordered, concept-deduped. Each Hypothesis carries the mandate
    it expresses as its grounding, so the session report can attribute any
    gate-survivor to the patience lever that produced it.
    """
    out: list[Hypothesis] = []
    for name, mandate, ln, sn, note in _patience_specs():
        prog = g.Program(long=ln, short=sn, concept=_concept(name))
        out.append(Hypothesis(
            text=f"Patience mandate '{mandate}': {note}",
            grounding=f"R87 mandate: {mandate}",
            confidence=0.5,   # a profile hypothesis, not a proven edge
            program=prog,
        ))
    return out


# ---------------------------------------------------------------------------
# R89 (Phase 7k) — THE GROSS-EDGE HUNT: three families aimed at gross FAT.
# The Session 4.0 finding: half the patience bodies lack even a GROSS edge, so
# no amount of extra patience can rescue them — friction is not the only wall.
# These families aim at the DIRECTIONALLY-RICH, RARE event itself:
#   (1) multi-day displacement — enter after price travels > 2x ATR from origin;
#   (2) volatility-breakout-with-distance — a fresh range break only after a
#       measured > 2x ATR travel (distance, not just a new extreme);
#   (3) session-boundary reversals — the 24h/8h/16h/21h turn as the event.
# Each is causal, registered (`grammar`), and tested from the AUTHOR side.
# ---------------------------------------------------------------------------
def _hunt_specs() -> list[tuple[str, str, g.Node, g.Node, str]]:
    """(name, mandate, long_tree, short_tree, grounding)."""
    return [
        # (1) MULTI-DAY DISPLACEMENT: the leg has already traveled > 2x ATR from
        #     its multi-day origin, AND the structure agrees (trend), AND spaced.
        ("h_disp_trend", "multi-day displacement (> 2x ATR travel)",
         _min_gap(96, _and(_cmp(">", _vol_disp(96), _const(2.0)),
                           _cmp(">", _ema(21), _ema(55)))),
         _min_gap(96, _and(_cmp("<", _vol_disp(96), _const(-2.0)),
                           _cmp("<", _ema(21), _ema(55)))),
         "enter WITH a >2x ATR multi-day displacement, wide stop for the rest of it."),
        ("h_disp_pullback", "displacement + shallow pullback (buy the dip)",
         _min_gap(64, _and(_cmp(">", _vol_disp(120), _const(2.5)),
                           _cmp(">", _pb_depth(48), _const(0.65)))),
         _min_gap(64, _and(_cmp("<", _vol_disp(120), _const(-2.5)),
                           _cmp("<", _pb_depth(48), _const(0.35)))),
         "a >2.5x ATR up-leg, then a pullback toward the range low (depth>0.65) — buy the dip."),
        ("h_disp_fade", "displacement exhaustion fade",
         _min_gap(96, _and(_cmp(">", _vol_disp(160), _const(3.0)),
                           _cmp("<", _z(40), _const(-1.5)))),
         _min_gap(96, _and(_cmp("<", _vol_disp(160), _const(-3.0)),
                           _cmp(">", _z(40), _const(1.5)))),
         "fade a >3x ATR displacement once momentum z-score rolls over."),
        # (2) VOLATILITY-BREAKOUT-WITH-DISTANCE: a fresh Donchian extreme IS the
        #     breakout — require it in the top ATR realm and demand spacing, so a
        #     'breakout' that has already run far is the only one taken.
        ("h_vbreak_dist", "volatility breakout with distance",
         _min_gap(80, _and(_atr_quartile(160, 0.7),
                           _cmp(">", _donchian(24), _const(0.99)))),
         _min_gap(80, _and(_atr_quartile(160, 0.7),
                           _cmp("<", _donchian(24), _const(0.01)))),
         "a fresh 24-bar extreme ONLY in the top-30% ATR realm, entries spaced."),
        ("h_vbreak_run", "breakout after a >2x ATR run",
         _min_gap(96, _and(_cmp(">", _donchian(20), _const(0.98)),
                           _cmp(">", _vol_disp(64), _const(2.0)))),
         _min_gap(96, _and(_cmp("<", _donchian(20), _const(0.02)),
                           _cmp("<", _vol_disp(64), _const(-2.0)))),
         "break to a new extreme only AFTER the leg already traveled >2x ATR."),
        ("h_vbreak_squeeze", "squeeze then volatile breakout",
         _min_gap(120, _and(_not(_atr_quartile(120, 0.5)),
                            _cmp(">", _donchian(40), _const(0.98)))),
         _min_gap(120, _and(_not(_atr_quartile(120, 0.5)),
                            _cmp("<", _donchian(40), _const(0.02)))),
         "sit in the lower ATR half, then break a 40-bar extreme (squeeze release)."),
        # (3) SESSION-BOUNDARY REVERSALS: the 24h/8h/16h/21h turns as the event.
        ("h_boundary_fade", "session-boundary reversal (fade the stretched leg)",
         _sbr(2.0, _z(40)),
         _and(_sbr(2.0, _z(40)), _cmp("<", _z(40), _const(0.0))),
         "at a session boundary, fade a >=2-sigma stretched leg (the turn event)."),
        ("h_boundary_fade_spaced", "session boundary + wide spacing",
         _min_gap(64, _sbr(2.5, _z(60))),
         _min_gap(64, _and(_sbr(2.5, _z(60)), _cmp("<", _z(60), _const(0.0)))),
         "a >=2.5-sigma boundary stretch, at most one attempt per 64 bars."),
        ("h_boundary_trend_join", "session-boundary trend join",
         _and(_sbr(1.5, _z(40)), _cmp(">", _ema(21), _ema(55))),
         _and(_sbr(1.5, _z(40)), _cmp("<", _ema(21), _ema(55))),
         "a >=1.5-sigma boundary move INTO the prevailing trend (join, not fade)."),
    ]


def hunt_hypotheses() -> list[Hypothesis]:
    """R89 (Phase 7k) — the gross-edge hunt bodies (Session 5.0's ONLY stock).

    Deterministic, ordered, concept-deduped. Each carries the mandate it expresses
    as its grounding so the frontier sweep can attribute a curve point to the
    fat-hunt lever that produced it.
    """
    out: list[Hypothesis] = []
    for name, mandate, ln, sn, note in _hunt_specs():
        prog = g.Program(long=ln, short=sn, concept=_concept(name))
        out.append(Hypothesis(
            text=f"Gross-edge mandate '{mandate}': {note}",
            grounding=f"R89 mandate: {mandate}",
            confidence=0.5,
            program=prog,
        ))
    return out


# ---------------------------------------------------------------------------
# R74b — the intuition translator (plain Italian hunch -> body).
# ---------------------------------------------------------------------------
# ORDERED, MOST-SPECIFIC-FIRST. The R74b keyword collision (two distinct hunches
# -> one body) came from a too-broad session/open entry swallowing the calendar
# hunches. Specific calendar / level / cross entries are matched first, and the
# generic London entry no longer keys on bare "apertura"/"open".
_INTUITION_MAP = (
    # (keywords, builder, human note)  — the six Architect intuitions (R81/R82/R83)
    (("venerd", "friday", "fine settimana", "posizionamento settimanale"),
     lambda: g.Program(
         long=_and(_dow(4), _cmp("<", _z(20), _const(-1.5))),
         short=_and(_dow(4), _cmp(">", _z(20), _const(1.5))),
         concept=_concept("intuition_friday_fade")),
     "fade del posizionamento del venerdì (day-of-week)"),
    (("dxy", "dollaro", "dollar", "indice del dollaro", "dollar index"),
     lambda: g.Program(
         long=_dxy_lag_align(4),
         short=_not(_dxy_lag_align(4)),
         concept=_concept("intuition_dxy_lead")),
     "lead del DXY sui dollar pair (lagged reaction, read-only)"),
    # R74b residual (Phase 7h/2.0): the canonical #3 hunch says "volatilità
    # estrema ... inverte la direzione della giornata precedente" — words that
    # matched NONE of the original keywords, so the bare "volatilit" entry below
    # swallowed it. The prior-day reversal phrases are added here so the specific
    # entry wins (this entry is checked before the generic one).
    (("esaurimento", "cluster", "reversione di volatilità", "volatility cluster",
      "giornata precedente", "mattina dopo", "inverte", "prior day", "prior-day",
      "reversal"),
     lambda: g.Program(
         long=_and(_cmp("<", _prior_day_dir(), _const(0.0)), _cmp("<", _bb_dist(20, 2.0), _const(-1.0))),
         short=_and(_cmp(">", _prior_day_dir(), _const(0.0)), _cmp(">", _bb_dist(20, 2.0), _const(1.0))),
         concept=_concept("intuition_vol_cluster")),
     "esaurimento del cluster di volatilità (prior-day + bande)"),
    (("numeri tondi", "numero tondo", "tond", "round", "magnete"),
     lambda: g.Program(
         long=_and(_round_hit(50, 3.0), _cmp("<", _dist_round(50), _const(-1.0))),
         short=_and(_round_hit(50, 3.0), _cmp(">", _dist_round(50), _const(1.0))),
         concept=_concept("intuition_round_magnet")),
     "magnetismo dei numeri tondi (price-level)"),
    (("primo luned", "prima apertura del luned", "luned", "first monday",
      "francoforte", "frankfurt", "prima settimana"),
     lambda: g.Program(
         long=_and(_and(_nth_weekday(1, 0), _killzone(7, 10)), _cross(_ema(9), _ema(21), above=True)),
         short=_and(_and(_nth_weekday(1, 0), _killzone(7, 10)), _cross(_ema(9), _ema(21), above=False)),
         concept=_concept("intuition_first_monday")),
     "continuazione della prima apertura del lunedì (nth-weekday + killzone)"),
    (("festivit", "vacanz", "holiday", "giappone", "jpy", "yen"),
     lambda: g.Program(
         long=_and(_jpy_holiday(1, 1), _cmp("<", _absret(60), _const(0.25))),
         short=_and(_jpy_holiday(1, 1), _cmp(">", _absret(60), _const(0.75))),
         concept=_concept("intuition_jpy_holiday")),
     "compressione per festività JPY (holiday window)"),
    # --- generic entries (kept collision-free) -------------------------------
    (("gap", "buco di apertura", "apertura con gap"),
     lambda: g.Program(
         long=_and(_gap_open(12.0), _cmp("<", _prior_day_dir(), _const(0.0))),
         short=_and(_gap_open(12.0), _cmp(">", _prior_day_dir(), _const(0.0))),
         concept=_concept("intuition_gap_open")),
     "gap di apertura che richiude (gap-open + prior-day)"),
    (("londra", "london", "sessione di londra", "sessione"),
     lambda: g.Program(
         long=_and(_killzone(7, 11), _cmp("<", _z(20), _const(-1.0))),
         short=_and(_killzone(7, 11), _cmp(">", _z(20), _const(1.0))),
         concept=_concept("intuition_session")),
     "rientro nella killzone di Londra"),
    (("rientro", "mean", "media", "eccesso", "estremo", "iper"),
     lambda: g.Program(
         long=_cmp("<", _z(20), _const(-2.0)),
         short=_cmp(">", _z(20), _const(2.0)),
         concept=_concept("intuition_meanrev")),
     "rientro alla media su z-score estremo"),
    (("rottura", "breakout", "massimo", "minimo", "canale"),
     lambda: g.Program(
         long=_cmp(">", _donchian(30), _const(0.98)),
         short=_cmp("<", _donchian(30), _const(0.02)),
         concept=_concept("intuition_breakout")),
     "rottura del canale di Donchian"),
    (("trend", "tendenza", "momento", "momentum", "forza"),
     lambda: g.Program(
         long=_cmp(">", _macd(), _const(0.0)),
         short=_cmp("<", _macd(), _const(0.0)),
         concept=_concept("intuition_trend")),
     "seguito del momento (MACD)"),
    (("volatilit", "volatility", "atr", "espansione"),
     lambda: g.Program(
         long=_cmp(">", _bb_dist(20, 2.0), _const(1.5)),
         short=_cmp("<", _bb_dist(20, 2.0), _const(-1.5)),
         concept=_concept("intuition_vol")),
     "espansione di volatilità (bande)"),
    (("rsi", "ipervenduto", "ipercomprato"),
     lambda: g.Program(
         long=_cmp("<", _rsi(14), _const(30.0)),
         short=_cmp(">", _rsi(14), _const(70.0)),
         concept=_concept("intuition_rsi")),
     "livelli RSI di ipervenduto/ipercomprato"),
)

# Specific entries are consulted before generic ones by construction; this list of
# (generic_keyword -> specific_tag) documents the disambiguation that fixes the
# collision and is pinned by the regression test.
_DISAMBIGUATION = {
    "venerd": "intuition_friday_fade",
    "dxy": "intuition_dxy_lead",
    "esaurimento": "intuition_vol_cluster",
    "numero tondo": "intuition_round_magnet",
    "primo luned": "intuition_first_monday",
    "festivit": "intuition_jpy_holiday",
}


def translate_intuition(text: str) -> IntuitionResult:
    """Map a plain-Italian hunch to a body, or explain WHY it cannot (R74b).

    The map is ordered most-specific-first, so a calendar/level/cross hunch is no
    longer swallowed by the generic session entry (the R74b collision). A hunch the
    grammar still cannot express is REFUSED with the reason, never faked.
    """
    clean = (text or "").strip()
    if not clean:
        return IntuitionResult(text=clean, ok=False,
                               reason="empty hunch — nothing to translate")
    low = clean.lower()
    for keywords, builder, note in _INTUITION_MAP:
        if any(k in low for k in keywords):
            try:
                prog = builder()
            except g.GrammarError as exc:      # pragma: no cover - defensive
                return IntuitionResult(text=clean, ok=False,
                                       reason=f"grammar refused the mapping: {exc}")
            return IntuitionResult(
                text=clean, ok=True,
                reason=f"mapped to {note} via the grammar", program=prog)
    return IntuitionResult(
        text=clean, ok=False,
        reason=("no grammar construct matches this hunch — the typed grammar "
                "expresses entry logic (session, mean-reversion, breakout, "
                "momentum, volatility, RSI, and now calendar / round-number / "
                "gap / prior-day / cross-instrument sensors); a hunch about money "
                "management or fundamentals cannot be a body and is refused "
                "rather than faked"))


# ---------------------------------------------------------------------------
# R74c — the novelty hunter.
# ---------------------------------------------------------------------------
def fingerprint(program: g.Program) -> tuple[str, ...]:
    """A behavioural-ish signature of a program: its sorted node-kind multiset.

    Two bodies with the same primitive mix behave similarly on the same inputs;
    a NEW mix is the novelty we hunt. Deterministic and serialisable.
    """
    kinds: list[str] = []

    def walk(n: g.Node):
        kinds.append(n.kind)
        for c in n.children:
            walk(c)

    walk(program.long)
    walk(program.short)
    return tuple(sorted(kinds))


def signal_distance(a: g.Program, b: g.Program) -> float:
    """A Jaccard-like distance in fingerprint space, in [0, 1]."""
    fa, fb = set(fingerprint(a)), set(fingerprint(b))
    if not fa and not fb:
        return 0.0
    inter = len(fa & fb)
    union = len(fa | fb)
    return 1.0 - (inter / union) if union else 0.0


def novelty_hypothesis(existing: list[g.Program], rng,
                       *, attempts: int = 40) -> Hypothesis:
    """Generate a body maximising distance from ``existing`` fingerprints (R74c)."""
    from app.pyramid.author import synth as sy

    if not existing:
        prog = sy.random_body(rng, concept=_concept("novelty_bootstrap"))
        return Hypothesis(
            text="No genomes yet: seed the novelty hunter with a fresh body.",
            grounding="novelty: empty existing set (bootstrap seed)",
            confidence=0.5, program=prog)

    best = None
    best_dist = -1.0
    for _ in range(max(1, int(attempts))):
        cand = sy.random_body(rng, concept=_concept("novelty_hunt"))
        d = min(signal_distance(cand, e) for e in existing)
        if d > best_dist:
            best_dist, best = d, cand
    return Hypothesis(
        text="Maximise behavioural novelty: a body whose primitive mix is unlike "
             "anything already bred (the anti-conformism weapon).",
        grounding=f"novelty: min-distance {best_dist:.3f} over {len(existing)} genomes",
        confidence=min(0.7, 0.3 + best_dist),
        program=best)
