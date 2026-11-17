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
