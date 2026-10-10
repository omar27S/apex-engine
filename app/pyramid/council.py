"""THE COUNCIL OF SEVEN — the crown authority (Phase 3.1).

Seven seats. Seven future champions ("sette campioni"). The council convenes at
the end of a tournament and performs three acts:

1. **PROMOTION** — it crowns a genome into a seat ONLY if the genome clears the
   lottery-tax bar (R16) *under the CONSERVATIVE cost book* (R20). The book it
   judged under must be the SELECTION book; a result ranked under the reporting
   book is refused (fail-closed), because a gentler book must never crown.
2. **EXILE** (R21) — it records the negative-net genomes the tournament exiled to
   the death ledger (cause ``"friction"``): the leaderboard floor is now also a
   gate.
3. **TRIBUNAL** (R10) — it receives the death summary as the tribunal's evidence
   input, so a family dying systematically is visible to the council, not hidden.

An empty seat is reported as EMPTY (``None``) — never a placeholder, never a
default genome. At MUSTER time, before any genome has cleared the bar, all seven
seats are empty and the council says so in plain language.

Pure: operates on plain rows/dicts or a TournamentResult. No I/O, no services.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping

from app.quant import costs, fitness

__all__ = [
    "SEATS",
    "Champion",
    "CouncilState",
    "convene",
    "survival_certificate",
]

# The seven seats are law (Phase 3.1). Not 6, not 8.
SEATS: int = 7


@dataclass(frozen=True)
class Champion:
    """One crowned genome in a council seat."""

    seat: int
    signature: str
    family: str
    wilson_lb: float
    net_r: float
    trades: int
    book_hash: str  # the SELECTION book that crowned it (R20)
    # R38 (Phase 5) — the RAMS survivability certificate that co-crowned it. Empty
    # when the council is not certificate-required (a legacy, evidence-only call).
    certificate: dict = field(default_factory=dict)


def survival_certificate(signature: str, verdict: dict, *, config_hash: str = "") -> dict:
    """R38+R40+R46 — a content-addressed certificate from a RAMS verdict.

    The certificate binds ``signature`` to its verdict and the sealed thresholds,
    so a seat can never be held without evidence the strategy survived the
    adversary. When the verdict is a MULTI-SEED verdict (R40) the certificate also
    binds the majority ruling, the worst seed and the catastrophic-seed exposure —
    the hash changes iff ANY of that evidence changes. R46 additionally binds the
    SEEN and UNSEEN verdicts SIDE BY SIDE (the crown gate is the UNSEEN verdict).
    Deterministic (sorted JSON).
    """
    majority = verdict.get("majority", {}) or {}
    seen = verdict.get("seen", {}) or {}
    unseen = verdict.get("unseen", {}) or {}
    payload = {
        "signature": str(signature),
        "survives": bool(verdict.get("survives", False)),
        "failed_keys": sorted(verdict.get("failed_keys", [])),
        "thresholds": verdict.get("thresholds", {}),
        "config_hash": str(config_hash),
        # R40 — the majority exposure is part of the evidence.
        "majority_needed": int(majority.get("needed", 0) or 0),
        "majority_survived": int(majority.get("survived", 0) or 0),
        "worst_seed": verdict.get("worst_seed"),
        "catastrophic_seeds": sorted(verdict.get("catastrophic_seeds", []) or []),
        # R46 — seen vs unseen are both part of the evidence.
        "seen_survives": bool(seen.get("survives", False)),
        "unseen_survives": bool(unseen.get("survives", False)),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "signature": str(signature),
        "survives": bool(verdict.get("survives", False)),
        "hash": digest,
        "failed_keys": payload["failed_keys"],
        "rams_config_hash": str(config_hash),
        # R40 — surfaced so the council can name the failing face.
        "majority": dict(majority) if majority else {},
        "worst_seed": verdict.get("worst_seed"),
        "catastrophic_seeds": payload["catastrophic_seeds"],
        # R46 — seen vs unseen verdicts ride side by side.
        "seen": dict(seen),
        "unseen": dict(unseen),
    }


def _certificate_failure_key(cert: dict) -> str:
    """R40 — name WHICH face a failing certificate failed: bar/majority/catastrophic."""
    if not cert:
        return "missing"
    if cert.get("survives", False):
        return ""
    if cert.get("catastrophic_seeds"):
        return "catastrophic"
    majority = cert.get("majority", {}) or {}
    needed = int(majority.get("needed", 0) or 0)
    survived = int(majority.get("survived", 0) or 0)
    if needed and survived < needed:
        return "majority"
    keys = cert.get("failed_keys", []) or []
    if "no_trades" in keys:
        return "no_trades"
    return "bar"


@dataclass(frozen=True)
class CouncilState:
    """The council after it convenes: seats (or empty), plus its three reports."""

    seats: tuple[Champion | None, ...]      # always length SEATS
    promotion_bar: float
    trials: int
    book_hash: str
    book_ok: bool
    promotions: tuple[dict, ...] = ()
    exiles: tuple[dict, ...] = ()
    tribunal: dict = field(default_factory=dict)
    outfit_exposure: tuple[dict, ...] = ()
    notes: tuple[str, ...] = ()
    # R38 (Phase 5) — RAMS survivability certificates (signature -> certificai).
    certificates: tuple[dict, ...] = ()
    require_certificate: bool = False
    certificates_ok: bool = True

    @property
    def crowned(self) -> tuple[Champion, ...]:
        return tuple(s for s in self.seats if s is not None)

    @property
    def empty_seats(self) -> int:
        return sum(1 for s in self.seats if s is None)

    def to_dict(self) -> dict:
        return {
            "seats_total": SEATS,
            "seats_filled": len(self.crowned),
            "empty_seats": self.empty_seats,
            "seats": [
                None if s is None else {
                    "seat": s.seat, "family": s.family, "signature": s.signature,
                    "wilson_lb": s.wilson_lb, "net_r": s.net_r, "trades": s.trades,
                    "certificate": dict(s.certificate),
                }
                for s in self.seats
            ],
            "promotion_bar": self.promotion_bar,
            "trials": self.trials,
            "book_hash": self.book_hash,
            "book_ok": self.book_ok,
            "promotions": list(self.promotions),
            "exiles": list(self.exiles),
            "tribunal": dict(self.tribunal),
            "outfit_exposure": list(self.outfit_exposure),
            "certificates": list(self.certificates),
            "require_certificate": self.require_certificate,
            "certificates_ok": self.certificates_ok,
            "notes": list(self.notes),
        }


def _rows(result) -> list[dict]:
    if isinstance(result, Mapping):
        return list(result.get("leaderboard") or [])
    return list(getattr(result, "leaderboard", []) or [])


def _exposed_signatures(result) -> set[str]:
    if isinstance(result, Mapping):
        exposure = result.get("outfit_exposure") or []
    else:
        exposure = getattr(result, "outfit_exposure", []) or []
    out: set[str] = set()
    for e in exposure:
        if isinstance(e, Mapping):
            out.add(str(e.get("signature", "")))
        else:
            out.add(str(getattr(e, "signature", "")))
    return out


def _death_summary(result) -> dict:
    if isinstance(result, Mapping):
        return dict(result.get("death_summary") or {})
    return dict(getattr(result, "death_summary", {}) or {})


def _book_hash(result) -> str:
    if isinstance(result, Mapping):
        return str(result.get("cost_model_hash", ""))
    return str(getattr(result, "cost_model_hash", ""))


def _trials(result) -> int:
    if isinstance(result, Mapping):
        return int(result.get("trials", 0))
    return int(getattr(result, "trials", 0))


def convene(
    result,
    *,
    bar: float | None = None,
    book: costs.CostModel = costs.SELECTION_COST_MODEL,
    certificates: Mapping | None = None,
    require_certificate: bool = False,
) -> CouncilState:
    """Convene the council on a finished tournament (or its persisted dict).

    ``book`` MUST be a SELECTION book (R20): the council refuses to crown under a
    reporting book, returning all-empty seats with an explanatory note. ``bar``
    defaults to the R16 lottery-tax bar at the run's ``trials``.

    A candidate earns a seat only if ALL hold:

    * it is on the (already net-positive, R21) leaderboard;
    * its ``wilson_lb`` clears ``bar`` under the conservative book (R20);
    * it did NOT appear in the outfit-exposure report (a train hero that failed
      live is not a champion — the walk-forward veto);
    * R38 (Phase 5) — when ``require_certificate`` is set, its RAMS survivability
      certificate (keyed by signature in ``certificates``) exists AND passes. A
      seat can never be held without evidence the strategy survived the adversary.

    Empty seats stay empty. There is no placeholder and no default genome.
    """
    rows = _rows(result)
    book_hash = _book_hash(result)
    trials = _trials(result)
    bar = float(bar if bar is not None else fitness.promotion_bar(trials))
    expected_hash = book.digest()
    certs = dict(certificates or {})

    notes: list[str] = []
    book_ok = True
    # R20 — the council cannot crown under a non-selection book.
    if not costs.is_selection_book(book):
        book_ok = False
        notes.append(
            f"refused: book {book.name!r} is a {book.book!r} book; only the "
            f"CONSERVATIVE (selection) book may crown (R20)"
        )
    if book_hash and book_hash != expected_hash:
        book_ok = False
        notes.append(
            f"refused: run judged under book {book_hash[:16]}… but the council's "
            f"selection book is {expected_hash[:16]}… (R20 fail-closed)"
        )

    exposure_sigs = _exposed_signatures(result)
    death_summary = _death_summary(result)

    # R21 — the exiled are the rows whose net_r <= 0 (they never reach the
    # leaderboard, but the council reports them as its exile act).
    exiles: list[dict] = []
    if isinstance(result, Mapping):
        population = result.get("final_population") or []
    else:
        population = getattr(result, "final_population", []) or []
    for row in population:
        net_r = float(row.get("net_r", 0.0))
        if net_r <= 0.0:
            exiles.append(
                {"signature": str(row.get("signature", "")),
                 "family": str(row.get("family", "")),
                 "net_r": net_r,
                 "cause": "friction"}
            )

    seats: list[Champion | None] = [None] * SEATS
    promotions: list[dict] = []
    certificates_ok = True
    if book_ok:
        seat_idx = 0
        for row in rows:
            if seat_idx >= SEATS:
                break
            sig = str(row.get("signature", ""))
            lb = float(row.get("wilson_lb", 0.0))
            net_r = float(row.get("net_r", 0.0))
            if net_r <= 0.0:
                continue  # R21 floor (defensive; leaderboard is already positive)
            if lb < bar:
                continue  # does not clear the bar
            if sig in exposure_sigs:
                notes.append(
                    f"withheld seat from {row.get('family','?')} ({sig}): train hero, "
                    f"test zero (outfit exposure)"
                )
                continue
            # R38 — a seat needs a passing RAMS survivability certificate when the
            # council is certificate-required. Absent or failing -> refused.
            cert: dict = {}
            if require_certificate:
                cert = dict(certs.get(sig, {}))
                if not cert:
                    certificates_ok = False
                    notes.append(
                        f"withheld seat from {row.get('family','?')} ({sig}): no RAMS "
                        f"survivability certificate (R38 fail-closed)"
                    )
                    continue
                if not cert.get("survives", False):
                    certificates_ok = False
                    face = _certificate_failure_key(cert)
                    extra = ""
                    if face == "majority":
                        mj = cert.get("majority", {}) or {}
                        extra = (f" [majority {mj.get('survived','?')}/"
                                 f"{len(mj.get('seeds', []))} < {mj.get('needed','?')}]")
                    elif face == "catastrophic":
                        extra = f" [catastrophic seeds {cert.get('catastrophic_seeds', [])}]"
                    elif face == "no_trades":
                        extra = " [no trades — fail-closed]"
                    notes.append(
                        f"withheld seat from {row.get('family','?')} ({sig}): did NOT "
                        f"survive RAMS — failed {{{face}}}{extra} (R38/R40)"
                    )
                    continue
            seats[seat_idx] = Champion(
                seat=seat_idx, signature=sig, family=str(row.get("family", "")),
                wilson_lb=lb, net_r=net_r, trades=int(row.get("trades", 0)),
                book_hash=expected_hash, certificate=cert,
            )
            promotions.append(
                {"seat": seat_idx, "family": seats[seat_idx].family, "signature": sig,
                 "wilson_lb": lb, "net_r": net_r,
                 "certificate_hash": cert.get("hash", "")}
            )
            seat_idx += 1

    if require_certificate and not certs and book_ok and rows:
        notes.append("certificate-required but no certificates were supplied (R38)")

    if not promotions and book_ok:
        if not rows:
            notes.append("no candidate reached the leaderboard; all seven seats empty")
        else:
            best = max((float(r.get("wilson_lb", 0.0)) for r in rows), default=0.0)
            if best < bar:
                notes.append(
                    f"no candidate cleared the bar ({bar:.3f}); best LB {best:.3f} — "
                    f"seven empty seats"
                )

    tribunal = {
        "cause_counts": dict(death_summary.get("by_cause", {})),
        "family_counts": dict(death_summary.get("by_family", {})),
        "total": int(death_summary.get("total", 0)),
    }

    return CouncilState(
        seats=tuple(seats),
        promotion_bar=bar,
        trials=trials,
        book_hash=book_hash or expected_hash,
        book_ok=book_ok,
        promotions=tuple(promotions),
        exiles=tuple(exiles),
        tribunal=tribunal,
        outfit_exposure=tuple(
            dict(e) if isinstance(e, Mapping) else {
                "signature": getattr(e, "signature", ""),
                "family": getattr(e, "family", ""),
                "reason": getattr(e, "reason", ""),
            }
            for e in (
                (result.get("outfit_exposure") if isinstance(result, Mapping)
                 else getattr(result, "outfit_exposure", [])) or []
            )
        ),
        notes=tuple(notes),
        certificates=tuple(dict(v) for v in certs.values()),
        require_certificate=bool(require_certificate),
        certificates_ok=bool(certificates_ok),
    )