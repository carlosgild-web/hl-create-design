"""Read-only views of SAP for the Start panel (decision 0018).

`GET /api/sap/designs` lists the designs SAP knows, with the revision a new revision would
get; `GET /api/sap/designs/{number}` returns one. SAP is reached only through `SapClient`
(invariant 4) and nothing is written.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from app.agent.tools import sap_error_info
from app.api.deps import SapFactoryDep, SettingsDep
from app.designs import next_free_revision
from app.sap.client import SapDesign, SapError

router = APIRouter(prefix="/api/sap", tags=["sap"])

SELECTABLE = frozenset({"IN_WORK", "RELEASED"})  # a new revision may be added (06-sap-statuses)
Department = Literal["HW", "PWR", "EMB", "TFX"]
Status = Literal["IN_WORK", "RELEASED", "BLOCKED", "OBSOLETE"]


def _row(design: SapDesign, settings) -> dict[str, Any]:
    return {
        "design_number": design.design_number,
        "department": design.department,
        "name": design.name,
        "status": design.status,
        "material": design.material,
        "wbs": design.wbs,
        "revisions": list(design.revisions),
        "current_revision": design.current_revision,
        "next_free_revision": next_free_revision(design, settings.designs_root),
        "block_reason": design.block_reason,
        "successor": design.successor,
        "selectable": design.status in SELECTABLE,
    }


def _unavailable(exc: SapError) -> JSONResponse:
    return JSONResponse(sap_error_info(exc), status_code=503 if exc.unavailable else 502)


@router.get("/designs", response_model=None)
def list_designs(
    settings: SettingsDep,
    sap_factory: SapFactoryDep,
    department: Department | None = None,
    status: Status | None = None,
    q: Annotated[str, Query(max_length=40)] = "",
    lang: Literal["en", "es"] = "en",
) -> list[dict[str, Any]] | JSONResponse:
    """The designs SAP knows, ordered by number. `q` matches the number or the name
    (SAP's OData cannot filter on the name, so this filter runs here)."""
    try:
        with sap_factory() as sap:
            sap.use_language(lang)
            designs = sap.list_designs(department=department, status=status, top=500)
    except SapError as exc:
        return _unavailable(exc)
    needle = q.strip().lower()
    return [
        _row(d, settings)
        for d in designs
        if not needle or needle in d.design_number.lower() or needle in d.name.lower()
    ]


@router.get("/designs/{design_number}", response_model=None)
def get_design(
    design_number: Annotated[str, Path(max_length=40)],
    settings: SettingsDep,
    sap_factory: SapFactoryDep,
    lang: Literal["en", "es"] = "en",
) -> dict[str, Any] | JSONResponse:
    try:
        with sap_factory() as sap:
            sap.use_language(lang)
            design = sap.get_design(design_number)
    except SapError as exc:
        return _unavailable(exc)
    if design is None:
        raise HTTPException(404, f"SAP does not know {design_number}")
    return _row(design, settings)
