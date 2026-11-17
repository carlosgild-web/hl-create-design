# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

### Changed

- Relative `DESIGNS_ROOT` and `DATA_DIR` are resolved against the repo root.

- sap-mock tests ignore Starlette's warning that asks TestClient users to switch to
  `httpx2`. The stack keeps `httpx`.
