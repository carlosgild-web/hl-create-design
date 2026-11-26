"""Shared fixtures: isolated settings and database, the fake SAP, the manual index."""

from __future__ import annotations

import pytest

from app.core.config import MANUAL_DIR, Settings
from app.db.session import get_engine
from app.standards.manual_search import ManualIndex
from tests.fake_sap import FakeSap


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        designs_root=tmp_path / "designs",
        data_dir=tmp_path / "data",
        kicad_cli="kicad-cli",
        kicad_autodetect=False,  # tests never depend on a KiCad installed here
        llm_provider="fake",
        agent_max_iterations=6,
        # The loop's mechanics tests script every call; pre-retrieval has its own tests.
        agent_preretrieval="off",
    )


@pytest.fixture
def engine(settings):
    return get_engine(settings.data_dir)


@pytest.fixture
def fake_sap() -> FakeSap:
    return FakeSap()


@pytest.fixture
def sap(fake_sap):
    with fake_sap.client() as client:
        yield client


@pytest.fixture(scope="session")
def manual() -> ManualIndex:
    return ManualIndex(MANUAL_DIR)
