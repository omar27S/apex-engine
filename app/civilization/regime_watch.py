"""THE REGIME WATCHTOWER -- JUMP 4: INSTANT REGIME ADAPTATION (the system changes skin).

The system used to discover a market shift AFTER it happened -- when trend strategies
started losing, minutes or hours too late. The Watchtower watches the falcon's live
regime flags and, the moment a pair's regime changes, acts:

  * THE SHIFT DETECTOR -- when a pair's regime changes (trending->ranging), it notes
    the transition timestamp, the CONFIDENCE (how clean the shift signal is), and the
    AFFECTED families (those specialized in the OLD regime). The event fires into the
    interbrain with the mode "IL MONDO CAMBIA" -- visible to all;
  * THE INSTANT RECONFIGURATION PROTOCOL -- with confidence above the threshold, the
    families of the OLD regime are PAUSED for new entries and the families of the NEW
    regime receive a PRIORITY BOOST. Existing positions are managed normally: the exit
    logic is regime-agnostic;
  * THE PORTFOLIO REGIME MAP -- which families are ACTIVE vs PAUSED per pair, across
    the portfolio. The Guardian watches it: if more than half of the strategies are
    paused at once, the system is confused and the Council must intervene.

Honesty is binding. A shift with no measured confidence is never acted on (the
reconfiguration is "trattenuta"); an unmeasured regime is ``None`` (never a guess).
Pure at import (Scar #6): every reduction takes the readings + the previous map it is
given; it never reads the wall clock.
"""

from __future__ import annotations

from app.civilization import falcon
from app.factory import realms

__all__ = [
    "REGIME_VERSION",
    "REGIME_EVENT_MODE",
    "SHIFT_CONFIDENCE_THRESHOLD",
    "PAUSE_ALARM_FRACTION",
    "REGIME_AFFINITY",
    "shift_confidence",
    "detect_shifts",
    "fire_regime_event",
    "reconfiguration",
    "portfolio_regime_map",
    "guardian_alarm",
    "update_regimes",
    "regime_watch_block",
]

REGIME_VERSION: int = 1

# The mode of the regime event (visible to all in the interbrain).
REGIME_EVENT_MODE: str = "IL MONDO CAMBIA"

# A shift must be at least this clean before the system changes skin.
SHIFT_CONFIDENCE_THRESHOLD: float = 0.6

# If more than this fraction of the strategy states are paused, the Guardian alarms.
PAUSE_ALARM_FRACTION: float = 0.5

# Which FAMILY GROUPS specialize in which falcon regime. This is the honest domain
# knowledge: trend/momentum/breakout/structure hunt a TREND; meanrev/relative/pattern
# fade a RANGE; volatility/breakout/momentum ride a BURST. Nothing specializes in a
# DEAD market -- the tuple is empty and the reading says so.
REGIME_AFFINITY: dict[str, tuple[str, ...]] = {
    "trending": ("trend", "momentum", "breakout", "structure"),
    "ranging": ("meanrev", "relative", "pattern"),
    "volatile": ("volatility", "breakout", "momentum"),
    "dead": (),
}


def shift_confidence(reading: dict, *, to: str | None = None) -> float | None:
    """How CLEAN a pair's shift signal is, from the live reading (0..1), or ``None``.

    Derived from the MEASURED axes only. The confidence measures how DECISIVELY the
    reading sits in the NEW regime: a collapse to ``dead`` is cleaner the LOWER the
    velocity; every other regime is cleaner the higher the velocity/volatility/delta.
    Honest: no measured velocity -> ``None`` (an unmeasured shift is never acted on).
    """
    r = reading or {}
    vel = r.get("tick_velocity")
    if vel is None:
        return None
    vel = float(vel)
    if to == "dead":
        return round(max(0.0, 1.0 - min(1.0, vel / 10.0)), 3)
    parts = [min(1.0, max(0.0, vel) / 30.0)]
    vol = r.get("volatility_pips")
    if vol is not None:
        parts.append(min(1.0, max(0.0, float(vol)) / 15.0))
    delta = r.get("session_delta")
    if delta is not None:
        parts.append(min(1.0, abs(float(delta)) / 60.0))
    return round(sum(parts) / len(parts), 3)


def detect_shifts(prev_regimes: dict, curr_regimes: dict, *,
                  readings: dict | None = None, ts: str = "") -> list[dict]:
    """Detect per-pair REGIME SHIFTS between two regime maps (honest).

    A shift is recorded only when BOTH the previous and the current regime are
    MEASURED and they differ. Each event carries the timestamp, the confidence (or
    ``None``), the affected families (old regime) and the unlocked families (new).
    """
    readings = readings or {}
    out: list[dict] = []
    for pair, to in sorted((curr_regimes or {}).items()):
        frm = (prev_regimes or {}).get(pair)
        if to is None or frm is None or to == frm:
            continue
        conf = shift_confidence(readings.get(pair) or {}, to=to)
        out.append({
            "ts": str(ts), "pair": pair, "from": frm, "to": to,
            "confidence": conf,
            "affected": list(REGIME_AFFINITY.get(frm, ())),
            "unlocked": list(REGIME_AFFINITY.get(to, ())),
            "reading": (f"{pair}: {frm}->{to} (confidenza "
                        + (f"{conf:.0%}" if conf is not None else "non misurata") + ")"),
        })
    return out


def fire_regime_event(state: dict, shift: dict, *, ts: str = "") -> dict:
    """Fire a regime event into the interbrain (mode "IL MONDO CAMBIA", visible to all).

    It INFORMS; it does not command. The Council may call an extraordinary session on
    a high-confidence, multi-pair shift -- that is the Council's call, not the tower's.
    """
    row = {"mode": REGIME_EVENT_MODE, "ts": str(ts or shift.get("ts", "")), **shift}
    st = state if state is not None else {}
    reg = st.setdefault("regime", {})
    reg.setdefault("events", []).append(row)
    del reg["events"][:-200]
    st.setdefault("interbrain", []).append(
        {"author": "regime",
         "idea": f"{REGIME_EVENT_MODE}: {shift.get('reading', '')}",
         "kind": "discovery", "ts": row["ts"], "status": "open"})
    return row


def reconfiguration(shift: dict, *,
                    threshold: float = SHIFT_CONFIDENCE_THRESHOLD) -> dict:
    """The INSTANT RECONFIGURATION PROTOCOL for one shift.

    With confidence above the threshold: PAUSE the old-regime families (no new
    entries) and BOOST the new-regime families. Honest: an unmeasured confidence
    never triggers a change ("trattenuta"); a confidence below the threshold is
    explicitly held back. An empty old/new set still applies (nothing to pause).
    """
    conf = shift.get("confidence")
    old = list(shift.get("affected") or [])
    new = list(shift.get("unlocked") or [])
    if conf is None:
        return {"applied": False, "paused": [], "boosted": [], "measured": False,
                "reading": "riconfigurazione non applicata (confidenza non misurata)"}
    if conf < threshold:
        return {"applied": False, "paused": [], "boosted": [], "measured": True,
                "confidence": conf,
                "reading": (f"riconfigurazione trattenuta (confidenza {conf:.0%} "
                            f"< soglia {threshold:.0%})")}
    return {"applied": True, "paused": old, "boosted": new, "measured": True,
            "confidence": conf,
            "reading": (f"il sistema cambia pelle: {len(old)} famiglie in pausa, "
                        f"{len(new)} attivate ({shift.get('pair')}: "
                        f"{shift.get('from')}->{shift.get('to')})")}


def portfolio_regime_map(state: dict) -> dict:
    """The live PORTFOLIO REGIME MAP: active vs paused families per pair.

    Aggregates the persisted gating into rows and the honest paused fraction (over
    the strategy STATES, not the families -- a family paused on 3 pairs weighs 3).
    """
    gating = ((state or {}).get("regime") or {}).get("gating") or {}
    rows: list[dict] = []
    paused_states = total_states = 0
    for pair, g in sorted(gating.items()):
        paused = list((g or {}).get("paused") or [])
        active = list((g or {}).get("active") or [])
        rows.append({"pair": pair, "paused": paused, "active": active})
        paused_states += len(paused)
        total_states += len(paused) + len(active)
    frac = (paused_states / total_states) if total_states else None
    return {"rows": rows, "paused": paused_states,
            "active": total_states - paused_states,
            "paused_fraction": (round(frac, 4) if frac is not None else None),
            "reading": (f"mappa dei regimi: {paused_states} stati in pausa su "
                        f"{total_states} ({frac:.0%})" if total_states
                        else "mappa dei regimi: nessuna riconfigurazione")}


def guardian_alarm(regime_map: dict, *,
                   fraction: float = PAUSE_ALARM_FRACTION) -> dict | None:
    """The Guardian's alarm: too many strategies paused at once (the system is confused).

    Honest: an unmeasured paused fraction never alarms (no data, no alarm).
    """
    f = (regime_map or {}).get("paused_fraction")
    if f is None:
        return None
    if f > fraction:
        return {"fraction": f, "measured": True,
                "reading": (f"ALLARME GUARDIANO: {f:.0%} delle strategie in pausa "
                            "-- il sistema e' confuso, il Consiglio intervenga")}
    return None


def update_regimes(state: dict, readings: dict, *, ts: str = "",
                   threshold: float = SHIFT_CONFIDENCE_THRESHOLD) -> dict:
    """One Watchtower turn: detect shifts, fire events, reconfigure, map, alarm.

    Compares the pair regimes now to the last recorded map, fires a "IL MONDO CAMBIA"
    event per shift, applies the reconfiguration for each confident shift (persisting
    the gating per pair), and returns the block (shifts, reconfigurations, map,
    Guardian alarm). Fail-open: a state without readings still yields an honest block.
    """
    st = state if state is not None else {}
    reg = st.setdefault("regime", {})
    flags = falcon.regime_flags(readings or {})
    curr = {r["pair"]: r["regime"] for r in flags["rows"]}
    prev = dict(reg.get("last") or {})
    shifts = detect_shifts(prev, curr, readings=readings, ts=ts)

    gating = dict(reg.get("gating") or {})
    applied: list[dict] = []
    for sh in shifts:
        fire_regime_event(st, sh, ts=ts)
        rec = reconfiguration(sh, threshold=threshold)
        if rec["applied"]:
            gating[sh["pair"]] = {"paused": list(rec["paused"]),
                                  "active": list(rec["boosted"])}
            applied.append({"pair": sh["pair"], **rec})

    reg["last"] = curr
    reg["gating"] = gating
    reg.setdefault("events", [])
    rmap = portfolio_regime_map(st)
    alarm = guardian_alarm(rmap)
    reg["last_map"] = rmap
    reg["last_alarm"] = alarm
    return {
        "shifts": shifts, "applied": applied, "map": rmap, "alarm": alarm,
        "regimes": flags["counts"], "unmeasured": flags["unmeasured"],
        "reading": (f"veglia dei regimi: {len(shifts)} cambi, "
                    f"{len(applied)} riconfigurazioni; {rmap['reading']}"),
    }


def regime_watch_block(state: dict, *, readings: dict | None = None,
                       ts: str = "") -> dict:
    """The regime watch block for the artifact + the Letter ("LA PELLE DEL GIORNO").

    Runs a Watchtower turn over the readings (or the falcon's stored ones) and
    returns the shifts, the reconfigurations, the map and the Guardian alarm.
    """
    st = state if state is not None else {}
    if readings is None:
        readings = (st.get("falcon") or {}).get("readings") or {}
    block = update_regimes(st, readings, ts=ts)
    st["regime_summary"] = block
    return block
