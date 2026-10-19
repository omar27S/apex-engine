"""THE DEEP IMPROVEMENTS -- the river's intelligence deepens (Part Four, items 10-14).

Five standing improvements, each honest and each feeding the state artifact + Letter:

  * item 10 FALCON-STRATEGY FUSION -- every strategy scored in a micro is scored ALSO
    on "live context awareness": would it have avoided trading during a spread
    blowout? did it prefer the falcon's hot pairs? Aligned strategies gain a survival
    bonus, so evolution SELECTS for market-awareness, not only backtest fitness.
  * item 11 THE COUNTER-FACTUAL LEDGER -- the best setup REJECTED this hour, and what
    happened to it; weekly, the cost of caution and the value of discipline.
  * item 12 THE CROSS-PAIR CONTAGION MAP -- which pairs move TOGETHER right now (live
    correlation, not stale history); feeds the ensemble's diversity + the Council's
    portfolio awareness.
  * item 13 THE GENERATION WISDOM DISTILLERY -- at every Grand, the day's 3 lessons in
    the School's format; monthly, 30 days into ONE Generation Manual entry.
  * item 14 THE MARKET DIARY -- the falcon's 100-word daily narrative of what it SAW.

Honest-measurement throughout: an absent axis is ``None``; a correlation over too few
points is ``None`` (never a fabricated 1.0); a diary with no model is "il falco tace".
Pure at import (Scar #6); the model calls live in the tools.
"""

from __future__ import annotations

import math

__all__ = [
    "DEEP_VERSION",
    "ALIGNMENT_BONUS",
    "MIN_CORRELATION_POINTS",
    "CONTAGION_THRESHOLD",
    "context_alignment",
    "fusion_score",
    "rejected_setup",
    "counterfactual_report",
    "live_correlation",
    "contagion_map",
    "portfolio_warning",
    "generation_wisdom",
    "monthly_manual",
    "market_diary_entry",
    "diary_search",
]

DEEP_VERSION: int = 1

# The survival bonus a fully context-aligned strategy earns (bounded, a bonus only).
ALIGNMENT_BONUS: float = 0.05
# Correlations need at least this many paired points (else honest None).
MIN_CORRELATION_POINTS: int = 12
# |correlation| at or above this is "moving together" on the contagion map.
CONTAGION_THRESHOLD: float = 0.7


# --- item 10: THE FALCON-STRATEGY FUSION ------------------------------------


def context_alignment(*, strategy_pairs: list[str], falcon_hot: list[str],
                      traded_during_blowout: bool,
                      spread_ok: bool = True) -> dict:
    """How well a strategy ALIGNS with the falcon's live reading (item 10).

    Returns a 0..1 alignment plus its parts. Honest: with no falcon reading the
    alignment is ``None`` (unmeasured), never a default bonus.
    """
    hot = list(falcon_hot or [])
    pairs = list(strategy_pairs or [])
    if not hot:
        return {"alignment": None, "measured": False,
                "reading": "fusione non misurata (falco silente)"}
    overlap = len([p for p in pairs if p in hot])
    pair_share = overlap / max(1, len(pairs))
    blowout_penalty = 0.0 if not traded_during_blowout else 0.5
    spread_penalty = 0.0 if spread_ok else 0.5
    align = max(0.0, min(1.0, pair_share - blowout_penalty - spread_penalty))
    return {"alignment": round(align, 4), "measured": True, "pair_share": round(pair_share, 4),
            "traded_during_blowout": bool(traded_during_blowout),
            "reading": (f"allineamento al contesto: {align:.0%} "
                        f"(coppie calde {overlap}/{len(pairs)})")}


def fusion_score(*, fitness: float, alignment: float | None,
                 bonus: float = ALIGNMENT_BONUS) -> dict:
    """Blend a strategy's backtest fitness with its live-context alignment (item 10).

    ``fused = fitness * (1 + bonus * alignment)`` -- aligned strategies gain a bounded
    survival edge. Honest: an unmeasured alignment leaves the fitness UNCHANGED.
    """
    if alignment is None:
        return {"fused": fitness, "bonus_applied": 0.0, "measured": False,
                "reading": "punteggio fuso: fitness puro (contesto non misurato)"}
    a = max(0.0, min(1.0, float(alignment)))
    fused = fitness * (1.0 + bonus * a)
    return {"fused": round(fused, 6), "bonus_applied": round(fused - fitness, 6),
            "measured": True,
            "reading": f"punteggio fuso: {fused:.4f} (bonus contesto +{fused - fitness:.4f})"}


# --- item 11: THE COUNTER-FACTUAL LEDGER ------------------------------------


def rejected_setup(*, ts: str, pair: str, reason: str,
                   outcome_r: float | None = None) -> dict:
    """Log the best setup REJECTED this hour and what happened to it (item 11).

    ``outcome_r`` is the realised R had the setup been taken (``None`` until known).
    """
    return {"ts": str(ts), "pair": str(pair), "reason": str(reason),
            "outcome_r": outcome_r if isinstance(outcome_r, (int, float)) else None}


def counterfactual_report(rejected: list[dict]) -> dict:
    """The weekly Counter-Factual Report: the cost of caution, the value of discipline.

    Honest: only rejections with a KNOWN outcome are summed; the rest are counted as
    pending. An empty ledger reports ``None`` (never a fabricated total).
    """
    known = [r for r in (rejected or []) if isinstance(r.get("outcome_r"), (int, float))]
    pending = len(rejected or []) - len(known)
    if not known:
        return {"n": len(rejected or []), "n_known": 0, "pending": pending,
                "net_r": None, "measured": False,
                "reading": "contro-fattuale: nessun esito noto ancora"}
    net = sum(r["outcome_r"] for r in known)
    missed_win = sum(r["outcome_r"] for r in known if r["outcome_r"] > 0)
    avoided_loss = sum(r["outcome_r"] for r in known if r["outcome_r"] < 0)
    return {"n": len(rejected or []), "n_known": len(known), "pending": pending,
            "net_r": round(net, 2), "missed_win_r": round(missed_win, 2),
            "avoided_loss_r": round(avoided_loss, 2), "measured": True,
            "reading": (f"contro-fattuale: netto {net:+.1f}R su {len(known)} rifiuti "
                        f"(mancati +{missed_win:.1f}R, evitati {avoided_loss:.1f}R)")}


# --- item 12: THE CROSS-PAIR CONTAGION MAP ----------------------------------


def live_correlation(a: list[float], b: list[float],
                     min_points: int = MIN_CORRELATION_POINTS) -> float | None:
    """The LIVE Pearson correlation of two return series (item 12).

    Honest: fewer than ``min_points`` paired points, or a zero-variance series, is
    ``None`` -- never a fabricated 1.0.
    """
    n = min(len(a or []), len(b or []))
    if n < max(2, int(min_points)):
        return None
    xs, ys = list(a)[:n], list(b)[:n]
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return round(cov / math.sqrt(vx * vy), 4)


def contagion_map(returns: dict, *, threshold: float = CONTAGION_THRESHOLD) -> dict:
    """The LIVE correlation map: which pairs move TOGETHER right now (item 12).

    ``returns`` maps pair -> its recent return series. Pairs whose |correlation| is at
    or above ``threshold`` are grouped. Honest: too-short series are skipped.
    """
    pairs = [p for p, s in (returns or {}).items() if len(s or []) >= MIN_CORRELATION_POINTS]
    links: list[dict] = []
    for i, p in enumerate(pairs):
        for q in pairs[i + 1:]:
            c = live_correlation(returns[p], returns[q])
            if c is not None and abs(c) >= threshold:
                links.append({"a": p, "b": q, "corr": c,
                              "sign": "same" if c > 0 else "inverse"})
    links.sort(key=lambda l: (-abs(l["corr"]), l["a"], l["b"]))
    return {"pairs": pairs, "links": links,
            "reading": (f"contagio: {len(links)} legami forti tra {len(pairs)} coppie"
                        if links else "contagio: nessun legame forte misurato")}


def portfolio_warning(proposed_pairs: list[str], contagion: dict) -> dict | None:
    """Warn the Council when proposed trades are really ONE trade (item 12).

    "You are about to take 3 trades that are currently ONE trade -- the map shows it."
    """
    proposed = set(proposed_pairs or [])
    clustered = [l for l in (contagion or {}).get("links", [])
                 if l["a"] in proposed and l["b"] in proposed]
    if len(proposed) >= 2 and clustered:
        return {"clustered": clustered, "n": len(clustered),
                "reading": (f"ATTENZIONE: {len(proposed)} operazioni sono in realta "
                            f"{len(clustered)} correlazioni forti -- e' un solo trade")}
    return None


# --- item 13: THE GENERATION WISDOM DISTILLERY ------------------------------


def generation_wisdom(*, day: str, lessons: list[str], source: str = "dragon") -> dict:
    """One day's GENERATION WISDOM entry: the 3 most important lessons (item 13).

    The Dragon (Deep) writes it; the entry lands in the School's curriculum format.
    Honest: no lessons -> an empty entry (the day taught nothing it could name).
    """
    top = [str(x) for x in (lessons or []) if str(x).strip()][:3]
    return {"day": str(day), "lessons": top, "n": len(top), "source": source,
            "reading": (f"saggezza della generazione ({day}): {len(top)} lezioni"
                        if top else f"saggezza della generazione ({day}): nessuna lezione")}


def monthly_manual(*, month: str, daily_entries: list[dict]) -> dict:
    """Distill 30 daily entries into ONE Generation Manual entry (item 13).

    Honest: an empty month yields an empty manual entry (never an invented lesson).
    """
    lessons: list[str] = []
    for e in (daily_entries or []):
        lessons.extend(e.get("lessons") or [])
    # keep the first appearance of each lesson (stable, deduplicated)
    seen: set[str] = set()
    unique = [x for x in lessons if not (x in seen or seen.add(x))]
    return {"month": str(month), "lessons": unique[:12], "n": len(unique),
            "days": len(daily_entries or []),
            "reading": (f"manuale della generazione ({month}): {len(unique)} lezioni "
                        f"da {len(daily_entries or [])} giorni")}


# --- item 14: THE MARKET DIARY ----------------------------------------------


def market_diary_entry(*, day: str, text: str, ts: str = "",
                       source: str = "falcon") -> dict:
    """One day's MARKET DIARY entry: the falcon's narrative of what it SAW (item 14).

    Honest: an empty narrative is "il falco tace", never a fabricated story.
    """
    body = str(text or "").strip()
    return {"day": str(day), "ts": ts, "text": body, "source": source,
            "spoken": bool(body),
            "reading": (body[:160] if body else "il falco tace (nessuna narrazione)")}


def diary_search(entries: list[dict], *, day: str | None = None,
                 contains: str | None = None) -> list[dict]:
    """Search the market diary -- "read the diary from the last FOMC day" (item 14)."""
    needle = str(contains).lower() if contains else None
    return [e for e in (entries or [])
            if (day is None or e.get("day") == day)
            and (needle is None or needle in str(e.get("text", "")).lower())]
