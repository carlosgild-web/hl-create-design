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

5. **The start scripts check before launching** (`python -m app.cli llm-check`, run by
   `start.cmd` / `start.sh` in local mode). It starts from the configured provider and walks the
   chain (`groq` or `auto`: groq, ollama, fake; `ollama`: ollama, fake; `fake`: fake), prints why
   anything was skipped, and the script runs the app with the provider that works
   (`LLM_PROVIDER=<name>` for that run only). So even an explicit `LLM_PROVIDER=groq` in `.env`
   starts on Ollama or the demo model when Groq's quota is gone, with a message saying so.
   Docker mode relies on the app's own `auto`.
6. **Both scripts open the browser** once `/api/health` answers (`NO_BROWSER=1` skips it).
7. A Groq daily-quota error now says so, with the reset time and what to do (restart
   `start.cmd`, or `LLM_PROVIDER=auto`); only waits over 15 minutes are called a daily quota.

## Update (2026-11-20): realistic probe, 429 classes, the person chooses

The 4-token probe passed while the first real chat turn failed: a turn sends ~2-3k tokens (system
prompt + tool specs) and makes 2-4 calls, and the free tier allows 8,000 tokens per minute. So:

- **The probe sends a real first turn** (`app.agent.service.probe_turn()`: system prompt, all
  tool specs, a short user message; `max_tokens` 8). The agent builds it and passes it in, so
  `app/llm/` does not import the agent.
- **429s are classified by Groq's text**, not only by the wait: `(TPM)`/`(RPM)` is per-minute,
  `(TPD)`/`(RPD)` is daily, with "used X of Y" and the reset time. Waits like `3h10m5s` are
  parsed (the old pattern read them as 5 s). Without that text, a wait over 2 minutes counts as
  daily. Per-minute limits are waited out and retried up to 65 s; daily ones never are. This
  replaces the 30 s / 15 min thresholds of point 7.
- **Status, not just a pick**: `check_providers()` reports Groq as `ok | per_minute | daily |
  no_key | bad_key | unreachable | error` and Ollama as `ready | no_model | not_running |
  not_installed` ("installed" = on PATH or in `%LOCALAPPDATA%\Programs\Ollama`).
- **`llm-check` asks** (replaces point 5's silent walk): it prints both statuses, suggests Groq
  when usable (`Use Groq? [Y/n]`), else Ollama or the demo (`[O/d]`); if Ollama is installed but
  stopped (and `OLLAMA_BASE_URL` is local) it offers to start `ollama serve` (detached, no
  window) and waits up to 30 s. A missing model prints the `ollama pull` command; the demo is
  used. Enter takes the suggestion; with no terminal the suggestion is taken silently and
  nothing is started. Questions go to stderr; the choice goes to stdout and `--out FILE`
  (`start.cmd` reads the file, because a `for /f` capture cannot read the keyboard).
- The app's own `auto` (Docker) uses the same status without asking.

## Consequences

- The code default changed from `fake` to `auto`. A fresh clone with no key and no Ollama still
  ends up on the scripted model, so "needs no external service" still holds.
- A probe sends one first-turn-sized request (~2-3k tokens) to Groq on every start when a key
  is configured, about 1% of the free daily quota.
- The UI does not show the resolved provider yet (only `/api/health` does).
