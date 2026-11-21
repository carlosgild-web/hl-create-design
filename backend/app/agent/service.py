"""One chat turn: load the conversation, run the agent, store messages and the trace.

Used by `POST /api/chat` (as server-sent events) and by `python -m app.cli chat`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import Engine

from app.agent import runs
from app.agent.intent import classify
from app.agent.loop import AgentEvent, RunOutcome, run_agent
from app.agent.prompts import system_prompt, user_message
from app.agent.tools import FREE_TEXT_MAX, ToolContext, ToolRegistry
from app.agent.trace import AgentTrace
from app.core.config import Settings
from app.db import store
from app.llm.base import LLMClient, Message, ToolSpec
from app.sap.client import SapClient
from app.standards.manual_search import ManualIndex


@dataclass
class AgentDeps:
    settings: Settings
    engine: Engine
    client: LLMClient
    sap: SapClient
    manual: ManualIndex
    registry: ToolRegistry = field(default_factory=ToolRegistry)
    today: date | None = None
    # Which providers the UI may offer when a turn times out (`POST /api/llm/switch`).
    switch_options: Callable[[], list[str]] = field(default=lambda: [])


def model_history(stored: list[dict[str, Any]]) -> list[Message]:
    """The history the model sees: the user's messages, the assistant's answers and the
    backend events. Tool calls of earlier runs stay in their traces, which keeps the
    context of a small local model short."""
    history: list[Message] = []
    for data in stored:
        role = data.get("role")
        if role == "user" or (role == "assistant" and not data.get("tool_calls")):
            history.append(Message(role, data.get("content") or ""))
        elif role == "event":
            history.append(Message("user", data.get("content") or ""))
    return history


def probe_turn(language: str = "en") -> tuple[list[Message], list[ToolSpec]]:
    """A first chat turn as the model would get it (system prompt, all tool specs, a short
    user message), for checking that a provider's limits allow a real turn right now."""
    messages = [
        Message("system", system_prompt(language, date.today())),
        Message("user", user_message("Hello", {})),
    ]
    return messages, ToolRegistry().specs


# A small local model gets fewer, shorter passages, so the prompt plus the search fit its
# context and stay quick on CPU (decision 0024).
OLLAMA_SEARCH_LIMIT = 3
OLLAMA_PASSAGE_CHARS = 500


def preretrieval_for(settings: Settings, text: str, language: str) -> dict[str, Any] | None:
    """The arguments of the backend's own manual search for this message, or None.
    `AGENT_PRERETRIEVAL`: auto = questions about the rules or the app, on = always."""
    mode = settings.agent_preretrieval
    if mode == "off" or not text.strip():
        return None
    if mode == "auto" and classify(text) != "rule_question":
        return None
    return {"query": text.strip()[:FREE_TEXT_MAX], "language": language}


def chat_turn(
    deps: AgentDeps,
    *,
    text: str,
    conversation_id: str | None = None,
    form: dict[str, str] | None = None,
    language: str = "en",
) -> Iterator[AgentEvent]:
    """Yields `conversation` first, then the loop's events, then `done`."""
    stored = store.get_messages(deps.engine, conversation_id) if conversation_id else None
    if stored is None:
        conversation_id = store.create_conversation(deps.engine)
        stored = []
    assert conversation_id is not None
    yield AgentEvent("conversation", {"id": conversation_id})

    client = deps.client
    run_id = store.start_run(deps.engine, conversation_id, client.provider, client.model)
    user = {
        "role": "user",
        "content": user_message(text, form),
        "text": text,
        "form": form or {},
        "run_id": run_id,
    }
    messages = [
        Message("system", system_prompt(language, deps.today or date.today())),
        *model_history(stored),
        Message("user", user["content"]),
    ]
    ctx = ToolContext(
        settings=deps.settings,
        sap=deps.sap,
        manual=deps.manual,
        engine=deps.engine,
        conversation_id=conversation_id,
        run_id=run_id,
        language=language,
    )
    if client.provider == "ollama":
        ctx.search_limit, ctx.passage_chars = OLLAMA_SEARCH_LIMIT, OLLAMA_PASSAGE_CHARS
    trace = AgentTrace(client.provider, client.model, deps.settings.agent_max_iterations)
    outcome = RunOutcome()
    cancel = runs.register(run_id)
    yield AgentEvent("run", {"id": run_id})
    try:
        for event in run_agent(
            client,
            deps.registry,
            ctx,
            messages,
            max_iterations=deps.settings.agent_max_iterations,
            trace=trace,
            outcome=outcome,
            cancel=cancel,
            timeout_s=deps.settings.agent_turn_timeout_s,
            preretrieve=preretrieval_for(deps.settings, text, language),
        ):
            if event.data.get("code") == "turn_timeout":
                event = AgentEvent("error", {**event.data, "can_switch_to": deps.switch_options()})
            yield event
    finally:
        runs.release(run_id)
        # Also when the client disconnects mid-stream: keep what happened.
        if outcome.status == "running":
            outcome.status = trace.status = "error"
            trace.error = trace.error or "interrupted"
        kept = [user] + [m.to_dict() | {"run_id": run_id} for m in outcome.new_messages]
        store.append_messages(deps.engine, conversation_id, kept)
        store.finish_run(
            deps.engine,
            run_id,
            status=outcome.status,
            model_calls=trace.model_calls,
            trace=trace.to_dict(),
        )
        store.add_tokens(deps.engine, trace.tokens)
    yield AgentEvent(
        "done", {"conversation_id": conversation_id, "run_id": run_id, "status": outcome.status}
    )
