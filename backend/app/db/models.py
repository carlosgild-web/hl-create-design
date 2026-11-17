"""SQLite tables of the backend: audit log, conversations, agent runs, pending actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    """One row per created design and per reserved SAP number. Rows are never updated."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    action: Mapped[str] = mapped_column(String(40))  # "design_created", "number_reserved"
    actor: Mapped[str] = mapped_column(String(80))
    design_number: Mapped[str | None] = mapped_column(String(20), index=True)
    revision: Mapped[str | None] = mapped_column(String(2))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class TokenUsage(Base):
    """Model tokens spent per UTC day (the demo's daily cap, `DAILY_TOKEN_CAP`)."""

    __tablename__ = "token_usage"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    tokens: Mapped[int] = mapped_column(Integer, default=0)


class Conversation(Base):
    """One chat with the assistant. `messages` is the history in the neutral shape of
    `app.llm.base.Message` (as dicts), plus `event` messages for confirmed actions."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class AgentRun(Base):
    """One bounded agent run (invariant 6): the trace of every model and tool call."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))  # answered | limit | error
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    trace: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PendingAction(Base):
    """A side effect the assistant proposed and only the user's click executes (invariant 2).

    Life cycle: pending -> executing -> confirmed | failed; pending -> cancelled; a
    pending action past `expires_at` can't be confirmed. Each action runs at most once.
    """

    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # create_design | reserve_number
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
