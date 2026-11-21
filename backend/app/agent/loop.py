"""The bounded agent loop (no framework, decision 0002).

1. The model gets the system prompt, the history, the user's message and the tools.
2. Each model call either answers in text (the run ends) or asks for tool calls; the loop
   runs them through the registry and sends the results back.
3. The run makes at most `max_iterations` model calls, the final answer included: the
   last allowed call offers no tools, so the model must answer with what it has.

Each model call runs in a worker thread, so the loop can pass on what the client reports
while it waits (`status`, e.g. a rate limit), stop when the user cancels, and end the turn
after `AGENT_TURN_TIMEOUT_S` (decision 0017).

The loop yields events for the UI as they happen (`tool_call`, `tool_result`,
`form_proposal`, `pending_action`, `message`, `notice`, `status`, `error`) and records
everything in an `AgentTrace` (invariant 6). It never executes a side effect: the gated
tools only open confirmation cards (invariant 2).
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from app.agent.tools import ToolContext, ToolRegistry
from app.agent.trace import AgentTrace
from app.llm.base import ChatTurn, LLMClient, LLMError, Message, ToolCall, ToolSpec, call_with

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
    status: str = "running"  # answered | limit | error | cancelled | timeout


def _notice(client: LLMClient, trace: AgentTrace, iteration: int) -> Iterator[AgentEvent]:
    """What the client says happened behind the call, e.g. Groq's daily quota ran out and
    it moved to Ollama: into the trace, and to the UI."""
    notice = client.take_notice()
    if notice:
        trace.record_notice(iteration, notice)
        yield AgentEvent("notice", notice)


class RunStopped(Exception):
    """The run ends early: `status` is "cancelled" (the user pressed Stop) or "timeout"."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="model-call")
POLL_S = 0.2


def _model_call(
    client: LLMClient,
    conversation: list[Message],
    offered: list[ToolSpec],
    *,
    cancel: threading.Event | None,
    deadline: float | None,
) -> Generator[AgentEvent, None, ChatTurn]:
    """Run `client.chat` in a worker thread. Meanwhile yield what the client reports (e.g.
    `status` rate_limited) and stop waiting on cancel or when the turn's time is up."""
    reports: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
    stop = threading.Event()  # tells the client to stop waiting out a rate limit
    future = _executor.submit(
        call_with,
        lambda kind, data: reports.put((kind, data)),
        stop,
        lambda: client.chat(conversation, offered),
    )
    try:
        while True:
            try:
                kind, data = reports.get(timeout=POLL_S)
                yield AgentEvent("status", {"kind": kind, **data})
                continue
            except queue.Empty:
                pass
            if cancel is not None and cancel.is_set():
                raise RunStopped("cancelled")
            if deadline is not None and time.monotonic() >= deadline:
                raise RunStopped("timeout")
            if future.done():
                while not reports.empty():  # anything reported just before the end
                    kind, data = reports.get_nowait()
                    yield AgentEvent("status", {"kind": kind, **data})
                return future.result()  # raises the client's LLMError, if any
    finally:
        # A call in flight finishes in the background; its result is dropped.
        stop.set()


def run_agent(
    client: LLMClient,
    registry: ToolRegistry,
    ctx: ToolContext,
    messages: list[Message],
    *,
    max_iterations: int,
    trace: AgentTrace,
    outcome: RunOutcome,
    cancel: threading.Event | None = None,
    timeout_s: float | None = None,
    preretrieve: dict[str, Any] | None = None,
) -> Iterator[AgentEvent]:
    """`messages` = system prompt + history + the new user message. `cancel` stops the run
    (Stop button); `timeout_s` caps the whole turn (`AGENT_TURN_TIMEOUT_S`). With
    `preretrieve` (the arguments of a `search_design_manual` call), the backend runs that
    search before the first model call and adds it to the conversation as if the model
    had made it (decision 0024): traced with `auto`, shown in Agent steps, and not a model
    call, so it doesn't count against `max_iterations`."""
    deadline = time.monotonic() + timeout_s if timeout_s else None
    try:
        yield from _run(
            client,
            registry,
            ctx,
            messages,
            max_iterations,
            trace,
            outcome,
            cancel,
            deadline,
            preretrieve,
        )
    except RunStopped as stopped:
        outcome.status = trace.status = stopped.status
        if stopped.status == "timeout":
            trace.error = f"no answer within {timeout_s:g} s"
            yield AgentEvent(
                "error",
                {
                    "code": "turn_timeout",
                    "message": f"The model did not answer within {timeout_s:g} s.",
                    "timeout_s": timeout_s,
                },
            )
        else:
            trace.error = "stopped by the user"


def _run(
    client: LLMClient,
    registry: ToolRegistry,
    ctx: ToolContext,
    messages: list[Message],
    max_iterations: int,
    trace: AgentTrace,
    outcome: RunOutcome,
    cancel: threading.Event | None,
    deadline: float | None,
    preretrieve: dict[str, Any] | None = None,
) -> Iterator[AgentEvent]:
    conversation = list(messages)
    trace.record_input(conversation)
    specs = registry.specs
    if preretrieve is not None:
        call = ToolCall(f"auto_{ctx.run_id or 1}", "search_design_manual", preretrieve)
        yield from _execute(call, registry, ctx, trace, outcome, conversation, 0, auto=True)

    for iteration in range(1, max_iterations + 1):
        last_call = iteration == max_iterations
        offered = [] if last_call else specs
        started = time.perf_counter()
        try:
            turn = yield from _model_call(
                client, conversation, offered, cancel=cancel, deadline=deadline
            )
        except LLMError as exc:
            yield from _notice(client, trace, iteration)  # e.g. switched, then that failed
            trace.status, trace.error = "error", str(exc)
            outcome.status = "error"
            yield AgentEvent("error", {"message": str(exc)})
            return
        yield from _notice(client, trace, iteration)
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
            if cancel is not None and cancel.is_set():  # no card opens after Stop
                raise RunStopped("cancelled")
            yield from _execute(call, registry, ctx, trace, outcome, conversation, iteration)


def _execute(
    call: ToolCall,
    registry: ToolRegistry,
    ctx: ToolContext,
    trace: AgentTrace,
    outcome: RunOutcome,
    conversation: list[Message],
    iteration: int,
    *,
    auto: bool = False,
) -> Iterator[AgentEvent]:
    """Run one tool call through the registry; record it, show it, and add its result to
    the conversation. The backend's own search (`auto`) also adds the assistant message
    that asks for it, so the model sees a normal call and result."""
    flag = {"auto": True} if auto else {}
    yield AgentEvent(
        "tool_call", {"id": call.id, "name": call.name, "arguments": call.arguments, **flag}
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
        auto=auto,
    )
    yield AgentEvent(
        "tool_result",
        {"id": call.id, "name": call.name, "ok": result.ok, "result": result.content, **flag},
    )
    if result.event is not None:
        event = dict(result.event)
        yield AgentEvent(event.pop("type"), event)
    if auto:
        request = Message("assistant", "", tool_calls=(call,))
        conversation.append(request)
        outcome.new_messages.append(request)
    tool_message = Message("tool", text, tool_call_id=call.id, name=call.name)
    conversation.append(tool_message)
    outcome.new_messages.append(tool_message)
