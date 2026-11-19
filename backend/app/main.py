"""FastAPI entry point: `uvicorn app.main:app --reload --port 8000`."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import __version__
from app.api import actions, chat, designs
from app.cleanup import cleanup_designs
from app.core.config import get_settings
from app.db.session import get_engine

log = logging.getLogger("app.cleanup")
CLEANUP_EVERY_S = 3600


async def _cleanup_loop() -> None:
    """Hourly: delete generated designs older than DESIGNS_TTL_HOURS (public demo)."""
    settings = get_settings()
    while True:
        try:
            removed = await asyncio.to_thread(
                cleanup_designs,
                settings.designs_root,
                get_engine(settings.data_dir),
                older_than_hours=settings.designs_ttl_hours,
            )
            if removed:
                log.info("cleanup removed %d design folders", len(removed))
        except Exception:  # keep the job alive; the next round tries again
            log.exception("cleanup failed")
        await asyncio.sleep(CLEANUP_EVERY_S)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_cleanup_loop()) if get_settings().designs_ttl_hours > 0 else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Create Design", version=__version__, lifespan=lifespan)
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(designs.router)


def mount_frontend(application: FastAPI, directory: Path) -> bool:
    """Serve the built React app at `/` (one container serves UI and API). Unknown paths
    return `index.html` so client-side routes work; `/api/*` is never shadowed."""
    index = directory / "index.html"
    if not index.is_file():
        return False
    root = directory.resolve()

    @application.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)

    return True


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe. Reports the version and which LLM provider is configured."""
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": get_settings().llm_provider,
    }


# Registered last, so every `/api/...` route above wins.
mount_frontend(app, get_settings().frontend_dir)
