"""THE ONE BRAIN, WIRED — run the collective over one night's REAL data.

This is the integration point (the One Brain, First Acts 5-12): it reduces the
night report and the civilization state into the collective's block — the minds and
their reliability weights, each funded idea's cognitive package, the decisions (with
their soul), the vetoes, the Kelly voice, the unified market model and what changed,
the collective mood, the simulations, the belief ledger, the theories, the
playground, the synergy score, and the metacognition trend.

Honest measurement (R47): every axis is READ from the report; an unmeasured axis is
``None`` (never invented). A proposal that clears no gate yields NO decision — the
One Brain says "nothing" rather than forcing a trade.
"""

from __future__ import annotations

import hashlib

from app.civilization import career as career_mod
from app.civilization import gaze, mind, one_brain, playground

__all__ = ["run_one_brain", "minds_from_report", "TITANIUM_FLOOR"]

TITANIUM_FLOOR = one_brain.TITANIUM_FLOOR


def _shape(*parts: str) -> str:
    """A deterministic shape key (the pattern-memory key; no RNG, no clock)."""
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def minds_from_report(night_report: dict) -> dict:
    """Each measured mind (a leaderboard family) and its REAL reliability axes.

    calibration <- the adversary win-rate (does the family's read match reality?);
    intuition_hit_rate <- the adversary win-rate (its gut's hit-rate);
    theory_survival <- 1.0 when the family cleared the adversary bar, else 0.0.
    simulation_accuracy and emotional_calibration are ``None`` — this report does not
    measure them, and an unmeasured axis is never invented.
    """
    out: dict[str, dict] = {}
    for row in (night_report.get("leaderboard") or []):
        fam = row.get("family")
        if not fam:
            continue
        wr = row.get("adv_win_rate")
        lb = row.get("adv_lb")
        out[str(fam)] = {
            "calibration": float(wr) if isinstance(wr, (int, float)) else None,
            "intuition_hit_rate": float(wr) if isinstance(wr, (int, float)) else None,
            "theory_survival": (1.0 if float(lb) >= 0.45 else 0.0)
                               if isinstance(lb, (int, float)) else None,
            "simulation_accuracy": None,
            "emotional_calibration": None,
        }
    return out


def _agent_affects(night_report: dict) -> dict[str, str]:
    """Each measured family's affective state, from its REAL record (honest).

    FEAR is reserved for genuine bleeding (net R negative AND a real drawdown);
    a family that is merely losing more than it wins is DISGUSTED by a tape that
    punishes it; a family with a real edge is EXCITED; otherwise it is CALM. The
    streak passed in is the LOSS COUNT only when the family is bleeding — total
    losses on a winning family are not a streak (the honest reading).
    """
    out: dict[str, str] = {}
    for row in (night_report.get("leaderboard") or []):
        fam = row.get("family")
        if not fam:
            continue
        net = row.get("adv_net_r")
        wr = row.get("adv_win_rate")
        dd = float(row.get("measured_dd_r") or 0.0)
        bleeding = isinstance(net, (int, float)) and float(net) < 0.0 and dd > 0.0
        losing_style = isinstance(wr, (int, float)) and float(wr) < 0.45
        out[str(fam)] = mind.affect(
            losing_streak=int(row.get("losses") or 0) if bleeding else 0,
            drawdown=dd,
            opportunity_rich=(isinstance(wr, (int, float)) and float(wr) >= 0.5
                              and isinstance(net, (int, float)) and float(net) > 0.0),
            # DISGUST is reserved for a tape that is genuinely punishing this
            # style: a low win-rate AND real bleeding. A family merely making less
            # than it wins but still profitable is not disgusted (it is calm) — the
            # tape is not poison to it. Honest: never a verdict without the loss.
            regime_poison=(losing_style and bleeding))
    return out


def _packages(night_report: dict, state: dict, ts: str) -> list[dict]:
    """One cognitive package per FUNDED idea (the integration layer)."""
    from app.civilization import economy
    pkgs: list[dict] = []
    for idea in state.get("ideas", []):
        if not economy.funded(idea):
            continue
        text = str(idea.get("idea") or "")
        shape = _shape("idea", text)
        # The deliberate mind (System 2): a hypothesis, its mechanism, a falsifier,
        # and the prediction the burst will test. All derived from the idea itself.
        thought = mind.thought_record(
            agent="council", hypothesis=text,
            mechanism="the market funded this idea with collective attention",
            falsifier="the burst finds no certified survivor — the idea is false",
            prediction="the burst yields a survivor with net R > 0", ts=ts)
        # The intuitive mind (System 1): scan the pattern memory for this shape.
        # The library lives at ``one_brain.patterns`` (where the nightly learning
        # writes it), NOT at the top level of the state — reading the wrong key
        # made the council's gut a permanent None (a lazy-None, BUG-1).
        intuition = mind.recognise(
            (state.get("one_brain") or {}).get("patterns", []),
            agent="council", shape=shape)
        # The simulation (Klein): the imagined burst path and where it feels fragile.
        sim = mind.simulate(
            agent="council", entry="funded idea", path="burst -> gauntlet -> survivor",
            danger="the unseen gauntlet rejects the candidate",
            exit="a certified survivor or an honest zero",
            fragile_points=["il burst non trova un survivor",
                            "il survivor non regge il gauntlet"],
            ts=ts)
        theory = {"agent": "council", "claim": text,
                  "rationale": "the market's attention is the civilization's own bet",
                  "status": "untested", "checks": 0, "ts": ts}
        pkgs.append(one_brain.integration_package(
            proposal={"idea": text, "attention": idea.get("attention", 0.0),
                      "kind": "forge_burst", "shape": shape},
            thought=thought, intuition=intuition, simulation=sim, theory=theory,
            lineage=[f"shape:{shape}"]))
    return pkgs


def _condemned_families(ledger: list) -> list[str]:
    """Families the Council condemned by E4 (retire_family decisions).

    R152 — THE GHOST CONDEMNED: the belief once rode the report's rows
    alone, so it counted families the Council had condemned hours before
    (the Sage's 21:54 synthesize: "the census counts four ghosts as
    alive"). Derived from the EVENTS, never hand-transported: the extra
    ``family`` field when the entry carries it (R147+), the ``what`` text
    for the pre-extra history.
    """
    out = set()
    for e in ledger or []:
        if e.get("kind") != "retire_family":
            continue
        fam = e.get("family")
        if not fam:
            what = str(e.get("what") or "")
            if what.startswith("retire the family "):
                fam = what[len("retire the family "):].strip()
        if fam:
            out.add(str(fam))
    return sorted(out)


def _market_model(night_report: dict, *, version: int, ts: str,
                  hawk: dict | None = None, futures: dict | None = None,
                  condemned: list[str] | None = None) -> dict:
    """The unified market model from the report's REAL axes (honest).

    C5 — THE MARKET MODEL'S SENSES: the model also absorbs the HAWK's live ticks
    (``hawk``) and the futures context (``futures``) when the VM published them, so
    the shared picture sees the REAL market, not only history. An absent reading is
    omitted, never invented.
    """
    rows = night_report.get("leaderboard") or []
    pairs = sorted({str(r.get("family")) for r in rows if r.get("family")})
    # R147 — THE RIGHT NAME: resilience (a survival share) once rode in the
    # `regimes` axis and the whole civilization read it as regime health — the
    # thermometer lied by label (the Dragon's fourth denuncia). Resilience now
    # rides under its own name; `regimes` carries ONLY a REAL regime census
    # (pair -> regime label) when the world measured one (the hawk's live map),
    # and stays honestly empty otherwise — never a survival score in a regime's
    # clothes.
    resilience = {str(r.get("family")): (float(r.get("resilience"))
                   if isinstance(r.get("resilience"), (int, float)) else None)
                  for r in rows if r.get("family")}
    regimes: dict = {}
    if isinstance(hawk, dict) and isinstance(hawk.get("regimes"), dict):
        regimes = {str(k): v for k, v in hawk["regimes"].items() if v}
    flows = {str(r.get("family")): (float(r.get("adv_net_r"))
             if isinstance(r.get("adv_net_r"), (int, float)) else None)
             for r in rows if r.get("family")}
    sessions: dict = {}
    if isinstance(hawk, dict) and hawk.get("reading"):
        sessions["hawk_tick"] = str(hawk.get("reading"))
    if isinstance(futures, dict) and futures.get("reading"):
        sessions["futures_context"] = str(futures.get("reading"))
    m = one_brain.market_model(pairs=pairs, flows=flows, regimes=regimes,
                               sessions=sessions, resilience=resilience,
                               version=version, ts=ts)
    if pairs:
        belief = f"il mondo ha {len(pairs)} famiglia/e: {', '.join(pairs)}"
        # R152 — THE GHOST CONDEMNED: the rows stay (they ran — the
        # factory's truth) and the CONDEMNATION is named beside them (the
        # Council's truth): the model holds both, never either alone.
        condemned_running = sorted(set(condemned or []) & set(pairs))
        if condemned_running:
            belief += (f" — {len(condemned_running)} condannata/e (E4): "
                       f"{', '.join(condemned_running)}")
        m["belief"] = belief
        m["condemned"] = condemned_running
    if sessions:
        m["senses"] = sorted(sessions)
    return m


def run_one_brain(store_state: dict, *, night_report: dict | None = None,
                  agents: list[str] | None = None, ts: str = "",
                  hawk: dict | None = None, futures: dict | None = None,
                  evo: dict | None = None) -> dict:
    """Run the collective over one night; mutate ``store_state``; return the block.

    Deterministic and honest. Every funded idea becomes a cognitive package; the
    minds' weights are recomputed from the report; a decision is born only when the
    integrated field clears the bar. Nothing measured -> honest ``None``.
    """
    night_report = night_report or {}
    agents = agents or ["king-trend", "king-range", "philosopher-1",
                        "explorer-1", "sniper-1"]
    ob = store_state.setdefault("one_brain", {"version": 0, "history": [],
                                              "belief_ledger": [], "theories": [],
                                              "patterns": [], "generations": [],
                                              "refusals": []})
    ob.setdefault("refusals", [])
    version = int(ob.get("version", 0)) + 1

    # --- the minds, their affects, and the reliability-weighted field ---------
    minds = minds_from_report(night_report)
    weights = one_brain.reliability_weights(minds)
    affects = _agent_affects(night_report)
    mood = mind.collective_mood([{"affect": a} for a in affects.values()])

    # --- the pattern memory (System 1): learn this night's shapes -------------
    for row in (night_report.get("leaderboard") or []):
        fam = row.get("family")
        if not fam:
            continue
        mind.remember_pattern(ob.setdefault("patterns", []), agent="council",
                              shape=_shape("family", str(fam)),
                              resolved_up=bool(float(row.get("adv_lb") or 0) >= 0.45),
                              ts=ts)
    # --- the unified market model (versioned) + what changed ------------------
    #     C5: the model also absorbs the hawk's live ticks + the futures context.
    model = _market_model(night_report, version=version, ts=ts,
                          hawk=hawk, futures=futures,
                          condemned=_condemned_families(
                              store_state.get("ledger") or []))
    model_change = one_brain.market_model_changed(ob.get("model"), model)

    # --- THE CAREER LEDGER (R142): the civilization's memory of merit across ----
    #     nights. Each night's leaderboard folds into a per-family LIFETIME record
    #     (pooled wins/trades, the same Wilson arithmetic the night certifies
    #     with); a family whose CAREER clears the same bar with a real track record
    #     is a survivor EVEN ON A NIGHT IT DID NOT WIN -- evidence compounds, it
    #     does not restart every dawn. Idempotent per (family, date): a re-read
    #     report replaces its receipt, never a double count.
    career_ledger = career_mod.career_state(store_state)
    career_mod.career_step(career_ledger, night_report.get("leaderboard") or [],
                           date=str(night_report.get("date") or str(ts)[:10]), ts=ts)
    career_certified = career_mod.certified_families(career_ledger)

    # --- the theories (System 2): score the standing theory from real evidence
    theories: list[dict] = ob.setdefault("theories", [])
    newborn = not theories  # R137: a birth gets its first night of grace
    if not theories:
        theories.append(mind.theory(agent="council",
                                    claim="collective attention finds survivors",
                                    rationale="the market funds what the many believe",
                                    ts=ts))
    for t in theories:
        row = next((r for r in (night_report.get("leaderboard") or [])
                    if float(r.get("adv_lb") or 0) >= 0.45), None)
        # THE CAREER speaks too: a lifetime-certified family IS the market funding
        # what the many believe -- twenty nights of receipts are as real as one.
        mind.score_theory(t, supported=1 if (row or career_certified) else 0,
                          weakening=0,
                          falsified=0 if (row or career_certified) else 1)

    # --- THE FORGETTING (R137): the theories killed by data leave the ------
    # working memory (CoALA: forgetting is a function, not an accident). Only
    # a theory that STOOD through a cycle may retire -- a newborn gets its
    # first night of grace (a question deserves one full test, not a death
    # in the same breath it was asked). The falsified retire with honor, the
    # working list stays small, and the reading says the retirement aloud.
    retired_now = ([] if newborn else mind.retire_theories(
        theories, ob.setdefault("retired_theories", [])))

    # --- the belief ledger: the revisitation of the world model --------------
    yesterday = ob.get("last_model_belief") or {}
    today = {"model.belief": model.get("belief"),
             "model.pairs": ",".join(model.get("pairs", []))}
    ob["belief_ledger"] = (ob.get("belief_ledger") or []) + \
        mind.revisitation("council", yesterday=yesterday, today=today)
    ob["last_model_belief"] = today

    # --- the decisions (with a soul) + the veto + the Kelly voice ------------
    supporters = sorted([f for f, m in minds.items()
                         if (m.get("theory_survival") or 0.0) >= 0.5])
    opposers = sorted([f for f, m in minds.items() if f not in supporters])
    decisions: list[dict] = []
    vetoes: list[dict] = []
    kelly: list[dict] = []
    # C4 — re-evaluate PAST refusals against tonight's real survivors ("was the
    # veto right?"). The survivors are the report's certified families -- and, since
    # R142, the CAREER-certified ones: a family whose lifetime evidence cleared the
    # same bar is a survivor even on a night it did not win.
    survivors = sorted({str(r.get("family")) for r in (night_report.get("leaderboard") or [])
                        if r.get("family") and float(r.get("adv_lb") or 0) >= 0.45}
                       | set(career_certified))
    ob["refusals"] = one_brain.reconsider_refusals(ob.get("refusals") or [],
                                                   survivors=survivors, ts=ts)
    # R147 — THE VETO'S PALACE IS BOUNDED: the refusal memory grew unbounded in
    # the state (only the RETURNED block was trimmed) — a palace, not a hoard
    # (the same cure the play queue received, BUG-3b's family).
    ob["refusals"] = ob["refusals"][-200:]
    packages = _packages(night_report, store_state, ts)
    # THE GAZE feeds the brain (Part Five): the visual context the eyes produced this
    # night rides every package as first-class evidence, and a sighting that several
    # agents SAW (convergent seeing) makes them VISUAL supporters of the field. Honest:
    # no sighting -> no visual context, no visual supporters.
    gaze_state = store_state.get("gaze") or {}
    seen_now = [{"agent": s.get("agent"), "what": s.get("what")}
                for s in (gaze_state.get("sightings") or []) if s.get("mode") == "VEDO"]
    convergence = gaze.convergent_seeing(seen_now)
    visual_supporters = sorted({a for c in convergence.get("convergent", [])
                                for a in c["agents"] if a in weights})
    visual_ctx = None
    if seen_now:
        top = seen_now[-1]
        visual_ctx = gaze.visual_context(
            chart=top.get("what"),
            notes=[c["what"] for c in convergence.get("convergent", [])][:3])
    for pkg in packages:
        pkg["visual"] = visual_ctx
    for pkg in packages:
        # C3 — the Oracle's SECOND SIGHT over this package, recorded with the
        # decision so the brain's cognitive view is auditable per trade.
        pkg["second_sight"] = one_brain.second_sight(pkg)
        d = one_brain.decide(pkg, weights=weights, mood=mood, model=model,
                             supporters=supporters, opposers=opposers,
                             visual_supporters=visual_supporters, ts=ts)
        if d is None:
            continue
        decisions.append(d)
        # The council LEARNS its own proposal's shape after the decision. The
        # honest signal is the NIGHT's real collective outcome (did the market
        # fund any survivor?), NOT ``decided`` — using the decision itself would
        # be circular (the decision needs a bullish gut, which needs the outcome).
        # This is what lets the SAME idea's shape be RECOGNISED next night; without
        # it the pattern memory held only family shapes and the council's intuition
        # was a structural None (a lazy-None, BUG-1).
        shape = (pkg.get("proposal") or {}).get("shape")
        if shape:
            night_found_survivors = any(
                float(r.get("adv_lb") or 0) >= 0.45
                for r in (night_report.get("leaderboard") or [])) or bool(career_certified)
            mind.remember_pattern(ob.setdefault("patterns", []), agent="council",
                                  shape=shape, resolved_up=night_found_survivors,
                                  ts=ts)
        if d.get("decided"):
            v = one_brain.veto(d, belief_ledger=ob["belief_ledger"], mood=mood)
            vetoes.append(v)
            if v["vetoed"]:
                # The bouncer is AUTHORITATIVE: a vetoed decision does not stand.
                # Downgrade it to an honest refusal carrying the veto's reasons, so
                # the minutes never record a "decide" the soul then blocked (a
                # silent failure: the veto was computed but changed nothing, BUG-11).
                d["decided"] = False
                d["vetoed"] = True
                d["reasons"] = list(d.get("reasons") or []) + [
                    f"veto: {r}" for r in v["reasons"]]
                # C4 — the refusal enters the veto's memory for later re-evaluation.
                ob["refusals"].append(one_brain.refusal_entry(d, ts=ts))
            else:
                edge = (pkg["proposal"] or {}).get("attention")
                kelly.append(one_brain.kelly_voice(
                    float(edge) if isinstance(edge, (int, float)) else None,
                    floor=TITANIUM_FLOOR))
        elif d.get("reasons"):
            # An honest refusal from the field (no veto needed): remembered too, so
            # the veto's memory covers EVERY rejected proposal, not only vetoed ones.
            ob["refusals"].append(one_brain.refusal_entry(d, ts=ts))

    # --- the emergence metric (synergy) + metacognition ----------------------
    lb = [float(r.get("adv_lb") or 0.0) for r in (night_report.get("leaderboard") or [])]
    best_individual = max(lb) if lb else None
    supported = [float(r.get("adv_lb") or 0.0)
                 for r in (night_report.get("leaderboard") or [])
                 if float(r.get("adv_lb") or 0.0) >= 0.45]
    collective_quality = (sum(supported) / len(supported)) if supported else None
    synergy = one_brain.synergy_score(collective_quality=collective_quality,
                                      best_individual_quality=best_individual)
    generations = ob.setdefault("generations", [])
    prev_quality = generations[-1].get("quality") if generations else None
    gen = one_brain.metacognition_generation(generation=version,
                                             quality=collective_quality,
                                             previous=prev_quality)
    generations.append(gen)

    # --- the playground (Vygotsky's play) ------------------------------------
    play_items = playground.playground_slots(agents, max_slots=2, ts=ts)
    play = playground.play_report(play_items)

    # --- the antibias audit --------------------------------------------------
    audit = mind.bias_audit(list(store_state.get("ledger", [])))

    # --- C2 — the generation archive: distill this generation's patterns ------
    archive = mind.generation_archive(generation=version, minds=minds,
                                      weights=weights, survivors=survivors)
    ob["archive"] = (ob.get("archive") or []) + [archive]
    ob["archive"] = ob["archive"][-12:]

    # --- C4 — the veto's calibration over its own memory ---------------------
    calibration = one_brain.veto_calibration(ob["refusals"])

    block = {
        "version": version, "ts": ts,
        "minds": minds, "weights": weights, "affects": affects, "mood": mood,
        "packages": len(packages),
        "decisions": decisions, "vetoes": vetoes, "kelly": kelly,
        "packages_detail": packages,
        "model": model, "model_change": model_change,
        "theories": theories,
        "theories_retired_now": len(retired_now),
        "retired_theories": (ob.get("retired_theories") or [])[-12:],
        "belief_ledger": ob["belief_ledger"][-8:],
        "play": play, "play_items": play_items,
        "synergy": synergy, "generation": gen, "bias_audit": audit,
        "refusals": ob["refusals"][-12:], "veto_calibration": calibration,
        "generation_archive": archive,
        "family_careers": career_mod.career_report(career_ledger),
        "visual": {"context": visual_ctx, "convergent": convergence,
                   "visual_supporters": visual_supporters},
    }
    block["reading"] = (
        f"One Brain v{version}: {len(minds)} mind(s), "
        f"{sum(1 for d in decisions if d.get('decided'))} decision(s), "
        f"umore {mood.get('dominant')}, sinergia {synergy}, "
        f"modello {'cambiato' if model_change.get('changed') else 'stabile'}"
        + (f"; {len(retired_now)} teoria/e ritirata/e nell'archivio"
           if retired_now else ""))
    # THE BRIDGE (the evolution's pantry, honestly read) rides the block: the
    # Letter and the funders can finally SEE the heart's harvest. Honest None
    # when no view was handed in (an older grand renders as before).
    block["evolution"] = evo

    ob["version"] = version
    ob["model"] = model
    ob["weights"] = weights
    ob.setdefault("history", []).append(block)
    ob["history"] = ob["history"][-12:]
    ob["last"] = block
    return block
