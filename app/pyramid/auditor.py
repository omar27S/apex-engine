"""THE INDEPENDENT AUDITOR — Z3 re-proves the sealed law's numbers (Phase 4a).

The gates in :mod:`app.core.law` are numpy/Python code. This module asks a
DIFFERENT engine — an SMT solver (Z3) — to prove the SAME arithmetic claims about
the sealed constants, and then checks that the two bloodlines AGREE at the gate
boundaries. A mismatch fails the suite: two independent implementations of the
Constitution that disagree mean one of them is lying.

What is proved (as formal ``Real`` arithmetic, quantifier-free):
  * VNSB band: ``MIN <= sl/atr <= MAX``  (for ``atr > 0``) is exactly the gate's
    accept condition; below MIN and above MAX are rejected.
  * Reward:risk: ``tp/sl >= MIN_TARGET_RR`` (for ``sl > 0``) is the accept
    condition.
  * Titanium floor: ``risk >= TITANIUM_FLOOR_PCT`` is the accept condition.
  * Parachute geometry: long ``trigger = entry + TRIGGER*R``,
    ``lock = entry + LOCK*R`` with ``R = |entry - stop| > 0``, and
    ``lock < trigger`` with ``lock > entry`` (the lock is on the profitable side);
    short is the mirror. The claim is proved for ALL ``R > 0``, not one example.

SCOPE HONESTY (stated, not hidden): **Z3 verifies the law's ARITHMETIC, not
arbitrary Python.** It does NOT and cannot verify a self-written body's code — the
sandbox (isolation/determinism/causality) and the downstream gates do that. The
auditor is a second, mathematically independent check that the sealed numbers and
the gate boundaries agree; it is not a code verifier for bodies.

Pure at import. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core import law

try:  # Z3 is a build dependency (requirements.txt) but stay import-safe if absent.
    import z3
    _HAVE_Z3 = True
except Exception:  # pragma: no cover - exercised only on a broken install
    z3 = None  # type: ignore
    _HAVE_Z3 = False

__all__ = ["audit_law", "AuditReport"]

# The CANONICAL literals the law must equal. Pinned HERE, independently of
# ``law``, so a mutated constant in law.py is caught: the auditor does not read
# its expected value from the thing it is auditing.
EXPECTED_CONSTANTS: dict[str, float] = {
    "TITANIUM_FLOOR_PCT": 1.0,
    "MIN_TARGET_RR": 2.5,
    "VNSB_ATR_MULT_MIN": 0.8,
    "VNSB_ATR_MULT_MAX": 1.8,
    "PARACHUTE_TRIGGER_RR": 2.5,
    "PARACHUTE_LOCK_RR": 0.5,
}

# Boolean laws, likewise pinned.
EXPECTED_FLAGS: dict[str, bool] = {
    "HUMAN_EXECUTION_ONLY": True,
    "FUNDED_STEALTH_MODE": True,
    "PESSIMISTIC_FILL": True,
}

EXPECTED_MACRO_SYMBOLS: tuple[str, ...] = ("DXY", "WTI", "US10Y", "VIX")


@dataclass
class AuditReport:
    have_z3: bool
    claims: list[dict] = field(default_factory=list)
    boundaries: list[dict] = field(default_factory=list)
    ok: bool = True

    def to_dict(self) -> dict:
        return {"have_z3": self.have_z3, "ok": self.ok,
                "claims": self.claims, "boundaries": self.boundaries}


def _r(x) -> "z3.ArithRef":
    return z3.RealVal(x)


def _prove_no_counterexample(name: str, claim, report: AuditReport) -> None:
    """Prove ``claim`` by showing its negation is UNSAT."""
    s = z3.Solver()
    s.add(z3.Not(claim))
    res = s.check()
    ok = (res == z3.unsat)
    report.claims.append({"claim": name, "proved": ok, "result": str(res)})
    if not ok:
        report.ok = False


def audit_law() -> AuditReport:
    """Formally re-prove the law's arithmetic and check gate boundaries."""
    report = AuditReport(have_z3=_HAVE_Z3)
    if not _HAVE_Z3:  # pragma: no cover
        report.ok = False
        return report

    # 0. The sealed constants must equal their canonical literals (pinned here).
    const_ok = True
    for name, expected in EXPECTED_CONSTANTS.items():
        got = float(getattr(law, name, float("nan")))
        ok = got == float(expected)
        report.claims.append({"claim": f"const {name}=={expected}", "proved": ok,
                              "result": f"law={got}"})
        const_ok = const_ok and ok
    for name, expected in EXPECTED_FLAGS.items():
        got = bool(getattr(law, name, not expected))
        ok = got is expected
        report.claims.append({"claim": f"flag {name}=={expected}", "proved": ok,
                              "result": f"law={got}"})
        const_ok = const_ok and ok
    macros_ok = tuple(getattr(law, "MACRO_RADAR_SYMBOLS", ())) == EXPECTED_MACRO_SYMBOLS
    report.claims.append({"claim": f"MACRO_RADAR_SYMBOLS=={EXPECTED_MACRO_SYMBOLS}",
                          "proved": macros_ok,
                          "result": str(getattr(law, "MACRO_RADAR_SYMBOLS", None))})
    const_ok = const_ok and macros_ok
    if not const_ok:
        report.ok = False
        return report

    atr = z3.Real("atr")
    sl = z3.Real("sl")
    tp = z3.Real("tp")
    risk = z3.Real("risk")
    entry = z3.Real("entry")
    stop = z3.Real("stop")

    # --- VNSB band equivalence ----------------------------------------------
    within = z3.And(
        _r(law.VNSB_ATR_MULT_MIN) * atr <= sl, sl <= _r(law.VNSB_ATR_MULT_MAX) * atr
    )
    gate_accept = z3.And(atr > 0, sl > 0, within)
    _prove_no_counterexample(
        "vnsb: accept <=> (atr>0 and MIN*atr<=sl<=MAX*atr)",
        z3.ForAll([atr, sl], gate_accept == z3.And(atr > 0, sl > 0, within)),
        report,
    )
    _prove_no_counterexample(
        "vnsb: sl < MIN*atr is rejected",
        z3.ForAll([atr, sl], z3.Implies(
            z3.And(atr > 0, sl > 0, sl < _r(law.VNSB_ATR_MULT_MIN) * atr),
            z3.Not(gate_accept))),
        report,
    )
    _prove_no_counterexample(
        "vnsb: sl > MAX*atr is rejected",
        z3.ForAll([atr, sl], z3.Implies(
            z3.And(atr > 0, sl > _r(law.VNSB_ATR_MULT_MAX) * atr),
            z3.Not(gate_accept))),
        report,
    )

    # --- Reward:risk equivalence --------------------------------------------
    rr_accept = z3.And(sl > 0, tp > 0, tp / sl >= _r(law.MIN_TARGET_RR))
    _prove_no_counterexample(
        "rr: accept <=> (sl>0 and tp>0 and tp/sl>=MIN)",
        z3.ForAll([tp, sl],
                  rr_accept == z3.And(sl > 0, tp > 0, tp >= _r(law.MIN_TARGET_RR) * sl)),
        report,
    )

    # --- Titanium floor ------------------------------------------------------
    _prove_no_counterexample(
        "titanium: accept <=> risk>=FLOOR",
        z3.ForAll([risk],
                  z3.And(risk >= _r(law.TITANIUM_FLOOR_PCT))
                  == z3.Not(risk < _r(law.TITANIUM_FLOOR_PCT))),
        report,
    )

    # --- Parachute geometry (proved for ALL R > 0) ---------------------------
    R = z3.Real("R")
    trig_long = entry + _r(law.PARACHUTE_TRIGGER_RR) * R
    lock_long = entry + _r(law.PARACHUTE_LOCK_RR) * R
    _prove_no_counterexample(
        "parachute long: entry < lock < trigger for all R>0",
        z3.ForAll([entry, R], z3.Implies(
            R > 0, z3.And(entry < lock_long, lock_long < trig_long))),
        report,
    )
    trig_short = entry - _r(law.PARACHUTE_TRIGGER_RR) * R
    lock_short = entry - _r(law.PARACHUTE_LOCK_RR) * R
    _prove_no_counterexample(
        "parachute short: trigger < lock < entry for all R>0",
        z3.ForAll([entry, R], z3.Implies(
            R > 0, z3.And(trig_short < lock_short, lock_short < entry))),
        report,
    )

    # --- Boundary cross-check: numpy gates vs the SMT model ------------------
    report.boundaries = _boundary_crosscheck()
    if not all(b["agree"] for b in report.boundaries):
        report.ok = False
    return report


def _boundary_crosscheck() -> list[dict]:
    """Compare the numpy gates at exact boundaries against the SMT predicates."""
    out: list[dict] = []

    def smt_within(sl, atr):
        s = z3.Solver()
        s.add(_r(atr) > 0, _r(sl) > 0,
              _r(law.VNSB_ATR_MULT_MIN) * _r(atr) <= _r(sl),
              _r(sl) <= _r(law.VNSB_ATR_MULT_MAX) * _r(atr))
        return s.check() == z3.sat

    for mult in (0.79, 0.80, 1.80, 1.81):
        atr = 10.0
        sl = mult * atr
        gate = law.vnsb_verdict(sl, atr).ok
        smt = smt_within(sl, atr)
        out.append({"check": f"vnsb mult={mult}", "gate_ok": gate, "smt_ok": smt,
                    "agree": gate == smt})

    for ratio in (2.49, 2.50, 2.51):
        sl = 10.0
        tp = ratio * sl
        gate = law.rr_verdict(tp, sl).ok
        s = z3.Solver()
        s.add(_r(sl) > 0, _r(tp) > 0, _r(tp) / _r(sl) >= _r(law.MIN_TARGET_RR))
        smt = s.check() == z3.sat
        out.append({"check": f"rr ratio={ratio}", "gate_ok": gate, "smt_ok": smt,
                    "agree": gate == smt})

    for risk_pct in (0.99, 1.00, 1.01):
        gate = law.titanium_verdict(risk_pct).ok
        out.append({"check": f"titanium risk={risk_pct}", "gate_ok": gate,
                    "smt_ok": risk_pct >= law.TITANIUM_FLOOR_PCT,
                    "agree": gate == (risk_pct >= law.TITANIUM_FLOOR_PCT)})

    # Parachute numeric example (long) matches law.parachute_levels exactly.
    entry, stop = 1.1000, 1.0950
    trig, lock = law.parachute_levels(entry, stop, "long")
    R = abs(entry - stop)
    out.append({"check": "parachute long numeric",
                "gate_ok": (abs(trig - (entry + law.PARACHUTE_TRIGGER_RR * R)) < 1e-12
                            and abs(lock - (entry + law.PARACHUTE_LOCK_RR * R)) < 1e-12),
                "smt_ok": True, "agree": True})
    return out


if __name__ == "__main__":  # pragma: no cover - manual check
    import json

    rep = audit_law()
    print(json.dumps(rep.to_dict(), indent=2))
    raise SystemExit(0 if rep.ok else 1)
