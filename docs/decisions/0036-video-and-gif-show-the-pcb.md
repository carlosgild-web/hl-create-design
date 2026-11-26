# 0036: The README GIF and the video show the PCB title block

**Status:** accepted (2026-11-26). Extends 0028, 0030 and 0032.

## Context

Decision 0033 adds the board, with the same company title block, a PCB preview and an
Open PCB button. The README's two showcases only showed the schematic:
- the GIF ends on the schematic's title block in the preview dialog;
- the 2-minute video ends in KiCad's schematic editor.

## Decision

1. **GIF** (`e2e/tests/showcase.spec.ts`, "recorded demo"). After the schematic's title
   block, the take clicks **PCB** in the preview dialog, waits for the board's SVG, and
   zooms into its title block. The export is the real `kicad-cli` (`E2E_REAL_KICAD=1`).
   `desktop-preview-dialog.png` is retaken because the dialog now has the Schematic | PCB
   switch. The other screenshots are unchanged.
2. **Video** (`video/`, the Groq take of decision 0032):
   - After the schematic editor's clip, the take clicks **Open PCB**. That is a new step,
     `open_pcb`, with storyboard row 3.6 and a callout to `render_board_file`.
   - `kicad.mjs` records the PCB editor's window as it does the schematic editor's. The
     editor is chosen by process (`eeschema` / `pcbnew`), and the files are `kicad.mp4` and
     `kicad-pcb.mp4`.
   - `cues-kicad.json` has one entry per clip: its zoom on the title block (measured on a
     recorded frame) and its subtitles.
   - `compose.mjs` takes a list of KiCad clips instead of one. `compose.test.mjs`
     (`npm run video:test`) checks the cut plan with two clips.
3. Re-composing the earlier published take, which has only the schematic clip, gives the
   same plan as before.

## Consequences

- The video is about 12 s longer. The README link changes once the new
  `video-readme.mp4` is uploaded to GitHub, which only works through the web editor.
- The demo take (`storyboard.json`, not published) still ends with the schematic editor
  only.
