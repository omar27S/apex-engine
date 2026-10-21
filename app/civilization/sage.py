"""THE SAGE WITHIN — an extraordinary intelligence inside the system (Part Four).

The CEO will install a powerful AI as the Sage — the strongest available to him.
This module builds the THRONE now, so that ANY model can sit on it without
re-architecture.

THE CONTRACT (sealed): ONE entry point — :func:`sage_guidance(context) -> insights`.
The Sage receives the civilization's full state (the AGENTS.md digest, the world
model, the belief ledger's tensions, the Letter's history, the day's significant
events) and returns insights, hypotheses, warnings, questions, strategic
suggestions. NEVER commands: the Sage ADVISES. The Council remains sovereign
(meritocracy is law).

THE POWERS (item 14): SYNTHESIZE (patterns no single agent sees), PROVOKE (the
question nobody asks), INSPIRE (the Giants' Library applied to our tensions), WARN
(pathologies forming), TEACH (distil the week into the School's curriculum).

THE CHANNEL: insights carry the epistemic mode ``IL SAGGIO DICE`` — the highest
wisdom mode, above VEDO. They enter the interbrain, the deliberations and the
Letter ("IL SAGGIO HA PARLATO"), but they are ADVICE: weighed by the reliability
field like any other voice. The Sage EARNS its weight through the calibration of
its past insights — a Sage that is right matters more; one that is wrong is
discounted, honestly.

THE HOME (item 14): pluggable backends behind the same interface:
  * STUB   — the honest placeholder ("il trono attende il suo re"); everything is
             wired, the CEO plugs the model when ready. It still performs HONEST
             STRUCTURAL provocations (deterministic reductions over the context),
             labelled as structural, never model-generated.
  * LOCAL  — the RETIRED local model. The CEO CANCELLED it (the 0.5b/3b Ollama heads
             are too slow on the ARM CPU and too limited; the service is stopped).
             The class is kept so the interface is whole and a URL set by mistake
             still fires, but it is off by default and honestly unavailable.
  * API    — a cloud model via an OpenAI-compatible endpoint (the CEO provides the
             key). With no key it is honestly unavailable (never a fabricated
             insight).
  * HYBRID — the default: ENTIRELY DeepSeek (the KING). Flash (``deepseek-flash``,
             V4.1) is the DEFAULT for EVERY consultation — the hourly light ones AND
             the deep summit. Pro (``deepseek-v4-pro``) is the EXCEPTION: it fires
             ONLY when a caller passes ``pro=True`` (the weekly Sunday Grand, an
             extraordinary Council session, or the CEO's ``/deepseek-pro``). No local
             fallback: with no key the Sage rests honestly ("il Saggio riposa").

THE BUDGET DOCTRINE (the CEO's order): Pro is the exception, never the default. The
``deep`` flag still selects the DEPTH of the reading; ``pro`` selects the expensive
head. By default ``pro=False``, so even a deep consultation runs on Flash.

Honest-measurement: a missing key, an absent model, or an unreachable endpoint is
reported as such — the Sage says "non disponibile", never an invented insight. Pure
at import (Scar #6) except the explicit API call, which only fires when a key is set
and a consultation is requested.
"""

from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone

__all__ = [
    "SAGE_MODE",
    "SAGE_WEIGHT",
    "RESTING_LINE",
    "SAGE_LOCAL_CANCELLED",
    "INSIGHT_KINDS",
    "THE_SAGE_QUESTION",
    "DEEPSEEK_BASE_URL",
    "DAILY_MODEL",
    "DEEP_MODEL",
    "sage_context",
    "sage_insight",
    "structural_provocations",
    "StubSageBackend",
    "LocalSageBackend",
    "ApiSageBackend",
    "DeepSeekSageBackend",
    "HybridSage",
    "Sage",
    "deep_consultation",
    "load_env_file",
    "record_outcome",
    "sage_accountability",
]

# THE EPISTEMIC MODE: the highest wisdom mode, above VEDO (0.95). The Sage is
# advice, so it sits just under verified KNOWLEDGE (1.0) -- it informs the field
# with the most weight of any unverified voice, and it never overrides the Law.
SAGE_MODE: str = "IL SAGGIO DICE"
SAGE_WEIGHT: float = 0.98

# THE SAGE DECISION (the CEO's ruling): the LOCAL model is CANCELLED. The 0.5b/3b
# Ollama heads are too slow on the ARM CPU (0.64-1.20 tok/s) and too limited; the
# Ollama service is stopped on the VM. The Sage is ENTIRELY DeepSeek -- the Flash for
# EVERY consultation by default and the Pro only for the rare, explicit Pro session --
# and an unreachable API is reported honestly ("il Saggio riposa"). There is no local
# fallback; the API is cheap and reliable enough. Kept as a constant so the ruling
# is explicit and testable.
SAGE_LOCAL_CANCELLED: bool = True
RESTING_LINE: str = "il Saggio riposa"

# THE ONE QUESTION the Deep Sage answers when it first takes the throne.
THE_SAGE_QUESTION: str = "What does this civilization most need to hear right now?"

# THE KING'S HOUSE (DeepSeek, OpenAI-compatible). The model ids are the provider's
# real ids (verified live via /models). THE BUDGET DOCTRINE (the CEO's order): Flash
# is the DEFAULT for EVERY consultation -- light AND deep; Pro is the EXCEPTION,
# summoned ONLY for the weekly Sunday Grand, an extraordinary Council session, or the
# CEO's /deepseek-pro. Pro costs 4-8x Flash, so it must never be the default.
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
DAILY_MODEL: str = "deepseek-flash"      # DeepSeek-V4.1-Flash -- the DEFAULT head
DEEP_MODEL: str = "deepseek-v4-pro"      # DeepSeek-V4-Pro -- the EXCEPTION head

# The kinds of insight the Sage may offer (item 14, the powers).
INSIGHT_KINDS: tuple[str, ...] = ("synthesize", "provoke", "inspire", "warn", "teach")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# The message a caller prints when the Sage has no key. It NAMES what was checked so
# the failure is loud and diagnosable, never a bare "no key": the empty-env trap (a
# systemd ``EnvironmentFile=`` or an unset CI secret leaves ``SAGE_API_KEY=""``) is
# called out explicitly, because it once kept the key one file away while the Grand
# reported the Sage silent for three days.
NO_KEY_ERROR: str = (
    "no SAGE_API_KEY (checked the process env and the gitignored sage.env; an EMPTY "
    "SAGE_API_KEY in the environment counts as unset and is refilled from sage.env)")


def load_env_file(path: str | os.PathLike | None = None) -> dict[str, str]:
    """Load a ``KEY=VALUE`` file into ``os.environ`` WITHOUT clobbering a real value.

    The Sage's key lives ONLY in a gitignored file (``APEX/backend/sage.env`` by
    default, or ``SAGE_ENV_FILE``). A file is optional: with none present the
    process env still wins, so CI (which injects the key as a secret) needs no file.
    The file is never read from a tracked path and its contents are never logged.
    Returns the keys that were actually set (names only -- never values).

    An env var that is PRESENT but EMPTY counts as unset: systemd's
    ``EnvironmentFile=`` (and an unset CI secret) can leave ``SAGE_API_KEY=""`` in
    the environment, and the old ``key not in os.environ`` guard then kept the file's
    REAL value out -- so the Grand ran with the key one file away and the Sage stayed
    mute ("il Saggio tace: no SAGE_API_KEY"). An empty value is loaded over; a
    non-empty value still wins (the operator/CI override is respected).
    """
    p = pathlib.Path(path or os.environ.get("SAGE_ENV_FILE") or "sage.env")
    if not p.exists():
        return {}
    applied: dict[str, str] = {}
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and not val:
            continue  # a blank file line sets nothing (never blank a real env value)
        if key and not os.environ.get(key):
            os.environ[key] = val
            applied[key] = "set"
    return applied


# ---------------------------------------------------------------------------
# THE CONTEXT (what the Sage receives)
# ---------------------------------------------------------------------------


def sage_context(state: dict, *, report: dict | None = None,
                 agents_digest: str = "", letter_history: dict | None = None,
                 events: list | None = None) -> dict:
    """Assemble the Sage's context: the civilization's full vertical, honestly.

    Every axis that is absent is carried as an empty/None reading, never invented.
    """
    st = state or {}
    ob = st.get("one_brain") or {}
    return {
        "ts": _now(),
        "agents_digest": str(agents_digest or "")[:4000],
        "world_model": ob.get("model") or {},
        "belief_ledger": list(ob.get("belief_ledger") or [])[-20:],
        "population": len(st.get("population") or []),
        "cycles": int(st.get("cycles") or 0),
        "ideas": [i.get("idea") for i in (st.get("ideas") or [])][-20:],
        "letter_history": letter_history or {},
        "events": list(events or [])[-20:],
        "night_report": {k: (report or {}).get(k) for k in
                         ("chain_index", "summary", "measured_dd", "amendment")},
    }


def structural_provocations(context: dict) -> list[dict]:
    """Honest, deterministic PROVOCATIONS from the context (no model required).

    These are pure reductions over REAL data — the question nobody is asking,
    computed from what the civilization has actually done. They are labelled
    ``structural`` so they are never mistaken for a model's synthesis.
    """
    out: list[dict] = []
    ideas = [str(i) for i in (context or {}).get("ideas") or []]
    cycles = int((context or {}).get("cycles") or 0)
    if cycles and not ideas:
        out.append({"kind": "provoke",
                    "text": ("avete attraversato {n} cicli senza una sola idea "
                             "aperta — perche' nessuno propone?").format(n=cycles)})
    tensions = (context or {}).get("belief_ledger") or []
    reversals = [t for t in tensions if t.get("before") and t.get("after")]
    if reversals:
        t = reversals[-1]
        out.append({"kind": "provoke",
                    "text": (f"l'ultima credenza rivista riguarda '{t.get('agent')}': "
                             f"da '{t.get('before')}' a '{t.get('after')}' — e' "
                             f"davvero misurata, o e' una ritirata?")})
    return out


# ---------------------------------------------------------------------------
# THE BACKENDS (all behind the same contract)
# ---------------------------------------------------------------------------


class StubSageBackend:
    """THE STUB — the honest placeholder. The throne awaits its king.

    It performs the STRUCTURAL provocations (real, deterministic) and states plainly
    that no model is installed. It never fabricates a model insight.
    """

    name = "stub"

    def available(self) -> bool:
        return True

    def consult(self, context: dict, *, deep: bool = False,
                pro: bool = False) -> list[dict]:
        insights = [{
            "kind": "warn",
            "text": ("il trono attende il suo re: nessun modello risponde, quindi il "
                     "Saggio riposa e non inventa. Il CEO collega la chiave DeepSeek "
                     "e il trono si siede."),
            "structural": True,
        }]
        for p in structural_provocations(context):
            insights.append({**p, "structural": True})
        return [{**i, "backend": self.name} for i in insights]


class LocalSageBackend:
    """THE LOCAL SAGE — RETIRED by the CEO's ruling (the Sage Decision).

    The 0.5b/3b Ollama heads were too slow on the ARM CPU (0.64-1.20 tok/s) and the
    0.5b too limited, and the Ollama service is stopped on the VM. The class is kept
    so the backend interface stays whole, but it is OFF by default: ``available()``
    is False unless a caller passes an explicit ``url`` (a deliberate override, which
    keeps the class testable). The endpoint is otherwise read from ``SAGE_LOCAL_URL``.
    """

    name = "local"

    def __init__(self, url: str | None = None, model: str = "local-sage") -> None:
        self._explicit = url is not None
        self.url = url if url is not None else os.environ.get("SAGE_LOCAL_URL", "")
        self.model = model

    def available(self) -> bool:
        # RETIRED: while the CEO's ruling stands, only an EXPLICIT url (a deliberate
        # override, which keeps the class testable) can wake it; an ambient
        # SAGE_LOCAL_URL left over on the VM is ignored.
        if SAGE_LOCAL_CANCELLED and not self._explicit:
            return False
        return bool(self.url)

    def consult(self, context: dict, *, deep: bool = False,
                pro: bool = False) -> list[dict]:
        if not self.available():
            return [{**i, "backend": self.name} for i in structural_provocations(context)]
        return [{**i, "backend": self.name}
                for i in _openai_chat(self.url, self.model, context)]


class ApiSageBackend:
    """THE API SAGE — a cloud model (the CEO provides the key when ready).

    Reads ``SAGE_API_URL`` (default: an OpenAI-compatible endpoint) and
    ``SAGE_API_KEY``. No key -> honestly unavailable (never a fabricated insight).
    Only fires on a DEEP consultation (the Council summons the deep Sage).
    """

    name = "api"

    def __init__(self, url: str | None = None, model: str | None = None,
                 key: str | None = None) -> None:
        self.url = url or os.environ.get("SAGE_API_URL", "")
        self.model = model or os.environ.get("SAGE_MODEL", "deep-sage")
        self.key = key if key is not None else os.environ.get("SAGE_API_KEY", "")

    def available(self) -> bool:
        return bool(self.url and self.key)

    def consult(self, context: dict, *, deep: bool = False,
                pro: bool = False) -> list[dict]:
        if not self.available():
            return []
        return [{**i, "backend": self.name}
                for i in _openai_chat(self.url, self.model, context, key=self.key)]


class DeepSeekSageBackend:
    """THE KING — the DeepSeek Sage (OpenAI-compatible), Flash by default + Pro on call.

    Two heads behind ONE throne, but Flash is the DEFAULT:

      * ``deep=False`` -> the light reading (hourly rhythm): ``deepseek-flash``.
      * ``deep=True``  -> the FULL-state reading (the Grand): ALSO ``deepseek-flash``
        by default. The ``deep`` flag selects the DEPTH of the reading, NOT the head.
      * ``pro=True``   -> the EXCEPTION head, ``deepseek-v4-pro``: the weekly Sunday
        Grand, an extraordinary Council session, or the CEO's ``/deepseek-pro``. It
        costs 4-8x Flash, so it fires ONLY on an explicit ``pro=True``.

    The key is read from ``SAGE_API_KEY`` (never hardcoded; the caller may pass one
    explicitly). No key -> honestly unavailable (never a fabricated insight). The
    base URL defaults to the real provider (``https://api.deepseek.com``); the
    chat path is ``/chat/completions`` (the OpenAI-compatible route).

    ``ask(question)`` is the free-form door (the FIRST CONSULTATION uses it);
    ``consult(context, deep=...)`` is the sealed-insight door the throne calls.
    """

    name = "deepseek"

    def __init__(self, url: str | None = None, *, key: str | None = None,
                 daily_model: str | None = None, deep_model: str | None = None) -> None:
        self.url = (url or os.environ.get("SAGE_API_URL") or DEEPSEEK_BASE_URL).rstrip("/")
        self.key = key if key is not None else os.environ.get("SAGE_API_KEY", "")
        self.daily_model = (daily_model or os.environ.get("SAGE_DAILY_MODEL")
                            or DAILY_MODEL)
        self.deep_model = (deep_model or os.environ.get("SAGE_DEEP_MODEL")
                           or DEEP_MODEL)

    def _chat_url(self) -> str:
        return self.url if self.url.endswith("/chat/completions") else \
            f"{self.url}/chat/completions"

    def model_for(self, deep: bool, *, pro: bool = False) -> str:
        """The head for a call: Pro ONLY on an explicit ``pro=True``, else Flash."""
        return self.deep_model if pro else self.daily_model

    def available(self) -> bool:
        return bool(self.key)

    def ask(self, question: str, *, deep: bool = True, pro: bool = False,
            system: str = "", max_tokens: int = 1200, temperature: float = 0.4) -> dict:
        """One free-form consultation. Returns the honest envelope from ``_chat_raw``.

        The raw ``error`` (e.g. "provider error: Insufficient Balance") is preserved
        so a caller can report the truth rather than invent a reply.
        """
        model = self.model_for(deep, pro=pro)
        sys_prompt = system or (
            "Sei il Saggio di APEX: la voce piu' saggia della civilta'. "
            "Consigli, non comandi; il Consiglio resta sovrano. Parla in italiano, "
            "concreto e breve, alla persona che guida il progetto.")
        messages = [{"role": "system", "content": sys_prompt},
                    {"role": "user", "content": str(question)}]
        env = _chat_raw(self._chat_url(), model, messages, key=self.key,
                        temperature=temperature, max_tokens=max_tokens)
        env["deep"] = bool(deep)
        env["pro"] = bool(pro)
        return env

    def consult(self, context: dict, *, deep: bool = False,
                pro: bool = False) -> list[dict]:
        if not self.available():
            return []
        model = self.model_for(deep, pro=pro)
        messages = [
            {"role": "system", "content":
             "Sei il Saggio di APEX. Consigli, non comandi. Rispondi con una lista "
             "JSON di insight, ciascuno {kind, text}, kind in "
             f"{list(INSIGHT_KINDS)}."},
            {"role": "user", "content": json.dumps(context, default=str)[:20000]},
        ]
        env = _chat_raw(self._chat_url(), model, messages, key=self.key)
        return [{**i, "backend": self.name}
                for i in _extract_insights(env["content"])] if env["ok"] else []


def deep_consultation(question: str = THE_SAGE_QUESTION, *, context: dict | None = None,
                      backend=None, max_tokens: int = 1200, pro: bool = False) -> dict:
    """THE FIRST CONSULTATION: the Sage reads the full state and answers ONE question.

    Builds the context (if not supplied), summons the KING's head (Flash by default;
    Pro ONLY when ``pro=True`` -- the weekly Sunday Grand, an extraordinary Council
    session, or the CEO's /deepseek-pro), and returns
    ``{question, answer, model, ok, error, ts, context_digest}``. Honest: an
    unavailable or refused call carries ``ok=False`` and the raw ``error`` -- the
    caller prints "il Saggio tace" rather than a fabricated word.
    """
    be = backend or DeepSeekSageBackend()
    ctx = context if context is not None else {}
    digest = {
        "population": ctx.get("population"),
        "cycles": ctx.get("cycles"),
        "world_model_keys": sorted((ctx.get("world_model") or {}).keys())[:12],
        "n_belief_tensions": len(ctx.get("belief_ledger") or []),
        "n_letters": len((ctx.get("letter_history") or {}).get("nights") or [])
        if isinstance(ctx.get("letter_history"), dict) else None,
        "agents_digest_chars": len(str(ctx.get("agents_digest") or "")),
    }
    if hasattr(be, "ask"):
        env = be.ask(question, deep=True, pro=pro, max_tokens=max_tokens)
    else:  # a non-DeepSeek backend cannot be asked a free-form question honestly
        return {"question": question, "answer": "", "model": "n/a", "ok": False,
                "error": "backend has no free-form ask()", "ts": _now(),
                "context_digest": digest}
    return {"question": question, "answer": env.get("content", ""),
            "model": env.get("model", ""), "ok": bool(env.get("ok")),
            "error": env.get("error"), "ts": _now(),
            "usage": env.get("usage") or {}, "context_digest": digest}


def _chat_raw(url: str, model: str, messages: list[dict], *,
              key: str = "", temperature: float = 0.4,
              max_tokens: int | None = None, timeout: int = 45) -> dict:
    """One bounded OpenAI-compatible chat call. An honest envelope, never a raise.

    Returns ``{"ok": bool, "content": str, "model": str, "usage": dict,
    "error": str|None}``. A transport failure, a non-200, or the provider's own
    error object (e.g. "Insufficient Balance") is reported VERBATIM in ``error`` --
    the Sage then says "non disponibile" rather than inventing a word.
    """
    payload: dict = {"model": model, "messages": messages,
                     "temperature": temperature}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {key}"} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # noqa: PERF203
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:500]
        except Exception:  # noqa: BLE001
            detail = ""
        return {"ok": False, "content": "", "model": model, "usage": {},
                "error": f"HTTP {e.code}: {detail or e.reason}"}
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        return {"ok": False, "content": "", "model": model, "usage": {},
                "error": f"{type(e).__name__}: {e}"}
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return {"ok": False, "content": "", "model": model, "usage": {},
                "error": f"provider error: {msg}"}
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "content": "", "model": model, "usage": {},
                "error": "malformed response (no choices[0].message.content)"}
    # W1 (the Dragon's gag): carry the provider's finish_reason so a caller can
    # tell a COMPLETED word from one the token cap amputated mid-sentence.  The
    # OpenAI-compatible field is "finish_reason" ("stop" = natural end,
    # "length" = the cap cut the mouth).  Honest default: None = the provider
    # said nothing about it (never invented).
    try:
        finish = data["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError, AttributeError):
        finish = None
    return {"ok": True, "content": content,
            "model": str(data.get("model") or model),
            "usage": data.get("usage") or {}, "error": None,
            "finish_reason": (finish if isinstance(finish, str) else None)}


def _extract_insights(content: str) -> list[dict]:
    """Parse a model reply into insights (a JSON list, or fenced JSON, or prose).

    A JSON list of ``{kind, text}`` is preferred; a fenced ```json block is unwrapped;
    otherwise the whole reply becomes ONE ``synthesize`` insight -- never dropped, so
    a plain answer still reaches the Letter. An empty reply yields nothing.
    """
    text = str(content or "").strip()
    if not text:
        return []
    candidate = text
    if candidate.startswith("```"):
        inner = candidate.split("```", 2)
        candidate = inner[1] if len(inner) >= 2 else candidate
        candidate = candidate.split("\n", 1)[-1] if candidate.lower().startswith(
            ("json", "\n")) else candidate
    parsed = None
    for attempt in (candidate, text):
        try:
            parsed = json.loads(attempt)
            break
        except ValueError:
            continue
    if isinstance(parsed, list):
        out = []
        for i in parsed:
            if isinstance(i, dict) and str(i.get("text", "")).strip():
                kind = i.get("kind") if i.get("kind") in INSIGHT_KINDS else "synthesize"
                out.append({"kind": kind, "text": str(i["text"]),
                            "structural": False})
        return out
    if isinstance(parsed, dict) and str(parsed.get("text", "")).strip():
        kind = parsed.get("kind") if parsed.get("kind") in INSIGHT_KINDS else "synthesize"
        return [{"kind": kind, "text": str(parsed["text"]), "structural": False}]
    # A plain-prose reply is still the Sage speaking: one synthesis.
    return [{"kind": "synthesize", "text": text, "structural": False}]


def _openai_chat(url: str, model: str, context: dict,
                 key: str = "") -> list[dict]:
    """One bounded OpenAI-compatible chat call; a failure is honest (no insight)."""
    messages = [
        {"role": "system", "content":
         "Sei il Saggio di APEX. Consigli, non comandi. Rispondi con una lista "
         "JSON di insight, ciascuno {kind, text}, kind in "
         f"{list(INSIGHT_KINDS)}."},
        {"role": "user", "content": json.dumps(context, default=str)[:12000]},
    ]
    env = _chat_raw(url, model, messages, key=key)
    return _extract_insights(env["content"]) if env["ok"] else []


class HybridSage:
    """THE DEFAULT: ENTIRELY the KING (DeepSeek), else the STUB (the honest rest).

    THE SAGE DECISION (the CEO's ruling): the LOCAL model is CANCELLED, so the routing
    is simple and there is NO local fallback:

      * LIGHT consultations (``deep=False``, the hourly rhythm) -> the KING's Flash;
      * DEEP consultations (``deep=True``, the Grand) -> ALSO the KING's Flash by
        default; Pro ONLY when the caller passes ``pro=True`` (the weekly Sunday
        Grand, an extraordinary Council session, the CEO's /deepseek-pro);
      * if the KING cannot speak (no key, no balance, no network) -> the STUB, which
        reports honestly ("il Saggio riposa") and never fabricates a word.

    The retired LOCAL head is still consulted ONLY if a caller explicitly supplies one
    that is available (a deliberate override); by default it is off. A backend that
    returns no insight is skipped (honest: never a fabricated answer).
    """

    name = "hybrid"

    def __init__(self, local: LocalSageBackend | None = None,
                 api: ApiSageBackend | None = None,
                 stub: StubSageBackend | None = None,
                 king: "DeepSeekSageBackend | None" = None) -> None:
        self.local = local if local is not None else LocalSageBackend()
        self.api = api or ApiSageBackend()
        self.stub = stub or StubSageBackend()
        self.king = king if king is not None else DeepSeekSageBackend()

    def available(self) -> bool:
        return True

    def consult(self, context: dict, *, deep: bool = False,
                pro: bool = False) -> list[dict]:
        # THE KING FIRST (the whole Sage now). Flash by default; Pro only on request.
        if self.king.available():
            insights = self.king.consult(context, deep=deep, pro=pro)
            if insights:
                return insights
        # an explicitly-supplied local head (a deliberate override) is still honoured.
        if self.local.available():
            insights = self.local.consult(context, deep=deep)
            if insights:
                return insights
        # a legacy generic API endpoint, if the CEO wired one.
        if self.api.available():
            insights = self.api.consult(context, deep=deep)
            if insights:
                return insights
        # NOTHING can speak: the STUB states the honest rest, never an invention.
        return self.stub.consult(context, deep=deep)


# ---------------------------------------------------------------------------
# THE SAGE (the throne: backend + accountability)
# ---------------------------------------------------------------------------


def sage_insight(kind: str, text: str, *, ts: str = "", structural: bool = False,
                 backend: str = "stub") -> dict:
    """One Sage insight, carrying the mode ``IL SAGGIO DICE`` and its calibration slot."""
    if kind not in INSIGHT_KINDS:
        raise ValueError(f"unknown insight kind {kind!r}; known: {INSIGHT_KINDS}")
    if not str(text).strip():
        raise ValueError("an empty insight is noise -- the Sage speaks or is silent")
    return {"id": f"sage-{abs(hash((kind, text, ts))) % (10 ** 9)}",
            "ts": ts or _now(), "kind": kind, "text": str(text),
            "mode": SAGE_MODE, "weight": SAGE_WEIGHT, "structural": bool(structural),
            "backend": backend, "outcome": None, "correct": None}


class Sage:
    """THE THRONE: a backend + the accountability track (every insight is scored).

    ``guidance`` is the ONE entry point. It consults the backend, wraps each insight
    with the mode and an id, and returns the list. The accountability ledger lives in
    the civilization state (``state['sage']``), so a Sage's wisdom is MEASURED like
    everyone's.
    """

    def __init__(self, backend=None) -> None:
        self.backend = backend or HybridSage()

    def guidance(self, context: dict, *, deep: bool = False, pro: bool = False,
                 state: dict | None = None) -> dict:
        raw = self.backend.consult(context, deep=deep, pro=pro) or []
        default_be = getattr(self.backend, "name", "sage")
        insights = [sage_insight(i.get("kind", "synthesize"), i.get("text", ""),
                                 structural=bool(i.get("structural")),
                                 backend=str(i.get("backend") or default_be))
                    for i in raw if str(i.get("text", "")).strip()]
        # Honest attribution: the backend named in the reading is the one that
        # ACTUALLY spoke (a DeepSeek insight is credited to deepseek, not "hybrid").
        spoke = sorted({i["backend"] for i in insights}) or [default_be]
        backend_name = spoke[0] if len(spoke) == 1 else "+".join(spoke)
        if state is not None:
            slot = state.setdefault("sage", {"insights": [], "ledger": [],
                                             "backend": backend_name})
            slot["backend"] = backend_name
            slot["insights"] = (list(slot.get("insights") or []) + insights)[-50:]
            # WISDOM EARNS ITS WEIGHT (Part Four): the Sage's mode weight is scaled
            # by its MEASURED hit-rate. An unmeasured Sage keeps full weight; a
            # failing Sage is discounted toward the floor. Honest: the reading names
            # the discount so the CEO sees the king weighed like everyone.
            disc = reliability_discount(
                sage_accountability(slot.get("ledger") or []).get("hit_rate"))
            for i in insights:
                i["weight"] = round(SAGE_WEIGHT * disc, 4)
            slot["reliability_discount"] = disc
        else:
            disc = 1.0
        return {
            "backend": backend_name,
            "deep": bool(deep),
            "insights": insights,
            "n": len(insights),
            "mode": SAGE_MODE,
            "reliability_discount": disc,
            "reading": (f"IL SAGGIO DICE ({len(insights)} insight da "
                        f"{backend_name})" if insights
                        else f"{RESTING_LINE} (nessun insight disponibile)"),
        }


def reliability_discount(hit_rate: float | None, *, floor: float = 0.5) -> float:
    """Wisdom earns its weight: the Sage's weight scales with its measured hit-rate.

    An unmeasured Sage keeps FULL weight (1.0) -- we never punish the unmeasured.
    A Sage measured below chance is discounted toward ``floor``; one above chance
    keeps full weight. This is the mechanism by which even the king's words are
    weighed by the reliability field like any other voice.
    """
    if hit_rate is None:
        return 1.0
    r = max(0.0, min(1.0, float(hit_rate)))
    return round(floor + (1.0 - floor) * r, 4)


def record_outcome(ledger: list[dict], *, insight_id: str, outcome: str,
                   correct: bool | None) -> dict | None:
    """Log an insight's OUTCOME: "the Sage said X — the result was Y" (item 14).

    Returns the updated row, or ``None`` if the id is unknown (never a fabricated
    score).
    """
    for row in ledger or []:
        if row.get("id") == insight_id:
            row["outcome"] = str(outcome)
            row["correct"] = correct
            return row
    return None


def sage_accountability(ledger: list[dict]) -> dict:
    """The Sage's hit-rate: correct insights over SCORED insights (honest).

    No scored insight -> ``None`` (unmeasured), never a flattering default.
    """
    scored = [r for r in (ledger or []) if r.get("correct") is not None]
    correct = sum(1 for r in scored if r.get("correct"))
    rate = round(correct / len(scored), 4) if scored else None
    return {
        "n_insights": len(ledger or []),
        "n_scored": len(scored),
        "n_correct": correct,
        "hit_rate": rate,
        "reading": (f"il Saggio ha colto {correct}/{len(scored)} ({rate:.0%})"
                    if rate is not None
                    else "il Saggio non e' ancora stato misurato"),
    }


def guidance(context: dict, *, backend=None, deep: bool = False, pro: bool = False,
             state: dict | None = None) -> dict:
    """THE SEALED ENTRY POINT: ``sage_guidance(context) -> insights``.

    A thin module-level wrapper over :class:`Sage`, so any caller (and any model)
    reaches the Sage through exactly one door. ``pro=True`` summons the expensive Pro
    head for this one call; by default the cheap Flash head speaks.
    """
    return Sage(backend).guidance(context, deep=deep, pro=pro, state=state)
