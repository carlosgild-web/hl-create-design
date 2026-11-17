"""The bounded agent loop (no framework, decision 0002).

1. The model gets the system prompt, the history, the user's message and the tools.
2. Each model call either answers in text (the run ends) or asks for tool calls; the loop
   runs them through the registry and sends the results back.
3. The run makes at most `max_iterations` model calls, the final answer included: the
   last allowed call offers no tools, so the model must answer with what it has.

The loop yields events for the UI as they happen (`tool_call`, `tool_result`,
`form_proposal`, `pending_action`, `message`, `error`) and records everything in an
`AgentTrace` (invariant 6). It never executes a side effect: the gated tools only open
confirmation cards (invariant 2).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.agent.tools import ToolContext, ToolRegistry
from app.agent.trace import AgentTrace
from app.llm.base import LLMClient, LLMError, Message

LIMIT_FALLBACK = (
    "I couldn't finish within the steps allowed for one answer. Please tell me what you "
    "want to do next, or check the form."
)
EMPTY_FALLBACK = "I have no answer for that. Could you rephrase it?"


@dataclass(frozen=True)
class AgentEvent:
    type: str
    data: dict[str, Any]


@dataclass
class RunOutcome:
    """Filled while the loop runs: the messages to keep in the history and the answer."""

    new_messages: list[Message] = field(default_factory=list)
    answer: str = ""
    status: str = "running"  # answered | limit | error


def run_agent(
    client: LLMClient,
    registry: ToolRegistry,
    ctx: ToolContext,
    messages: list[Message],
    *,
    max_iterations: int,
    trace: AgentTrace,
    outcome: RunOutcome,
) -> Iterator[AgentEvent]:
    """`messages` = system prompt + history + the new user message."""
    conversation = list(messages)
    trace.record_input(conversation)
    specs = registry.specs

    for iteration in range(1, max_iterations + 1):
        last_call = iteration == max_iterations
        offered = [] if last_call else specs
        started = time.perf_counter()
        try:
            turn = client.chat(conversation, offered)
        except LLMError as exc:
            trace.status, trace.error = "error", str(exc)
            outcome.status = "error"
            yield AgentEvent("error", {"message": str(exc)})
            return
        trace.record_model_call(
            iteration, [s.name for s in offered], turn, (time.perf_counter() - started) * 1000
        )

        if not turn.tool_calls or last_call:
            # "limit": the tools were withheld on this call (tool calls are ignored).
            status = "limit" if last_call and max_iterations > 1 else "answered"
            answer = turn.content.strip() or (
                LIMIT_FALLBACK if status == "limit" else EMPTY_FALLBACK
            )
            final = Message("assistant", answer)
            outcome.new_messages.append(final)
            outcome.answer, outcome.status = answer, status
            trace.status = status
            yield AgentEvent("message", {"role": "assistant", "content": answer})
            return

        assistant = Message("assistant", turn.content, tool_calls=turn.tool_calls)
        conversation.append(assistant)
        outcome.new_messages.append(assistant)
        if turn.content.strip():
            yield AgentEvent("thinking", {"content": turn.content.strip()})

        for call in turn.tool_calls:
            yield AgentEvent(
                "tool_call", {"id": call.id, "name": call.name, "arguments": call.arguments}
            )
            started = time.perf_counter()
            result = registry.execute(call, ctx)
            text = result.for_model()
            trace.record_tool_call(
                iteration,
                call.name,
                call.arguments,
                text,
                result.ok,
                (time.perf_counter() - started) * 1000,
            )
            yield AgentEvent(
                "tool_result",
                {"id": call.id, "name": call.name, "ok": result.ok, "result": result.content},
            )
            if result.event is not None:
                event = dict(result.event)
                yield AgentEvent(event.pop("type"), event)
            tool_message = Message("tool", text, tool_call_id=call.id, name=call.name)
            conversation.append(tool_message)
            outcome.new_messages.append(tool_message)
