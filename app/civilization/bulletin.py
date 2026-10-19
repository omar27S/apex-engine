"""LAW 4 (Physical Might) -- THE NIGHT BULLETIN v3 (the civilization's diary).

Every night the civilization writes a ONE-MINUTE Italian page and commits it with
the certificate at ``APEX/bulletins/notte_YYYY-MM-DD.md``. The page is the
civilization's autobiography: what the night did, the complete statistics, what we
learned, the Guardians, the Council's decisions WITH their reasoning, the network's
exchanges, the Heart, tonight's curiosity and dreams, and the requests to the CEO.

Absolute honesty: a statistic the night did not produce is printed "non misurato",
never invented. The page is PURE (Scar #6): it reduces the report + cycle block the
caller hands it.
"""

from __future__ import annotations

import re

from app.state import charter as _charter

__all__ = ["build_bulletin_v3", "bulletin_filename", "bulletin_path",
           "statistics_from"]


def _f(v, dash="non misurato"):
    if v is None or v == "":
        return dash
    return v


def _pct(v):
    return "non misurato" if v is None else f"{v}%"


def _frac_pct(v):
    """A ratio in [0,1] as a percentage (resilience/win-rate style)."""
    if v is None:
        return "non misurato"
    try:
        return f"{round(float(v) * 100.0, 2)}%"
    except (TypeError, ValueError):
        return "non misurato"


def _trend(history: list | None) -> str:
    """A weekly trend arrow from a numeric history (up/down/flat), honestly."""
    nums = [h for h in (history or []) if isinstance(h, (int, float))]
    if len(nums) < 2:
        return "non misurato"
    if nums[-1] > nums[0]:
        return "in salita ^"
    if nums[-1] < nums[0]:
        return "in calo v"
    return "piatto -"


def _pick(st: dict, *keys):
    """First non-None value among ``keys`` (the diary and the report use aliases)."""
    for k in keys:
        v = st.get(k)
        if v is not None and v != "":
            return v
    return None


def _why(st: dict, key: str) -> str:
    """Why a field could not be measured (never a bare "non misurato")."""
    return (st.get("_why") or {}).get(key) or "il report non porta questo dato"


def _u(st: dict, key: str) -> str:
    """An unmeasured field, rendered WITH its reason (Law 10 on the bulletin)."""
    return f"non misurato (perche': {_why(st, key)})"


def _v(st: dict, key: str, *aliases, fmt=None):
    """A field's value, or an honest 'non misurato (perche': ...)' when absent."""
    val = _pick(st, key, *aliases)
    if val is None or val == "":
        return _u(st, key)
    return fmt(val) if fmt else val


def _stats_lines(st: dict) -> list[str]:
    kings_cmd = _pick(st, "kings_command")
    if kings_cmd is None and _pick(st, "kings") is not None:
        kings_cmd = f"{st['kings']} re in carica"

    # The win-rate line RECONCILES with the survivors/deaths (the CEO's check):
    # the portfolio figure is survivors/finalists, and the deaths are printed
    # beside it so a "best win rate" can never contradict "0 survivors".
    surv = _pick(st, "wr_survivors")
    fin = _pick(st, "wr_finalists")
    if surv is not None and fin:
        recon = f"riconciliazione: {surv}/{fin} finalisti sopravvissuti"
    else:
        recon = f"riconciliazione: {_u(st, 'wr_finalists')}"

    return [
        f"  - Win rate (migliore / portafoglio / trend sett.): "
        f"{_v(st, 'wr_best', fmt=_frac_pct)} / "
        f"{_v(st, 'wr_portfolio', fmt=_frac_pct)} / "
        f"{_v(st, 'wr_trend')}",
        f"      {recon}; morti {_v(st, 'wr_deaths')}",
        f"  - RR realizzato (min / medio / migliore): "
        f"{_v(st, 'rr_min')} / {_v(st, 'rr_avg', 'rr')} / {_v(st, 'rr_best')}",
        f"      RR obiettivo (legge, minimo 2.5): {_v(st, 'rr_target')} "
        f"-- {_v(st, 'ambition')}",
        f"  - Resilienza autopsia (migliore / portafoglio) [NON e' il win rate]: "
        f"{_v(st, 'res_best', fmt=_frac_pct)} / {_v(st, 'res_portfolio', fmt=_frac_pct)}",
        f"  - Profit Factor / expectancy per trade (netto): "
        f"{_v(st, 'profit_factor')} / {_v(st, 'expectancy_r')} R",
        f"  - Drawdown misurato / frazione deployabile: "
        f"{_v(st, 'dd_r')} R / {_v(st, 'deployable_pct', fmt=_pct)}",
        f"  - Volume: {_v(st, 'volume_worst_week')} trade distinti/sett. "
        f"(peggior finestra) vs legge {_f(st.get('volume_law', 5))}/sett. "
        f"-- divario {_v(st, 'volume_gap')}",
        f"  - Re dei regni: comanda {_f(kings_cmd)}; "
        f"cadono {_v(st, 'kings_fall')}; nati {_v(st, 'kings_born')}",
        f"  - Frizione (multiplo medio / distanza da 3x): "
        f"{_v(st, 'friction_avg', 'friction')} / {_v(st, 'friction_gap')}",
        f"  - Popolazione (vivi / pensionati / figli-del-re): "
        f"{_v(st, 'population')} / {_v(st, 'retired')} / {_v(st, 'king_children')}",
    ]


def _mean_pct(vals):
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def statistics_from(report: dict, *, volume=None, history=None,
                    friction_target: float = 3.0) -> dict:
    """The complete statistics block, read from the report (honest, never invented).

    The aggregation is wired to the RIGHT source field for each statistic. In
    particular (the CEO's audit, Law 10):

    * the RESILIENCE column is ``1 - fixable_deaths/trades`` (an autopsy share) --
      it is printed as "Resilienza autopsia", NEVER as a win rate;
    * the win rate is the realized share of winning trades -- ``win_rate`` when the
      report carries it, else the Wilson lower bound as a conservative proxy;
    * RR is the reward:risk target the genome TRADES (``target_rr``, >= 2.5 by
      law), never the mean net-R per trade (which is a completely different unit);
    * the portfolio win rate RECONCILES with survivors/deaths (survivors/finalists).

    Every field the report does not carry is left ``None`` so the page prints
    "non misurato (perche': ...)". ``_why`` records the reason per field.
    """
    r = report or {}
    lb = r.get("leaderboard") or []
    # Prefer the full finalist table (richer) when present, else the leaderboard.
    rows = r.get("final_population") or lb

    def _col(key):
        return [x.get(key) for x in rows
                if isinstance(x.get(key), (int, float))]

    # --- win rate: the realized share of winning trades. If the report does not
    # carry it, it is honestly UNMEASURED -- the autopsy resilience (a different
    # quantity) or the Wilson LB (a different quantity) must never stand in.
    wr = _col("win_rate") or _col("adv_win_rate")
    if wr:
        wr_best = round(max(wr), 4)
        wr_portfolio = _mean_pct(wr)
        wr_src = "win_rate"
    else:
        wr_best = None
        wr_portfolio = None
        wr_src = "non misurato"

    # --- resilience (autopsy share): kept SEPARATE from the win rate.
    res = _col("resilience") or _col("autopsy_resilience")
    res_best = round(max(res), 4) if res else None
    res_portfolio = _mean_pct(res)

    # --- RR: the reward:risk target the genome trades (>= 2.5 by law).
    rr = _col("target_rr")
    if rr:
        rr_min, rr_avg, rr_best = round(min(rr), 4), _mean_pct(rr), round(max(rr), 4)
    else:
        rr_min = rr_avg = rr_best = None

    # --- profit factor / expectancy / realized DD: THE FULL FEEDING. These read the
    # FINALISTS (the night's survivors) when the report carries them — the honest
    # portfolio figure the CEO asked for — and fall back to the wider ranked rows.
    # The per-trade expectancy is the pooled net R over the pooled trades (never a
    # genome total mislabelled as per-trade — the audit's warning).
    def _col2(key, rws):
        return [x.get(key) for x in rws if isinstance(x.get(key), (int, float))]

    frows = r.get("gauntlet")
    if not isinstance(frows, list) or not frows:
        frows = r.get("finalists") if isinstance(r.get("finalists"), list) else []
    pool = frows or rows

    pf = _col2("profit_factor", pool) or _col2("profit_factor", rows)
    if not pf:
        pf = [r.get("profit_factor")] if isinstance(r.get("profit_factor"), (int, float)) else []
    gp, gl = _col2("gross_profit_r", pool), _col2("gross_loss_r", pool)
    if gp and gl and sum(gl) > 0:
        pf = [sum(gp) / sum(gl)]  # pooled portfolio profit factor

    trades_col, net_col = _col2("trades", pool), _col2("net_r", pool)
    if trades_col and sum(trades_col) > 0:
        exp_r = [sum(net_col) / sum(trades_col)]
    else:
        exp_r = _col2("expectancy_r", pool) or _col("expectancy_r")

    # THE FULL FEEDING — the census' king-children (the birth register) ride in the
    # folded civilization block; read them so the population line is complete.
    _civ = r.get("civilization") if isinstance(r.get("civilization"), dict) else {}
    _census = _civ.get("census") if isinstance(_civ.get("census"), dict) else {}
    _diary = _civ.get("diary") if isinstance(_civ.get("diary"), dict) else {}
    king_children = (r.get("king_children") if isinstance(r.get("king_children"), int)
                     else _census.get("king_children"))
    born_n = (r.get("births") if isinstance(r.get("births"), int)
              else (len(_diary.get("births")) if isinstance(_diary.get("births"), list)
                    else None))

    md = r.get("measured_dd") or {}
    # THE FULL FEEDING — the deployable fraction is derivable from ANY measured DD
    # (charter act 6: ceiling/DD). The finalists' realized DD rides in measured_dd;
    # with no survivor, the per-row measured DD of the ranked candidates is the
    # measured source. The fraction is computed HERE from a real DD, never invented.
    _realized_dd = md.get("realized_dd_r")
    if _realized_dd is not None:
        _dd_for_fraction = _realized_dd
    else:
        _dd_col = _col("measured_dd_r")
        _dd_for_fraction = round(max(_dd_col), 4) if _dd_col else None
    if _realized_dd is not None:
        _deployable_pct = md.get("implied_deployable_pct")
    elif _dd_for_fraction:
        _deployable_pct = round(
            _charter.deployable_fraction(_dd_for_fraction) * 100.0, 2)
    else:
        _deployable_pct = None
    death = r.get("death_causes") or {}
    deaths = sum(int(v) for v in death.values()) if death else None
    survivors = r.get("majority_survivors")
    finalists = r.get("finalists")
    if isinstance(finalists, list):
        # The --out report carries the finalist TABLE; the committed STDOUT report
        # carries the finalist COUNT. Reduce either to the honest count, so the two
        # reports agree (Cure 3).
        finalists = len(finalists)
    elif finalists is None:
        finalists = len(r.get("gauntlet") or []) or len(lb) or None

    # --- volume law: prefer the report's own block, else the supplied entries.
    vlaw = r.get("volume_law") or {}
    if not vlaw and volume is not None:
        try:
            from app.state import volume_law as vl
            vlaw = vl.volume_law_status(volume)
        except Exception:  # noqa: BLE001
            vlaw = {}
    vworst = vlaw.get("worst_window_trades_per_week") if isinstance(vlaw, dict) else None

    fr = r.get("friction")
    if not isinstance(fr, (int, float)):
        fr = _mean_pct(_col("friction")) if _col("friction") else None
    # THE FULL FEEDING — R85's gross-to-friction gate arithmetic: pool the finalists'
    # paid multiples (gross edge per unit of friction) and report the mean + distance
    # from the sealed 3x bar. Read from the rows' own friction_breakdown; never invented.
    def _paid_multiple(row):
        fb = row.get("friction_breakdown")
        return fb.get("paid_multiple") if isinstance(fb, dict) else None

    if fr is None:
        paid = [_paid_multiple(x) for x in pool]
        paid = [p for p in paid if isinstance(p, (int, float))]
        if paid:
            fr = round(sum(paid) / len(paid), 4)

    amb = r.get("ambition") or {}
    rr_target = amb.get("current_target_rr") if isinstance(amb, dict) else None
    ambition_reading = amb.get("reading") if isinstance(amb, dict) else None

    kings = r.get("kings")
    if not isinstance(kings, int):
        kings = 2 if r else None  # the two kings are structural; absent report -> None

    out = {
        "wr_best": wr_best,
        "wr_portfolio": wr_portfolio,
        "wr_trend": _trend(history.get("win_rate") if isinstance(history, dict) else None),
        "wr_survivors": survivors,
        "wr_finalists": finalists,
        "wr_deaths": deaths,
        "wr_src": wr_src,
        "res_best": res_best,
        "res_portfolio": res_portfolio,
        "rr_min": rr_min,
        "rr_avg": rr_avg,
        "rr_best": rr_best,
        "rr_target": rr_target,
        "ambition": ambition_reading or "in cammino verso 1:6 (poi 1:30)",
        "profit_factor": (round(max(pf), 4) if pf else None),
        "expectancy_r": (round(sum(exp_r) / len(exp_r), 4) if exp_r else None),
        "dd_r": (md.get("realized_dd_r")
                 if md.get("realized_dd_r") is not None
                 else (round(max(_col("measured_dd_r")), 4)
                       if _col("measured_dd_r") else None)),
        "deployable_pct": _deployable_pct,
        "volume_worst_week": vworst,
        "volume_law": vlaw.get("law_trades_per_week", 5) if isinstance(vlaw, dict) else 5,
        "volume_gap": (round(5 - vworst, 3)
                       if isinstance(vworst, (int, float)) else None),
        "kings_command": (f"{kings} re in carica" if kings is not None else None),
        "kings_fall": deaths,
        "kings_born": r.get("births") if isinstance(r.get("births"), int) else None,
        "friction_avg": fr,
        "friction_gap": (round(friction_target - fr, 3)
                         if isinstance(fr, (int, float)) else None),
        "population": r.get("population"),
        "retired": death.get("apoptosis") if isinstance(death, dict) else None,
        "king_children": king_children,
        "kings_born": (born_n if isinstance(born_n, int) else None),
    }
    out["_why"] = _reasons(r, out, wr_src)
    return out


def _reasons(report: dict, out: dict, wr_src: str) -> dict:
    """The honest WHY for every field the report could not measure (Law 10)."""
    why = {
        "wr_portfolio": (None if out.get("wr_portfolio") is not None
                         else "il report non porta win_rate ne' wilson_lb"),
        "wr_best": (None if out.get("wr_best") is not None
                    else "il report non porta win_rate ne' wilson_lb"),
        "wr_trend": ("serve una serie storica di win_rate (>= 2 notti)"
                     if out.get("wr_trend") == "non misurato" else None),
        "wr_finalists": (None if out.get("wr_finalists") else
                         "il report non porta finalisti ne' gauntlet"),
        "wr_deaths": (None if out.get("wr_deaths") is not None else
                      "il report non porta death_causes"),
        "rr_min": (None if out.get("rr_min") is not None else
                   "il report non porta target_rr (il genoma non e' nel leaderboard)"),
        "rr_avg": (None if out.get("rr_avg") is not None else
                   "il report non porta target_rr"),
        "rr_best": (None if out.get("rr_best") is not None else
                    "il report non porta target_rr"),
        "rr_target": (None if out.get("rr_target") is not None else
                      "il report non porta ambition"),
        "profit_factor": (None if out.get("profit_factor") is not None else
                          "il report non porta profit_factor"),
        "expectancy_r": (None if out.get("expectancy_r") is not None else
                         "il report non porta net_r per riga"),
        "dd_r": (None if out.get("dd_r") is not None else
                 "measured_dd assente: nessun finalista sopravvissuto rende il DD indefinito"),
        "deployable_pct": (None if out.get("deployable_pct") is not None else
                           "misurato solo su un DD realizzato definito"),
        "volume_worst_week": (None if out.get("volume_worst_week") is not None else
                              "serve la lista delle operazioni eseguite (15 coppie)"),
        "volume_gap": (None if out.get("volume_gap") is not None else
                       "deriva dalla peggior finestra settimanale, non misurata"),
        "friction_avg": (None if out.get("friction_avg") is not None else
                         "il report non porta il multiplo di frizione"),
        "friction_gap": (None if out.get("friction_gap") is not None else
                         "deriva dalla frizione media, non misurata"),
        "king_children": (None if out.get("king_children") is not None else
                          "il censimento non traccia i figli-del-re"),
        "kings_born": (None if out.get("kings_born") is not None else
                       "il report non porta il conteggio delle nascite"),
    }
    if wr_src != "win_rate":
        why["wr_best"] = ("il report non porta win_rate (la resilienza di autopsia "
                          "non e' un win rate)")
        why["wr_portfolio"] = why["wr_best"]
    return {k: v for k, v in why.items() if v}


def build_bulletin_v3(report: dict, *, civilization: dict | None = None,
                      body: dict | None = None, queue: dict | None = None,
                      heart: dict | None = None, date: str = "",
                      history: dict | None = None) -> str:
    """Render the civilization's one-minute Italian page (bulletin v3)."""
    r = report or {}
    civ = civilization or {}
    d = civ.get("diary") if isinstance(civ.get("diary"), dict) else civ
    body = body or {}
    queue = queue or {}
    st = d.get("stats") or statistics_from(r, history=history)

    L: list[str] = []
    L.append("# APEX -- BOLLETTINO NOTTURNO (il diario della civilta')")
    if date:
        L.append(f"_Notte del {date} -- una lettura da un minuto._")
    L.append("")

    # STANOTTE
    death = r.get("death_causes") or {}
    deaths = sum(int(v) for v in death.values()) if isinstance(death, dict) else None
    survivors = r.get("majority_survivors")
    finalists = r.get("finalists")
    if isinstance(finalists, list):
        # The --out report carries the finalist TABLE; the committed STDOUT report
        # carries the finalist COUNT. Reduce either to the honest count, so the two
        # reports agree (Cure 3).
        finalists = len(finalists)
    elif finalists is None:
        finalists = len(r.get("gauntlet") or []) or None
    L.append("## STANOTTE")
    L.append(f"  - prove (trials)      : {_f(r.get('trials'))}")
    L.append(f"  - morti / sopravvissuti: {_f(deaths)} / {_f(survivors)} "
             f"(su {_f(finalists)} finalisti)")
    L.append(f"      riconciliazione: {_f(survivors)} sopravvissuti / "
             f"{_f(finalists)} finalisti; morti registrate {_f(deaths)}")
    L.append(f"  - catena cresciuta    : indice {_f(r.get('chain_index'))}")
    L.append(f"  - ore lavorate        : {_f(body.get('hours_worked'))}/24")
    L.append(f"  - lavori completati   : {_f(body.get('jobs_done'))}")
    # Cure 2 — the body's PROOF rides the page: the committed queue checkpoint's
    # own reading (depth, jobs drained, inter-job gap). Unmeasured stays honest.
    if queue:
        L.append(f"  - coda del corpo      : {_f(queue.get('reading'))}")
    L.append("")

    # LE STATISTICHE COMPLETE
    L.append("## LE STATISTICHE COMPLETE")
    L.extend(_stats_lines(st))
    L.append("")

    # COSA ABBIAMO IMPARATO
    L.append("## COSA ABBIAMO IMPARATO (E2)")
    learned = d.get("learned") or []
    if learned:
        for x in learned:
            L.append(f"  - {x}")
    else:
        L.append("  - non misurato")
    L.append("")

    # I GUARDIANI
    L.append("## I GUARDIANI")
    g = d.get("guardians") or {}
    cap = body.get("capacity") or {}
    L.append(f"  - macchina (risorse misurate): {_f(g.get('machine'))}")
    L.append(f"  - capacita' misurate          : {_f(cap.get('reading'))}")
    L.append(f"  - utilizzazione               : {_pct(body.get('util_pct'))} "
             f"(armi: {_f((body.get('concurrency') or {}).get('workers'))})")
    L.append(f"  - account                     : {_f(g.get('account'))}")
    L.append(f"  - termini                     : {_f(g.get('terms'))}")
    L.append("")

    # IL CONSIGLIO HA DECISO
    L.append("## IL CONSIGLIO HA DECISO")
    decisions = civ.get("decisions") or d.get("decisions") or []
    if decisions:
        for dec in decisions:
            L.append(f"  - {dec.get('what')}")
            L.append(f"      perche': {dec.get('why')}")
    else:
        L.append("  - nessuna decisione (niente da deliberare)")
    L.append("")

    # LA RETE HA DETTO
    L.append("## LA RETE HA DETTO")
    exchanges = d.get("exchanges") or []
    if exchanges:
        for e in exchanges:
            L.append(f"  - {e}")
    else:
        net = civ.get("network") or {}
        L.append(f"  - {_f(net.get('reading'))}")
    L.append("")

    # IL CUORE
    L.append("## IL CUORE")
    h = heart or {}
    L.append(f"  - VM / ore            : {_f(h.get('vm'))} / {_f(h.get('hours'))}")
    # ``heartbeat.json`` (the VM's real reading) carries no jobs/stalls/last_beat:
    # the completed work is the body's ``done``, the heartbeat is the reading's own
    # timestamp, and "stalls" is the queue's failed count. Read the REAL keys, with
    # the legacy names kept as fallbacks so an older page still renders.
    done = h.get("jobs", h.get("done"))
    L.append(f"  - lavori completati   : {_f(done)}")
    L.append(f"  - stalli              : {_f(h.get('stalls', h.get('failed')))}")
    L.append(f"  - ultimo battito      : {_f(h.get('last_beat', h.get('ts')))}")
    L.append("")

    # CURIOSITA' E SOGNI
    L.append("## CURIOSITA' E SOGNI")
    cur = civ.get("curiosity") or d.get("curiosity") or {}
    thin = cur.get("thinnest") or {}
    if thin:
        L.append(f"  - curiosita' (zona)   : {_f(thin.get('zone'))} -- "
                 f"{_f(thin.get('why'))}")
    else:
        L.append("  - curiosita'          : non misurato")
    dr = civ.get("dreams") or d.get("dreams") or {}
    born = dr.get("born_ideas") or []
    if born:
        for b in born:
            L.append(f"  - sogno               : {b.get('idea')}")
    else:
        L.append(f"  - sogni               : nessuno ({_f(dr.get('reading'))})")
    L.append("")

    # RICHIESTE AL CEO
    L.append("## RICHIESTE AL CEO")
    reqs = list(d.get("requests") or [])
    esc = (body.get("escalation") or {})
    if esc.get("propose"):
        reqs.append("potenziare il server a 4 OCPU / 24 GB (misurato: "
                    f"{esc.get('reading')})")
        reqs.extend("    " + s for s in (body.get("upgrade_steps") or []))
    if reqs:
        for x in reqs:
            L.append(f"  - {x}")
    else:
        L.append("  - niente da chiedere, capo")
    # Already-granted orders: consult the register, never re-ask the CEO.
    for x in (d.get("granted") or []):
        L.append(f"  - gia' autorizzato (direttiva del CEO): {x} -- non richiesto")
    L.append("")
    L.append("_Bollettino generato da un agente AI (OpenHands) per il CEO._")
    return "\n".join(L) + "\n"


def bulletin_filename(date: str) -> str:
    """``notte_YYYY-MM-DD.md`` from a date string (or today)."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(date or ""))
    if m:
        return f"notte_{m.group(1)}.md"
    from datetime import datetime, timezone
    return f"notte_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"


def bulletin_path(date: str, *, root: str = "..") -> str:
    """The committed location: ``APEX/bulletins/notte_YYYY-MM-DD.md``."""
    return f"{root}/bulletins/{bulletin_filename(date)}"
