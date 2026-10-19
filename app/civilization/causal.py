"""THE WHY ENGINE — Section A of MEGA PHASE 4 (the causal inference layer).

The civilization recorded WHAT happened; it never inferred WHY. This module is the
abductive layer: given a trade's outcome and ALL the evidence that existed at the
time (the falcon's regime timeline, the macro radar's DXY/rates, the web-watch's
news, the strategy's own family and regime), it names the most likely CAUSE, the
CAUSAL CHAIN behind it, and the COUNTERFACTUALS that would have changed the outcome.

Design honesty (the project's founding rule): a cause is only asserted when the
evidence for it is PRESENT. A missing block yields an empty chain and an explicit
"non misurato" -- never an invented story. The pure reducers here are the truth;
the Dragon (deep) may only ADD an inferred reading on top, never overwrite the
measured evidence.

Pure at import (Scar #6): the readings are data; the functions reduce. No I/O, no
clock, no RNG -- ``ts`` is always passed in.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "TREND_FAMILIES",
    "MEAN_REVERSION_FAMILIES",
    "UNSTABLE_REGIMES",
    "parse_ts",
    "extract_evidence",
    "infer_cause",
    "counterfactuals",
    "knowledge_entry",
    "knowledge_base",
    "render_knowledge",
    "dragon_causal_prompt",
]

# Families that need a TREND to work (a regime shift into a range kills them).
TREND_FAMILIES: tuple[str, ...] = (
    "trend", "momentum", "breakout", "donchian", "keltner_expansion",
    "ignition", "squeeze_breakout", "carry",
)
# Families that need a RANGE (a trend shift kills them).
MEAN_REVERSION_FAMILIES: tuple[str, ...] = (
    "mean_reversion", "reversion", "dealing_range", "range", "bollinger",
    "fade", "judas_swing",
)
# Regimes a trend-follower cannot survive.
UNSTABLE_REGIMES: tuple[str, ...] = ("ranging", "choppy", "chop", "dead", "volatile")


def parse_ts(value) -> float | None:
    """An ISO-8601 timestamp -> epoch seconds, or None (honest: never a guess)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _is_trend_family(family: str) -> bool:
    f = (family or "").lower()
    return any(k in f for k in TREND_FAMILIES)


def _is_mr_family(family: str) -> bool:
    f = (family or "").lower()
    return any(k in f for k in MEAN_REVERSION_FAMILIES)


def extract_evidence(*, falcon: dict | None, web_watch: dict | None,
                     civilization: dict | None, trade: dict | None) -> dict:
    """Gather the causal inputs that EXISTED around the trade, honestly.

    Returns a dict with the strategy's family, the regime (if measured), the regime
    shifts near the trade, the DXY direction, and the news items. Every absent piece
    is left out (or None) -- the caller sees exactly what was available.
    """
    trade = trade or {}
    civ = civilization or {}
    fal = falcon or {}
    ww = web_watch or {}

    regime = civ.get("regime") or {}
    regime_counts = regime.get("regimes") or {}
    # The dominant measured regime, if any non-zero count exists.
    dominant = None
    if regime_counts:
        live = {k: v for k, v in regime_counts.items() if v}
        if live:
            dominant = max(live, key=lambda k: live[k])

    shifts = [s for s in (regime.get("shifts") or []) if isinstance(s, dict)]

    # DXY direction from the falcon's macro block (prev -> value).
    macro = (fal.get("falcon") or fal).get("macro") or {}
    dxy = macro.get("DXY") or {}
    dxy_dir = None
    if isinstance(dxy, dict) and dxy.get("value") is not None and dxy.get("prev") is not None:
        try:
            d = float(dxy["value"]) - float(dxy["prev"])
            dxy_dir = "up" if d > 0 else ("down" if d < 0 else "flat")
        except (TypeError, ValueError):
            dxy_dir = None

    news = []
    for item in (ww.get("items") or ww.get("news") or [])[:8]:
        if isinstance(item, dict):
            news.append(item.get("title") or item.get("headline") or str(item))
        else:
            news.append(str(item))

    return {
        "strategy": trade.get("strategy") or trade.get("strategy_id") or trade.get("signature"),
        "family": trade.get("family"),
        "pair": trade.get("pair"),
        "direction": trade.get("direction"),
        "won": trade.get("won"),
        "net_r": trade.get("net_r"),
        "regime": dominant,
        "regime_counts": dict(regime_counts) if regime_counts else None,
        "shifts": shifts,
        "dxy_dir": dxy_dir,
        "news": [n for n in news if n],
    }


def infer_cause(*, trade: dict, evidence: dict, ts: str = "") -> dict:
    """Abduce the most likely cause of a trade's outcome, with its causal chain.

    The rules, in priority order (each fires ONLY on present evidence):

      * A regime shift DURING a trend-family trade that lost -> the shift is the
        cause (the strategy was trend-following into what became a range).
      * An unstable dominant regime for a trend-family trade -> the regime is the
        cause even without a recorded shift.
      * A DXY break aligned with the outcome -> the macro push is the cause.
      * A news item co-timed with the trade -> the news is a candidate cause.
      * Otherwise: no measured cause (honest "non misurato").
    """
    won = trade.get("won")
    family = (evidence.get("family") or trade.get("family") or "")
    chain: list[dict] = []
    cause = "non misurato"
    confidence = 0.0

    regime = evidence.get("regime")
    shifts = evidence.get("shifts") or []
    shifted = bool(shifts) and any(s.get("kind") or s.get("reading") for s in shifts)
    trend = _is_trend_family(family)
    mr = _is_mr_family(family)

    if won is False and trend and shifted:
        cause = "regime_shift_mid_trade"
        confidence = 0.7
        first = shifts[0]
        chain = [
            {"link": "regime_shift",
             "detail": first.get("reading") or first.get("kind") or "a regime shift",
             "ts": first.get("ts") or ""},
            {"link": "strategy_family", "detail": f"{family} needs a trend"},
            {"link": "outcome", "detail": "the trend did not persist -> the trade lost"},
        ]
    elif won is False and trend and regime in UNSTABLE_REGIMES:
        cause = "adverse_regime"
        confidence = 0.6
        chain = [
            {"link": "regime", "detail": f"dominant regime was {regime}"},
            {"link": "strategy_family", "detail": f"{family} cannot work in {regime}"},
            {"link": "outcome", "detail": "the trade lost in a hostile regime"},
        ]
    elif won is True and trend and regime == "trending":
        cause = "regime_aligned"
        confidence = 0.5
        chain = [
            {"link": "regime", "detail": "dominant regime was trending"},
            {"link": "strategy_family", "detail": f"{family} rode the trend"},
            {"link": "outcome", "detail": "the trend persisted -> the trade won"},
        ]
    elif mr and won is False and regime == "trending":
        cause = "trend_defeated_reversion"
        confidence = 0.55
        chain = [
            {"link": "regime", "detail": "dominant regime was trending"},
            {"link": "strategy_family", "detail": f"{family} faded a real trend"},
            {"link": "outcome", "detail": "the trend continued -> the fade lost"},
        ]

    # The macro push: a DXY break aligned with a win, or against a loss.
    dxy_dir = evidence.get("dxy_dir")
    if dxy_dir in ("up", "down") and won is not None:
        if (won is True) or (won is False):
            chain.append({"link": "macro", "detail": f"DXY moved {dxy_dir}"})
            if cause == "non misurato":
                cause = "macro_push"
                confidence = 0.45

    if evidence.get("news"):
        chain.append({"link": "news", "detail": evidence["news"][0]})
        if cause == "non misurato":
            cause = "news_event"
            confidence = 0.35

    return {
        "cause": cause,
        "confidence": round(confidence, 3),
        "family": family,
        "won": won,
        "net_r": trade.get("net_r"),
        "chain": chain,
        "reading": _cause_reading(cause, family, won, chain),
        "ts": ts,
    }


def _cause_reading(cause: str, family: str, won, chain: list[dict]) -> str:
    if cause == "non misurato":
        return "causa non misurata: nessuna prova disponibile"
    if cause == "regime_shift_mid_trade":
        return f"{family}: perso PERCHE' il regime e' cambiato a meta' trade"
    if cause == "adverse_regime":
        return f"{family}: perso PERCHE' il regime era avverso"
    if cause == "regime_aligned":
        return f"{family}: vinto PERCHE' il regime era allineato"
    if cause == "trend_defeated_reversion":
        return f"{family}: perso PERCHE' il trend ha battuto la reversione"
    if cause == "macro_push":
        return f"{family}: il dollaro (DXY) ha spinto il mercato"
    if cause == "news_event":
        return f"{family}: una notizia ha mosso il mercato"
    return f"{family}: {cause}"


def counterfactuals(*, trade: dict, evidence: dict) -> list[dict]:
    """The "what if" branches that would have changed the outcome (honest only)."""
    out: list[dict] = []
    family = evidence.get("family") or trade.get("family") or ""
    won = trade.get("won")
    regime = evidence.get("regime")

    if _is_trend_family(family) and won is False and regime in UNSTABLE_REGIMES:
        out.append({"if": "il regime fosse rimasto in trend",
                    "then": "il trade avrebbe potuto vincere",
                    "kind": "regime"})
    if evidence.get("dxy_dir") in ("up", "down"):
        out.append({"if": "il DXY non avesse rotto",
                    "then": "il segnale forse non sarebbe scattato",
                    "kind": "macro"})
    if evidence.get("shifts"):
        out.append({"if": "fossimo entrati 15 minuti prima",
                    "then": "l'ingresso sarebbe stato migliore",
                    "kind": "timing"})
    if not out:
        out.append({"if": "non ci fossero state le prove mancanti",
                    "then": "il controfattuale resta non misurato",
                    "kind": "unmeasured"})
    return out


def knowledge_entry(*, cause: str, family: str, won, pair: str = "", ts: str = "") -> dict:
    """One row of the causal knowledge base (a cause observed once)."""
    return {"cause": cause, "family": family, "won": won, "pair": pair, "ts": ts}


def knowledge_base(entries: list[dict]) -> dict:
    """Aggregate observed causes into wisdom: which cause drives which outcome.

    Returns per-cause tallies and a plain reading. Honest: with no entries the base
    is empty (never an invented rule).
    """
    by_cause: dict[str, dict] = {}
    for e in entries:
        c = e.get("cause") or "non misurato"
        row = by_cause.setdefault(c, {"cause": c, "n": 0, "losses": 0, "wins": 0,
                                      "families": {}})
        row["n"] += 1
        if e.get("won") is False:
            row["losses"] += 1
        elif e.get("won") is True:
            row["wins"] += 1
        fam = e.get("family") or "?"
        row["families"][fam] = row["families"].get(fam, 0) + 1
    causes = sorted(by_cause.values(), key=lambda r: (-r["losses"], -r["n"], r["cause"]))
    for r in causes:
        r["loss_rate"] = round(r["losses"] / r["n"], 3) if r["n"] else None
    return {"causes": causes, "n_entries": len(entries),
            "reading": render_knowledge(causes, len(entries))}


def render_knowledge(causes: list[dict], n: int) -> str:
    if not n:
        return "base causale vuota: nessun esito registrato"
    top = causes[0]
    return (f"{n} esiti; causa dominante '{top['cause']}' "
            f"({top['losses']} persi su {top['n']}, tasso {top['loss_rate']})")


def dragon_causal_prompt(*, trade: dict, evidence: dict, ts: str = "") -> str:
    """The prompt the Dragon (deep) answers to ADD an inferred reading.

    The measured chain is provided; the model may only add the WHY narrative on top,
    never contradict the evidence.
    """
    return (
        "Sei il Drago di APEX. Ecco l'ESITO di un trade e le PROVE che esistevano:\n"
        f"{trade}\n{evidence}\n"
        "In una frase secca, in italiano, di' la CATENA CAUSALE piu' probabile "
        "(perche' e' andata cosi'). Non inventare prove assenti; se mancano, dillo."
    )
