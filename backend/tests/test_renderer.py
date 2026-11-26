"""Template rendering: golden `.kicad_pro`, title block in the `.kicad_sch` and the
`.kicad_pcb`, no overwrites."""

import json
import os
from pathlib import Path

import pytest

from app.kicad import renderer
from app.kicad.renderer import DesignFolderExistsError, TitleBlock, render_project

GOLDEN = Path(__file__).parent / "golden"
STEM = "HL-HW-26-0042_A"

BLOCK = TitleBlock(
    design_number="HL-HW-26-0042",
    revision="A",
    title="Bead Drill Controller",
    issue_date="2026-11-17",
    designer="C. Velazquez",
    department="HW – Hardware Design",
    sap_material="40001234",
    project="P-26-0108",
)


def template_text(suffix: str) -> str:
    return (renderer.TEMPLATE_DIR / f"{renderer.TEMPLATE_STEM}{suffix}").read_text(encoding="utf-8")


def test_rendered_project_file_matches_the_golden_file():
    rendered = renderer.render_project_file(template_text(".kicad_pro"), STEM, BLOCK)
    golden_file = GOLDEN / f"{STEM}.kicad_pro"
    if os.environ.get("UPDATE_GOLDEN") == "1":  # regenerate after a deliberate template change
        golden_file.write_text(rendered, encoding="utf-8", newline="\n")
    assert rendered == golden_file.read_text(encoding="utf-8")


def test_project_file_has_the_text_variables_and_the_drawing_sheet():
    project = json.loads(renderer.render_project_file(template_text(".kicad_pro"), STEM, BLOCK))
    assert project["meta"]["filename"] == f"{STEM}.kicad_pro"
    assert project["schematic"]["page_layout_descr_file"] == "hl_title_block.kicad_wks"
    assert project["pcbnew"]["page_layout_descr_file"] == "hl_title_block.kicad_wks"
    assert project["text_variables"] == {
        "HL_DESIGN_NUMBER": "HL-HW-26-0042",
        "HL_SAP_MATERIAL": "40001234",
        "HL_PROJECT": "P-26-0108",
        "HL_DEPARTMENT": "HW – Hardware Design",
        "HL_DESIGNER": "C. Velazquez",
    }


def test_schematic_gets_the_title_block_and_the_project_name():
    text = renderer.render_schematic_file(template_text(".kicad_sch"), STEM, BLOCK)
    assert text.count("(title_block") == 1
    assert '(title "Bead Drill Controller")' in text
    assert '(date "2026-11-17")' in text
    assert '(rev "A")' in text
    assert '(company "Hilda & Luna Beadworks")' in text
    assert '(project "hl_template"' not in text
    assert f'(project "{STEM}"' in text
    assert text.count("(") == text.count(")")


def test_board_gets_the_same_title_block():
    block = TitleBlock(**{**BLOCK.__dict__, "description": "Main board"})
    board = renderer.render_board_file(template_text(".kicad_pcb"), block)
    schematic = renderer.render_schematic_file(template_text(".kicad_sch"), STEM, block)
    assert board.startswith("(kicad_pcb")
    assert board.count("(title_block") == 1
    expected = renderer.title_block_sexpr(block)
    assert expected in board
    assert expected in schematic
    assert '(paper "A4")' in board
    assert board.count("(") == board.count(")")


def test_template_board_without_a_title_block_is_an_error():
    with pytest.raises(ValueError, match="board has no"):
        renderer.render_board_file("(kicad_pcb\n)", BLOCK)


def test_title_block_strings_are_escaped():
    block = TitleBlock(**{**BLOCK.__dict__, "title": 'Say "hi" \\ (bye)\nnow'})
    text = renderer.render_schematic_file(template_text(".kicad_sch"), STEM, block)
    assert '(title "Say \\"hi\\" \\\\ (bye)\\nnow")' in text


def test_template_drawing_sheet_uses_every_field():
    wks = (renderer.TEMPLATE_DIR / renderer.DRAWING_SHEET).read_text(encoding="utf-8")
    for variable in [*BLOCK.text_variables(), "TITLE", "REVISION", "ISSUE_DATE", "COMPANY"]:
        assert "${" + variable + "}" in wks, variable
    assert "(bitmap" in wks  # the H&L logo


def test_render_project_creates_the_revision_folder(tmp_path):
    folder = tmp_path / "HW" / "HL-HW-26-0042" / "A"
    project = render_project(folder, STEM, BLOCK)

    assert sorted(p.name for p in folder.iterdir()) == [
        f"{STEM}.kicad_pcb",
        f"{STEM}.kicad_pro",
        f"{STEM}.kicad_sch",
        "hl_title_block.kicad_wks",
        "output",
    ]
    assert project.output_dir.is_dir()
    assert b"\r\n" not in project.schematic_file.read_bytes()
    assert b"\r\n" not in project.board_file.read_bytes()
    assert '(title "Bead Drill Controller")' in project.board_file.read_text(encoding="utf-8")


def test_render_project_never_overwrites(tmp_path):
    folder = tmp_path / "A"
    folder.mkdir()
    (folder / "keep.txt").write_text("mine", encoding="utf-8")

    with pytest.raises(DesignFolderExistsError):
        render_project(folder, STEM, BLOCK)
    assert [p.name for p in folder.iterdir()] == ["keep.txt"]


def test_failed_render_removes_the_folder(tmp_path):
    folder = tmp_path / "A"
    with pytest.raises(FileNotFoundError):
        render_project(folder, STEM, BLOCK, template_dir=tmp_path / "missing")
    assert not folder.exists()
