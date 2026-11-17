"""The trace of one agent run (invariant 6): every model call and every tool call, with
the arguments and the results exactly as the model saw them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.llm.base import ChatTurn, Message


@dataclass
class AgentTrace:
    provider: str
    model: str
    max_iterations: int
    input: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"
    error: str | None = None

    @property
    def model_calls(self) -> int:
        return sum(1 for s in self.steps if s["type"] == "model_call")

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return [s for s in self.steps if s["type"] == "tool_call"]

    def record_input(self, messages: list[Message]) -> None:
        self.input = [m.to_dict() for m in messages]

    def record_model_call(
        self, iteration: int, tools_offered: list[str], turn: ChatTurn, ms: float
    ) -> None:
        self.steps.append(
            {
                "type": "model_call",
                "iteration": iteration,
                "tools_offered": tools_offered,
                "content": turn.content,
                "tool_calls": [c.to_dict() for c in turn.tool_calls],
                "prompt_tokens": turn.prompt_tokens,
                "completion_tokens": turn.completion_tokens,
                "ms": round(ms, 1),
            }
        )

    def record_tool_call(
        self, iteration: int, name: str, arguments: dict[str, Any], result: str, ok: bool, ms: float
    ) -> None:
        self.steps.append(
            {
                "type": "tool_call",
                "iteration": iteration,
                "name": name,
                "arguments": arguments,
                "result": result,
                "ok": ok,
                "ms": round(ms, 1),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "max_iterations": self.max_iterations,
            "status": self.status,
            "error": self.error,
            "input": self.input,
            "steps": self.steps,
        }
