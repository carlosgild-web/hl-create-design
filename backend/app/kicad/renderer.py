"""Copy the company KiCad template into a revision folder and fill in the title block.

The template (`kicad/template/`) is a complete KiCad 9 project. Rendering it:

- renames `hl_template.kicad_pro/.kicad_sch` to `<DesignNumber>_<Rev>.*`
  (04-folder-structure#file-names) and copies the drawing sheet `hl_title_block.kicad_wks`;
- writes the company fields as project text variables (`${HL_DESIGN_NUMBER}`, ...) in the
  `.kicad_pro`, which the drawing sheet shows;
- writes the built-in fields (`${TITLE}`, `${REVISION}`, `${ISSUE_DATE}`, `${COMPANY}`) in
  the schematic's `(title_block ...)`.

The values arrive already validated and normalized (`standards/validators.py`); this module
only escapes them. It never overwrites: the revision folder must not exist (invariant 3 and
04-folder-structure#revision-folders), and a failed render removes the folder it created.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.config import REPO_ROOT

TEMPLATE_DIR = REPO_ROOT / "kicad" / "template"
TEMPLATE_STEM = "hl_template"
DRAWING_SHEET = "hl_title_block.kicad_wks"
OUTPUT_DIR = "output"
COMPANY = "Hilda & Luna Beadworks"


class DesignFolderExistsError(FileExistsError):
    """The revision folder already exists; nothing was changed."""


@dataclass(frozen=True)
class TitleBlock:
    """Every value the title block shows, already validated and in display form."""

    design_number: str
    revision: str
    title: str
    issue_date: str  # YYYY-MM-DD
    designer: str
    department: str  # "HW – Hardware Design"
    sap_material: str = ""  # without leading zeros, "" if unknown
    project: str = ""  # WBS element, "" if unknown
    company: str = COMPANY

    def text_variables(self) -> dict[str, str]:
        """The project text variables the drawing sheet uses."""
        return {
            "HL_DESIGN_NUMBER": self.design_number,
            "HL_SAP_MATERIAL": self.sap_material,
            "HL_PROJECT": self.project,
            "HL_DEPARTMENT": self.department,
            "HL_DESIGNER": self.designer,
        }


@dataclass(frozen=True)
class RenderedProject:
    folder: Path
    project_file: Path
    schematic_file: Path
    drawing_sheet: Path
    output_dir: Path


# --- pure text transforms (golden-file tested) ------------------------------------------


def render_project_file(template_text: str, stem: str, block: TitleBlock) -> str:
    """The `.kicad_pro` (JSON) with the new file name, drawing sheet and text variables."""
    project = json.loads(template_text)
    project.setdefault("meta", {})["filename"] = f"{stem}.kicad_pro"
    project.setdefault("schematic", {})["page_layout_descr_file"] = DRAWING_SHEET
    project["text_variables"] = block.text_variables()
    return json.dumps(project, indent=2, ensure_ascii=False) + "\n"


def sexpr_string(value: str) -> str:
    """A KiCad s-expression string literal."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def title_block_sexpr(block: TitleBlock, indent: str = "\t") -> str:
    inner = indent * 2
    return (
        f"{indent}(title_block\n"
        f"{inner}(title {sexpr_string(block.title)})\n"
        f"{inner}(date {sexpr_string(block.issue_date)})\n"
        f"{inner}(rev {sexpr_string(block.revision)})\n"
        f"{inner}(company {sexpr_string(block.company)})\n"
        f"{indent})"
    )


def _sexpr_span(text: str, start: int) -> int:
    """Index just past the s-expression that opens at `text[start] == "("`."""
    depth, i, in_string = 0, start, False
    while i < len(text):
        char = text[i]
        if in_string:
            if char == "\\":
                i += 1
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced s-expression in the template schematic")


def render_schematic_file(template_text: str, stem: str, block: TitleBlock) -> str:
    """The `.kicad_sch` with the new title block and the project name in symbol instances."""
    start = template_text.find("(title_block")
    if start < 0:
        raise ValueError("the template schematic has no (title_block ...)")
    line_start = template_text.rfind("\n", 0, start) + 1
    indent = template_text[line_start:start]
    end = _sexpr_span(template_text, start)
    text = template_text[:line_start] + title_block_sexpr(block, indent) + template_text[end:]
    # Symbol instances name the project they belong to; keep references after the rename.
    return text.replace(f"(project {sexpr_string(TEMPLATE_STEM)}", f"(project {sexpr_string(stem)}")


# --- files ---------------------------------------------------------------------------


def render_project(
    folder: Path, stem: str, block: TitleBlock, template_dir: Path = TEMPLATE_DIR
) -> RenderedProject:
    """Create `folder` (it must not exist) with the rendered project and an `output/` folder."""
    folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()
    except FileExistsError as exc:
        raise DesignFolderExistsError(f"{folder} already exists; nothing was changed") from exc

    try:
        project_file = folder / f"{stem}.kicad_pro"
        schematic_file = folder / f"{stem}.kicad_sch"
        drawing_sheet = folder / DRAWING_SHEET
        output_dir = folder / OUTPUT_DIR

        pro_template = (template_dir / f"{TEMPLATE_STEM}.kicad_pro").read_text(encoding="utf-8")
        sch_template = (template_dir / f"{TEMPLATE_STEM}.kicad_sch").read_text(encoding="utf-8")
        _write(project_file, render_project_file(pro_template, stem, block))
        _write(schematic_file, render_schematic_file(sch_template, stem, block))
        shutil.copyfile(template_dir / DRAWING_SHEET, drawing_sheet)
        output_dir.mkdir()
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise

    return RenderedProject(folder, project_file, schematic_file, drawing_sheet, output_dir)


def _write(path: Path, text: str) -> None:
    # newline="\n": KiCad writes LF on every platform; keep the files identical everywhere.
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
