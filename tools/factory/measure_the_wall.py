"""THE WALL, MEASURED — Law 1 (measure before the word).

What really kills round one? 160 random genomes (the factory's own draw,
fixed reproducible seed) judged on the SELECTION book (conservative):

  * on EURUSD (the screen's cheap pair);
  * on all five pairs (the "era" round).

For each: trades, gross_r, net_r, wilson_lb, ranked. Then the honest
percentiles and counts: how many trade 30+ times? how many are gross
positive? how many would clear the R85 gate (gross >= 3x friction)? how
many the old absolute screen? The bare truth, order included — no word
without a measure. This is the instrument that motivated R97 (the living
funnel): keep it runnable, keep the wall visible.

Run from backend/:
    python -m tools.factory.measure_the_wall
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.data import load_parquet          # noqa: E402
from app.core.pairs import PAIR_PIP             # noqa: E402
from app.quant import frames as fr              # noqa: E402
from app.quant import breeding                  # noqa: E402
from app.quant import costs                     # noqa: E402
from app.quant import evaluator as ev           # noqa: E402
from app.quant import fitness as fitness_mod    # noqa: E402
from app.core import law                        # noqa: E402
import numpy as np                              # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "EURGBP", "AUDJPY"]
ROWS = 20000
N = 160
SEED = 123457


def pct(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> int:
    universe = {}
    for pair in PAIRS:
        m15 = load_parquet(f"data/history/{pair}_M15.parquet")
        m15 = m15.iloc[-ROWS:].reset_index(drop=True)
        universe[pair] = fr.build_frames(m15, pair, PAIR_PIP[pair])

    rng = np.random.default_rng(SEED)
    cfg = ev.EvaluationConfig(cost_model=costs.SELECTION_COST_MODEL)
    rows = []
    for i in range(N):
        g = breeding.random_genome(rng, concrete=False,
                                   ensemble_quota=0.25, layers_quota=0.0)
        rep_c = ev.evaluate(g, {"EURUSD": universe["EURUSD"]}, cfg, world_seed=0)
        fit_c = fitness_mod.fitness(rep_c.metrics, 30)
        rep_f = ev.evaluate(g, universe, cfg, world_seed=0)
        fit_f = fitness_mod.fitness(rep_f.metrics, 30)
        m = rep_f.metrics
        fric = m.gross_r - m.net_r
        mult = (m.gross_r / fric) if fric > 0 else 0.0
        gate = law.gross_to_friction_verdict(m.gross_r, m.net_r)
        rows.append({
            "family": g.family, "trades_c": rep_c.metrics.trades,
            "gross_c": rep_c.metrics.gross_r, "net_c": rep_c.metrics.net_r,
            "wilson_c": fit_c.wilson_lb, "ranked_c": fit_c.ranked,
            "trades_f": m.trades, "gross_f": m.gross_r, "net_f": m.net_r,
            "wilson_f": fit_f.wilson_lb, "ranked_f": fit_f.ranked,
            "friction_f": fric, "multiple_f": mult, "gate_ok": gate.ok,
        })
        if (i + 1) % 40 == 0:
            print(f"  ... {i + 1}/{N} misurati", flush=True)

    def share(pred):
        return sum(1 for r in rows if pred(r))

    print("\n===== LA VERITA' DI %d GENOMI RANDOM (libro SELECTION, %d righe) =====" % (N, ROWS))
    print("EURUSD (cheap): trades mediana %.0f | p25 %.0f | p75 %.0f | max %.0f" % (
        pct([r["trades_c"] for r in rows], .5), pct([r["trades_c"] for r in rows], .25),
        pct([r["trades_c"] for r in rows], .75), max(r["trades_c"] for r in rows)))
    print("5 coppie (era):  trades mediana %.0f | p25 %.0f | p75 %.0f | max %.0f" % (
        pct([r["trades_f"] for r in rows], .5), pct([r["trades_f"] for r in rows], .25),
        pct([r["trades_f"] for r in rows], .75), max(r["trades_f"] for r in rows)))
    print()
    print("quanti fanno 30+ trade su EURUSD:        %3d/%d (%.0f%%)" % (share(lambda r: r["trades_c"] >= 30), N, 100 * share(lambda r: r["trades_c"] >= 30) / N))
    print("quanti fanno 30+ trade su 5 coppie:      %3d/%d (%.0f%%)" % (share(lambda r: r["trades_f"] >= 30), N, 100 * share(lambda r: r["trades_f"] >= 30) / N))
    print("quanti fanno  1+ trade su 5 coppie:      %3d/%d (%.0f%%)" % (share(lambda r: r["trades_f"] >= 1), N, 100 * share(lambda r: r["trades_f"] >= 1) / N))
    print("quanti NON fanno nulla su 5 coppie:      %3d/%d (%.0f%%)" % (share(lambda r: r["trades_f"] == 0), N, 100 * share(lambda r: r["trades_f"] == 0) / N))
    print("gross positivo su 5 coppie:              %3d/%d (%.0f%%)" % (share(lambda r: r["gross_f"] > 0), N, 100 * share(lambda r: r["gross_f"] > 0) / N))
    print("net positivo su 5 coppie:                %3d/%d (%.0f%%)" % (share(lambda r: r["net_f"] > 0), N, 100 * share(lambda r: r["net_f"] > 0) / N))
    print("gate R85 (gross>=3x friz, 5 coppie):     %3d/%d (%.0f%%)" % (share(lambda r: r["gate_ok"]), N, 100 * share(lambda r: r["gate_ok"]) / N))
    print("gate R85 su EURUSD:                      %3d/%d (%.0f%%)" % (share(lambda r: law.gross_to_friction_verdict(r["gross_c"], r["net_c"]).ok), N, 100 * share(lambda r: law.gross_to_friction_verdict(r["gross_c"], r["net_c"]).ok) / N))
    print("SCREEN ATTUALE (ranked EURUSD + gate):   %3d/%d (%.0f%%)" % (share(lambda r: r["ranked_c"]), N, 100 * share(lambda r: r["ranked_c"]) / N))
    print()
    print("gross (5 coppie): mediana %.2f | p75 %.2f | p90 %.2f | max %.2f" % (
        pct([r["gross_f"] for r in rows], .5), pct([r["gross_f"] for r in rows], .75),
        pct([r["gross_f"] for r in rows], .9), max(r["gross_f"] for r in rows)))
    print("net   (5 coppie): mediana %.2f | p75 %.2f | p90 %.2f | max %.2f" % (
        pct([r["net_f"] for r in rows], .5), pct([r["net_f"] for r in rows], .75),
        pct([r["net_f"] for r in rows], .9), max(r["net_f"] for r in rows)))
    print("wilson (5 coppie, chi e' ranked): max %.4f" % max((r["wilson_f"] for r in rows), default=0.0))
    print("multiple gross/friction (5 coppie): p75 %.2f | p90 %.2f | max %.2f" % (
        pct([r["multiple_f"] for r in rows], .75), pct([r["multiple_f"] for r in rows], .9),
        max(r["multiple_f"] for r in rows)))
    print()
    print("===== PER FAMIGLIA (5 coppie) =====")
    by_fam = defaultdict(list)
    for r in rows:
        by_fam[r["family"]].append(r)
    for fam in sorted(by_fam, key=lambda f: -len(by_fam[f])):
        rs = by_fam[fam]
        print("%-26s n=%2d | trades med %.0f | 30+ %d | gross>0 %d | net>0 %d | gate %d" % (
            fam[:26], len(rs), pct([r["trades_f"] for r in rs], .5),
            sum(1 for r in rs if r["trades_f"] >= 30),
            sum(1 for r in rs if r["gross_f"] > 0),
            sum(1 for r in rs if r["net_f"] > 0),
            sum(1 for r in rs if r["gate_ok"])))
    print()
    print("===== LE FAMIGLIE CHE FANNO TRADE (le materie prime dell'evoluzione) =====")
    makers = [r for r in rows if r["trades_f"] >= 30]
    print("genomi 30+ trade:", len(makers), "| famiglie:", dict(Counter(r["family"] for r in makers)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
