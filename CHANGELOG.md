# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.0.0] - 2026-11-24

The first release: Phases 0-10 of [PLAN.md](PLAN.md).

### Added

- Phase 0 skeleton: `backend/` and `sap-mock/` FastAPI services with health endpoints,
  settings from environment variables (`.env.example`), ruff and pytest.
- `frontend/`: Vite + React + TypeScript, Tailwind v4, shadcn/ui (Radix, Nova preset),
  TanStack Query, oxlint and Vitest with Testing Library.
- Decision records 0001–0005 (KiCad, provider-agnostic LLM, confirmation gate,
  OData v2 mock SAP, FTS5 for the manual).
- CI: ruff and pytest for both Python services; lint, test and build for the frontend.
- Phase 1: the Design Manual in `docs/manual/{en,es}` (7 sections each, shared anchor
  ids for citations), SAP seed data in `sap-mock/seed` (4 departments, 30 designs, all
  statuses) with a test of every manual rule, and the H&L logo for the title block
  (decision 0006: reused from luna-hybrid-agent).
- Phase 2: the mock SAP service `ZHL_PLM_DESIGN_SRV` in `sap-mock/`: OData v2 reads
  (`DesignSet` with `$filter`/`$top`/`$skip`/`$expand`, `RevisionSet`, `DepartmentSet`,
  `$metadata`), number reservation that is atomic in SQLite, Basic auth with the SAP
  Gateway CSRF handshake, SAP-style errors, and chaos switches (`SAP_LATENCY_MS`,
  `SAP_FAIL_RATE`, `SAP_MAINTENANCE`). `SAP_TODAY` pins the mock's date (decision 0007).
  `sap-mock/README.md` has curl examples.
- Phase 3: the KiCad template and generator. `kicad/template/` has the H&L drawing sheet
  (`hl_title_block.kicad_wks`: logo, design number, SAP material, project, department,
  designer, revision, date) and a 24 V to 5 V buck-stage schematic that passes ERC.
  `standards/validators.py` checks every rule of the Design Manual and cites its section.
  `kicad/renderer.py` copies the template into `<DEPT>/<Number>/<Rev>/` and fills the
  title block; `kicad/exporter.py` runs `kicad-cli` for PDF and SVG. `create_design()`
  is all or nothing and writes `audit_log` (SQLAlchemy, `DATA_DIR/app.db`). New CLI:
  `python -m app.cli create-design`. `docs/showcase/before.pdf` and `after.pdf`.
  Decision 0008.
- Phase 4: the assistant, local-first. `llm/` has `LLMClient`, `OllamaClient` (native tools,
  recovers tool calls written as text) and the scripted `FakeClient`; `sap/client.py` is
  `SapClient` (CSRF + session cookie, retries); `standards/manual_search.py` is FTS5 search
  over the manual. `agent/` has the 8 tools, the bounded loop, traces and the prompt that
  treats free text as data. `POST /api/chat` streams SSE; `POST /api/actions/{id}/confirm`
  is the only side-effect path (confirm once, expiry, re-validation, audit).
  CLI: `chat`, `confirm`, `cancel`. Decision 0009: the Anthropic client waits for Phase 7.
- Phase 6 (evaluation and hardening): `python -m app.cli agent-eval` runs scripted scenarios
  (rules, SAP errors, prompt injection, path traversal) against any provider and writes
  JSON/Markdown reports to `docs/eval/`; prompt tuning took Ollama (qwen3 4B) from 11/27 to
  21/27 with every invariant held.
- Phase 7 (packaging, decision 0013): a Docker image on the official KiCad image, compose
  with the app and the mock SAP (Ollama as a profile), `start.cmd`/`start.sh`, and a CI job
  that exports a real PDF with `kicad-cli`.
- Phase 8 (showcase, decisions 0014-0020):
  - Hilda & Luna palette, the "How this demo works" guide, and a one-screen layout: chat on
    the left, a Start panel (new design or existing SAP design), a guided two-column form
    with inline validation, value-source labels and SAP auto-fill with Undo, and a live
    title-block preview.
  - `LLM_PROVIDER=auto` and a startup check that suggests a model; a session moves to Ollama
    or the demo when Groq's daily quota runs out. Turns never stall silently: status events,
    a turn timeout, Stop and a provider switch.
  - Optional design description (`${COMMENT1}`), Open in KiCad, project zip, copy path.
  - README rewritten for v1.0 with the GIF, before/after title block, architecture,
    invariants and eval table; screenshots recorded by a Playwright showcase spec.
- Phase 9 (review fixes and FAQ knowledge, decisions 0021-0026):
  - The user FAQ is manual content: chapter 08 "Using Create Design", user-worded 07-faq
    sections, a `Keywords:` column, EN/ES stopwords, and a retrieval test (top-3 >= 95%).
  - Rule messages render in the UI language from `code` + `params`. The designer accepts
    two initials and particles, title case keeps `LEDs`/`Burn-In`, version words are
    errors only as whole-name modifiers, and new warnings flag Spanish names and names
    already in SAP.
  - New revisions are recorded in SAP (`POST RevisionSet`) before the folder is written.
    A failed PDF export keeps the project with a warning (KiCad optional). Cards show
    their warnings before Confirm. The name locks after Get SAP number, and there is no
    second reservation after Create.
  - The backend searches the manual itself for questions (`AGENT_PRERETRIEVAL`). Ollama
    gets 3 short passages. Citations with Unicode dashes are normalized.
  - `LLM_PROVIDER=demo`: a rule-based demo assistant. It answers FAQ questions with a
    citation, fills the form from a sentence and opens the card when valid.
  - Manual references open their passage (`GET /api/manual/{lang}/{document}/{anchor}`),
    rendered with its lists, tables, bold and code (no raw Markdown, no HTML).
  - README screenshots and GIF regenerated with real KiCad, plus a cited manual answer
    and its passage.
  - SAP texts and card failures in the UI language (decision 0027): the mock answers in
    the `sap-language` the backend sends; the UI words our part from `failure.<kind>`.
  - 16 FAQ eval scenarios (EN and ES; `cite_any`, `language`), `agent-eval --provider
    demo`, `--preretrieval` and `--few-shot`.
  - `start.cmd` and `start.sh` offer to stop a process that holds port 8000 or 8100.

- Phase 10 (video, decisions 0028-0032):
  - Dahl as the first cloud provider (GLM-5.3 Flash; Phase 9 runs 38/49, invariants held).
    A busy Dahl model hands over to the next one (`DAHL_FALLBACK_MODELS`).
  - Open in KiCad starts the schematic editor with the design.
  - `video/`: recorded explainer videos from the real app, with an "Under the hood" panel
    whose payloads are checked against the capture, and the KiCad window at the end. The
    README video is the 2-minute Groq take ([docs/video.md](docs/video.md)).
  - `start.cmd video`: fresh seed data in `data-video/` for recordings.
  - Fixes found in the takes: a model-opened card fills the form, a confirmed reservation
    fills the name, chat answers render bold and code, placeholders read "e.g. …",
    `<think>` reasoning is never shown.

### Changed

- Relative `DESIGNS_ROOT` and `DATA_DIR` are resolved against the repo root.

- sap-mock tests ignore Starlette's warning that asks TestClient users to switch to
  `httpx2`. The stack keeps `httpx`.
- Phase 5: the React UI. Form (department, number, revision, name, designer, folder
  preview) with the assistant's suggestions highlighted until you edit them; assistant
  panel with SSE streaming, SAP cards and confirmation cards (confirm, cancel, expired,
  rule errors under the field); preview of the title block (SVG, PDF link); recent
  designs; agent-steps drawer; ES/EN. Backend: `/api/departments`, `/api/designs`,
  `/api/designs/.../preview.{pdf,svg}`, `POST /api/actions` (decision 0010).
  Playwright e2e in `e2e/` on a scripted model and a stub `kicad-cli`; new CI job.

[Unreleased]: https://github.com/carlosgild-web/hl-create-design/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/carlosgild-web/hl-create-design/releases/tag/v1.0.0
