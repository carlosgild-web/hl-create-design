# 0018: Start panel (new design or new revision of an existing one) and preview dialog

**Status:** accepted (2026-11-20)

## Context

The form mixed two jobs:
- **starting a new design**, where SAP issues the number;
- **adding a revision to a design that SAP already knows**.

Nothing told the user which job they were doing, and they could type a number by hand. The
preview sat in a 256 px tab below the fold at 1440x900, so users did not see it.

## Decision

1. **A Start panel picks the job**: "New design" or "From existing design". The mode lives in
   the form state, so the form, the stepper, the assistant context and the cards all read the
   same value.
2. **New design: the number only comes from SAP (Q4 a).**
   - The Design number field is read-only and filled only by "Get SAP number", which opens the
     existing `reserve_number` confirmation card. The gate is unchanged.
   - The revision is A.
   - The `HL-<DEPT>-<YY>-` prefix pre-fill from 0017 block F is not used in this mode.
3. **From existing design: SAP decides the identity.**
   - The user picks from the SAP list (`GET /api/sap/designs`, read-only, through `SapClient`).
   - Department, number and name are read-only (**Q1 a**). A different name is an error:
     `name_differs_from_sap`, ref `03-title-block#name-from-sap`.
   - The revision is read-only, always the next free one (**Q2 a**). It is computed with the
     same rule as validation (SAP revisions plus the folders on disk), and a test asserts the
     list and `/api/validate` agree.
   - Only the designer is typed.
4. **BLOCKED and OBSOLETE designs are listed but disabled (Q3 a)**, with SAP's reason.
   - OBSOLETE rows offer "Use successor".
   - Confirm still refuses them even if the UI is bypassed: the validators decide.
5. **A new revision exists on disk and in `audit_log` only.** The mock SAP has no revision
   write, and the title block takes SAP's name, material and WBS.
6. **The preview is a dialog** (Radix Dialog from the installed `radix-ui`).
   - It opens on a confirmed create, on "Show preview" and on a recent design.
   - It has fit/100%, a title-block zoom, Open and Download PDF, and Close/Esc.
   - It is full screen on phones.
7. **Layout:**
   - 3 columns at ≥1280 px: Assistant | Start | Form. One screen, each column scrolls inside.
   - Assistant | (Start above Form) between 1024 and 1279 px.
   - Tabs "Design | Assistant | Recent" on phones.
8. **The assistant knows the mode** (the form context carries `mode`). In existing mode it
   does not propose department, number or name. When it proposes a number that SAP lists, the
   UI switches to existing mode and selects that row, with a visible note.

## Consequences

- One more read-only endpoint and one more SAP call (the list, cached by the UI).
- Typing a design number by hand is gone. Existing designs are picked; new ones are reserved.
