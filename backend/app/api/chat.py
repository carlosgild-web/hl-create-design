"""`POST /api/chat`: one turn with the assistant, streamed as server-sent events.

Events, in order: `conversation` {id}; then any of `thinking`, `tool_call`,
`tool_result`, `form_proposal`, `pending_action`, `message`, `error`; finally `done`
{conversation_id, run_id, status}.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.loop import AgentEvent
from app.agent.service import AgentDeps, chat_turn
from app.api.deps import (
    EngineDep,
    LLMFactoryDep,
    ManualDep,
    RateLimited,
    SapFactoryDep,
    SettingsDep,
)
from app.db import store
from app.llm.base import LLMError

router = APIRouter(prefix="/api", tags=["assistant"])

MESSAGE_MAX = 2000
DAILY_CAP_MESSAGE = (
    "The demo has used its daily model budget. The form, the checks and the confirmation "
    "cards still work; the assistant is back tomorrow (UTC)."
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MESSAGE_MAX)
    conversation_id: str | None = Field(default=None, max_length=32)
    language: Literal["en", "es"] = "en"
    form: dict[str, str] = Field(default_factory=dict, max_length=10)


def sse(event: AgentEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


@router.post("/chat", dependencies=[RateLimited])
def chat(
    body: ChatRequest,
    settings: SettingsDep,
    engine: EngineDep,
    manual: ManualDep,
    sap_factory: SapFactoryDep,
    llm_factory: LLMFactoryDep,
) -> StreamingResponse:
    form = {k[:40]: v[:200] for k, v in body.form.items()}

    def stream() -> Iterator[str]:
        cap = settings.daily_token_cap
        if cap and store.tokens_today(engine) >= cap:
            yield sse(AgentEvent("error", {"message": DAILY_CAP_MESSAGE, "code": "daily_cap"}))
            yield sse(AgentEvent("done", {"status": "error"}))
            return
        try:
            client = llm_factory()
        except LLMError as exc:
            yield sse(AgentEvent("error", {"message": str(exc)}))
            yield sse(AgentEvent("done", {"status": "error"}))
            return
        with sap_factory() as sap:
            deps = AgentDeps(
                settings=settings, engine=engine, client=client, sap=sap, manual=manual
            )
            for event in chat_turn(
                deps,
                text=body.message,
                conversation_id=body.conversation_id,
                form=form,
                language=body.language,
            ):
                yield sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, engine: EngineDep) -> dict:
    """What the UI shows: the user's texts, the answers, the events and the actions."""
    messages = store.get_messages(engine, conversation_id)
    if messages is None:
        raise HTTPException(404, "Conversation not found")
    visible = []
    for m in messages:
        if m["role"] == "user":
            visible.append({"role": "user", "content": m.get("text", m["content"])})
        elif m["role"] == "assistant" and not m.get("tool_calls"):
            visible.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "event":
            visible.append({"role": "event", "event": m.get("event", {})})
    actions = [a.to_dict() for a in store.list_actions(engine, conversation_id)]
    return {"id": conversation_id, "messages": visible, "actions": actions}


@router.get("/runs/{run_id}")
def get_run(run_id: int, engine: EngineDep) -> dict:
    """The trace of one agent run (invariant 6)."""
    run = store.get_run(engine, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run
