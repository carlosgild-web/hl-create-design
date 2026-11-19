"""FastAPI dependencies. Tests override them (fake LLM, fake SAP transport, fake kicad-cli)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import Engine

from app.core.config import MANUAL_DIR, Settings, get_settings
from app.core.limits import client_ip, get_limiter
from app.db.session import get_engine
from app.kicad.exporter import Runner
from app.llm.base import LLMClient
from app.llm.factory import make_client
from app.sap.client import SapClient
from app.standards.manual_search import ManualIndex

SapFactory = Callable[[], SapClient]
LLMFactory = Callable[[], LLMClient]


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def engine_dep(settings: SettingsDep) -> Engine:
    return get_engine(settings.data_dir)


@lru_cache
def _manual() -> ManualIndex:
    return ManualIndex(MANUAL_DIR)


def manual_dep() -> ManualIndex:
    return _manual()


def sap_factory_dep(settings: SettingsDep) -> SapFactory:
    """A factory, not a client: a streamed response outlives the dependency's scope, so
    the chat endpoint opens and closes its own client."""

    def make() -> SapClient:
        return SapClient(
            settings.sap_base_url, settings.sap_user, settings.sap_password.get_secret_value()
        )

    return make


def llm_factory_dep(settings: SettingsDep) -> LLMFactory:
    return lambda: make_client(settings)


def runner_dep() -> Runner:
    return subprocess.run


def rate_limit_dep(request: Request, settings: SettingsDep) -> None:
    """Per-IP limit on the requests that cost tokens or change things (`RATE_LIMIT_PER_MIN`)."""
    if settings.rate_limit_per_min <= 0:
        return
    ip = client_ip(
        request.client.host if request.client else None,
        request.headers.get("x-forwarded-for"),
        trust_forwarded=settings.trust_forwarded_for,
    )
    wait = get_limiter(settings.rate_limit_per_min).hit(ip)
    if wait is not None:
        raise HTTPException(
            429,
            "rate_limited",
            headers={"Retry-After": str(wait)},
        )


RateLimited = Depends(rate_limit_dep)

EngineDep = Annotated[Engine, Depends(engine_dep)]
ManualDep = Annotated[ManualIndex, Depends(manual_dep)]
SapFactoryDep = Annotated[SapFactory, Depends(sap_factory_dep)]
LLMFactoryDep = Annotated[LLMFactory, Depends(llm_factory_dep)]
RunnerDep = Annotated[Runner, Depends(runner_dep)]
