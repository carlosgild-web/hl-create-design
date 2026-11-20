"""`LLM_PROVIDER=auto`: pick the best provider that works right now, once per process.

Order: Groq (a key and quota left), then Ollama (running, model pulled), then the scripted
demo model. The reasons for each skipped provider are kept, so the person starting the app
can see why (logged at startup and shown by `/api/health`).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.groq import GroqClient
from app.llm.ollama import OllamaClient

log = logging.getLogger("app.llm")


@dataclass(frozen=True)
class Resolution:
    client: LLMClient
    skipped: tuple[str, ...]  # why a better provider was not used

    @property
    def provider(self) -> str:
        return self.client.provider

    def describe(self) -> str:
        text = f"{self.provider} ({self.client.model})"
        return text + (f"; skipped: {'; '.join(self.skipped)}" if self.skipped else "")


_lock = threading.Lock()
_cached: Resolution | None = None


def resolve_auto(
    settings: Settings,
    *,
    groq_transport: httpx.BaseTransport | None = None,
    ollama_transport: httpx.BaseTransport | None = None,
) -> Resolution:
    """Resolve once and reuse (the probes cost a request each). Use `reset_auto()` to redo it."""
    global _cached
    with _lock:
        if _cached is None:
            _cached = _probe_in_order(settings, groq_transport, ollama_transport)
            log.info("LLM provider (auto): %s", _cached.describe())
        return _cached


def current_resolution() -> Resolution | None:
    return _cached


def reset_auto() -> None:
    global _cached
    with _lock:
        _cached = None


def _probe_in_order(
    settings: Settings,
    groq_transport: httpx.BaseTransport | None,
    ollama_transport: httpx.BaseTransport | None,
) -> Resolution:
    skipped: list[str] = []

    key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
    if key:
        groq = GroqClient(
            key, settings.groq_model, base_url=settings.groq_base_url, transport=groq_transport
        )
        ok, note = groq.probe()
        if ok:
            return Resolution(groq, tuple(skipped))
        groq.close()
        skipped.append(f"groq: {note}")
    else:
        skipped.append("groq: no GROQ_API_KEY")

    local = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        timeout=settings.ollama_timeout_s,
        transport=ollama_transport,
    )
    ok, note = local.probe()
    if ok:
        return Resolution(local, tuple(skipped))
    local.close()
    skipped.append(f"ollama: {note}")

    return Resolution(FakeClient(), tuple(skipped))
