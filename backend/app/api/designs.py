"""Endpoints the UI needs next to the assistant (Phase 5).

`POST /api/actions` lets the form open a confirmation card without the model. It only
*proposes*: the files and the SAP number still wait for `POST /api/actions/{id}/confirm`
(invariant 2). `GET /api/designs/.../preview.{pdf,svg}` serves files from inside
`DESIGNS_ROOT` only (invariant 3).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import sap_lookup_for
from app.api.deps import EngineDep, RateLimited, SapFactoryDep, SettingsDep
from app.db import store
from app.db.models import AuditLog
from app.designs import check_fields, normalize_payload
from app.standards import validators as v

router = APIRouter(prefix="/api", tags=["designs"])

MEDIA = {"pdf": "application/pdf", "svg": "image/svg+xml"}
FIELD_MAX = 200


class ProposeAction(BaseModel):
    kind: Literal["create_design", "reserve_number"]
    payload: dict[str, str] = Field(default_factory=dict, max_length=10)
    conversation_id: str | None = Field(default=None, max_length=32)


@router.get("/departments")
def departments() -> list[dict[str, str]]:
    return [
        {"code": code, "name": name, "name_es": v.DEPARTMENTS_ES.get(code, name)}
        for code, name in v.DEPARTMENTS.items()
    ]


class ValidateRequest(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict, max_length=10)


@router.post("/validate")
def validate(body: ValidateRequest, settings: SettingsDep, sap_factory: SapFactoryDep) -> dict:
    """The form's inline check: the same result as the assistant's `validate_design_request`
    tool (`app.designs.check_fields`). Read-only: it writes nothing and reserves nothing."""
    fields = {k[:40]: val[:FIELD_MAX] for k, val in body.fields.items()}
    if not any(val.strip() for val in fields.values()):
        return {"ok": True, "normalized": {}, "errors": [], "warnings": [], "missing": []}
    with sap_factory() as sap:
        return check_fields(fields, settings.designs_root, sap_lookup_for(sap))


@router.post("/actions", status_code=201, dependencies=[RateLimited])
def propose_action(body: ProposeAction, engine: EngineDep) -> dict[str, Any]:
    """The user's own form opens a pending action. Nothing is executed here. The values
    are stored as they will be written (title case, capitals), so the card shows that."""
    conversation_id = body.conversation_id
    if conversation_id is None:
        conversation_id = store.create_conversation(engine)
    elif store.get_messages(engine, conversation_id) is None:
        raise HTTPException(404, "Conversation not found")
    payload = normalize_payload({k[:40]: val[:FIELD_MAX] for k, val in body.payload.items()})
    action = store.create_action(
        engine, conversation_id=conversation_id, run_id=None, kind=body.kind, payload=payload
    )
    return action.to_dict()


@router.get("/designs")
def recent_designs(engine: EngineDep, limit: int = 20) -> list[dict[str, Any]]:
    """The designs created through the tool, newest first (from the audit log)."""
    limit = max(1, min(limit, 100))
    query = (
        select(AuditLog)
        .where(AuditLog.action == "design_created")
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    with Session(engine) as session:
        return [
            {
                "design_number": row.design_number,
                "revision": row.revision,
                "name": row.details.get("name", ""),
                "description": row.details.get("description", ""),
                "department": row.details.get("department", ""),
                "designer": row.actor,
                "pdf": bool(row.details.get("pdf")),
                "created_at": row.created_at.isoformat(),
            }
            for row in session.scalars(query)
        ]


@router.get("/designs/{department}/{design_number}/{revision}/preview.{fmt}")
def preview(
    department: str,
    design_number: str,
    revision: str,
    fmt: Literal["pdf", "svg"],
    settings: SettingsDep,
) -> FileResponse:
    try:
        folder = v.design_folder(settings.designs_root, department, design_number, revision)
    except v.UnsafePathError as exc:
        raise HTTPException(404, "Design not found") from exc
    output = folder / "output"
    stem = v.design_file_stem(design_number, revision)
    # The SVG export names its file after the sheet; take the first one.
    candidates = [output / f"{stem}.pdf"] if fmt == "pdf" else sorted(output.glob("*.svg"))
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise HTTPException(404, "No preview for this design")
    return FileResponse(path, media_type=MEDIA[fmt], headers={"Cache-Control": "no-cache"})
