# 0023: Revisions are recorded in SAP, no PDF is a warning, and the card shows what to check

**Status:** accepted (2026-11-21)

## Context

Phase 9 block 9c (`PLAN-phase-9-review-and-faq.md`, findings 4, 7–9, 12–14 and 18; open
questions Q3, Q4 and Q8).
- Revisions created in Create Design never reached SAP. The list showed "latest B → rev E",
  and a cleanup that deleted folders could free letters again (`02-revisions#never-reuse`).
- Without `kicad-cli` a create failed and kept nothing, although the README says KiCad is
  optional.
- The RELEASED/ECO warning showed in the Start panel but not on the card, where the user
  decides.
- After a reservation the name stayed editable. After a create, Undo and Get SAP number
  stayed available, so a duplicate number could be reserved.

## Decision

1. **Revisions in SAP (Q3: option A).**
   - The mock SAP has `POST RevisionSet` (CSRF like the reservation). It accepts only the
     next free letter, and refuses BLOCKED and OBSOLETE designs with codes `ZHL_PLM/020`,
     `/021` and `/022`.
   - The backend calls it with `SapClient.add_revision`, and `fake_sap` mirrors it.
   - `CurrentRevision` now sorts by length, then by letter, so `AA` comes after `Y`. The
     metadata allows two-letter revisions.
2. **SAP first (Q4).** Inside the confirm (invariant 2), `create_design` checks the rules,
   then checks that the folder doesn't exist, then records the revision in SAP through the
   caller's `record_revision`, then writes the folder.
   - Revision A of a reserved number is already in SAP, so it isn't recorded again.
   - If SAP refuses, nothing is on disk, and the card shows the SAP failure.
   - A failure after the folder was written, other than the export, still removes the
     folder, so every folder has an audit row (invariant 8). The audit row records
     `sap_revision_recorded`.
3. **No PDF is a warning (Q8).** Any export failure (`kicad-cli` missing, crashing or timing
   out) keeps the project, and the result carries a `pdf_not_exported` warning. Its variant
   is `not_installed` or `failed`, and it cites `08#no-pdf`. Rolling back would leave SAP
   with a revision that has no project. The CLI still exits with 3, so CI notices, but the
   project is kept. Error kind `export` and HTTP 500 are gone from the confirm endpoint.
4. **Warnings on the card before Confirm (finding 7).**
   - `POST /api/actions` (the form) runs the same read-only `check_fields` as the inline
     check, including the SAP same-name list, and stores its warnings in the card payload.
     The assistant's `request_create_design` already did this; `request_reserve_number`
     now does too.
   - Warnings sent by the client are ignored.
   - The card lists them above Confirm with the form's warning style (⚠, muted box), not
     amber: decision 0014 reserves amber for values the assistant suggested.
5. **Locked after reservation (finding 8).** In new mode, once SAP issued the number,
   department and name are read-only (also for the assistant's proposals). Undo clears the
   number and unlocks them. The designer stays editable, as in existing mode, because SAP
   doesn't fix it. A different name for a just-reserved number gets its own wording
   (`name_differs_from_sap.reserved`).
6. **After Create (finding 9).** Undo is hidden on the reservation card and in the Start
   panel, and Get SAP number stays disabled until **New design**.
7. **Smaller fixes.**
   - Finding 12: the "Started over" notice says "waiting cards were cancelled" only when a
     card was pending; otherwise it says that earlier cards stay in the history.
   - Finding 13: `useValidation` reports `checking`. A Create click during the check shows
     "Checking…" and runs once the answer for those values says they're valid. An edit in
     between drops the click.
   - Finding 14: the title-block preview wraps the description instead of cutting it.

## Consequences

- Revision folders created before this change (C and D in the review) still count from disk.
  SAP doesn't know them, so the list can still say "latest B" for those two designs.
- A revision can now be in SAP without a folder: when the later write failed, or when the
  folder was deleted. That letter stays used, as the manual requires.
- Still English in the Spanish UI: SAP refusal messages and internal errors on a card
  (`result.message`), and the demo notice (9e).
