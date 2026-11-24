# 0029: Dahl as the first cloud provider

**Status:** accepted (2026-11-22)

## Context

The real-model runs left from Phase 9 waited on Groq. The free tier's daily token quota ran
out on 2026-11-21, and a 49-scenario eval does not fit in one day of it. The user has
credit on Dahl inference (`inference.dahl.global`), an OpenAI-compatible API that resells
GPU capacity. They asked to use it for the missing runs and to have start-up check it
before Groq.

On 2026-11-22 we checked the three models the key lists with one real first turn each:
the system prompt, the tool specs and "Why was revision I rejected?".

| Model | Result |
|---|---|
| `zai-org/GLM-5.3-Flash` | native `tool_calls` → `search_design_manual`, 5.3 s, 2,095 + 107 tokens |
| `deepseek-ai/DeepSeek-V4-Flash-0731` | 503 "all hosts are at capacity" |
| `MiniMaxAI/MiniMax-M2.7` | 429 "at concurrency capacity; paid accounts are admitted first" |

## Decision

1. **Same client, another name.** `DahlClient` subclasses `GroqClient` (decision 0012). Both
   speak plain-httpx `/chat/completions` with native `tools`. The provider-specific parts
   are class attributes:
   - `provider`;
   - `label`, used in error texts;
   - `key_env`;
   - `model_env`.

   The probe, the waits on per-minute 429s and the tool-call parsing are shared. No SDK,
   and nothing outside `backend/app/llm/` changes (invariant 5).
2. **Settings.** `DAHL_API_KEY`, `DAHL_MODEL` (default `zai-org/GLM-5.3-Flash`, the one
   model that answered with a tool call) and `DAHL_BASE_URL`, plus `LLM_PROVIDER=dahl`.
3. **Order.** `auto` and `dahl` try Dahl, then Groq, then Ollama, then the demo.
   `LLM_PROVIDER=groq` still starts at Groq. `llm-check` (run by `start.cmd` and `start.sh`)
   shows a Dahl line first and asks "Use Dahl?" before "Use Groq?".
4. **No credit counts as quota.** HTTP 402 raises `QuotaExhausted`, like Groq's daily 429.
   The probe reports `no_credit`, which is not usable. A 429 with a short `Retry-After`
   (a model at capacity) is waited out and retried, like Groq's per-minute limit.
5. **Mid-session fallback in chain order.** When Dahl's quota or credit runs out, the
   `SwitchingClient` moves the session to Groq if Groq's probe says it can serve, else to
   Ollama, else to the demo. After Groq it is Ollama, else the demo, never back to a cloud
   provider. The chat notice names the provider that ran out (`{from}`) and has a third
   text for a move to Groq.

## Consequences

- The Phase 9 real-model runs (9f eval, and 9d's tokens per FAQ turn with pre-retrieval off
  vs on) run on Dahl. Groq stays the second choice.
- Tests and CI need no key. The new tests use mocked httpx transports: Dahl first in the
  chain, 402 → Groq, the probe states, the question order, and the fallback chain.
- Dahl publishes no official docs that we found, and model availability changes with its
  capacity. `DAHL_MODEL` is a setting for that reason.
