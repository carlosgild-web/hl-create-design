"""Endpoints the UI needs next to the assistant (Phase 5).

`POST /api/actions` lets the form open a confirmation card without the model. It only
*proposes*: the files and the SAP number still wait for `POST /api/actions/{id}/confirm`
(invariant 2). `GET /api/designs/.../preview.{pdf,svg}` (the schematic) and
`.../pcb.{pdf,svg}` (the board, decision 0033) serve files from inside `DESIGNS_ROOT` only
(invariant 3), and so do `.../files`, `.../project.zip` and `.../open` (Open in KiCad and
Open PCB, local mode only; decisions 0019 and 0033).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import sap_lookup_for, sap_names_for
from app.api.deps import EngineDep, LauncherDep, RateLimited, SapFactoryDep, SettingsDep
from app.core.config import Settings
from app.db import store
from app.db.models import AuditLog
from app.db.session import write_audit
from app.designs import check_fields, normalize_payload
from app.kicad.exporter import BOARD_SUFFIX
from app.kicad.launcher import OpenTarget, can_open, open_command, zip_folder
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
        return check_fields(fields, settings.designs_root, sap_lookup_for(sap), sap_names_for(sap))


@router.post("/actions", status_code=201, dependencies=[RateLimited])
def propose_action(
    body: ProposeAction, engine: EngineDep, settings: SettingsDep, sap_factory: SapFactoryDep
) -> dict[str, Any]:
    """The user's own form opens a pending action. Nothing is executed here. The values
    are stored as they will be written (title case, capitals), so the card shows that,
    with the warnings of the same read-only check the form runs (decision 0023): the
    user sees them before Confirm. The rules are checked again at confirm."""
    conversation_id = body.conversation_id
    if conversation_id is None:
        conversation_id = store.create_conversation(engine)
    elif store.get_messages(engine, conversation_id) is None:
        raise HTTPException(404, "Conversation not found")
    raw = {k[:40]: val[:FIELD_MAX] for k, val in body.payload.items() if k != "warnings"}
    payload: dict[str, Any] = normalize_payload(raw)
    with sap_factory() as sap:
        checked = check_fields(raw, settings.designs_root, sap_lookup_for(sap), sap_names_for(sap))
    payload["warnings"] = checked["warnings"]
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


def _existing_folder(settings: Settings, department: str, design_number: str, revision: str):
    """The revision folder, checked and confined to DESIGNS_ROOT (invariant 3); 404 when
    the values are not a design or the folder doesn't exist."""
    try:
        folder = v.design_folder(settings.designs_root, department, design_number, revision)
    except v.UnsafePathError as exc:
        raise HTTPException(404, "Design not found") from exc
    if not folder.is_dir():
        raise HTTPException(404, "Design not found")
    return folder


@router.get("/designs/{department}/{design_number}/{revision}/files")
def design_files(
    department: str, design_number: str, revision: str, settings: SettingsDep
) -> dict[str, Any]:
    """Where the project is on disk, whether Open in KiCad / Open PCB can work here, and
    whether the board has a preview (designs made before decision 0033 have no board)."""
    folder = _existing_folder(settings, department, design_number, revision)
    stem = v.design_file_stem(design_number, revision)
    project = folder / f"{stem}.kicad_pro"
    has_board = (folder / f"{stem}.kicad_pcb").is_file()
    return {
        "folder": str(folder),
        "project_file": str(project),
        "can_open": settings.kicad_open_enabled and can_open(settings.kicad_cli),
        "can_open_pcb": has_board
        and settings.kicad_open_enabled
        and can_open(settings.kicad_cli, "pcb"),
        "has_pcb_preview": (folder / "output" / f"{stem}{BOARD_SUFFIX}.svg").is_file(),
    }


@router.post("/designs/{department}/{design_number}/{revision}/open", dependencies=[RateLimited])
def open_in_kicad(
    department: str,
    design_number: str,
    revision: str,
    settings: SettingsDep,
    engine: EngineDep,
    launch: LauncherDep,
    target: OpenTarget = "schematic",
) -> dict[str, Any]:
    """Start KiCad's schematic editor (decision 0030) or, with `target=pcb`, its PCB editor
    (decision 0033) with the design; the Project Manager when that editor is missing. On
    the user's click only. Writes no file and calls no SAP (decision 0019); audited like
    every other action on a design."""
    folder = _existing_folder(settings, department, design_number, revision)
    if not (settings.kicad_open_enabled and can_open(settings.kicad_cli, target)):
        raise HTTPException(409, "Open in KiCad is not available on this server")
    stem = v.design_file_stem(design_number, revision)
    command = open_command(settings.kicad_cli, folder, stem, target)
    if command is None:
        raise HTTPException(404, f"The {target} and the project file are missing")
    gui = Path(command[0])
    project = folder / f"{stem}.kicad_pro"
    try:
        launch(command)
    except OSError as exc:
        raise HTTPException(500, f"KiCad did not start: {exc}") from exc
    write_audit(
        engine,
        action="design_opened",
        actor="",
        design_number=design_number,
        revision=revision,
        details={"department": department, "program": gui.name, "target": target},
    )
    return {"ok": True, "project_file": str(project)}


@router.get("/designs/{department}/{design_number}/{revision}/project.zip")
def project_zip(
    department: str, design_number: str, revision: str, settings: SettingsDep
) -> Response:
    folder = _existing_folder(settings, department, design_number, revision)
    stem = v.design_file_stem(design_number, revision)
    return Response(
        zip_folder(folder, stem),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}.zip"',
            "Cache-Control": "no-cache",
        },
    )


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
    # The SVG export names its file after the sheet; take the first one (not the board's).
    sheets = [p for p in sorted(output.glob("*.svg")) if not p.stem.endswith(BOARD_SUFFIX)]
    candidates = [output / f"{stem}.pdf"] if fmt == "pdf" else sheets
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise HTTPException(404, "No preview for this design")
    return FileResponse(path, media_type=MEDIA[fmt], headers={"Cache-Control": "no-cache"})


@router.get("/designs/{department}/{design_number}/{revision}/pcb.{fmt}")
def pcb_preview(
    department: str,
    design_number: str,
    revision: str,
    fmt: Literal["pdf", "svg"],
    settings: SettingsDep,
) -> FileResponse:
    """The board with its title block (decision 0033), exported next to the schematic."""
    try:
        folder = v.design_folder(settings.designs_root, department, design_number, revision)
    except v.UnsafePathError as exc:
        raise HTTPException(404, "Design not found") from exc
    stem = v.design_file_stem(design_number, revision)
    path = folder / "output" / f"{stem}{BOARD_SUFFIX}.{fmt}"
    if not path.is_file():
        raise HTTPException(404, "No PCB preview for this design")
    return FileResponse(path, media_type=MEDIA[fmt], headers={"Cache-Control": "no-cache"})
