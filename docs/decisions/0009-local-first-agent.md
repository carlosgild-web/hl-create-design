# 0009: Local-first assistant; the cloud provider moves to Phase 7

**Status:** accepted (2026-11-17)

## Context

Decision 0002 planned three providers for Phase 4. The assistant can run entirely on the
user's PC with Ollama (`qwen3:4b-instruct-2507-q4_K_M` is installed), which needs no key,
no cost and sends nothing out. A cloud model is only needed for the public demo, where no
Ollama is available (Phase 7).

## Decision

1. Phase 4 builds `OllamaClient` and `FakeClient`. `AnthropicClient` is built in Phase 7;
   until then `LLM_PROVIDER=anthropic` fails with a clear message. PLAN's "Done when"
   asks for a manual run on Ollama only.
2. The default Ollama tag is `qwen3:4b-instruct-2507-q4_K_M`, the one that is installed.
3. Phase 4 also builds what the tools need: `SapClient`, the FTS5 manual search, the chat
   and action endpoints, and `chat`/`confirm`/`cancel` CLI commands.
4. Pending actions: `pending -> executing -> confirmed | failed`, or `pending ->
   cancelled`. They expire after 30 minutes, run at most once, and are validated again
   with fresh SAP data at confirmation. A run opens at most one card per kind.
5. Chat events (SSE): `conversation`, `thinking`, `tool_call`, `tool_result`,
   `form_proposal`, `pending_action`, `message`, `error`, `done`.

## Consequences

- Tests and CI are unchanged (Fake only). A small model's quirks stay inside `OllamaClient`.
- Phase 7 adds `AnthropicClient` behind the same interface, without touching the loop.
