# 0031: Dahl moves to another model when one is busy

**Status:** accepted (2026-11-24). Amends 0029.

## Context

Decision 0029 runs the app on Dahl with one model, `zai-org/GLM-5.3-Flash`. On 2026-11-24
two takes of the short video failed on Dahl's side. GLM answered HTTP 429 ("This model is
at concurrency capacity. Paid accounts are admitted first.") again and again, and then a
call timed out. The error named the models that were free at that moment:
`deepseek-ai/DeepSeek-V4-Flash-0731` and `MiniMaxAI/MiniMax-M2.7`. The client only waited
out each Retry-After on GLM, so the turn failed even though Dahl could have served it.

## Decision

1. `DAHL_FALLBACK_MODELS` (comma-separated; default
   `deepseek-ai/DeepSeek-V4-Flash-0731,MiniMaxAI/MiniMax-M2.7`; empty turns it off) lists
   the models to try after `DAHL_MODEL`, in order.
2. **At startup** (`LLM_PROVIDER=auto`, and `start.cmd`'s check) the Dahl probe tries the
   models in order. The session starts on the first one that answers. A rejected key and
   a used-up credit stop the probe, because no other model would help.
3. **Mid-session**, a 429 or a timeout moves the call to the next model at once, with no
   wait. The client stays on the model that answered. When every model is busy, it waits
   out the Retry-After on the last one, as before. A used-up credit (402) still moves the
   session to Groq, Ollama or the demo (0029).
4. The switch is told once, as a `notice` with code `model_switched` (from, to, reason).
   The UI shows it in the chat. The trace records it as a step, and the run's `model`
   (trace and `agent_runs`) is the model that answered. `/api/health` reports
   `llm_model` for the cloud providers.
5. The short video's storyboard lists the models it may show. Its banner names the model
   in use and changes if the model changes.

## Consequences

- The Phase 9 eval numbers are for GLM-5.3 Flash (decision 0029). A session or a video on a
  fallback model is not covered by them, and the banner and trace say which model it was.
- When it was checked on 2026-11-22, GLM was the one model that answered a real turn with a
  native tool call. The fallbacks may handle tools less well. The validators and the
  confirmation gate still decide, so a weaker model costs quality, not safety.
