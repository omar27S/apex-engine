"""LAW 1/2 (Physical Might) -- THE MACHINE BODY (measure -> decide -> push).

The body of the civilization: it measures the REAL machine (CPU, RAM, thermals),
decides how many runners may work at once (cool -> parallel, hot -> serialize),
and -- after 48h of sustained saturation with thermal headroom -- prepares THE
4 OCPU / 24 GB UPGRADE as a MEASURED proposal with exact console steps in plain
Italian, never a hope.

Absolute honesty (Guardian doctrine): a missing reading is carried as ``None`` with
a ``reason`` and sets no limit -- never a flattering default. The escalation fires
only on a measured reading over the threshold.

Pure at import (Scar #6): the body is a reduction over the measurements the caller
hands it; it performs no I/O.
"""

from __future__ import annotations

import math

__all__ = [
    "CONCURRENCY_MAX",
    "HOT_UTIL_PCT",
    "ESCALATION_UTIL_PCT",
    "ESCALATION_HOURS",
    "THERMAL_HEADROOM_C",
    "capacity_reading",
    "concurrency_decision",
    "escalation_reading",
    "upgrade_steps_it",
    "machine_body_report",
]

CONCURRENCY_MAX: int = 4          # at most four arms (the 4 OCPU future)
HOT_UTIL_PCT: float = 85.0        # at/over this the box is HOT -> serialize
ESCALATION_UTIL_PCT: float = 85.0  # sustained saturation that justifies 4 OCPU
ESCALATION_HOURS: float = 48.0    # over this many hours of sustained saturation
THERMAL_HEADROOM_C: float = 75.0  # below this the box has thermal headroom

# The upgrade the Machine Guardian prepares when saturation is measured.
_UPGRADE = {
    "now": "2 OCPU / 12 GB",
    "target": "4 OCPU / 24 GB",
    "eur": 0,
}


def _finite_or_none(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def capacity_reading(*, cpu_cores=None, ram_gb=None, cpu_util_pct=None,
                     ram_util_pct=None, thermal_c=None) -> dict:
    """The body's honest capacity: measured values, and what could not be measured."""
    measured: dict = {}
    unmeasured: list[str] = []
    for name, val in (("cpu_cores", cpu_cores), ("ram_gb", ram_gb),
                      ("cpu_util_pct", cpu_util_pct), ("ram_util_pct", ram_util_pct),
                      ("thermal_c", thermal_c)):
        v = _finite_or_none(val)
        if v is None:
            unmeasured.append(name)
        else:
            measured[name] = v
    return {
        "measured": measured,
        "unmeasured": unmeasured,
        "reading": (f"machine measured: {sorted(measured) or 'none'}"
                    + (f"; unmeasured: {unmeasured}" if unmeasured else "")),
    }


def concurrency_decision(*, cpu_util_pct=None, ram_util_pct=None,
                         thermal_c=None) -> dict:
    """How many arms may run at once: cool -> parallel, hot -> serialize.

    Fails closed to a single worker when nothing is measured (never over-commit a
    box whose state is unknown). ``hot`` is true at/over ``HOT_UTIL_PCT`` on either
    CPU or RAM, or at/over the thermal headroom cap.
    """
    cpu = _finite_or_none(cpu_util_pct)
    ram = _finite_or_none(ram_util_pct)
    therm = _finite_or_none(thermal_c)

    if cpu is None and ram is None and therm is None:
        return {"workers": 1, "hot": None, "measured": False,
                "why": "nothing measured -- the body runs one arm (fail-closed)"}

    hot = False
    reasons: list[str] = []
    if cpu is not None and cpu >= HOT_UTIL_PCT:
        hot = True
        reasons.append(f"cpu {cpu:g}% >= {HOT_UTIL_PCT:g}%")
    if ram is not None and ram >= HOT_UTIL_PCT:
        hot = True
        reasons.append(f"ram {ram:g}% >= {HOT_UTIL_PCT:g}%")
    if therm is not None and therm >= THERMAL_HEADROOM_C:
        hot = True
        reasons.append(f"thermal {therm:g}C >= {THERMAL_HEADROOM_C:g}C")

    if hot:
        return {"workers": 1, "hot": True, "measured": True,
                "why": "HOT: serialize to 1 arm (" + ", ".join(reasons) + ")"}

    # cool: parallelism scales with the free CPU headroom, bounded.
    if cpu is not None:
        headroom = max(0.0, 100.0 - cpu)
        workers = max(1, min(CONCURRENCY_MAX, int(math.floor(headroom / 25.0)) + 1))
        why = f"cool: cpu {cpu:g}% -> {workers} arm(s)"
    else:
        workers = 2
        why = "cool (cpu unmeasured): 2 arms"
    return {"workers": workers, "hot": False, "measured": True, "why": why}


def escalation_reading(*, sustained_util_pct=None, hours=None,
                       thermal_c=None) -> dict:
    """THE MEASURED PATH UP: is the box saturated enough to justify 4 OCPU / 24 GB?

    Proposes the upgrade only when a MEASURED sustained utilization is over
    ``ESCALATION_UTIL_PCT`` for over ``ESCALATION_HOURS`` hours AND the thermals
    have headroom. Otherwise it reports honestly how far from the threshold the
    machine is -- never a hope.
    """
    util = _finite_or_none(sustained_util_pct)
    hrs = _finite_or_none(hours)
    therm = _finite_or_none(thermal_c)

    if util is None or hrs is None:
        return {"propose": False, "measured": False, "upgrade": None,
                "reading": "escalation unmeasured: no sustained utilization reading "
                           "-- not yet (measure first)"}

    thermal_ok = therm is None or therm < THERMAL_HEADROOM_C
    propose = util > ESCALATION_UTIL_PCT and hrs > ESCALATION_HOURS and thermal_ok
    if propose:
        return {"propose": True, "measured": True, "upgrade": dict(_UPGRADE),
                "util_pct": util, "hours": hrs, "thermal_c": therm,
                "reading": (f"MEASURED: {util:g}% sustained for {hrs:g}h with thermal "
                            f"headroom -> propose 4 OCPU / 24 GB (0 EUR under PAYG)")}
    gap_u = round(max(0.0, ESCALATION_UTIL_PCT - util), 1)
    gap_h = round(max(0.0, ESCALATION_HOURS - hrs), 1)
    return {"propose": False, "measured": True, "upgrade": None,
            "util_pct": util, "hours": hrs, "thermal_c": therm,
            "reading": (f"not yet: {util:g}%/{ESCALATION_UTIL_PCT:g}% "
                        f"({gap_u:g} pts away), {hrs:g}h/{ESCALATION_HOURS:g}h "
                        f"({gap_h:g}h away)")}


def upgrade_steps_it() -> list[str]:
    """The exact console steps for the 4 OCPU / 24 GB upgrade, in plain Italian."""
    return [
        "1. Accedi alla Console Oracle Cloud (cloud.oracle.com) con l'account del CEO.",
        "2. Menu -> Compute -> Instances -> seleziona l'istanza del Cuore (apex-heart).",
        "3. Spegni l'istanza: Instance -> Stop (attendi 'Stopped').",
        "4. Instance -> Edit -> Edit shape: scegli VM.Standard.A1.Flex.",
        "5. Imposta 4 OCPU e 24 GB di memoria (il massimo sempre-gratuito Ampere A1).",
        "6. Avvia l'istanza: Start. Attendi 'Running'.",
        "7. Controlla che il costo resti 0 EUR: Menu -> Billing & Cost Management -> "
        "Cost Analysis (con PAYG il sempre-gratuito resta a 0 EUR entro i limiti A1).",
        "8. Verifica l'upgrade: ssh e `nproc` deve mostrare 4, `free -g` circa 24 GB.",
        "9. I Guardiani ri-misurano da soli: nuovi limiti -> nuovo ritmo automatico.",
    ]


def machine_body_report(*, capacity: dict | None = None, concurrency: dict | None = None,
                        escalation: dict | None = None) -> dict:
    """Assemble the body's nightly reading (capacity + concurrency + escalation)."""
    cap = capacity or {}
    conc = concurrency or {}
    esc = escalation or {}
    return {
        "capacity": cap,
        "concurrency": conc,
        "escalation": esc,
        "reading": (f"{cap.get('reading', 'capacity unmeasured')}; "
                    f"{conc.get('why', 'concurrency unmeasured')}; "
                    f"{esc.get('reading', 'escalation unmeasured')}"),
    }
