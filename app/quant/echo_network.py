"""THE ECHO STATE NETWORK -- chaotic memory (Mega Phase 2, Section E).

A Reservoir Computer: a large random RECURRENT matrix (the reservoir) that is never
trained transforms the recent input into a high-dimensional state; only a linear
READOUT trains (a ridge regression -- seconds on the VM). The reservoir's state IS a
fading memory of everything it has seen, so the ESN recognises chaotic patterns that
hand-crafted indicators miss.

Three services (the directive's E1/E2/E3):

  * PREDICTION -- P(the next ``horizon`` bars close up) feeds the signal generator;
  * PATTERN RECOGNITION -- when the current state is CLOSE (cosine) to a historical
    state, the ESN "recognises" the pattern and retrieves the historical outcome
    ("this internal state last occurred 34 times; 24 times price went up");
  * SENSOR -- runs on the live tape every bar close, its predictions become
    candidates and its recognition extends the déjà-vu engine to INTERNAL states.

CAUSALITY: the reservoir is driven bar-by-bar; the readout trains on states whose
forward horizon has already resolved, so no bar is read before it closes. Honesty:
too little history -> no prediction (never fabricated); an unmeasured outcome stays
``None``. Pure at import (Scar #6).
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "ESN_VERSION",
    "RESERVOIR_SIZE",
    "SPECTRAL_RADIUS",
    "INPUT_SCALE",
    "RIDGE_LAMBDA",
    "EchoStateNetwork",
    "echo_block",
]

ESN_VERSION: int = 1

RESERVOIR_SIZE: int = 120        # the high-dimensional state size
SPECTRAL_RADIUS: float = 0.9     # < 1 for the echo-state property (fading memory)
INPUT_SCALE: float = 0.6
RIDGE_LAMBDA: float = 1e-2
WASHOUT: int = 50                # states ignored before the readout is trusted


class EchoStateNetwork:
    """A reservoir computer over the shared feature bridge (pure numpy)."""

    def __init__(self, size: int = RESERVOIR_SIZE, spectral_radius: float = SPECTRAL_RADIUS,
                 input_scale: float = INPUT_SCALE, seed: int = 0, horizon: int = 4) -> None:
        self.size = int(size)
        self.horizon = int(horizon)
        self._seed = int(seed)
        self.input_scale = float(input_scale)
        rng = np.random.default_rng(seed)
        # the feature bridge's dimension comes from the frames; built lazily on fit.
        self.W = self._random_reservoir(rng, self.size, spectral_radius)
        self.Win = None
        self.coef = None
        self.n_inputs = None

    @staticmethod
    def _random_reservoir(rng, size: int, spectral_radius: float) -> np.ndarray:
        W = rng.normal(0, 1, size=(size, size))
        # sparsity: keep ~10% of connections (cheaper, more chaotic)
        mask = rng.random((size, size)) < 0.1
        W = W * mask
        try:
            ev = np.max(np.abs(np.linalg.eigvals(W)))
            if ev > 0:
                W = W * (spectral_radius / ev)
        except np.linalg.LinAlgError:
            pass
        return W

    def _states(self, U: np.ndarray) -> np.ndarray:
        U = np.nan_to_num(np.asarray(U, dtype="float64"))
        n = U.shape[0]
        if self.Win is None or self.Win.shape[1] != U.shape[1] + 1:
            rng = np.random.default_rng(self._seed)
            self.Win = rng.normal(0, self.input_scale, size=(self.size, U.shape[1] + 1))
            self.n_inputs = U.shape[1]
        z = np.concatenate([U, np.ones((n, 1))], axis=1)
        h = np.zeros(self.size)
        states = np.zeros((n, self.size))
        for i in range(n):
            h = np.tanh(self.Win @ z[i] + self.W @ h)
            states[i] = h
        return states

    def fit(self, F) -> "EchoStateNetwork | None":
        """Train the readout on the pair's feature history (causal walk of states)."""
        from app.quant import features as feat

        X, _ = feat.feature_matrix(F)
        close = np.asarray(F.exec["close"].to_numpy(), dtype="float64")
        n = len(close)
        h = max(1, self.horizon)
        y = np.full(n, np.nan, dtype="float64")
        if n > h:
            y[:n - h] = (close[h:] > close[:n - h]).astype("float64")
        states = self._states(X)
        ok = np.isfinite(y) & (np.arange(n) >= WASHOUT)
        if ok.sum() < 30:
            self.coef = None
            return None
        H = np.concatenate([states[ok], np.ones((int(ok.sum()), 1))], axis=1)
        yy = y[ok]
        A = H.T @ H + RIDGE_LAMBDA * np.eye(H.shape[1])
        b = H.T @ yy
        try:
            self.coef = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            self.coef = None
        return self

    def predict(self, F) -> np.ndarray:
        """P(up) for every bar from the trained readout (NaN before washout)."""
        from app.quant import features as feat

        X, _ = feat.feature_matrix(F)
        n = X.shape[0]
        out = np.full(n, np.nan, dtype="float64")
        if self.coef is None:
            return out
        states = self._states(X)
        H = np.concatenate([states, np.ones((n, 1))], axis=1)
        raw = H @ self.coef
        out = 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))
        out[:WASHOUT] = np.nan
        return out

    def recognize(self, F, *, k: int = 23, min_similarity: float = 0.9) -> dict:
        """Recognise the CURRENT state among historical states; retrieve outcomes.

        Cosine similarity between the last state and every PRIOR state, restricted to
        states whose forward outcome has resolved. Honest: no close state -> not
        measured.
        """
        from app.quant import features as feat

        if self.coef is None:
            return {"measured": False, "n": 0, "up": None, "down": None,
                    "reading": "esn: readout non addestrato -- nessuna memoria"}
        X, _ = feat.feature_matrix(F)
        close = np.asarray(F.exec["close"].to_numpy(), dtype="float64")
        n = close.shape[0]
        h = max(1, self.horizon)
        y = np.full(n, np.nan, dtype="float64")
        if n > h:
            d = close[h:] - close[:n - h]
            y[:n - h] = np.where(d > 0, 1.0, np.where(d < 0, -1.0, 0.0))
        states = self._states(X)
        if n == 0:
            return {"measured": False, "n": 0, "up": None, "down": None,
                    "reading": "esn: nessuno stato"}
        q = states[-1]
        B = states[:-1]
        nq = np.linalg.norm(q)
        nb = np.linalg.norm(B, axis=1)
        ok = (nb > 0) & np.isfinite(y[:-1]) & (np.arange(n - 1) >= WASHOUT)
        if nq == 0 or not ok.any():
            return {"measured": False, "n": 0, "up": None, "down": None,
                    "reading": "esn: nessuna memoria risolta"}
        sims = np.full(n - 1, np.nan, dtype="float64")
        sims[ok] = (B[ok] @ q) / (nb[ok] * nq)
        hit = ok & (sims >= min_similarity)
        idx = np.where(hit)[0]
        if idx.size == 0:
            return {"measured": False, "n": 0, "up": None, "down": None,
                    "reading": "esn: nessuno stato interno simile"}
        order = idx[np.argsort(-sims[idx])][:max(1, int(k))]
        outs = y[order]
        up = int(np.count_nonzero(outs > 0))
        down = int(np.count_nonzero(outs < 0))
        return {"measured": True, "n": int(order.size), "up": up, "down": down,
                "up_rate": round(up / (up + down), 4) if (up + down) else None,
                "reading": (f"stato interno riconosciuto: {order.size} stati simili "
                            f"nel passato -- SU {up}, GIU' {down}")}


def echo_block(F, *, horizon: int = 4, k: int = 23, min_similarity: float = 0.9,
               seed: int = 0) -> dict:
    """The Letter block: the ESN's live prediction + pattern recognition (honest)."""
    esn = EchoStateNetwork(seed=seed, horizon=horizon)
    if esn.fit(F) is None:
        return {"version": ESN_VERSION, "measured": False,
                "reading": "esn: storia insufficiente -- nessuna predizione"}
    probs = esn.predict(F)
    last = probs[-1] if probs.size else np.nan
    rec = esn.recognize(F, k=k, min_similarity=min_similarity)
    conf = 0.6
    direction = None
    if np.isfinite(last):
        if last >= conf:
            direction = 1
        elif last <= 1 - conf:
            direction = -1
    return {
        "version": ESN_VERSION,
        "prediction_up": (round(float(last), 4) if np.isfinite(last) else None),
        "direction": direction,
        "recognition": rec,
        "measured": bool(np.isfinite(last) or rec.get("measured")),
        "reading": (f"esn: P(rialzo) {last:.2f}" if np.isfinite(last)
                    else "esn: non misurato"),
    }
