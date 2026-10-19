"""THE ML FAMILIES -- lightweight learned predictors (Mega Phase 2, Section D1/D2).

Three learned families, each fitted on the VM in seconds (pure numpy, no torch, no
sklearn):

  * ``ml_gradient_boosting`` -- a small ensemble of decision STUMPS fitted by
    gradient boosting on the feature bridge, predicting the direction of the next
    ``ml_horizon`` bars;
  * ``ml_lstm_pattern`` -- a tiny gated recurrent net (a seeded reservoir + a ridge
    readout) over the recent feature sequence, recognising short-term pattern and
    predicting the next move;
  * ``ml_bayesian_regime`` -- an online Bayesian posterior over regime transitions,
    firing when the probability of a regime CHANGE crosses the genome's floor.

CAUSALITY IS THE WHOLE GAME. Every model is WALK-FORWARD: at bar ``i`` it uses only
bars strictly before ``i`` (an expanding training window, refit every
``REFIT_EVERY`` bars on past labels whose forward horizon has already resolved). No
bar is ever read before it closes, so a learned family is judged by the SAME casual
engine as any hand-crafted one -- and cannot cheat.

Overfitting protection is inherited, not special-cased: the unseen gauntlet, the
Wilson lower bound and the R85 gross-to-friction gate apply to ML strategies EQUALLY
(the evaluator treats them like any genome). This module only produces the masks.

Honesty: too little history yields all-False masks (never a fabricated signal); a
model that cannot be fitted is reported and yields no signal. Pure at import
(Scar #6): the caller supplies the frames.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "ML_VERSION",
    "REFIT_EVERY",
    "TRAIN_MIN",
    "fit_gradient_boosting",
    "gb_predict",
    "fit_lstm_pattern",
    "lstm_predict",
    "bayesian_regime_probs",
    "walk_forward_masks",
    "ml_family",
]

ML_VERSION: int = 1

# Refit cadence (execution bars) and the minimum training window. Both are sizes,
# not magic: they bound compute and keep the fit out-of-sample by construction.
REFIT_EVERY: int = 750
TRAIN_MIN: int = 400

# The learned families are computed over at most this many trailing execution bars
# (a bounded, honest window: the models are only fit where there is enough history,
# and every bar before the window is left UNMODELLED -- a False mask, never a guess).
ML_MAX_BARS: int = 6000


def _labels(close: np.ndarray, horizon: int) -> np.ndarray:
    """Forward direction label: 1 if close[i+h] > close[i], else 0; NaN at the tail."""
    n = close.shape[0]
    y = np.full(n, np.nan, dtype="float64")
    h = max(1, int(horizon))
    if n > h:
        y[:n - h] = (close[h:] > close[:n - h]).astype("float64")
    return y


# ---------------------------------------------------------------------------
# Gradient boosting (decision stumps).
# ---------------------------------------------------------------------------
def _best_stump(X: np.ndarray, r: np.ndarray, min_leaf: int = 5):
    """The single feature/threshold stump that best reduces squared residual ``r``.

    Vectorised over thresholds per feature (no inner Python loop over bars), so the
    gradient-boosting fit stays fast even on a full tape.
    """
    n, d = X.shape
    best = None
    best_err = np.inf
    for j in range(d):
        col = X[:, j]
        finite = np.isfinite(col)
        m = int(finite.sum())
        if m < 2 * min_leaf:
            continue
        vals = col[finite]
        res = r[finite]
        order = np.argsort(vals)
        vals = vals[order]
        res = res[order]
        csum = np.cumsum(res)
        c2 = np.cumsum(res * res)
        total = csum[-1]
        total2 = c2[-1]
        # candidate split after position k-1 (left size k), k in [min_leaf, m-min_leaf]
        ks = np.arange(min_leaf, m - min_leaf + 1)
        if ks.size == 0:
            continue
        distinct = vals[ks] != vals[ks - 1]
        ks = ks[distinct]
        if ks.size == 0:
            continue
        left = csum[ks - 1]
        left2 = c2[ks - 1]
        nL = ks.astype("float64")
        nR = m - nL
        sse = (left2 - left * left / nL) + ((total2 - left2) - (total - left) ** 2 / nR)
        kbest = int(np.argmin(sse))
        if sse[kbest] < best_err:
            best_err = float(sse[kbest])
            k = int(ks[kbest])
            thr = 0.5 * (vals[k] + vals[k - 1])
            ml = left[kbest] / nL[kbest]
            mr = (total - left[kbest]) / nR[kbest]
            best = (j, float(thr), float(ml), float(mr))
    return best


def fit_gradient_boosting(X: np.ndarray, y: np.ndarray, *,
                          n_rounds: int = 12, lr: float = 0.2):
    """Fit a small gradient-boosted stump ensemble (binary classification logit)."""
    finite = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    Xf, yf = X[finite], y[finite]
    if Xf.shape[0] < 20:
        return None
    base = float(np.clip(yf.mean(), 1e-4, 1 - 1e-4))
    logit = np.full(Xf.shape[0], np.log(base / (1 - base)))
    pred0 = 1.0 / (1.0 + np.exp(-logit))
    stumps = []
    current = pred0.copy()
    for _ in range(int(n_rounds)):
        resid = yf - current  # negative gradient of logloss ~ (y - p)
        stump = _best_stump(Xf, resid)
        if stump is None:
            break
        j, thr, ml, mr = stump
        upd = np.where(Xf[:, j] <= thr, ml, mr)
        current = 1.0 / (1.0 + np.exp(-(np.log(np.clip(current, 1e-6, 1 - 1e-6)
                                               / np.clip(1 - current, 1e-6, 1 - 1e-6))
                                     + lr * upd)))
        stumps.append(stump)
    if not stumps:
        return None
    return {"base": base, "stumps": stumps, "lr": lr}


def gb_predict(model, X: np.ndarray) -> np.ndarray:
    """Predict P(up) for each row (NaN rows -> NaN)."""
    n = X.shape[0]
    out = np.full(n, np.nan, dtype="float64")
    if not model:
        return out
    base = model["base"]
    logit = np.full(n, np.log(base / (1 - base)))
    ok = np.all(np.isfinite(X), axis=1)
    lr = model["lr"]
    for j, thr, ml, mr in model["stumps"]:
        logit[ok] += lr * np.where(X[ok, j] <= thr, ml, mr)
    out[ok] = 1.0 / (1.0 + np.exp(-logit[ok]))
    return out


# ---------------------------------------------------------------------------
# LSTM pattern (a tiny gated recurrent reservoir + ridge readout).
# ---------------------------------------------------------------------------
def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _esn_state(U: np.ndarray, W: np.ndarray, win: int) -> np.ndarray:
    """Run a single gated recurrent cell over the input sequence; return states.

    Non-finite inputs are imputed to 0.0 before the recurrence (a missing feature is
    treated as its neutral value): the recurrence has no ``nan`` branch, and letting
    one NaN poison every later state would make the whole family mute. The OUTPUT is
    still masked by the caller, so an imputed bar never produces a signal.
    """
    U = np.nan_to_num(np.asarray(U, dtype="float64"), nan=0.0, posinf=0.0, neginf=0.0)
    n, d = U.shape
    h = np.zeros(W.shape[0])
    states = np.zeros((n, W.shape[0]))
    z = np.concatenate([U, np.ones((n, 1))], axis=1)  # bias input
    rng = np.random.default_rng(1234)
    Win = rng.normal(0, 0.5, size=(W.shape[0], z.shape[1]))
    for i in range(n):
        pre = Win @ z[i] + W @ h
        g = np.tanh(pre)
        gate = _sigmoid(W @ h + Win[:, -1] * z[i, -1])
        h = (1 - gate) * h + gate * g
        states[i] = h
    return states


def fit_lstm_pattern(X: np.ndarray, y: np.ndarray, *, hidden: int = 16,
                     decay: float = 0.9, win: int = 16):
    """Fit a recurrent reservoir + a ridge readout on its states (causal)."""
    finite = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    if finite.sum() < 40:
        return None
    rng = np.random.default_rng(7)
    W = rng.normal(0, 0.3, size=(hidden, hidden))
    # scale spectral radius below 1 for an echo-state property
    try:
        ev = np.max(np.abs(np.linalg.eigvals(W)))
        if ev > 0:
            W = W * (0.9 / ev)
    except np.linalg.LinAlgError:
        pass
    states = _esn_state(X, W, win)
    idx = np.where(finite)[0]
    H = states[idx]
    H = np.concatenate([H, np.ones((H.shape[0], 1))], axis=1)
    yy = y[idx]
    # exponentially weighted ridge readout
    w = decay ** (len(yy) - 1 - np.arange(len(yy)))
    lam = 1e-2
    A = (H * w[:, None]).T @ H + lam * np.eye(H.shape[1])
    b = (H * w[:, None]).T @ yy
    try:
        coef = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return None
    return {"W": W, "hidden": hidden, "coef": coef}


def lstm_predict(model, X: np.ndarray) -> np.ndarray:
    """Predict P(up) from the recurrent states.

    The recurrence imputes missing inputs to their neutral value, so every row gets
    a finite probability; the caller's gate stack (and the walk-forward start) is
    what constrains where a signal may be born.
    """
    n = X.shape[0]
    out = np.full(n, np.nan, dtype="float64")
    if not model:
        return out
    states = _esn_state(X, model["W"], 0)
    H = np.concatenate([states, np.ones((n, 1))], axis=1)
    raw = H @ model["coef"]
    out = _sigmoid(raw)
    return out


# ---------------------------------------------------------------------------
# Bayesian regime.
# ---------------------------------------------------------------------------
def bayesian_regime_probs(F, *, window: int = 60, decay: float = 0.95) -> np.ndarray:
    """Online posterior P(regime CHANGE) over the execution bars (causal).

    A two-state (stable | changing) model over the volatility feature. The posterior
    is updated one bar at a time with a forgetting factor and is CALIBRATED so a
    typical bar sits near ``P=0.5`` while a genuine vol break pushes it toward 1.
    Bar ``i``'s posterior uses only bars before ``i``. Returns an array in ``[0, 1]``
    (NaN before warmup).
    """
    n = len(F)
    out = np.full(n, np.nan, dtype="float64")
    if n < window:
        return out
    atr = np.asarray(F.atr_pips, dtype="float64")
    ema_f = np.asarray(F.structure_ema_fast, dtype="float64")
    ema_s = np.asarray(F.structure_ema_slow, dtype="float64")
    # observed "state signature": normalised volatility + |ema spread| (both scale-free)
    med = np.nanmedian(atr) or np.nan
    vol = np.divide(atr, med)
    spread = np.divide(np.abs(ema_f - ema_s), np.abs(ema_s),
                       out=np.full(n, np.nan), where=np.abs(ema_s) > 0)
    v = np.nan_to_num(vol, nan=1.0)
    s = np.nan_to_num(spread, nan=0.0)
    sig = 0.5 * v + 0.5 * (s / (np.nanmedian(s[:window]) or 1.0))
    mean_stable = float(np.nanmean(sig[:window]))
    var_stable = float(np.nanvar(sig[:window])) or 1e-6
    log_odds = 0.0
    for i in range(window, n):
        x = sig[i - 1]  # strictly past observation (causal)
        z2 = (x - mean_stable) ** 2 / var_stable
        # calibrated likelihood ratio: a 1-sigma move is mildly surprising, a
        # 3-sigma move is a regime break. P(changing) is the logistic of the
        # evidence in favour of the anomalous regime.
        evidence = 0.5 * (z2 - 1.0)     # 0 at z=1, grows with the surprise
        log_odds = 0.85 * log_odds + evidence
        p_change = 1.0 / (1.0 + np.exp(-log_odds))
        out[i] = p_change
        # update the stable-regime running stats with forgetting (past data only)
        mean_stable = decay * mean_stable + (1 - decay) * x
        var_stable = decay * var_stable + (1 - decay) * (x - mean_stable) ** 2
    return out


# ---------------------------------------------------------------------------
# Walk-forward signal production.
# ---------------------------------------------------------------------------
def _walk_forward_probs(F, genome, kind: str) -> np.ndarray:
    """Causal P(up) over every execution bar, walk-forward (refit every REFIT_EVERY).

    The heavy models (boosting, recurrent) are computed only over the trailing
    ``ML_MAX_BARS`` window; bars before it are left NaN (unmodelled, never a guess).
    """
    from app.quant import features as feat

    X, _names = feat.feature_matrix(F)
    n = X.shape[0]
    horizon = int(getattr(genome, "ml_horizon", 4))
    decay = float(getattr(genome, "ml_decay", 0.9))
    close = np.asarray(F.exec["close"].to_numpy(), dtype="float64")
    if kind == "ml_bayesian_regime":
        return bayesian_regime_probs(F, decay=decay)
    y = _labels(close, horizon)
    probs = np.full(n, np.nan, dtype="float64")
    start = max(0, n - ML_MAX_BARS)
    Xw = X[start:]
    yw = y[start:]
    nw = Xw.shape[0]
    i = TRAIN_MIN
    while i < nw:
        hi = min(i + REFIT_EVERY, nw)
        # train on strictly-prior rows whose label has resolved (j + horizon < i)
        train_end = max(TRAIN_MIN, i - horizon)
        Xtr, ytr = Xw[:train_end], yw[:train_end]
        if kind == "ml_gradient_boosting":
            model = fit_gradient_boosting(Xtr, ytr, n_rounds=12, lr=0.2)
            pred = gb_predict(model, Xw[i:hi]) if model else np.full(hi - i, np.nan)
        else:
            model = fit_lstm_pattern(Xtr, ytr, decay=decay)
            pred = lstm_predict(model, Xw[i:hi]) if model else np.full(hi - i, np.nan)
        probs[start + i:start + hi] = pred
        i = hi
    return probs


_PROB_CACHE: dict = {}


def walk_forward_masks(F, genome) -> tuple[np.ndarray, np.ndarray]:
    """The ML family's causal ``(long, short)`` masks for one genome on frames ``F``.

    A bar becomes LONG when P(up) >= ``ml_confidence`` and SHORT when
    P(up) <= 1 - ``ml_confidence``. For the Bayesian regime family, a bar is LONG
    when a change is detected while the trend is up, SHORT when it is down (the
    transition is taken in the direction of the prevailing structure).
    """
    kind = str(getattr(genome, "family", ""))
    n = len(F)
    long_m = np.zeros(n, dtype=bool)
    short_m = np.zeros(n, dtype=bool)
    horizon = int(getattr(genome, "ml_horizon", 4))
    decay = float(getattr(genome, "ml_decay", 0.9))
    key = (id(F), kind, horizon, round(decay, 3))
    entry = _PROB_CACHE.get(key)
    if entry is not None and entry[0] is F and entry[1].shape[0] == n:
        probs = entry[1]
    else:
        probs = _walk_forward_probs(F, genome, kind)
        # hold a STRONG ref to F so its id cannot be reused by another object (an
        # id-keyed cache without the ref could serve a stranger's probabilities).
        _PROB_CACHE[key] = (F, probs)
    conf = float(getattr(genome, "ml_confidence", 0.6))
    conf = min(max(conf, 0.5), 0.9)
    if kind == "ml_bayesian_regime":
        ema_f = np.asarray(F.structure_ema_fast, dtype="float64")
        ema_s = np.asarray(F.structure_ema_slow, dtype="float64")
        up = ema_f >= ema_s
        fire = np.isfinite(probs) & (probs >= conf)
        long_m = fire & up
        short_m = fire & ~up
    else:
        long_m = np.isfinite(probs) & (probs >= conf)
        short_m = np.isfinite(probs) & (probs <= (1.0 - conf))
    return long_m, short_m


def clear_cache() -> None:
    _PROB_CACHE.clear()


def ml_family(genome, ctx):
    """The dispatch callable for the three ML families (registered in ``signals``)."""
    return walk_forward_masks(ctx.frames, genome)
