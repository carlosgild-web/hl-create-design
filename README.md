# Create Design

[![CI](https://github.com/carlosgild-web/hl-create-design/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosgild-web/hl-create-design/actions/workflows/ci.yml)

An AI-assisted internal tool for the Electronics Engineering department of **Hilda & Luna**
(a fictional company). It creates a KiCad 9 project from the company template with the title
block already filled in, and exports a PDF preview with `kicad-cli`. A mock SAP service issues
and looks up design numbers. An assistant guides the employee through the fields and explains
errors from the company Design Manual. **The AI guides; the code decides.**

> Work in progress. The roadmap is in [PLAN.md](PLAN.md); decisions are in
> [docs/decisions/](docs/decisions/). The full README comes in Phase 8.

## Repository layout

| Folder | What it is |
|---|---|
| `backend/` | FastAPI app: agent, LLM clients, validators, SAP client, KiCad generator |
| `sap-mock/` | Mock SAP PLM service shaped like an SAP Gateway OData v2 API |
| `frontend/` | React + Vite + TypeScript + Tailwind + shadcn/ui |
| `docs/` | Decision records, the Design Manual (ES/EN) and showcase material |

## Run it (development)

Requires Python 3.11+ and Node 20+. Copy `.env.example` to `.env` if you want to change
anything; the defaults need no external service.

```bash
# backend (http://localhost:8000/api/health)
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# mock SAP (http://localhost:8100/health)
cd sap-mock
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8100

# frontend (http://localhost:5173, proxies /api to :8000)
cd frontend
npm ci
npm run dev
```

## Checks

```bash
cd backend  && pytest -q && ruff check . && ruff format --check .
cd sap-mock && pytest -q && ruff check . && ruff format --check .
cd frontend && npm run lint && npm test && npm run build
```

## License

[MIT](LICENSE)
