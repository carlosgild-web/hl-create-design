# 0002: Provider-agnostic LLM layer (Ollama, Anthropic, Fake)

**Status:** accepted (2026-11-17)

## Context

The assistant has to run locally on Carlos's machine (Ollama, no cost, no data leaving
the PC), in a public cloud demo where no Ollama is available, and in CI where no model is
available at all. The previous project (`luna-hybrid-agent`) used only Ollama.

## Decision

One interface, `LLMClient`, with three implementations under `backend/app/llm/`:

| Provider | Use | Tool calling |
|---|---|---|
| `OllamaClient` | Local runs; default model `qwen3:4b-instruct-2507` | Native `tools` in `/api/chat` |
| `AnthropicClient` | Cloud demo; model from `ANTHROPIC_MODEL` | Messages API tool use |
| `FakeClient` | Tests, CI, demo mode without a key | Scripted replies and tool calls |

`LLM_PROVIDER` (`fake` | `ollama` | `anthropic`) selects one at startup; `fake` is the
default so a fresh clone runs with nothing installed. Provider SDKs are imported only
under `backend/app/llm/` (invariant 5). The agent loop sees a neutral message and
tool-call shape, and each client translates to and from its provider.

There is no agent framework (same reasoning as luna decision 0032): the loop is small
and is a part a reviewer wants to read.

## Consequences

- The same scripted conversations test the agent without a network.
- The evaluation suite (Phase 6) can compare a small local model with a cloud model
  on the same scenarios.
- Each provider's quirks (for example a small model writing tool calls as text) are
  handled inside its client, not in the loop.
