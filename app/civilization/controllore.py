"""THE CONTROLLORE -- the independent verifier of the Letter's numbers (Part Three).

The writer never self-verifies. The CONTROLLORE is a separate agent whose ONLY job
is to reconcile the Morning Letter's numbers against the RAW artifacts
(certificates/report, queue_state, the economy ledger, the body's reading) BEFORE
the Letter is committed. A discrepancy is CORRECTED before the CEO ever sees the
page: the controllore's independent reading wins.

It signs the Letter with its own line -- "verificato dal controllore -- numeri
riconciliati" -- so the CEO can see the numbers were checked, not asserted.

Pure at import (Scar #6): the verification is a reduction over the blocks the
caller hands it; it touches no disk and no clock.
"""

from __future__ import annotations

from app.civilization import bulletin as bl

__all__ = ["independent_metrics", "verify", "signature_line", "apply_corrections"]

# The keys the controllore re-derives independently from the raw blocks.
_TOL = 0.02  # absolute tolerance for a float comparison (2%)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def independent_metrics(report: dict, *, civilization: dict, body: dict,
                 thermometer: dict) -> dict:
    """Re-derive the checkable numbers from the raw blocks (the controllore's view).

    Deliberately re-reads the report DIRECTLY (its own path), not the Letter's
    pre-computed metrics, so a writer bug cannot hide behind the same reduction.
    """
    r = report or {}
    st = bl.statistics_from(r)
    d = (civilization or {}).get("diary")
    if not isinstance(d, dict):
        d = {}
    for k, v in (d.get("stats") or {}).items():
        if v is not None and v != "":
            st[k] = v

    lb = r.get("leaderboard") or []
    net_pos = None
    if lb:
        net_pos = sum(1 for x in lb
                      if isinstance(x.get("adv_net_r", x.get("net_r")), (int, float))
                      and x.get("adv_net_r", x.get("net_r")) > 0)

    e2 = ((r.get("amendment") or {}).get("E2_failure_law") or {})
    reg, chg = _num(e2.get("failures_registered")), _num(e2.get("failures_that_changed_behaviour"))
    e2_ratio = round(chg / reg, 4) if reg and chg is not None else None

    alive = _num(st.get("population"))
    retired = _num(st.get("retired"))
    blist = d.get("births")
    born = len(blist) if isinstance(blist, list) else None

    kings = _num(st.get("kings")) or (2 if r else None)

    return {
        "wr_best": _num(st.get("wr_best")),
        "wr_portfolio": _num(st.get("wr_portfolio")),
        "rr_min": _num(st.get("rr_min")),
        "rr_avg": _num(st.get("rr_avg")),
        "rr_best": _num(st.get("rr_best")),
        "ambition_pos": _num(st.get("rr_target")),
        "profit_factor": _num(st.get("profit_factor")),
        "expectancy_r": _num(st.get("expectancy_r")),
        "dd_r": _num(st.get("dd_r")),
        "deployable_pct": _num(st.get("deployable_pct")),
        "volume_worst_week": _num(st.get("volume_worst_week")),
        "volume_gap": _num(st.get("volume_gap")),
        "net_positive_strategies": net_pos,
        "friction_avg": _num(st.get("friction_avg")),
        "friction_gap": _num(st.get("friction_gap")),
        "kings": kings,
        "body_hours": _num((body or {}).get("hours_worked")),
        "util_pct": _num((body or {}).get("util_pct")),
        "thermometer": _num((thermometer or {}).get("index")),
        "e2_ratio": e2_ratio,
        # population trio (text form, reconciled separately)
        "_population_trio": (f"{int(alive)}/{int(retired)}/{int(born)}"
                             if None not in (alive, retired, born) else None),
    }


def _close(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= max(_TOL, _TOL * abs(float(b)))
    return str(a) == str(b)


def verify(*, table: dict, metrics: dict, report: dict,
           civilization: dict | None = None, body: dict | None = None,
           queue: dict | None = None, thermometer: dict | None = None) -> dict:
    """Reconcile the Letter's table against the raw artifacts, number by number.

    Returns ``{"ok", "checked", "matched", "discrepancies", "corrections",
    "signature", "reading"}``. ``corrections`` maps a metric key to the
    controllore's independent value (the Letter must be corrected to it before the
    CEO sees it).
    """
    indep = independent_metrics(report, civilization=civilization or {},
                         body=body or {}, thermometer=thermometer or {})
    checked = 0
    matched = 0
    discrepancies: list[dict] = []
    corrections: dict[str, object] = {}

    for key, truth in indep.items():
        if key.startswith("_"):
            continue
        claimed = (metrics.get(key) or {}).get("value")
        # A metric the Letter left unmeasured while the raw block HAS a value is a
        # discrepancy too (the writer undersold a real number).
        if claimed is None and truth is None:
            continue
        checked += 1
        if _close(claimed, truth):
            matched += 1
        else:
            discrepancies.append({"metric": key, "letter": claimed,
                                  "controllore": truth})
            corrections[key] = truth

    # the population trio is textual; reconcile it too.
    trio_claim = (metrics.get("population_trio") or {}).get("text")
    trio_truth = indep.get("_population_trio")
    if trio_claim is not None or trio_truth is not None:
        checked += 1
        if _close(trio_claim, trio_truth):
            matched += 1
        else:
            discrepancies.append({"metric": "population_trio", "letter": trio_claim,
                                  "controllore": trio_truth})
            corrections["population_trio"] = trio_truth

    ok = not discrepancies
    verdict = {
        "ok": ok,
        "checked": checked,
        "matched": matched,
        "discrepancies": discrepancies,
        "corrections": corrections,
        "signature": "",
        "reading": (f"controllore: {matched}/{checked} numeri riconciliati"
                    + ("" if ok else f"; {len(discrepancies)} correzione/i applicata/e")),
    }
    verdict["signature"] = signature_line(verdict)
    return verdict


def signature_line(verdict: dict) -> str:
    """The controllore's own signature line, under the table."""
    if verdict.get("ok"):
        return (f"_Verificato dal controllore -- numeri riconciliati "
                f"({verdict.get('matched')}/{verdict.get('checked')} controllati)._")
    n = len(verdict.get("discrepancies") or [])
    return (f"_Verificato dal controllore -- {verdict.get('matched')}/"
            f"{verdict.get('checked')} riconciliati; {n} correzione/i applicata/e "
            f"prima della consegna._")


def apply_corrections(table: dict, metrics: dict, verdict: dict) -> dict:
    """Rewrite the table's cells with the controllore's independent values.

    Returns the corrected ``metrics`` (the same objects the table rows point at),
    and refreshes each affected row's ``today`` text so the rendered page carries
    the verified number, not the writer's.
    """
    corrections = verdict.get("corrections") or {}
    if not corrections:
        return metrics
    from app.civilization import letter as _letter
    for key, truth in corrections.items():
        m = metrics.setdefault(key, {"value": None, "text": None, "why": None})
        if key == "population_trio":
            m["text"] = truth
        else:
            unit = _letter._unit_for(key)
            m["value"] = truth
            m["text"] = _letter._cell(truth, unit)
            m["why"] = None
    for row in table.get("rows", []):
        if row["key"] in corrections:
            m = metrics[row["key"]]
            row["today"] = m["text"] if m["text"] is not None else "--"
            row["today_value"] = m.get("value")
    return metrics
