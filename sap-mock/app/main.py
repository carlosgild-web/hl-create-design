"""FastAPI entry point: `uvicorn app.main:app --reload --port 8100`.

A mock of an SAP Gateway OData v2 service, `ZHL_PLM_DESIGN_SRV`, for the Create Design
demo. Not a real SAP. See `sap-mock/README.md` and decision 0004.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.chaos import chaos
from app.config import Settings
from app.db import Database
from app.messages import request_language
from app.odata import INVALID_REQUEST, RESOURCE_NOT_FOUND, SapError, error_response
from app.routes import router
from app.security import CsrfStore, gateway


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own `Settings` (temporary database, fixed date)."""
    settings = settings or Settings()
    db = Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.init()
        yield

    app = FastAPI(
        title="H&L mock SAP (demo, not a real SAP)",
        version=__version__,
        description="Mock of an SAP Gateway OData v2 service for the Create Design demo.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.csrf = CsrfStore()

    # The last middleware added runs first: chaos, then auth and CSRF, then the route.
    app.add_middleware(BaseHTTPMiddleware, dispatch=gateway)
    app.add_middleware(BaseHTTPMiddleware, dispatch=chaos)

    @app.exception_handler(SapError)
    async def sap_error(request: Request, exc: SapError) -> JSONResponse:
        return error_response(
            exc.status,
            exc.code,
            exc.message,
            exc.headers,
            language=request_language(request),
            params=exc.params,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"Invalid request: {where or 'body'}: {first.get('msg', 'invalid value')}"
        return error_response(400, INVALID_REQUEST, message)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = RESOURCE_NOT_FOUND if exc.status_code == 404 else INVALID_REQUEST
        return error_response(exc.status_code, code, str(exc.detail), exc.headers)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness probe for compose and the backend's SapClient (no auth, no chaos)."""
        return {"status": "ok", "version": __version__}

    app.include_router(router)
    return app


app = create_app()
