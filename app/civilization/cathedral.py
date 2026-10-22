"""THE CATHEDRAL OF CONFLUENCE -- the decision architecture that mathematically
produces high win rates (THE REAL HUNT, Part One).

A trade with a high win probability is not born from ONE brilliant strategy -- it is
born from SEVEN INDEPENDENT CONFIRMATIONS that all align. Like a cathedral: no single
column holds it up -- seven together create something that cannot fall.

  * THE SEVEN COLUMNS -- REGIME (the market type), STRUCTURE (at a level that
    matters), MOMENTUM (price IS moving our way -- confirmation, not prediction),
    TIMING (the right window), MACRO (the intermarket context), CONSENSUS (3+
    UNCORRELATED strategies agree), EVIDENCE (this type of setup works NOW). Each
    column is HONEST: an unmeasured column is ``confirmed=None`` (no confirmation),
    never a guess;
  * THE CONFIDENCE CASCADE -- the columns confirm IN SEQUENCE (REGIME -> STRUCTURE ->
    TIMING -> MACRO -> MOMENTUM -> CONSENSUS -> EVIDENCE), each confirmation
    triggering the next; the building TENSION is reported live. A break resets it;
  * THE CATHEDRAL GATES -- 7/7 aligned = CLASS A (the strongest); 6/7 = CLASS B (the
    missing column is NAMED -- prepare, do not enter); 5/7 or fewer = NO TRADE;
  * THE ADAPTIVE COLUMN WEIGHTS -- each column carries a MEASURED accuracy (how often
    its confirmation led to a win); columns that are right gain weight, wrong ones are
    recalibrated. A column below 40% for two weeks triggers a Council review.

Honesty is binding: an unmeasured column never confirms; a confidence with no measured
accuracy is ``None`` (never an invented probability); the accuracy ledger only moves
on a REAL resolved outcome. Pure at import (Scar #6): the caller supplies the evidence
and the timestamp; this module never reads the wall clock.
"""

from __future__ import annotations

__all__ = [
    "CATHEDRAL_VERSION",
    "COLUMNS",
    "CONFIDENCE_CASCADE_ORDER",
    "CLASS_A_MIN",
    "CLASS_B_MIN",
    "COLUMN_REVIEW_FLOOR",
    "cathedral",
    "column_accuracy",
    "record_outcome",
    "column_weights",
    "evaluate_column",
    "_sky_verdict",
    "columns_from_context",
    "cascade",
    "gate",
    "cathedral_block",
]

CATHEDRAL_VERSION: int = 1

# The seven columns (the full architecture). The CASCADE order is the sequence in
# which they confirm (Part One.2); it differs from the listing order on purpose.
COLUMNS: tuple[str, ...] = (
    "regime", "structure", "momentum", "timing", "macro", "consensus", "evidence",
)
CONFIDENCE_CASCADE_ORDER: tuple[str, ...] = (
    "regime", "structure", "timing", "macro", "momentum", "consensus", "evidence",
)

# THE CATHEDRAL GATES: 7/7 = CLASS A; 6/7 = CLASS B; 5/7 or fewer = NO TRADE.
CLASS_A_MIN: int = 7
CLASS_B_MIN: int = 6

# A column below this accuracy for two weeks triggers a Council review.
COLUMN_REVIEW_FLOOR: float = 0.40

# A regime that supports a directional hunt (a "dead"/"ranging" regime does not).
_SUPPORTIVE_REGIMES: frozenset[str] = frozenset({"trending", "volatile"})
# A structure is "fresh" while it has not been tested this many times.
MAX_LEVEL_TESTS: int = 3
# The minimum live score for the EVIDENCE column to confirm (works NOW, not in 2023).
EVIDENCE_LIVE_FLOOR: float = 0.0


def cathedral(state: dict) -> dict:
    """The Cathedral's persistent structures (created empty on first access)."""
    st = state if state is not None else {}
    return st.setdefault("cathedral", {
        "version": CATHEDRAL_VERSION,
        "accuracy": {},          # column -> {hits, n, accuracy}
        "history": [],           # the resolved signals (for the accuracy ledger)
        "last": None,            # the last evaluated block
    })


# --- THE ADAPTIVE COLUMN WEIGHTS -------------------------------------------

def column_accuracy(state: dict, column: str) -> dict:
    """A column's MEASURED accuracy: how often its confirmation led to a win.

    Honest: no resolved signal -> ``None`` (unmeasured), never an invented rate.
    """
    row = (cathedral(state).get("accuracy") or {}).get(str(column)) or {}
    n = int(row.get("n") or 0)
    hits = int(row.get("hits") or 0)
    acc = round(hits / n, 4) if n else None
    return {"column": str(column), "hits": hits, "n": n, "accuracy": acc,
            "measured": n > 0,
            "review": bool(n >= 5 and acc is not None and acc < COLUMN_REVIEW_FLOOR),
            "reading": (f"{column}: accuratezza {acc:.0%} su {n}"
                        if n else f"{column}: accuratezza non misurata")}


def record_outcome(state: dict, *, confirmed_columns, won: bool, ts: str = "") -> dict:
    """Credit every CONFIRMED column with a REAL resolved outcome.

    A confirmed column HITS when the trade won, MISSES when it lost. Only confirmed
    columns are credited (an unconfirmed column made no claim). Honest: the ledger
    moves only here, on a real outcome -- never on a guess.
    """
    cat = cathedral(state)
    acc = cat.setdefault("accuracy", {})
    cols = [str(c) for c in (confirmed_columns or []) if str(c) in COLUMNS]
    for c in cols:
        row = acc.setdefault(c, {"hits": 0, "n": 0})
        row["n"] = int(row.get("n") or 0) + 1
        if won:
            row["hits"] = int(row.get("hits") or 0) + 1
        row["accuracy"] = round(row["hits"] / row["n"], 4)
    rec = {"ts": str(ts), "columns": cols, "won": bool(won)}
    cat.setdefault("history", []).append(rec)
    del cat["history"][:-400]
    return {"credited": cols, "won": bool(won),
            "reading": (f"esito registrato ({'vinta' if won else 'persa'}): "
                        f"creditate {len(cols)} colonne")}


def column_weights(state: dict) -> dict:
    """Every column's adaptive weight (its measured accuracy, or 1.0 if unmeasured).

    Honest: an unmeasured column weighs the neutral 1.0 -- it is neither trusted nor
    distrusted, and the block says how many columns were actually measured.
    """
    out: dict[str, float] = {}
    measured = 0
    for c in COLUMNS:
        a = column_accuracy(state, c)
        if a["measured"]:
            out[c] = float(a["accuracy"])
            measured += 1
        else:
            out[c] = 1.0
    return {"weights": out, "measured": measured, "n": len(COLUMNS)}


# --- THE SEVEN COLUMNS -----------------------------------------------------

def _sky_verdict(reg: str, hunts) -> tuple[bool, str, str]:
    """THE RELATIVE SKY (R144): one law for the Watchtower and the Cathedral.

    ``hunts`` is the candidate's blood GROUP -- its way of hunting -- or ``None``
    for a general (family-less) hunt. A SPECIALIST blood (a group the Watchtower's
    own ``REGIME_AFFINITY`` names) is confirmed only in the skies its blood hunts,
    so the Cathedral can never confirm what the Watchtower would pause: the meanrev
    blood now hunts the range that used to refuse EVERYONE, and the trend blood no
    longer rides a sky it does not hunt. Blood that is unclassified or not a
    specialist falls to the old directional law -- honest: no invented
    specialization, no invented refusal. Fail-closed: a ``dead`` sky confirms
    nobody (nothing hunts a dead market). The import is lazy so this module stays
    pure at import time (Scar #6).
    """
    from app.civilization.regime_watch import REGIME_AFFINITY  # the single law
    hunts = (str(hunts).strip() if isinstance(hunts, str) else "") or None
    directional = reg in _SUPPORTIVE_REGIMES
    if hunts and hunts != "unknown" and any(
            hunts in groups for groups in REGIME_AFFINITY.values()):
        hunted = hunts in REGIME_AFFINITY.get(reg, ())
        return (hunted,
                f"regime {reg}, il sangue {hunts} "
                + ("caccia questo cielo" if hunted else "non caccia questo cielo"),
                f"regime {reg}: " + ("conferma" if hunted
                                     else f"il sangue {hunts} non caccia questo cielo"))
    label = (", sangue non classificato" if hunts == "unknown"
             else (f", sangue {hunts} non specializzato" if hunts else ""))
    return (directional, f"regime {reg}{label}",
            f"regime {reg}: " + ("conferma" if directional
                                 else "non e' un regime da caccia"))


def evaluate_column(name: str, evidence: dict) -> dict:
    """Evaluate ONE column from its evidence (honest: unmeasured -> confirmed None).

    Returns ``{column, confirmed, measured, detail, reading}``. ``confirmed`` is
    ``True``/``False``/``None`` (``None`` = unmeasured, no confirmation claimed).
    """
    name = str(name)
    ev = evidence or {}
    if name == "regime":
        reg = ev.get("regime")
        if reg is None:
            return _col(name, None, False, "regime non misurato",
                        "regime non misurato: nessuna conferma (onesto)")
        reg = str(reg)
        transition = bool(ev.get("transitioning"))
        ok, detail, why = _sky_verdict(reg, ev.get("hunts"))
        return _col(name, ok, True, detail + (" (in transizione)" if transition else ""), why)
    if name == "structure":
        at = ev.get("at_level")
        if at is None:
            return _col(name, None, False, "struttura non misurata",
                        "struttura non misurata: nessuna conferma (onesto)")
        tests = ev.get("tests")
        kind = ev.get("kind") or "livello"
        fresh = True if tests is None else (int(tests) <= MAX_LEVEL_TESTS)
        ok = bool(at) and fresh
        detail = f"{kind} (testato {tests}x)" if tests is not None else f"{kind} (freschezza non misurata)"
        why = ("prezzo a un livello strutturale" if ok else
               ("livello troppo consumato" if at and not fresh else "prezzo non a un livello"))
        return _col(name, ok, True, detail, f"struttura: {why}")
    if name == "momentum":
        conf = ev.get("confirmed")
        if conf is None:
            return _col(name, None, False, "momentum non misurato",
                        "momentum non misurato: nessuna conferma (onesto)")
        d = ev.get("direction")
        return _col(name, bool(conf), True, f"direzione {d}" if d else "movimento confermato",
                    "momentum: il prezzo SI muove " + ("nella nostra direzione"
                    if conf else "contro di noi"))
    if name == "timing":
        in_window = ev.get("in_window")
        if in_window is None:
            return _col(name, None, False, "finestra non misurata",
                        "timing non misurato: nessuna conferma (onesto)")
        win = ev.get("window") or "finestra"
        return _col(name, bool(in_window), True, str(win),
                    ("timing: " + (f"nella finestra giusta ({win})" if in_window
                                   else "coppia giusta, ora sbagliata")))
    if name == "macro":
        support = ev.get("support")
        if support is None:
            return _col(name, None, False, "macro non misurato",
                        "macro non misurato: nessuna conferma (onesto)")
        reason = ev.get("reason") or ""
        return _col(name, bool(support), True, reason,
                    "macro: " + ("supporta il trade" if support else "va contro"))
    if name == "consensus":
        n = ev.get("n_independent")
        if n is None:
            return _col(name, None, False, "consenso non misurato",
                        "consenso non misurato: nessuna conferma (onesto)")
        # DEBT-062: independence is MEASURED (from the return series), not claimed.
        # When the caller supplies ``independent`` (True/False) use it; when it is
        # None (no series) the independence axis is UNMEASURED -> no confirmation.
        independent = ev.get("independent")
        if independent is None:
            return _col(name, None, False, f"{int(n)} voci, indipendenza non misurata",
                        "consenso: l'indipendenza non e' misurata (nessuna conferma)")
        ok = int(n) >= 3 and bool(independent)
        return _col(name, ok, True, f"{int(n)} strategie indipendenti",
                    ("consenso: 3+ approcci indipendenti concordano" if ok
                     else "consenso: non abbastanza voci indipendenti"))
    if name == "evidence":
        live = ev.get("live_score")
        if live is None:
            return _col(name, None, False, "prova dal vivo non misurata",
                        "prova: il presente non ha ancora giudicato (onesto)")
        n = ev.get("n")
        ok = float(live) > EVIDENCE_LIVE_FLOOR
        return _col(name, ok, True, f"punteggio dal vivo {float(live):+.3f}R"
                    + (f" su {n} finestre" if n else ""),
                    ("prova: questo setup funziona ORA" if ok
                     else "prova: nessuna prova recente (0 dalla colonna)"))
    return _col(name, None, False, "colonna sconosciuta",
                f"{name}: colonna sconosciuta (nessuna conferma)")


def _col(name: str, confirmed, measured: bool, detail: str, reading: str) -> dict:
    return {"column": str(name), "confirmed": confirmed, "measured": bool(measured),
            "detail": str(detail), "reading": str(reading)}


def columns_from_context(ctx: dict) -> list[dict]:
    """Build all seven columns from a live context (each column reads its own keys).

    The context carries the measured evidence (falcon readings, levels, circadian,
    macro radar, the collective, the forward chamber). A missing key yields an
    UNMEASURED column -- never a fabricated confirmation.
    """
    c = ctx or {}
    return [
        evaluate_column("regime", c.get("regime") or {}),
        evaluate_column("structure", c.get("structure") or {}),
        evaluate_column("momentum", c.get("momentum") or {}),
        evaluate_column("timing", c.get("timing") or {}),
        evaluate_column("macro", c.get("macro") or {}),
        evaluate_column("consensus", c.get("consensus") or {}),
        evaluate_column("evidence", c.get("evidence") or {}),
    ]


# --- THE CONFIDENCE CASCADE + THE GATES ------------------------------------

def cascade(columns: list[dict]) -> dict:
    """Confirm the columns IN SEQUENCE (the building tension), stopping at a break.

    Each column's confirmation triggers the next. The cascade stops at the first
    column that is measured-and-NOT-confirmed (the tension RESETS with an honest
    reason); unmeasured columns are reported as ``unmeasured`` (no confirmation
    claimed) and also stop the cascade. The ``tension`` is the count confirmed so far.
    """
    by = {c["column"]: c for c in (columns or [])}
    seq: list[dict] = []
    tension = 0
    broken = None
    for name in CONFIDENCE_CASCADE_ORDER:
        col = by.get(name) or _col(name, None, False, "assente", f"{name}: assente")
        if col.get("confirmed") is True:
            tension += 1
            seq.append({"column": name, "state": "confirmed", "reading": col["reading"]})
            continue
        state = "unmeasured" if not col.get("measured") else "broken"
        seq.append({"column": name, "state": state, "reading": col["reading"]})
        broken = {"column": name, "state": state, "reason": col["reading"]}
        break
    return {"sequence": seq, "tension": tension, "broken": broken,
            "reading": (f"cascata: {tension} colonne in tensione"
                        + (f", rotta su {broken['column']} ({broken['state']})"
                           if broken else " -- tutte allineate"))}


def gate(columns: list[dict], *, weights: dict | None = None) -> dict:
    """The Cathedral gate: 7/7 = CLASS A; 6/7 = CLASS B; 5/7 or fewer = NO TRADE.

    The missing columns are NAMED with an honest reason (unmeasured vs contrary). The
    ``confidence`` is the mean adaptive accuracy of the CONFIRMED columns (honest:
    ``None`` when no column accuracy is measured -- never an invented probability).
    """
    cols = list(columns or [])
    confirmed = [c["column"] for c in cols if c.get("confirmed") is True]
    missing = [{"column": c["column"], "reason": c.get("detail") or c.get("reading"),
                "unmeasured": not c.get("measured")}
               for c in cols if c.get("confirmed") is not True]
    n = len(confirmed)
    if n >= CLASS_A_MIN:
        cls = "A"
    elif n >= CLASS_B_MIN:
        cls = "B"
    else:
        cls = "none"
    w = (weights or {}).get("weights") or {}
    accs = [float(w[c]) for c in confirmed if isinstance(w.get(c), (int, float))
            and (weights or {}).get("measured")]
    confidence = round(sum(accs) / len(accs), 4) if accs else None
    reading = (
        "LA CATTEDRALE PARLA: 7/7 colonne allineate (CLASSE A)" if cls == "A"
        else (f"quasi: {n}/7, manca {missing[0]['column']} "
              f"({missing[0]['reason']})" if cls == "B" and missing
              else f"nessun trade: {n}/7 colonne allineate")
    )
    return {"class": cls, "n_confirmed": n, "n_total": len(cols),
            "confirmed": confirmed, "missing": missing,
            "confidence": confidence,
            "confidence_measured": bool(accs),
            "reading": reading}


def cathedral_block(state: dict, ctx: dict, *, ts: str = "") -> dict:
    """The Cathedral's block for the artifact + the Letter: columns, cascade, gate.

    Evaluates the seven columns from the live context, runs the confidence cascade and
    the gate, and reports the adaptive weights. Fail-open: a fault is caught and the
    block says so honestly. The last block is stored for the accuracy ledger.
    """
    try:
        cols = columns_from_context(ctx)
        w = column_weights(state)
        cas = cascade(cols)
        g = gate(cols, weights=w)
        block = {
            "version": CATHEDRAL_VERSION,
            "columns": cols,
            "cascade": cas,
            "gate": g,
            "weights": w,
            "accuracies": {c: column_accuracy(state, c) for c in COLUMNS},
            "measured": g["n_confirmed"] > 0,
            "reading": (f"la Cattedrale: {g['n_confirmed']}/7 colonne "
                        f"(classe {g['class']}); {cas['reading']}"),
        }
        cathedral(state)["last"] = block
        return block
    except Exception as e:  # noqa: BLE001 -- the Cathedral must never break the night
        return {"version": CATHEDRAL_VERSION, "columns": [], "measured": False,
                "gate": {"class": "none", "n_confirmed": 0, "n_total": len(COLUMNS),
                         "confirmed": [], "missing": [], "confidence": None,
                         "confidence_measured": False,
                         "reading": "cattedrale: fault tollerato (onesto)"},
                "cascade": {"sequence": [], "tension": 0, "broken": None,
                            "reading": "cascata non valutata"},
                "weights": {"weights": {}, "measured": 0, "n": len(COLUMNS)},
                "accuracies": {},
                "reading": f"cattedrale: fault tollerato ({type(e).__name__})"}
