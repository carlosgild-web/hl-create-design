"""FastAPI entry point: `uvicorn app.main:app --reload --port 8100`.

The OData service `ZHL_PLM_DESIGN_SRV` arrives in Phase 2 (see PLAN.md, section 4).
"""

from fastapi import FastAPI

from app import __version__

app = FastAPI(title="H&L mock SAP", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for compose and the backend's SapClient."""
    return {"status": "ok", "version": __version__}
