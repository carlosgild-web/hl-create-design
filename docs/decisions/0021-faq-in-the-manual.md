# 0021: The user FAQ lives in the Design Manual

**Status:** accepted (2026-11-21)

## Context

Phase 9 block 9a (`PLAN-phase-9-review-and-faq.md`). The review produced 54 user questions in
English and Spanish (`docs/qa/`). 12 of them were about the app itself (Start panel, cards,
Undo, expiry, demo mode, Open in KiCad, the template circuit…), and the manual had no section
for those, so the assistant could not cite an answer. The rest are rule questions worded the
way users ask them, not the way the manual is written.

Retrieval was measured with a new question bank (`backend/app/evals/faq_questions.json`): 54
questions per language, each with 2 paraphrases (informal wording, a typo, Mexican Spanish)
and the manual anchors that answer it. Strict top-3 of `ManualIndex.search` in the question's
language, with equivalent anchors accepted:

| | Before | After |
|---|---|---|
| EN questions | 34/54 (63 %) | 54/54 (100 %) |
| ES questions | 33/54 (61 %) | 53/54 (98 %) |
| EN paraphrases | 51/108 (47 %) | 103/108 (95 %) |
| ES paraphrases | 59/108 (55 %) | 107/108 (99 %) |

## Decision

1. **The FAQ is manual content, searched by the existing tool.** There's no fine-tuning, no
   new knowledge store and no new tool. Every provider (Groq, Ollama, the demo) gets the
   answers from `search_design_manual`, and every answer is citable under the existing rule
   "cite only ids a tool returned".
2. **New chapter `08-using-create-design.md`** (EN and ES, same anchors): `what-it-does`,
   `new-or-existing`, `start-panel`, `assistant-fills-form`, `step-by-step`,
   `confirmation-cards`, `card-expired`, `undo-number`, `next-free-revision`,
   `template-circuit`, `open-in-kicad`, `no-pdf`, `agent-steps`, `demo-mode`, `slow-assistant`.
   The facts were checked against the code, not copied from the Q&A draft. Two answers in the
   draft were wrong:
   - **"No PDF"**: without `kicad-cli`, a create in the app fails and nothing is kept. The
     draft said the project is still created. See the follow-up below.
   - **Template circuit**: the example circuit stays in the template, as the user chose for
     Q7, and `08#template-circuit` explains it.
3. **`07-faq.md` gets four sections in user wording**: `designer-format`,
   `where-are-my-files`, `department-leads`, `same-name`. "Same name" lives only in 07 (the
   9a plan also listed an `08#duplicate-names`), so two passages don't compete for one
   question.
4. **A `Keywords:` / `Palabras clave:` line** ends every section, in chapters 01–08. It holds
   synonyms in both languages. This goes beyond the plan, which asked only for new and
   extended sections: without keywords on chapters 01–06, paraphrases stayed at 70 % (EN).
   The line is parsed into its own FTS5 column with bm25 weight **2.0** (heading 3.0, text
   1.0). Weights 1.0, 1.5, 2.0, 3.0 and 4.0 were tried; 1.0 scored lower and 2.0 to 4.0 were
   equal. Keywords are **not** part of the passage text, so the model never sees the synonym
   list.
5. **Stopwords**: `fts_query` drops EN and ES question and function words (what, the, how,
   qué, el, de, puedo…), compared without accents. Words that change a rule's meaning stay
   searchable (`no`, `not`, `new`, `nuevo`, `rev`, `sap`). If a query is only stopwords, the
   unfiltered words are used, so a query is never empty.
6. **A CI retrieval test** (`backend/tests/test_faq_retrieval.py`) asserts ≥ 95 % top-3 per
   language for questions and for paraphrases. It also checks that every accepted anchor
   exists. `-s` prints the score table and the misses.

## Consequences

- Adding an app feature that users will ask about means adding an 08 section with keywords
  and a bank entry; the test says whether it is found.
- The EN paraphrase score is exactly at the 95 % threshold. The remaining misses are a typo
  ("desing"), single-letter queries ("revision O", where one-letter words are dropped) and
  "release a design", which ranks the RELEASED status sections above "who changes".
  Accepted as they are; 9d's pre-retrieval and the model's own second search cover them.
- `08#demo-mode` describes today's fixed notice; block 9e rewrites it with the `DemoClient`.
- Follow-up for 9c (new finding 18): without `kicad-cli`, **Create** fails with "The PDF export
  failed, so nothing was kept". The README says KiCad is optional ("everything works except
  the PDF and the preview"), which isn't true in the app. Either the app creates the project
  without the PDF when `kicad-cli` is missing, or the README changes.
