# Phase 9 — Review fixes and FAQ knowledge for the assistant

Plan for Claude Code, from a hands-on review of the running app on 2026-11-21 (local mode,
`LLM_PROVIDER=fake`, ES and EN UI) and a read of the backend, the manual and the eval suite.

**Work one session per block (9a … 9f), in order.** Each block lists its files, tests and
acceptance checks. Follow `CLAUDE.md`: propose a short plan before coding, ask before
creating files that a block does not list, record deviations in `docs/decisions/` (next free
number: `0021`), small conventional commits. The 8 invariants are not negotiable; every
change below keeps them, and the blocks say where they touch one.

**Inputs that come with this plan:**
- `create-design-user-qa.md` (EN) and `create-design-preguntas-frecuentes-es.md` (ES): 54 user
  questions with the manual anchor that answers each one. They are the source for 9a and 9f.
  Copy them to `docs/qa/` (ask first) so they're versioned with the code.

**What the review created** (clean up if you want a fresh demo): SAP number `HL-TFX-26-0007`
(TFX, "Kiln Burn-in Rack") with rev A, and `HL-EMB-24-0002` rev D. Both are in `data/`
(gitignored) and the mock SAP SQLite.

---

## 0. Findings

Severity: **P1** = wrong behavior or a broken promise, **P2** = confusing or risky UX,
**P3** = polish.

| # | Sev | Finding | Evidence | Block |
|---|---|---|---|---|
| 1 | P1 | Demo mode is a fixed English notice, not a scripted assistant. The README says "without a model, the assistant runs in a scripted demo mode" and the GIF shows it filling the form. The app's own **Probar un ejemplo** button gets the notice. | `llm/fake.py` `DEMO_NOTICE`; tested in the UI | 9e |
| 2 | P1 | English text in the Spanish UI: every validator message, the demo notice, and the RELEASED/ECO warning in the Start panel. | `validators.py` builds English strings; screenshots ES | 9b |
| 3 | P1 | Designer check rejects real names: `C. de la Torre` (lowercase particle) and `J. C. Pérez` (two initials). | `_DESIGNER_RE` + `isupper()` on the surname | 9b |
| 4 | P1 | Revisions created in Create Design never reach SAP. The list shows "latest B → rev E" for Bead Counter Display and "latest C" for Workshop Sensor Node after rev D was created. If `DESIGNS_TTL_HOURS` cleanup ever runs, the deleted folders free letters C/D again, which breaks 02-revisions#never-reuse. | `revisions_in_use` = SAP ∪ disk; decision 0018 item 5; `cleanup.py` | 9c |
| 5 | P2 | `title_case` mangles mixed-case and hyphenated words: `LEDs` → `Leds`, `iPhone` → `Iphone`, `burn-in` → `Burn-in` (preview shows "Kiln Burn-in Rack"). The manual promises that capitals are kept. | `validators.title_case` | 9b |
| 6 | P2 | Forbidden words in the code (`rev`, `revision`) aren't in the manual and block valid names: "Copy Stand Controller", "Revision Counter Board". | `_NAME_FORBIDDEN_WORDS` vs 03-title-block#design-name | 9b |
| 7 | P2 | The RELEASED/ECO warning shows in the Start panel but not on the confirmation card, which is where the user decides. | Created EMB-24-0002 rev D: card had no warning | 9c |
| 8 | P2 | After **Get SAP number**, the design name stays editable. Changing it gives an error that talks about "a new revision" (wrong for rev A) and in English. | Tested: "Kiln Burn-in Fixture" after reserving | 9c |
| 9 | P2 | After **Create**, the Start panel still offers **Deshacer** for the reservation, and **Obtener número SAP** stays available with the same values, so a second click reserves a duplicate number. | Tested after creating TFX-26-0007 | 9c |
| 10 | P2 | Spanish design names pass ("Prueba" was created as HL-HW-26-0044) and duplicate names pass ("Bead Drill Controller" exists under 4 numbers). Neither gets a warning. | `/api/designs` list | 9b |
| 11 | P2 | Every new design and revision contains the template circuit "24 V to 5 V supply, 3 A", including rev D of an existing design. Users will ask; nothing explains it. | `kicad/template/hl_template.kicad_sch:2551`; preview | 9a (Q&A) |
| 12 | P3 | "Empezaste de nuevo: las tarjetas anteriores se cancelaron" shows even when the earlier cards were completed. | Switching mode after a create | 9c |
| 13 | P3 | A click on **Crear diseño** during the ~1 s validation debounce is ignored silently. | Tested | 9c |
| 14 | P3 | The HTML title-block preview truncates the description with "…"; the KiCad PDF shows it in full. | 46-char description | 9c |
| 15 | P3 | The revision hint says "One letter", but after `Y` comes `AA`. | `hint.revision` | 9b |
| 16 | P3 | The "Diseño nuevo" / "Desde un diseño existente" radios have no accessible name. The Start panel shows "Rellena antes…" twice, in an order different from the form. Manual refs show as raw `[03-title-block#designer]` text. | a11y tree; UI | 9f |
| 17 | P3 | Local `.env` sets `LLM_PROVIDER` twice (`fake`, then `auto`). Both Create Design and Bead Studio use port 8000. The demo notice mentions only Ollama. | `.env`; first visit served Bead Studio | 9f |
| 18 | P1 | Without `kicad-cli`, **Create** fails and keeps nothing ("The PDF export failed, so nothing was kept"). The README says KiCad is optional and "everything works except the PDF and the preview". | `actions._create` always exports; found while writing `08#no-pdf` (decision 0021) | 9c |

What works well (keep): the confirmation gate, BLOCKED/OBSOLETE handling (`/api/validate`
returns `status_blocked` with SAP's reason), the inline checks, the reserve → fill → create
flow, the preview dialog, the real KiCad PDF.

---

## 1. How to teach the assistant the Q&A

**No fine-tuning and no new knowledge store.** The assistant already has the right shape:
`search_design_manual` (SQLite FTS5 over `docs/manual/{en,es}`, one passage per `##` section,
anchors as citation ids). The Q&A becomes **manual content**, so every provider gets it from
the same search, and every answer is citable under the rule "cite only ids a tool returned".
Four layers, from cheapest to most effective:

1. **Content (9a).** A new chapter `08-using-create-design.md` (EN and ES, same anchors) for
   the app-usage questions the manual doesn't cover (Start panel, cards, Undo, expiry, demo
   mode, Open in KiCad, template circuit, "latest B → rev E"). Extend `07-faq.md` with the rule
   questions that users phrase differently from the manual. Each section ends with a
   `Keywords:` line of synonyms in both languages, which FTS indexes. Keep each passage under
   `MAX_TEXT_CHARS` (900).
2. **Retrieval quality (9a).** Measured today with the 42 cited questions per language (strict
   top-3, before any change): **EN 29/42, ES 30/42.** Several misses land on an equivalent FAQ
   anchor; the real misses are app-usage questions and generic wording. Fixes: EN/ES stopwords
   in `fts_query` (today "what/the/do/qué/el/de" are OR-ed in), the `Keywords:` lines, and a
   CI retrieval test. Target: **≥ 40/42 per language** with accepted alternative anchors.
3. **Backend grounding (9d).** The known failure of `qwen3:4b` is skipping the search, or
   writing the call as text (docs/eval). So for question-like messages the backend runs the
   search **itself** before the first model call and adds it to the conversation as a
   synthetic `search_design_manual` call and result. It shows up in the trace and in "Agent
   steps" (invariant 6). The model still decides how to phrase the answer, and can search
   again.
4. **Per-provider tuning (9d, 9e)**:
   - **Ollama** (`qwen3:4b-instruct`): grounding always on, 3 passages trimmed to ~500
     characters, temperature 0, an answer template in the prompt ("1–3 sentences, then
     `[source]`"), one short few-shot example.
   - **Groq** (`gpt-oss-120b`): grounding on (it also saves a round trip under the rate
     limit). Normalize citations (NFKC, `‑` → `-`) in the checker and the renderer; that
     fixes the known false negative.
   - **Demo, no model**: a new rule-based `DemoClient`. It goes through the same tools, so it
     answers FAQ questions from the top passage with a citation, fills the form from simple
     sentences, and gives a localized notice otherwise. It is deterministic, so CI can test it.

Evals (9f) check all of this per provider with the same question bank.

---

## 9a — FAQ content and retrieval (no model needed)

**Status: done (2026-11-21, decision 0021).** Top-3 retrieval with accepted alternative
anchors: EN questions 34/54 → 54/54, ES 33/54 → 53/54, EN paraphrases 51/108 → 103/108,
ES 59/108 → 107/108. Deviations: `Keywords:` lines on every section of 01–08 (not only the
new ones); "same name" only in `07-faq#same-name` (no `08#duplicate-names`); `08` also has
`what-it-does`, `assistant-fills-form` and `step-by-step`. Q7 answered: keep the template
circuit and explain it.

**Goal:** every question in the Q&A files finds an accepted manual anchor in the top 3, in both
languages.

Files:
- `docs/manual/en/08-using-create-design.md`, `docs/manual/es/08-using-create-design.md` (new;
  ask first). Sections with anchors, at least these:
  `start-panel`, `new-or-existing`, `confirmation-cards`, `card-expired` (30 min,
  `ACTION_TTL`), `undo-number` (Undo clears the form, not the reservation), `next-free-revision`
  ("latest B → rev E"), `template-circuit` (the 24 V → 5 V example: delete it and draw your
  circuit), `open-in-kicad`, `no-pdf` (`kicad-cli` missing), `agent-steps`, `demo-mode`,
  `slow-assistant`, `duplicate-names`.
- `docs/manual/{en,es}/07-faq.md`: add the rule questions in user wording that are not there
  yet (designer format, "where are my files", "who are the leads", "same name").
- Every new or extended section ends with `Keywords: …` (EN and ES synonyms: `undo, deshacer,
  liberar, release number`).
- `backend/app/standards/manual_search.py`: EN and ES stopword sets removed in `fts_query` (keep
  domain words like `rev`, `sap`, `no`). Check whether `Keywords:` should be a separate FTS
  column with its own bm25 weight (try 2.0).
- `backend/app/evals/faq_questions.json` (new): `{id, lang, question, accepted_refs[],
  paraphrases[]}`, built from the two Q&A files plus 2 paraphrases per question (informal
  wording, typos, Mexican Spanish: "¿cómo le hago para…?").
- `backend/tests/test_faq_retrieval.py` (new): for every question and paraphrase,
  `ManualIndex.search(q, lang)` returns an accepted ref in the top 3. Print a score table.
- `docs/decisions/0021-faq-in-the-manual.md`: the FAQ lives in the manual and is cited;
  keywords; stopwords.

Acceptance:
- Retrieval test ≥ 95% top-3 for EN and ES, questions and paraphrases. Today's baseline is in
  the decision record.
- `pytest -q`, ruff, `agent-eval --fake` still green. No validator changes in this block.

---

## 9b — Validators, i18n of messages, warnings

**Status: done (2026-11-21, decision 0022).** Messages by code + params (variants for codes
with several wordings), designer per Q1, title case, version words per Q2 with one
refinement (`Copy` as the first word is only a warning, so "Copy Stand Controller" passes),
`name_looks_spanish` and `name_exists_in_sap` warnings, revision hint. Also: every manual
section now fits the 900-character passage (design-name didn't). Left for 9c/9e: non-issue
action errors and the demo notice are still English.

**Goal:** rules match the manual, and every message reaches the user in their language.

1. **i18n by code (finding 2).** Validators keep returning `Issue(field, code, message, ref)`;
   `message` stays English for the model, traces and logs. Add `params: dict` to `Issue` (for
   example `{"expected": "J", "letters": "I"}`). The frontend renders `issue.code` through
   `messages.ts` templates (`issue.rev_skipped_letter`: "Las letras I, O, Q, S, X y Z no se usan
   nunca ({letters}). La siguiente revisión libre es {expected}.") and falls back to
   `message`. The same applies to the SAP status warning in the Start panel and on cards. A test
   makes sure every `code` in `validators.py` has an EN and an ES template.
2. **Designer (finding 3).** Ask Carlos (open question Q1). Proposed rule: one or two initials
   (`C.` or `J. C.`), then a surname that may contain lowercase particles (`de`, `del`, `de la`,
   `de los`, `van`, `von`, `y`), apostrophes and hyphens. The surname's last word starts with a
   capital. Update `03-title-block#designer` in EN and ES with examples. Tests:
   `C. de la Torre`, `J. C. Pérez`, `M. van Dijk` pass; `c. velazquez`, `C.Velazquez`, `C. 123`
   fail.
3. **Title case (finding 5).** Keep any word that has a capital after its first letter (`LEDs`,
   `iPhone`, `RS-485`, `USB-C`). Capitalize each hyphen-separated part of lowercase words
   (`burn-in` → `Burn-In`). Update the manual sentence and examples. Tests for each case.
4. **Forbidden words (finding 6).** Align code and manual. Proposal (Q2): errors for `new`,
   `final`, `copy` only as **whole-name modifiers**: first or last word, or next to a revision
   letter (`Final Board`, `Board Copy`, `Rev A`). "Copy Stand Controller" and "Revision Counter
   Board" become warnings ("check that this describes the function"), not errors. List the
   words in `03-title-block#design-name`.
5. **Warnings (finding 10)**, never errors, so the code still decides validity:
   - `name_looks_spanish`: the name has ≥ 2 common Spanish words (`de, la, el, para, placa,
     control, prueba, fuente, tarjeta…`) or is one of them. Ref `07-faq#name-language`.
   - `name_exists_in_sap`: another SAP design has the same normalized name. The message names
     it and suggests a new revision of that number instead. Ref
     `01-design-numbering#new-number-or-revision`. Needs `SapClient.list_designs`, already
     available; cache per request.
6. **Revision hint (finding 15):** "Letters, starting at A (after Y comes AA). Never I, O, Q, S,
   X or Z." in EN and ES.

Files: `standards/validators.py`, `designs.py`, `agent/tools.py` (pass params through),
`frontend/src/i18n/messages.ts`, form and card components, `docs/manual/{en,es}/03-title-block.md`,
tests (`test_validators.py`, a new `test_issue_i18n.py`, frontend tests), decision `0022`.

Acceptance: ES UI shows no English validator text (e2e check in ES); the 34 eval scenarios still
pass with `--fake` (update the scripted explanations if codes change); the invariant 1 tests are
unchanged.

---

## 9c — Revision bookkeeping and the card/state UX

**Status: done (2026-11-21, decision 0023).** Option A: `POST RevisionSet` in the mock SAP +
`SapClient.add_revision`, written at confirm before the folder (Q4). Any export failure keeps
the project with a `pdf_not_exported` warning (Q8, finding 18). Card warnings before Confirm
(also the reserve card), name and department locked after reservation (designer stays
editable), no Undo or second reservation after Create, notice wording, queued Create click,
wrapping preview description. e2e: "latest D → rev E" and no second reservation.

1. **Revisions created here count forever (finding 4).** Two options; ask Carlos (Q3):
   - **A (recommended):** add a revision write to the mock SAP (`POST
     /sap/opu/odata/sap/ZHL_PLM_DESIGN_SRV/RevisionSet`, CSRF, like the reserve call) and
     `SapClient.add_revision()`. `_create` calls it **inside the confirm** (invariant 2), after
     the folder is written. If SAP fails, keep the folder, mark the action as partly done and
     show it. Decide and record whether that's acceptable, or whether SAP should be written
     first. This mirrors a real PLM and fixes "latest B → rev E".
   - **B (smaller):** `revisions_in_use` = SAP ∪ disk ∪ `audit_log` `design_created` rows.
     Cleanup can never free a letter. The UI "latest" label shows the max of the three.

   In both cases: a test where a revision folder is deleted (cleanup) and the next free
   revision still skips it.
2. **Warnings on the card (finding 7).** `request_create_design` and `POST /api/actions` store
   `warnings` in the action payload; `ActionCard` shows them (amber, localized by code, with
   the manual link) above **Confirmar**.
3. **Lock the name after reservation (finding 8).** In new mode, once SAP returned the number,
   lock department, name and designer like existing mode ("Set by SAP (locked)"). **Deshacer**
   unlocks them and clears the number. Add a `name_differs_from_sap` wording for rev A: "This
   number was reserved with the name '…'; a design keeps its SAP name."
4. **State after create (finding 9).** After a confirmed create, hide **Deshacer** on the
   reservation card and in the Start panel, and disable **Obtener número SAP** until the user
   clicks **Nuevo diseño**. An e2e test checks that you can't reserve twice from the same values.
5. **Wording (finding 12):** "Empezaste de nuevo. Las tarjetas pendientes se cancelaron; las
   completadas siguen en el historial." Only mention cancellation if a card was pending.
6. **Debounce (finding 13):** while validation is pending, the button shows "Comprobando…"
   and the click is queued, not dropped.
7. **Preview fidelity (finding 14):** the HTML title block lets the description wrap or shrink
   the way the `.kicad_wks` does, so it isn't truncated. Add a visual test with a 60-char
   description.

Files: `sap-mock/` (option A), `sap/client.py`, `actions.py`, `designs.py`,
`standards/validators.py` (option B), `frontend/src/components/{ActionCard,StartPanel,DesignForm,TitleBlockPreview}.tsx`,
`messages.ts`, tests, e2e, decision `0023`.

Acceptance: invariant 2 tests unchanged and green (no SAP write outside confirm); new e2e
"create rev D, then the list says latest D → rev E"; no double reservation possible.

---

## 9d — Agent grounding and provider tuning

**Status: done (2026-11-21, decision 0024), except the Groq token measurement.** Detector
`agent/intent.py` (recall 321/324 on the FAQ bank, no form fill flagged), pre-retrieval in
the loop (`auto_<run id>`, traced `auto`, not a model call), `AGENT_PRERETRIEVAL` +
`agent-eval --preretrieval`, prompt line, Ollama 3 × 500-char passages, `normalize_refs` in
the eval checker, two fake scenarios (fake eval 36/36). The Ollama few-shot waits for the 9f
A/B. **Pending:** Groq's daily quota was almost used up on 2026-11-21; measure Groq tokens per
FAQ turn (off vs auto) after the reset.

1. **Question detector** (`agent/intent.py`, new; ask first): returns `rule_question` when the
   message ends with `?` or starts with `¿`, or contains why/can/how/must/what/when/where /
   por qué/puedo/cómo/debo/qué/cuándo/dónde, **and** no design number with a revision. Pure
   function, unit tested in EN and ES with the FAQ bank (≥ 95% recall on questions, ≤ 5% on the
   form-fill sentences of the eval scenarios).
2. **Pre-retrieval** in `agent/loop.py`: for `rule_question`, before the first model call, run
   `search_design_manual(query=message, language=ui_lang)` through the normal tool executor and
   append the call and result as if the model had made them (id `auto_1`, flagged
   `"auto": true` in the trace). Config: `AGENT_PRERETRIEVAL=auto|on|off` (default `auto` = on
   for questions). Add it to `.env.example` and `core/config.py`.
3. **Prompt** (`prompts.py`): one line, "If a manual search result is already in the
   conversation, answer from it in 1–3 sentences and cite its `source`; search again only if it
   doesn't answer." Plus one short few-shot pair (question → answer with `[02-revisions#skipped-letters]`),
   used only for Ollama if it improves the eval (A/B in 9f).
4. **Ollama:** `search` limit 3 and passages trimmed to ~500 characters when the provider is
   Ollama (pass a `max_chars` from the tool context), `temperature: 0`, check that `num_ctx`
   holds the prompt plus 3 passages.
5. **Groq:** citation normalizer `normalize_ref()` (NFKC, non-breaking hyphens → `-`, strip
   spaces) used by the eval checker and by the frontend renderer. Measure tokens per FAQ turn
   before and after pre-retrieval (the daily cap is `DAILY_TOKEN_CAP`).
6. **Citations:** the model cites only refs that a tool, including the auto search, returned.
   The existing check stays as is.

Files: `agent/intent.py` (new), `agent/loop.py`, `agent/prompts.py`, `agent/tools.py`,
`core/config.py`, `.env.example`, `llm/ollama.py` (options), tests (`test_agent_loop.py`, new
`test_intent.py`), decision `0024`.

Acceptance: `agent-eval --fake` green; new fake scenarios prove that pre-retrieval runs only
for questions, never opens a card, and is traced; prompt-injection scenarios unchanged.

---

## 9e — A real demo mode (`DemoClient`)

**Status: done (2026-11-21, decision 0025).** `LLM_PROVIDER=demo` (Q5), `fake` stays the test
double. FAQ bank 103/108 cited, demo eval 31/33 (wizard and folder-check route fail by design),
header badge, README/manual/Q&A updated, `agent-eval --provider demo`.

**Goal:** with no model, the assistant still helps, and the README claim becomes true.

- `llm/demo.py` (new; ask first): `DemoClient(LLMClient)`, provider `demo`, model `rules`. It's
  separate from `FakeClient`, which stays the test double. It reads the last user message and
  the tool results in `messages` and returns `ChatTurn`s:
  1. **Question** (`intent.rule_question`, or a pre-retrieval result present): answer with the
     top passage's first 1–2 sentences + `[source]`, in the UI language, prefixed "(Asistente
     de demostración)". No passage → localized "I can't find that in the manual; try other
     words."
  2. **Form sentence**: extract the department (codes plus EN/ES names, the same map as
     `DEPARTMENTS_ES`: "Hardware", "potencia", "embebida", "utillaje"), design number (regex),
     revision (`rev C`, `revisión C`), designer (`[A-Z]\. \w+`), name in quotes → call
     `propose_form_values`, then `validate_design_request`, then explain errors with their refs.
     Opens a card only when validation is ok, like a good model.
  3. Otherwise: a localized help message listing what it can do, **without** env var names.
- `llm/factory.py` / `resolve.py`: `LLM_PROVIDER=fake` in the app uses `DemoClient`; tests keep
  `FakeClient` (or add `demo` as its own value and keep `fake` for tests; record the choice).
  The `auto` fallback ends in `demo`.
- UI: the header shows "Asistente: demostración (sin IA)" / "Assistant: demo (no AI)".
- README: describe exactly what demo mode does. Re-record the GIF only if it changes.
- Tests: the demo answers the FAQ bank (≥ 90% cite an accepted ref, deterministic), fills the
  form for the 3 example sentences in EN and ES, and never confirms anything (invariant 2).
  Decision `0025`.

---

## 9f — Evals, real-model runs and polish

1. **FAQ scenarios** in `evals/scenarios.py`: about 15 grouped scenarios (numbers, revisions,
   statuses, name/designer, files/KiCad, cards/app), each in EN and ES, from
   `faq_questions.json`. Expectations: a manual search happened (by the model or pre-retrieval),
   the answer cites an accepted ref, no card is opened, the answer is in the user's language.
2. **Runs and reports** in `docs/eval/` (same format as today):
   - `--fake` (CI).
   - `--provider demo` (CI, deterministic).
   - `--provider ollama --allow-failures`: run with pre-retrieval off, then on, to show the
     improvement.
   - `--provider groq --allow-failures`.

   Update the README eval table.
3. **Polish (findings 16, 17):** accessible names on the mode radios; one "Rellena antes…"
   hint, in the same order as the form; render `[ref]` as a link that opens the passage
   (`GET /api/manual/{lang}/{source}`, read-only, serves only indexed passages) in a small
   dialog; `start.cmd`/`start.sh` check whether port 8000 is busy and say which app holds it
   (or offer `PORT=`). **`start.cmd` done** (ports 8000 and 8100, offers to stop the process;
   decision 0017 item 24); `start.sh` still to do; remove the duplicate `LLM_PROVIDER` from your local `.env` (manual, not
   committed).
4. Close the phase: CHANGELOG, PLAN.md status, README screenshots if the UI changed.

---

## Open questions for Carlos (answer before the block that needs them)

| # | Block | Question | Proposal |
|---|---|---|---|
| Q1 | 9b | Which designer formats are valid? | **Answered (2026-11-21): yes** — one or two initials; surname with lowercase particles (de, del, de la, van, von, y) |
| Q2 | 9b | Forbidden words: errors or warnings? | **Answered: yes** — errors only as whole-name modifiers (`Final`, `Copy` at the end, `Rev A`); otherwise a warning |
| Q3 | 9c | Write revisions to the mock SAP (A) or count `audit_log` (B)? | **Answered (2026-11-21): A** — closer to a real PLM, fixes the "latest" label |
| Q4 | 9c | If SAP fails after the folder is written, roll back the folder or mark the action as partly done? | **Answered: yes** — write SAP first, then the folder; roll back nothing on disk |
| Q5 | 9e | Should `fake` mean the demo in the app, or add a `demo` provider? | **Answered (2026-11-21): add `demo`**; keep `fake` for tests only |
| Q6 | 9d | Pre-retrieval for Groq too, or only Ollama? | **Answered (2026-11-21): both** (saves a round trip on Groq) |
| Q7 | 9a | Should new designs start without the template circuit? | **Answered: keep it** and explain it in `08#template-circuit` |
| Q8 | 9c | Finding 18: without `kicad-cli`, create the project without the PDF, or fix the README? | **Answered: create without the PDF** and say so on the card (KiCad stays optional) |
