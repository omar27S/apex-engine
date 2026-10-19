"""THE CIVILIZATION'S LANGUAGE -- the APEX TONGUE + the WISE SILENCE (Part Six).

Agents talk like people in a well-run office: work in silence, SPEAK WHEN SPEECH
CHANGES SOMETHING. This module is the tongue they speak and the protocol that
decides whether to open the mouth at all.

* THE APEX TONGUE v1 -- a compact, EVOLVED working vocabulary of market concepts,
  risk states, discoveries and requests. It is born small and grows; frequently
  used words COMPRESS (natural abbreviation) so the tongue optimizes itself for
  thought-speed.
* THE WISE SILENCE PROTOCOL -- the golden rule: *speak if it changes another's
  work; otherwise, work.*
* THE THREE CHANNELS -- URGENT (danger: interrupts), RELEVANT (a discovery useful
  to someone: delivered to whom it serves), SILENCE (everything else: the flow).
* THE SPEAKING INTERBRAIN -- conversations are recorded in the tongue; the best
  exchanges surface in the Letter (translated to Italian for the CEO). POLYPHONY:
  agents whose communications prove useful gain weight in the Council.

For the CEO, always plain Italian: the tongue is the agents'; the Letter is his.

Pure at import (Scar #6): a reduction over data the caller owns.
"""

from __future__ import annotations

__all__ = [
    "TONGUE_VERSION",
    "VOCAB",
    "CHANNELS",
    "URGENT",
    "RELEVANT",
    "SILENCE",
    "MODALITIES",
    "KNOW",
    "BELIEVE",
    "SUSPECT",
    "FEEL",
    "DREAM",
    "VEDO",
    "SAGGIO",
    "MODALITY_WEIGHTS",
    "MODALITY_ITALIAN",
    "DEPTHS",
    "QUICK",
    "DEEP",
    "concept",
    "classify",
    "should_speak",
    "modality",
    "context_packet",
    "utterance",
    "compress",
    "abbrev",
    "translate",
    "ITALIAN",
    "polyphony_weights",
]

TONGUE_VERSION: int = 2

# THE MODALITY MARKERS (v2, the RICH TONGUE). Every message now carries its
# EPISTEMIC MODE — how the sender knows what it says. The civilization stops
# confusing its facts with its hunches: a receiver treats KNOWLEDGE differently
# from SUSPICION, and a FEELING informs but never decides (its weight sits below
# the deciding bar). Order is strongest -> weakest.
KNOW = "KNOW"          # verified data
BELIEVE = "BELIEVE"    # theory, unverified
SUSPECT = "SUSPECT"    # intuition, weak
FEEL = "FEEL"          # emotional signal, uncalibrated
DREAM = "DREAM"        # sleep-born insight
VEDO = "VEDO"          # the eye: what was SEEN (the most trusted sense)
SAGGIO = "SAGGIO"      # THE SAGE: the wisdom above the action (Part Four)
MODALITIES: tuple[str, ...] = (KNOW, BELIEVE, SUSPECT, FEEL, DREAM, VEDO, SAGGIO)

# How much each mode weighs when a receiver reasons over it. A FEELING (0.3) sits
# BELOW the deciding bar (0.5): it informs, it never decides. A DREAM is a hint
# (0.2). Verified KNOWLEDGE (1.0) outweighs a hunch. VEDO (0.95) sits just under
# KNOW: the eye is the most trusted sense (80% of the brain is visual), so a
# SEEING outweighs a SUSPECT and a FEEL — but it is still evidence, and it never
# overrides the Law.
MODALITY_WEIGHTS: dict[str, float] = {
    KNOW: 1.0, BELIEVE: 0.6, SUSPECT: 0.4, FEEL: 0.3, DREAM: 0.2, VEDO: 0.95,
SAGGIO: 0.98,
}
DECIDING_BAR: float = 0.5   # a mode at/above this may decide; below it, informs only

# The Italian the CEO reads for each mode (the Letter translates the tongue).
MODALITY_ITALIAN: dict[str, str] = {
    KNOW: "SO", BELIEVE: "CREDO", SUSPECT: "SOSPETTO",
    FEEL: "SENTO", DREAM: "HO SOGNATO", VEDO: "VEDO",
    SAGGIO: "IL SAGGIO DICE",
}

# THE PRIORITY GRAMMAR, 4th dimension (v2): quick exchanges vs deep deliberations,
# chosen honestly per topic. It rides alongside URGENT/RELEVANT/SILENCE.
QUICK = "QUICK"
DEEP = "DEEP"
DEPTHS: tuple[str, ...] = (QUICK, DEEP)

# The three channels. Frozen names (they ride the recorded exchanges).
URGENT = "URGENT"
RELEVANT = "RELEVANT"
SILENCE = "SILENCE"
CHANNELS: tuple[str, ...] = (URGENT, RELEVANT, SILENCE)

# THE WORKING VOCABULARY v1: a word -> (gloss, Italian). Born small; grows as
# needed (a word may be added by the caller). Kept to market concepts, risk states,
# discoveries and requests -- the things an agent must say fast.
VOCAB: dict[str, tuple[str, str]] = {
    "edg": ("a measured net-positive edge", "vantaggio misurato"),
    "drw": ("drawdown state / capital at risk", "stato di drawdown"),
    "rgm": ("market regime reading", "lettura del regime"),
    "frk": ("friction / cost multiple", "frizione"),
    "nov": ("novelty of a region of the search", "novita'"),
    "kll": ("a clean death (autopsy signal)", "morte pulita"),
    "cure": ("a family is sick, cure it", "famiglia malata, cura"),
    "raid": ("colonize an unknown realm", "raid nell'ignoto"),
    "seed": ("a strategy seed for the cage", "seme di strategia"),
    "veto": ("the orchestra refuses (danger)", "veto dell'orchestra"),
    "flw": ("orderflow pressure reading", "pressione dell'orderflow"),
    "ask?": ("a request for help", "richiesta d'aiuto"),
    "ans": ("an answer to a request", "risposta"),
    "!!": ("danger: interrupts everything", "pericolo"),
}

# The Italian translations (the CEO always reads Italian).
ITALIAN: dict[str, str] = {w: it for w, (_g, it) in VOCAB.items()}


def concept(word: str) -> tuple[str, str]:
    """The (gloss, italian) of a tongue word (fail-closed on an unknown word)."""
    if word not in VOCAB:
        raise KeyError(f"unknown tongue word {word!r}; known: {sorted(VOCAB)}")
    return VOCAB[word]


def classify(*, changes_work: bool, danger: bool = False,
             useful_to: str | None = None) -> str:
    """The WISE SILENCE rule: pick the channel for a would-be utterance.

    * danger -> URGENT (interrupts);
    * changes another's work (and names whom it serves) -> RELEVANT;
    * otherwise -> SILENCE (say nothing; the work's flow is the default).
    """
    if danger:
        return URGENT
    if changes_work and useful_to:
        return RELEVANT
    return SILENCE


def should_speak(*, changes_work: bool, danger: bool = False,
                 useful_to: str | None = None) -> bool:
    """True when speech CHANGES something (the golden rule made a predicate)."""
    return classify(changes_work=changes_work, danger=danger,
                    useful_to=useful_to) != SILENCE


def modality(kind: str) -> dict:
    """The epistemic mode's contract: its weight and whether it may DECIDE.

    ``may_decide`` is False for FEEL and DREAM: a feeling informs, it never
    decides. Fail-closed on an unknown mode.
    """
    if kind not in MODALITIES:
        raise ValueError(f"unknown modality {kind!r}; known: {MODALITIES}")
    w = MODALITY_WEIGHTS[kind]
    return {"modality": kind, "weight": w, "may_decide": w >= DECIDING_BAR,
            "italian": MODALITY_ITALIAN[kind]}


def context_packet(*, steps: list[str] | None = None) -> dict:
    """A COMPACT reasoning context: the two or three steps that produced a message.

    Not just the conclusion — the receiver can AUDIT the sender's thinking and
    challenge a step ("your step 2 is wrong"). Bounded to the last three steps (a
    packet is compact by design). Empty steps -> an empty packet (honest).
    """
    kept = [str(s) for s in (steps or []) if str(s).strip()][-3:]
    return {"steps": kept, "n": len(kept),
            "reading": (" -> ".join(kept) if kept else "(nessun passo di contesto)")}


def utterance(*, sender: str, word: str, body: str = "", channel: str = RELEVANT,
              to: str = "*", ts: str = "", mode: str = BELIEVE,
              depth: str = QUICK, steps: list[str] | None = None) -> dict:
    """One utterance in the tongue (fail-closed on an unknown word, channel, mode).

    The message carries its EPISTEMIC MODE (how the sender knows it) and its
    PRIORITY DEPTH (quick exchange vs deep deliberation), plus an optional CONTEXT
    PACKET (the reasoning steps behind it). Backward compatible: a caller that
    omits ``mode``/``depth`` gets the honest defaults (BELIEVE / QUICK).
    """
    if word not in VOCAB:
        raise ValueError(f"unknown tongue word {word!r}; known: {sorted(VOCAB)}")
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}; known: {CHANNELS}")
    if mode not in MODALITIES:
        raise ValueError(f"unknown modality {mode!r}; known: {MODALITIES}")
    if depth not in DEPTHS:
        raise ValueError(f"unknown depth {depth!r}; known: {DEPTHS}")
    from datetime import datetime, timezone
    pkt = context_packet(steps=steps)
    return {"ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "from": sender, "to": to, "channel": channel, "word": word,
            "body": body, "italian": ITALIAN[word],
            "mode": mode, "mode_weight": MODALITY_WEIGHTS[mode],
            "may_decide": MODALITY_WEIGHTS[mode] >= DECIDING_BAR,
            "depth": depth, "context": pkt}


def abbrev(word: str, *, usage: int, threshold: int = 20) -> str:
    """A frequently-used word COMPRESSES (the tongue optimizes for thought-speed).

    A word used at least ``threshold`` times returns its compressed form (its first
    two letters + a marker); a rarer word stays whole. Deterministic and honest:
    compression is driven by real usage counts, never by whim.
    """
    if usage >= threshold and len(word) > 3:
        return word[:2] + "."
    return word


def compress(vocab: dict[str, tuple[str, str]] | None = None, *,
             usage: dict[str, int] | None = None, threshold: int = 20) -> dict[str, str]:
    """The compression map for the whole tongue, from real usage counts."""
    vocab = vocab or VOCAB
    usage = usage or {}
    return {w: abbrev(w, usage=usage.get(w, 0), threshold=threshold) for w in vocab}


def translate(u: dict) -> str:
    """An utterance in plain Italian (the CEO always reads Italian).

    Renders the EPISTEMIC MODE as a leading marker ("CREDO:", "SENTO:", ...) so the
    CEO sees HOW the civilization knows what it says — a feeling is visibly a
    feeling, not a fact. Older utterances (no mode) render exactly as before.
    """
    ch = u.get("channel")
    prefix = {"URGENT": "[URGENTE] ", "RELEVANT": "", "SILENCE": ""}.get(ch, "")
    mode = u.get("mode")
    marker = f"{MODALITY_ITALIAN[mode]}: " if mode in MODALITY_ITALIAN else ""
    return f"{prefix}{marker}{u.get('from')}: {u.get('italian') or u.get('word')}" + (
        f" -- {u['body']}" if u.get("body") else "")


def polyphony_weights(exchanges: list[dict], *, floor: float = 1.0,
                      gain: float = 0.5) -> dict[str, float]:
    """POLYPHONY: agents whose communications prove USEFUL gain Council weight.

    ``exchanges`` is the recorded interbrain traffic; an exchange is USEFUL when it
    is RELEVANT or URGENT (it changed someone's work or warned of danger). Every
    agent starts at ``floor``; each useful utterance adds ``gain``. Silence costs
    nothing -- speaking WELL is the merit.
    """
    w: dict[str, float] = {}
    for e in exchanges or []:
        sender = e.get("from") or e.get("sender")
        if not sender:
            continue
        w.setdefault(sender, floor)
        if e.get("channel") in (RELEVANT, URGENT):
            w[sender] = round(w[sender] + gain, 4)
    return dict(sorted(w.items()))
