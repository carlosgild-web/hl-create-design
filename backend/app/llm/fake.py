"""A scripted LLM client for tests, CI and demo mode: no model, no network.

A script is a list of steps. Each step is a `ChatTurn`, or a function that receives the
messages and the offered tools and returns a `ChatTurn` (so a script can react to a tool
result). In tests the script must cover the whole conversation: running out raises,
so a test can't pass by accident. Without a script the client is in demo mode and
always gives the same notice.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.llm.base import ChatTurn, LLMClient, LLMError, Message, ToolCall, ToolSpec

Step = ChatTurn | Callable[[list[Message], list[ToolSpec]], ChatTurn]

DEMO_NOTICE = (
    "Demo mode: no language model is configured (LLM_PROVIDER=fake). The form and the "
    "checks work; set LLM_PROVIDER=ollama to talk to the assistant."
)

_ids = itertools.count(1)


def say(text: str) -> ChatTurn:
    """A text reply."""
    return ChatTurn(content=text)


def call(name: str, /, **arguments: Any) -> ChatTurn:
    """A reply with one tool call."""
    return ChatTurn(tool_calls=(ToolCall(f"fake_{next(_ids)}", name, arguments),))


def calls(*pairs: tuple[str, dict[str, Any]]) -> ChatTurn:
    """A reply with several tool calls in one turn."""
    return ChatTurn(
        tool_calls=tuple(ToolCall(f"fake_{next(_ids)}", name, args) for name, args in pairs)
    )


class FakeScriptExhausted(LLMError):
    """The conversation needed more model turns than the script has."""


@dataclass
class RecordedCall:
    messages: list[Message]
    tools: list[ToolSpec]


class FakeClient(LLMClient):
    provider = "fake"

    def __init__(self, script: Sequence[Step] | None = None, model: str = "scripted") -> None:
        self._script = list(script) if script is not None else None
        self._position = 0
        self.model = model
        self.calls: list[RecordedCall] = []

    @property
    def remaining(self) -> int:
        return 0 if self._script is None else len(self._script) - self._position

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        self.calls.append(RecordedCall(list(messages), list(tools)))
        if self._script is None:
            return ChatTurn(content=DEMO_NOTICE)
        if self._position >= len(self._script):
            raise FakeScriptExhausted(
                f"FakeClient script has {len(self._script)} turns; call {self._position + 1}"
                " was not scripted."
            )
        step = self._script[self._position]
        self._position += 1
        return step if isinstance(step, ChatTurn) else step(list(messages), list(tools))
