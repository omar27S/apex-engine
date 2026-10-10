"""STATISTICAL ARBITRAGE — relative value across a pair universe.

The spread between two co-moving pairs is ``log(close_A) - log(close_B)`` with
the partner aligned by the LAST CLOSED bar (``frames.align_htf``). The z-score of
that spread is SHIFTED by one bar, so a decision at ``t`` uses only information
available at the close of ``t-1`` — no same-bar lookahead.

If a partner is missing, unknown, or yields a length-mismatched z, the result is
``None`` and the caller MUST reject; the dispatcher records
``statarb_unavailable`` in the funnel (counted, never silent).
"""

from __future__ import annotations

import numpy as np

from app.quant import frames as frames_mod
from app.quant import indicators as ind

__all__ = ["spread_z", "partner_for", "statarb_z_map", "cointegration_statarb"]


def partner_for(pair: str, genome, universe) -> str | None:
    """The partner pair for ``pair``: the declared one if valid, else the first other.

    ``statarb_partner`` must name a DIFFERENT pair present in ``universe``;
    otherwise we fall back to the first other pair in the universe (stable order).
    Returns ``None`` when no partner exists.
    """
    declared = str(getattr(genome, "statarb_partner", "") or "").strip()
    others = [p for p in universe if p != pair]
    if declared and declared != pair and declared in universe:
        return declared
    return others[0] if others else None


def spread_z(close_a, ts_a, close_b, ts_b, window: int) -> np.ndarray | None:
    """Shifted z-score of the log spread, partner aligned last-closed-only.

    Returns an array the same length as ``close_a`` or ``None`` if the inputs are
    unusable (empty, mismatched, or a non-positive price). Strictly causal: the
    z at ``t`` is the spread z as of ``t-1``.
    """
    ca = np.asarray(close_a, dtype="float64")
    cb = np.asarray(close_b, dtype="float64")
    ts_a = np.asarray(ts_a, dtype="int64")
    ts_b = np.asarray(ts_b, dtype="int64")
    if ca.size == 0 or cb.size == 0 or ca.size != ts_a.size or cb.size != ts_b.size:
        return None
    if window < 2:
        return None
    aligned_b = frames_mod.align_htf(ts_a, ts_b, 0, cb)
    with np.errstate(invalid="ignore", divide="ignore"):
        spread = np.log(ca) - np.log(aligned_b)
    if not np.isfinite(spread).any():
        return None
    raw = ind.zscore(spread, int(window))
    shifted = np.full(raw.shape, np.nan)
    shifted[1:] = raw[:-1]  # decide at t on the t-1 close
    return shifted


def statarb_z_map(genome, universe_frames: dict) -> dict:
    """Per-pair shifted z arrays over a universe of :class:`frames.Frames`.

    ``universe_frames`` maps a pair name to its Frames. For each pair the partner
    is :func:`partner_for`; ``None`` entries mark unusable pairs (the caller must
    reject — never a silent pass).
    """
    universe = list(universe_frames)
    window = int(getattr(genome, "statarb_window", 100))
    out: dict = {}
    for pair, F in universe_frames.items():
        partner = partner_for(pair, genome, universe)
        if partner is None:
            out[pair] = None
            continue
        Pb = universe_frames[partner]
        z = spread_z(
            F.exec["close"].to_numpy(), F.exec["ts"].to_numpy(),
            Pb.exec["close"].to_numpy(), Pb.exec["ts"].to_numpy(),
            window,
        )
        out[pair] = z
    return out


def cointegration_statarb(genome, ctx) -> tuple[np.ndarray, np.ndarray]:
    """Long when ``z <= -statarb_z``, short when ``z >= +statarb_z``.

    Reads ``ctx.statarb_z`` (the shifted spread z, computed by the caller via
    :func:`statarb_z_map` and attached to the context). If it is absent or the
    wrong length, returns all-False — the dispatcher records
    ``statarb_unavailable`` so the mute is explicit, never silent.
    """
    z = getattr(ctx, "statarb_z", None)
    n = len(ctx.frames)
    if z is None:
        return np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    z = np.asarray(z, dtype="float64")
    if z.size != n:
        return np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    thr = float(getattr(genome, "statarb_z", 2.0))
    finite = np.isfinite(z)
    long = finite & (z <= -thr)
    short = finite & (z >= thr)
    return long, short
