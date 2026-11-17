"""SQLite tables of the backend. Phase 3 has the audit log only (invariant 8)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
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
