"""The create_design() service and the CLI, end to end with a fake kicad-cli."""

from datetime import date

import pytest

from app import cli
from app.core.config import Settings
from app.db.session import audit_rows, get_engine
from app.designs import DesignValidationError, create_design
from app.kicad.exporter import ExportError
from app.kicad.renderer import DesignFolderExistsError
from app.standards.validators import DesignRequest
from tests.test_exporter import FakeKicadCli

TODAY = date(2026, 11, 17)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        designs_root=tmp_path / "designs",
        data_dir=tmp_path / "data",
        kicad_cli="kicad-cli",
    )


def request(**changes) -> DesignRequest:
    fields = {
        "department": "HW",
        "design_number": "HL-HW-26-0042",
        "revision": "A",
        "name": "bead drill controller",
        "designer": "C. Velazquez",
        "sap_material": "000000000040001234",
        "project": "P-26-0108",
    }
    return DesignRequest(**(fields | changes))


def test_creates_the_revision_with_pdf_and_audit(settings):
    fake = FakeKicadCli()
    created = create_design(request(), settings=settings, today=TODAY, runner=fake)

    folder = settings.designs_root / "HW" / "HL-HW-26-0042" / "A"
    assert created.project.folder == folder.resolve()
    assert created.relative_folder == "HW/HL-HW-26-0042/A"
    assert created.request.name == "Bead Drill Controller"
    assert created.export and created.export.pdf.name == "HL-HW-26-0042_A.pdf"

    schematic = created.project.schematic_file.read_text(encoding="utf-8")
    assert '(title "Bead Drill Controller")' in schematic
    assert '(date "2026-11-17")' in schematic
    project = created.project.project_file.read_text(encoding="utf-8")
    assert '"HL_SAP_MATERIAL": "40001234"' in project

    [row] = audit_rows(get_engine(settings.data_dir))
    assert row.action == "design_created"
    assert (row.actor, row.design_number, row.revision) == ("C. Velazquez", "HL-HW-26-0042", "A")
    assert row.details["folder"] == "HW/HL-HW-26-0042/A"
    assert row.details["pdf"] is True
    assert row.details["pcb_pdf"] is True

    # Decision 0033: the board has the same title block and its own PDF.
    board = created.project.board_file.read_text(encoding="utf-8")
    assert '(title "Bead Drill Controller")' in board
    assert created.board_export and created.board_export.pdf.name == "HL-HW-26-0042_A_pcb.pdf"


def test_a_failed_board_export_keeps_the_schematic_pdf(settings):
    def board_fails(command, **kwargs):
        if command[1] == "pcb":
            return FakeKicadCli(returncode=2)(command, **kwargs)
        return FakeKicadCli()(command, **kwargs)

    created = create_design(request(), settings=settings, today=TODAY, runner=board_fails)

    assert created.export is not None and created.board_export is None
    [warning] = [w for w in created.warnings if w.code == "pcb_pdf_not_exported"]
    assert "exit code 2" in warning.params["detail"]
    assert not [w for w in created.warnings if w.code == "pdf_not_exported"]
    [row] = audit_rows(get_engine(settings.data_dir))
    assert row.details["pdf"] is True and row.details["pcb_pdf"] is False


def test_a_missing_kicad_cli_gives_one_warning_only(settings):
    def missing(command, **kw):
        raise FileNotFoundError(command[0])

    created = create_design(request(), settings=settings, today=TODAY, runner=missing)
    assert [w.code for w in created.warnings if w.field == "pdf"] == ["pdf_not_exported"]


def test_next_revision_follows_the_folders_on_disk(settings):
    create_design(request(), settings=settings, today=TODAY, export=False)

    with pytest.raises(DesignValidationError) as caught:
        create_design(request(revision="A"), settings=settings, today=TODAY, export=False)
    assert [e.code for e in caught.value.report.errors] == ["rev_reused"]

    with pytest.raises(DesignValidationError) as caught:
        create_design(request(revision="C"), settings=settings, today=TODAY, export=False)
    assert [e.code for e in caught.value.report.errors] == ["rev_jump"]

    created = create_design(request(revision="b"), settings=settings, today=TODAY, export=False)
    assert created.request.revision == "B"


def test_invalid_request_creates_nothing(settings):
    with pytest.raises(DesignValidationError) as caught:
        create_design(request(revision="I", name="x"), settings=settings, export=False)
    assert {e.code for e in caught.value.report.errors} == {"rev_skipped_letter", "name_length"}
    assert not settings.designs_root.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"revision": "..\\..\\Windows"},
        {"revision": "../../etc"},
        {"design_number": "..\\..\\Windows"},
        {"department": "..", "design_number": "HL-HW-26-0042"},
        {"department": "C:\\", "design_number": "HL-HW-26-0042"},
    ],
)
def test_path_traversal_is_refused(settings, tmp_path, changes):
    with pytest.raises(DesignValidationError):
        create_design(request(**changes), settings=settings, export=False)
    assert not settings.designs_root.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_a_failed_export_keeps_the_project_without_a_pdf(settings):
    created = create_design(
        request(), settings=settings, today=TODAY, runner=FakeKicadCli(returncode=1)
    )
    assert created.export is None
    folder = settings.designs_root / "HW" / "HL-HW-26-0042" / "A"
    assert (folder / "HL-HW-26-0042_A.kicad_pro").is_file()
    [warning] = [w for w in created.warnings if w.code == "pdf_not_exported"]
    assert warning.params["variant"] == "failed" and warning.ref == "08-using-create-design#no-pdf"
    [row] = audit_rows(get_engine(settings.data_dir))
    assert row.details["pdf"] is False and "pdf_not_exported" in row.details["warnings"]


def test_a_missing_kicad_cli_is_named_as_such(settings):
    def missing(command, **kw):
        raise FileNotFoundError(command[0])

    created = create_design(request(), settings=settings, today=TODAY, runner=missing)
    [warning] = [w for w in created.warnings if w.code == "pdf_not_exported"]
    assert warning.params == {"variant": "not_installed"}


def test_an_audit_failure_removes_the_folder(settings, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr("app.designs.write_audit", broken)
    with pytest.raises(RuntimeError):
        create_design(request(), settings=settings, today=TODAY, export=False)
    assert not (settings.designs_root / "HW" / "HL-HW-26-0042" / "A").exists()


def test_existing_folder_is_never_overwritten(settings, monkeypatch):
    folder = settings.designs_root / "HW" / "HL-HW-26-0042" / "A"
    folder.mkdir(parents=True)
    # The folder exists, but pretend the disk scan missed it (a race with another user).
    monkeypatch.setattr("app.designs.v.revisions_on_disk", lambda *a: [])
    with pytest.raises(DesignFolderExistsError):
        create_design(request(), settings=settings, today=TODAY, export=False)
    assert list(folder.iterdir()) == []


# --- CLI -------------------------------------------------------------------------------

ARGS = [
    "create-design",
    "--dept",
    "HW",
    "--number",
    "HL-HW-26-0042",
    "--rev",
    "A",
    "--name",
    "Bead Drill Controller",
    "--designer",
    "C. Velazquez",
    "--date",
    "2026-11-17",
]


def test_cli_creates_a_design(settings, capsys):
    assert cli.main([*ARGS, "--no-export"], settings=settings) == 0
    out = capsys.readouterr().out
    assert "Created HL-HW-26-0042 rev A: Bead Drill Controller" in out
    assert (settings.designs_root / "HW" / "HL-HW-26-0042" / "A").is_dir()


def test_cli_explains_errors_with_manual_references(settings, capsys):
    args = [*ARGS, "--no-export"]
    args[args.index("A")] = "I"
    assert cli.main(args, settings=settings) == 1
    err = capsys.readouterr().err
    assert "error [revision]" in err
    assert "(manual: 02-revisions#skipped-letters)" in err


def test_cli_keeps_the_project_and_reports_a_missing_pdf(settings, capsys, monkeypatch):
    monkeypatch.setattr(
        "app.designs.export_schematic",
        lambda *a, **k: (_ for _ in ()).throw(ExportError("kicad-cli not found")),
    )
    assert cli.main(ARGS, settings=settings) == 3
    out = capsys.readouterr()
    assert "Created HL-HW-26-0042" in out.out and "pdf_not_exported" not in out.err
    assert "No PDF" in out.err


def test_cli_requires_the_fields(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["create-design", "--dept", "HW"])
    assert caught.value.code == 2
