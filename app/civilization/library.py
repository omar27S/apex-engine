"""THE GIANTS' LIBRARY -- learning from the world (Part Five).

The civilization HUNTS public wisdom: fund letters, documented strategies, open
source indicators, orderflow research, academic forex papers. Everything found is
downloaded, read, and SPOLIATED -- ideas extracted and translated into TESTABLE
hypotheses for the cage. The catalog lives in the state's memory; the Letter's
"LA BIBLIOTECA" section reports what was found and digested.

Free sources only by default (paid = a CEO request with exact cost). The giants'
extracted strategies become SEEDS -- new families inspired by the giants -- but
they pass OUR cage (RR 2.5+, 1% floor, VNSB): no exceptions for legends.

Pure at import (Scar #6): spoliation is a reduction over text the caller already
fetched; the fetching lives in ``tools/library_hunt.py``. Nothing here opens a
socket.
"""

from __future__ import annotations

import re

__all__ = [
    "LIBRARY_VERSION",
    "DIGEST_KINDS",
    "SPOLIATION_PATTERNS",
    "spoliate",
    "to_hypotheses",
    "catalog_entry",
    "library_digest",
    "sources",
]

LIBRARY_VERSION: int = 1

# The kinds of idea the spoliation can extract (each maps to a cage-testable seed).
DIGEST_KINDS: tuple[str, ...] = (
    "entry_rule", "exit_rule", "risk_rule", "indicator", "regime", "warning",
)

# The spoliation grammar: a compiled pattern -> (kind, the seed it becomes). The
# patterns are deliberately simple and honest -- they find DOCUMENTED rules, never
# invent them. A document with no match yields no hypothesis (never a false gem).
SPOLIATION_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\b(?:buy|long|enter|go long)\s+(?:when|if|on)\b(.{0,120})", "entry_rule",
     "enter when: {m}"),
    (r"\b(?:sell|short|exit|go short)\s+(?:when|if|on)\b(.{0,120})", "exit_rule",
     "exit when: {m}"),
    (r"\b(?:stop[- ]?loss|risk)\s+(?:of|at|is)\b(.{0,80})", "risk_rule",
     "risk rule: {m}"),
    (r"\b(?:rsi|macd|atr|bollinger|moving average|ema|sma|ichimoku|vwap)\b(.{0,80})",
     "indicator", "indicator: {m}"),
    (r"\b(?:trend|range|volatil|regime|breakout|reversal)\b(.{0,80})", "regime",
     "regime: {m}"),
    (r"\b(?:blow[- ]?up|collapse|drawdown|margin call|ruin|liquidity)\b(.{0,80})",
     "warning", "warning from history: {m}"),
)


def sources() -> list[dict]:
    """The curated FREE public sources the hunter may visit (no key required).

    Each entry is a stable public URL + what it is. The list is deliberately small
    and honest: public, free, and durable. A paid source is NEVER here -- it takes
    a CEO request with cost and payoff.
    """
    return [
        {"name": "stooq", "url": "https://stooq.com/q/d/?s=eurusd",
         "kind": "market_data", "note": "free historical FX/market quotes"},
        {"name": "wikipedia-forex", "url":
         "https://en.wikipedia.org/wiki/Foreign_exchange_market",
         "kind": "strategy_docs", "note": "the foreign-exchange market, documented"},
        {"name": "wikipedia-moving-average", "url":
         "https://en.wikipedia.org/wiki/Moving_average", "kind": "strategy_docs",
         "note": "moving averages, the base of trend indicators"},
        {"name": "wikipedia-trading", "url":
         "https://en.wikipedia.org/wiki/Technical_analysis", "kind": "reference",
         "note": "reference on technical analysis + indicators"},
        # Kept for the record but NOT relied upon: investopedia.com and
        # babypips.com answer 403 to a non-browser UA, so the hunt honestly skips
        # them (a failed fetch never grows the catalog).
    ]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def spoliate(text: str, *, source: str = "", title: str = "",
             max_per_kind: int = 3) -> list[dict]:
    """SPOLIATE a document: extract the DOCUMENTED ideas into seeds.

    Returns a list of ``{"kind", "seed", "quote", "source"}``. Every extraction
    quotes the text it came from (so a human can audit it) and is capped per kind
    (``max_per_kind``) so one verbose document cannot flood the library.
    """
    found: list[dict] = []
    counts: dict[str, int] = {}
    for pat, kind, tmpl in SPOLIATION_PATTERNS:
        if counts.get(kind, 0) >= max_per_kind:
            continue
        for m in re.finditer(pat, text or "", flags=re.IGNORECASE):
            if counts.get(kind, 0) >= max_per_kind:
                break
            frag = _clean(m.group(1)) if m.groups() else _clean(m.group(0))
            if not frag:
                continue
            seed = tmpl.format(m=frag)
            found.append({"kind": kind, "seed": seed, "quote": _clean(m.group(0)),
                          "source": source, "title": title})
            counts[kind] = counts.get(kind, 0) + 1
    return found


def to_hypotheses(ideas: list[dict]) -> list[dict]:
    """Translate extracted ideas into CAGE-TESTABLE hypotheses (the giants' seeds).

    Every hypothesis carries the cage's non-negotiables (RR floor 2.5, 1% risk
    floor, VNSB) -- a giant's idea is a seed, not a crown: it passes OUR cage or it
    dies with an autopsy like any other body.
    """
    out = []
    for i in ideas:
        out.append({
            "seed": i.get("seed"),
            "kind": i.get("kind"),
            "source": i.get("source"),
            "cage": {"min_target_rr": 2.5, "floor_pct": 1.0, "vnsb": True},
            "status": "pending",
            "testable": True,
        })
    return out


def catalog_entry(*, title: str, source: str, url: str = "", kind: str = "",
                  ideas: list[dict] | None = None, digest: str = "") -> dict:
    """One catalog row: what was found and how much was digested from it."""
    ideas = ideas or []
    kinds: dict[str, int] = {}
    for i in ideas:
        kinds[i.get("kind", "?")] = kinds.get(i.get("kind", "?"), 0) + 1
    return {
        "title": title or url or "(untitled)",
        "source": source,
        "url": url,
        "kind": kind,
        "digested": len(ideas),
        "hypotheses": len(to_hypotheses(ideas)),
        "by_kind": dict(sorted(kinds.items())),
        "digest": digest,
    }


def library_digest(catalog: list[dict], hypotheses: list[dict]) -> dict:
    """A compact reading of the library: what we hold and how much is testable."""
    return {
        "documents": len(catalog),
        "hypotheses": len(hypotheses),
        "pending": sum(1 for h in hypotheses if h.get("status") == "pending"),
        "reading": (f"biblioteca: {len(catalog)} documento/i, "
                    f"{len(hypotheses)} ipotesi testabili"),
        "catalog": catalog,
    }
