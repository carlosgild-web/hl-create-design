"""Which model answers: the providers' status, and `LLM_PROVIDER=auto`'s pick (decision 0016).

Order: Groq (a key, and quota for a real turn right now), then Ollama (running, model
pulled), then the rule-based demo assistant (decision 0025). `check_providers` reports each
provider's state;
`app.cli llm-check` shows it and asks the person starting the app, while `resolve_auto` (the
app's own startup, e.g. in Docker) takes the first usable one without asking. The reasons
for each skipped provider are kept (logged at startup and shown by `/api/health`).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.llm.base import LLMClient, Message, ToolSpec
from app.llm.demo import DemoClient
from app.llm.groq import GroqClient, GroqProbe
from app.llm.ollama import OllamaClient, OllamaProbe

log = logging.getLogger("app.llm")

# A realistic first turn (system prompt + tool specs), built by `app.agent.service.probe_turn`
# and passed in, so this package does not import the agent.
Turn = tuple[list[Message], list[ToolSpec]]

# What to try, and in which order, for each configured provider.
CHAINS: dict[str, tuple[str, ...]] = {
    "auto": ("groq", "ollama", "demo"),
    "groq": ("groq", "ollama", "demo"),
    "ollama": ("ollama", "demo"),
    "demo": ("demo",),
    "fake": ("fake",),
}


@dataclass(frozen=True)
class ProviderStatus:
    groq: GroqProbe | None  # None: not in the chain, not checked
    ollama: OllamaProbe | None

    def first_usable(self) -> str:
        if self.groq and self.groq.usable:
            return "groq"
        if self.ollama and self.ollama.usable:
            return "ollama"
        return "demo"

    def skipped_before(self, provider: str) -> tuple[str, ...]:
        """Why each provider ahead of `provider` in the order was not used."""
        reasons = []
        for name, probe in (("groq", self.groq), ("ollama", self.ollama)):
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
) -> ProviderStatus:
    """Probe the providers in the configured chain. Ollama is checked even when Groq is
    usable, so the start script can offer it as the alternative."""
    order = CHAINS[configured or settings.llm_provider]
    groq = check_groq(settings, turn, groq_transport) if "groq" in order else None
    ollama = check_ollama(settings, ollama_transport) if "ollama" in order else None
    return ProviderStatus(groq, ollama)


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
) -> Resolution:
    """Resolve once and reuse (the probes cost a request each). Use `reset_auto()` to redo it."""
    global _cached
    with _lock:
        if _cached is None:
            # Ollama is only probed when Groq is not usable: no question to ask here.
            groq = check_groq(settings, turn, groq_transport)
            ollama = None if groq.usable else check_ollama(settings, ollama_transport)
            status = ProviderStatus(groq, ollama)
            provider = status.first_usable()
            _cached = Resolution(
                _client(provider, settings, groq_transport, ollama_transport),
                status.skipped_before(provider),
            )
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
