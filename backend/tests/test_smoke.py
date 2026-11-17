from fastapi.testclient import TestClient

from app import __version__
from app.core.config import Settings
from app.main import app


def test_health_reports_ok_and_version():
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_settings_defaults_need_no_external_service(monkeypatch):
    # Ignore the developer's .env and environment: these are the code defaults.
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "fake"
    assert settings.anthropic_api_key is None
    assert settings.agent_max_iterations == 6


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "3")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "ollama"
    assert settings.agent_max_iterations == 3
