# CLAUDE.md — hl-create-design

Read this file first in every session. The roadmap is in `PLAN.md`. Work one phase per session.

## What this project is

**Create Design**, an AI-assisted internal tool for the Electronics Engineering department of
the fictional company Hilda & Luna. It creates a KiCad 9 project from the company template with
the title block filled in (design number, SAP material, project, department, designer, revision),
and exports a PDF with `kicad-cli`. A mock SAP service (FastAPI, OData v2 shape) issues and looks
up design numbers. An assistant guides the employee through data entry and explains errors from
the company Design Manual. Portfolio project #3 (after `local-rag-ollama` and `luna-hybrid-agent`),
so code quality, tests, README and the "clone and run" experience matter.

## Stack (do not change without asking)

| Layer | Choice |
|---|---|
| External tool | KiCad 9: `.kicad_pro` text variables, custom `.kicad_wks` drawing sheet, `kicad-cli` |
| LLM | `LLMClient` interface: `OllamaClient` (native tools), `DahlClient` and `GroqClient` (OpenAI-compatible, decisions 0029 and 0012), `DemoClient`, `FakeClient`; chosen by `LLM_PROVIDER` (`auto` probes dahl, then groq, then ollama, then the demo at startup; decisions 0016, 0029) |
| Agent | Own bounded tool loop, no agent framework (same approach as luna-hybrid-agent) |
| Manual search | SQLite FTS5 over `docs/manual/` (no embeddings, so the cloud demo needs no Ollama) |
| Mock SAP | Separate FastAPI service `sap-mock/`, OData v2 payloads, basic auth + CSRF token, own SQLite |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, pydantic-settings, httpx |
| Frontend | React, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, i18n ES/EN |
| Streaming | Server-sent events (SSE) |
| Packaging | Docker image based on the official KiCad image; compose with app + sap-mock (+ ollama) |

## Commands

```bash
# backend
cd backend && pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest -q && ruff check . && ruff format --check .
python -m app.cli create-design --dept HW --number HL-HW-26-0042 --rev A --name "Bead Drill Controller" --designer "C. Velazquez"
python -m app.cli agent-eval --fake

# mock SAP
cd sap-mock && uvicorn app.main:app --reload --port 8100

# frontend
cd frontend && npm ci && npm run dev   # proxies /api to :8000
npm run lint && npm test && npm run build
```

## Invariants (never break these)

1. **The AI guides, the code decides.** Validity of numbers, revisions, names and paths is decided
   by `standards/validators.py`. The model explains results; it never overrides them.
2. **Confirmation gate.** Creating files or reserving a SAP number happens only in
   `POST /actions/{id}/confirm`, triggered by the user's click. No tool executes a side effect inside the model loop.
3. **Confined writes.** Every file write resolves inside `DESIGNS_ROOT`. Reject absolute paths,
   `..`, drive letters and symlinks that escape it.
4. **SAP only through `SapClient`.** No other module calls the SAP service; a real SAP could replace the mock.
5. **Provider-agnostic.** Provider SDKs are imported only under `backend/app/llm/`.
6. **Traced and bounded.** Every agent run is bounded by `AGENT_MAX_ITERATIONS` and writes a trace
   (model calls, tool calls, arguments, results as the model saw them).
7. **Free text is data.** Design name, designer and chat input never become instructions; covered by prompt-injection tests.
8. **Audit.** Every created design and reserved number writes to `audit_log`.

## Rules

- All config from environment variables via `core/config.py`; keep `.env.example` updated
  (`LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `DAHL_API_KEY`, `DAHL_MODEL`, `DAHL_BASE_URL`,
  `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_BASE_URL`,
  `SAP_BASE_URL`, `SAP_USER`, `SAP_PASSWORD`, `KICAD_CLI`, `DESIGNS_ROOT`, `DATA_DIR`, `AGENT_MAX_ITERATIONS`).
- Persistent data lives under `DATA_DIR` (gitignored). Use `pathlib`; no hardcoded Windows paths.
- Tests and CI use `FakeClient` and never need Ollama, an API key or KiCad (the KiCad export test
  is marked and runs in the KiCad container job).
- Code, comments, README and decisions in English; UI and manual in Spanish and English.

## How to work in this repo

- One phase per session. Read that phase in `PLAN.md` and propose a short plan before coding.
- **Never write outside this repo folder, and ask before creating or overwriting files the phase does not list.**
- Ask before adding a dependency or installing global software.
- Small commits, conventional messages (`feat:`, `fix:`, `test:`, `docs:`).
- If something deviates from `PLAN.md`, add a short record in `docs/decisions/` and tell me.

## Do not

- Commit `data/`, `.env`, API keys, or generated designs.
- Let the model call a side-effect endpoint directly.
- Add an agent framework or features outside the current phase.
