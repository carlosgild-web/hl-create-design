"""Command line: `python -m app.cli create-design --dept HW --number HL-HW-26-0042 ...`.

Exit codes: 0 created, 1 refused by a rule or by the file system, 2 bad arguments,
3 kicad-cli failed (nothing was kept).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from app.core.config import Settings, get_settings
from app.designs import DesignValidationError, create_design
from app.kicad.exporter import ExportError
from app.kicad.renderer import DesignFolderExistsError
from app.standards.validators import DesignRequest, Issue, UnsafePathError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create-design", help="Create a KiCad project from the company template"
    )
    create.add_argument("--dept", required=True, help="Department code: HW, PWR, EMB or TFX")
    create.add_argument("--number", required=True, help="Design number, e.g. HL-HW-26-0042")
    create.add_argument("--rev", required=True, help="Revision letter, e.g. A")
    create.add_argument("--name", required=True, help="Design name, e.g. 'Bead Drill Controller'")
    create.add_argument(
        "--designer", required=True, help="Initial and surname, e.g. 'C. Velazquez'"
    )
    create.add_argument("--material", default="", help="SAP material number (until Phase 4)")
    create.add_argument("--project", default="", help="WBS element, e.g. P-26-0108 (until Phase 4)")
    create.add_argument("--date", default="", help="Issue date YYYY-MM-DD (default: today)")
    create.add_argument(
        "--no-export", action="store_true", help="Skip the kicad-cli PDF/SVG export"
    )
    return parser


def _issue_line(kind: str, issue: Issue) -> str:
    return f"{kind} [{issue.field}] {issue.message} (manual: {issue.ref})"


def run_create_design(args: argparse.Namespace, settings: Settings) -> int:
    request = DesignRequest(
        department=args.dept,
        design_number=args.number,
        revision=args.rev,
        name=args.name,
        designer=args.designer,
        sap_material=args.material,
        project=args.project,
        issue_date=args.date,
    )
    try:
        created = create_design(request, settings=settings, export=not args.no_export)
    except DesignValidationError as exc:
        for issue in exc.report.errors:
            print(_issue_line("error", issue), file=sys.stderr)
        return 1
    except UnsafePathError as exc:
        print(_issue_line("error", exc.issue), file=sys.stderr)
        return 1
    except DesignFolderExistsError as exc:
        print(f"error {exc} (manual: 04-folder-structure#revision-folders)", file=sys.stderr)
        return 1
    except ExportError as exc:
        print(f"error {exc}", file=sys.stderr)
        if exc.log:
            print(exc.log, file=sys.stderr)
        print("Nothing was kept. Fix KICAD_CLI or use --no-export.", file=sys.stderr)
        return 3

    req = created.request
    print(f"Created {req.design_number} rev {req.revision}: {req.name}")
    print(f"  folder:    {created.project.folder}")
    print(f"  project:   {created.project.project_file.name}")
    print(f"  schematic: {created.project.schematic_file.name}")
    if created.export:
        print(f"  pdf:       {created.export.pdf}")
    for warning in created.warnings:
        print(_issue_line("warning", warning))
    print(f"  audit id:  {created.audit_id}")
    return 0


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    settings = settings or get_settings()
    if args.command == "create-design":
        return run_create_design(args, settings)
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":
    sys.exit(main())
