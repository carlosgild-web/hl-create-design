"""The provider-neutral chat shape the agent loop speaks (decision 0002, invariant 5).

Each client translates these types to and from its provider's API. Nothing outside
`app/llm/` imports a provider SDK or knows a provider's message format.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

T = TypeVar("T")

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    """One function call the model asked for. `arguments` is always a dict; a client
    that receives arguments it can't parse passes them as `{"__invalid__": raw}`."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        return cls(id=data["id"], name=data["name"], arguments=dict(data.get("arguments") or {}))


@dataclass(frozen=True)
class Message:
    """One chat message. A `tool` message answers the call `tool_call_id` of tool `name`."""

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [c.to_dict() for c in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.name:
            data["name"] = self.name
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            role=data["role"],
            content=data.get("content") or "",
            tool_calls=tuple(ToolCall.from_dict(c) for c in data.get("tool_calls") or ()),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
        )


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model: name, description and a JSON schema of its arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ChatTurn:
    """One reply of the model: text, tool calls, or both, plus token counts (0 if unknown)."""

    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMError(RuntimeError):
    """The provider failed (unreachable, unknown model, bad answer). The message is meant
    for the person running the tool, so it says what to do."""


class LLMClient(ABC):
    """A chat model with tool calling."""

    provider: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        """One non-streaming chat turn. An empty `tools` list means: answer in text."""

    def take_notice(self) -> dict[str, str] | None:
        """Something the user should be told about the last `chat` call (e.g. the client
        switched provider), once; then None. Plain clients have nothing to say."""
        return None


class QuotaExhausted(LLMError):
    """The provider's quota for today is used up: waiting a minute will not help."""


class CallInterrupted(LLMError):
    """The caller stopped waiting (the user pressed Stop, or the turn ran out of time)."""


# --- per-call context ------------------------------------------------------------------
# The agent runs each `chat()` in a worker thread with a listener and a stop flag, so a
# client can say "waiting 40 s for a rate limit" while it waits, and stop waiting when told.
# Thread-local, so a client shared by several requests reports to the right one.

Listener = Callable[[str, dict[str, Any]], None]
_call = threading.local()


def call_with(listener: Listener | None, stop: threading.Event | None, fn: Callable[[], T]) -> T:
    """Run `fn` (a `chat()` call) with this listener and stop flag for the current thread."""
    _call.listener, _call.stop = listener, stop
    try:
        return fn()
    finally:
        _call.listener = _call.stop = None


def report(kind: str, **data: Any) -> None:
    """Tell whoever runs this call what is happening (e.g. kind="rate_limited", wait_s=40)."""
    listener = getattr(_call, "listener", None)
    if listener is not None:
        listener(kind, data)


def wait(seconds: float, sleep: Callable[[float], None] | None = None) -> None:
    """Sleep, unless the caller stops waiting first (then raise `CallInterrupted`). A test
    `sleep` is used as is."""
    stop: threading.Event | None = getattr(_call, "stop", None)
    if sleep is not None:
        sleep(seconds)
    elif stop is not None:
        stop.wait(seconds)
    else:
        time.sleep(seconds)
    if stop is not None and stop.is_set():
        raise CallInterrupted("stopped while waiting")
