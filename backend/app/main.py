"""FastAPI entry point: `uvicorn app.main:app --reload --port 8000`."""

from fastapi import FastAPI

from app import __version__
from app.api import actions, chat
from app.core.config import get_settings

app = FastAPI(title="Create Design", version=__version__)
app.include_router(chat.router)
app.include_router(actions.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe. Reports the version and which LLM provider is configured."""
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": get_settings().llm_provider,
    }
