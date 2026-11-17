"""The backend's SQLite database, `DATA_DIR/app.db`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Base

DB_FILE = "app.db"


@lru_cache
def get_engine(data_dir: Path) -> Engine:
    """One engine per data folder; creates the folder and the tables on first use."""
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{(data_dir / DB_FILE).as_posix()}")
    Base.metadata.create_all(engine)
    return engine


def write_audit(
    engine: Engine,
    *,
    action: str,
    actor: str,
    design_number: str | None = None,
    revision: str | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Append one audit row and return its id."""
    with Session(engine) as session, session.begin():
        row = AuditLog(
            action=action,
            actor=actor,
            design_number=design_number,
            revision=revision,
            details=details or {},
        )
        session.add(row)
        session.flush()
        return row.id


def audit_rows(engine: Engine, design_number: str | None = None) -> list[AuditLog]:
    """Audit rows, oldest first; filtered by design number when given."""
    query = select(AuditLog).order_by(AuditLog.id)
    if design_number is not None:
        query = query.where(AuditLog.design_number == design_number)
    with Session(engine) as session:
        return list(session.scalars(query))
