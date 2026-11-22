"""Pick the LLM client from `LLM_PROVIDER`."""

from __future__ import annotations

import threading

from app.core.config import Settings
from app.llm.base import LLMClient, LLMError
from app.llm.demo import DemoClient
from app.llm.fake import FakeClient
from app.llm.fallback import SwitchingClient
from app.llm.resolve import (
    check_groq,
    check_ollama,
    dahl_client,
    groq_client,
    ollama_client,
    resolve_auto,
)

# The cloud providers whose used-up quota or credit moves the session on (decision 0029).
CLOUD = ("dahl", "groq")

_lock = threading.Lock()
_switching: dict[tuple[str, ...], SwitchingClient] = {}
_override: LLMClient | None = None


def make_client(settings: Settings, *, fallback: bool = True) -> LLMClient:
    """`demo` (the rule-based demo assistant, decision 0025), `ollama` (local), `dahl` and
    `groq` (cloud, decisions 0029 and 0012), `auto` (the first of dahl, groq, ollama, demo
    that works; decision 0016), or `fake` (the scripted test double; tests only).

    With `fallback` (the app), a cloud client is wrapped so that a used-up quota or credit
    moves the rest of the session to the next provider that works. One wrapper per process,
    so once switched, later requests do not try it again. Evals pass `fallback=False`:
    explicit is explicit.
    """
    if fallback and _override is not None:  # the user switched in the UI
        return _override
    provider = settings.llm_provider
    if provider == "auto":
        client = resolve_auto(settings).client
        if not fallback or client.provider not in CLOUD:
            return client
        return _shared(("auto", str(id(client))), lambda: client, settings)
    if provider == "ollama":
        return ollama_client(settings)
    if provider in CLOUD:
        build = dahl_client if provider == "dahl" else groq_client
        if not fallback:
            return build(settings)
        secret = getattr(settings, f"{provider}_api_key")
        key = secret.get_secret_value() if secret else ""
        model = getattr(settings, f"{provider}_model")
        ident = (provider, key, model, getattr(settings, f"{provider}_base_url"))
        return _shared(ident, lambda: build(settings), settings)
    if provider == "demo":
        return DemoClient()
    return FakeClient()


def _shared(ident: tuple[str, ...], primary, settings: Settings) -> SwitchingClient:
    with _lock:
        client = _switching.get(ident)
        if client is None:
            first = primary()
            client = SwitchingClient(first, lambda: fallback_client(settings, first.provider))
            _switching[ident] = client
        return client


def fallback_client(settings: Settings, failed: str = "groq") -> LLMClient:
    """Where a session goes when a cloud provider's quota or credit is gone: the next one in
    the chain that works. After Dahl: Groq (if its probe says it can serve), then Ollama if
    ready, else the demo. After Groq: Ollama, else the demo."""
    if failed == "dahl" and check_groq(settings).usable:
        return groq_client(settings)
    if check_ollama(settings).usable:
        return ollama_client(settings)
    return DemoClient()


class SwitchUnavailable(LLMError):
    """The provider asked for cannot serve right now (e.g. Ollama is not running)."""


def switch_options(settings: Settings) -> list[str]:
    """What the UI may offer when a turn is stuck: Ollama if it is ready, and the demo
    model; never the provider already in use."""
    current = make_client(settings).provider
    options = []
    if current != "ollama" and check_ollama(settings).usable:
        options.append("ollama")
    if current != "demo":
        options.append("demo")
    return options


def switch_to(settings: Settings, provider: str) -> LLMClient:
    """The user's choice (`POST /api/llm/switch`): use this provider for the rest of the
    process. No files or SAP are touched, so it is not a gated action."""
    global _override
    if provider == "ollama":
        if not check_ollama(settings).usable:
            raise SwitchUnavailable("Ollama is not running with the model pulled.")
        client: LLMClient = ollama_client(settings)
    elif provider == "demo":
        client = DemoClient()
    else:
        raise SwitchUnavailable(f"Cannot switch to '{provider}'.")
    with _lock:
        _override = client
    return client


def current_override() -> LLMClient | None:
    return _override


def reset_shared() -> None:
    global _override
    with _lock:
        _switching.clear()
        _override = None
