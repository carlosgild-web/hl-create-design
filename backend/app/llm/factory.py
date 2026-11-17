"""Pick the LLM client from `LLM_PROVIDER`."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import LLMClient, LLMError
from app.llm.fake import FakeClient
from app.llm.ollama import OllamaClient


def make_client(settings: Settings) -> LLMClient:
    """`fake` (demo mode), `ollama` (local). `anthropic` arrives in Phase 7 (decision 0009)."""
    if settings.llm_provider == "ollama":
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    if settings.llm_provider == "anthropic":
        raise LLMError(
            "LLM_PROVIDER=anthropic is planned for the online demo (Phase 7, decision 0009). "
            "Use LLM_PROVIDER=ollama to run the assistant locally."
        )
    return FakeClient()
