"""Which model answers: the providers' status, and `LLM_PROVIDER=auto`'s pick (decision 0016).

Order: Dahl, then Groq (each: a key, and room for a real turn right now; decision 0029),
then Ollama (running, model pulled), then the rule-based demo assistant (decision 0025).
`check_providers` reports each provider's state; `app.cli llm-check` shows it and asks the
person starting the app, while `resolve_auto` (the app's own startup, e.g. in Docker) takes
the first usable one without asking. The reasons for each skipped provider are kept (logged
at startup and shown by `/api/health`).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.llm.base import LLMClient, Message, ToolSpec
from app.llm.demo import DemoClient
from app.llm.groq import DahlClient, GroqClient, GroqProbe
from app.llm.ollama import OllamaClient, OllamaProbe

log = logging.getLogger("app.llm")

# A realistic first turn (system prompt + tool specs), built by `app.agent.service.probe_turn`
# and passed in, so this package does not import the agent.
Turn = tuple[list[Message], list[ToolSpec]]

# What to try, and in which order, for each configured provider.
CHAINS: dict[str, tuple[str, ...]] = {
    "auto": ("dahl", "groq", "ollama", "demo"),
    "dahl": ("dahl", "groq", "ollama", "demo"),
    "groq": ("groq", "ollama", "demo"),
    "ollama": ("ollama", "demo"),
    "demo": ("demo",),
    "fake": ("fake",),
}


@dataclass(frozen=True)
class ProviderStatus:
    groq: GroqProbe | None  # None: not in the chain, not checked
    ollama: OllamaProbe | None
    dahl: GroqProbe | None = None

    def _in_order(self) -> tuple[tuple[str, GroqProbe | OllamaProbe | None], ...]:
        return (("dahl", self.dahl), ("groq", self.groq), ("ollama", self.ollama))

    def first_usable(self) -> str:
        for name, probe in self._in_order():
            if probe and probe.usable:
                return name
        return "demo"

    def skipped_before(self, provider: str) -> tuple[str, ...]:
        """Why each provider ahead of `provider` in the order was not used."""
        reasons = []
        for name, probe in self._in_order():
            if name == provider:
                break
            if probe is not None:
                reasons.append(f"{name}: {probe.detail}")
        return tuple(reasons)


def groq_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> GroqClient:
    key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
    return GroqClient(
        key, settings.groq_model, base_url=settings.groq_base_url, transport=transport
    )


def dahl_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> DahlClient:
    key = settings.dahl_api_key.get_secret_value() if settings.dahl_api_key else ""
    return DahlClient(
        key, settings.dahl_model, base_url=settings.dahl_base_url, transport=transport
    )


def ollama_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> OllamaClient:
    return OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        timeout=settings.ollama_timeout_s,
        transport=transport,
    )


def check_groq(
    settings: Settings, turn: Turn | None = None, transport: httpx.BaseTransport | None = None
) -> GroqProbe:
    if not (settings.groq_api_key and settings.groq_api_key.get_secret_value()):
        return GroqProbe("no_key", "no GROQ_API_KEY")
    client = groq_client(settings, transport)
    try:
        return client.probe(*(turn or (None, None)))
    finally:
        client.close()


def check_dahl(
    settings: Settings, turn: Turn | None = None, transport: httpx.BaseTransport | None = None
) -> GroqProbe:
    if not (settings.dahl_api_key and settings.dahl_api_key.get_secret_value()):
        return GroqProbe("no_key", "no DAHL_API_KEY")
    client = dahl_client(settings, transport)
    try:
        return client.probe(*(turn or (None, None)))
    finally:
        client.close()


def check_ollama(settings: Settings, transport: httpx.BaseTransport | None = None) -> OllamaProbe:
    client = ollama_client(settings, transport)
    try:
        return client.probe()
    finally:
        client.close()


def check_providers(
    settings: Settings,
    configured: str | None = None,
    turn: Turn | None = None,
    *,
    groq_transport: httpx.BaseTransport | None = None,
    ollama_transport: httpx.BaseTransport | None = None,
    dahl_transport: httpx.BaseTransport | None = None,
) -> ProviderStatus:
    """Probe the providers in the configured chain. All of them are checked, even when the
    first is usable, so the start script can offer the others as alternatives."""
    order = CHAINS[configured or settings.llm_provider]
    dahl = check_dahl(settings, turn, dahl_transport) if "dahl" in order else None
    groq = check_groq(settings, turn, groq_transport) if "groq" in order else None
    ollama = check_ollama(settings, ollama_transport) if "ollama" in order else None
    return ProviderStatus(groq, ollama, dahl)


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
    turn: Turn | None = None,
    *,
    groq_transport: httpx.BaseTransport | None = None,
    ollama_transport: httpx.BaseTransport | None = None,
    dahl_transport: httpx.BaseTransport | None = None,
) -> Resolution:
    """Resolve once and reuse (the probes cost a request each). Use `reset_auto()` to redo it."""
    global _cached
    with _lock:
        if _cached is None:
            # Each provider is only probed when the ones before it are not usable: no
            # question to ask here.
            dahl = check_dahl(settings, turn, dahl_transport)
            groq = None if dahl.usable else check_groq(settings, turn, groq_transport)
            ahead = dahl.usable or (groq is not None and groq.usable)
            ollama = None if ahead else check_ollama(settings, ollama_transport)
            status = ProviderStatus(groq, ollama, dahl)
            provider = status.first_usable()
            client = (
                dahl_client(settings, dahl_transport)
                if provider == "dahl"
                else _client(provider, settings, groq_transport, ollama_transport)
            )
            _cached = Resolution(client, status.skipped_before(provider))
            log.info("LLM provider (auto): %s", _cached.describe())
        return _cached


def _client(
    provider: str,
    settings: Settings,
    groq_transport: httpx.BaseTransport | None,
    ollama_transport: httpx.BaseTransport | None,
) -> LLMClient:
    if provider == "groq":
        return groq_client(settings, groq_transport)
    if provider == "ollama":
        return ollama_client(settings, ollama_transport)
    return DemoClient()


def current_resolution() -> Resolution | None:
    return _cached


def reset_auto() -> None:
    global _cached
    with _lock:
        _cached = None
