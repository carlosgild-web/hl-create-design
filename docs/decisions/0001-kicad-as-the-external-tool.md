# 0001: KiCad 9 as the external design tool

**Status:** accepted (2026-11-17)

## Context

Create Design starts a new schematic project with the company title block already
filled in. It needs a real EDA tool whose files it can generate without running the
tool's GUI, and whose output (a PDF) can be produced headlessly in CI and in a container.
The usual commercial tools (Altium, OrCAD) use binary or licensed formats and can't run
in a free cloud demo.

## Decision

Use **KiCad 9**:

- **Text variables in `.kicad_pro`** (`text_variables`) carry the company fields
  (`HL_DESIGN_NUMBER`, `HL_SAP_MATERIAL`, `HL_PROJECT`, `HL_DEPARTMENT`, `HL_DESIGNER`).
- **A custom drawing sheet `.kicad_wks`** lays out the H&L title block and logo and
  references those variables plus the built-ins (`${TITLE}`, `${REVISION}`,
  `${ISSUE_DATE}`, `${COMPANY}`).
- **The `title_block` in `.kicad_sch`** holds title, revision, date and company.
- **`kicad-cli sch export pdf|svg`** produces the preview, with its path from `KICAD_CLI`.

All three files are S-expression or JSON text, so the generator is plain file rendering
from a template that can be checked with golden-file tests.

## Consequences

- Open source and free: the demo, CI and Docker image can all run it.
- The official KiCad Docker image includes `kicad-cli`, so Phase 7 builds on it.
- Unit tests never need KiCad. Only the export test needs `kicad-cli`; it is marked
  `kicad` and runs in a dedicated CI job inside the KiCad image.
- KiCad's file formats change between major versions. The template targets KiCad 9 and
  the README says so.
