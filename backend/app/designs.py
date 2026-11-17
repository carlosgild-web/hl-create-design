"""Create a design revision: validate, render the KiCad project, export the PDF, audit.

This is the only code path that creates design files. In Phase 4 it runs behind the
confirmation gate (`POST /actions/{id}/confirm`, invariant 2); in Phase 3 the CLI calls it.

Either the whole revision is created (project, PDF and SVG, audit row) or nothing is:
a failure after the folder was created removes that folder again.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from sqlalchemy import Engine

from app.core.config import Settings
from app.db.session import get_engine, write_audit
from app.kicad.exporter import ExportResult, Runner, export_schematic
from app.kicad.renderer import TEMPLATE_DIR, RenderedProject, TitleBlock, render_project
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


def check_design_request(request: DesignRequest, designs_root: Path) -> ValidationReport:
    """Validate against the manual and against the revision folders that already exist."""
    existing: list[str] = []
    if (
        v.validate_department(request.department).ok
        and v.validate_design_number(request.design_number, request.department).ok
    ):
        existing = v.revisions_on_disk(
            designs_root, request.department.strip(), request.design_number.strip()
        )
    return v.validate_design_request(request, existing_revisions=existing)


def create_design(
    request: DesignRequest,
    *,
    settings: Settings,
    export: bool = True,
    today: date | None = None,
    engine: Engine | None = None,
    runner: Runner = subprocess.run,
    template_dir: Path = TEMPLATE_DIR,
) -> CreatedDesign:
    """Create one revision folder from the company template. Raises on any failure.

    Raises `DesignValidationError` (rules), `UnsafePathError` (path outside DESIGNS_ROOT),
    `DesignFolderExistsError` (never overwrites) or `ExportError` (kicad-cli).
    """
    if not request.issue_date:
        request = replace(request, issue_date=(today or date.today()).isoformat())

    report = check_design_request(request, settings.designs_root)
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
