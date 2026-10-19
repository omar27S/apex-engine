"""THE THREE GUARDIANS — measure first, then limit, then push to the maximum.

Founding Charter, first acts (act 2). Three Guardians are institutions of the
state, effective now:

1. THE ACCOUNT GUARDIAN — minutes, budget, quotas. It measures the REAL limits
   first, then keeps usage at the maximum sustainable.
2. THE MACHINE GUARDIAN — CPU / RAM / storage / thermals of the compute (2 or 4
   OCPUs — whatever is REAL). It measures first, sets the work rhythm at the true
   maximum, never a cycle wasted, never one beyond.
3. THE TERMS GUARDIAN — platform ToS thresholds. It keeps the profile of a serious
   user, never an abuser.

GUARDIAN DOCTRINE (binding, implemented here):

    MEASURE the real resources FIRST (never assume)
    -> SET limits on what was measured
    -> PUSH work to the maximum within those limits
    -> RE-READ reality every night (resources change -> limits recalculate)
    -> REPORT in every nightly summary: resources measured, limits active,
       utilization percentage.

Two rules follow from "never assume" and "absolute honesty":

* A guardian NEVER invents a measurement. A missing reading is carried as ``None``
  with a ``reason`` — never a flattering default — and NO limit is set off it.
* A limit is set ONLY from a measured resource. A non-finite or non-positive
  measurement is refused (fail-closed): the state must not set its rhythm off a
  number it cannot trust.

Pure at import (Scar #6): the guardians are reductions over the measurements the
caller hands them. They perform no I/O; the caller measures and passes the numbers.
"""

from __future__ import annotations

import math

__all__ = [
    "AccountGuardian",
    "MachineGuardian",
    "TermsGuardian",
    "GUARDIANS",
    "guardians_report",
    "cognitive_watch",
]

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _finite_positive(value, *, name: str) -> float:
    """Return ``value`` as a finite, positive float, or raise (fail-closed).

    A guardian that sets a limit off a missing/NaN/negative measurement is how a
    state runs off a cliff. Refuse the number instead.
    """
    if value is None:
        raise ValueError(f"{name} is unmeasured (never assume; fail-closed)")
    v = float(value)
    if not math.isfinite(v) or v <= 0.0:
        raise ValueError(f"{name} must be finite and positive, got {value!r} (fail-closed)")
    return v


def _finite_nonneg(value, *, name: str) -> float:
    """Return ``value`` as a finite, non-negative float, or raise (fail-closed)."""
    if value is None:
        raise ValueError(f"{name} is unmeasured (never assume; fail-closed)")
    v = float(value)
    if not math.isfinite(v) or v < 0.0:
        raise ValueError(f"{name} must be finite and non-negative, got {value!r} (fail-closed)")
    return v


def _utilization_pct(measured: float, limit: float) -> float:
    """Utilization of a set limit, capped at 100 (a reading, not a warning)."""
    if limit <= 0:
        return 0.0
    return round(min(1.0, measured / limit) * 100.0, 2)


class _Guardian:
    """Base Guardian: every subclass turns measurements into a governed rhythm."""

    name: str = "guardian"

    def read(self, **measured) -> dict:  # pragma: no cover - interface
        raise NotImplementedError

    def _envelope(self, *, measured: dict, limits: dict, rhythm: dict,
                  utilization_pct: float | None, notes: str) -> dict:
        return {
            "guardian": self.name,
            "measured": measured,
            "limits": limits,
            "rhythm": rhythm,
            "utilization_pct": utilization_pct,
            "notes": notes,
            "reading": (f"{self.name}: {notes} "
                        f"(utilization {utilization_pct}%)"
                        if utilization_pct is not None else f"{self.name}: {notes}"),
        }


# ---------------------------------------------------------------------------
# 1. THE ACCOUNT GUARDIAN — minutes, budget, quotas
# ---------------------------------------------------------------------------
class AccountGuardian(_Guardian):
    """Keeps CI/run usage at the maximum sustainable within the REAL budget.

    The measured resource is the account's monthly run-minute budget and how much
    of it is already spent; the limit is how many more runs of the measured cost
    fit; the rhythm is the number of nights to run. It never assumes a budget: an
    unmeasured budget sets no limit.
    """

    name = "account"

    def read(self, *, minutes_used, monthly_budget, days_left_in_month,
             minutes_per_run) -> dict:
        used = _finite_nonneg(minutes_used, name="minutes_used")
        budget = _finite_positive(monthly_budget, name="monthly_budget")
        per_run = _finite_positive(minutes_per_run, name="minutes_per_run")
        days_left = max(0, int(_finite_nonneg(days_left_in_month,
                                              name="days_left_in_month")))
        remaining = max(0.0, budget - used)
        runs_affordable = int(remaining // per_run)
        # PUSH to the maximum: run every remaining night the budget affords, but
        # never more nights than remain in the month.
        allowed_runs = min(days_left, runs_affordable)
        utilization = _utilization_pct(used, budget)
        notes = (f"budget {budget:g} min, used {used:g} min, {remaining:g} min left; "
                 f"a run costs {per_run:g} min -> {allowed_runs} more run(s) this month")
        return self._envelope(
            measured={"minutes_used": used, "monthly_budget": budget,
                      "days_left_in_month": days_left, "minutes_per_run": per_run},
            limits={"remaining_minutes": round(remaining, 3),
                    "runs_affordable": runs_affordable,
                    "max_runs_this_month": allowed_runs},
            rhythm={"runs_this_month": allowed_runs,
                    "minutes_per_run": per_run},
            utilization_pct=utilization, notes=notes)


# ---------------------------------------------------------------------------
# 2. THE MACHINE GUARDIAN — CPU / RAM / storage / thermals
# ---------------------------------------------------------------------------
# The state leaves headroom on every axis so a run never starves the machine or
# the night's own verification steps. These are the state's own margins on the
# MEASURED hardware, not guesses about it.
CPU_HEADROOM_FRACTION = 0.25      # reserve 25% of cores for the OS/other work
RAM_HEADROOM_FRACTION = 0.20      # never plan to use more than 80% of RAM
STORAGE_HEADROOM_FRACTION = 0.15  # keep 15% of disk free
THERMAL_CAP_C = 85.0              # throttle threshold the state holds itself to


class MachineGuardian(_Guardian):
    """Sets the work rhythm at the true maximum of the MEASURED compute.

    The measured resources are the real CPU cores, RAM, and storage (and thermals
    when available). The limits are the usable maxima after headroom; the rhythm is
    the worker count. If the machine is hot (thermals at/over the cap) the rhythm is
    cut to one worker so the state never melts the box for a night's work.
    """

    name = "machine"

    def read(self, *, cpu_cores, ram_gb, storage_gb, storage_used_gb=None,
             thermal_c=None) -> dict:
        cores = _finite_positive(cpu_cores, name="cpu_cores")
        ram = _finite_positive(ram_gb, name="ram_gb")
        storage = _finite_positive(storage_gb, name="storage_gb")

        max_workers = max(1, int(math.floor(cores * (1.0 - CPU_HEADROOM_FRACTION))))
        ram_cap = ram * (1.0 - RAM_HEADROOM_FRACTION)
        storage_cap = storage * (1.0 - STORAGE_HEADROOM_FRACTION)

        notes_parts = [f"{cores:g} cores -> {max_workers} worker(s)",
                       f"RAM cap {ram_cap:.2f}/{ram:g} GiB",
                       f"disk cap {storage_cap:.2f}/{storage:g} GiB"]

        hot = False
        if thermal_c is not None:
            t = float(thermal_c)
            if not math.isfinite(t):
                raise ValueError(f"thermal_c must be finite, got {thermal_c!r} (fail-closed)")
            hot = t >= THERMAL_CAP_C
            notes_parts.append(f"thermals {t:g}C (cap {THERMAL_CAP_C:g}C)")
            if hot:
                max_workers = 1
                notes_parts.append("HOT: rhythm cut to 1 worker")

        # Utilization is the binding axis: the fullest of the measured usages
        # against its cap. Storage usage is the only axis measured here directly.
        util = None
        if storage_used_gb is not None:
            su = float(storage_used_gb)
            if not math.isfinite(su):
                raise ValueError("storage_used_gb must be finite (fail-closed)")
            util = _utilization_pct(su, storage_cap)

        return self._envelope(
            measured={"cpu_cores": cores, "ram_gb": ram, "storage_gb": storage,
                      "storage_used_gb": storage_used_gb, "thermal_c": thermal_c},
            limits={"max_workers": max(1, int(math.floor(
                        cores * (1.0 - CPU_HEADROOM_FRACTION)))),
                    "ram_cap_gb": round(ram_cap, 3),
                    "storage_cap_gb": round(storage_cap, 3),
                    "thermal_cap_c": THERMAL_CAP_C},
            rhythm={"workers": max_workers, "hot": hot},
            utilization_pct=util, notes="; ".join(notes_parts))


# ---------------------------------------------------------------------------
# 3. THE TERMS GUARDIAN — platform ToS thresholds
# ---------------------------------------------------------------------------
# The state's own conservative margins. These are POLICY ceilings the state sets
# for itself to stay a serious user, deliberately far below any platform's hard
# limit — the Guardian's job is the PROFILE, not the maximum the platform allows.
TOOLS_API_CALLS_PER_HOUR_CAP = 300.0   # far below GitHub's 5,000/hr authenticated
TOOLS_ACCOUNT_ACTIONS_PER_HOUR_CAP = 60.0
TOOLS_MAX_DISTINCT_IDENTITIES = 1      # one identity: a person, not a botnet


class TermsGuardian(_Guardian):
    """Keeps the state inside a serious-user profile, never an abuser's.

    The measured inputs are the state's own request/action rates. The limits are
    conservative self-imposed ceilings; the rhythm is the maximum sustainable rate
    (the ceiling). It fails closed on a non-finite rate and flags any breach.
    """

    name = "terms"

    def read(self, *, api_calls_per_hour=0.0, account_actions_per_hour=0.0,
             distinct_identities=1) -> dict:
        calls = float(api_calls_per_hour)
        actions = float(account_actions_per_hour)
        if not math.isfinite(calls) or not math.isfinite(actions):
            raise ValueError("request rates must be finite (fail-closed)")
        calls = max(0.0, calls)
        actions = max(0.0, actions)
        ids = int(distinct_identities)

        call_util = _utilization_pct(calls, TOOLS_API_CALLS_PER_HOUR_CAP)
        action_util = _utilization_pct(actions, TOOLS_ACCOUNT_ACTIONS_PER_HOUR_CAP)
        util = max(call_util, action_util)

        breaches = []
        if calls > TOOLS_API_CALLS_PER_HOUR_CAP:
            breaches.append("api_calls_per_hour over the serious-user ceiling")
        if actions > TOOLS_ACCOUNT_ACTIONS_PER_HOUR_CAP:
            breaches.append("account_actions_per_hour over the serious-user ceiling")
        if ids > TOOLS_MAX_DISTINCT_IDENTITIES:
            breaches.append("more than one identity (looks like an abuser)")

        notes = (f"{calls:g}/{TOOLS_API_CALLS_PER_HOUR_CAP:g} calls/hr, "
                 f"{actions:g}/{TOOLS_ACCOUNT_ACTIONS_PER_HOUR_CAP:g} actions/hr, "
                 f"{ids} identity(ies)"
                 + (f"; BREACH: {breaches}" if breaches else "; profile clean"))
        return self._envelope(
            measured={"api_calls_per_hour": calls,
                      "account_actions_per_hour": actions,
                      "distinct_identities": ids},
            limits={"api_calls_per_hour_cap": TOOLS_API_CALLS_PER_HOUR_CAP,
                    "account_actions_per_hour_cap": TOOLS_ACCOUNT_ACTIONS_PER_HOUR_CAP,
                    "max_distinct_identities": TOOLS_MAX_DISTINCT_IDENTITIES},
            rhythm={"api_calls_per_hour": min(calls, TOOLS_API_CALLS_PER_HOUR_CAP),
                    "serious_user": not breaches},
            utilization_pct=util, notes=notes)


GUARDIANS = (AccountGuardian(), MachineGuardian(), TermsGuardian())


def guardians_report(*, account: dict | None = None, machine: dict | None = None,
                     terms: dict | None = None) -> dict:
    """Assemble the Guardians' readings for the nightly STATE REPORT (act 5).

    Each block is the output of that Guardian's ``read`` (or ``None`` if the
    resource could not be measured this night — carried honestly, never faked).
    """
    blocks = {"account": account, "machine": machine, "terms": terms}
    measured = [k for k, v in blocks.items() if v is not None]
    missing = [k for k, v in blocks.items() if v is None]
    return {
        "guardians": blocks,
        "measured_this_night": measured,
        "unmeasured_this_night": missing,
        "reading": (f"guardians read: {', '.join(measured) or 'none'}"
                    + (f"; unmeasured: {', '.join(missing)}" if missing else "")),
    }


# ---------------------------------------------------------------------------
# C7 — THE GUARDIANS' COGNITIVE WATCH (the mind's vital signs)
# ---------------------------------------------------------------------------
# Honest alarm thresholds. A belief-reversal rate at/over RIGID (too few changes:
# the mind is stuck) or at/under CHAOTIC (too many: it has no spine) is a genuine
# concern. A drift beyond DRIFT_TOL is a real recalibration, not noise.
REVERSAL_RIGID_CEILING = 0.02   # fewer than 2% of beliefs revised -> rigid
REVERSAL_CHAOTIC_FLOOR = 0.60   # more than 60% revised -> chaotic
DRIFT_TOLERANCE = 0.15          # |emotion calibration drift| beyond this -> alarm


def cognitive_watch(*, belief_reversals: float | None = None,
                    reversals_total: float | None = None,
                    simulation_accuracy: float | None = None,
                    simulation_accuracy_prior: float | None = None,
                    emotion_calibration: float | None = None,
                    emotion_calibration_prior: float | None = None) -> dict:
    """The nightly COGNITIVE WATCH: honest alarms over the mind's vital signs.

    Three watches:
      * BELIEF REVERSAL RATE — too low and the mind is RIGID (it never reconsiders);
        too high and it is CHAOTIC (it has no spine). The rate is
        ``belief_reversals / reversals_total``.
      * SIMULATION ACCURACY TREND — the imagined paths vs reality, this night vs the
        prior: a real decline is an alarm.
      * EMOTION CALIBRATION DRIFT — how far the feelings' predictive lift moved from
        the prior: a drift beyond tolerance is an alarm.

    Honest: an unmeasured axis yields NO alarm (``None``), never a fabricated one.
    """
    alarms: list[str] = []

    rate = None
    if belief_reversals is not None and reversals_total:
        rate = round(float(belief_reversals) / float(reversals_total), 6)
        if rate < REVERSAL_RIGID_CEILING:
            alarms.append(f"mente RIGIDA: solo {rate:.1%} di credenze riviste "
                          f"(soglia {REVERSAL_RIGID_CEILING:.0%})")
        elif rate > REVERSAL_CHAOTIC_FLOOR:
            alarms.append(f"mente CAOTICA: {rate:.1%} di credenze riviste "
                          f"(soglia {REVERSAL_CHAOTIC_FLOOR:.0%})")

    sim_trend = None
    if simulation_accuracy is not None and simulation_accuracy_prior is not None:
        sim_trend = round(float(simulation_accuracy) - float(simulation_accuracy_prior), 6)
        if sim_trend < -DRIFT_TOLERANCE:
            alarms.append(f"accuratezza delle simulazioni in calo: {sim_trend:+.3f}")

    emo_drift = None
    if emotion_calibration is not None and emotion_calibration_prior is not None:
        emo_drift = round(float(emotion_calibration) - float(emotion_calibration_prior), 6)
        if abs(emo_drift) > DRIFT_TOLERANCE:
            alarms.append(f"calibrazione emotiva in deriva: {emo_drift:+.3f}")

    measured = [n for n, v in (("reversal", rate), ("simulation", sim_trend),
                               ("emotion", emo_drift)) if v is not None]
    return {
        "belief_reversal_rate": rate,
        "simulation_accuracy_trend": sim_trend,
        "emotion_calibration_drift": emo_drift,
        "alarms": alarms,
        "measured": measured,
        "reading": ("allarmi cognitivi: " + "; ".join(alarms) if alarms
                    else (f"mente sana ({len(measured)} asse/i misurato/i)"
                          if measured else "nessuna lettura cognitiva stanotte")),
    }
