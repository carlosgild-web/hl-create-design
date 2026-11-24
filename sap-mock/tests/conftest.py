"""Fixtures: an app per test with its own SQLite file and the seed snapshot date."""

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.odata import SERVICE_ROOT

TODAY = date(2026, 11, 17)  # seed snapshot date: the next HW-26 number is 0042
AUTH = ("demo", "demo")
SEED = Path(__file__).resolve().parents[1] / "seed"


def make_settings(data_dir: Path, **overrides) -> Settings:
    """Settings that ignore the developer's `.env` and environment chaos switches."""
    values = {
        "sap_user": "demo",
        "sap_password": "demo",
        "data_dir": data_dir,
        "sap_today": TODAY,
        "sap_latency_ms": 0,
        "sap_fail_rate": 0.0,
        "sap_maintenance": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def seed_designs() -> list[dict]:
    return json.loads((SEED / "designs.json").read_text(encoding="utf-8"))["designs"]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def make_client():
    """Build an authenticated client for given settings (the lifespan seeds the db)."""
    clients: list[TestClient] = []

    def _make(settings: Settings, auth: tuple[str, str] | None = AUTH) -> TestClient:
        client = TestClient(create_app(settings))
        client.__enter__()
        if auth is not None:
            client.auth = auth
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client, settings: Settings) -> TestClient:
    return make_client(settings)


@pytest.fixture
def db(settings: Settings) -> Database:
    database = Database(settings.db_path)
    database.init()
    return database


def svc(path: str = "") -> str:
    """A path under the OData service root."""
    return SERVICE_ROOT + path


def fetch_token(client: TestClient) -> str:
    """CSRF handshake; the session cookie stays in the client's cookie jar."""
    response = client.get(svc("/"), headers={"x-csrf-token": "Fetch"})
    assert response.status_code == 200
    return response.headers["x-csrf-token"]


def reserve(client: TestClient, token: str, **body):
    payload = {"Department": "HW", "Name": "Bead Drill Controller", "CreatedBy": "C. Velazquez"}
    payload.update(body)
    return client.post(svc("/DesignSet"), json=payload, headers={"x-csrf-token": token})


def assert_sap_error(response, status: int, code: str, lang: str = "en") -> dict:
    """The SAP Gateway error body; returns `error` for further checks."""
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]["lang"] == lang
    assert error["message"]["value"]
    assert error["innererror"]["transactionid"]
    return error
