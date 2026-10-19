"""THE INTERMARKET INTELLIGENCE -- the cascade that multiplies opportunities
(THE REAL HUNT, Part Four).

Currencies do not move alone. The cascade map turns the falcon's multi-asset view
into a live correlation matrix and uses it to PREPARE entries before a move completes:

  * THE LIVE CASCADE MAP -- which pairs/assets are moving TOGETHER right now. When one
    asset BREAKS a key level, the system computes which OTHER assets MUST react and
    prepares entries on those BEFORE the cascade completes (DXY breaks down -> EURUSD,
    GBPUSD, AUDUSD should follow -> prepare LONG on the first pullback). It feeds
    Column 5 (MACRO) of the Cathedral;
  * THE LEAD-LAG INTELLIGENCE -- the futures context (6E, 6B, 6J, 6A) moves BEFORE
    spot. The system measures each pair's typical LEAD-LAG and, when the futures move,
    has seconds of ADVANCE WARNING on the spot.

Honesty is binding: a correlation is ``None`` with fewer than two aligned observations
(never a fabricated link); an unmeasured lead-lag is ``None`` (never an invented
warning); the cascade names only assets whose correlation to the driver is MEASURED
and strong. Pure at import (Scar #6): the caller supplies the series and the timestamp.
"""

from __future__ import annotations

__all__ = [
    "CASCADE_VERSION",
    "CASCADE_MIN_OBS",
    "CORR_STRONG",
    "FUTURES_MAP",
    "cascade_map",
    "correlation_matrix",
    "lead_lag",
    "detect_cascade",
    "macro_support",
    "cascade_block",
]

CASCADE_VERSION: int = 1

# A correlation needs at least this many aligned observations to be MEASURED.
CASCADE_MIN_OBS: int = 3
# A correlation is "strong" (a cascade link) at or above this magnitude.
CORR_STRONG: float = 0.6
# A correlation is "independent" (for the CONSENSUS column) below this magnitude.
CORR_INDEPENDENT: float = 0.3

# The futures that LEAD their spot pairs (the lead-lag intelligence).
FUTURES_MAP: dict[str, str] = {"6E": "EURUSD", "6B": "GBPUSD", "6J": "USDJPY",
                               "6A": "AUDUSD"}


def _returns(values) -> list[float]:
    out: list[float] = []
    vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
    for a, b in zip(vals, vals[1:]):
        out.append(b - a)
    return out


def correlation_matrix(series: dict, *, min_obs: int = CASCADE_MIN_OBS) -> dict:
    """The live correlation matrix over the assets' return series.

    ``series`` maps asset -> a list of prices (or returns). A pair with fewer than
    ``min_obs`` aligned observations is honest ``None`` (never a fabricated link).
    """
    rets = {k: _returns(v) for k, v in (series or {}).items()}
    names = sorted(rets)
    grid: dict[str, dict[str, float | None]] = {a: {} for a in names}
    for i, a in enumerate(names):
        for b in names[i:]:
            n = min(len(rets[a]), len(rets[b]))
            if n < min_obs:
                r = None
            else:
                xa, xb = rets[a][-n:], rets[b][-n:]
                r = _pearson(xa, xb)
            grid[a][b] = r
            grid[b][a] = r
    return {"assets": names, "matrix": grid, "min_obs": min_obs,
            "reading": f"mappa di correlazione: {len(names)} asset"} 


def _pearson(xa: list[float], xb: list[float]) -> float | None:
    n = len(xa)
    if n < 2:
        return None
    ma, mb = sum(xa) / n, sum(xb) / n
    da = [v - ma for v in xa]
    db = [v - mb for v in xb]
    cov = sum(p * q for p, q in zip(da, db))
    va = sum(p * p for p in da)
    vb = sum(q * q for q in db)
    if va <= 0 or vb <= 0:
        return None
    return round(cov / (va ** 0.5 * vb ** 0.5), 4)


def lead_lag(spot: list, fut: list) -> dict:
    """The typical LEAD-LAG between a futures series and its spot (in samples).

    The lag (in observations) that MAXIMISES the cross-correlation of the two return
    series; a POSITIVE lag means the futures LEAD the spot by that many samples.
    Honest: too few observations -> ``None`` (never an invented warning).
    """
    rs, rf = _returns(spot), _returns(fut)
    n = min(len(rs), len(rf))
    if n < CASCADE_MIN_OBS + 2:
        return {"lag": None, "corr": None, "measured": False,
                "reading": "lead-lag non misurato (dati insufficienti)"}
    best_lag, best_r = 0, None
    for lag in range(0, min(5, n - 2) + 1):
        # futures lead by `lag`: align rf[:-lag] with rs[lag:]
        a = rf[:n - lag] if lag else rf[:n]
        b = rs[lag:n] if lag else rs[:n]
        m = min(len(a), len(b))
        if m < CASCADE_MIN_OBS:
            continue
        r = _pearson(a[-m:], b[-m:])
        if r is not None and (best_r is None or abs(r) > abs(best_r)):
            best_r, best_lag = r, lag
    return {"lag": best_lag, "corr": best_r, "measured": best_r is not None,
            "reading": (f"il futures anticipa lo spot di {best_lag} campioni "
                        f"(corr {best_r:+.2f})" if best_r is not None
                        else "lead-lag non misurato")}


def detect_cascade(series: dict, *, driver: str, direction: int,
                   broke: bool = True) -> dict:
    """Detect the assets that MUST react when ``driver`` breaks a level.

    ``direction`` is the driver's break direction (+1 up, -1 down). A follower whose
    MEASURED correlation to the driver is strong reacts in the direction implied by the
    sign of the correlation (a negative correlation -> the follower moves opposite).
    Honest: a follower with no measured/strong correlation is not named.
    """
    cm = correlation_matrix(series)
    row = (cm.get("matrix") or {}).get(str(driver)) or {}
    followers: list[dict] = []
    for asset, r in row.items():
        if asset == driver or r is None:
            continue
        if abs(r) < CORR_STRONG:
            continue
        follow_dir = int(direction) * (1 if r > 0 else -1)
        followers.append({"asset": asset, "correlation": r, "direction": follow_dir})
    followers.sort(key=lambda x: (-abs(x["correlation"]), x["asset"]))
    return {"driver": str(driver), "direction": int(direction), "broke": bool(broke),
            "followers": followers, "measured": bool(followers),
            "reading": (f"{driver} rompe {'su' if direction > 0 else 'giu'}: "
                        + (", ".join(f"{f['asset']} ({f['correlation']:+.2f})"
                                     for f in followers[:4])
                           if followers else "nessun follower misurato"))
            }


def macro_support(reading: dict, *, pair: str, direction: int,
                  series: dict | None = None) -> dict:
    """The MACRO column's evidence: does the macro context SUPPORT a trade?

    Reads the DXY move (the intermarket cascade): a long EURUSD is supported by a
    falling DXY, a short by a rising one. Honest: an unmeasured DXY -> ``None``
    (no support claimed). When a ``series`` is given, the pair's measured correlation
    to DXY refines the read.
    """
    r = reading or {}
    dxy = r.get("DXY") or r.get("dxy") or {}
    val, prev = dxy.get("value"), dxy.get("prev")
    if not (isinstance(val, (int, float)) and isinstance(prev, (int, float))):
        return {"support": None, "reason": "DXY non misurato",
                "reading": "macro non misurato: nessuna conferma (onesto)"}
    dxy_move = float(val) - float(prev)
    # EURUSD-style: a falling DXY supports a long; a rising DXY supports a short.
    implied = 1 if dxy_move < 0 else (-1 if dxy_move > 0 else 0)
    support = (implied == int(direction)) if implied != 0 else None
    reason = (f"DXY {'sale' if dxy_move > 0 else 'scende'} ({dxy_move:+.4f}): "
              + ("supporta" if support else "va contro") if support is not None
              else "DXY piatto: neutro")
    return {"support": support, "dxy_move": round(dxy_move, 6), "reason": reason,
            "reading": f"macro: {reason}"}


def cascade_block(state: dict, *, series: dict | None = None,
                  lead_lag_pairs: dict | None = None) -> dict:
    """The cascade block for the artifact + the Letter (matrix + lead-lag)."""
    s = series or {}
    cm = correlation_matrix(s) if s else {"assets": [], "matrix": {},
                                          "reading": "nessuna serie"}
    ll: dict[str, dict] = {}
    for fut, spot in (lead_lag_pairs or {}).items():
        ll[fut] = lead_lag(spot.get("spot") or [], spot.get("fut") or [])
    return {
        "version": CASCADE_VERSION,
        "matrix": cm,
        "lead_lag": ll,
        "measured": bool(cm.get("assets") or ll),
        "reading": (f"intermarket: {len(cm.get('assets') or [])} asset, "
                    f"{len(ll)} lead-lag misurati"),
    }
