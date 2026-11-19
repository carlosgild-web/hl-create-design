# 0012: Groq as the cloud provider (replaces Anthropic)

**Status:** accepted (2026-11-19)

## Context

PLAN and decision 0009 named Anthropic Claude as the cloud provider for the online demo
and the second real eval run. The owner chose Groq instead and already has a key
(`gsk_...`) with the model `openai/gpt-oss-120b`. Note: Groq (groq.com, inference hosting)
is not xAI's Grok.

## Decision

1. **`GroqClient`** in `backend/app/llm/groq.py`, selected by `LLM_PROVIDER=groq`.
   Groq's API is OpenAI-compatible (`/chat/completions`, native `tools`), so it is plain
   `httpx` like `OllamaClient`: no vendor SDK and no new dependency. Invariant 5 holds.
2. **Config:** `GROQ_API_KEY`, `GROQ_MODEL` (default `openai/gpt-oss-120b`) and
   `GROQ_BASE_URL` replace the `ANTHROPIC_*` settings. `anthropic` is no longer a valid
   `LLM_PROVIDER`; the Stack table in CLAUDE.md and PLAN.md are updated.
3. **Errors say what to do:** missing key, 401/403, unknown model and 429 (with
   `Retry-After` when sent) become `LLMError`, which the chat stream reports as an
   `error` event and the eval reports without a stack trace.
4. **Tests never need the key:** the client is tested over `httpx.MockTransport`; CI keeps
   using `FakeClient`.
5. The eval for this provider is published in `docs/eval/` once the free-tier daily quota
   allows a full run (it was exhausted on 2026-11-19).

## Consequences

- The interface (`LLMClient`) did not change, so adding or swapping a provider stays a
  one-file change.
- Free-tier rate limits apply (the daily quota was hit on 2026-11-19), so real eval runs may need
  `--only` batches or another day. There is no hosted demo (decision 0013).
- `gpt-oss` is a reasoning model; if it returns reasoning text outside `content`, it is
  ignored, as with Ollama's `<think>` blocks.
