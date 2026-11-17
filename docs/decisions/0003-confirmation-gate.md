# 0003: Confirmation gate for side effects

**Status:** accepted (2026-11-17)

## Context

Two actions have lasting effects: creating a design folder with KiCad files, and
reserving a design number in SAP (a number can't be returned once issued). A language
model can be wrong, can be talked into things by text in a field (prompt injection), and
can claim it did something it didn't. The tool's principle is "the AI guides, the code
decides".

## Decision

- The model never executes a side effect. The gated tools (`request_create_design`,
  `request_reserve_number`) only **record a pending action** and return its id. The UI
  shows a confirmation card with the exact values.
- The side effect happens only in `POST /actions/{id}/confirm`, called by the user's
  click. That endpoint validates the values again with `standards/validators.py`
  before doing anything, so a confirmed action can't skip validation.
- The outcome (created, reserved, failed) goes back to the conversation as a new
  message, so the model reports what actually happened.
- Pending actions expire, and each can be confirmed once.
- Every executed action writes to `audit_log` (invariant 8).

## Consequences

- A tests-only `FakeClient` script that tries to "create 10 designs" ends with ten
  pending cards and zero files. That is the prompt-injection test.
- The UI needs a confirmation card component and the action table in SQLite.
- One extra click for the user. That's intended: it is the moment they check the values.
