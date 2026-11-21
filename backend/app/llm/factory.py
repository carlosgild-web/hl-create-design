"""Pick the LLM client from `LLM_PROVIDER`."""

from __future__ import annotations

import threading

from app.core.config import Settings
from app.llm.base import LLMClient, LLMError
from app.llm.demo import DemoClient
from app.llm.fake import FakeClient
from app.llm.fallback import SwitchingClient
from app.llm.resolve import check_ollama, groq_client, ollama_client, resolve_auto

_lock = threading.Lock()
_switching: dict[tuple[str, ...], SwitchingClient] = {}
_override: LLMClient | None = None


def make_client(settings: Settings, *, fallback: bool = True) -> LLMClient:
    """`demo` (the rule-based demo assistant, decision 0025), `ollama` (local), `groq`
    (cloud, decision 0012), `auto` (the first of groq, ollama, demo that works; decision
    0016), or `fake` (the scripted test double; tests only).

    With `fallback` (the app), Groq is wrapped so that a used-up daily quota moves the rest
    of the session to Ollama or the demo model. One wrapper per process, so once switched,
    later requests do not try Groq again. Evals pass `fallback=False`: explicit is explicit.
    """
    if fallback and _override is not None:  # the user switched in the UI
        return _override
    provider = settings.llm_provider
    if provider == "auto":
        client = resolve_auto(settings).client
        if not fallback or client.provider != "groq":
            return client
        return _shared(("auto", str(id(client))), lambda: client, settings)
    if provider == "ollama":
        return ollama_client(settings)
    if provider == "groq":
        if not fallback:
            return groq_client(settings)
        key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
        ident = ("groq", key, settings.groq_model, settings.groq_base_url)
        return _shared(ident, lambda: groq_client(settings), settings)
    if provider == "demo":
        return DemoClient()
    return FakeClient()


def _shared(ident: tuple[str, ...], primary, settings: Settings) -> SwitchingClient:
    with _lock:
        client = _switching.get(ident)
        if client is None:
            client = SwitchingClient(primary(), lambda: fallback_client(settings))
            _switching[ident] = client
        return client


def fallback_client(settings: Settings) -> LLMClient:
    """Where a session goes when Groq's quota is gone: Ollama if ready, else the demo."""
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
