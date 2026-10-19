"""THE NAVIGATOR — the eyes on the world (real pages, seen as pages).

The agents do not only read feeds; they OPEN real pages and SEE them. This module
fetches a page over plain HTTP GET, parses its LAYOUT HIERARCHY (what is a title,
what is emphasized, what is large and near the top) and builds the page's VISUAL
IMPORTANCE MAP — so an agent scans a page the way a human scans: title first,
emphasis next, then read what matters.

Two standing laws hold here:

* READ-ONLY. Only ``GET`` on ``http``/``https`` is permitted (:func:`read_only_guard`);
  there are no accounts, no logins, and no click that commits anything. The
  navigator looks; it never touches.
* THE CAGE EXTENDS TO THE WEB. Page content is DATA, never code: it is parsed with
  the stdlib ``HTMLParser`` (no JavaScript is ever executed, nothing is ``eval``'d).
  A page cannot reach into the civilization; it can only be looked at.

Honest by construction: a fetch that fails (no egress, 403, timeout) yields a
sighting with ``ok=False`` and the real error — never a fabricated page.
"""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser

from app.civilization import gaze

__all__ = [
    "SITE_TARGETS",
    "read_only_guard",
    "fetch_page",
    "parse_layout",
    "visual_selector",
    "layout_image",
    "patrol_slot",
    "patrol",
    "NAVIGATOR_VERSION",
]

NAVIGATOR_VERSION: int = 1

# The three real sites of the first patrol (Part Two / First Act B).
SITE_TARGETS: tuple[dict, ...] = (
    {"name": "forexfactory", "kind": "calendar",
     "url": "https://www.forexfactory.com/calendar"},
    {"name": "investing", "kind": "news",
     "url": "https://www.investing.com/news/"},
    {"name": "ecb", "kind": "central_bank",
     "url": "https://www.ecb.europa.eu/"},
)

_MAX_BYTES: int = 400_000          # cap what we read from a page (honest truncation)
_MAX_TEXT: int = 240               # cap a single element's text


def read_only_guard(url: str) -> None:
    """Fail-closed unless ``url`` is a plain ``http``/``https`` GET target."""
    u = str(url or "").strip()
    if not re.match(r"^https?://", u, re.IGNORECASE):
        raise ValueError(f"read-only navigator refuses non-http(s) url: {url!r}")


def fetch_page(url: str, *, timeout: float = 12.0,
               user_agent: str = "apex-gaze/1.0 (read-only; +https://github.com/the-private-vault)") -> dict:
    """GET a real page (read-only). Returns an HONEST result, never a fake one."""
    read_only_guard(url)
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — guarded
            raw = resp.read(_MAX_BYTES)
            status = getattr(resp, "status", None) or resp.getcode()
        text = raw.decode("utf-8", errors="replace")
        return {"url": url, "ok": True, "status": int(status), "bytes": len(raw),
                "text": text, "error": None}
    except urllib.error.HTTPError as e:
        return {"url": url, "ok": False, "status": int(e.code), "bytes": 0,
                "text": "", "error": f"HTTP {e.code} {e.reason}"}
    except Exception as e:  # noqa: BLE001 — no egress / timeout / DNS: report honestly
        return {"url": url, "ok": False, "status": None, "bytes": 0,
                "text": "", "error": f"{type(e).__name__}: {e}"}


class _Layout(HTMLParser):
    """A read-only layout reader: tags + text + depth + emphasis (data only)."""

    _SKIP = {"script", "style", "noscript", "svg", "head", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.title = ""
        self._in_title = False
        self._stack: list[str] = []
        self._cur_tag: str | None = None
        self._cur_text: list[str] = []
        self._cur_depth = 0
        self.elements: list[dict] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self.depth += 1
        if tag in self._SKIP:
            self._stack.append(tag)
            return
        if tag == "title":
            self._in_title = True
        self._flush()
        self._cur_tag, self._cur_text, self._cur_depth = tag, [], self.depth
        self._stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        self._flush()
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        d = data.strip()
        if not d:
            return
        if self._in_title and not self.title:
            self.title = d[:_MAX_TEXT]
        elif self._cur_tag:
            self._cur_text.append(d)

    def _flush(self):
        if self._cur_tag and self._cur_text:
            txt = " ".join(self._cur_text).strip()[:_MAX_TEXT]
            if txt:
                self.elements.append({"tag": self._cur_tag, "text": txt,
                                      "depth": self._cur_depth})
        self._cur_tag, self._cur_text = None, []


def parse_layout(html: str) -> dict:
    """The LAYOUT HIERARCHY of a page: title, headings, emphasis, blocks (data)."""
    p = _Layout()
    try:
        p.feed(html or "")
        p._flush()
    except Exception:  # noqa: BLE001 — a malformed page is data, not a crash
        pass
    els = p.elements
    headings = [e for e in els if e["tag"] in ("h1", "h2", "h3", "h4")]
    emphasis = [e for e in els if e["tag"] in ("strong", "b", "em")]
    links = [e for e in els if e["tag"] == "a"]
    blocks = [e for e in els if e["tag"] in ("p", "div", "span", "li")]
    return {"title": p.title, "headings": headings, "emphasis": emphasis,
            "links": links, "blocks": blocks, "n_elements": len(els)}


def visual_selector(layout: dict, *, k: int = 5) -> list[dict]:
    """DECIDE what merits deep reading: the page's visual importance map, ranked.

    A human scans title first, then headings, then emphasis, then the largest text
    blocks near the top. The score is deterministic and honest (no content is
    invented); an empty page yields an empty selection.
    """
    picked: list[dict] = []
    title = (layout or {}).get("title")
    if title:
        picked.append({"text": title, "why": "titolo", "score": 100.0})
    for e in (layout or {}).get("headings", []):
        picked.append({"text": e["text"], "why": f"intestazione <{e['tag']}>",
                       "score": 80.0 - 5.0 * e.get("depth", 0)})
    for e in (layout or {}).get("emphasis", []):
        picked.append({"text": e["text"], "why": "enfasi", "score": 60.0})
    for e in (layout or {}).get("blocks", []):
        # larger text blocks near the top matter more (length + shallowness)
        score = min(50.0, len(e["text"]) / 4.0) + max(0.0, 20.0 - e.get("depth", 0))
        picked.append({"text": e["text"], "why": "blocco", "score": score})
    # de-dup by text, keep the highest score, then rank deterministically
    best: dict[str, dict] = {}
    for it in picked:
        cur = best.get(it["text"])
        if cur is None or it["score"] > cur["score"]:
            best[it["text"]] = it
    ranked = sorted(best.values(), key=lambda x: (-x["score"], x["text"]))
    return ranked[:max(0, int(k))]


def layout_image(layout: dict, *, width: int = 240, height: int = 180,
                 k: int = 6) -> bytes:
    """Render the page's VISUAL IMPORTANCE MAP as a PNG (bars, top = first seen).

    Each selected element is a bar: length ~ importance, color ~ kind (title gold,
    heading teal, emphasis blue, block grey). Pure and deterministic.
    """
    c = gaze.Canvas(width, height)
    c.rect(0, 0, width - 1, 0, gaze._GRID)
    sel = visual_selector(layout, k=k)
    if not sel:
        c.rect(1, 1, width - 2, height - 2, gaze._EMPTY)
        return c.png()
    color = {"titolo": gaze._WALL, "enfasi": (96, 140, 220)}
    row = max(3, (height - 2) // len(sel))
    for i, it in enumerate(sel):
        y = 1 + i * row
        blen = max(2, round(min(1.0, it["score"] / 100.0) * (width - 3)))
        col = color.get(it["why"], (70, 180, 170) if it["why"].startswith("intestazione")
                        else (90, 96, 110))
        c.rect(1, y, blen, y + row - 2, col)
    return c.png()


def patrol_slot(*, agent: str, target: dict, ts: str = "") -> dict:
    """One patrol slot: an agent takes the watch over one real site."""
    return {"kind": "patrol", "agent": str(agent),
            "target": str((target or {}).get("name")),
            "url": str((target or {}).get("url")), "ts": ts,
            "why": "la vedetta guarda il web finanziario e riporta cio' che colpisce",
            "reading": f"{agent} tiene la vedetta su {(target or {}).get('name')}"}


def patrol(targets: tuple[dict, ...] = SITE_TARGETS, *,
           agents: list[str] | None = None, ts: str = "",
           fetcher=fetch_page) -> dict:
    """The visual watch rotation: browse the sites and report WHAT CATCHES THE EYE.

    Read-only and honest. For each target: fetch, parse the layout, select what
    matters, and render the importance map (kept as a sha256, so the state stays
    lean but the image's identity is provable). A failed fetch is reported, never
    faked. Returns ``{"sightings": [...], "ok_count", "reading"}``.
    """
    agents = agents or ["scout-1", "scout-2", "scout-3"]
    sightings: list[dict] = []
    for i, tgt in enumerate(targets or ()):
        agent = agents[i % len(agents)] if agents else "scout"
        page = fetcher(tgt.get("url", ""))
        layout = parse_layout(page.get("text", "")) if page.get("ok") else {}
        highlights = visual_selector(layout, k=4) if page.get("ok") else []
        img_sha = None
        if page.get("ok"):
            png = layout_image(layout)
            img_sha = hashlib.sha256(png).hexdigest()
        sighting = {
            "target": tgt.get("name"), "kind": tgt.get("kind"), "url": tgt.get("url"),
            "agent": agent, "ok": bool(page.get("ok")), "status": page.get("status"),
            "title": layout.get("title") or None,
            "highlights": [h["text"] for h in highlights],
            "n_elements": int(layout.get("n_elements") or 0),
            "image_sha256": img_sha, "error": page.get("error"),
            "reading": (f"{tgt.get('name')}: visto, {layout.get('n_elements', 0)} "
                        f"elementi, {len(highlights)} in evidenza"
                        if page.get("ok") else
                        f"{tgt.get('name')}: NON visto ({page.get('error')})"),
            "ts": ts,
        }
        sightings.append(sighting)
    ok = sum(1 for s in sightings if s["ok"])
    return {"sightings": sightings, "ok_count": ok,
            "reading": f"vedetta: {ok}/{len(sightings)} siti visti"}
