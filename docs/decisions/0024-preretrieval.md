# 0024: The backend searches the manual itself for questions (pre-retrieval)

**Status:** accepted (2026-11-21); Groq measurements pending (daily quota, see below)

## Context

Phase 9 block 9d (`PLAN-phase-9-review-and-faq.md`, section 1 layer 3). `qwen3:4b`'s known
failure is skipping the manual search, or writing the call as text (docs/eval). Since 9a,
the FAQ lives in the manual (decision 0021), so a search before the first model call
grounds every provider in the same passages. Q6: pre-retrieval runs for Groq too, not only
Ollama; it also saves Groq a round trip under its rate limit.

## Decision

1. **Question detector** `agent/intent.py`, a pure function (`classify`).
   - A message is a `rule_question` when it ends with `?`, starts with `¿`, starts with a
     question word, has a question word in its first three words or as its last word, or
     contains a problem word ("didn't work", "bloqueado", "no hay", "caducó"…).
   - A leading command ("Create …", "Crea …") is a form fill, unless it reports a problem.
   - A leading reply ("No, …", "Ya, …", "Not that one…") doesn't count as a problem.
   - A message that names a design number **and** a revision is never a question: the
     model validates it.
   - Measured: recall 321/324 (99 %) on the FAQ bank's questions and paraphrases, and none
     of the eval scenarios' form-fill sentences flagged. `test_intent.py` keeps ≥ 95 % and
     zero.
2. **Pre-retrieval in the loop.** For a question, `chat_turn` passes `search_design_manual`
   arguments (the message, the UI language) to `run_agent`. The loop runs the call through
   the normal registry before the first model call. It adds an assistant message with the
   call (id `auto_<run id>`) and the tool result, exactly as if the model had made them.
   - It's traced with `"auto": true` at iteration 0, and the events carry `auto`. Agent
     steps marks it "searched by Create Design before the model".
   - It isn't a model call, so it doesn't count against `AGENT_MAX_ITERATIONS`.
   - It's a read tool: it never opens a card (invariant 2).
3. **Config:** `AGENT_PRERETRIEVAL=auto|on|off` (default `auto` = questions only; `on` =
   every message, for comparisons). `agent-eval --preretrieval auto|on|off` runs the same
   comparison. The test suite's shared settings use `off`, so the mechanics tests keep
   scripting every call; pre-retrieval has its own tests.
4. **Prompt:** one line. When a search result is already in the conversation, the model
   answers from it in 1–3 sentences, cites its `source`, and searches again only if it
   doesn't answer. The Ollama few-shot example is **not** added: the plan wants it only if
   an Ollama A/B shows it helps (9f).
5. **Ollama:** 3 passages of at most 500 characters (`ToolContext.search_limit`,
   `passage_chars`), so the prompt stays short on CPU. `temperature: 0` and
   `num_ctx: 8192` were already set. The prompt, the tool specs and 3 passages need about
   3,500 tokens.
6. **Citations:** `normalize_refs` (NFKC, every Unicode dash as `-`, no spaces inside the
   brackets) runs before the eval's citation check. That fixes the known Groq false
   negative (`[02‑revisions#…]` with U+2011). The chat doesn't render references as links
   yet; when it does (9f), it uses the same rule. The rule "cite only ids a tool returned"
   is unchanged; the backend's search counts as a tool.
7. **Two fake scenarios** (`preretrieval-answers-a-question`, `preretrieval-es`): the
   scripted model never searches, yet the answer cites a reference the backend's search
   returned, and no card opens. With `--preretrieval off` exactly these two fail, which
   shows that the citation comes from the automatic search.

## Pending (Groq's daily quota was almost used up on 2026-11-21)

- Measure Groq tokens per FAQ turn with `AGENT_PRERETRIEVAL=off` vs `auto`, against
  `DAILY_TOKEN_CAP`. To do after the daily reset, before the 9f Groq eval run.
- Real-model runs (Ollama with pre-retrieval off, then on; Groq) are part of 9f.

## Consequences

- A question costs one more tool message in the prompt even when the model would have
  searched anyway; the model usually saves a model call in return.
- A false positive only adds a passage list to the prompt; it decides nothing.
