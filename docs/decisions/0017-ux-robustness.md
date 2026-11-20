# 0017: UX and robustness pass (after the first real manual test)

**Status:** accepted (2026-11-20). Block A is done; blocks B–E are added below as they land.

## Context

A manual test with start.cmd on Groq (gpt-oss-120b) showed later turns staying on "Thinking…"
for 3–6 minutes. `GroqClient` waits out per-minute 429s inside `chat()` (up to 4 × 65 s), and
the agent loop could not yield anything until `chat()` returned, so the UI had nothing to show
and Stop could not reach the backend. The console logged nothing about the model either.

## Decision (block A: the assistant never stalls silently)

1. **Each model call runs in a worker thread** (`agent/loop.py`, `_model_call`). The loop polls
   every 0.2 s, so it can:
   - pass on what the client reports through a thread-local per-call context
     (`llm/base.py`: `call_with`, `report`, `wait`). Groq reports
     `rate_limited {wait_s, scope, provider}` before each wait, and the loop turns that into a
     `status` SSE event. The context is thread-local because one client is shared by all
     requests (decision 0016);
   - **cancel**: `POST /api/runs/{id}/cancel` sets a per-run flag (`agent/runs.py`, in
     memory). The run ends as `cancelled`, and no tool runs after Stop, so no card opens;
   - **cap the whole turn** with `AGENT_TURN_TIMEOUT_S` (default 120 s). The run ends as
     `timeout` with an `error` event `turn_timeout` that lists `can_switch_to` (Ollama only if
     it is ready, and the demo model; never the provider in use).

   When the loop stops waiting, it also sets the call's stop flag, so a rate-limit wait ends at
   once (`CallInterrupted`). An HTTP request already in flight finishes in the background and
   its result is dropped.
2. **The user can switch provider**: `POST /api/llm/switch {to: ollama|fake}` sets a
   per-process override in `llm/factory.py`, and `/api/health` reports it. It touches no files
   and no SAP, so it is a plain endpoint, not a gated action (invariant 2 covers files and SAP
   numbers).
3. **New run statuses**: `cancelled` and `timeout`, next to `answered | limit | error`.
   `chat_turn` sends an early `run {id}` event so the UI can stop the run.
4. **Logging**: every Groq and Ollama call logs one line on the `app.llm` logger (model, HTTP
   status, latency, tokens; a 429 with its scope and wait). `main.py` gives the `app` logger
   a console handler at INFO, so the lines show next to uvicorn's.
5. **UI**: the "Thinking…" line shows the current tool ("Searching the Design Manual…",
   "Checking SAP…") or the rate-limit wait. Stop calls the cancel endpoint and the chat says
   "Stopped" (the stream is dropped after 3 s if `done` does not come). The timeout message
   has "Switch to Ollama" / "Use the demo model" buttons, and there is a "New conversation"
   button.
6. **"Try an example" fills the department**: the prompt now says that any value named in the
   message (a department by name in English or Spanish too) goes to `propose_form_values`
   first, and the department list carries both names (`validators.DEPARTMENTS_ES`, as in SAP).
   New eval scenarios `example-button-fill-en/-es` use the exact button texts.

## Decision (block B: the form says what it knows)

7. **One read-only check for the form and the assistant**: `app.designs.check_fields`
   (moved out of the `validate_design_request` tool) backs both the tool and the new
   `POST /api/validate`. Same input, same result, which a test asserts. It writes nothing and
   reaches SAP only through `SapClient` (invariants 1 and 4).
8. **Inline validation**: the form sends the filled fields 400 ms after the last keystroke
   and shows errors and warnings under each field with their manual reference. Revision `I`
   now shows `rev_skipped_letter` at once and stays `I`: no code ever replaced it. The "A"
   seen in the manual test was the assistant re-proposing a value (see 9).
9. **Where a value came from**: each field is marked `ai` (amber, "Suggested by the
   assistant"), `sap` (sea, "From SAP") or nothing (the user's own value).
   - An assistant proposal fills empty fields, or fields it filled itself, and only marks
     values it changes.
   - It never overwrites a value the user typed or SAP gave. The proposal shows as "The
     assistant suggests: X [Use it]".
10. **Stored values are visible before confirming**:
    - The form shows "Will be saved as: Bead Sorter Vision Board".
    - `POST /api/actions` stores card payloads normalized (`normalize_payload`: title case,
      capitals), so the card shows what will be written. The rules are still checked at
      confirm.
11. **Flow**:
    - A confirmed reservation fills the number and revision A (marked as SAP values), and
      the card offers Undo.
    - After creating, the form shows "Created ✓" and a "New design" button, and Create is
      disabled while the values match the created revision.
    - Confirm and Cancel show a spinner.
    - The preview scrolls into view, and the selected recent design is highlighted.
12. Pulled forward from blocks C and D because they were in the same files:
    - Translated card labels, with the department name in the UI language. `/api/departments`
      now returns `name_es`.
    - A `success` color token, a green distinct from sea, which marks SAP values.

## Decision (block C: i18n and accessibility)

13. **`<html lang>` follows the language** (an effect in `i18n/provider.tsx`), so screen
    readers and hyphenation use the right one.
14. **Plurals** come from a small `Intl.PluralRules` helper (`tn(base, count)` with
    `<base>.one` and `<base>.other` keys), so the text reads "1 llamada al modelo", not
    "1 llamadas". There is no i18n library.
15. **Steps drawer**:
    - A run that answered without tools says so, instead of "No steps yet".
    - Run statuses are translated, including `cancelled` and `timeout`.
    - The sheet's ✕ has a translated label (`closeLabel` on `SheetContent`).
16. **Demo guide panel**: the header leaves room for the ✕ (`pr-12`), so it no longer
    covers the title.
17. **The "unlabeled button" next to Recent designs** could not be reproduced. A Playwright
    probe found no button without an accessible name at 1440 or 375 px, with the guide open
    or as a pill. The floating demo-guide pill (bottom left) did overlap that card, so the
    page now has bottom padding to keep content clear of it.

## Decision (block D: layout and visual design)

18. **Luna's palette is kept** (the user's choice); the stricter color meanings are in the
    addendum to decision 0014.
19. **Desktop (`lg` and up)**:
    - Left column: the form with a progress stepper (Department → Number → Revision →
      Details → Confirm). It is worked out from the fields and the validators' errors, shows
      progress only and never blocks editing.
    - Under the form: tabs "Preview | Recent designs". Creating, Show preview and picking a
      recent design switch to Preview.
    - Right column: the assistant, sticky at viewport height, so its input is always in view.
20. **Phones (below `lg`)**:
    - Tabs "Form | Assistant | Preview". Sending a message opens Assistant, a new preview
      opens Preview, and the Assistant tab shows a badge while a card waits.
    - The form and the chat stay mounted, so a draft or a running answer survives a tab
      switch.
    - The demo banner is one line: no tag, the text cut to one line, and the button as an
      icon with an accessible name.
21. Tabs come from Radix (the `radix-ui` package already in use; no new dependency). The
    layout is chosen with `matchMedia` (`useMediaQuery`); without it (unit tests) the
    desktop layout is used.

## Consequences

- One extra thread per model call (pool of 8). Tests with `FakeClient` work as before; the
  event order now has `run` after `conversation`.
- A stuck Groq turn now ends after 120 s with a choice, instead of waiting up to ~5 min.
