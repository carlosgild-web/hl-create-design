"""Keep the assistant answering when Groq's daily quota runs out mid-session (decision 0016).

`SwitchingClient` wraps the Groq client. When a call fails with `QuotaExhausted`, it moves to
Ollama (if it is running with the model pulled) or to the scripted demo model, repeats the
same call there, and stays on it for the rest of the process. The switch is reported once
through `take_notice()`, which the agent loop turns into a `notice` event and a trace step.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from app.llm.base import ChatTurn, LLMClient, Message, QuotaExhausted, ToolSpec


class SwitchingClient(LLMClient):
    def __init__(self, primary: LLMClient, fallback: Callable[[], LLMClient]) -> None:
        self._current = primary
        self._fallback = fallback
        self._switched = False
        self._lock = threading.Lock()
        self._notice: dict[str, str] | None = None

    @property  # type: ignore[override]
    def provider(self) -> str:
        return self._current.provider

    @property  # type: ignore[override]
    def model(self) -> str:
        return self._current.model

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        client = self._current
        try:
            return client.chat(messages, tools)
        except QuotaExhausted as exc:
            replacement = self._switch(client, str(exc))
            return replacement.chat(messages, tools)

    def _switch(self, failed: LLMClient, reason: str) -> LLMClient:
        with self._lock:
            if self._current is failed and not self._switched:
                self._current = self._fallback()
                self._switched = True
                self._notice = {
                    "code": "provider_switched",
                    "from": failed.provider,
                    "to": self._current.provider,
                    "model": self._current.model,
                    "reason": reason,
                }
            return self._current

    def take_notice(self) -> dict[str, str] | None:
        with self._lock:
            notice, self._notice = self._notice, None
            return notice
