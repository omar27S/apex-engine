"""THE MORNING LETTER -- the civilization's voice to the CEO (the bulletin, evolved).

The night bulletin was a diary: what happened. THE LETTER is a LETTER: the state
TALKS to the CEO in the first person, in plain Italian -- what happened, what it
MEANS, what we need, how much we improved, how close we are to the objective.

Its spine is THE FULL NUMBERS TABLE (the CEO's binding addendum): ONE simple,
complete, maximum table -- all the numbers at a glance -- in the EXACT order the
CEO fixed, so his eye learns where to look. The table sits at the TOP of the
Letter: numbers first, then the voice tells the story.

Absolute honesty: every cell is a TRUE number or an honest ``--`` with the reason
in a footnote line under the table. The writer never self-verifies: the
CONTROLLORE (an independent counter-agent, :mod:`app.civilization.controllore`)
reconciles the numbers against the raw artifacts and signs the table before the
CEO ever sees it.

Pure at import (Scar #6): the Letter is a reduction over the report + blocks the
caller hands it; the only I/O is the history helpers the caller invokes.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.civilization import bulletin as bl
from app.civilization import controllore as ctrl
from app.civilization import council as cou
from app.civilization import dragon as dragon_mod
from app.civilization import ticket as ticket_mod
from app.civilization.sage_presence import (CEO_NOTE_HEADER, DAWN_NOTE_HEADER,
                                            SPONTANEOUS_TAG)

__all__ = [
    "TABLE_METRICS",
    "letter_metrics",
    "full_numbers_table",
    "render_table",
    "build_morning_letter",
    "letter_filename",
    "letter_path",
    "load_history",
    "append_history",
    "prior_week_metrics",
]

# THE CEO'S TABLE (binding order). Each row: (label, key, unit, direction).
#   unit      -- how the value is rendered;
#   direction -- "up" (higher is better), "down" (lower is better), "flat" (no trend).
# The order is FROZEN: the CEO's eye memorizes the map.
TABLE_METRICS: tuple[tuple[str, str, str, str], ...] = (
    ("Win rate (migliore)", "wr_best", "frac", "up"),
    ("Win rate (portafoglio)", "wr_portfolio", "frac", "up"),
    ("RR minimo", "rr_min", "num", "up"),
    ("RR medio", "rr_avg", "num", "up"),
    ("RR migliore", "rr_best", "num", "up"),
    ("Posizione curva ambizione", "ambition_pos", "amb", "up"),
    ("Profit Factor", "profit_factor", "num", "up"),
    ("Expectancy per trade (netto)", "expectancy_r", "r", "up"),
    ("DD ricerca cumulato (R)", "dd_r", "r", "up"),
    ("Fraz. deployabile (8%/DD ric.)", "deployable_pct", "pct", "up"),
    ("Trade distinti/settimana", "volume_worst_week", "num", "up"),
    ("Distanza legge 5/settimana", "volume_gap", "num", "up"),
    ("Strategie net-positive", "net_positive_strategies", "int", "up"),
    ("Frizione media (x)", "friction_avg", "x", "flat"),
    ("Distanza dal 3x", "friction_gap", "num", "up"),
    ("Popolazione (vivi/morti/nati)", "population_trio", "trio", "flat"),
    ("Re in carica", "kings", "int", "flat"),
    ("Ore lavorate corpo (X/24)", "body_hours", "num", "up"),
    ("Utilizzazione macchina", "util_pct", "pct", "up"),
    ("Tick al secondo (falco)", "hawk_tps", "num", "up"),
    ("Fonti live attive", "live_sources", "int", "up"),
    ("Termometro Stato (0-100)", "thermometer", "int", "up"),
    ("Miglioramento settimanale", "weekly_improvement", "pts", "flat"),
    ("Distanza obiettivo (90% WR)", "distance_to_goal", "pct", "up"),
    ("E2: lezioni->cambiamenti", "e2_ratio", "ratio", "flat"),
    ("Richieste al CEO", "ceo_requests", "int", "flat"),
)

_GOAL_WR = 0.90  # the objective: 90% win rate


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _cell(value, unit) -> str | None:
    """Render a numeric value for its unit; None stays None (an honest ``--``)."""
    if value is None:
        return None
    try:
        if unit == "frac":
            # the stats block carries a fraction in [0,1]; render as a percentage.
            v = float(value)
            if 0.0 <= v <= 1.0:
                return f"{round(v * 100.0, 2)}%"
            return f"{round(v, 2)}%"
        if unit == "pct":
            return f"{round(float(value), 2)}%"
        if unit == "r":
            return f"{round(float(value), 2)}R"
        if unit == "x":
            return f"{round(float(value), 2)}x"
        if unit == "int":
            return f"{int(round(float(value)))}"
        if unit == "pts":
            s = f"{round(float(value), 1)}"
            return (s if s.startswith("-") else "+" + s) + " punti"
        if unit == "amb":
            return f"1:{round(float(value), 1)}"
        if unit == "ratio":
            return str(value)
        return f"{round(float(value), 2)}"
    except (TypeError, ValueError):
        return None


def _hawk_blind(hawk: dict) -> bool:
    """True when a hawk reading carries no real ticks (unmeasured or all-zero)."""
    h = hawk or {}
    tps = _num(h.get("ticks_per_second"))
    sources = _num(h.get("sources_active"))
    received = _num(h.get("ticks_received"))
    return (tps in (None, 0)) and (sources in (None, 0)) and (received in (None, 0))


def effective_hawk(hawk: dict | None, heart: dict | None) -> dict:
    """The falcon whose reading the Letter reports.

    THE VM FALCON (the hawk's night reporting fix): the night runs on GitHub Actions
    where the falcon cannot fly (no feed route), so its ``hawk_eye.json`` is honestly
    0 ticks. The VM's always-on hawk service holds the REAL velocity; the VM's shift
    publishes it in ``heart.json``. When the local reading is BLIND and the VM
    carries a real one, report the VM falcon -- tagged ``_source``. A CI zero with
    no VM reading stays an honest zero.
    """
    h = hawk or {}
    vm = (heart or {}).get("hawk_eye")
    if _hawk_blind(h) and isinstance(vm, dict) and not _hawk_blind(vm):
        merged = dict(vm)
        merged["_source"] = (heart or {}).get("source") or "vm"
        return merged
    return h


def letter_metrics(report: dict, *, civilization: dict | None = None,
                   body: dict | None = None, queue: dict | None = None,
                   heart: dict | None = None, thermometer: dict | None = None,
                   hawk: dict | None = None, requests: int | None = None,
                   net_positive: int | None = None,
                   births: int | None = None) -> dict[str, dict]:
    """Every table metric, read from the REAL blocks (honest, never invented).

    Returns ``{key: {"value": float|None, "text": str|None, "why": str|None}}``.
    A value the blocks cannot measure is left ``None`` with a ``why`` -- the table
    prints ``--`` and the footnote carries the reason.
    """
    r = report or {}
    civ = civilization or {}
    body = body or {}
    thermo = thermometer or {}
    hawk = effective_hawk(hawk, heart)
    d = civ.get("diary") if isinstance(civ.get("diary"), dict) else {}

    st = bl.statistics_from(r)
    # The diary's own measured stats win where the report is silent (same merge the
    # bulletin v3 does), so the Letter never prints a zero the cycle actually knew.
    for k, v in (d.get("stats") or {}).items():
        if v is not None and v != "":
            st[k] = v

    death = r.get("death_causes") or {}
    finalists = r.get("finalists")
    if isinstance(finalists, list):
        finalists = len(finalists)

    # win rate best/portfolio are fractions in the stats block.
    wr_best = _num(st.get("wr_best"))
    wr_port = _num(st.get("wr_portfolio"))

    # E2: lessons -> changes (registered / that changed behaviour).
    e2 = ((r.get("amendment") or {}).get("E2_failure_law") or {})
    e2_reg = _num(e2.get("failures_registered"))
    e2_chg = _num(e2.get("failures_that_changed_behaviour"))
    e2_text = (f"{int(e2_reg)}/{int(e2_chg)}"
               if e2_reg is not None and e2_chg is not None else None)
    e2_ratio = (round(e2_chg / e2_reg, 4)
                if e2_reg and e2_chg is not None else None)

    # population trio: alive / retired (apoptosis) / born.
    alive = _num(st.get("population"))
    retired = _num(st.get("retired"))
    born = _num(births) if births is not None else None
    if born is None:
        blist = d.get("births")
        born = len(blist) if isinstance(blist, list) else None
    trio_text = (f"{int(alive)}/{int(retired)}/{int(born)}"
                 if None not in (alive, retired, born) else None)

    # ambition curve position: 1 : current_target_rr.
    amb_rr = _num(st.get("rr_target"))

    # distance to the 90% win-rate objective (a percentage-point gap).
    dist = round((wr_best - _GOAL_WR) * 100.0, 2) if wr_best is not None else None

    # body + machine.
    hours = _num(body.get("hours_worked"))
    util = _num(body.get("util_pct"))

    # the hawk (live market) block, when the hub has written one.
    tps = _num(hawk.get("ticks_per_second"))
    sources = _num(hawk.get("sources_active"))

    kings = _num(st.get("kings")) or (2 if r else None)

    def M(value, unit, why, text=None):
        return {"value": value if isinstance(value, (int, float)) else None,
                "text": text if text is not None else _cell(value, unit),
                "why": None if (value is not None or text is not None) else why}

    # The controllore's INDEPENDENT reading (raw blocks, its own path) -- the
    # Letter is written from it, so the table starts reconciled by construction.
    indep = ctrl.independent_metrics(r, civilization=civ, body=body,
                                     thermometer=thermo)

    metrics = {
        "wr_best": M(indep["wr_best"], "frac", st.get("_why", {}).get("wr_best")
                     or "il report non porta win_rate"),
        "wr_portfolio": M(indep["wr_portfolio"], "frac",
                          st.get("_why", {}).get("wr_portfolio")
                          or "il report non porta win_rate"),
        "rr_min": M(indep["rr_min"], "num", st.get("_why", {}).get("rr_min")
                    or "il genoma non e' nel leaderboard"),
        "rr_avg": M(indep["rr_avg"], "num", st.get("_why", {}).get("rr_avg")
                    or "il report non porta target_rr"),
        "rr_best": M(indep["rr_best"], "num", st.get("_why", {}).get("rr_best")
                     or "il report non porta target_rr"),
        "ambition_pos": M(indep["ambition_pos"], "amb", "il report non porta ambition"),
        "profit_factor": M(indep["profit_factor"], "num",
                           st.get("_why", {}).get("profit_factor")
                           or "il report non porta profit_factor"),
        "expectancy_r": M(indep["expectancy_r"], "r",
                          st.get("_why", {}).get("expectancy_r")
                          or "il report non porta net_r per riga"),
        "dd_r": M(indep["dd_r"], "r", st.get("_why", {}).get("dd_r")
                  or "measured_dd assente"),
        "deployable_pct": M(indep["deployable_pct"], "pct",
                            st.get("_why", {}).get("deployable_pct")
                            or "serve un DD misurato (realizzato o dei candidati)"),
        "volume_worst_week": M(indep["volume_worst_week"], "num",
                               st.get("_why", {}).get("volume_worst_week")
                               or "serve la lista delle operazioni eseguite"),
        "volume_gap": M(indep["volume_gap"], "num",
                        st.get("_why", {}).get("volume_gap")
                        or "deriva dalla peggior finestra settimanale"),
        "net_positive_strategies": M(indep["net_positive_strategies"], "int",
                                     "il leaderboard non e' nel report"),
        "friction_avg": M(indep["friction_avg"], "x",
                          st.get("_why", {}).get("friction_avg")
                          or "il report non porta il multiplo di frizione"),
        "friction_gap": M(indep["friction_gap"], "num",
                          st.get("_why", {}).get("friction_gap")
                          or "deriva dalla frizione media"),
        "population_trio": M(None, "trio",
                             "il report non porta vivi/morti/nati",
                             text=indep["_population_trio"]),
        "kings": M(indep["kings"], "int", "nessun report: i re sono strutturali"),
        "body_hours": M(indep["body_hours"], "num",
                        "il corpo non ha misurato le ore lavorate"),
        "util_pct": M(indep["util_pct"], "pct",
                      "il corpo non ha misurato l'utilizzazione"),
        "hawk_tps": M(tps, "num", "il falco (quote hub) non ha ancora misurato la velocita'"),
        "live_sources": M(sources, "int", "il falco (quote hub) non ha ancora fonti attive"),
        "thermometer": M(indep["thermometer"], "int",
                         "il termometro non ha una lettura (nessun dato di stato)"),
        "weekly_improvement": M(None, "pts", "serve la lettura del termometro di 7 notti fa"),
        "distance_to_goal": M((round((indep["wr_best"] - _GOAL_WR) * 100.0, 2)
                               if indep["wr_best"] is not None else None), "pct",
                              "serve il win rate (migliore)"),
        "e2_ratio": M(indep["e2_ratio"], "ratio",
                      "il report non porta l'amendment E2", text=e2_text),
        # THE CONTINUOUS LIFE (Parts Two-Three): the collective pulse and the
        # engagement read from the cycle's LIFE block (honest: absent -> --).
        "pulse_rate": M(_life_pulse(civ), "num",
                        "il polso non e' stato misurato (nessun ciclo LIFE)"),
        "engagement": M(_life_engagement(civ), "frac",
                        "l'engagement non e' stato misurato (nessun ciclo LIFE)"),
        "ceo_requests": M(requests, "int", "nessuna lettera composta"),
    }
    return metrics


def _life_block(civ: dict) -> dict:
    """The cycle's LIFE block, from ``civ`` or its embedded ``diary`` (honest)."""
    return (civ or {}).get("life") or ((civ or {}).get("diary") or {}).get("life") or {}


def _life_pulse(civ: dict) -> float | None:
    v = (_life_block(civ).get("pulse") or {}).get("rate_per_hour")
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _life_engagement(civ: dict) -> float | None:
    v = (_life_block(civ).get("engagement") or {}).get("ratio")
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _trend_cell(key, unit, direction, today, prior) -> str:
    """The TREND arrow: ^ up is good, v down, = flat (^^ = big jump)."""
    if direction == "flat":
        return "="
    if not isinstance(today, (int, float)) or not isinstance(prior, (int, float)):
        return "--"
    delta = today - prior
    tol = {"frac": 0.005, "pct": 0.5, "num": 0.05, "r": 0.05, "x": 0.05, "int": 0.0,
           "pts": 0.0}.get(unit, 0.05)
    if abs(delta) <= tol:
        return "="
    good = (delta > 0) if direction == "up" else (delta < 0)
    arrow = "^" if good else "v"
    # a BIG jump (the value more than ~1.6x the prior, same sign) earns a double arrow.
    if isinstance(prior, (int, float)) and prior > 0 and today > 0:
        ratio = today / prior
        if (direction == "up" and ratio >= 1.6) or (direction == "down" and ratio <= 0.625):
            arrow += arrow
    return arrow


def full_numbers_table(metrics: dict[str, dict], *,
                       prior: dict[str, dict] | None = None) -> dict:
    """The complete table: one row per metric, always in the CEO's frozen order.

    Returns ``{"rows": [...], "footnotes": [...], "text": <markdown>}``. Every cell
    is a TRUE number or an honest ``--`` (with its reason in the footnotes).
    """
    prior = prior or {}
    rows: list[dict] = []
    footnotes: list[str] = []
    for label, key, unit, direction in TABLE_METRICS:
        m = metrics.get(key) or {}
        today_text = m.get("text")
        if today_text is None:
            today_text = "--"
            if m.get("why"):
                footnotes.append(f"{label}: {m['why']}")
        p = prior.get(key) or {}
        prior_text = p.get("text") if p.get("text") is not None else "--"
        trend = _trend_cell(key, unit, direction, m.get("value"), p.get("value"))
        rows.append({"metric": label, "key": key, "today": today_text,
                     "prior": prior_text, "trend": trend,
                     "today_value": m.get("value"), "prior_value": p.get("value")})
    return {"rows": rows, "footnotes": footnotes,
            "text": render_table(rows)}


def render_table(rows: list[dict]) -> str:
    """Render the rows as the CEO's fixed-width markdown table."""
    head = ("METRICA", "OGGI", "SETTIMA SCORSA", "TREND")
    w0 = max([len(head[0])] + [len(r["metric"]) for r in rows])
    w1 = max([len(head[1])] + [len(r["today"]) for r in rows])
    w2 = max([len(head[2])] + [len(r["prior"]) for r in rows])
    w3 = max([len(head[3])] + [len(r["trend"]) for r in rows])

    def line(a, b, c, d):
        return (f"| {a.ljust(w0)} | {b.ljust(w1)} | {c.ljust(w2)} | {d.ljust(w3)} |")

    sep = (f"|{'-' * (w0 + 2)}|{'-' * (w1 + 2)}|{'-' * (w2 + 2)}|{'-' * (w3 + 2)}|")
    out = [line(*head), sep]
    for r in rows:
        out.append(line(r["metric"], r["today"], r["prior"], r["trend"]))
    return "\n".join(out)


def _biggest_movers(table: dict, n: int = 2) -> list[tuple[str, str, str, str]]:
    """The rows with the biggest honest jump (label, today, prior, trend)."""
    movers = [r for r in table["rows"] if r["trend"] not in ("=", "--")]
    movers.sort(key=lambda r: (r["trend"].count("^") + r["trend"].count("v")),
                reverse=True)
    return [(r["metric"], r["today"], r["prior"], r["trend"]) for r in movers[:n]]


def _voice(report: dict, st: dict, table: dict, *, civilization, thermometer,
           history, date, corrections: int, sage_words: dict | None = None) -> list[str]:
    """The first-person letter: numbers first, then the voice tells the story."""
    r = report or {}
    civ = civilization or {}
    d = civ.get("diary") if isinstance(civ.get("diary"), dict) else {}
    thermo = thermometer or {}
    L: list[str] = []

    trials = r.get("trials")
    death = r.get("death_causes") or {}
    deaths = sum(int(v) for v in death.values()) if death else None
    surv = r.get("majority_survivors")

    L.append("## LA LETTERA DEL MATTINO")
    L.append("_La civilta' parla al CEO. Prima i numeri (sopra), poi la voce._")
    L.append("")

    # BOSS, STANOTTE...
    L.append("**Boss, stanotte...**")
    parts = []
    if trials is not None:
        parts.append(f"ho provato {trials} corpi")
    if deaths is not None:
        parts.append(f"ne ho sepolti {deaths} con l'autopsia in mano")
    if surv is not None:
        parts.append(f"{surv} hanno retto il tribunale")
    L.append("  " + (", ".join(parts) + "." if parts else
                     "non ho ancora un report da raccontare."))

    movers = _biggest_movers(table, n=2)
    for label, today, prior, trend in movers:
        if trend.startswith("^^") or trend.startswith("vv"):
            L.append(f"  Guarda la riga \"{label}\": da {prior} a {today} -- "
                     f"e' il salto piu' grosso della settimana.")
    L.append("")

    # LA SITUAZIONE
    L.append("**La situazione.**")
    wr = st.get("wr_best")
    if wr is not None:
        L.append(f"  Il miglior win rate e' {round(wr*100,2)}%: "
                 f"{'sopra' if wr >= _GOAL_WR else 'sotto'} l'obiettivo del 90%. "
                 f"Portafoglio {_pct(st.get('wr_portfolio'))}.")
    else:
        L.append("  Il win rate non e' misurato stanotte: la resilienza di autopsia "
                 "(una cosa diversa) e' l'unico segnale che ho.")
    vol = st.get("volume_worst_week")
    if vol is not None:
        L.append(f"  Volume: {vol} trade distinti/sett. nella peggior finestra; "
                 f"la legge ne chiede 5.")
    L.append("")

    # MI SERVE QUALCOSA?
    L.append("**Mi serve qualcosa?**")
    reqs = [x for x in (d.get("requests") or []) if not cou.request_is_granted(x)]
    granted = list(d.get("granted") or [])
    granted += [x for x in (d.get("requests") or [])
                if cou.request_is_granted(x) and x not in granted]
    if reqs:
        for x in reqs:
            L.append(f"  - {x}")
    else:
        L.append("  Niente, capo, procedo.")
    # The directive register's already-granted orders: recorded, never re-asked.
    for x in granted:
        L.append(f"  - gia' autorizzato (direttiva del CEO): {x} -- non richiesto")
    L.append("")

    # CI SIAMO MIGLIORATI?
    L.append("**Ci siamo migliorati?**")
    improved = [r_ for r_ in table["rows"]
                if r_["trend"] not in ("=", "--", "") and "v" not in r_["trend"]]
    worsened = [r_ for r_ in table["rows"]
                if "v" in r_["trend"]]
    if improved or worsened:
        for r_ in improved[:4]:
            L.append(f"  - {r_['metric']}: {r_['prior']} -> {r_['today']} ({r_['trend']})")
        for r_ in worsened[:3]:
            L.append(f"  - in calo: {r_['metric']}: {r_['prior']} -> {r_['today']} ({r_['trend']})")
    else:
        L.append("  Niente di confrontabile con la settimana scorsa, ancora.")
    L.append("")

    # QUANTO SIAMO VICINI ALL'OBIETTIVO?
    L.append("**Quanto siamo vicini all'obiettivo (90% WR / RR 1:6 / 5 trade-sett.)?**")
    if wr is not None:
        L.append(f"  Distanza dal 90% di win rate: {round((wr-_GOAL_WR)*100,2)} punti. "
                 f"Per chiudere il divario serve un'altra notte di corpi migliori, "
                 f"non una promessa.")
    else:
        L.append("  Non posso dire quanto sono vicino senza un win rate misurato.")
    L.append("")

    # LE CICATRICI (R121): the CEO reads the ORGANISM's own memory -- how many
    # wounds the body carries, each with its law and its tripwire -- and the
    # freshest words of the two youngest organs: what the historian healed
    # last night, and how well the forecaster knows itself. Fail-open by
    # law: a letter without scars still speaks its numbers.
    L.append("**Le cicatrici (che cosa ricorda il corpo).**")
    try:
        from app.factory.scars import census as _scar_census, load_scars as _load_scars
        _stats = _scar_census(_load_scars("scars.json"))
        L.append(f"  Porto {_stats['guarding']} ferite scritte nel registro "
                 f"({_stats['retired']} ritirate con onore): ogni ferita ha la "
                 f"sua legge e il suo allarme, e il guardiano le conta ogni "
                 f"giro. Chi dimentica le proprie ferite le guarisce due volte.")
    except Exception:
        pass
    try:
        _hh = json.loads(Path("history_health.json").read_text())
        _oldest = _hh.get("oldest_edge") or {}
        L.append(f"  Lo storico ha guarito {_hh.get('heals', 0)} pair "
                 f"({_hh.get('bars_healed', 0)} barre cucite); la memoria "
                 f"profonda finisce a {_oldest.get('age_h', '?')} ore fa "
                 f"(pair piu' vecchio: {_oldest.get('pair', '?')}).")
    except Exception:
        pass
    try:
        _rows = [json.loads(_x) for _x in
                 Path("factory_oath.jsonl").read_text().splitlines() if _x.strip()]
        _graded = [r for r in _rows if r.get("grade")]
        if _graded:
            _brier = _graded[-1]["grade"].get("mean_brier")
            L.append(f"  L'indovino ha votato se stesso: Brier {_brier} "
                     f"sulla notte passata (0 = profeta, 0.25 = moneta). "
                     f"Ieri non sapevo dire cosa avrei fatto; oggi lo dico "
                     f"in numeri, e i numeri si giudicano.")
    except Exception:
        pass
    L.append("")

    return L


def _pct(v):
    if not isinstance(v, (int, float)):
        return "non misurato"
    return f"{round(v*100,2)}%"


def build_morning_letter(report: dict, *, civilization: dict | None = None,
                         body: dict | None = None, queue: dict | None = None,
                         heart: dict | None = None, thermometer: dict | None = None,
                         history: dict | None = None, hawk: dict | None = None,
                         date: str = "", sage_words: dict | None = None) -> str:
    """Render THE LETTER: the full numbers table FIRST, then the voice."""
    r = report or {}
    civ = civilization or {}
    d = civ.get("diary") if isinstance(civ.get("diary"), dict) else {}

    # requests + net-positive strategies are read here so the table can carry them.
    # CONSULT THE DIRECTIVE REGISTER FIRST: a realm the CEO already authorized is
    # never re-asked, even if a stale committed civilization.json still carries the
    # old request (the CEO-request loop's safety net).
    reqs = [x for x in (d.get("requests") or []) if not cou.request_is_granted(x)]
    # keep the diary's recorded grants, and surface any legacy request the register
    # already covers so it is shown as authorized rather than asked again.
    granted_reqs = list(d.get("granted") or [])
    granted_reqs += [x for x in (d.get("requests") or [])
                     if cou.request_is_granted(x) and x not in granted_reqs]
    lb = r.get("leaderboard") or []
    net_pos = sum(1 for x in lb
                  if isinstance(x.get("adv_net_r", x.get("net_r")), (int, float))
                  and x.get("adv_net_r", x.get("net_r")) > 0) if lb else None

    metrics = letter_metrics(r, civilization=civ, body=body, queue=queue,
                             heart=heart, thermometer=thermometer, hawk=hawk,
                             requests=len(reqs), net_positive=net_pos)
    prior = prior_week_metrics(history, date)
    table = full_numbers_table(metrics, prior=prior)

    # weekly improvement: the thermometer delta vs the prior week (honest).
    t_now = metrics.get("thermometer", {}).get("value")
    t_prior = (prior.get("thermometer") or {}).get("value")
    if isinstance(t_now, (int, float)) and isinstance(t_prior, (int, float)):
        metrics["weekly_improvement"] = {
            "value": round(t_now - t_prior, 1),
            "text": _cell(t_now - t_prior, "pts"), "why": None}
        # re-render the row with the now-measured value.
        for row in table["rows"]:
            if row["key"] == "weekly_improvement":
                row["today"] = metrics["weekly_improvement"]["text"]
                row["today_value"] = metrics["weekly_improvement"]["value"]
        table["text"] = render_table(table["rows"])

    # THE CONTROLLORE verifies the table against the raw artifacts, number by number.
    verdict = ctrl.verify(table=table, metrics=metrics, report=r, civilization=civ,
                          body=body, queue=queue, thermometer=thermometer)
    # The controllore's independent value WINS: correct the Letter before the CEO
    # ever sees it (the writer never self-verifies).
    if verdict.get("corrections"):
        ctrl.apply_corrections(table, metrics, verdict)
        table["text"] = render_table(table["rows"])
        verdict["signature"] = ctrl.signature_line(verdict)

    st = bl.statistics_from(r)
    for k, v in (d.get("stats") or {}).items():
        if v is not None and v != "":
            st[k] = v

    L: list[str] = []
    L.append("# APEX -- LA LETTERA DEL MATTINO")
    if date:
        L.append(f"_Al CEO, dal suo stato -- la notte del {date}._")
    L.append("")

    # 1) THE FULL NUMBERS TABLE FIRST.
    L.append("## I NUMERI (tutti, a colpo d'occhio)")
    L.append("")
    L.append(table["text"])
    L.append("")
    if table["footnotes"]:
        L.append("_Note sotto la tabella (celle '--'):_")
        for f in table["footnotes"]:
            L.append(f"- {f}")
        L.append("")
    L.append(ctrl.signature_line(verdict))
    L.append("")

    # 1b) THE DRAGON'S ANALYSIS (Role 5): the strongest mind's first-person
    #     reflection on the day, rendered AT THE TOP (the CEO reads it with his
    #     coffee). It may CHALLENGE the CEO -- rendered in full, never softened.
    dg = (civ.get("dragon") or (civ.get("diary") or {}).get("dragon") or {})
    dan = dg.get("analysis") or {}
    if dan.get("text"):
        L.append(f"## {dragon_mod.analysis_header()}")
        L.append("")
        L.append(f"_{dan['text']}_")
        L.append("")

    # 2) THE VOICE.
    L.extend(_voice(r, st, table, civilization=civ, thermometer=thermometer,
                    history=history, date=date,
                    corrections=len(verdict.get("discrepancies") or []),
                    sage_words=sage_words))

    # 3) THE FULL STATISTICS (the bulletin's honest block, kept verbatim).
    L.append("## LE STATISTICHE COMPLETE")
    L.extend(bl._stats_lines(st))
    L.append("")

    # 4) THE STATE THERMOMETER with its breakdown.
    L.append("**Il termometro dello stato.**")
    L.append(f"  Indice di salute: {thermo_line(thermometer)}")
    for b in (thermometer or {}).get("breakdown") or []:
        L.append(f"    - {b['axis']}: {b['value']} (peso {b['weight']})")
    L.append("")

    # 4b) THE FALCON (the live market eye). The night computes on GitHub, where the
    # falcon cannot fly; when the VM published a real reading, it is reported here
    # and its source is named, so the CEO knows whose falcon it is.
    hawk_eff = effective_hawk(hawk, heart)
    if hawk_eff:
        src = hawk_eff.get("_source")
        src_note = (f" -- dal {src}" if src else "")
        L.append("**Il falco (occhio sul mercato).**")
        L.append(f"  - {hawk_eff.get('reading') or 'nessuna lettura'}{src_note}")
        L.append("")

    # 5) THE NETWORK SAID (the tongue's best exchanges, translated to Italian).
    L.append("**La rete ha detto.**")
    exchanges = d.get("exchanges") or []
    tongue_ex = (civ.get("tongue") or {}).get("exchanges") or []
    if tongue_ex:
        from app.civilization import tongue as _tg
        for u in tongue_ex[:6]:
            L.append(f"  - {_tg.translate(u)}")
    elif exchanges:
        for e in exchanges:
            L.append(f"  - {e}")
    else:
        L.append("  - silenzio saggio: nessuno ha cambiato il lavoro di un altro.")
    L.append("")

    # 5b) LA SALUTE DELLA RETE (D5): the CEO reads whether the civilization is
    #     actually TALKING -- how many questions got an answer, which ones are still
    #     open (the dead channel, measured), the response depth, and whether a
    #     collapsed diversity of opinion triggered a devil's advocate. Honest: an
    #     unmeasured conversation is reported as such, never as "healthy".
    conv = (civ.get("conversation") or (civ.get("diary") or {}).get("conversation")
            or {})
    if conv:
        L.append("**La salute della rete.**")
        sent = conv.get("by_kind") or {}
        if sent:
            L.append("  - messaggi per tipo: " +
                     ", ".join(f"{k} {v}" for k, v in sent.items()))
        q = conv.get("questions")
        ans = conv.get("answered")
        if q is not None:
            L.append(f"  - domande {q}, con risposta {ans if ans is not None else 'non misurato'}")
        open_q = conv.get("unanswered") or []
        if open_q:
            L.append(f"  - senza risposta: {len(open_q)} "
                     f"(es. \"{open_q[0].get('body')}\")")
        elif (conv.get("answered") or 0) > 0:
            L.append(f"  - tutte le domande hanno risposta ({conv.get('answered')}) "
                     f"-- la rete risponde.")
        else:
            L.append("  - nessuna domanda senza risposta: la rete risponde.")
        echo = conv.get("echo") or {}
        if echo.get("alarm"):
            L.append(f"  - ALLARME ECO: accordo {echo.get('agreement')} su "
                     f"{echo.get('voices')} voci -- devils advocate assegnato.")
        L.append("")

    # 5c) IL CERIMONIALE DELIBERANTE (D2): how the question was deliberated -- the
    #     tension (only when real), and the MINORITIES that did not prevail.
    delib = (civ.get("deliberation") or (civ.get("diary") or {}).get("deliberation")
             or {})
    if delib:
        L.append("**Il cerimoniale deliberante.**")
        L.append(f"  - domanda: {delib.get('opening')}")
        if delib.get("conflict"):
            t = delib.get("tension") or {}
            L.append(f"  - tensione: a favore {t.get('for')}, contro {t.get('against')}")
        else:
            L.append("  - nessun conflitto: la deliberazione era concorde.")
        if delib.get("minorities"):
            L.append(f"  - minoranze (non prevalsero): {delib.get('minorities')}")
        L.append(f"  - esito: {delib.get('resolution')}")
        L.append("")

    # 5d) IL DIALOGO TRA GENERAZIONI (D3): the newborns put real questions to the
    #     retired minds and the ancestors with a recorded lesson answer (office hours).
    anc = (civ.get("ancestry") or (civ.get("diary") or {}).get("ancestry") or [])
    if anc:
        L.append("**Il dialogo tra generazioni.**")
        for a in anc:
            L.append(f"  - {a.get('newborn')}: {a.get('reading')}")
        L.append("")

    # 5e) COSA ABBIAMO VISTO (THE GAZE): the night's key SIGHTINGS -- the shapes the
    #     eyes recognised, the patrol findings, the flow-born intuitions. The CEO
    #     reads what the civilization SAW, not only what it computed.
    gz = (civ.get("gaze") or (civ.get("diary") or {}).get("gaze") or {})
    if gz:
        L.append("**Cosa abbiamo visto.**")
        L.append(f"  - {gz.get('reading')}")
        rec = gz.get("recognition") or {}
        if rec.get("recognised"):
            L.append(f"  - forma riconosciuta: {rec.get('reading')}")
        elif rec.get("reading"):
            L.append(f"  - {rec.get('reading')}")
        if gz.get("deja_vu"):
            L.append(f"  - deja-vu: {gz['deja_vu'].get('reading')}")
        sight = gz.get("sightings") or []
        vedo = [s for s in sight if s.get("mode") == "VEDO"]
        flow = [s for s in sight if s.get("mode") == "FLOW"]
        if vedo:
            L.append(f"  - vedute (VEDO): {len(vedo)}")
            for s in vedo[:4]:
                L.append(f"      * {s.get('what')}")
        if flow:
            for s in flow[:2]:
                L.append(f"  - {s.get('what')}")
        L.append(f"  - {gz.get('patrol')}")
        rep = gz.get("report") or {}
        L.append(f"  - memoria visiva: {rep.get('library_shapes')} forme, "
                 f"{rep.get('archived_scenes')} scene, "
                 f"{rep.get('flow_intuitions')} intuizioni dal flow")
        if gz.get("ascii"):
            L.append(f"  - cio' che gli occhi hanno visto ({gz.get('pair')}):")
            for line in str(gz["ascii"]).splitlines():
                L.append(f"      {line}")
        L.append("")

    # 5f) LA GIORNATA (Part Five): the circadian phase — the day's real breath.
    lf = (civ.get("life") or (civ.get("diary") or {}).get("life") or {})
    if lf.get("circadian"):
        L.append("**La giornata.**")
        L.append(f"  - {lf['circadian'].get('reading')}")
        L.append("")

    # 5g) IL POLSO (Part Three): the collective pulse, its trend, and the engagement.
    if lf.get("pulse"):
        L.append("**Il polso.**")
        L.append(f"  - {lf['pulse'].get('reading')}")
        if lf.get("pulse_trend"):
            L.append(f"  - {lf['pulse_trend'].get('reading')}")
        if lf.get("engagement"):
            L.append(f"  - {lf['engagement'].get('reading')}")
        if lf.get("balance"):
            L.append(f"  - {lf['balance'].get('reading')}")
        if lf.get("vital_signs"):
            L.append(f"  - {lf['vital_signs'].get('reading')}")
        L.append("")

    # 5h) IL SAGGIO HA PARLATO (Part Four): the Sage's insights, always visible.
    sg = (civ.get("sage") or (civ.get("diary") or {}).get("sage") or {})
    if sg or (sage_words and (sage_words.get("answer") or sage_words.get("error"))):
        L.append("**Il Saggio ha parlato.**")
        # THE DAWN NOTE (THE FULL VOICE): the first thing the Council reads.
        dawn = sg.get("dawn") or {}
        if dawn.get("text"):
            L.append(f"  - {DAWN_NOTE_HEADER}: {dawn['text']}")
        elif dawn.get("error"):
            L.append(f"  - la Nota dell'Alba tace: {dawn['error']}")
        if sage_words and sage_words.get("answer"):
            L.append(f"  - IL SAGGIO HA PARLATO (prima consultazione, "
                     f"{sage_words.get('model')}): {sage_words['answer']}")
        elif sage_words and sage_words.get("error"):
            L.append(f"  - il Saggio tace: {sage_words['error']}")
        if sg:
            L.append(f"  - {sg.get('reading')}")
            for ins in (sg.get("insights") or [])[:6]:
                tag = " [SPONTANEO]" if ins.get("tag") == SPONTANEOUS_TAG else ""
                L.append(f"    - [{ins.get('kind')}]{tag} {ins.get('text')}")
        # THE PRESENCE (Part Two/Four): the live alerts, the spontaneous voice, the
        # cost of wisdom, the hit-rate, the CEO note, the Council question.
        pres = sg.get("presence") or {}
        alerts = (pres.get("alerts") or [])
        if alerts:
            L.append("  - ALLARMI DEL SAGGIO (vede in tempo reale):")
            for a in alerts[:5]:
                L.append(f"    - [{a.get('kind')}] {a.get('text')}")
        sp = (pres.get("spontaneous") or {})
        if sp.get("insight"):
            L.append(f"  - VOCE SPONTANEA (SPONTANEO): {sp['insight'].get('text')}")
        note = (pres.get("ceo_notes") or [])
        if note:
            L.append(f"  - {CEO_NOTE_HEADER}: {note[-1].get('text')}")
        qs = (pres.get("council_questions") or [])
        if qs:
            L.append(f"  - DOMANDA AL CONSIGLIO: {qs[-1].get('question')}")
        acc = (pres.get("accountability") or {})
        cost = (pres.get("cost") or {})
        if acc.get("reading") or cost.get("reading"):
            L.append(f"  - accountability: {acc.get('reading')}; "
                     f"peso {pres.get('reliability_discount')}")
        if cost.get("reading"):
            # THE COST OF WISDOM (the CEO's order): the split -- what the cheap Flash
            # head cost (N consultations) and what the one Pro session cost -- so the
            # CEO always sees what wisdom costs. Honest: a month with no Pro call says
            # "Pro $0.00 (0 consultazioni)", never a hidden charge.
            L.append(f"  - {cost.get('reading')}")
        L.append("")

    # 5h-bis) IL DRAGO (the dominant intelligence): its perpetual thought, its
    #     directed research, its JUDGMENTS (the dissent rendered in FULL), its
    #     architectural proposals, the training it gave, and its measured hit-rate.
    dg = dg or (civ.get("dragon") or (civ.get("diary") or {}).get("dragon") or {})
    if dg:
        L.append("**Il Drago (la mente piu' forte).**")
        L.append(f"  - {dg.get('reading')}")
        th = dg.get("last_thought") or {}
        if th.get("text"):
            L.append(f"  - {dragon_mod.DRAGON_MODE}: {th['text']}")
        hyps = dg.get("hypotheses") or []
        if hyps:
            L.append("  - IPOTESI DIRETTE (la ricerca e' AIMED, non cieca):")
            for h in hyps[:6]:
                L.append(f"    - muta {h.get('family')} {h.get('direction')} "
                         f"({h.get('gene')}): {h.get('reason')}")
        dis = dg.get("dissents") or []
        for j in dis[:3]:
            L.append(f"  - IL DRAGO DISSIENTE ({j.get('kind')}: {j.get('what')}): "
                     f"{j.get('reasoning')}")
        props = dg.get("proposals") or []
        for p in props[:3]:
            L.append(f"  - {p.get('header')} (-> {p.get('route')}): "
                     f"{p.get('title')} -- {p.get('change')}")
        tr = dg.get("training") or []
        for t in tr[:3]:
            L.append(f"  - FORMAZIONE ({t.get('agent')}): {t.get('feedback')}")
        acc = dg.get("accountability") or {}
        if acc.get("reading"):
            L.append(f"  - accountability: {acc.get('reading')}")
        cost = dg.get("cost") or {}
        if cost.get("reading"):
            L.append(f"  - {cost.get('reading')}")
        L.append("")

    # 5h-ter) IL FALCO ELEVATO (THE PERPETUAL MOTION, Part One): the navigator -- its
    #     multiple eyes, the live MACRO RADAR (DXY/WTI/US10Y/VIX), the regime flags,
    #     the pair selection, the sirens, and the orderflow reading. Honest: an
    #     unmeasured source is "dorme", an unmeasured regime is "--".
    fc = (civ.get("falcon") or (civ.get("diary") or {}).get("falcon") or {})
    if fc:
        L.append("**Il falco (il navigatore).**")
        L.append(f"  - {fc.get('reading')}")
        radar = fc.get("macro") or {}
        if radar.get("rows"):
            seen = [r for r in radar["rows"] if r.get("seen")]
            if seen:
                L.append("  - RADAR MACRO (visto in tempo reale): " +
                         ", ".join(f"{r['name']} {r['value']}" for r in seen))
            else:
                L.append("  - radar macro: non visto (nessuno strumento risponde)")
        if fc.get("regimes"):
            L.append("  - regimi: " +
                     ", ".join(f"{k} {v}" for k, v in fc["regimes"].items() if v)
                     + (f", non misurati {fc.get('regime_unmeasured')}"
                        if fc.get("regime_unmeasured") else ""))
        if fc.get("diary"):
            for e in fc["diary"]:
                if e.get("spoken"):
                    L.append(f"  - DIARIO DEL MERCATO ({e.get('day')}): {e.get('text')}")
        L.append("")

    # 5h-quater) LA GUARDIA WEB (THE PERPETUAL MOTION, Part Two): the standing watch,
    #     the news pulse ("il mondo dice"), the event horizon alert, and the social ear
    #     with its contrarian flag. All CONTEXT (Law 9): it informs, never trades.
    ww = (civ.get("web_watch") or (civ.get("diary") or {}).get("web_watch") or {})
    if ww:
        L.append("**La guardia web (gli occhi fuori).**")
        L.append(f"  - {ww.get('reading')}")
        if ww.get("pulse"):
            L.append(f"  - il mondo dice: {ww['pulse']}")
        al = ww.get("alert")
        if al:
            L.append(f"  - {al.get('reading')}")
        cf = ww.get("contrarian")
        if cf:
            L.append(f"  - {cf.get('reading')}")
        ear = ww.get("ear") or {}
        if ear.get("measured"):
            L.append(f"  - orecchio sociale: paura/avidita {ear.get('fear_greed')}, "
                     f"reddit {ear.get('reddit_posts')}, "
                     f"stocktwits +{ear.get('stocktwits_bullish')}/-{ear.get('stocktwits_bearish')}")
        L.append("")

    # 5h-quinquies) IL TUBO (THE PERPETUAL MOTION, Part Three): the unified state
    #     artifact's vital signs and the HEARTBEAT. If the heartbeat is missing the
    #     Letter says so LOUDLY -- never a silent false zero.
    pb = (civ.get("pipe") or (civ.get("diary") or {}).get("pipe") or {})
    if pb:
        L.append("**Il tubo (VM-GitHub).**")
        art = pb.get("artifact") or {}
        L.append(f"  - stato unificato: ore macchina {art.get('machine_hours')}, "
                 f"coda {art.get('queue_depth')}, "
                 f"tornei {art.get('tournaments_today')}, "
                 f"sopravvissuti {art.get('survivors_today')}")
        hb = pb.get("heartbeat") or {}
        if hb.get("reading"):
            L.append(f"  - {hb.get('reading')}")
        fl = (civ.get("flow") or (civ.get("diary") or {}).get("flow") or {})
        if fl.get("today"):
            L.append(f"  - {fl['today'].get('reading')}")
        L.append("")

    # 5h-sexies) LA PELLE DEL GIORNO (THE FIRST ASCENSION, Jump 4): the regime shifts
    #     and the reconfigurations -- the system changes skin when the market does.
    rg = (civ.get("regime") or (civ.get("diary") or {}).get("regime") or {})
    if rg:
        L.append("**La pelle del giorno (i cambi di regime).**")
        shifts = rg.get("shifts") or []
        if shifts:
            for s in shifts[:6]:
                L.append(f"  - {s.get('reading')}")
            for a in (rg.get("applied") or [])[:6]:
                L.append(f"  - {a.get('reading')}")
        else:
            L.append("  - nessun cambio di regime misurato questa ora.")
        m = rg.get("map") or {}
        if m.get("reading"):
            L.append(f"  - {m['reading']}")
        if rg.get("alarm"):
            L.append(f"  - {rg['alarm'].get('reading')}")
        L.append("")

    # 5h-septies) IL PRESENTE GIUDICA (THE FIRST ASCENSION, Jump 3): the live scores of
    #     the enrolled strategies, the biggest stale strategies, and the divergence
    #     between history and the present -- the present is the judge.
    ftb = (civ.get("forward_test") or (civ.get("diary") or {}).get("forward_test") or {})
    if ftb:
        L.append("**Il presente giudica (i punteggi dal vivo).**")
        L.append(f"  - {ftb.get('reading')}")
        for r in (ftb.get("top") or [])[:5]:
            L.append(f"  - {r.get('strategy')}: doppio {r.get('dual')}, "
                     f"storico {r.get('backtest')}, presente {r.get('live')}"
                     + (" [STALE]" if r.get("stale") else ""))
        for s in (ftb.get("stale") or [])[:5]:
            L.append(f"  - STALE {s.get('strategy')}: storico {s.get('backtest')} "
                     f"ma presente {s.get('live')} -- il mercato e' andato oltre")
        L.append("")

    # 5h-octies) LO STRESS-TEST (THE FIRST ASCENSION, Jump 6): the present vulnerability
    #     profile -- flash crash, spread explosion, news shock -- and any survival alarm.
    sb = (civ.get("stress_test") or (civ.get("diary") or {}).get("stress_test") or {})
    if sb:
        L.append("**Lo stress-test (la vulnerabilita' del presente).**")
        L.append(f"  - {sb.get('reading')}")
        led = sb.get("ledger") or {}
        for sc in (led.get("scenarios") or []):
            L.append(f"  - {sc.get('reading')}")
        obs = led.get("observed") or {}
        if obs.get("reading"):
            L.append(f"  - {obs.get('reading')}")
        if sb.get("alarm"):
            L.append(f"  - {sb['alarm'].get('reading')}")
        L.append("")

    # 5h-nonies) THE SECOND ASCENSION (Jumps 1/2/5): the Dragon's continuous mind,
    #     the collective model (the shared belief + the coherence metric), and the
    #     civilization's autobiography (today's chapter). Each block is skipped when
    #     unmeasured -- an empty mind, an unmeasured coherence, no chapter yet.
    mb = (civ.get("dragon") or (civ.get("diary") or {}).get("dragon") or {}).get("mind")
    if mb and mb.get("measured"):
        L.append("**La mente continua del Drago (non si azzera mai).**")
        L.append(f"  - {mb.get('reading')}")
        th = mb.get("theory") or {}
        if th:
            L.append(f"  - teoria della caccia v{th.get('version')}: {th.get('thesis')}")
        L.append("")

    cb = civ.get("collective") or (civ.get("diary") or {}).get("collective") or {}
    if cb and cb.get("measured"):
        L.append("**Il modello collettivo (da esercito a organismo).**")
        L.append(f"  - {cb.get('reading')}")
        for row in (cb.get("belief_map", {}).get("rows") or [])[:6]:
            if row.get("regime"):
                L.append(f"  - la collettivita' crede {row.get('pair')} "
                         f"{row.get('regime')} (confidenza {row.get('confidence')}, "
                         f"supporto {row.get('support')})")
        L.append("")

    ab = civ.get("autobiography") or (civ.get("diary") or {}).get("autobiography") or {}
    if ab and ab.get("measured"):
        L.append("**L'autobiografia (la storia che scriviamo).**")
        L.append(f"  - {ab.get('reading')}")
        L.append("")

    # 5h-decies) LA CACCIA (THE REAL HUNT, Part Six): the PREDATOR at work -- the
    #     Cathedral's seven columns (the gate class + the missing column NAMED), the
    #     three hunters' results, the Red Council's attack and any trade ticket with
    #     its full WHY. Each sub-block is skipped when unmeasured.
    cat = civ.get("cathedral") or (civ.get("diary") or {}).get("cathedral") or {}
    if cat and cat.get("measured"):
        g = cat.get("gate") or {}
        L.append("**LA CACCIA -- la Cattedrale di confluenza.**")
        L.append(f"  - {cat.get('reading')}")
        for col in (cat.get("columns") or []):
            mark = ("OK" if col.get("confirmed") is True
                    else ("--" if not col.get("measured") else "NO"))
            L.append(f"    - {col.get('column')}: {mark} -- {col.get('detail')}")
        if g.get("missing"):
            L.append(f"  - manca: {g['missing'][0].get('column')} "
                     f"({g['missing'][0].get('reason')})")
        L.append("")

    # 5h-undeci) LA CATTEDRALE HA VALUTATO N OPPORTUNITA' (Mega Phase 1, A4): the
    #     civilization's FIRST ACT -- the surviving strategies asked the LIVE market
    #     "would you enter RIGHT NOW?" for every operational pair, and the Cathedral
    #     judged each candidate. Honest: only real candidates are counted.
    sgen = civ.get("signal_generation") or {}
    if sgen and sgen.get("n_candidates") is not None:
        n_cand = int(sgen.get("n_candidates") or 0)
        n_acc = int(sgen.get("n_accepted") or 0)
        L.append(f"**LA CATTEDRALE HA VALUTATO {n_cand} opportunita'** "
                 f"(dal vivo; {n_acc} accettate).")
        for c in (sgen.get("candidates") or [])[:6]:
            dirn = "long" if c.get("direction") == 1 else "short"
            L.append(f"    - {c.get('pair')} {dirn} [{c.get('family')}]: "
                     f"ingresso {c.get('entry_price')} "
                     f"(stop {c.get('stop_distance')}, tp {c.get('target_distance')})")
        L.append("")

    # 5h-duodeci) L'ARSENALE COMPLETO (Mega Phase 2): every remaining lever activated --
    #     the world cloner, the modular army, self-play, the ML families, the echo state
    #     network, the diplomat, the anima, the Grok sensor, the Kelly sizing, and the
    #     second (local) sage. Each line is honest: an unmeasured lever says so.
    arsenal = civ.get("full_arsenal") or (civ.get("diary") or {}).get("full_arsenal") or {}
    lv = arsenal.get("levers") or {}
    if arsenal:
        L.append(f"**L'ARSENALE COMPLETO** -- {arsenal.get('reading', '')}")
        wc = lv.get("world_cloner") or {}
        if wc:
            L.append(f"  - clonatore di mondi (Lever 14): {wc.get('reading')}")
        ma = lv.get("modular_army") or {}
        if ma:
            L.append(f"  - esercito modulare (Lever 11): {ma.get('reading')}")
        sp = lv.get("self_play") or {}
        if sp:
            L.append(f"  - self-play (Lever 18): {sp.get('reading')}")
        ml = lv.get("ml_families") or {}
        if ml:
            L.append(f"  - famiglie ML (Lever 4): {ml.get('reading')}")
        esn = lv.get("echo_network") or {}
        if esn:
            L.append(f"  - echo state network (Lever 22): {esn.get('reading')}")
            rec = esn.get("recognition") or {}
            if rec.get("measured"):
                L.append(f"      {rec.get('reading')}")
        dip = lv.get("diplomat") or {}
        if dip:
            L.append(f"  - {dip.get('reading')}")
        anima = lv.get("anima") or {}
        if anima:
            L.append(f"  - anima (Lever 17): {anima.get('reading')}")
            cp = (anima.get("cross_pair") or {})
            if cp.get("measured"):
                L.append(f"      trasferimento tra coppie: {cp.get('reading')}")
        grok = lv.get("grok_sensor") or {}
        if grok:
            L.append(f"  - sensore Grok (X): {grok.get('reading')}")
            pulse = (grok.get("pulse") or {})
            if pulse.get("breaking"):
                L.append(f"      {pulse.get('reading')}")
        kelly = lv.get("kelly") or {}
        if kelly:
            L.append(f"  - Kelly / anti-rovina: {kelly.get('reading')}")
        lsage = lv.get("local_sage") or {}
        if lsage:
            L.append(f"  - Saggio: {lsage.get('reading')}")
        L.append("")

    hb = civ.get("hunters") or (civ.get("diary") or {}).get("hunters") or {}
    if hb and (hb.get("fired") or hb.get("prepared")):
        L.append("**I cacciatori.**")
        L.append(f"  - {hb.get('reading')}")
        for h in (hb.get("hunters") or []):
            if h.get("fire") or h.get("prepare"):
                L.append(f"    - caccia {h.get('hunter')}: {h.get('reading')}")
        L.append("")

    rcb = civ.get("red_council") or (civ.get("diary") or {}).get("red_council") or {}
    if rcb and rcb.get("measured"):
        L.append("**Il Consiglio Rosso (l'antifragilita').**")
        L.append(f"  - {rcb.get('reading')}")
        lc = rcb.get("last_challenge") or {}
        if lc.get("argument"):
            L.append(f"  - l'avvocato del diavolo: {lc.get('argument')}")
        L.append("")

    tk = civ.get("ticket") or {}
    if tk.get("ok") and tk.get("ticket"):
        L += ticket_mod.ticket_lines(tk["ticket"])
        L.append("")

    # 5i) I DORMIENTI (Part Three): who is sleeping, and the countdown to retirement.
    if lf.get("dormienti"):
        L.append("**I dormienti (il Guardian caccia l'ozio).**")
        for dm in lf["dormienti"][:8]:
            L.append(f"  - {dm.get('agent')}: dormiente da {dm.get('idle_days')}g "
                     f"(soglia {dm.get('threshold_days')}g, "
                     f"{dm.get('days_to_retirement')}g al pensionamento)")
        L.append("")

    # 6) THE COUNCIL DECIDED + WHY.
    L.append("**Il Consiglio ha deciso.**")
    decisions = civ.get("decisions") or d.get("decisions") or []
    if decisions:
        for dec in decisions:
            L.append(f"  - {dec.get('what')} -- perche': {dec.get('why')}")
    else:
        L.append("  - nessuna decisione: niente da deliberare.")
    L.append("")

    # 6b) THE ONE BRAIN (LETTER v5): the CEO now reads the civilization's MIND --
    #     the decision with its soul, the collective mood, the simulations, who
    #     changed idea, the world model, the synergy score, generation vs generation,
    #     the strongest/dying theories, and the playground.
    L.extend(one_brain_lines(civ))

    # 6c) THE FRONTIER (MEGA PHASE 4): the elevations beyond the Renaissance --
    #     the causal engine (WHY), the predictive world model (the 4h prophecy), the
    #     meta-learning engine (how it learns), and the system's self-description.
    #     Honest: a block that was not measured renders no section.
    L.extend(frontier_lines(civ))

    # 7) THE KINGS OF THE NIGHT (coronation progress).
    kings = (civ.get("coronation") or {}).get("candidates") or []
    L.append("**I re della notte (coronazione).**")
    if kings:
        for c in kings:
            L.append(f"  - {c.get('family')}: net_r {c.get('net_r')} "
                     f"(corona {c.get('progress_pct')}%, fase {c.get('phase')})")
    else:
        L.append("  - nessun candidato in coronazione.")
    L.append("")

    # 8) THE LIBRARY (what was found + digested).
    lib = civ.get("library") or {}
    L.append("**La biblioteca.**")
    if lib.get("catalog"):
        for e in lib["catalog"][:4]:
            L.append(f"  - {e.get('title')} [{e.get('source')}]: "
                     f"{e.get('digested')} idea/e -> {e.get('hypotheses')} ipotesi")
    else:
        L.append("  - nessun documento digerito questa settimana.")
    L.append("")

    # 8b) THE FUTURES CONTEXT (the delayed CME quotes read against spot).
    fc = (civ.get("hawk_eye") or {}).get("futures_context") or {}
    if fc:
        L.append("**Il contesto futures (lead/lag).**")
        L.append(f"  - {fc.get('reading')}")
        for leg in (fc.get("legs") or [])[:6]:
            mark = "osservato" if leg.get("watched") else "non osservato"
            L.append(f"    - {leg.get('contract')} ({leg.get('name')}) "
                     f"vs {leg.get('spot')}: {mark}; {leg.get('reading')}")
        L.append("")

    # 9) REQUESTS TO THE CEO (again, at the end, so they are never missed).
    L.append("**Richieste al CEO.**")
    if reqs:
        for x in reqs:
            L.append(f"  - {x}")
    else:
        L.append("  - niente, capo, procedo.")
    for x in granted_reqs:
        L.append(f"  - gia' autorizzato (direttiva del CEO): {x} -- non richiesto")
    L.append("")
    L.append("_Lettera generata da un agente AI (OpenHands) per il CEO; "
             "numeri verificati dal controllore._")
    return "\n".join(L) + "\n"


def one_brain_lines(civ: dict | None) -> list[str]:
    """THE LETTER v5 — the CEO reads the civilization's MIND (the One Brain block).

    Renders the new sections from the One Brain's block (``civ['one_brain']``): the
    decision with its soul, the collective mood, the simulations, who changed idea,
    the world model, the synergy score, generation vs generation, the strongest and
    dying theories, and the playground. Honest: a missing reading is reported as
    "non misurato", never invented. Returns an empty list when the block is absent
    (an older committed civilization.json renders no mind — no fabricated sections).
    """
    ob = (civ or {}).get("one_brain") or {}
    if not ob:
        return []
    L: list[str] = []
    L.append("## IL CERVELLO UNO (la mente collettiva)")

    # IL CERVELLO UNO HA DECISO: each decision with its SOUL.
    L.append("**Il Cervello Uno ha deciso.**")
    decided = [d for d in (ob.get("decisions") or []) if d.get("decided")]
    refused = [d for d in (ob.get("decisions") or []) if not d.get("decided")]
    if decided:
        for d in decided:
            soul = d.get("soul") or {}
            prop = d.get("proposal") or {}
            L.append(f"  - {prop.get('idea')}: SUPPORTATO da {soul.get('supporters')}; "
                     f"CONTRARIO {soul.get('opposers') or 'nessuno'}; "
                     f"umore {soul.get('mood')}; "
                     f"la simulazione teme: {soul.get('simulation_fears')}")
    else:
        L.append("  - nessun trade: il campo integrato non ha superato la soglia.")
    for d in refused:
        prop = d.get("proposal") or {}
        L.append(f"  - rifiutato {prop.get('idea')}: {'; '.join(d.get('reasons') or [])}")
    L.append("")

    # L'UMORE COLLETTIVO.
    mood = ob.get("mood") or {}
    L.append("**L'umore collettivo.**")
    if mood.get("population"):
        c = mood.get("counts") or {}
        L.append(f"  - paura {c.get('fear', 0)}, eccitazione {c.get('excitement', 0)}, "
                 f"disgusto {c.get('disgust', 0)}, calma {c.get('calm', 0)} "
                 f"-> dominante: {mood.get('dominant')}")
    else:
        L.append("  - nessun umore misurato (popolazione vuota).")
    L.append("")

    # LE SIMULAZIONI.
    sims = [p.get("simulation") for p in (ob.get("packages_detail") or [])
            if p.get("simulation")]
    L.append("**Le simulazioni.**")
    if sims:
        for s in sims[:3]:
            L.append(f"  - {s.get('agent')}: {s.get('path')}; "
                     f"punti fragili: {s.get('fragile_points')}")
    else:
        L.append("  - nessuna simulazione questa notte.")
    L.append("")

    # CHI HA CAMBIATO IDEA (the belief ledger).
    bl = ob.get("belief_ledger") or []
    L.append("**Chi ha cambiato idea.**")
    if bl:
        for b in bl[-3:]:
            L.append(f"  - {b.get('agent')}: {b.get('before')} -> {b.get('after')} "
                     f"({b.get('reason')})")
    else:
        L.append("  - nessun cambio di convinzione: le credenze tengono.")
    L.append("")

    # IL MODELLO DEL MONDO.
    model = ob.get("model") or {}
    change = ob.get("model_change") or {}
    L.append("**Il modello del mondo.**")
    L.append(f"  - v{model.get('version')}: {model.get('belief') or 'non misurato'}")
    L.append(f"  - {change.get('reading')}")
    L.append("")
    # THE BRIDGE: la dispensa dell'evoluzione -- il cuore e la mente si parlano.
    evo = ob.get("evolution")
    if evo:
        L.append("**La dispensa dell'evoluzione (il ponte col cuore).**")
        isles = evo.get("islands") or {}
        present = [i for i, v in isles.items()
                   if isinstance(v, dict) and v.get("present")]
        above = 0
        if present:
            tot = sum(int(isles[i].get("champions") or 0) for i in present)
            meas = sum(int(isles[i].get("measured") or 0) for i in present)
            above = sum(int(isles[i].get("above_floor") or 0) for i in present)
            L.append(f"  - {tot} campioni in dispensa ({', '.join(present)}); "
                     f"{meas} misurati, {above} sopra il pavimento.")
            top = max((isles[i].get("top") for i in present
                       if isles[i].get("top")),
                      key=lambda t: float(t.get("wilson_lb") or 0.0),
                      default=None)
            if top:
                L.append(f"  - migliore: {top.get('family')} "
                         f"(wilson_lb {top.get('wilson_lb')}).")
        else:
            L.append("  - nessuna isola ha ancora una dispensa (non misurato).")
        led = evo.get("ledger") or {}
        trials = led.get("trials_today") or 0
        if trials:
            seal = f" [{led.get('dna_seal')}]" if led.get("dna_seal") else ""
            L.append(f"  - il cuore ha girato {trials:,} prove oggi{seal}.")
        if not above:
            L.append("  - l'evoluzione sta ancora cercando: nessun campione "
                     "ha superato il pavimento.")
        L.append("")

    # IL PUNTEGGIO DI SINERGIA.
    L.append("**Il punteggio di sinergia.**")
    syn = ob.get("synergy")
    L.append(f"  - {('sinergia ' + str(syn) + ' (>1: il Cervello Uno supera le parti)') if syn is not None else 'non misurata: nessun survivor collettivo questa notte'}")
    L.append("")

    # GENERAZIONE vs GENERAZIONE.
    gen = ob.get("generation") or {}
    L.append("**Generazione vs generazione.**")
    L.append(f"  - {gen.get('reading')}")
    L.append("")

    # LE TEORIE PIU' FORTI E QUELLE MORENTI.
    theories = ob.get("theories") or []
    L.append("**Le teorie piu' forti e quelle morenti.**")
    if theories:
        for t in theories:
            L.append(f"  - [{t.get('status')}] {t.get('claim')} "
                     f"(check {t.get('checks')})")
    else:
        L.append("  - nessuna teoria formulata.")
    L.append("")

    # IL PARCO GIOCHI.
    play = ob.get("play") or {}
    L.append("**Il parco giochi.**")
    if play.get("played"):
        for it in (ob.get("play_items") or [])[:3]:
            L.append(f"  - {it.get('agent')} prova: {it.get('shape')} "
                     f"(rischio 0) -- {it.get('why')}")
    else:
        L.append("  - nessun gioco stanotte.")
    L.append("")

    # I VIZI (the antibias audit) — the cognitive vices the month can name.
    audit = ob.get("bias_audit") or {}
    if audit:
        L.append("**I vizi (audit cognitivo).**")
        counts = audit.get("counts") or {}
        if counts:
            for name, n in counts.items():
                L.append(f"  - {name}: {n} decisione/i sospetta/e")
        else:
            L.append(f"  - nessun vizio nominato su {audit.get('audited', 0)} "
                     f"decisioni auditate.")
        L.append("")
    return L


def thermo_line(thermometer: dict | None) -> str:
    t = thermometer or {}
    if t.get("index") is None:
        return f"non misurato (perche': {t.get('why') or 'nessun dato di stato'})"
    return (f"{t['index']}/100 ({t.get('band') or '?'})"
            + (f" -- {t['reading']}" if t.get("reading") else ""))


# ---------------------------------------------------------------------------
# The letter's memory: the weekly comparison (the CEO always compares to last week).
# ---------------------------------------------------------------------------
def letter_filename(date: str) -> str:
    m = __import__("re").match(r"(\d{4}-\d{2}-\d{2})", str(date or ""))
    if m:
        return f"lettera_{m.group(1)}.md"
    from datetime import datetime, timezone
    return f"lettera_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"


def letter_path(date: str, *, root: str = "..") -> str:
    """The committed location: ``APEX/letters/lettera_YYYY-MM-DD.md``."""
    return f"{root}/letters/{letter_filename(date)}"


def load_history(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"nights": []}
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {"nights": []}
    if not isinstance(data, dict):
        return {"nights": []}
    data.setdefault("nights", [])
    return data


def append_history(history: dict, *, date: str, metrics: dict) -> dict:
    """Append tonight's raw metric values (idempotent per date), keep it bounded."""
    nights = history.setdefault("nights", [])
    entry = {"date": date, "metrics": {k: v.get("value")
                                       for k, v in (metrics or {}).items()}}
    nights[:] = [n for n in nights if n.get("date") != date]
    nights.append(entry)
    nights[:] = nights[-400:]
    return history


def prior_week_metrics(history: dict | None, date: str, *,
                       days: int = 7) -> dict[str, dict]:
    """The metric values from ~7 nights before ``date`` (the CEO compares to last week).

    Honest: when fewer than two nights are stored the prior is EMPTY -- every trend
    prints ``--`` rather than a fabricated arrow.
    """
    nights = (history or {}).get("nights") or []
    dated = [n for n in nights if n.get("date") and n.get("date") != date]
    if not dated:
        return {}
    from datetime import date as _d, timedelta
    try:
        y, m, dd = (int(x) for x in date.split("-"))
        target = _d(y, m, dd) - timedelta(days=days)
    except (ValueError, AttributeError):
        target = None
    pick = None
    if target is not None:
        for n in sorted(dated, key=lambda n: n["date"], reverse=True):
            try:
                yy, mm, ddd = (int(x) for x in n["date"].split("-"))
            except ValueError:
                continue
            if _d(yy, mm, ddd) <= target:
                pick = n
                break
    if pick is None:
        pick = min(dated, key=lambda n: n["date"])
    out: dict[str, dict] = {}
    for k, v in (pick.get("metrics") or {}).items():
        text = _cell(v, _unit_for(k))
        out[k] = {"value": v, "text": text, "why": None if v is not None else "non misurato"}
    return out


def _unit_for(key: str) -> str:
    for _label, k, unit, _dir in TABLE_METRICS:
        if k == key:
            return unit
    return "num"


def frontier_lines(civ: dict | None) -> list[str]:
    """THE FRONTIER (MEGA PHASE 4): the elevations beyond the Renaissance.

    Renders the new intelligence the civilization now carries, from its block
    (``civ['frontier']``): the CAUSAL engine (WHY a trade won or lost), the
    PREDICTIVE world model (the 4h prophecy + its calibration), the META-LEARNING
    engine (how efficiently it learns, and where its creative leaps came from), and
    the system's SELF-DESCRIPTION. Honest: a block that was not measured renders no
    section (an older committed civilization.json shows nothing -- never fabricated).
    """
    f = (civ or {}).get("frontier") or {}
    if not f:
        return []
    L: list[str] = []
    L.append("## LA FRONTIERA (le elevazioni oltre il Rinascimento)")
    L.append("")

    # THE WHY ENGINE: the causal reading of the last outcomes.
    ca = f.get("causal") or {}
    if ca.get("analyses"):
        L.append("**Il motore causale (il perche').**")
        L.append(f"  - {ca.get('reading')}")
        for a in ca["analyses"][:3]:
            L.append(f"  - {a.get('reading')} (fiducia {a.get('confidence')})")
            for link in (a.get("chain") or [])[:3]:
                L.append(f"    - {link.get('link')}: {link.get('detail')}")
            cfs = a.get("counterfactuals") or []
            if cfs:
                L.append(f"    - controfattuale: se {cfs[0].get('if')}, "
                         f"allora {cfs[0].get('then')}")
        L.append("")

    # THE PROPHECY: the 4h forecast + the calibration of the past prophecies.
    pr = f.get("prophecy") or {}
    fc = pr.get("forecast") or {}
    if fc.get("measured"):
        L.append("**La profezia (modello del mondo predittivo).**")
        L.append(f"  - {fc.get('reading')}")
        st = pr.get("scenario_tree") or {}
        if st.get("measured"):
            L.append(f"  - albero di scenario: {st.get('reading')}")
            for b in (st.get("branches") or []):
                L.append(f"    - ramo {b.get('branch')}: {b.get('what')} "
                         f"(p {b.get('p')}, {b.get('r')}R)")
        cal = pr.get("calibration") or {}
        if cal.get("n"):
            L.append(f"  - calibrazione: {cal.get('reading')}")
        L.append("")

    # THE META-LEARNING: efficiency, acceleration, the optimized curriculum, leaps.
    ml = f.get("meta_learning") or {}
    eff = ml.get("efficiency") or {}
    if eff.get("measured"):
        L.append("**L'apprendimento (meta-apprendimento).**")
        L.append(f"  - {eff.get('reading')}")
        cur = ml.get("curriculum") or {}
        if cur.get("emphasize"):
            L.append(f"  - curriculum: enfatizza {cur.get('emphasize')}")
        if cur.get("retire"):
            L.append(f"  - curriculum: ritira {cur.get('retire')}")
        leap = ml.get("creative_leap") or {}
        if leap.get("leaps"):
            L.append(f"  - {leap.get('reading')}")
            cond = (ml.get("leap_conditions") or {}).get("reproducible") or []
            if cond:
                L.append(f"    - condizioni riproducibili dei salti: {cond}")
        L.append("")

    # THE SELF-DESCRIPTION: who the system is, in its own words.
    sd = f.get("self_description") or {}
    if sd.get("who_am_i"):
        L.append("**Chi sono (autodescrizione).**")
        if sd.get("dragon_prose"):
            L.append(f"  - {sd['dragon_prose']}")
        L.append(f"  - {sd.get('who_am_i')}")
        if sd.get("what_i_can_do"):
            L.append(f"  - so fare: {len(sd['what_i_can_do'])} cose")
        if sd.get("my_strengths"):
            L.append(f"  - forze: {sd['my_strengths'][:3]}")
        if sd.get("my_weaknesses"):
            L.append(f"  - debolezze: {sd['my_weaknesses'][:3]}")
        L.append("")
    return L
