"""SELF-PLAY -- the civilization spars with itself (Mega Phase 2, Section C, Lever 18).

The system's own strategies become the adversary. Two surviving strategies with
OPPOSITE directional bias on the same pair are pitted against each other on the same
tape; whichever's entry logic proves more accurate wins the round, the winner gains
fitness and the loser's genes are discounted. This is what made AlphaGo superhuman:
playing against ITSELF at full strength.

THE ADVERSARIAL MUTATION (C2): when a strategy keeps winning, the system breeds an
ADVERSARY designed to beat it (an opposite-bias mutation). If the adversary wins, the
champion's weakness is EXPOSED; if it loses, the champion's robustness is PROVEN.

THE LADDER (C3): Bronze -> Silver -> Gold -> Platinum -> Diamond, by real survival
record. Strategies spar ONLY within their rank; a Diamond that loses three consecutive
spars is demoted to Platinum for retraining.

Honesty is binding: a round with no resolvable winner (both flat, or either unmeasured)
is reported as a DRAW -- never a fabricated victory; the ladder tier reads the REAL
survival record. Pure at import (Scar #6): genomes, frames and config from the caller.
"""

from __future__ import annotations

__all__ = [
    "SELF_PLAY_VERSION",
    "LADDER",
    "DEMOTION_LOSSES",
    "directional_bias",
    "opposite_bias",
    "sparring",
    "adversarial_mutation",
    "ladder_tier",
    "self_play_block",
]

SELF_PLAY_VERSION: int = 1

LADDER: tuple[str, ...] = ("Bronze", "Silver", "Gold", "Platinum", "Diamond")
DEMOTION_LOSSES: int = 3


def directional_bias(genome, universe, config=None) -> int | None:
    """The genome's net directional bias on a universe: +1 long-leaning, -1 short, 0 flat.

    Measured from the REAL evaluator over ``universe`` (net R of longs vs shorts).
    Honest: with no trades or no frames, ``None`` (never a fabricated bias).
    """
    from app.quant import evaluator as ev
    from app.quant.metrics import trade_net_r

    if not universe:
        return None
    cfg = config or ev.EvaluationConfig()
    rep = ev.evaluate(genome, universe, cfg)
    long_r = 0.0
    short_r = 0.0
    n = 0
    for pair_rep in rep.per_pair.values():
        for t in pair_rep.trades:
            r = float(trade_net_r(t))
            if str(getattr(t, "direction", "")) == "long":
                long_r += r
            else:
                short_r += r
            n += 1
    if n == 0:
        return None
    if long_r > short_r:
        return 1
    if short_r > long_r:
        return -1
    return 0


def opposite_bias(a: int | None, b: int | None) -> bool:
    """True when two directional biases are fully opposed (one long, one short)."""
    return isinstance(a, int) and isinstance(b, int) and a != 0 and b != 0 and a == -b


def sparring(genome_a, genome_b, universe, *, config=None) -> dict:
    """One self-play round: the two genomes fight on the SAME tape.

    With opposite directional bias the higher NET R wins; the winner gains the round,
    the loser is discounted (its ``losses`` incremented). Honest: equal net R, or a
    round with no reference, is a DRAW (no winner claimed).
    """
    from app.quant import evaluator as ev

    cfg = config or ev.EvaluationConfig()
    if not universe:
        return {"ok": False, "winner": None, "reading": "self-play: nessun tape"}
    ra = ev.evaluate(genome_a, universe, cfg)
    rb = ev.evaluate(genome_b, universe, cfg)
    na = float(getattr(ra.metrics, "net_r", 0.0) or 0.0)
    nb = float(getattr(rb.metrics, "net_r", 0.0) or 0.0)
    if na == nb:
        return {"ok": True, "winner": None, "draw": True,
                "a": {"signature": genome_a.signature(), "net_r": na},
                "b": {"signature": genome_b.signature(), "net_r": nb},
                "reading": f"self-play: pareggio (entrambi {na:.3f}R)"}
    winner, loser = (genome_a, genome_b) if na > nb else (genome_b, genome_a)
    wn, ln = (na, nb) if na > nb else (nb, na)
    return {
        "ok": True, "winner": winner.signature(), "loser": loser.signature(),
        "draw": False,
        "a": {"signature": genome_a.signature(), "net_r": na},
        "b": {"signature": genome_b.signature(), "net_r": nb},
        "margin_r": round(wn - ln, 4),
        "reading": (f"self-play: {winner.signature()} batte {loser.signature()} "
                    f"({wn:.3f}R vs {ln:.3f}R)"),
    }


def adversarial_mutation(champion, *, rng=None, universe=None, config=None) -> dict:
    """Breed an ADVERSARY designed to beat a champion (opposite directional bias).

    The adversary keeps the champion's family but flips its trend alignment (the
    headline bias axis), so it takes the OTHER side of the same structures. With a
    random generator the other mutable genes jitter, so the adversary is a genuine
    challenger, not a clone. Returns ``{adversary, reading}``.
    """
    import random as _random
    from dataclasses import replace
    from app.quant.genome import GENE_BOUNDS_BY_NAME, clamp_gene

    rng = rng or _random.Random(0)
    changes: dict = {}
    # flip the directional bias axis
    try:
        changes["trend_align"] = 2 if int(getattr(champion, "trend_align", 1)) != 2 else 0
    except Exception:  # noqa: BLE001
        changes["trend_align"] = 2
    # jitter two random numeric genes so the adversary is not a mirror clone
    numeric = [b.name for b in GENE_BOUNDS_BY_NAME.values()
               if b.name not in changes and not b.is_int][:8]
    if numeric:
        pick = rng.sample(numeric, k=min(2, len(numeric)))
        for name in pick:
            b = GENE_BOUNDS_BY_NAME[name]
            value = rng.uniform(b.low, b.high)
            changes[name] = clamp_gene(name, value)
    try:
        adversary = replace(champion, **changes)
    except (TypeError, ValueError):
        adversary = champion
    return {"adversary": adversary,
            "reading": (f"avversario generato contro {champion.signature()} "
                        f"(bias invertito, geni {list(changes)})")}


def ladder_tier(survival_record: dict) -> dict:
    """The self-play ladder tier from a REAL survival record.

    ``survival_record`` carries ``tournaments_survived``, ``net_r`` and
    ``consecutive_self_play_losses``. Tier: Platinum requires a net-positive week;
    Diamond requires the unseen gauntlet passed; three consecutive spar losses demote
    one tier. Honest: an empty record is ``Bronze`` and labelled unmeasured.
    """
    if not survival_record:
        return {"tier": "Bronze", "demoted": False, "measured": False,
                "reading": "scala: Bronze (record non misurato)"}
    survived = int(survival_record.get("tournaments_survived") or 0)
    net_r = survival_record.get("net_r")
    gauntlet = bool(survival_record.get("passed_gauntlet"))
    losses = int(survival_record.get("consecutive_self_play_losses") or 0)
    if gauntlet:
        tier = "Diamond"
    elif isinstance(net_r, (int, float)) and net_r > 0 and survived >= 3:
        tier = "Platinum"
    elif survived >= 3:
        tier = "Gold"
    elif survived >= 1:
        tier = "Silver"
    else:
        tier = "Bronze"
    demoted = False
    if losses >= DEMOTION_LOSSES and tier != "Bronze":
        idx = max(0, LADDER.index(tier) - 1)
        tier = LADDER[idx]
        demoted = True
    return {"tier": tier, "demoted": demoted, "measured": True,
            "consecutive_losses": losses,
            "reading": (f"scala: {tier}" + (" (retrocesso per 3 sconfitte)" if demoted else ""))}


def self_play_block(population: list[dict], *, universe=None, config=None,
                    survival_records: dict | None = None) -> dict:
    """The Letter block: run one sparring session across the survivors + the ladder.

    ``population`` is a list of ``{genome, signature, ...}`` best-first. We pair
    opposite-bias survivors and play one round each (bounded to a handful). Honest:
    no population or no frames -> not measured.
    """
    rows = [r for r in (population or []) if r.get("genome") is not None]
    if not rows or not universe:
        return {"version": SELF_PLAY_VERSION, "measured": False, "rounds": [],
                "reading": "self-play: nessun combattente o nessun tape"}
    rounds: list[dict] = []
    biases = {}
    for r in rows[:6]:
        biases[r["signature"]] = directional_bias(r["genome"], universe, config)
    # pair each with the next survivor of opposite bias (one round apiece)
    played = set()
    for i, ra in enumerate(rows[:6]):
        for rb in rows[i + 1:6]:
            if not opposite_bias(biases.get(ra["signature"]), biases.get(rb["signature"])):
                continue
            if ra["signature"] in played or rb["signature"] in played:
                continue
            res = sparring(ra["genome"], rb["genome"], universe, config=config)
            rounds.append({"a": ra["signature"], "b": rb["signature"], **res})
            played.add(ra["signature"])
            played.add(rb["signature"])
            break
        if len(rounds) >= 3:
            break
    ladder = {}
    for sig, rec in (survival_records or {}).items():
        ladder[sig] = ladder_tier(rec)
    winners = [r.get("winner") for r in rounds if r.get("winner")]
    return {
        "version": SELF_PLAY_VERSION,
        "rounds": rounds,
        "n_rounds": len(rounds),
        "winners": winners,
        "ladder": ladder,
        "measured": bool(rounds),
        "reading": (f"self-play: {len(rounds)} round di sparring tra i sopravvissuti "
                    f"({len(winners)} vincitori)"
                    if rounds else "self-play: nessun round (nessun bias opposto)"),
    }
