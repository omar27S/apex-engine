"""THE BREEDING LOOM — draw, mutate, cross. The machinery of evolution.

Phase 2.3a builds the genetic operators. No tournament runs here; this module only
manufactures and recombines DNA. Everything is deterministic under a caller-seeded
``numpy`` generator and law-abiding *by construction*:

* :func:`random_genome` draws every numeric gene from ``genome.GENE_BOUNDS`` (the
  law lives inside the bounds — ``target_rr`` can never be drawn below 2.5),
  weighted per family by the R10 draw table (DATA: ``family_weights.json``).
* :func:`mutate_genome` jitters a random gene subset with Gaussian noise clamped
  to the bounds, flips the family occasionally, and repairs coherence.
* :func:`crossover_genome` recombines two parents uniformly, gene by gene.

COHERENCE is the running theme: ``ema_fast < ema_slow``, ``macd_fast < macd_slow``,
``fib_low < fib_high``, ``rsi_oversold < rsi_overbought``, an ensemble quorum in
``[2, n_members]`` (R3), and — the 2.1-era scar — a child that is not an ensemble
carries NO ``ensemble_members`` (no dead DNA).

Build Mode: pure functions, no I/O at import. The draw table is read lazily via
:func:`family_draw_weights` (R10 data), never at module load.
"""

from __future__ import annotations

import numpy as np

from app.quant import tribunal
from app.quant.genome import (
    ENSEMBLE_FAMILY,
    ENSEMBLE_MIN_MEMBERS,
    FAMILIES,
    GENE_BOUNDS,
    ML_FAMILIES,
    StrategyGenome,
    clamp_gene,
)

__all__ = [
    "family_draw_weights",
    "random_genome",
    "mutate_genome",
    "crossover_genome",
    "evolve_ensemble_member",
    "distinct_member_families",
    "elite_soup_pool",
    "elite_soup_members",
]

# R15: the ensemble floor is sealed in genome.py — imported, never re-declared.
ENSEMBLE_MAX_MEMBERS = 10
_ML_PREFIX = "ml_"
# The genes that parameterize the learned models (drawn only for an ML family).
_ML_GENES = frozenset({"ml_horizon", "ml_confidence", "ml_decay"})
_MAX_MEMBER_DIVERSITY_TRIES = 40

# R58 (Phase 7c) — THE ELITE SOUP. Ensemble members are drawn from the previous
# generation's top-ranked SINGLE genomes; a small EXPLORATION share stays random so
# the soup never starves for novel DNA. The thesis is five independent ELITE
# voters, not five dice.
ELITE_SOUP_EXPLORATION = 0.10

# R55 — the ensemble survival table's two arms. Kept here (the breeding layer's
# closed vocabulary) so the tournament and the reporting tool share one name.
ENSEMBLE_FAMILY_LABEL = ENSEMBLE_FAMILY


def distinct_member_families(members) -> bool:
    """R55 — True iff no two members of an ensemble share a family.

    The diversity is BY CONSTRUCTION: the draw, the crossover and the mutation all
    repair toward this invariant, so a violation here means an operator leaked.
    """
    fams = [
        (m.get("family") if isinstance(m, dict) else getattr(m, "family", None))
        for m in (members or ())
    ]
    concrete = [f for f in fams if f is not None and f != ENSEMBLE_FAMILY]
    return len(concrete) == len(set(concrete))


def _repair_member_families(members, rng: np.random.Generator, *, frozen: int = 0):
    """R55 repair — make member families distinct, holding the first ``frozen``.

    Duplicated families (after the frozen prefix) are redrawn as fresh concrete
    members whose family is not yet used. The member count is preserved.
    """
    out = list(members)
    used = set()
    for i, m in enumerate(out):
        fam = m.get("family") if isinstance(m, dict) else getattr(m, "family", None)
        if i < frozen:
            used.add(fam)
            continue
        if fam is None or fam == ENSEMBLE_FAMILY or fam in used:
            for _ in range(_MAX_MEMBER_DIVERSITY_TRIES):
                fresh = random_genome(rng, concrete=True)
                if fresh.family not in used:
                    out[i] = fresh.to_dict()
                    fam = fresh.family
                    break
            else:  # family space exhausted (cannot happen: ~44 families > 10)
                out[i] = random_genome(rng, concrete=True).to_dict()
                fam = out[i]["family"]
        used.add(fam)
    return tuple(out)


# ---------------------------------------------------------------------------
# R58 — THE ELITE SOUP (Phase 7c).
# ---------------------------------------------------------------------------
def elite_soup_pool(elites) -> list[StrategyGenome]:
    """The top-ranked SINGLE genomes of the previous generation (the soup pot).

    Only CONCRETE, non-ensemble genomes qualify: an ensemble may not be an
    ensemble member (R3 — nesting is forbidden), and an ``ml_*`` family is never a
    member. The order is preserved (best first), so a caller can weight toward the
    front. Duplicate signatures are collapsed, keeping the first (best) occurrence.
    """
    pool: list[StrategyGenome] = []
    seen: set[str] = set()
    for item in elites or ():
        g = item if hasattr(item, "signature") else StrategyGenome.from_dict(item)
        if g.family == ENSEMBLE_FAMILY or str(g.family).startswith(_ML_PREFIX):
            continue
        sig = g.signature()
        if sig in seen:
            continue
        seen.add(sig)
        pool.append(g)
    return pool


def elite_soup_members(
    soup,
    rng: np.random.Generator,
    *,
    size: int,
    exploration: float = ELITE_SOUP_EXPLORATION,
) -> tuple[tuple[dict, ...], str]:
    """R58 — draw ``size`` distinct-family members from the elite soup.

    Returns ``(members, source)`` where ``source`` is ``"elite"`` when every
    member came from the soup and ``"random"`` when ANY member was a random
    exploration draw. With probability ``exploration`` the WHOLE ensemble is a
    random-member ensemble (the 10% exploration share); otherwise every member is
    an elite from the soup. Distinct families are enforced by construction (R55
    repair preserves the member count), and a soup too small to fill ``size``
    distinct families is topped up with random concrete draws — the ensemble is
    never degenerate.

    Deterministic under a seeded ``rng``.
    """
    n = max(ENSEMBLE_MIN_MEMBERS, min(int(size), ENSEMBLE_MAX_MEMBERS))
    if not soup or rng.random() < exploration:
        return _draw_members(rng, n), "random"

    picks: list[dict] = []
    used: set[str] = set()
    order = list(soup)
    rng.shuffle(order)
    for g in order:
        if g.family in used:
            continue
        used.add(g.family)
        picks.append(g.to_dict())
        if len(picks) >= n:
            break
    # Top up with random concrete draws for any family still missing. A top-up
    # makes the ensemble PARTLY random, so its provenance is honestly "random".
    topped_up = False
    while len(picks) < n:
        fresh = random_genome(rng, concrete=True)
        if fresh.family in used:
            continue
        used.add(fresh.family)
        picks.append(fresh.to_dict())
        topped_up = True
    members = _repair_member_families(picks, rng)
    source = "elite" if (not topped_up and len(members) == len(picks)) else "random"
    return members, source


# ---------------------------------------------------------------------------
# Family draw weights (R10 data).
# ---------------------------------------------------------------------------
def family_draw_weights() -> dict[str, float]:
    """The per-family draw weight, from the committed R10 table (neutral if absent).

    Read lazily so importing this module never touches the filesystem. A family
    missing from the table draws at neutral weight 1.0 — it is never dropped.
    """
    table = tribunal.load_family_weights()
    return {fam: float(table.get(fam, 1.0)) for fam in FAMILIES}


def _eligible_families(concrete: bool) -> list[str]:
    """Families that may be drawn by the weighted search.

    The ``ml_*`` learned families are entered through the institutional SEEDS and the
    population's registration (Mega Phase 2, Section D), NOT through the weighted
    random draw: keeping them out of this set leaves the R10 draw stream for every
    other family byte-identical, so the pinned tournament reproductions hold.
    ``concrete`` additionally excludes the ensemble (R3 -- an ensemble member must be
    a plain series model, never a nested ensemble or a learned model).
    """
    out = [f for f in FAMILIES if not f.startswith(_ML_PREFIX)]
    if concrete:
        out = [f for f in out if f != ENSEMBLE_FAMILY]
    return out


def _draw_family(rng: np.random.Generator, concrete: bool) -> str:
    """Weighted family draw (R10 weights) over the eligible set."""
    eligible = _eligible_families(concrete)
    weights = family_draw_weights()
    prob = np.array([weights.get(f, 1.0) for f in eligible], dtype="float64")
    total = prob.sum()
    if total <= 0:
        return eligible[0]  # never happen with neutral-positive weights; defensive
    prob = prob / total
    return str(rng.choice(eligible, p=prob))


# ---------------------------------------------------------------------------
# Gene drawing.
# ---------------------------------------------------------------------------
def _draw_gene(rng: np.random.Generator, family: str, gene: str):
    """Draw one gene inside its (possibly tribunal-widened) bound.

    An optional per-family bias ``b`` samples ``low + (high-low) * u**b`` so the
    gene leans toward its floor while remaining unfixed (``u`` uniform in [0,1)).
    """
    low, high, is_int = tribunal.effective_bounds(family, gene)
    bias = tribunal.gene_bias(family, gene)
    u = float(rng.random())
    if bias != 1.0:
        u = u ** bias
    value = low + (high - low) * u
    if is_int:
        return int(round(min(max(value, low), high)))
    return float(value)


def _draw_genes(rng: np.random.Generator, family: str) -> dict:
    """Every numeric gene that applies to ``family``, drawn and coherence-repaired.

    The ML genes (``ml_horizon``/``ml_confidence``/``ml_decay``) are drawn ONLY for
    an ML family: a non-ML genome keeps its defaults, so adding the learned families
    does not shift the weighted draw stream for every other family (the pinned
    tournament reproductions stay byte-identical).
    """
    genes = {
        b.name: _draw_gene(rng, family, b.name)
        for b in GENE_BOUNDS
        if family in ML_FAMILIES or b.name not in _ML_GENES
    }
    return _repair_coherence(genes, family)


def _repair_coherence(genes: dict, family: str) -> dict:
    """Enforce the cross-gene invariants in place; returns ``genes``.

    Repairs only ever move a gene within its sealed/widened bound, so a repair
    can never smuggle a value past the law.
    """
    # slow averages must exceed fast, and MACD slow must exceed fast.
    genes["ema_slow"] = clamp_gene("ema_slow", max(genes["ema_slow"], genes["ema_fast"] + 1))
    genes["macd_slow"] = clamp_gene("macd_slow", max(genes["macd_slow"], genes["macd_fast"] + 1))
    # a Fibonacci band needs low < high; the bounds overlap so a swap is safe.
    if genes["fib_low"] >= genes["fib_high"]:
        genes["fib_low"], genes["fib_high"] = genes["fib_high"], genes["fib_low"]
    # an oversold/overbought pair needs strict ordering.
    if genes["rsi_oversold"] >= genes["rsi_overbought"]:
        genes["rsi_overbought"] = clamp_gene(
            "rsi_overbought", genes["rsi_oversold"] + 1
        )
    # a stop lookback inside a range only makes sense if it is shorter than the range.
    if genes["smc_fvg_lookback"] > genes["smc_range_lookback"]:
        genes["smc_fvg_lookback"] = genes["smc_range_lookback"]
    return genes


# ---------------------------------------------------------------------------
# Ensemble construction.
# ---------------------------------------------------------------------------
def _draw_members(rng: np.random.Generator, size: int) -> tuple[dict, ...]:
    """``size`` concrete member dicts, DISTINCT BY FAMILY (R55) and distinct by DNA.

    The old "distinct signature" guard let two members share a family (same logic,
    different parameters). R55 forbids that: no two members of one ensemble may
    share a family. ``_repair_member_families`` enforces it by construction.
    """
    members: list[dict] = []
    seen: set[str] = set()
    tries = 0
    # Try for DNA diversity, but never loop forever: the family space is finite, so
    # a duplicate signature is acceptable once we have exhausted reasonable attempts.
    while len(members) < size and tries < _MAX_MEMBER_DIVERSITY_TRIES * size:
        tries += 1
        member = random_genome(rng, concrete=True)
        sig = member.signature()
        if sig in seen:
            continue
        seen.add(sig)
        members.append(member.to_dict())
    while len(members) < size:  # fallback for a tiny family space
        members.append(random_genome(rng, concrete=True).to_dict())
    return _repair_member_families(members, rng)


def _ensemble_quorum(rng: np.random.Generator, n_members: int) -> int:
    """An explicit quorum in ``[2, n_members]`` (R3: never zero-means-unanimity)."""
    from app.quant.ensemble import effective_quorum

    raw = int(rng.integers(1, 21))
    return effective_quorum(raw, n_members)


def _attach_ensemble(genes: dict, rng: np.random.Generator, size: int | None = None) -> dict:
    """Give an ensemble genome a member set and a coherent quorum."""
    n = int(size if size is not None else rng.integers(
        ENSEMBLE_MIN_MEMBERS, ENSEMBLE_MAX_MEMBERS + 1))
    n = max(ENSEMBLE_MIN_MEMBERS, min(n, ENSEMBLE_MAX_MEMBERS))
    genes["ensemble_members"] = _draw_members(rng, n)
    genes["ensemble_min_votes"] = _ensemble_quorum(rng, n)
    genes["ensemble_size"] = clamp_gene("ensemble_size", n)
    return genes


# ---------------------------------------------------------------------------
# Random draw.
# ---------------------------------------------------------------------------
def random_genome(
    rng: np.random.Generator,
    *,
    concrete: bool = False,
    ensemble_quota: float = 0.0,
    layers_quota: float = 0.0,
    family: str | None = None,
) -> StrategyGenome:
    """A fresh random genome, every gene drawn inside the law.

    ``concrete=True`` forbids the ensemble family (and any ``ml_*``), so a caller
    that needs a leaf strategy (e.g. an ensemble member) gets one every time.

    R55 — ``ensemble_quota`` (a probability in [0, 1]) forces the ensemble family
    on that share of draws, giving ensembles a GUARANTEED population share instead
    of competing for the table's weighted draw. Ignored when ``concrete``.

    JUMP 7 — ``layers_quota`` (a probability in [0, 1]) gives that share of draws a
    MULTI-LAYER coordination stack (strategic D1 + tactical H4 above the execution
    M15). Ignored when ``concrete`` (a leaf must stay flat). Honest: 0.0 leaves the
    classic flat genome unchanged (byte-identical).

    R143 — ``family`` (optional) names the family outright: the genes are drawn
    exactly as the weighted draw would draw them for that family; only the CHOICE
    of family is the caller's (the gene flood spreads its founder wave across the
    table). ``None`` leaves the weighted draw byte-identical, quota and all.
    """
    if family is None:
        family = _draw_family(rng, concrete)
        if not concrete and ensemble_quota > 0.0 and rng.random() < ensemble_quota:
            family = ENSEMBLE_FAMILY  # R55 — dedicated evolutionary pressure
    else:
        family = str(family)
    genes = _draw_genes(rng, family)
    if family == ENSEMBLE_FAMILY:
        genes = _attach_ensemble(genes, rng)
    genes["family"] = family
    if not concrete and layers_quota > 0.0 and family != ENSEMBLE_FAMILY \
            and rng.random() < layers_quota:
        genes["layers"] = _draw_layers(family, rng)
    # from_dict clamps and ignores unknown keys — the final safety net.
    return StrategyGenome.from_dict(genes)


def eligible_families(concrete: bool = False) -> list[str]:
    """The table's eligible family names (R143: the flood spreads across them).

    The same list the weighted draw samples from -- nothing invented, nothing
    hidden: a founder wave drawn from this list is a founder the tournament
    was already willing to judge.
    """
    return list(_eligible_families(concrete))


def _draw_layers(execution_family: str, rng: np.random.Generator) -> tuple[dict, ...]:
    """Compose a random 2-3 layer coordination stack (execution family = the signal)."""
    from app.civilization import layers as layers_mod

    concrete = [f for f in _eligible_families(concrete=True)
                if f != ENSEMBLE_FAMILY]
    strat = str(rng.choice(concrete))
    tact = str(rng.choice(concrete))
    return layers_mod.compose_layers(
        execution_family=execution_family, strategic_family=strat,
        tactical_family=tact,
        strategic_direction=int(rng.choice([-1, 0, 1])),
        tactical_direction=int(rng.choice([-1, 0, 1])),
    )


# ---------------------------------------------------------------------------
# Mutation.
# ---------------------------------------------------------------------------
def _jitter_gene(rng: np.random.Generator, family: str, gene: str, value, jitter: float):
    low, high, is_int = tribunal.effective_bounds(family, gene)
    span = high - low
    delta = float(rng.normal(0.0, jitter * span))
    moved = value + delta
    moved = min(max(moved, low), high)
    return int(round(moved)) if is_int else float(moved)


def mutate_genome(
    genome: StrategyGenome,
    rng: np.random.Generator,
    *,
    rate: float = 0.3,
    jitter: float = 0.2,
    family_flip: float = 0.10,
) -> StrategyGenome:
    """A mutated copy: gene-subset jitter, occasional family flip, coherence.

    Deterministic under a seeded ``rng``. Every moved gene is clamped to its
    bound, so a mutation can never leave the law's space.
    """
    family = genome.family
    # Family flip (weighted), skipping a no-op flip to an identical family.
    if rng.random() < family_flip:
        candidate = _draw_family(rng, concrete=False)
        if candidate != family:
            family = candidate

    genes = {b.name: getattr(genome, b.name) for b in GENE_BOUNDS}
    for b in GENE_BOUNDS:
        if rng.random() < rate:
            genes[b.name] = _jitter_gene(rng, family, b.name, genes[b.name], jitter)

    # Session redraw: a mutation may move the genome to a different session.
    if rng.random() < rate:
        genes["session_id"] = _draw_gene(rng, family, "session_id")

    genes = _repair_coherence(genes, family)
    genes["family"] = family

    # JUMP 7 — a layered genome keeps its coordination stack through mutation (its
    # direction clauses may drift); a flat genome stays flat (no phantom layers).
    if genome.layers:
        from app.civilization import layers as layers_mod
        genes["layers"] = layers_mod.mutate_layers(genome, rng, rate=rate)
    else:
        genes["layers"] = ()

    if family == ENSEMBLE_FAMILY:
        # R58 — provenance survives an in-place mutation of an ensemble: an elite
        # ensemble that keeps its member set is still elite-sourced. Dropping this
        # key made from_dict fall back to "random", so the survival table showed
        # ensemble_elite trials=0 even though elite ensembles were being bred.
        genes["ensemble_source"] = genome.ensemble_source
        genes = _mutate_members(genome, genes, rng, rate)
    else:
        genes["ensemble_members"] = ()  # no dead DNA for a non-ensemble child
        genes["ensemble_source"] = "random"

    return StrategyGenome.from_dict(genes)


def _mutate_members(genome, genes: dict, rng: np.random.Generator, rate: float) -> dict:
    """Grow / shrink / jitter an ensemble's members, then re-quorum (R3, R15).

    A mutation may shrink an ensemble down to the SEALED minimum
    (``genome.ENSEMBLE_MIN_MEMBERS`` = 3) but never below it, and a torn
    (below-minimum) ensemble is repaired to a freshly drawn coherent member set.
    """
    members = [
        StrategyGenome.from_dict(m)
        for m in (genome.ensemble_members or ())
        if _member_is_concrete(m)
    ]
    if len(members) < ENSEMBLE_MIN_MEMBERS:
        # Torn or degenerate: repair to a freshly drawn coherent member set, which
        # is random-member by construction — provenance must say so (R58).
        genes["ensemble_source"] = "random"
        return _attach_ensemble(genes, rng)
    size = len(members)

    # Grow or shrink by one, bounded to [ENSEMBLE_MIN_MEMBERS, ENSEMBLE_MAX_MEMBERS].
    if rng.random() < rate:
        if size < ENSEMBLE_MAX_MEMBERS and rng.random() < 0.5:
            # A fresh member is a random draw, so the member set is no longer
            # wholly elite-sourced — the provenance is honestly "random" (R58).
            genes["ensemble_source"] = "random"
            members.append(random_genome(rng, concrete=True))
            size += 1
        elif size > ENSEMBLE_MIN_MEMBERS:  # never below the sealed floor
            members.pop(int(rng.integers(0, size)))
            size -= 1

    # Jitter a random member's genes.
    if members and rng.random() < rate:
        idx = int(rng.integers(0, len(members)))
        members[idx] = mutate_genome(members[idx], rng, rate=rate, jitter=0.2)

    genes["ensemble_members"] = tuple(m.to_dict() for m in members)
    genes["ensemble_min_votes"] = _ensemble_quorum(rng, len(members))
    genes["ensemble_size"] = clamp_gene("ensemble_size", len(members))
    # R55 — members keep DISTINCT families across mutation (repair preserves count).
    pre_repair = genes["ensemble_members"]
    final = _repair_member_families(pre_repair, rng)
    # R58 — a family repair that swapped in a fresh member breaks elite provenance.
    if final != pre_repair:
        genes["ensemble_source"] = "random"
    genes["ensemble_members"] = final
    return genes


def evolve_ensemble_member(
    genome: StrategyGenome, rng: np.random.Generator, *,
    rate: float = 0.3, jitter: float = 0.2,
) -> StrategyGenome:
    """R55 — MEMBER-LEVEL EVOLUTION. Mutate exactly ONE member of an elite ensemble.

    The other members and the quorum are preserved byte-for-byte (lineage intact):
    the child differs from its parent only inside the chosen member's genes, so an
    elite ensemble improves locally while its winning core survives. Falls back to
    a full :func:`mutate_genome` for a non-ensemble or torn parent.
    """
    if genome.family != ENSEMBLE_FAMILY:
        return mutate_genome(genome, rng, rate=rate, jitter=jitter)
    members = [
        StrategyGenome.from_dict(m)
        for m in (genome.ensemble_members or ())
        if _member_is_concrete(m)
    ]
    if len(members) < ENSEMBLE_MIN_MEMBERS:
        return mutate_genome(genome, rng, rate=rate, jitter=jitter)
    idx = int(rng.integers(0, len(members)))
    members[idx] = mutate_genome(members[idx], rng, rate=rate, jitter=jitter)
    genes = {b.name: getattr(genome, b.name) for b in GENE_BOUNDS}
    genes["family"] = ENSEMBLE_FAMILY
    genes["ensemble_members"] = tuple(m.to_dict() for m in members)
    genes["ensemble_size"] = clamp_gene("ensemble_size", len(members))
    # R58 — member-level evolution preserves the member set (only one member
    # moves), so provenance is unchanged: carry the parent's source.
    genes["ensemble_source"] = genome.ensemble_source
    # Keep the parent's quorum when it is still valid; re-quorum only if torn.
    genes["ensemble_min_votes"] = genome.ensemble_min_votes
    return StrategyGenome.from_dict(genes)


def _member_is_concrete(member) -> bool:
    """True iff ``member`` is a concrete (non-ensemble) strategy."""
    fam = member.get("family") if isinstance(member, dict) else getattr(member, "family", None)
    return fam is not None and fam != ENSEMBLE_FAMILY and not str(fam).startswith(_ML_PREFIX)


# ---------------------------------------------------------------------------
# Crossover.
# ---------------------------------------------------------------------------
def crossover_genome(
    a: StrategyGenome, b: StrategyGenome, rng: np.random.Generator
) -> StrategyGenome:
    """Uniform gene-by-gene recombination of two parents.

    Every gene takes one parent's value verbatim (no gene is invented), then the
    coherence repairs run. An ensemble child takes its members from either parent;
    a non-ensemble child carries no members (the 2.1-era scar).
    """
    family = a.family if rng.random() < 0.5 else b.family
    genes: dict = {}
    for bound in GENE_BOUNDS:
        src = a if rng.random() < 0.5 else b
        genes[bound.name] = getattr(src, bound.name)

    genes = _repair_coherence(genes, family)
    genes["family"] = family

    # JUMP 7 — a multi-layer child takes the coordination stack from whichever
    # parent carries one (preferring parent ``a``); a flat pair stays flat.
    if a.layers or b.layers:
        genes["layers"] = tuple(dict(l) for l in (a.layers if a.layers else b.layers))
    else:
        genes["layers"] = ()

    if family == ENSEMBLE_FAMILY:
        pool = []
        for parent in (a, b):
            if parent.family == ENSEMBLE_FAMILY:
                pool.extend(
                    parent.ensemble_members or ()
                )
        concrete = [m for m in pool if _member_is_concrete(m)]
        members, topped_up = _crossover_members(concrete, rng)
        genes["ensemble_members"] = members
        genes["ensemble_min_votes"] = _ensemble_quorum(rng, len(members))
        # R58 — provenance: an ensemble child is elite-sourced only when BOTH
        # parents were elite-sourced AND no fresh random member was needed.
        elite_parents = (a.ensemble_source == "elite" and b.ensemble_source == "elite")
        genes["ensemble_source"] = "elite" if (elite_parents and not topped_up) else "random"
    else:
        genes["ensemble_members"] = ()
        genes["ensemble_source"] = "random"
    return StrategyGenome.from_dict(genes)


def _crossover_members(pool: tuple, rng: np.random.Generator) -> tuple[tuple[dict, ...], bool]:
    """Take a coherent, concrete member set for an ensemble child.

    Members are drawn from the pooled parents (repaired to concrete); if the pool
    is too small, fresh concrete members are drawn so the child is never a
    degenerate (< 2 member) ensemble. Returns ``(members, topped_up)`` — a top-up
    means the child's member set is not wholly parent-sourced (R58 provenance).
    """
    pool_sigs = {StrategyGenome.from_dict(m).signature() for m in pool}
    members: list[dict] = []
    seen: set[str] = set()
    shuffled = list(pool)
    rng.shuffle(shuffled)
    for m in shuffled:
        g = StrategyGenome.from_dict(m)
        if g.family == ENSEMBLE_FAMILY:  # repaired to concrete
            g = random_genome(rng, concrete=True)
        sig = g.signature()
        if sig in seen:
            continue
        seen.add(sig)
        members.append(g.to_dict())
        if len(members) >= ENSEMBLE_MAX_MEMBERS:
            break
    while len(members) < ENSEMBLE_MIN_MEMBERS:
        g = random_genome(rng, concrete=True)
        if g.signature() in seen:
            continue
        seen.add(g.signature())
        members.append(g.to_dict())
    # R55 — the child's members keep DISTINCT families (repair preserves count).
    final = _repair_member_families(members, rng)
    # R58 — provenance is honest by construction: the child is parent-sourced only
    # if EVERY surviving member came from the pool. A top-up OR a family repair
    # that swapped in a fresh member both make it random-sourced.
    parent_sourced = all(
        StrategyGenome.from_dict(m).signature() in pool_sigs for m in final
    )
    return final, not parent_sourced
