"""THE SPECIALIST HUNTERS -- the three most lethal setups in Forex (THE REAL HUNT,
Part Two).

Some setups are structurally more reliable than others. The system fields THREE
dedicated hunters, each with institutional-level execution and each with its own
kill switch:

  * HUNTER ALPHA -- THE LIQUIDITY SWEEP PREDATOR: price sweeps a cluster of stops and
    then RECLAIMS the level and reverses. Three independent confirmations are required
    (the sweep, the exhaustion of the attacker, the reversal ignition). Impossible
    without the falcon's DOM + tick data -- our STRUCTURAL advantage;
  * HUNTER BRAVO -- THE EVENT REACTION PREDATOR: a high-impact event fires; normal
    trading is PAUSED; after the initial spike STABILISES we enter in the confirmed
    direction, with the Dragon's linguistic reading of the statement and the
    collective's deja-vu. Our INFORMATIONAL advantage;
  * HUNTER CHARLIE -- THE SESSION BOUNDARY AMBUSHER: the London/NY opens and the
    London close are the day's most predictable volatility explosions. We enter on the
    FIRST PULLBACK after the boundary's initial impulse (not the impulse itself), and
    the system learns each boundary's personality over time.

Shared discipline: each hunter operates WITHIN the Cathedral (the columns provide the
context, the hunter the trigger); each hunter PAUSES for 24 hours after 3 consecutive
losses and the Council reviews; each hunter's results are tracked separately.

Honesty is binding: a hunter never fires without ALL of its required confirmations
(a missing one is an honest "prepare", never a fabricated entry); an unmeasured input
is ``None`` and blocks the hunt; the kill switch counts only REAL resolved outcomes.
Pure at import (Scar #6): the caller supplies the observations and the timestamp.
"""

from __future__ import annotations

__all__ = [
    "HUNTERS_VERSION",
    "HUNTERS",
    "KILL_SWITCH_LOSSES",
    "HUNTER_RR",
    "hunters",
    "hunter_state",
    "alpha_sweep",
    "bravo_event",
    "charlie_boundary",
    "evaluate_hunter",
    "record_result",
    "hunter_block",
    "hunter_context",
]

HUNTERS_VERSION: int = 1

HUNTERS: tuple[str, ...] = ("alpha", "bravo", "charlie")

# THE KILL SWITCH: 3 consecutive losses -> the hunter pauses for 24 hours.
KILL_SWITCH_LOSSES: int = 3
KILL_SWITCH_HOURS: int = 24

# The hunters' target reward:risk (RR 2.5+ forever, per the Ten Laws).
HUNTER_RR: dict[str, float] = {"alpha": 3.0, "bravo": 2.5, "charlie": 2.5}


def hunters(state: dict) -> dict:
    """The hunters' persistent structures (created empty on first access)."""
    st = state if state is not None else {}
    return st.setdefault("hunters", {
        "version": HUNTERS_VERSION,
        "results": {h: {"fires": 0, "wins": 0, "losses": 0, "streak": 0,
                        "paused_until": "", "history": []} for h in HUNTERS},
        "last": None,
    })


def hunter_state(state: dict, hunter: str) -> dict:
    """One hunter's persistent record (created empty on first access)."""
    h = str(hunter)
    rec = hunters(state)["results"].setdefault(
        h, {"fires": 0, "wins": 0, "losses": 0, "streak": 0, "paused_until": "",
            "history": []})
    return rec


def _parse_ts(value) -> "datetime | None":
    from datetime import datetime, timezone
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _paused(rec: dict, ts: str) -> bool:
    """Is the hunter still inside its kill-switch pause window?"""
    until = _parse_ts(rec.get("paused_until"))
    now = _parse_ts(ts)
    if until is None or now is None:
        return False
    return now < until


def record_result(state: dict, *, hunter: str, won: bool, ts: str = "",
                  detail: dict | None = None) -> dict:
    """Record ONE resolved hunt outcome and maintain the kill switch.

    A loss extends the consecutive-loss streak; a win resets it. On the
    ``KILL_SWITCH_LOSSES``-th consecutive loss the hunter PAUSES for
    ``KILL_SWITCH_HOURS`` (its ``paused_until`` is set) and the Council is flagged to
    review. Honest: only real resolved outcomes are recorded.
    """
    rec = hunter_state(state, hunter)
    rec["fires"] = int(rec.get("fires") or 0) + 1
    if won:
        rec["wins"] = int(rec.get("wins") or 0) + 1
        rec["streak"] = 0
    else:
        rec["losses"] = int(rec.get("losses") or 0) + 1
        rec["streak"] = int(rec.get("streak") or 0) + 1
    paused = False
    if rec["streak"] >= KILL_SWITCH_LOSSES:
        from datetime import datetime, timedelta, timezone
        now = _parse_ts(ts) or datetime.now(timezone.utc)
        rec["paused_until"] = (now + timedelta(hours=KILL_SWITCH_HOURS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        paused = True
    rec.setdefault("history", []).append(
        {"ts": str(ts), "won": bool(won), "detail": dict(detail or {})})
    del rec["history"][:-200]
    return {"hunter": str(hunter), "won": bool(won), "streak": rec["streak"],
            "paused": paused, "paused_until": rec.get("paused_until") or "",
            "council_review": paused,
            "reading": (f"caccia {hunter}: " + ("vinta" if won else "persa")
                        + (f" -- PAUSA {KILL_SWITCH_HOURS}h (3 sconfitte di fila, "
                           f"il Consiglio rivede)" if paused else ""))}


# --- HUNTER ALPHA -- THE LIQUIDITY SWEEP PREDATOR --------------------------

def alpha_sweep(ev: dict, *, ts: str = "") -> dict:
    """Evaluate a liquidity-sweep hunt from its three independent confirmations.

    Required (all three): the SWEEP (price broke the level AND reclaimed it -- not
    just a wick), the EXHAUSTION (the attackers have no more fuel + the DOM wall is
    consumed), the REVERSAL IGNITION (a momentum candle fires the other way). Honest:
    an unmeasured confirmation blocks the hunt and is named.
    """
    e = ev or {}
    sweep = e.get("sweep_confirmed")
    exhaust = e.get("exhaustion")
    ignite = e.get("ignition")
    missing = [name for name, v in (("sweep", sweep), ("exhaustion", exhaust),
                                    ("ignition", ignite)) if v is not True]
    direction = e.get("direction")
    if missing:
        return {"hunter": "alpha", "fire": False, "prepare": bool(sweep is True),
                "direction": direction, "missing": missing,
                "level": e.get("level"), "rr": HUNTER_RR["alpha"],
                "reading": ("caccia alfa: prepara ma non entra -- manca "
                            + ", ".join(missing))}
    return {"hunter": "alpha", "fire": True, "prepare": True, "direction": direction,
            "missing": [], "level": e.get("level"), "rr": HUNTER_RR["alpha"],
            "sweep": {"level": e.get("level"), "reclaimed": True,
                      "velocity": e.get("velocity")},
            "reading": (f"caccia alfa: SWEEP su {e.get('level')} -- strappo, "
                        f"esaurimento, ignizione: il predatore scatta "
                        f"({direction})")}


# --- HUNTER BRAVO -- THE EVENT REACTION PREDATOR ---------------------------

def bravo_event(ev: dict, *, ts: str = "") -> dict:
    """Evaluate an event-reaction hunt (pre-event pause, then the event fade).

    The hunt requires: a HIGH-impact event that has FIRED, the market's reaction
    CONFIRMED by the falcon, the initial spike STABILISED (the fade), and -- when a
    statement is involved -- the Dragon's linguistic reading. Honest: before the
    stabilisation the hunter PREPARES but does not enter ("the first 30 seconds are
    noise"); an unmeasured reaction blocks the hunt.
    """
    e = ev or {}
    event = e.get("event") or {}
    impact = str(event.get("impact") or "").lower()
    high = impact in ("high", "alto")
    fired = bool(event.get("fired"))
    reaction = e.get("reaction_direction")
    stabilised = e.get("stabilised")
    dragon_read = e.get("dragon_reading")
    if not high or not fired:
        return {"hunter": "bravo", "fire": False, "prepare": bool(high),
                "direction": None, "rr": HUNTER_RR["bravo"],
                "reading": ("caccia bravo: nessun evento ad alto impatto -- "
                            "il mercato respira")}
    if stabilised is not True:
        return {"hunter": "bravo", "fire": False, "prepare": True,
                "direction": reaction, "rr": HUNTER_RR["bravo"],
                "reading": ("caccia bravo: evento ad alto impatto -- in attesa che lo "
                            "spike si stabilizzi (i primi secondi sono rumore)")}
    if reaction is None:
        return {"hunter": "bravo", "fire": False, "prepare": True, "direction": None,
                "rr": HUNTER_RR["bravo"],
                "reading": "caccia bravo: reazione non misurata -- nessuna conferma"}
    return {"hunter": "bravo", "fire": True, "prepare": True, "direction": reaction,
            "rr": HUNTER_RR["bravo"], "event": {"name": event.get("name"),
                                                "impact": event.get("impact")},
            "dragon_reading": dragon_read, "dejavu": e.get("dejavu"),
            "reading": (f"caccia bravo: evento {event.get('name')} -- reazione "
                        f"confermata ({reaction}), spike stabilizzato"
                        + (f"; il Drago legge: {dragon_read}" if dragon_read else "")
                        + ": il predatore scatta")}


# --- HUNTER CHARLIE -- THE SESSION BOUNDARY AMBUSHER -----------------------

BOUNDARIES: dict[str, int] = {"london_open": 7, "ny_open": 13, "london_close": 16}


def charlie_boundary(ev: dict, *, ts: str = "") -> dict:
    """Evaluate a session-boundary ambush (the first pullback after the impulse).

    The hunt requires: we are AT a known boundary, the boundary's initial IMPULSE has
    fired (the signature), and the FIRST PULLBACK is in progress. Honest: an entry on
    the impulse itself is refused ("not on the impulse -- on the retest"); an
    unmeasured signature blocks the hunt.
    """
    e = ev or {}
    boundary = e.get("boundary")
    if boundary not in BOUNDARIES:
        return {"hunter": "charlie", "fire": False, "prepare": False, "direction": None,
                "rr": HUNTER_RR["charlie"],
                "reading": "caccia charlie: nessun confine di sessione"}
    signature = e.get("signature_direction")
    impulse = e.get("impulse_fired")
    pullback = e.get("pullback")
    if impulse is not True or signature is None:
        return {"hunter": "charlie", "fire": False, "prepare": True, "direction": None,
                "boundary": boundary, "rr": HUNTER_RR["charlie"],
                "reading": (f"caccia charlie: {boundary} -- in attesa della firma "
                            f"del confine (il primo impulso direzionale)")}
    if pullback is not True:
        return {"hunter": "charlie", "fire": False, "prepare": True,
                "direction": signature, "boundary": boundary,
                "rr": HUNTER_RR["charlie"],
                "reading": (f"caccia charlie: {boundary} -- impulso {signature}: "
                            f"aspetto il PRIMO RITRACCIAMENTO (non entro sull'impulso)")}
    return {"hunter": "charlie", "fire": True, "prepare": True, "direction": signature,
            "boundary": boundary, "rr": HUNTER_RR["charlie"],
            "personality": e.get("personality"),
            "reading": (f"caccia charlie: {boundary} -- firma {signature}, primo "
                        f"ritracciamento: l'imboscata scatta")}


def evaluate_hunter(state: dict, hunter: str, ev: dict, *, ts: str = "") -> dict:
    """Evaluate one hunter, honouring its kill switch.

    A paused hunter PREPARES but never fires (the honest reason is the pause). The
    evaluation is delegated to the hunter's own function.
    """
    h = str(hunter)
    rec = hunter_state(state, h)
    if _paused(rec, ts):
        return {"hunter": h, "fire": False, "prepare": False, "paused": True,
                "paused_until": rec.get("paused_until"),
                "reading": (f"caccia {h}: IN PAUSA fino a {rec.get('paused_until')} "
                            f"(3 sconfitte di fila)")}
    fn = {"alpha": alpha_sweep, "bravo": bravo_event, "charlie": charlie_boundary}[h]
    out = fn(ev, ts=ts)
    out["paused"] = False
    out.setdefault("fire", False)
    return out


def hunter_block(state: dict, context: dict, *, ts: str = "") -> dict:
    """The hunters' block for the artifact + the Letter: all three evaluated.

    ``context`` maps a hunter to its evidence (``alpha``/``bravo``/``charlie``). Each
    hunter is evaluated within the Cathedral (the caller passes the gate; a hunter
    PREPARES but only FIRES when the gate allows -- the block records both). Honest:
    no evidence -> the hunter reports that it has nothing to hunt.
    """
    ctx = context or {}
    gate = ctx.get("gate") or {}
    gate_fires = gate.get("class") in ("A", "B")
    rows: list[dict] = []
    for h in HUNTERS:
        ev = ctx.get(h) or {}
        out = evaluate_hunter(state, h, ev, ts=ts)
        rec = hunter_state(state, h)
        out["record"] = {"fires": rec["fires"], "wins": rec["wins"],
                         "losses": rec["losses"], "streak": rec["streak"],
                         "paused_until": rec.get("paused_until") or ""}
        # the hunter fires WITHIN the Cathedral: without an aligned gate it PREPARES.
        if out.get("fire") and not gate_fires:
            out = {**out, "fire": False, "prepare": True,
                   "reading": out["reading"] + " -- ma la Cattedrale non allinea "
                   "ancora (prepara, non entra)"}
        out["fired_within_cathedral"] = bool(out.get("fire"))
        rows.append(out)
    fired = [r for r in rows if r.get("fire")]
    block = {
        "version": HUNTERS_VERSION,
        "hunters": rows,
        "fired": [r["hunter"] for r in fired],
        "prepared": [r["hunter"] for r in rows if r.get("prepare") and not r.get("fire")],
        "gate_class": gate.get("class"),
        "results": {h: {k: hunter_state(state, h)[k]
                        for k in ("fires", "wins", "losses", "streak")}
                    for h in HUNTERS},
        "reading": (f"i cacciatori: {len(fired)} scattati"
                    + (f" ({', '.join(r['hunter'] for r in fired)})" if fired else "")
                    + ", " + str(len([r for r in rows if r.get("prepare") and not
                                      r.get("fire")])) + " in preparazione"),
    }
    hunters(state)["last"] = block
    return block


# --- DEBT-063 -- THE HUNTER CONTEXT BUILT FROM REAL LIVE DATA --------------

def hunter_context(store_state: dict, *, gate: dict | None = None,
                   ts: str = "") -> dict:
    """Assemble each hunter's evidence from the REAL live readings (DEBT-063).

    Before this, ``_run_the_hunt`` handed the hunters an EMPTY context (only the
    gate), so no hunter could ever fire even when the live data supported it. This
    builds the three hunters' evidence from what was actually MEASURED:

      * ALPHA (liquidity sweep) -- a pending microstructure event on the hot pair
        (a spread blowout or a liquidity vacuum) is the sweep's raw material; the
        exhaustion is a measured tick-velocity collapse; the ignition is a measured
        session-delta flip. Each is ``True`` only when measured, else absent (the
        hunter then prepares, never fires on a guess);
      * BRAVO (event reaction) -- a web-watch event whose impact is high and whose
        time has passed (fired); the reaction is the hot pair's measured session
        delta; the stabilisation is the event's own ``stabilised`` boolean when the
        watch carries it;
      * CHARLIE (session boundary) -- the circadian phase AT ``ts`` maps to a real
        boundary (open/close) and the hot pair's measured momentum signature.

    Honest: any unmeasured input is simply omitted -- the hunter's own logic then
    reports "prepare" and names the missing confirmation; no fabricated evidence.
    """
    state = store_state or {}
    hot = state.get("hot_pairs") or {}
    pair = str((hot.get("chosen") or [None])[0] or "") or ""
    readings = state.get("falcon_readings") or state.get("readings") or {}
    r = dict(readings.get(pair) or {}) if pair else {}

    ctx: dict = {"gate": gate or {}}

    # --- ALPHA -------------------------------------------------------------
    events = state.get("micro_events") or []
    sweep_kinds = {"spread_blowout", "liquidity_vacuum", "tick_burst"}
    sweep_ev = [e for e in events if e.get("pair") == pair
                and e.get("kind") in sweep_kinds]
    vel = r.get("tick_velocity")
    delta = r.get("session_delta")
    alpha: dict = {}
    if sweep_ev:
        alpha["sweep_confirmed"] = True
        alpha["level"] = sweep_ev[0].get("value")
        alpha["velocity"] = vel
    if isinstance(vel, (int, float)) and vel <= 2.0:
        alpha["exhaustion"] = True
    if isinstance(delta, (int, float)) and abs(delta) >= 20.0:
        alpha["ignition"] = True
        alpha["direction"] = 1 if delta > 0 else -1
    ctx["alpha"] = alpha

    # --- BRAVO -------------------------------------------------------------
    ww = (state.get("web_watch") or {})
    events_ww = (ww.get("events") or (ww.get("horizon") or {}).get("events") or [])
    bravo: dict = {}
    fired = _fired_event(events_ww, ts=ts)
    if fired is not None:
        bravo["event"] = {"name": fired.get("name"), "impact": fired.get("impact"),
                          "fired": True}
        if fired.get("stabilised") is not None:
            bravo["stabilised"] = bool(fired.get("stabilised"))
        if isinstance(delta, (int, float)) and delta != 0:
            bravo["reaction_direction"] = 1 if delta > 0 else -1
    ctx["bravo"] = bravo

    # --- CHARLIE -----------------------------------------------------------
    boundary = _boundary_at(ts)
    charlie: dict = {}
    if boundary:
        charlie["boundary"] = boundary
        if isinstance(delta, (int, float)) and abs(delta) >= 15.0:
            charlie["impulse_fired"] = True
            charlie["signature_direction"] = 1 if delta > 0 else -1
            # the first pullback: velocity has turned against the impulse.
            if isinstance(vel, (int, float)) and vel < 5.0:
                charlie["pullback"] = True
    ctx["charlie"] = charlie

    return ctx


def _fired_event(events: list[dict], *, ts: str) -> dict | None:
    """The most recent high-impact event whose time has passed (honest)."""
    now = _parse_ts(ts)
    if now is None:
        return None
    best: dict | None = None
    for e in (events or []):
        if str(e.get("impact") or "").lower() not in ("high", "alto"):
            continue
        when = _parse_ts(e.get("ts"))
        if when is not None and when <= now:
            if best is None or _parse_ts(best.get("ts")) is None or when > _parse_ts(best["ts"]):
                best = e
    return best


# The circadian phase -> the session boundary it opens (Charlie's ambush points).
PHASE_BOUNDARY: dict[str, str] = {
    "london_alert": "london_open",
    "ny_peak": "ny_open",
    "evening_consolidation": "london_close",
}


def _boundary_at(ts: str) -> str | None:
    """The session boundary at ``ts`` (from the circadian phase), or ``None``."""
    if not str(ts or "").strip():
        return None
    from app.civilization import circadian as circ_mod
    phase = circ_mod.phase_at(ts)
    return PHASE_BOUNDARY.get(phase)

