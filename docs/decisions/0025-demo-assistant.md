# 0025: A rule-based demo assistant (`LLM_PROVIDER=demo`)

**Status:** accepted (2026-11-21)

## Context

Phase 9 block 9e (`PLAN-phase-9-review-and-faq.md`, finding 1).
- Without a model the assistant only answered a fixed English notice, even to the app's own
  **Try an example** button.
- The README promised a "scripted demo mode", and the GIF shows the assistant filling the
  form.
- Q5: add a `demo` provider, and keep `fake` (the scripted `FakeClient`) for tests only.

## Decision

1. **`DemoClient`** (`llm/demo.py`, provider `demo`, model `rules`). It goes through the same
   loop and tools as a model, and decides from what the current turn holds:
   - a card was opened → "review it and click Confirm";
   - `validate_design_request` answered → explain its errors with their refs, or open the
     create or reservation card when the values are complete, or name what is missing;
   - SAP lookups and the department list answered → summarize them;
   - a manual search answered (the backend's pre-retrieval, decision 0024, or its own for a
     message ending in `?`) → the top passage's first sentences and its `[source]`;
   - otherwise it takes the values a sentence names and calls `propose_form_values` +
     `validate_design_request`; or it explains what the demo can do, without config names.

   Every answer starts with "(Demo assistant)" / "(Asistente de demostración)", in the UI
   language, which it reads from the system prompt.
2. **The tools decide, not the demo** (invariant 1).
   - Extraction is deliberately loose: `HL-HW-0042` reaches the validator, which explains
     it.
   - A department code inside a design number doesn't override the department the user
     named, so "HL-HW-… for Power Electronics" gives the mismatch error, not a quiet fix.
   - A card opens only after the validator said ok; confirming stays a click (invariant 2).
3. **The `llm` package doesn't import the agent.** The demo doesn't use the question
   detector; it relies on the backend's search result, or on a trailing `?`.
4. **Wiring.**
   - `LLM_PROVIDER=demo`; `auto`, the Groq-quota fallback and `llm-check` end in `demo`.
   - The UI's switch target is `demo`.
   - `agent-eval --provider demo` runs the suite on it.
   - `fake` still selects `FakeClient`, whose notice now points to `demo`.
5. **UI.** The header shows "Assistant: demo (no AI)" / "Asistente: demostración (sin IA)"
   when `/api/health` says `demo`, and refreshes after a switch.
6. **Measured.**
   - FAQ bank: 103/108 answers (95 %) cite an accepted ref (`test_demo.py` keeps ≥ 90 %).
   - Eval suite on the demo: 31/33. The multi-turn wizard needs memory of earlier turns,
     and the path-traversal scenario expects the folder-check tool. The demo validates
     instead and creates nothing. Both are accepted as demo limits.

## Consequences

- README, `.env.example`, `08#demo-mode` and the Q&A describe what the demo really does.
  The GIF was recorded with the scripted test model and stays as it is.
- A `.env` that still says `LLM_PROVIDER=fake` gets the test double's notice; use `demo`.
