# 0026: FAQ evals, clickable manual references, and the last polish of Phase 9

**Status:** accepted (2026-11-21); the Ollama A/B is done (items 7-8), the Groq run is pending

## Context

Phase 9 block 9f (`PLAN-phase-9-review-and-faq.md`, findings 16–17 and the eval plan).

## Decision

1. **FAQ scenarios.** Eight topics, each in EN and ES (16 scenarios, tag `faq`): own number,
   revision I, RELEASED, Spanish name, designer, template circuit, where the files are,
   card expired. They're generated from `faq_questions.json`. Each one expects:
   - a manual search (the model's or the backend's pre-retrieval);
   - a citation of one of the question's accepted anchors (new `Expect.cite_any`);
   - no card;
   - the answer in the user's language (new `Expect.language`, a word-count heuristic in
     `answer_language`).
2. **Reports** in `docs/eval/`: scripted 52/52, demo 47/49. CI also runs the demo,
   informational because of its two known limits (decision 0025).
3. **Few-shot switch.** `AGENT_FEW_SHOT` (default off) adds one short example answer to the
   prompt, and only for Ollama. `agent-eval --few-shot` runs the A/B. It stays off unless
   the Ollama run shows that it helps.
4. **Manual references open the passage.**
   - `GET /api/manual/{lang}/{document}/{anchor}` (`api/manual.py`) is read-only and serves
     only indexed passages: the path parts are an index key, never a file path, so `..`
     gives a 404.
   - In the chat, on the form, on cards and on the SAP card, `[ref]` is a button that
     opens the passage in a dialog, in the UI language. The button's accessible name is
     its visible `[ref]` text; the hint is a tooltip. An `aria-label` such as "Open manual
     section 03-title-block#designer" would also match the label "Designer", so the e2e
     run caught it.
   - The chat uses `normalizeRefs` (the same rule as the backend's `normalize_refs`), so a
     Groq citation with U+2011 dashes still links.
5. **"Fill in first" hint (finding 16).** It lists only the missing fields, in the form's
   order: Department · Designer · Design name. The form's "To create:" blockers use the same
   order.
   - The mode radios already had accessible names (`aria-labelledby`, Phase 8), so nothing
     changed there.
6. **`start.sh`** got the port check of `start.cmd`. It finds the owner with `lsof`, or `ss`
   on Linux, and asks before stopping it. Without a terminal it never stops anything; it
   explains and exits. Only the "port free" path was run (Windows Git Bash has neither
   tool); the "busy" path still needs a run on Linux or macOS.

## Decided after the Ollama A/B (2026-11-21)

7. **Few-shot stays off.** It scored 38/49 against 34/49 with pre-retrieval alone, but in
   both "revision I" scenarios the model called no tool and pasted the example's answer,
   citing a reference no tool returned. `AGENT_FEW_SHOT` stays available for experiments
   (default off). A fact-free example was not tried.
8. **A linked section counts as returned.** The eval's `returned_refs` now also includes the
   sections that a returned passage links to (`See [02-revisions](02-revisions.md#…)`). The
   id is in the tool's output, and the model citing it cites the manual correctly.
   `faq-revision-i` failed on exactly this in all three passes. The finished Ollama reports
   are not re-scored: Ollama got passages cut to 500 characters, so what it saw can't be
   rebuilt. The rule applies from the next run.

## Pending

- The Groq run and the Groq token measurement of decision 0024, after the daily quota
  resets (it was nearly used up on 2026-11-21).
- The user's local `.env` sets `LLM_PROVIDER` twice (finding 17): a manual clean-up, not
  committed.
