"""R140 -- THE DOLLAR EYE (l'occhio del dollaro).

The causal engine has testified for nights that the dollar is this
civilization's dominant executioner: 43 of 45 analyzed losses died of
``macro_push`` (2026-10-22) -- the DXY pushing the market against the
position. Yet every gene in the genome was born blind to it: ema windows,
rsi gates, atr multiples -- all of them watch only the pair's own tape.

The Dollar Eye is the genome's first sense organ that looks OUTSIDE the
pair. Two genes carry it (``usd_eye_mode``: blind 0 / watching 1, and
``usd_eye_strength``: how many sigmas of opposing USD-basket momentum an
entry may not fight). From the universe the evaluator already carries,
the eye builds a USD-strength index -- the mean, sign-corrected,
self-normalized momentum of the universe's USD pairs on the execution
timeline -- and refuses entry signals that fight a move beyond the
genome's threshold.

Honest by construction:

* BLIND BY DEFAULT -- ``usd_eye_mode=0`` for every existing genome; no
  living blood changes behavior the night the eye lands. The eye must be
  GROWN by mutation or drawn in newborns, then PROVEN by selection.
* the eye can only REFUSE entries (the spread gate's idiom), never
  invent one: trade frequency can only fall, never rise;
* strictly causal -- the strength at an execution bar uses only USD bars
  closed at or before that bar (the house's closed-bar law);
* a stale USD tape (no closed bar for over two hours) is a BLIND bar,
  never a fabricated one;
* crosses carry no USD leg: the eye does not see them (said aloud);
* fewer than two visible USD pairs in the universe -> no eye at all
  (None, spoken by absence).

Build Mode: pure functions, numpy only, no I/O at import.
"""

from __future__ import annotations

import numpy as np

__all__ = ["usd_leg", "eye_open", "build_usd_index", "entry_masks",
           "USD_STALE_SECONDS", "USD_LOOKBACK", "USD_NORM_WINDOW"]

# The eye's constants are LAWS, not knobs: one momentum window, one
# normalization window, one staleness horizon -- fixed and declared.
USD_LOOKBACK = 6        # execution bars (H1): the macro push window (~6h)
USD_NORM_WINDOW = 100   # execution bars: the self-normalization window
USD_STALE_SECONDS = 2 * 60 * 60  # a USD bar older than 2h is stale -> blind


def usd_leg(pair: str) -> int:
    """The pair's dollar side: +1 USD base (USDJPY), -1 USD quote (EURUSD),
    0 a cross (EURGBP) -- the eye is blind for crosses by law."""
    p = str(pair).upper()
    if len(p) == 6 and p[:3] == "USD" and p[3:] != "USD":
        return 1
    if len(p) == 6 and p[3:] == "USD" and p[:3] != "USD":
        return -1
    return 0


def eye_open(genome) -> bool:
    """True only when the genome grew a watching eye (mode=1)."""
    return int(getattr(genome, "usd_eye_mode", 0)) == 1


def _z_series(close: np.ndarray) -> np.ndarray:
    """Sign-free, self-normalized momentum on one pair's closes.

    ``out[i]`` is the z-score of the ``USD_LOOKBACK``-bar return ending at
    bar ``i + USD_LOOKBACK`` (strictly causal: the return at bar T uses
    bars T-LOOKBACK..T, all closed at or before T). A NaN where the
    normalization window is not yet full.
    """
    n = len(close)
    need = USD_LOOKBACK + USD_NORM_WINDOW + 1
    if n < need:
        return np.array([], dtype="float64")
    mom = (close[USD_LOOKBACK:] - close[:-USD_LOOKBACK]) / close[:-USD_LOOKBACK]
    cs = np.cumsum(mom)
    cs2 = np.cumsum(mom * mom)
    pad = np.concatenate(([0.0], cs))
    pad2 = np.concatenate(([0.0], cs2))
    idx = np.arange(len(mom))
    lo = np.maximum(idx - USD_NORM_WINDOW + 1, 0)
    cnt = (idx - lo + 1).astype("float64")
    s = pad[idx + 1] - pad[lo]
    s2 = pad2[idx + 1] - pad2[lo]
    var = np.where(cnt >= USD_NORM_WINDOW, s2 / cnt - (s / cnt) ** 2, np.nan)
    std = np.sqrt(np.maximum(var, 0.0))
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(std > 0, mom / std, np.nan)
    return z


def build_usd_index(universe_frames) -> tuple[np.ndarray, np.ndarray] | None:
    """The USD-strength index on the union execution timeline.

    For every USD pair of the universe: the z-scored LOOKBACK return of its
    closes on its own execution bars, sign-corrected so that positive always
    means THE DOLLAR RISING. The index at a union timestamp is the mean of
    every pair's freshest value at or before it (stale bars contribute
    nothing). Returns ``None`` when fewer than two USD pairs are visible --
    one tape is an anecdote, not an index.
    """
    series: list[tuple[np.ndarray, np.ndarray]] = []
    for pair in sorted(universe_frames):
        F = universe_frames[pair]
        leg = usd_leg(F.pair if getattr(F, "pair", None) else pair)
        if leg == 0:
            continue
        try:
            ts = np.asarray(F.exec["ts"].values, dtype="int64")
            close = np.asarray(F.exec["close"].values, dtype="float64")
        except Exception:
            continue  # a frame the eye cannot read is a blind frame, spoken by absence
        if len(ts) < USD_LOOKBACK + USD_NORM_WINDOW + 1:
            continue
        z = _z_series(close) * leg  # sign-correct: + = dollar rising
        ts_z = ts[USD_LOOKBACK:]
        ok = np.isfinite(z)
        if ok.any():
            series.append((ts_z[ok], z[ok]))
    if len(series) < 2:
        return None
    all_ts = np.unique(np.concatenate([s[0] for s in series]))
    stack = np.full((len(series), len(all_ts)), np.nan)
    for r, (ts_u, z_u) in enumerate(series):
        pos = np.searchsorted(ts_u, all_ts, side="right") - 1
        has = pos >= 0
        jp = np.maximum(pos, 0)
        fresh = has & ((all_ts - ts_u[jp]) <= USD_STALE_SECONDS)
        with np.errstate(invalid="ignore"):
            stack[r, fresh] = z_u[jp[fresh]]
    with np.errstate(invalid="ignore"):
        strength = np.nanmean(stack, axis=0)
    return all_ts, strength


def entry_masks(F, index, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """(ok_long, ok_short) per execution bar of ``F``.

    An entry that FIGHTS a dollar move beyond ``threshold`` sigmas is
    refused: for a USD-quote pair (long = short USD) longs are refused
    while the dollar rises beyond the threshold and shorts while it falls;
    for a USD-base pair the mirror. Blind bars (no fresh USD data) allow
    everything -- the eye never fabricates a verdict it cannot see.
    """
    all_ts, strength = index
    ts = np.asarray(F.exec["ts"].values, dtype="int64")
    leg = usd_leg(F.pair)
    pos = np.searchsorted(all_ts, ts, side="right") - 1
    has = pos >= 0
    jp = np.maximum(pos, 0)
    fresh = has & ((ts - all_ts[jp]) <= USD_STALE_SECONDS)
    with np.errstate(invalid="ignore"):
        s = np.where(fresh, strength[jp], np.nan)
    rising = np.isfinite(s) & (s > threshold)
    falling = np.isfinite(s) & (s < -threshold)
    if leg == -1:      # XXXUSD: long = short USD
        ok_long = ~rising
        ok_short = ~falling
    else:              # USDXXX: long = long USD
        ok_long = ~falling
        ok_short = ~rising
    return ok_long, ok_short
