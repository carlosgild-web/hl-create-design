"""The OData service `ZHL_PLM_DESIGN_SRV`: designs, revisions, departments, reservations.

Auth, CSRF and chaos are middleware (`security.py`, `chaos.py`); these handlers only
speak OData. Keys arrive as `DesignSet('HL-HW-26-0042')`; quotes may be URL-encoded.
"""

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.db import Database, ReservationError
from app.odata import (
    DEPARTMENT_NOT_FOUND,
    DESIGN_NOT_FOUND,
    INVALID_REQUEST,
    REVISION_NOT_FOUND,
    SERVICE_ROOT,
    SapError,
    department_entity,
    design_entity,
    key_literal,
    key_value,
    parse_filter,
    revision_entity,
)

METADATA_XML = (Path(__file__).parent / "metadata.xml").read_text(encoding="utf-8")
ENTITY_SETS = ["DesignSet", "RevisionSet", "DepartmentSet"]
DESIGN_FILTERS = {"Department": "department", "Status": "status", "DesignNumber": "design_number"}

router = APIRouter(prefix=SERVICE_ROOT)


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


DbDep = Annotated[Database, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
FormatParam = Annotated[str | None, Query(alias="$format")]
ExpandParam = Annotated[str | None, Query(alias="$expand")]


def service_url(request: Request) -> str:
    """Absolute URL of the service root, for `__metadata.uri` and `Location`."""
    return str(request.base_url).rstrip("/") + SERVICE_ROOT


def check_format(fmt: str | None) -> None:
    if fmt is not None and fmt != "json":
        raise SapError(400, INVALID_REQUEST, "The mock only answers JSON: use $format=json")


def expands_revisions(expand: str | None) -> bool:
    if expand is None:
        return False
    if expand.strip() == "Revisions":
        return True
    raise SapError(400, INVALID_REQUEST, f"Invalid $expand '{expand}'. Only 'Revisions'")


class DesignCreate(BaseModel):
    """Body of `POST DesignSet`. SAP issues the number, material and WBS itself."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    Department: str = Field(min_length=1, max_length=4)
    Name: str = Field(min_length=1, max_length=40)
    CreatedBy: str = Field(min_length=1, max_length=40)


# --- service document and metadata ----------------------------------------------------


@router.get("")
@router.get("/", include_in_schema=False)
def service_document(fmt: FormatParam = None) -> dict:
    """The service document; clients also call it to fetch a CSRF token."""
    check_format(fmt)
    return {"d": {"EntitySets": ENTITY_SETS}}


@router.get("/$metadata")
def metadata() -> Response:
    return Response(content=METADATA_XML, media_type="application/xml")


# --- designs ---------------------------------------------------------------------------


@router.get("/DesignSet")
def list_designs(
    request: Request,
    db: DbDep,
    filter_: Annotated[str | None, Query(alias="$filter")] = None,
    top: Annotated[int | None, Query(alias="$top", ge=0)] = None,
    skip: Annotated[int, Query(alias="$skip", ge=0)] = 0,
    expand: ExpandParam = None,
    fmt: FormatParam = None,
) -> dict:
    check_format(fmt)
    filters = parse_filter(filter_, DESIGN_FILTERS) if filter_ is not None else {}
    rows = db.list_designs(filters, top=top, skip=skip)
    base = service_url(request)
    revisions = (
        db.revisions(r["design_number"] for r in rows) if expands_revisions(expand) else None
    )
    results = [
        design_entity(r, base, revisions[r["design_number"]] if revisions else None) for r in rows
    ]
    return {"d": {"results": results}}


@router.get("/DesignSet('{design_number}')")
def get_design(
    request: Request,
    design_number: str,
    db: DbDep,
    expand: ExpandParam = None,
    fmt: FormatParam = None,
) -> dict:
    check_format(fmt)
    number = key_value(design_number)
    row = _design_or_404(db, number)
    revisions = db.revisions([number])[number] if expands_revisions(expand) else None
    return {"d": design_entity(row, service_url(request), revisions)}


@router.get("/DesignSet('{design_number}')/Revisions")
def list_design_revisions(
    request: Request, design_number: str, db: DbDep, fmt: FormatParam = None
) -> dict:
    check_format(fmt)
    number = key_value(design_number)
    _design_or_404(db, number)
    base = service_url(request)
    return {"d": {"results": [revision_entity(r, base) for r in db.revisions([number])[number]]}}


@router.post("/DesignSet", status_code=201)
def reserve_design(
    request: Request,
    response: Response,
    payload: DesignCreate,
    db: DbDep,
    settings: SettingsDep,
) -> dict:
    """Reserve the next design number of the department for the current year."""
    try:
        number = db.reserve(payload.Department, payload.Name, payload.CreatedBy, settings.today())
    except ReservationError as exc:
        raise SapError(400, exc.code, exc.message) from exc
    entity = design_entity(_design_or_404(db, number), service_url(request))
    response.headers["Location"] = entity["__metadata"]["uri"]
    return {"d": entity}


@router.get("/RevisionSet(DesignNumber='{design_number}',Revision='{rev}')")
def get_revision(
    request: Request, design_number: str, rev: str, db: DbDep, fmt: FormatParam = None
) -> dict:
    check_format(fmt)
    number, letter = key_value(design_number), key_value(rev)
    row = db.get_revision(number, letter)
    if row is None:
        raise SapError(
            404, REVISION_NOT_FOUND, f"Revision {letter} of design {number} does not exist"
        )
    return {"d": revision_entity(row, service_url(request))}


def _design_or_404(db: Database, number: str) -> sqlite3.Row:
    row = db.get_design(number)
    if row is None:
        raise SapError(404, DESIGN_NOT_FOUND, f"Design {number} does not exist")
    return row


# --- departments -----------------------------------------------------------------------


@router.get("/DepartmentSet")
def list_departments(
    request: Request, db: DbDep, settings: SettingsDep, fmt: FormatParam = None
) -> dict:
    """Departments with the default project (WBS) for the current year."""
    check_format(fmt)
    base = service_url(request)
    rows = db.list_departments(settings.today().year)
    return {"d": {"results": [department_entity(r, base) for r in rows]}}


@router.get("/DepartmentSet('{code}')")
def get_department(
    request: Request, code: str, db: DbDep, settings: SettingsDep, fmt: FormatParam = None
) -> dict:
    check_format(fmt)
    value = key_value(code)
    row = db.get_department(value, settings.today().year)
    if row is None:
        raise SapError(404, DEPARTMENT_NOT_FOUND, f"Department {key_literal(value)} does not exist")
    return {"d": department_entity(row, service_url(request))}
