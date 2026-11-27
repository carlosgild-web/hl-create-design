# Create Design: "From a question to an answer" — video storyboard

Format: screen recording, English subtitles only, no audio. Duration is whatever it needs (about 7-9 min).
Model: scripted `DemoClient` (provider `demo`, decision 0025). It runs through the same code as Ollama or Groq;
only the model's decision of *which tool to call* is rule-based (see Scene 7).
Line numbers are from commit `7aac41e` + uncommitted changes. **Re-verify before rendering** (`grep -n` each symbol).

## Layout (1920x1080)

```
+-----------------------------------+------------------------------+
| LEFT 1280x1080: the real app      | RIGHT 640x1080: "Under the   |
| (chat + design form), recorded    |  hood" panel                 |
| with Playwright                   |  - file:function:line        |
|                                   |  - small code excerpt        |
|                                   |  - live payload (JSON)       |
+-----------------------------------+------------------------------+
| BOTTOM: subtitle bar (1-2 lines, max ~90 chars each)             |
+------------------------------------------------------------------+
```

A thin "pipeline strip" at the top of the right panel lights up the current layer:
`Browser -> FastAPI -> Agent loop -> Tools -> Validators / Manual / SAP -> back to Browser`.

---

## Scene 0 — Title and map (0:00-0:30)

| Screen | Subtitle |
|---|---|
| Title card: "Create Design — how a question becomes an answer" | Create Design is an assistant that helps an engineer create a KiCad design with a SAP number. |
| Architecture diagram (5 boxes, arrows) | The AI guides. The code decides. Every check, number and file is done by plain code. |
| Highlight the 8 invariants as a short list (3 of them animated: confirmation gate, confined writes, trace) | Three rules matter for this video: the model never has side effects, the user confirms, and every step is traced. |

## Scene 1 — A rule question (0:30-2:30)

User types: **"Why was revision I rejected?"** (ends with `?`, so it is a question).

| # | Screen / event | Subtitle | Right panel (callout) |
|---|---|---|---|
| 1.1 | Text typed in the chat box, click Send | An engineer asks a question in the chat. | `AssistantPanel.tsx` → `useChat.ts:send` L212-244 |
| 1.2 | Browser DevTools-style strip: `POST /api/chat` | The browser sends the text and the form fields as JSON. | `ChatRequest` `api/chat.py` L44-48 |
| 1.3 | Pipeline: FastAPI | FastAPI opens a Server-Sent Events stream. Events will arrive one by one. | `chat()` `api/chat.py` L55-101; `sse()` L51-52 → `event: {type}\ndata: {json}` |
| 1.4 | Pipeline: Agent | The backend creates a conversation and a run, and builds the first messages. | `chat_turn` `agent/service.py` L82-161; `SYSTEM_PROMPT` `prompts.py` L18-74 |
| 1.5 | Intent label: `rule_question` | A tiny classifier looks at the sentence. A question mark means: this is about the manual. | `classify()` `agent/intent.py` L69-91; `preretrieval_for` `service.py` L71-79 |
| 1.6 | Chip appears in chat: "Searching the manual…" (`status` event) | Before the model speaks, the backend searches the Design Manual itself. This is called pre-retrieval. | `_run` `agent/loop.py` L165-226 → `ToolCall("auto_N","search_design_manual",…)` flagged `auto` |
| 1.7 | Animated FTS5 lookup: words → stopwords removed → query → ranked list with scores | Not a vector database: SQLite full-text search. Words are stemmed, then ranked with BM25. Headings and keywords weigh more. | `fts_query` `standards/manual_search.py` L114-119; `ManualIndex.search` L141-166 (`bm25(passages,0,0,0,3.0,1.0,KEYWORDS_WEIGHT)`) |
| 1.8 | Highlight top passage `07-faq#revision-i` (FAQ heading = the question itself), then #2 `02-revisions#skipped-letters` | The best match is an FAQ entry whose heading is the same question. Headings weigh 3x. | `docs/manual/en/07-faq.md`; `02-revisions.md` L19-36 |
| 1.9 | JSON of `tool_result` (3 passages x 500 chars) | The result goes into the conversation as a tool message. A local model gets 3 passages of 500 characters to fit its context. | `OLLAMA_SEARCH_LIMIT`, `OLLAMA_PASSAGE_CHARS` `service.py` L67-68; `_execute` `loop.py` L228-271 |
| 1.10 | Pipeline: Model call | Now the model is called with the question and the passages. | `_model_call` `loop.py` L76-113 → `LLMClient.chat(messages, tools)` `llm/base.py` L93-106 |
| 1.11 | Split: left "DemoClient" / right "Ollama" (static card) | Here the demo model sees a search result and writes a reply with a citation. Ollama or Groq would write it by reading the passages. Same input, same output type. | `DemoClient.chat` `llm/demo.py` L223-289, `_snippet` L202-216 |
| 1.12 | `message` event arrives; answer streams into chat with a clickable `[02-revisions#skipped-letters]` | The answer comes back as one more SSE event. The citation is normalized by the backend. | `normalize_refs`; `parseSse`/`streamChat` `frontend/src/api/sse.ts` L4-28, L53-69; `handle` `useChat.ts` L144-210 |
| 1.13 | Click the citation → manual page opens at the anchor | Every answer points to the exact manual section. | `ManualRef.tsx`, `ManualText.tsx` |
| 1.14 | Open "Agent steps" drawer; shows the `search_design_manual` step with `auto` badge, args and result | Nothing is hidden: every tool call and its result is traced and visible. | `AgentTrace` `agent/trace.py` L13-98; `GET /api/runs/{id}` `chat.py` L122-128; `StepsDrawer.tsx` |

## Scene 2 — Fill the form from one sentence (2:30-4:30)

User types: **"Revision C of HL-HW-26-0003, Bead Sorter Vision Board, designer C. Velazquez"**.
(Verified live with demo, run 41: fills all 5 fields, validates OK, opens a `create_design` card. The e2e sentence
"Revision C of the bead sorter vision board" only fills `revision` with DemoClient; it was written for FakeClient.)
Variant 2.9: same sentence with **"Revision I"** (verified, run 42: `rev_skipped_letter`, "next free revision is C").

| # | Screen / event | Subtitle | Right panel |
|---|---|---|---|
| 2.1 | Typing + Send | The engineer describes the design in plain words. | `useChat.ts:send` L212-244 |
| 2.2 | Intent label: `other` (no `?`, command-like) | This is not a question, so no manual search is needed. | `classify()` `intent.py` L69-91 (number+revision → `other`) |
| 2.3 | Model call #1 | The model has to decide: which tool do I need? | `DemoClient.chat` L223-289 (decision order) |
| 2.4 | `extract_fields` highlighting "C", "bead sorter vision board" | The demo model extracts fields with rules. Ollama would do it with native tool calling: it returns a JSON `tool_calls` list. | `extract_fields` `demo.py` L143-185; `OllamaClient.chat` `llm/ollama.py` L95-156 |
| 2.5 | `tool_call` chip: `propose_form_values` + arguments JSON | It calls a tool. The call is just a name and arguments. | `propose_form_values` `agent/tools.py` L269-276; `ToolRegistry.execute` L465-483 |
| 2.6 | `tool_call`: `validate_design_request` | Then it asks the validators to check the values. | `validate_design_request` `tools.py` L204-215 → `check_fields` `backend/app/designs.py` L144-211 |
| 2.7 | Validators panel: revision rules, status rules, name rules, designer rules | The model does not decide if values are valid. These functions do. | `validate_revision` `standards/validators.py` L236+, `check_status_allows_revision` L319, `validate_design_name` L450, `validate_designer` L628 |
| 2.8 | `form_proposal` event; the form on the left fills in with a highlight | The result is a form proposal. The form fills itself, and the engineer can still edit it. | `_execute` `loop.py` L228-271 yields `result.event`; `useChat.ts` `handle` |
| 2.9 | Variant (10 s): same sentence with "revision I" → red message with code `rev_skipped_letter` | If the revision is wrong, the validator returns a code and a manual reference. The UI translates the code. | `validate_revision` `validators.py` L253-267 `Issue("revision","rev_skipped_letter",…,"02-revisions#skipped-letters")` |
| 2.10 | Final assistant message | The model now explains the result in words. It cannot change it. | `DemoClient._after_validation` `demo.py` L291-319 |

## Scene 3 — Reserve a SAP number (4:30-6:15)

User types: **"Reserve a Hardware number for Bead Polisher Controller, designer C. Velazquez."**
(Verified pattern with demo, run 40: `propose_form_values` → `validate_design_request` → `request_reserve_number` → `pending_action`.
Use a new name: "Bead Drill Controller" triggers the warning `name_exists_in_sap` (HL-HW-23-0004).
Do NOT use "...number for HW, ..." — DemoClient bug, see plan finding D1.)

| # | Screen / event | Subtitle | Right panel |
|---|---|---|---|
| 3.1 | Typing + Send; tools called: `propose_form_values`, `validate_design_request` | Same start: fill and validate. | as Scene 2 |
| 3.2 | Tool call `request_reserve_number` | The values are valid, so the model asks to reserve a number. It cannot do it. | `request_reserve_number` `tools.py` L313-333 |
| 3.3 | Code excerpt `_open_card` | The tool only opens a card. It writes a pending action row and returns. No SAP call happens here. | `_open_card` `tools.py` L292-310 → `create_action` `db/store.py` L164 (`ACTION_TTL` L15) |
| 3.4 | `pending_action` event; confirmation card appears with Confirm / Cancel | The user sees exactly what will happen, and decides. | `ActionCard.tsx` |
| 3.5 | Agent loop ends: `done` event; model's last message | The run is over. The server has done nothing irreversible. | `_run` `loop.py` L165-226 (no tool calls → final message) |
| 3.6 | Pause on a frame: "Confirmation gate (invariant 2)" | Side effects only happen in a separate endpoint, triggered by a click. | `CLAUDE.md` invariant 2 |

## Scene 4 — Confirm (6:15-8:00)

User clicks **Confirm**.

| # | Screen / event | Subtitle | Right panel |
|---|---|---|---|
| 4.1 | Click; `POST /api/actions/{id}/confirm` | The click calls a normal REST endpoint, not the model. | `confirm` `api/actions.py` L43-61 → `confirm_action` `actions.py` L64-92 |
| 4.2 | `claim_action` | The action is claimed once, so a double click cannot reserve two numbers. | `claim_action` `db/store.py` L207 |
| 4.3 | Re-validation | The values are checked again right now, because things could have changed. | `_reserve` `actions.py` L109-147 |
| 4.4 | Pipeline: SAP | The only door to SAP is `SapClient`. | `SapClient.reserve_number` `sap/client.py` L186-190 |
| 4.5 | HTTP trace: `GET` token fetch, `POST /DesignSet` with CSRF header, OData v2 `{"d": {...}}` response | The client gets a CSRF token, then POSTs the design. SAP replies with the number, the material and the WBS. | `_post` `sap/client.py` L198+; `sap-mock/` |
| 4.6 | `audit_log` row appears | Every reserved number is recorded in the audit log. | `write_audit("number_reserved")` in `_reserve` |
| 4.7 | UI: SAP record card with `HL-HW-26-NNNN`; form locks the fields SAP owns | The number comes back to the chat and the form. | `SapCard.tsx` |
| 4.8 | Type description `Polishing station controller, first release`; click the form button **Create design** → card "Create this design?" appears in the chat → Confirm (verified flow) | Creating the files is a second confirmed action. The form button also goes through a card. | `_create` `actions.py` L150-213 |
| 4.9 | Folder tree animation inside `DESIGNS_ROOT`; `resolve_inside` highlights | Every file path is resolved inside the designs folder. `..`, absolute paths and symlinks that escape are rejected. | `resolve_inside` `validators.py` L883 |
| 4.10 | `kicad-cli` exports PDF; preview dialog opens (mask the "Project file" Windows path) | KiCad exports the PDF with the title block filled, and the preview opens. | `create_design` → `kicad-cli`; `PreviewDialog.tsx` (for an existing design: `SapClient.add_revision` `sap/client.py` L192-196) |

## Scene 4b — Open in KiCad: what the tool actually produced (final scene of both videos)

Verified 2026-11-21: clicking **Open in KiCad** shows "KiCad is starting with the project. It may take a few
seconds." and starts the KiCad 9 desktop app. This part is **outside the browser**, so Playwright cannot record it:
it is recorded as a desktop capture (see plan, step V3b).

| # | Screen / event | Subtitle | Right panel |
|---|---|---|---|
| 4b.1 | Click **Open in KiCad** in the preview dialog; status line appears | The last click asks the backend to open the project in KiCad on this PC. | `open_in_kicad` `api/designs.py` L141-171 |
| 4b.2 | Code card | It only starts the program next to `kicad-cli`. It writes no file and calls no SAP, and it is audited. | `kicad_gui` `kicad/launcher.py` L22-29; `popen_detached` L32+; `write_audit("design_opened")` |
| 4b.3 | KiCad Project Manager window: file tree `HL-HW-26-0047_A.kicad_pro`, `.kicad_sch`, `hl_title_block.kicad_wks`, `output/` (`.pdf`, `.svg`) | These are the files the tool created from the company template, inside the designs folder. | folder `HW/HL-HW-26-0047/A` |
| 4b.4 | Open the schematic; zoom to the title block | The title block is filled: number, SAP material, project, department, designer, revision, date. | — |
| 4b.5 | File → Schematic Setup → Project → **Text Variables** | The values are not typed into the drawing. They are project text variables… | `.kicad_pro` `text_variables`: `HL_DESIGN_NUMBER`, `HL_SAP_MATERIAL`, `HL_PROJECT`, `HL_DEPARTMENT`, `HL_DESIGNER` |
| 4b.6 | File → Page Settings → drawing sheet `hl_title_block.kicad_wks` | …that the company drawing sheet reads. Change a variable and every sheet updates. | `hl_title_block.kicad_wks` |
| 4b.7 | Back to the browser, Recent designs shows the new design; fade to end card | From one sentence to a real KiCad project: the AI guided, the code decided, the user clicked. | — |

Masking: hide the Windows path in KiCad's title bar / Project Manager path bar, the Windows taskbar and the user name.

## Scene 5 — The full trace (8:00-8:40)

| Screen | Subtitle |
|---|---|
| `StepsDrawer` for the last run, then `GET /api/runs/{id}` JSON scrolling | One run, one trace: model calls, tool calls, arguments, and results exactly as the model saw them. |
| Counter: model calls, status `answered`, provider `demo`, model `rules` | A run is bounded by `AGENT_MAX_ITERATIONS`, so it cannot loop forever. |

## Scene 6 — What changes with a real model (8:40-9:30)

Static comparison table, then the same `tool_call` JSON on both sides.

| Piece | Demo / Fake | Ollama | Groq |
|---|---|---|---|
| Who picks the tool | Rules in `DemoClient` | The model, native `tools` | The model, OpenAI-style `tools` |
| Request | none | `POST /api/chat`, `temperature 0`, `num_ctx 8192` (`ollama.py` L95-156) | OpenAI-compatible `chat/completions` |
| Result shape | `ChatTurn` | `ChatTurn` (if the model writes the call as text: `_calls_from_text` L227-255) | `ChatTurn` |
| Everything else (pre-retrieval, tools, validators, gate, trace, SSE, UI) | **identical** | **identical** | **identical** |

Subtitle: "Only one thing is swapped: who decides which tool to call. Everything around it is the same code."

## Scene 7 — Closing (9:30-9:45)

Subtitle: "The AI guides. The code decides. Source: github.com/<user>/hl-create-design". End card with 8 invariants.

---

## Capture notes (for the plan)

- Every right-panel payload (args, results, events) must come from a real run, not typed by hand: dump with `GET /api/runs/{id}` and the SSE stream captured by Playwright.
- Scene 2 variant ("revision I") and Scene 4.8 need a SAP design that exists; use the e2e SAP seed (`SAP_TODAY=2026-11-17`).
- Recording uses the stub `kicad-cli` unless `E2E_REAL_KICAD=1` (real PDF in 4.10 looks better).
