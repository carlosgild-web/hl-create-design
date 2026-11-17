# 0008: Choices in the KiCad generator (Phase 3)

**Status:** accepted (2026-11-17)

## Context

Phase 3 builds `create_design()` and its CLI before the backend can talk to SAP
(`SapClient` arrives in Phase 4). PLAN.md describes the CLI without the SAP material and
the project, which the title block shows. It also doesn't say what happens when the PDF
export fails after the project files were written, or how relative paths in `.env` are read.

## Decision

1. **SAP fields as CLI flags until Phase 4.** `create-design` takes optional `--material`
   and `--project`. They are checked by the validators like every other field; when they
   are missing, the title block leaves them empty. From Phase 4 the service gets them
   from SAP through `SapClient`, and the flags remain only for offline use.
2. **All or nothing.** A revision is created completely (project files, PDF and SVG,
   audit row) or not at all. If `kicad-cli` fails or the audit write fails, the revision
   folder that this call created is removed again. `--no-export` skips the export on
   machines without KiCad. This follows the manual: Create Design never overwrites a
   folder and nothing is created halfway (04-folder-structure, 06-sap-statuses).
3. **Revisions on disk count as existing.** Until SAP is connected, the revision rules
   (no reuse, no jumps) are checked against the revision folders that exist under
   `DESIGNS_ROOT`. SAP will add the revisions that were abandoned or deleted.
4. **Relative storage paths are relative to the repo.** `DESIGNS_ROOT=./data/designs`
   means the repo's `data/designs`, whatever the working directory is, so the CLI run
   from `backend/` and the server write to the same place.
5. **The template schematic is generated once, then committed.** The buck-stage circuit
   uses symbols from the KiCad 9 standard library, embedded in the schematic, so the file
   opens without any library configured. It passes ERC with no errors.

## Consequences

- The title block of a design created offline can lack the SAP material and project.
  The manual says to never type the material by hand; the flags are a developer tool,
  and the UI (Phase 5) will not offer them.
- A failed export leaves no partial folder, so retrying with the same revision works.
- On a machine where KiCad is installed for the current user only (the winget default),
  `kicad-cli` lives under `%LOCALAPPDATA%\Programs\KiCad\9.0\bin\`, not `Program Files`.
