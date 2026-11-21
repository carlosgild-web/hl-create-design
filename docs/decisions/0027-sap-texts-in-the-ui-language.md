# 0027: SAP texts and card failures in the UI language

**Status:** accepted (2026-11-21)

## Context

After decision 0022, rule messages render in the UI language, but a failed card still
showed English in the Spanish UI. Two parts were English: our own wording ("SAP refused…",
"SAP is not available…", "… already exists. Nothing was overwritten.") and SAP's own
error text from the mock (`Design HL-HW-24-0015 is BLOCKED; no new revision allowed`).
The Start panel's "SAP down" message had the same problem.

## Decision

1. **SAP answers in the logon language, as SAP Gateway does.** The mock reads
   `sap-language` (URL parameter, then header; `ES`/`EN` or `S`/`E`), then
   `Accept-Language`, else English. Its error texts live in one catalog,
   `sap-mock/app/messages.py` (EN and ES, same parameters, checked by a test). Errors keep
   their code and parameters until the response is built. `message.lang` says which
   language came back. Technical request errors (`ZHL_GW/005`, `ZHL_GW/006`) stay English.
2. **The backend asks in the UI language.** `SapClient.use_language()` sets the header.
   `POST /api/actions/{id}/confirm?lang=`, `GET /api/sap/designs?lang=` and the chat
   (its `language`) use it. Default `en`, so older callers are unchanged. A real SAP behind
   `SapClient` would get the same header (invariant 4).
3. **Our wording is translated in the UI, as in 0022.** Card failures carry `params`
   (`sap_code`, `detail`, `folder`) next to the English `message`; the UI renders
   `failure.<error_kind>` (and `sap.<code>` for the Start panel) with them, and falls back
   to `message` when there is no template. The model still reads the English `message` in
   the event; its own reply follows the user's language.
4. `DesignFolderExistsError` carries its `folder`, so the conflict text is built in the UI.

## Consequences

- A Spanish user reads a SAP refusal fully in Spanish, for example
  "SAP lo rechazó: El diseño HL-HW-24-0015 está en BLOCKED; no se permiten revisiones
  nuevas (ZHL_PLM/020)". Status names stay as SAP writes them (`BLOCKED`), like on the
  status badges.
- Adding a SAP error means adding both texts to the catalog; the parity test fails otherwise.
- The browser tests and the frontend mocks now see `?lang=en` on these URLs.
