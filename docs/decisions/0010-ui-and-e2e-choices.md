# 0010: UI and browser-test choices (Phase 5)

Date: 2026-11-17. Status: accepted.

## Context

Phase 5 builds the React UI on the Phase 4 API. A few things the plan did not list were
needed, and a few were left open.

## Decision

- **Four small backend endpoints** (`api/designs.py`): `GET /api/departments`,
  `GET /api/designs` (recent, from `audit_log`; there is no `design_requests` table),
  `GET /api/designs/{dept}/{number}/{rev}/preview.{pdf,svg}` (confined with
  `design_folder`), and `POST /api/actions`.
- **The form does not create anything.** `POST /api/actions` only opens a pending action,
  exactly like the model's `request_*` tools. The user then clicks Confirm on the card, so
  invariant 2 has one path, not two.
- **Wizard vs. free chat** is a UI choice, not a backend mode: "Guide me step by step"
  sends a starter message and the system prompt already asks one question at a time.
- **i18n is hand-rolled** (`src/i18n`, about 60 lines, typed keys, ES/EN) instead of
  `react-i18next`: two languages and about 90 strings don't need the dependency.
- **Chat over `fetch`**, not `EventSource` (which can't POST); `api/sse.ts` parses the stream.
- **Tests without `user-event`**: Testing Library's `fireEvent` is enough, so no extra dependency.
- **Browser tests live in `e2e/`** with their own `package.json` (as in PLAN section 5).
  `e2e/harness.py` runs the real backend with a scripted `FakeClient` and a stub
  `kicad-cli`, next to the real mock SAP and the Vite dev server, on ports 8190, 8191 and
  5190 so a running dev stack is never reused. Locally set `E2E_BROWSER_CHANNEL=msedge`
  (or `chrome`) to use the installed browser; CI installs Chromium.

## Consequences

- The e2e proves the gate end to end: before the click the preview answers 404, after it 200.
- The PDF/SVG preview shows the first SVG sheet only (the template has one sheet).
- No login yet: the designer is a form field (PLAN section 8, question 4).
