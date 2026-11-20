# 0020: UI polish pass and a live title-block preview

**Status:** accepted (2026-11-20)

## Context

Block 6 of the Phase 8 UI plan is a polish pass with the `frontend-design` skill, within the
palette (0014) and the three-column layout (0018). The screenshots showed:
- three equal-weight column headings
- a mode toggle whose label wrapped at 1440 px
- chat bubbles and the confirmation card with the same visual weight
- codes set in the system monospace font
- a form column that ended halfway down the screen

## Decision

1. **Live title-block preview** (user's choice) under the form: a drawn copy of
   `kicad/template/hl_title_block.kicad_wks` with the same cells and labels, and column
   widths 50/45/45/40 mm. It fills in as the form changes, and each value is tinted by its
   source (sea for SAP, amber for the assistant). The name shows as the validators normalize
   it. It is display only: files are still written by the renderer after Confirm
   (invariant 2). The labels stay in English, as the drawing sheet prints them.
2. **Codes in Geist with tabular figures** (user's choice) instead of the system monospace.
   It's one type family across the UI. The demo-guide banner is shared across the portfolio
   and stays as it is.
3. **Hierarchy:**
   - Column headings drop to 15 px / 600.
   - The Start mode is two stacked choice rows, each with a one-line description. The radio
     names are unchanged, so tests are unaffected.
   - In the chat, assistant text has no bubble, and user bubbles are narrower.
   - The confirmation card has a header strip colored by state (pending cobalt, confirmed
     success, failed destructive, cancelled or stale muted) and a focus halo while it waits.
4. **Layout:** the wide form column is as tall as the other two, and the phone chat panel
   fits the viewport (with its input).

## Consequences

No new dependency. New unit test `TitleBlockPreview.test.tsx`. The e2e suite and the
showcase screenshots pass unchanged. If the drawing sheet changes, update the preview too:
it mirrors the layout by hand.
