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

## Consequences

- One extra thread per model call (pool of 8). Tests with `FakeClient` work as before; the
  event order now has `run` after `conversation`.
- A stuck Groq turn now ends after 120 s with a choice, instead of waiting up to ~5 min.
