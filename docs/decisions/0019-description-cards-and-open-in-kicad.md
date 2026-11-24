# 0019: Design description, one live card per request, and opening the result in KiCad

**Status:** accepted (2026-11-20)

## Context

A manual test of the Start panel UI (0018) found four gaps:
- The assistant opened a "Create this design?" card and **Create revision C** stayed
  enabled, so each click added an identical card.
- After a mode switch, earlier cards kept live Confirm, Use this number and Undo buttons
  that could change the new form.
- A disabled Create gave no reason (a new design needs **Get SAP number** first).
- The PDF could be opened, but nothing helped open the KiCad project itself.

The user also asked for a **Design description** field.

## Decision

1. **One live card per request.**
   - Create shows an already waiting card with the same form values instead of opening a copy.
   - A new card of the same kind cancels the older waiting one.
   - A mode switch or New design cancels the waiting cards, marks the earlier ones "from an
     earlier design" without buttons, and adds a divider to the chat.
   - Cancelling has no side effect, so invariant 2 is unchanged.
2. **Create says what is missing**, in the order to do it (fill in a field, get a SAP number,
   pick a design, fix the errors). It stays disabled while the inline check reports errors. A
   new design shows **Next: get SAP number** beside Create.
3. **Description: optional, at most 60 characters, one line.**
   - Rules are in `validate_description` and the manual (`03-title-block#description`).
     Accents and any language are allowed, because the description doesn't go to SAP.
     Control characters are refused, and so is `${`, which KiCad would expand as a text
     variable.
   - Written as the title block's `(comment 1 ...)` and printed by the drawing sheet as
     `${COMMENT1}` in small italics under the title.
   - Kept in the audit details and in the recent designs list.
   - Never locked, and empty when a design is picked from SAP.
   - It is free text, so it is data (invariant 7); a prompt-injection test covers it.
4. **Opening the result.** The preview dialog offers:
   - **Open in KiCad** (`POST /api/designs/{dept}/{num}/{rev}/open`) starts the KiCad GUI
     found next to `KICAD_CLI` with the `.kicad_pro`.
     - It runs only on the user's click and writes an `audit_log` row (`design_opened`).
     - It writes no file and doesn't call SAP. It is not a side effect in the sense of
       invariant 2, so it doesn't go through a confirmation card.
     - It starts a program on the machine that runs the backend, so it is shown only when
       `GET .../files` reports `can_open`: `KICAD_OPEN_ENABLED` is true (false in the Docker
       image) and the GUI binary exists.
   - **Download project (.zip)** (`GET .../project.zip`) works everywhere. Only regular files
     inside the folder are packed; symlinks are skipped.
   - **The full project path with Copy**, and the steps to open it in KiCad 9 by hand.

   All three resolve the folder with `design_folder` inside `DESIGNS_ROOT` (invariant 3).

## Consequences

- New setting `KICAD_OPEN_ENABLED` (in `.env.example`; the Dockerfile sets it to false).
- The e2e suite gains cases for the duplicate card, the mode switch, the disabled-Create hint
  and the description.
