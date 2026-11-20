"""Pick the LLM client from `LLM_PROVIDER`."""

from __future__ import annotations

import threading

from app.core.config import Settings
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.fallback import SwitchingClient
from app.llm.resolve import check_ollama, groq_client, ollama_client, resolve_auto

_lock = threading.Lock()
_switching: dict[tuple[str, ...], SwitchingClient] = {}


def make_client(settings: Settings, *, fallback: bool = True) -> LLMClient:
    """`fake` (demo mode), `ollama` (local), `groq` (cloud, decision 0012), or `auto`
    (the first of groq, ollama, fake that works; decision 0016).

    With `fallback` (the app), Groq is wrapped so that a used-up daily quota moves the rest
    of the session to Ollama or the demo model. One wrapper per process, so once switched,
    later requests do not try Groq again. Evals pass `fallback=False`: explicit is explicit.
    """
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
    return FakeClient()


def reset_shared() -> None:
    with _lock:
        _switching.clear()
