# 0035: Find KiCad in its install folder, and say what is missing

**Status:** accepted (2026-11-26).

## Context

A test of the GitHub download on Windows, on a PC with KiCad 9 installed, found that:
- the created design had an empty `output/` folder (no PDF);
- the preview dialog showed no Open in KiCad button.

Cause:
- The clone has no `.env`, so `KICAD_CLI` was its default, `kicad-cli`.
- The KiCad 9 installers for Windows (all users or per user, winget) and macOS don't add
  `kicad-cli` to the `PATH`.
- So the app found no KiCad, and said so only in two places that are easy to miss:
  - a one-line note in `start.cmd`. It was skipped whenever `.env` existed, because
    `.env.example` always has a `KICAD_CLI=` line;
  - the `pdf_not_exported` warning on the confirmation card.
- The Open button was hidden without any explanation.

## Decision

1. **Search the standard folders.** When `KICAD_CLI` is the bare default and not on the
   `PATH`, `app/kicad/locate.py` tries the standard KiCad 9 install folders:
   - Windows: `%ProgramFiles%\KiCad\9.0\bin` and `%LOCALAPPDATA%\Programs\KiCad\9.0\bin`;
   - macOS: `/Applications/KiCad/KiCad.app/Contents/MacOS`;
   - Linux: `/usr/bin`, `/usr/local/bin` and `/snap/bin`.

   `Settings` does this once, so every caller gets the resolved path. An explicit path is
   never replaced by a guess; if it is wrong, the messages name it. `KICAD_AUTODETECT=false`
   turns the search off. Tests and the eval harness turn it off, so they never depend on the
   machine's KiCad.
2. **`GET /api/kicad`** says whether KiCad was found, where, which version, and whether
   export, Open in KiCad and Open PCB can work.
3. **`python -m app.cli kicad-check`** replaces the start scripts' one-line note. It prints
   either "KiCad 9.0.8 found: <path>", or what works without KiCad, what needs it, the
   download link, and the `KICAD_CLI` hint. It always exits 0: KiCad is optional.
4. **In-app notice.** When KiCad is not found, the preview dialog shows a note in EN and ES:
   - the project files were created;
   - the PDF, the preview, Open in KiCad and Open PCB need KiCad 9;
   - a link to download it.
5. **README.** A "What each feature needs" table: feature, what it needs, and what happens
   without it.

## Consequences

- A clone on a machine with KiCad installed in its default folder works with no `.env`
  changes.
- `kicad-check` runs `kicad-cli version` once per start (about a second). The result is
  cached in the backend process.
- A KiCad installed in a non-standard folder still needs `KICAD_CLI`. Now both the start
  script and the app say so.
