"""Pick the LLM client from `LLM_PROVIDER`."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.groq import GroqClient
from app.llm.ollama import OllamaClient


def make_client(settings: Settings) -> LLMClient:
    """`fake` (demo mode), `ollama` (local), `groq` (cloud, decision 0012)."""
    if settings.llm_provider == "ollama":
        return OllamaClient(
            settings.ollama_base_url, settings.ollama_model, timeout=settings.ollama_timeout_s
        )
    if settings.llm_provider == "groq":
        key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
        return GroqClient(key, settings.groq_model, base_url=settings.groq_base_url)
    return FakeClient()
