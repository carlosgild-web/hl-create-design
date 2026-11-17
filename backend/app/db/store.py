"""Reads and writes of conversations, agent runs and pending actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.db.models import AgentRun, Conversation, PendingAction, utcnow

ACTION_TTL = timedelta(minutes=30)


def new_id() -> str:
    return uuid.uuid4().hex


def aware(moment: datetime) -> datetime:
    """SQLite gives naive datetimes back; every stored one is UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


# --- conversations -------------------------------------------------------------------


def create_conversation(engine: Engine) -> str:
    with Session(engine) as session, session.begin():
        conversation = Conversation(id=new_id(), messages=[])
        session.add(conversation)
        return conversation.id


def get_messages(engine: Engine, conversation_id: str) -> list[dict[str, Any]] | None:
    """The stored history, or None when the conversation doesn't exist."""
    with Session(engine) as session:
        conversation = session.get(Conversation, conversation_id)
        return None if conversation is None else list(conversation.messages)


def append_messages(engine: Engine, conversation_id: str, messages: list[dict[str, Any]]) -> None:
    with Session(engine) as session, session.begin():
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise KeyError(conversation_id)
        conversation.messages = [*conversation.messages, *messages]


# --- agent runs ----------------------------------------------------------------------


def start_run(engine: Engine, conversation_id: str, provider: str, model: str) -> int:
    with Session(engine) as session, session.begin():
        run = AgentRun(
            conversation_id=conversation_id, provider=provider, model=model, status="running"
        )
        session.add(run)
        session.flush()
        return run.id


def finish_run(
    engine: Engine, run_id: int, *, status: str, model_calls: int, trace: dict[str, Any]
) -> None:
    with Session(engine) as session, session.begin():
        run = session.get(AgentRun, run_id)
        if run is None:
            raise KeyError(run_id)
        run.status = status
        run.model_calls = model_calls
        run.trace = trace
        run.finished_at = utcnow()


def get_run(engine: Engine, run_id: int) -> dict[str, Any] | None:
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            return None
        return {
            "id": run.id,
            "conversation_id": run.conversation_id,
            "provider": run.provider,
            "model": run.model,
            "status": run.status,
            "model_calls": run.model_calls,
            "started_at": aware(run.started_at).isoformat(),
            "finished_at": aware(run.finished_at).isoformat() if run.finished_at else None,
            "trace": run.trace,
        }


# --- pending actions -----------------------------------------------------------------


@dataclass(frozen=True)
class ActionRecord:
    id: str
    conversation_id: str
    run_id: int | None
    kind: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "kind": self.kind,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "result": self.result,
        }


def _record(row: PendingAction) -> ActionRecord:
    return ActionRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        run_id=row.run_id,
        kind=row.kind,
        payload=dict(row.payload),
        status=row.status,
        created_at=aware(row.created_at),
        expires_at=aware(row.expires_at),
        decided_at=aware(row.decided_at) if row.decided_at else None,
        result=dict(row.result or {}),
    )


def create_action(
    engine: Engine,
    *,
    conversation_id: str,
    run_id: int | None,
    kind: str,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> ActionRecord:
    now = now or utcnow()
    with Session(engine) as session, session.begin():
        row = PendingAction(
            id=new_id(),
            conversation_id=conversation_id,
            run_id=run_id,
            kind=kind,
            payload=payload,
            status="pending",
            created_at=now,
            expires_at=now + ACTION_TTL,
            result={},
        )
        session.add(row)
        session.flush()
        return _record(row)


def get_action(engine: Engine, action_id: str) -> ActionRecord | None:
    with Session(engine) as session:
        row = session.get(PendingAction, action_id)
        return None if row is None else _record(row)


def list_actions(engine: Engine, conversation_id: str) -> list[ActionRecord]:
    query = (
        select(PendingAction)
        .where(PendingAction.conversation_id == conversation_id)
        .order_by(PendingAction.created_at)
    )
    with Session(engine) as session:
        return [_record(r) for r in session.scalars(query)]


def claim_action(engine: Engine, action_id: str, *, to: str, now: datetime | None = None) -> bool:
    """Move a pending, unexpired action to `to` (executing or cancelled) atomically.
    Returns False if another request got there first or the action expired."""
    now = now or utcnow()
    with Session(engine) as session, session.begin():
        row = session.get(PendingAction, action_id)
        if row is None or row.status != "pending" or aware(row.expires_at) <= now:
            return False
        changed = session.execute(
            update(PendingAction)
            .where(PendingAction.id == action_id, PendingAction.status == "pending")
            .values(status=to, decided_at=now)
        )
        return changed.rowcount == 1


def finish_action(engine: Engine, action_id: str, *, status: str, result: dict[str, Any]) -> None:
    with Session(engine) as session, session.begin():
        row = session.get(PendingAction, action_id)
        if row is None:
            raise KeyError(action_id)
        row.status = status
        row.result = result
