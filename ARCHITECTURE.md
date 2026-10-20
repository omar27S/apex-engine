# APEX — THE ARCHITECTURE

An evolving trading organism on one always-on VM. It measures markets,
breeds strategies, decides its own nights, and writes an honest letter
to its CEO every morning. Nothing here is decorative: every module
either measures, evolves, decides, or reports — and every claim it makes
is backed by a number it can show.

## THE BODY (where things live)

```
APEX/
  backend/
    app/
      core/           law, data (validators, fail-closed), pairs
      quant/          the physics: genome, engine, signals, costs,
                      evaluator, fitness (Wilson LB), breeding
      factory/        the reproductive loop (26 modules) -- the HEART
      civilization/   the 60-module mind: one_brain, sage, council,
                      dragon_mind, letter, evolution_view (the bridge)
      pyramid/        the roster and the veto
    tools/
      factory/        run_factory (the shift), measure_the_wall,
                      engine_sync (the public mirror, leak-scan)
      one_brain.py    the single brain's CLI
      grand_night.py  the 04:04 Grand batch
    configs/
      factory_shift.json   the shift's law-in-numbers (signed)
    tests/            ~1,700 tests; a claim without a test is a rumour
    data/history/     the tapes (M15 parquet, bid-derived, validated)
  deploy/heart/       factory_shift.py -- the systemd heart runner
  letters/            the morning letters (the VM writes to the CEO)
```

## THE HEARTBEAT (every 3 hours, apex-heart.timer)

1. `git pull --rebase --autostash` (the CEO may have pushed law or tapes)
2. resolve the island (R98 wheel: heart -> turbo -> vault, one per
   ledger line) and the rotating seed (R92: seed + 7919 x lines)
3. draw 240 genomes (gating honoured, champions injected from the
   island's pantry -- a champion without a measure is refused, Law 3)
4. **the living funnel (R97)**: round one keeps the living variety
   (top-60% graded by trades/wilson/net on the cheap pair -- life
   first); round two is the full judgement (ranked floor + the sealed
   3x friction gate, now seated where the invoice is full)
5. breed generations (elite, crossover, mutation, EDA memory, polish,
   CMA) -- only ranked bodies (min_trades on the full universe) can be
   crowned: **a couch is never a champion**
6. the nine seats (R96): up to 9 distinct-realm champions enter the
   pantry `factory_champions_{island}.json`; the migration (R68) can
   carry them across islands
7. append one honest line to `factory_ledger.jsonl` (sealed with the
   DNA: `dna=v1`), commit and push -- the CEO's phone sees the beat

## THE MIND (every night, apex-grand at 04:04)

The Grand batch runs the civilization: the ideas cycle (funded by the
One Brain's night decisions), the sage, the council, the meta-learning
engine, the self-description -- and, since the bridge, the One Brain
READS THE EVOLUTION'S PANTRIES first (`evolution_view`): how many
champions, how many measured, how many above the floor, how many
trials today. The morning letter tells the CEO both stories -- the
market's night and the heart's harvest -- from real numbers.

## THE LAW

* The twelve laws of the DNA (`app/factory/dna.py`): measure before
  the word; the dead must be proven; what is learned survives the
  shift; the seed is not the destiny; the receipt is evidence; silence
  is not consent; every eye declares its darkness; the wound is
  numbered; the living state wins; the system breathes alone; the
  proof is the real shift; what is written in the dark must be true
  in the morning.
* R16 lottery tax (promotion bar rises with trials) -- R17 net-R
  doctrine (Wilson 95% LB of the NET win rate) -- R69 staircase --
  R85 the 3x gross-to-friction gate (sealed at 3.0) -- R91 persistent
  champions -- R92 rotating seed -- R96 nine seats -- R97 the living
  funnel + the couch is never crowned -- R98 the island wheel.
* Fail-closed everywhere: no rate is invented, no island is imagined,
  no unmeasured body is ranked.

## THE STATE (the living artefacts)

| artefact | meaning |
| --- | --- |
| `factory_ledger.jsonl` | one honest line per shift (trials, seed, champions, dna seal) |
| `factory_champions_{island}.json` | each island's pantry (measured kings only) |
| `civilization_state.json` | the mind's state (regime, reputations, ideas...) |
| `data/history/.factory_run.json` | the last shift's full report (funnel, generations) |
| `letters/lettera_YYYY-MM-DD.md` | the CEO's morning letter |
| `falcon.json` | the eye's reading (which sources live, which regime) |

## THE SERVICES

| unit | cadence | role |
| --- | --- | --- |
| `apex-heart.timer` | 3h | one bounded factory shift |
| `apex-grand.timer` | 04:04 | the night's Grand batch + the letter |
| `apex-falcon.timer` | 15m | the market eye |
| `apex-flow.timer` / `apex-web-watch.timer` | hourly | the flow and the watch |
| GitHub runners (self-hosted) | on push | night-shift, certificate chain |

## HOW TO PROVE THINGS HERE

* tests: `python -m pytest tests/factory/ -q` (from `backend/`)
* the wall, measured: `python -m tools.factory.measure_the_wall`
* a real shift: `sudo -n systemctl start apex-heart.service`
  (the ONLY proof that counts is a real shift -- Law 11)
* the honest questions: read the ledger's last line, then the pantry,
  then the letter. Three files, one truth.

## HOW THE DIRECTOR WORKS

Every intervention is a numbered script (`scripts/faseNN.sh` over the
SSH bridge), a measured diagnosis, a law with tests, a real-shift
proof, an epic-honest commit, and the public mirror you are reading
(leak-scanned). The private vault keeps the living state; this mirror
keeps the craft public.
