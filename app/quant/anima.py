"""THE ANIMA -- market embeddings & situation search (Mega Phase 2, Section G).

Every market situation becomes a VECTOR: a point in a high-dimensional "meaning
space". The embedding stacks the last ``CONTEXT_BARS`` feature rows (each of
``features.FEATURE_NAMES``) into one fixed-length vector, so two situations that
LOOK alike also SIT CLOSE (cosine similarity high) and different ones sit far apart.

On top of the embedding sit three services:

  * SITUATION SEARCH -- match the current state against ALL historical states and
    return the K nearest neighbours with their realised forward outcomes ("this
    state last occurred 34 times; 24 times price went up");
  * CROSS-PAIR TRANSFER -- "GBPUSD now looks like EURUSD 3 hours ago": search a
    DIFFERENT pair's embedding history for analogues of the current state;
  * the DÉJÀ-VU engine's mathematical upgrade -- vector similarity instead of a
    visual chart pattern.

Honesty is binding: a situation with no finite neighbours reports ``measured=False``
and a ``None`` hit rate (never a fabricated analogue); the outcome of a neighbour is
read from the REAL tape, never invented. Pure at import (Scar #6): frames from the
caller, no wall clock.
"""

from __future__ import annotations

import numpy as np

from app.quant import features as _features

__all__ = [
    "ANIMA_VERSION",
    "CONTEXT_BARS",
    "EMBED_DIM",
    "build_embeddings",
    "outcome_labels",
    "situation_search",
    "cross_pair_transfer",
    "anima_block",
]

ANIMA_VERSION: int = 1

# How many consecutive feature rows form one embedding. 5 x 10 = 50 dimensions
# (the "~50 dimensions" the directive names).
CONTEXT_BARS: int = 5
EMBED_DIM: int = CONTEXT_BARS * len(_features.FEATURE_NAMES)


def build_embeddings(F, *, context: int = CONTEXT_BARS) -> np.ndarray:
    """The ``(n_bars, EMBED_DIM)`` embedding matrix for one pair (causal).

    Row ``i`` stacks the feature rows ``[i-context+1 .. i]`` (flat). A row with any
    missing context window is ``NaN`` (the whole situation is unmeasured).
    """
    X, _names = _features.feature_matrix(F)
    n = X.shape[0]
    dim = context * X.shape[1]
    out = np.full((n, dim), np.nan, dtype="float64")
    if n < context:
        return out
    for i in range(context - 1, n):
        window = X[i - context + 1:i + 1]
        if np.all(np.isfinite(window)):
            out[i] = window.reshape(-1)
    return out


def outcome_labels(F, *, horizon: int = 4) -> np.ndarray:
    """The realised forward outcome at each bar: ``+1`` up, ``-1`` down, ``NaN`` tail.

    Read from the REAL tape (close-to-close over ``horizon`` execution bars). An
    unresolved tail bar is ``NaN`` -- never a fabricated outcome.
    """
    close = np.asarray(F.exec["close"].to_numpy(), dtype="float64")
    n = close.shape[0]
    out = np.full(n, np.nan, dtype="float64")
    h = max(1, int(horizon))
    if n > h:
        d = close[h:] - close[:n - h]
        out[:n - h] = np.where(d > 0, 1.0, np.where(d < 0, -1.0, 0.0))
    return out


def _cosine(a: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Cosine similarity of vector ``a`` against each finite row of ``B`` (NaN rows)."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(B, axis=1)
    sims = np.full(B.shape[0], np.nan, dtype="float64")
    ok = np.isfinite(nb) & (nb > 0) & np.all(np.isfinite(B), axis=1)
    if na > 0 and ok.any():
        sims[ok] = (B[ok] @ a) / (nb[ok] * na)
    return sims


def situation_search(query: np.ndarray, embeddings: np.ndarray,
                     outcomes: np.ndarray, *, k: int = 23,
                     min_similarity: float = 0.9) -> dict:
    """Return the K nearest historical analogues of ``query`` and their outcomes.

    ``query`` is one embedding vector. Only neighbours with ``cosine >=
    min_similarity`` AND a resolved outcome are counted. Honest: with no such
    neighbour the block reports ``measured=False`` and ``None`` rates.
    """
    if query is None or embeddings is None or embeddings.shape[0] == 0:
        return {"measured": False, "n": 0, "up": None, "down": None,
                "up_rate": None, "reading": "anima: nessun vicino misurato"}
    sims = _cosine(np.asarray(query, dtype="float64"), np.asarray(embeddings))
    ok = np.isfinite(sims) & (sims >= min_similarity) & np.isfinite(outcomes)
    idx = np.where(ok)[0]
    if idx.size == 0:
        return {"measured": False, "n": 0, "up": None, "down": None,
                "up_rate": None,
                "reading": f"anima: nessun vicino con similarita' >= {min_similarity:.2f}"}
    order = idx[np.argsort(-sims[idx])][:max(1, int(k))]
    outs = outcomes[order]
    up = int(np.count_nonzero(outs > 0))
    down = int(np.count_nonzero(outs < 0))
    resolved = up + down
    up_rate = (up / resolved) if resolved else None
    return {
        "measured": True,
        "n": int(order.size),
        "up": up,
        "down": down,
        "up_rate": (round(up_rate, 4) if up_rate is not None else None),
        "top_similarity": round(float(sims[order[0]]), 5),
        "reading": (f"l'attuale situazione e' vicina a {order.size} situazioni "
                    f"storiche (similarita' >= {min_similarity:.2f}) -- risolte SU "
                    f"{up} volte, GIU' {down} volte"),
    }


def cross_pair_transfer(query: np.ndarray, other_embeddings: np.ndarray,
                        other_outcomes: np.ndarray, *, k: int = 23,
                        min_similarity: float = 0.9) -> dict:
    """Search a DIFFERENT pair's history for analogues of the current state.

    Same contract as :func:`situation_search`; the caller supplies the other pair's
    embeddings+outcomes. Honest: no analogue -> not measured.
    """
    return situation_search(query, other_embeddings, other_outcomes, k=k,
                            min_similarity=min_similarity)


def anima_block(F, *, horizon: int = 4, k: int = 23,
                min_similarity: float = 0.9,
                other_F=None) -> dict:
    """The Letter block: the current situation's analogues (own pair + cross-pair).

    ``F`` is the current pair's frames; ``other_F`` (optional) is another pair used
    for the CROSS-PAIR transfer. The query is the LAST embedding (the current state);
    the search space is every PRIOR bar (the future is never an analogue of itself).
    """
    emb = build_embeddings(F)
    outs = outcome_labels(F, horizon=horizon)
    if emb.shape[0] == 0 or not np.all(np.isfinite(emb[-1])):
        return {"version": ANIMA_VERSION, "measured": False,
                "reading": "anima: situazione attuale non misurata"}
    query = emb[-1]
    # the search space excludes the query bar itself (strictly prior bars)
    search = situation_search(query, emb[:-1], outs[:-1], k=k,
                              min_similarity=min_similarity)
    block = {"version": ANIMA_VERSION, "pair": getattr(F, "pair", None),
             "own": search, "measured": search.get("measured", False),
             "reading": search.get("reading")}
    if other_F is not None:
        other_emb = build_embeddings(other_F)
        other_outs = outcome_labels(other_F, horizon=horizon)
        block["cross_pair"] = {
            "pair": getattr(other_F, "pair", None),
            **cross_pair_transfer(query, other_emb, other_outs, k=k,
                                  min_similarity=min_similarity),
        }
    return block
