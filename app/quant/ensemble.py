"""ENSEMBLE VOTING — quorum over member strategies.

An :class:`EnsembleStrategy` holds concrete member genomes (never ensembles
themselves — enforced recursively), a trailing ``window`` for bias, and an
explicit integer ``min_votes``.

R3 — ENSEMBLE QUORUM DOCTRINE. ``min_votes`` is ALWAYS an explicit integer >= 2,
gene-bounded, and clamped to the member count. There is NO zero-means-unanimity
encoding. Unanimity is reachable only as ``min_votes == n_members``, a value the
GA may pick — never a trap the seeds fall into.

A member is *long-biased at bar t* if it fired long within the trailing window
and has not fired short after that (mirror for short). The ensemble fires long at
``t`` iff at least one member fires a FRESH long at ``t`` AND the count of
long-biased members at ``t`` is at least the effective quorum.
"""

from __future__ import annotations

import numpy as np

from app.quant.signals import SignalContext, dispatch

__all__ = ["EnsembleStrategy", "effective_quorum", "MIN_QUORUM"]


# Gene bounds for the quorum (kept in sync with genome.GENE_BOUNDS).
MIN_QUORUM = 2
MAX_QUORUM = 20


def effective_quorum(min_votes: int, n_members: int) -> int:
    """Clamp the declared quorum into ``[MIN_QUORUM, n_members]``.

    Fail-closed on nonsense: a non-integer or sub-minimum value is raised to
    ``MIN_QUORUM``; the result never exceeds the member count.
    """
    if n_members < MIN_QUORUM:
        return n_members  # a 1-member ensemble is not a quorum; caller should reject
    try:
        q = int(min_votes)
    except (TypeError, ValueError):
        q = MIN_QUORUM
    return max(MIN_QUORUM, min(q, n_members))


def _is_ensemble(genome) -> bool:
    return getattr(genome, "family", None) == "ensemble"


def _contains_ensemble(genome, seen: set | None = None) -> bool:
    """Recursively check whether ``genome`` or any member is an ensemble."""
    if _is_ensemble(genome):
        return True
    for member in getattr(genome, "ensemble_members", ()) or ():
        from app.quant.genome import StrategyGenome

        sub = member if hasattr(member, "family") else StrategyGenome.from_dict(member)
        if _contains_ensemble(sub):
            return True
    return False


def _bias_state(fired: np.ndarray, opposite: np.ndarray, window: int) -> np.ndarray:
    """Per-bar bias: fired same-side within the trailing window and no later opposite.

    ``out[i]`` is True iff some ``j`` in ``(i-window, i]`` has ``fired[j]`` and no
    ``k`` in ``(j, i]`` has ``opposite[k]``. Strictly causal and vectorized with
    running timestamps of the last same/opposite fire.
    """
    n = len(fired)
    out = np.zeros(n, dtype=bool)
    last_same = -10**9
    last_opp = -10**9
    for i in range(n):
        if fired[i]:
            last_same = i
        if opposite[i]:
            last_opp = i
        out[i] = (last_same > last_opp) and (i - last_same < window)
    return out


class EnsembleStrategy:
    """A quorum of concrete member strategies over one shared context."""

    def __init__(self, members, window: int, min_votes: int):
        if len(members) < 2:
            raise ValueError("an ensemble needs at least two members")
        for member in members:
            if _contains_ensemble(member):
                raise ValueError(
                    "nested ensembles are forbidden (R3): members must be "
                    "concrete, non-ensemble strategies"
                )
        self.members = list(members)
        self.window = int(window)
        if self.window < 1:
            raise ValueError("ensemble window must be >= 1 bar")
        self.min_votes = int(min_votes)
        self.quorum = effective_quorum(self.min_votes, len(self.members))

    # -- convenience --------------------------------------------------------
    @classmethod
    def from_genome(cls, genome) -> "EnsembleStrategy":
        """Build from a genome whose ``ensemble_members`` hold member dicts."""
        from app.quant.genome import StrategyGenome

        members = [
            m if hasattr(m, "family") else StrategyGenome.from_dict(m)
            for m in (genome.ensemble_members or ())
        ]
        return cls(members, genome.ensemble_window, genome.ensemble_min_votes)

    # -- core ---------------------------------------------------------------
    def member_signals(self, ctx: SignalContext):
        """Dispatch each member; returns a list of ``(long, short)`` masks.

        R59 — when ``ctx.vote_cache`` is set, each member's masks are read
        through the cache keyed on ``(member signature, pair, world seed, slice
        identity)``; a warm member is FREE (the elite-soup members were already
        judged as singles). A cache collision raises (fail-closed).
        """
        cache = getattr(ctx, "vote_cache", None)
        if cache is None:
            return [self._dispatch_member(member, ctx) for member in self.members]
        from app.quant.vote_cache import member_vote_key, slice_identity

        slice_id = slice_identity(ctx.frames)
        world_seed = int(getattr(ctx, "world_seed", 0))
        out = []
        for member in self.members:
            sig = member.signature()
            key = member_vote_key(member, ctx.pair, world_seed, slice_id)

            def _compute(member=member):
                long_m, short_m, _ = dispatch(member, ctx)
                return long_m, short_m, {}, {}

            long_m, short_m, _counts, _extra = cache.get_or_compute(
                key, sig, _compute)
            out.append((np.asarray(long_m, bool), np.asarray(short_m, bool)))
        return out

    @staticmethod
    def _dispatch_member(member, ctx: SignalContext):
        long_m, short_m, _ = dispatch(member, ctx)
        return (np.asarray(long_m, bool), np.asarray(short_m, bool))

    def signals(self, genome, ctx: SignalContext):
        """Ensemble masks plus the funnel from member dispatch.

        Returns ``(long, short, funnel_counts)`` where ``funnel_counts`` maps the
        ensemble stages (``member_long_biased``, ``fresh_long``, ``quorum_long``,
        and the short mirrors) to integer counts.
        """
        n = len(ctx.frames)
        sigs = self.member_signals(ctx)
        long_bias = np.zeros(n, dtype=bool)
        short_bias = np.zeros(n, dtype=bool)
        fresh_long = np.zeros(n, dtype=bool)
        fresh_short = np.zeros(n, dtype=bool)
        for long_m, short_m in sigs:
            long_bias |= _bias_state(long_m, short_m, self.window)
            short_bias |= _bias_state(short_m, long_m, self.window)
            fresh_long |= long_m
            fresh_short |= short_m

        long_votes = np.zeros(n, dtype=np.int64)
        short_votes = np.zeros(n, dtype=np.int64)
        for long_m, short_m in sigs:
            long_votes += _bias_state(long_m, short_m, self.window).astype(np.int64)
            short_votes += _bias_state(short_m, long_m, self.window).astype(np.int64)

        long_out = fresh_long & (long_votes >= self.quorum)
        short_out = fresh_short & (short_votes >= self.quorum)
        counts = {
            "member_long_biased": int(np.count_nonzero(long_bias)),
            "member_short_biased": int(np.count_nonzero(short_bias)),
            "fresh_long": int(np.count_nonzero(fresh_long)),
            "fresh_short": int(np.count_nonzero(fresh_short)),
            "quorum_long": int(np.count_nonzero(long_out)),
            "quorum_short": int(np.count_nonzero(short_out)),
        }
        return long_out, short_out, counts
