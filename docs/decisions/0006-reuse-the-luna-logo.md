# 0006: Reuse the Hilda & Luna logo from luna-hybrid-agent

**Status:** accepted (2026-11-17)

## Context

PLAN.md (Phase 1) asked for a new "H&L" monogram for the title block. But Hilda & Luna
Beadworks already has a logo in the previous portfolio project, `luna-hybrid-agent`: a
crescent moon made of glass beads with a hanging star, in the navy, cobalt, amber, opal
and sea palette. This tool belongs to the same fictional company.

## Decision

Reuse the luna mark instead of drawing a new monogram (Carlos's choice, 2026-11-17).

- `kicad/template/hl_logo.svg` is the mark alone, taken from luna's
  `frontend/public/hl-logo.svg` without the wordmark and cropped to the beads.
- `kicad/template/hl_logo.png` is the bitmap that KiCad embeds in the drawing sheet:
  250 × 300 px RGBA with a transparent background, rendered from the SVG with headless
  Chrome. Re-render it after changing the SVG.
- The company name is not in the bitmap. The title block draws it as KiCad text
  (`${COMPANY}`), which stays sharp at any zoom and can be searched in the PDF.
- `frontend/public/favicon.svg` is luna's `hl-mark.svg` (the mark on a navy tile).

## Consequences

- The same brand across the portfolio projects, as Phase 5 already asks for the UI.
- The mark has many small beads. At title-block size (about 12 mm) it reads as a
  crescent of coloured dots, which is enough for a logo; it isn't meant to be read in
  detail on a printed schematic.
