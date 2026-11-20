# 0016: `LLM_PROVIDER=auto` (provider fallback at startup)

**Status:** accepted (2026-11-20)

## Context

The app can run on Groq, on a local Ollama, or on the scripted demo model. Which one works
depends on the machine and the day: the Groq free tier has a daily token quota (it ran out on
2026-11-19), and Ollama may not be installed or running. A person who clones the project should
get a working assistant without editing `.env`, and should be told which one they got.

## Decision

1. **`auto` is the default.** At startup (FastAPI lifespan) it tries, in order:
   **Groq**: a key is set and one tiny request (4 tokens, 8 s timeout) succeeds. A daily-quota 429
   (long `Retry-After`) means "not available"; a short per-minute 429 still counts as usable,
   because `GroqClient` waits and retries (decision 0012).
   **Ollama**: reachable (3 s timeout) and the configured model is pulled.
   **Fake**: the scripted demo model, so the app always starts.
2. **Resolved once per process and cached** (the probes cost a request). The result is logged,
   and `/api/health` reports `llm_provider` (what is actually used) and `llm_note` (what was
   skipped and why). If Groq's quota runs out mid-session, the existing clear error is shown;
   restart to re-resolve.
3. **Explicit values stay explicit**: `groq`, `ollama` and `fake` never fall back, which is what
   the eval runs and the tests need. Tests keep passing `fake` and use mock transports.
4. The probes live on the clients (`probe()`), the order in `app/llm/resolve.py`; provider
   details stay under `backend/app/llm/` (invariant 5). It does not start Ollama for you.

## Consequences

- The code default changed from `fake` to `auto`. A fresh clone with no key and no Ollama still
  ends up on the scripted model, so "needs no external service" still holds.
- A probe sends a few tokens to Groq on every app start when a key is configured.
- The UI does not show the resolved provider yet (only `/api/health` does).
