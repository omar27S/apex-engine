"""THE GAZE — the civilization's vision (it SEES the market and the world).

80% of a brain's information arrives through the eyes. The agents already had a
brain; here they get EYES. This module is LITERAL VISION: the market rendered as
charts, walls of liquidity and a flowing tape; pages rendered as a visual
importance map; and a visual memory that recognises a shape it has SEEN before.

Two invariants hold everywhere here:

* PURE AND CAUSAL. Every renderer takes the frame data it is given and returns an
  image. Nothing reads a clock or an RNG, and a renderer can only ever draw the
  bars it was handed — so rendering the past never sees the future.
* HONEST. An unmeasured axis is ``None``/absent and an unmeasured frame renders
  EMPTY (``blind_frame``), never a fabricated candle. A shape is recognised only
  above a similarity floor; below it the answer is "never seen before".

The eyes INFORM. They never trade and never override the Ten Laws: a VEDO
statement enters the weighing field as the most trusted sense, but a decision is
still born only when every gate clears (see ``one_brain.decide``).

Stdlib only (the runner image carries no imaging library): the PNG encoder is
built here on ``zlib`` + ``struct``, so vision costs no new dependency.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

__all__ = [
    "GAZE_VERSION",
    "MONITOR_VIEWS",
    "VISUAL_FLOOR",
    "VEDO_FIELD_BONUS",
    "FLOW_ITALIAN",
    "encode_png",
    "Canvas",
    "render_chart",
    "render_multi_timeframe",
    "render_dom_wall",
    "render_tape",
    "render_heatmap",
    "blind_frame",
    "ascii_chart",
    "vision_on_demand",
    "visual_signature",
    "visual_similarity",
    "visual_recognise",
    "remember_visual",
    "deja_vu",
    "archive_scene",
    "find_scenes",
    "flow_slot",
    "harvest_intuition",
    "flow_budget",
    "visual_context",
    "convergent_seeing",
    "gaze_report",
]

GAZE_VERSION: int = 1

# The permanent visual stations every agent can watch (Part One).
MONITOR_VIEWS: tuple[str, ...] = (
    "multi_timeframe", "dom_wall", "tape_flow", "heatmap",
)

# A shape is called RECOGNISED only at/above this cosine similarity; below it the
# honest answer is "never seen before" (never a fabricated match).
VISUAL_FLOOR: float = 0.6

# The eye's extra trust in the weighing field (Part Five): a supporter whose mode
# was VEDO ("I SEE") counts this much more than its measured reliability alone. A
# stated constant — not a hidden multiplier — and it never overrides the Law.
VEDO_FIELD_BONUS: float = 1.15

# The flow-born seeing (Part Three), in the tongue's voice.
FLOW_ITALIAN: str = "L'HO VISTO NEL FLOW"

# --- the palette (deterministic; no theme, no randomness) --------------------
_BG = (12, 14, 20)
_GRID = (34, 38, 48)
_UP = (38, 166, 154)
_DOWN = (239, 83, 80)
_WICK = (176, 182, 196)
_TEXT = (208, 214, 224)
_WALL = (250, 214, 96)
_EMPTY = (24, 26, 34)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Linear blend of two colors; ``t`` in [0, 1] (clamped). Honest rounding."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
    return (round(a[0] + (b[0] - a[0]) * t),
            round(a[1] + (b[1] - a[1]) * t),
            round(a[2] + (b[2] - a[2]) * t))


class Canvas:
    """A tiny RGB framebuffer that can serialize itself to a PNG (stdlib only)."""

    def __init__(self, width: int, height: int, bg: tuple[int, int, int] = _BG):
        self.w = int(width)
        self.h = int(height)
        self.buf = bytearray(self.w * self.h * 3)
        self.fill(bg)

    def fill(self, color: tuple[int, int, int]) -> "Canvas":
        row = bytes(color) * self.w
        for y in range(self.h):
            i = y * self.w * 3
            self.buf[i:i + self.w * 3] = row
        return self

    def set(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            base = y * self.w * 3
            for x in range(max(0, x0), min(self.w - 1, x1) + 1):
                i = base + x * 3
                self.buf[i:i + 3] = bytes(color)

    def vline(self, x: int, y0: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            self.set(x, y, color)

    def png(self) -> bytes:
        return encode_png(self.w, self.h, bytes(self.buf))


def encode_png(width: int, height: int, pixels: bytes) -> bytes:
    """Encode raw RGB bytes into a PNG (8-bit truecolor, no interlace).

    Deterministic: the same pixels always yield the same bytes, so a rendered
    scene can be hashed and compared (the archive's photo identity).
    """
    if len(pixels) != width * height * 3:
        raise ValueError("pixel buffer does not match width*height*3")
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)                       # filter type 0 (None) per scanline
        raw += pixels[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + _chunk(b"IEND", b""))


def _chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


# --- PART ONE — THE PHYSICAL EYES -------------------------------------------

def _candles_of(frame: dict) -> list[dict]:
    """Normalize a frame's candles to ``{o,h,l,c,v}`` dicts (empty when none)."""
    out: list[dict] = []
    for b in (frame or {}).get("candles") or []:
        try:
            if isinstance(b, dict):
                o, h, l, c = (float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"]))
                v = float(b.get("v") or 0.0)
            else:                        # (o, h, l, c[, v])
                o, h, l, c = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
                v = float(b[4]) if len(b) > 4 else 0.0
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        out.append({"o": o, "h": h, "l": l, "c": c, "v": v})
    return out


def _draw_panel(c: Canvas, x0: int, w: int, frame: dict, *, h: int) -> None:
    """Draw ONE candlestick panel (pair + timeframe) into ``c`` at ``x0``."""
    candles = _candles_of(frame)
    # frame the panel
    c.rect(x0, 0, x0 + w - 1, 0, _GRID)
    c.vline(x0, 0, h - 1, _GRID)
    if not candles:
        c.rect(x0 + 1, 1, x0 + w - 2, h - 2, _EMPTY)     # honest blank: no data
        return
    hi = max(b["h"] for b in candles)
    lo = min(b["l"] for b in candles)
    rng = (hi - lo) or 1.0
    top, bottom = 14, h - 4
    plot = max(1, bottom - top)
    vol_max = max((b["v"] for b in candles), default=0.0) or 1.0
    n = len(candles)
    step = max(1, (w - 2) // n)

    def yp(price: float) -> int:
        return top + round((hi - price) / rng * plot)

    for i, b in enumerate(candles):
        x = x0 + 1 + i * step
        up = b["c"] >= b["o"]
        col = _UP if up else _DOWN
        c.vline(x, yp(b["h"]), yp(b["l"]), _WICK)
        y_o, y_c = yp(b["o"]), yp(b["c"])
        c.rect(x - max(0, step // 4), min(y_o, y_c), x + max(0, step // 4), max(y_o, y_c), col)
        # the volume stub (bottom band): height by relative volume
        vh = round(b["v"] / vol_max * 6)
        if vh:
            c.rect(x, h - 1 - vh, x, h - 2, _mix(col, _BG, 0.5))


def render_chart(frames: list[dict], *, width: int = 360, height: int = 180) -> bytes:
    """Render one or more candlestick frames SIDE BY SIDE into a PNG.

    ``frames`` is a list of ``{"pair", "tf", "candles": [{o,h,l,c,v}...]}``. Pure
    and causal: only the bars handed in are drawn. An empty frame renders blank.
    """
    frames = list(frames or [])
    n = len(frames) or 1
    c = Canvas(width, height)
    pw = max(1, width // n)
    for i, fr in enumerate(frames):
        _draw_panel(c, i * pw, pw, fr or {}, h=height)
    return c.png()


def render_multi_timeframe(pair: str, frames_by_tf: dict[str, dict], *,
                           width: int = 540, height: int = 180) -> bytes:
    """H1+H4+D1 (any set of timeframes) side by side — the trader's whole screen.

    ``frames_by_tf`` maps a timeframe label to a frame; the panels are ordered by a
    deterministic preference (H1, H4, D1 first) so the same input renders the same.
    """
    order = ["H1", "H4", "D1", "M15", "M5", "W1", "MN"]
    keys = sorted(frames_by_tf or {}, key=lambda k: (order.index(k) if k in order else 99, k))
    frames = []
    for tf in keys:
        fr = dict(frames_by_tf[tf] or {})
        fr.setdefault("pair", pair)
        fr["tf"] = tf
        frames.append(fr)
    return render_chart(frames, width=width, height=height)


def render_dom_wall(bids: list, asks: list, *, width: int = 240, height: int = 180,
                    mid: float | None = None) -> bytes:
    """The DOM WALL: bid depth (green, left) and ask depth (red, right) as bars.

    Each row is a price level; a bar's length is its size, so the STACKED side and
    the VACUUM are visible at a glance. The single largest level is flagged (wall).
    Pure: only the levels passed in are drawn.
    """
    c = Canvas(width, height)
    c.rect(0, 0, width - 1, 0, _GRID)
    if not bids and not asks:
        c.rect(1, 1, width - 2, height - 2, _EMPTY)
        return c.png()
    half = width // 2
    c.vline(half, 1, height - 1, _GRID)                    # the mid/spread column
    sizes = [float(s) for _, s in list(bids) + list(asks)]
    smax = max(sizes, default=0.0) or 1.0
    n = max(len(bids), len(asks)) or 1
    row = max(2, (height - 2) // n)
    for i, (price, size) in enumerate(bids or []):
        y = 1 + i * row
        blen = round(float(size) / smax * (half - 2))
        col = _WALL if float(size) >= smax else _UP
        c.rect(half - 1 - blen, y, half - 2, y + row - 2, col)
    for i, (price, size) in enumerate(asks or []):
        y = 1 + i * row
        blen = round(float(size) / smax * (half - 2))
        col = _WALL if float(size) >= smax else _DOWN
        c.rect(half + 1, y, half + blen, y + row - 2, col)
    return c.png()


def render_tape(ticks: list, *, width: int = 360, height: int = 90) -> bytes:
    """The TAPE FLOW: the tick ribbon — price as a flowing line, rhythm below.

    ``ticks`` is a list of prices (or ``(price, direction)``). The top band draws
    the path (colored by direction); the bottom band draws each tick's size, so the
    market's RHYTHM (calm / fast / panicked) is visible like a tape reader sees it.
    """
    c = Canvas(width, height)
    c.rect(0, 0, width - 1, 0, _GRID)
    if not ticks:
        c.rect(1, 1, width - 2, height - 2, _EMPTY)
        return c.png()
    prices: list[float] = []
    for t in ticks:
        prices.append(float(t[0] if isinstance(t, (list, tuple)) else t))
    hi, lo = max(prices), min(prices)
    rng = (hi - lo) or 1.0
    top, bottom = 4, height // 2
    plot = max(1, bottom - top)
    n = len(prices)
    step = max(1, (width - 2) // max(1, n))
    prev_y = None
    for i, p in enumerate(prices):
        x = 1 + i * step
        y = top + round((hi - p) / rng * plot)
        col = _UP if (i and p >= prices[i - 1]) else _DOWN
        if prev_y is not None:
            c.vline(x, min(prev_y, y), max(prev_y, y), col)
        c.set(x, y, col)
        prev_y = y
    deltas = [abs(prices[i] - prices[i - 1]) for i in range(1, n)]
    dmax = max(deltas, default=0.0) or 1.0
    band = height - 3
    for i, d in enumerate(deltas):
        x = 1 + i * step
        bh = round(d / dmax * (height - bottom - 6))
        c.rect(x, band - bh, x, band, _mix(_TEXT, _BG, 0.4))
    return c.png()


def render_heatmap(cells: list[dict], *, width: int = 300, height: int = 120,
                   cols: int = 5) -> bytes:
    """The HEAT MAP: every operational pair as a cell, red->green by change.

    ``cells`` is ``[{"pair","change"}...]`` where ``change`` is a fraction (e.g.
    0.012 = +1.2%). An unknown change is neutral (honest grey), never colored.
    """
    c = Canvas(width, height)
    cells = list(cells or [])
    if not cells:
        c.rect(0, 0, width - 1, height - 1, _EMPTY)
        return c.png()
    cols = max(1, int(cols))
    rows = (len(cells) + cols - 1) // cols
    cw = max(1, width // cols)
    ch = max(1, height // rows)
    vals = [abs(float(x["change"])) for x in cells
            if isinstance(x.get("change"), (int, float))]
    vmax = max(vals, default=0.0) or 1.0
    for i, cell in enumerate(cells):
        gx, gy = i % cols, i // cols
        ch_v = cell.get("change")
        if isinstance(ch_v, (int, float)):
            t = min(1.0, abs(float(ch_v)) / vmax)
            col = _mix(_BG, _UP if float(ch_v) >= 0 else _DOWN, 0.25 + 0.75 * t)
        else:
            col = _EMPTY
        c.rect(gx * cw, gy * ch, gx * cw + cw - 2, gy * ch + ch - 2, col)
    return c.png()


def blind_frame(*, width: int = 120, height: int = 80) -> bytes:
    """The honest blind frame: what the eyes render when there is nothing to see."""
    c = Canvas(width, height)
    c.rect(0, 0, width - 1, height - 1, _EMPTY)
    c.rect(0, 0, width - 1, 0, _GRID)
    return c.png()


def ascii_chart(candles: list, *, width: int = 48, height: int = 12) -> str:
    """An ASCII candlestick scene — so the Letter can PRINT what the eyes saw.

    Deterministic and honest: empty candles print the blindness, never a drawn fake.
    ``|`` is a wick, ``#`` an up body, ``=`` a down body.
    """
    bars = _candles_of({"candles": candles})
    if not bars:
        return "(nessuna scena: gli occhi sono ciechi)"
    step = max(1, len(bars) // max(1, width))
    cols: list[dict] = []
    for i in range(0, len(bars), step):
        grp = bars[i:i + step]
        cols.append({"o": grp[0]["o"], "h": max(b["h"] for b in grp),
                     "l": min(b["l"] for b in grp), "c": grp[-1]["c"]})
    cols = cols[-width:]
    hi = max(c["h"] for c in cols)
    lo = min(c["l"] for c in cols)
    rng = (hi - lo) or 1.0
    rows = [[" "] * len(cols) for _ in range(height)]

    def _row(price: float) -> int:
        return min(height - 1, max(0, round((hi - price) / rng * (height - 1))))

    for x, c in enumerate(cols):
        yh, yl = _row(c["h"]), _row(c["l"])
        for y in range(min(yh, yl), max(yh, yl) + 1):
            rows[y][x] = "|"
        yo, yc = _row(c["o"]), _row(c["c"])
        ch = "#" if c["c"] >= c["o"] else "="
        for y in range(min(yo, yc), max(yo, yc) + 1):
            rows[y][x] = ch
    return "\n".join("".join(row) for row in rows)


def vision_on_demand(candles: list, *, pair: str, tf: str = "H1") -> dict:
    """THE ON-DEMAND VISION ("fammi vedere"): render the market as a photograph.

    A pure capability: it takes the candles it is given and returns the PNG, its
    sha256, and an ASCII preview — so a "vision" job in the queue can hand any mind
    the image it asked for. Causal: it can only draw the bars handed in.
    """
    bars = _candles_of({"candles": candles})
    if not bars:
        png = blind_frame()
        return {"pair": pair, "tf": tf, "ok": False, "png": png,
                "sha256": hashlib.sha256(png).hexdigest(), "ascii": ascii_chart([]),
                "reading": f"{pair} {tf}: gli occhi sono ciechi (nessuna tape)"}
    png = render_chart([{"pair": pair, "tf": tf, "candles": bars}],
                       width=360, height=180)
    return {"pair": pair, "tf": tf, "ok": True, "png": png,
            "sha256": hashlib.sha256(png).hexdigest(), "ascii": ascii_chart(bars),
            "bars": len(bars),
            "reading": f"{pair} {tf}: visto ({len(bars)} barre)"}


# --- PART THREE/FOUR — THE VISUAL MEMORY (shape, déjà-vu, the photo archive) --

def visual_signature(candles: list) -> dict | None:
    """A compact, deterministic VISUAL feature vector for a candle scene.

    The features are proportions and texture (body/range, wick/range, up-share,
    trend, range volatility) — so two scenes with the same SHAPE land close even at
    different price levels. Empty input -> ``None`` (nothing to see, honestly).
    """
    bars = _candles_of({"candles": candles})
    if not bars:
        return None
    feats: list[float] = []
    body, up_w, lo_w, rngs, ups = [], [], [], [], 0
    for b in bars:
        r = (b["h"] - b["l"]) or 1e-9
        body.append(abs(b["c"] - b["o"]) / r)
        up_w.append((b["h"] - max(b["o"], b["c"])) / r)
        lo_w.append((min(b["o"], b["c"]) - b["l"]) / r)
        rngs.append(r / (b["c"] or 1.0))
        ups += 1 if b["c"] >= b["o"] else 0
    n = len(bars)
    mean_rng = sum(rngs) / n or 1e-9
    var = sum((x - mean_rng) ** 2 for x in rngs) / n
    feats = [
        sum(body) / n,
        sum(up_w) / n,
        sum(lo_w) / n,
        ups / n,
        (bars[-1]["c"] - bars[0]["o"]) / (bars[0]["o"] or 1.0),
        (var ** 0.5) / mean_rng,                     # volatility texture (CoV)
    ]
    return {"features": [round(f, 6) for f in feats], "n": n}


def visual_similarity(a: dict | None, b: dict | None) -> float:
    """Cosine similarity of two signatures, clamped to [0, 1]. Missing -> 0.0."""
    if not a or not b:
        return 0.0
    fa, fb = a.get("features") or [], b.get("features") or []
    if len(fa) != len(fb) or not fa:
        return 0.0
    dot = sum(x * y for x, y in zip(fa, fb))
    na = sum(x * x for x in fa) ** 0.5
    nb = sum(y * y for y in fb) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    s = dot / (na * nb)
    return round(max(0.0, min(1.0, s)), 6)


def visual_recognise(library: list[dict], signature: dict | None, *,
                     floor: float = VISUAL_FLOOR) -> dict:
    """Match a scene against the visual library: "I have SEEN this form before".

    Returns the best match at/above ``floor`` with its honest similarity and
    resolution, or ``{"recognised": False, "reading": "forma mai vista prima"}``.
    Never fabricates a match.
    """
    if not signature:
        return {"recognised": False, "similarity": 0.0, "n": 0,
                "reading": "nessuna scena da riconoscere"}
    best, best_sim = None, 0.0
    for e in library or []:
        sim = visual_similarity(signature, e.get("signature"))
        if sim > best_sim:
            best, best_sim = e, sim
    if best is not None and best_sim >= floor:
        return {"recognised": True, "label": best.get("label"),
                "similarity": best_sim, "resolved_up": best.get("resolved_up"),
                "n": int(best.get("n") or 0),
                "reading": (f"forma gia' vista: {best.get('label')} "
                            f"(somiglianza {best_sim:.2f}, {int(best.get('n') or 0)} volte)")}
    return {"recognised": False, "similarity": best_sim, "n": 0,
            "reading": "forma mai vista prima"}


def remember_visual(library: list[dict], *, signature: dict | None, label: str,
                    resolved_up: bool, ts: str = "") -> dict | None:
    """Record a seen shape in the visual library (increment its count on re-sight).

    Deterministic and honest: the same label accumulates sightings; a new label
    appends. Returns the entry, or ``None`` when there is no signature to remember.
    """
    if not signature:
        return None
    for e in library or []:
        if e.get("label") == label:
            e["n"] = int(e.get("n") or 0) + 1
            e["resolved_up"] = bool(resolved_up)
            e["ts"] = ts or e.get("ts")
            e["signature"] = signature
            return e
    entry = {"label": str(label), "signature": signature, "n": 1,
             "resolved_up": bool(resolved_up), "ts": ts}
    library.append(entry)
    return entry


def deja_vu(archive: list[dict], signature: dict | None, *,
            floor: float = VISUAL_FLOOR) -> dict | None:
    """Surface the PAST scene a present scene resembles (the sixth sense).

    Returns ``{"ts", "outcome", "similarity", "reading"}`` for the nearest archived
    scene at/above ``floor``, else ``None``. The reading names the date and how it
    resolved, exactly as an experienced trader's memory would.
    """
    if not signature:
        return None
    best, best_sim = None, 0.0
    for e in archive or []:
        sim = visual_similarity(signature, e.get("signature"))
        if sim > best_sim:
            best, best_sim = e, sim
    if best is not None and best_sim >= floor:
        return {"ts": best.get("ts"), "outcome": best.get("outcome"),
                "label": best.get("label"), "similarity": best_sim,
                "reading": (f"questa scena l'ultima volta il {best.get('ts')} — "
                            f"si risolse come {best.get('outcome')} "
                            f"(somiglianza {best_sim:.2f})")}
    return None


def archive_scene(archive: list[dict], *, scene_id: str, pair: str, tf: str,
                  signature: dict | None, outcome: str, ts: str = "",
                  note: str = "") -> dict | None:
    """Photograph a key moment into the archive (the civilization remembers images).

    A scene without a signature is not archived (there is nothing to remember) —
    ``None``. The entry is queryable later by shape (:func:`find_scenes`).
    """
    if not signature:
        return None
    entry = {"id": str(scene_id), "pair": str(pair), "tf": str(tf),
             "signature": signature, "outcome": str(outcome), "ts": ts,
             "note": str(note)}
    archive.append(entry)
    return entry


def find_scenes(archive: list[dict], signature: dict | None, *, k: int = 3) -> list[dict]:
    """Query the photo archive BY SHAPE: the ``k`` scenes that look most like this."""
    if not signature:
        return []
    scored = []
    for e in archive or []:
        scored.append((visual_similarity(signature, e.get("signature")), e))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("id"))))
    return [{**e, "similarity": s} for s, e in scored[:k]]


# --- PART THREE — FREE VISION (the flow slots + the intuition harvest) --------

def flow_slot(*, agent: str, ts: str = "", pair: str | None = None,
              minutes: int = 20) -> dict:
    """One purposeless-seeing slot: an agent simply WATCHES (no objective, no score).

    The flow state is protected — nothing here evaluates the watcher.
    """
    return {"kind": "flow", "agent": str(agent), "pair": pair, "minutes": int(minutes),
            "ts": ts, "why": "vedere senza scopo: e' dove nasce l'intuizione",
            "reading": f"{agent} guarda{(' ' + str(pair)) if pair else ''} "
                       f"per {int(minutes)} minuti, senza obiettivo"}


def harvest_intuition(*, agent: str, text: str, ts: str = "",
                      novelty_bonus: float = 1.0) -> dict:
    """What SURFACED after a flow session — reported as "L'HO VISTO NEL FLOW".

    Voluntary (never must): the agent may report a felt shape. It enters the Market
    of Ideas with a novelty bonus; it is a SEEING, not a claim of knowledge.
    """
    return {"mode": "FLOW", "agent": str(agent), "italian": FLOW_ITALIAN,
            "text": str(text), "novelty_bonus": round(float(novelty_bonus), 6),
            "ts": ts,
            "reading": f"{FLOW_ITALIAN} ({agent}): {text}"}


def flow_budget(*, starving: bool = False, drowning: bool = False,
                base: int = 2) -> int:
    """How many flow slots the night grants (the cognitive Guardians tune it).

    A population starved of intuition OR drowning in analysis both get MORE flow:
    the antidote to overthinking is seeing.
    """
    n = int(base)
    if starving:
        n += 2
    if drowning:
        n += 1
    return max(0, n)


# --- PART FIVE — INTEGRATION (VEDO enters cognition) ------------------------

def visual_context(*, chart: str | None = None, dom: str | None = None,
                   tape: str | None = None, notes: list[str] | None = None) -> dict:
    """The VISUAL CONTEXT a proposal may carry: what the eyes saw, in words.

    Honest: absent views stay absent; the reading is built only from what was seen.
    """
    parts = []
    if chart:
        parts.append(f"grafico: {chart}")
    if dom:
        parts.append(f"DOM: {dom}")
    if tape:
        parts.append(f"tape: {tape}")
    parts.extend(str(n) for n in (notes or []))
    return {"chart": chart, "dom": dom, "tape": tape,
            "notes": list(notes or []),
            "reading": ("; ".join(parts) if parts else "(nessun contesto visivo)")}


def convergent_seeing(statements: list[dict]) -> dict:
    """CONVERGENT SEEING: the same thing SEEN by several agents (the visual analogue
    of convergent analysis).

    ``statements`` is ``[{"agent", "what"}...]``. Returns the sightings seen by two
    or more agents (a convergence), with the agents that saw each. Honest: a single
    sighting is not convergence.
    """
    groups: dict[str, list[str]] = {}
    for s in statements or []:
        what = str(s.get("what") or "").strip()
        if not what:
            continue
        groups.setdefault(what, []).append(str(s.get("agent") or "?"))
    convergent = [{"what": w, "agents": sorted(set(a)), "n": len(set(a))}
                  for w, a in groups.items() if len(set(a)) >= 2]
    convergent.sort(key=lambda c: (-c["n"], c["what"]))
    return {"convergent": convergent, "n": len(convergent),
            "reading": (f"{len(convergent)} visione/i convergente/i"
                        if convergent else "nessuna visione convergente")}


def gaze_report(state: dict) -> dict:
    """The Gaze's digest: what the civilization has SEEN, counted honestly."""
    g = (state or {}).get("gaze") or {}
    library = g.get("visual_library") or []
    archive = g.get("archive") or []
    flow = g.get("flow") or []
    harvests = g.get("intuitions") or []
    return {
        "views": len(g.get("monitors") or []),
        "library_shapes": len(library),
        "archived_scenes": len(archive),
        "flow_slots": len(flow),
        "flow_intuitions": len(harvests),
        "patrols": len(g.get("patrols") or []),
        "deja_vu": len(g.get("deja_vu") or []),
        "reading": (f"viste {len(g.get('monitors') or [])}; "
                    f"{len(library)} forme in memoria; "
                    f"{len(archive)} scene archiviate; "
                    f"{len(harvests)} intuizioni dal flow"),
    }
