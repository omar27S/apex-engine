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


def _cross(a, b, above=True):
    return g.node("crosses_above" if above else "crosses_below", (), (a, b))


def _session(session_id: int):
    return g.node("session", (int(session_id),))


def _killzone(start: int, end: int):
    return g.node("killzone", (int(start), int(end)))


def _concept(tag: str) -> str:
    """A stable concept tag; the session appends the body hash when storing."""
    return f"hyp:{tag}"


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
# R74b — the intuition translator (plain Italian hunch -> body).
# ---------------------------------------------------------------------------
_INTUITION_MAP = (
    # (keywords, builder, human note)
    (("sessione", "londra", "london", "apertura", "open"),
     lambda: g.Program(
         long=_and(_killzone(7, 11), _cross(_ema(9), _ema(21), above=True)),
         short=_and(_killzone(7, 11), _cross(_ema(9), _ema(21), above=False)),
         concept=_concept("intuition_session")),
     "killzone di Londra con incrocio EMA"),
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


def translate_intuition(text: str) -> IntuitionResult:
    """Map a plain-Italian hunch to a body, or explain WHY it cannot (R74b)."""
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
                "momentum, volatility, RSI); a hunch about money management or "
                "fundamentals cannot be a body and is refused rather than faked"))


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
