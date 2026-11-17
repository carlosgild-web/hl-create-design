"""Create a design revision: validate, render the KiCad project, export the PDF, audit.

This is the only code path that creates design files. It runs behind the confirmation
gate (`POST /api/actions/{id}/confirm`, invariant 2); the developer CLI calls it too.

Either the whole revision is created (project, PDF and SVG, audit row) or nothing is:
a failure after the folder was created removes that folder again.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from app.core.config import Settings
from app.db.session import get_engine, write_audit
from app.kicad.exporter import ExportResult, Runner, export_schematic
from app.kicad.renderer import TEMPLATE_DIR, RenderedProject, TitleBlock, render_project
from app.sap.client import SapDesign
from app.standards import validators as v
from app.standards.validators import DesignRequest, Issue, ValidationReport


class DesignValidationError(ValueError):
    """The request breaks a rule of the Design Manual; nothing was created."""

    def __init__(self, report: ValidationReport) -> None:
        super().__init__("; ".join(e.message for e in report.errors))
        self.report = report


@dataclass(frozen=True)
class CreatedDesign:
    request: DesignRequest  # normalized
    project: RenderedProject
    export: ExportResult | None
    warnings: tuple[Issue, ...]
    audit_id: int

    @property
    def relative_folder(self) -> str:
        """The folder relative to DESIGNS_ROOT, with forward slashes."""
        parts = self.project.folder.parts[-3:]
        return "/".join(parts)


def check_design_request(
    request: DesignRequest,
    designs_root: Path,
    *,
    sap: SapDesign | None = None,
    require_sap: bool = False,
) -> ValidationReport:
    """Validate against the manual, the revision folders that exist and, when given,
    the SAP record of the design (status, revisions, material, project).

    With a SAP record, the material and the project come from SAP: they are never typed
    by hand (01-design-numbering#issued-by-sap). `require_sap` makes a number that SAP
    doesn't know an error; the confirm endpoint always sets it.
    """
    on_disk: list[str] = []
    if (
        v.validate_department(request.department).ok
        and v.validate_design_number(request.design_number, request.department).ok
    ):
        on_disk = v.revisions_on_disk(
            designs_root, request.department.strip(), request.design_number.strip()
        )
    if sap is None:
        report = v.validate_design_request(request, existing_revisions=on_disk)
        if require_sap and report.request.design_number:
            missing = v.check_known_in_sap(report.request.design_number, found=False)
            report = replace(report, errors=(*report.errors, *missing.errors))
        return report

    request = replace(request, sap_material=sap.material, project=sap.wbs)
    return v.validate_design_request(
        request,
        existing_revisions=v.revisions_in_use(sap.revisions, on_disk),
        sap_status=sap.status,
        block_reason=sap.block_reason or None,
        successor=sap.successor or None,
    )


def create_design(
    request: DesignRequest,
    *,
    settings: Settings,
    export: bool = True,
    today: date | None = None,
    engine: Engine | None = None,
    runner: Runner = subprocess.run,
    template_dir: Path = TEMPLATE_DIR,
    sap: SapDesign | None = None,
    require_sap: bool = False,
    audit_details: dict[str, Any] | None = None,
) -> CreatedDesign:
    """Create one revision folder from the company template. Raises on any failure.

    `sap` is the design's SAP record, looked up by the caller through `SapClient`
    (this module never calls SAP). Raises `DesignValidationError` (rules),
    `UnsafePathError` (path outside DESIGNS_ROOT), `DesignFolderExistsError` (never
    overwrites) or `ExportError` (kicad-cli).
    """
    if not request.issue_date:
        request = replace(request, issue_date=(today or date.today()).isoformat())

    report = check_design_request(request, settings.designs_root, sap=sap, require_sap=require_sap)
    if not report.ok:
        raise DesignValidationError(report)
    req = report.request

    folder = v.design_folder(settings.designs_root, req.department, req.design_number, req.revision)
    stem = v.design_file_stem(req.design_number, req.revision)
    block = TitleBlock(
        design_number=req.design_number,
        revision=req.revision,
        title=req.name,
        issue_date=str(req.issue_date),
        designer=req.designer,
        department=v.department_label(req.department),
        sap_material=v.material_display(req.sap_material) if req.sap_material else "",
        project=req.project,
    )

    project = render_project(folder, stem, block, template_dir)
    try:
        exported = (
            export_schematic(
                project.schematic_file,
                project.output_dir,
                kicad_cli=settings.kicad_cli,
                runner=runner,
            )
            if export
            else None
        )
        audit_id = write_audit(
            engine or get_engine(settings.data_dir),
            action="design_created",
            actor=req.designer,
            design_number=req.design_number,
            revision=req.revision,
            details={
                "name": req.name,
                "department": req.department,
                "folder": "/".join(folder.parts[-3:]),
                "sap_material": req.sap_material,
                "project": req.project,
                "issue_date": str(req.issue_date),
                "pdf": exported is not None,
                "warnings": [w.code for w in report.warnings],
                "sap_status": sap.status if sap else None,
                **(audit_details or {}),
            },
        )
    except BaseException:
        shutil.rmtree(project.folder, ignore_errors=True)
        raise

    return CreatedDesign(
        request=req,
        project=project,
        export=exported,
        warnings=report.warnings,
        audit_id=audit_id,
    )
