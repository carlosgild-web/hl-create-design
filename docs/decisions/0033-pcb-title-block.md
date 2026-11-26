# 0033: The board gets the company title block too

**Status:** accepted (2026-11-26). Extends 0018, 0019 and 0030.

## Context

Up to v1.0.0 a created design had a `.kicad_pro`, a `.kicad_sch` and the drawing sheet. Only
the schematic editor used the company drawing sheet. The PCB editor showed KiCad's default
sheet with an empty title block, so the engineer had to type the design number, revision
and the other fields again for the board, which is the kind of retyping this tool exists to
remove.

Checked on 2026-11-26 with KiCad 9.0.8:
- A project's text variables (`${HL_DESIGN_NUMBER}`, ...) are project-wide. The PCB editor
  reads them from the `.kicad_pro` like the schematic editor does.
- The PCB editor takes its drawing sheet from `pcbnew.page_layout_descr_file` in the
  `.kicad_pro`.
- The built-in fields (title, date, revision, company, comment 1) are stored separately in
  the `.kicad_sch` and in the `.kicad_pcb`. KiCad never copies them from one to the other.

## Decision

1. The template gets an empty KiCad 9 board, `kicad/template/hl_template.kicad_pcb`:
   - A4;
   - the standard two copper layers;
   - an empty title block;
   - no outline and no footprints.

   The renderer copies it as `<DesignNumber>_<Rev>.kicad_pcb`.
2. The `.kicad_pro` points both editors at `hl_title_block.kicad_wks`.
3. The renderer writes the same `TitleBlock` into the schematic and into the board, so the
   two never disagree. Both go through one function, `replace_title_block`.
4. After the schematic export, `kicad-cli pcb export pdf` and `pcb export svg` write
   `<stem>_pcb.pdf` and `<stem>_pcb.svg` into `output/`. They plot Edge.Cuts and the
   drawing sheet (the frame and the title block).
   - If the board export fails after a good schematic export, the design is kept with a
     `pcb_pdf_not_exported` warning.
   - When KiCad is missing, only the existing `pdf_not_exported` warning is shown.
   - The audit row records `pcb_pdf`.
5. The preview dialog gets a **Schematic | PCB** switch. It appears when the board has a
   preview, so designs made before this decision show no switch. The PDF links follow the
   switch. The board is served by `GET /api/designs/.../pcb.{pdf,svg}`, with the same path
   checks as `preview.{pdf,svg}`.
6. **Open PCB** starts `pcbnew` with the board, through `POST .../open?target=pcb`. It falls
   back to the Project Manager, like Open in KiCad. Only the user's click starts it, it
   writes nothing, and it is audited with `target`.

## Consequences

- One more file per revision folder, and about one second more of export time.
- The engineer still updates the board's title block by hand after a revision changes;
  Create Design only creates the first one, like the schematic.
- Older designs keep working: the dialog shows no PCB switch and no Open PCB button for
  them.
