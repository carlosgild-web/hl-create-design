"""Create a design revision: validate, render the KiCad project, export the PDF, audit.

This is the only code path that creates design files. It runs behind the confirmation
gate (`POST /api/actions/{id}/confirm`, invariant 2); the developer CLI calls it too.

Either the whole revision is created (project, PDF and SVG, audit row) or nothing is:
a failure after the folder was created removes that folder again.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
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


FORM_FIELDS = ("department", "design_number", "revision", "name", "designer")
# Without a design number the revision can only be checked for its format.
_SEQUENCE_CODES = frozenset({"rev_first_not_a", "rev_jump", "rev_reused"})

# Looks a number up in SAP for `check_fields`: (record or None, or a note when SAP failed).
SapLookup = Callable[[str], tuple[SapDesign | None, dict[str, Any] | None]]


def issue_dict(issue: Issue) -> dict[str, str]:
    return {"field": issue.field, "code": issue.code, "message": issue.message, "ref": issue.ref}


def check_fields(fields: dict[str, str], designs_root: Path, lookup: SapLookup) -> dict[str, Any]:
    """Check the fields given so far, read-only: missing fields are listed, not reported
    as errors. The assistant's `validate_design_request` tool and the form's inline check
    (`POST /api/validate`) both use this, so they always agree (invariant 1).

    The result has `ok`, `normalized` (the given fields as they would be stored),
    `errors`, `warnings`, `missing`, and when a number is given `next_free_revision`,
    `sap` {status, material, wbs} or `sap_unavailable`. `lookup` is the caller's SAP
    access (through `SapClient`); this module never calls SAP.
    """
    given = {name: fields[name] for name in FORM_FIELDS if fields.get(name, "").strip()}
    request = DesignRequest(**{name: given.get(name, "") for name in FORM_FIELDS})

    sap: SapDesign | None = None
    sap_note: dict[str, Any] | None = None
    number_ok = v.validate_design_number(request.design_number, request.department or None).ok
    if request.design_number and number_ok:
        sap, sap_note = lookup(request.design_number.strip())

    try:
        report = check_design_request(
            request,
            designs_root,
            sap=sap,
            require_sap=bool(request.design_number and number_ok and sap_note is None),
        )
    except v.UnsafePathError as exc:
        return {"ok": False, "normalized": {}, "errors": [issue_dict(exc.issue)], "warnings": []}

    errors = [
        issue_dict(e)
        for e in report.errors
        if (e.field in given or e.field == "status")
        and not ("design_number" not in given and e.code in _SEQUENCE_CODES)
    ]
    content: dict[str, Any] = {
        "ok": not errors,
        "normalized": {k: getattr(report.request, k) for k in given},
        "errors": errors,
        "warnings": [issue_dict(w) for w in report.warnings],
        "missing": [name for name in FORM_FIELDS if name not in given],
    }
    if "design_number" in given:
        content["next_free_revision"] = report.next_revision
    suggest = _suggestions(request, report.next_revision if "design_number" in given else None)
    if suggest:
        content["suggest"] = suggest
    if sap is not None:
        content["sap"] = {
            "status": sap.status,
            "material": sap.material,
            "wbs": sap.wbs,
            "name": sap.name,
        }
    if sap_note is not None:
        content["sap_unavailable"] = sap_note
    return content


def next_free_revision(sap: SapDesign, designs_root: Path) -> str:
    """The revision a new revision of this SAP design gets: after every revision SAP knows
    and every revision folder on disk. The same rule `check_design_request` applies, so the
    Start panel's list and the validation never disagree."""
    try:
        on_disk = v.revisions_on_disk(designs_root, sap.department, sap.design_number)
    except v.UnsafePathError:
        on_disk = []
    return v.next_revision(v.revisions_in_use(sap.revisions, on_disk))


def number_prefix(department: str, today: date | None = None) -> str:
    """`HL-HW-26-`: the part of a new design number known before SAP issues it (format
    only, 01-design-numbering#format; the sequence always comes from SAP)."""
    return f"HL-{department}-{(today or date.today()).year % 100:02d}-"


def _suggestions(request: DesignRequest, next_revision: str | None) -> dict[str, str]:
    """Values the form can offer before the user types them, from the rules and SAP."""
    suggest: dict[str, str] = {}
    department = request.department.strip()
    if v.validate_department(department).ok:
        suggest["design_number_prefix"] = number_prefix(department)
    if next_revision:
        suggest["revision"] = next_revision
    return suggest


def normalize_payload(payload: dict[str, str]) -> dict[str, str]:
    """The values of a card as they will be stored (`Bead Sorter Vision Board`, `C`),
    so the card shows exactly that. Only the formatting changes; the rules are still
    checked at confirm."""
    checks: dict[str, Callable[[str], v.FieldCheck]] = {
        "department": v.validate_department,
        "design_number": v.validate_design_number,
        "revision": v.validate_revision,
        "name": v.validate_design_name,
        "designer": v.validate_designer,
    }
    out = dict(payload)
    for name, check in checks.items():
        if out.get(name):
            out[name] = check(out[name]).value or out[name]
    return out


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
