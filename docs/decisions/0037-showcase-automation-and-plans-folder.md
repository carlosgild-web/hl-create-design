# 0037: `npm run showcase`, no local paths in the images, and `docs/plans/`

**Status:** accepted (2026-11-27). Extends 0028 and 0036. Phase 11 (portfolio README standard).

## Context

The portfolio README standard (shared by every Hilda & Luna repo) asks for the same GIF
pipeline in each repo, no local paths or secrets in any image, and a root folder with only
what a visitor needs. Three things fell short here:

- The GIF was turned from a WebM into `demo.gif` by hand, with an ffmpeg command copied from
  a comment, and the screenshots ran only with `SHOWCASE=1`.
- The preview dialog shows the project file's absolute path. The README GIF (its last
  seconds) and `desktop-preview-dialog.png` showed `C:\MyData\...\e2e\.tmp\backend\designs\...`.
  The video already blurred it (`video/record.spec.ts`).
- `PLAN-phase-9-review-and-faq.md` sat at the root, and decision 0028 and
  `video/storyboard.json` cited two plans in `Claude outputs/`, a folder that is not in git.

## Decision

1. **`npm run showcase`** writes the screenshots, and **`npm run showcase:gif`** records the
   GIF on fresh servers (it creates revision C, as the screenshot run does). The scripts are
   the ones hl-bead-studio uses. The GIF test saves the WebM and converts it with `toGif`
   (ported from hl-bead-studio): the standard's filter with `stats_mode=diff` and
   `diff_mode=rectangle`, trimmed from the loaded page to the last hold. `SHOWCASE=1` still
   works. A plain `npx playwright test` (CI) skips the file.
2. **Every showcase page blurs the path** (`code[title]`, the dialog's project file) with
   an init script, as the video does. The GIF and `desktop-preview-dialog.png` were
   re-recorded with the real `kicad-cli`: same flow, 30.8 s, 5.4 MB (was 33 s, 5.7 MB). The
   other screenshots don't show the path and were kept.
3. **Phase plans live in `docs/plans/`** (committed): the Phase 9 plan, the video plan and
   the video storyboard. Their references were updated (decisions 0021–0026 and 0028,
   `video/storyboard.json`). `Claude outputs/` holds local drafts only and is gitignored.

## Consequences

- No product code changed. The flag and the path only affect the showcase test.
- Regenerating the README images is two commands, documented in the header of
  `e2e/tests/showcase.spec.ts`.
