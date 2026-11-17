# 0011: Agent eval harness and demo safety (Phase 6)

**Status:** accepted (2026-11-17)

## Context

PLAN Phase 6 asks for a ~25-scenario suite scored on tool calls, unconfirmed side effects
and citations, plus rate limit, daily token cap and a `DESIGNS_ROOT` cleanup for the cloud
demo. Two things differ from the plan: the Anthropic provider does not exist yet
(decision 0009), and the suite needs a SAP and a kicad-cli outside the test folder.

## Decision

1. **The eval plays the real stack.** Agent loop, tools, validators, actions, SQLite and
   `SapClient` are real. Only the edges are fakes: the in-memory SAP gateway, a kicad-cli
   stub and the model. `FakeSap` and `FakeKicadCli` moved from `tests/` to `app/evals/`
   (tests import them from there) so the eval and the tests share one copy.
2. **Checks are objective.** Every scenario scores invariants (no side effect without a
   click, writes confined, run bounded, one card per kind per turn) plus its own
   expectations (tools, validator codes, cards, audit rows, folders, form fields). A
   citation only counts if it is a manual reference a tool returned, so an invented one
   fails. The model's wording is never graded.
3. **Scripts are for `--fake` only.** Scenarios tagged `fake-only` script a misbehaving
   model (obeys an injection, calls an unknown tool, never stops) to probe the guards; real
   providers skip them. Meta-tests prove the harness fails when it should (a leaky tool, a
   wrong expectation, an invented citation, an unused script).
4. **Real runs publish failures.** `agent-eval --provider X --allow-failures` writes
   `docs/eval/*.md|json`. CI runs only `--fake` and requires 100%.
5. **Anthropic results wait for Phase 7**, when `AnthropicClient` exists. The same command
   will produce them.
6. **Demo safety is off by default** (`RATE_LIMIT_PER_MIN`, `DAILY_TOKEN_CAP`,
   `DESIGNS_TTL_HOURS` = 0) and in-process: a sliding-window limiter per IP on the
   state-changing endpoints (chat, card open/confirm/cancel), a `token_usage` table that
   pauses the assistant at the cap (the form and cards keep working), and an hourly cleanup
   that removes old revision folders through `resolve_inside`, never follows symlinks and
   audits each removal. `X-Forwarded-For` is trusted only with `TRUST_FORWARDED_FOR=true`
   (last entry, the one the proxy added).

## Consequences

- One worker process only: limiter state is in memory (fine for the single-container demo).
- Token counts come from the provider; Fake and providers that report none count 0.
- The Windows symlink test of the cleanup is skipped without privileges; CI (Linux) runs it.
