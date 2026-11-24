"""Chaos switches for the demo: latency, random failures and a maintenance window.

They run before authentication, like an SAP Web Dispatcher in front of the Gateway, and
before any data is touched, so a failed request never reserves a number. `/health` is
not affected.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.config import Settings
from app.messages import request_language
from app.odata import BACKEND_UNAVAILABLE, MAINTENANCE, error_response, is_service_path

MAINTENANCE_RETRY_AFTER_S = 300


async def chaos(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if not is_service_path(request.url.path):
        return await call_next(request)

    settings: Settings = request.app.state.settings
    if settings.sap_latency_ms:
        await asyncio.sleep(settings.sap_latency_ms / 1000)
    if settings.sap_maintenance:
        return error_response(
            503,
            MAINTENANCE,
            "SAP system is in maintenance; try again later",
            headers={"Retry-After": str(MAINTENANCE_RETRY_AFTER_S)},
            language=request_language(request),
        )
    if settings.sap_fail_rate and random.random() < settings.sap_fail_rate:
        return error_response(
            503,
            BACKEND_UNAVAILABLE,
            "SAP backend system temporarily unavailable",
            language=request_language(request),
        )
    return await call_next(request)
