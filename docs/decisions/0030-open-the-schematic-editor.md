# 0030: "Open in KiCad" opens the schematic editor

**Status:** accepted (2026-11-22). Amends 0019.

## Context

Decision 0019 added "Open in KiCad". It starts the KiCad Project Manager (`kicad.exe`) with
the `.kicad_pro`. The engineer then sees a file list and still has to double-click the
schematic to see what the tool made: the drawing with the company title block filled in.
The explainer video (decision 0028) wants to end on that title block. A click that opens
it at once is also the better product.

Checked on 2026-11-22 with KiCad 9.0 on the HL-HW-26-0049 design. Started on its own with
the `.kicad_sch`, `eeschema.exe` loads the `.kicad_pro` next to it. The title block then
shows the filled text variables: number, title, description, department, project, SAP
material, designer, date and revision. The window title is "HL-HW-26-0049_A — Schematic
Editor", with no path.

## Decision

1. "Open in KiCad" starts KiCad's **schematic editor** (`eeschema`, next to `kicad-cli`) with
   `<design>_<rev>.kicad_sch`.
2. When eeschema or the schematic is missing, it starts the Project Manager with the
   `.kicad_pro`, as before. When neither can start, it answers 404, or 409 when Open is
   turned off or no KiCad GUI is installed.
3. Unchanged from 0019:
   - only the user's click starts it;
   - it writes no file and calls no SAP;
   - the folder is resolved inside `DESIGNS_ROOT`;
   - it is audited (`design_opened`), and the audit's `program` now says which program
     started.
4. The status line says "KiCad's schematic editor is opening with the design" (EN/ES). The
   button keeps its label.

## Consequences

- One click from the preview dialog to the drawing. The Project Manager is still one
  File › Open Project away, and the "Project file" path in the dialog says where it is.
- KiCad standalone eeschema works on the project's schematic with the project's settings.
  Saving from there writes the design's own files, as before.
