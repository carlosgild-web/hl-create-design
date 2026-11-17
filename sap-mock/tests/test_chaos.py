"""Chaos switches (latency, random failures, maintenance) and their configuration."""

import time
from datetime import date

from app.config import Settings
from app.odata import BACKEND_UNAVAILABLE, MAINTENANCE
from tests.conftest import assert_sap_error, fetch_token, make_settings, reserve, svc


def test_maintenance_answers_503_with_retry_after(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_maintenance=True))

    response = client.get(svc("/DesignSet('HL-HW-24-0007')"))

    assert_sap_error(response, 503, MAINTENANCE)
    assert int(response.headers["retry-after"]) > 0


def test_maintenance_comes_before_authentication(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_maintenance=True), auth=None)

    assert_sap_error(client.get(svc("/DesignSet")), 503, MAINTENANCE)


def test_health_is_not_affected_by_chaos(make_client, tmp_path):
    settings = make_settings(tmp_path, sap_maintenance=True, sap_fail_rate=1.0)
    client = make_client(settings)

    assert client.get("/health").status_code == 200


def test_fail_rate_one_always_fails(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_fail_rate=1.0))

    for _ in range(5):
        assert_sap_error(client.get(svc("/DepartmentSet")), 503, BACKEND_UNAVAILABLE)


def test_failed_requests_reserve_nothing(make_client, tmp_path):
    healthy = make_client(make_settings(tmp_path))
    token = fetch_token(healthy)
    flaky = make_client(make_settings(tmp_path, sap_fail_rate=1.0))
    flaky.cookies = healthy.cookies

    assert_sap_error(reserve(flaky, token), 503, BACKEND_UNAVAILABLE)

    assert reserve(healthy, token).json()["d"]["DesignNumber"] == "HL-HW-26-0042"


def test_latency_delays_service_responses(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_latency_ms=150))

    started = time.perf_counter()
    response = client.get(svc("/DepartmentSet"))
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed >= 0.15


def test_settings_read_the_chaos_switches_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SAP_TODAY", "2026-11-17")
    monkeypatch.setenv("SAP_LATENCY_MS", "250")
    monkeypatch.setenv("SAP_FAIL_RATE", "0.2")
    monkeypatch.setenv("SAP_MAINTENANCE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    settings = Settings(_env_file=None)

    assert settings.today() == date(2026, 11, 17)
    assert settings.sap_latency_ms == 250
    assert settings.sap_fail_rate == 0.2
    assert settings.sap_maintenance is True
    assert settings.db_path == tmp_path / "sap_mock.db"


def test_empty_sap_today_means_the_real_date(monkeypatch):
    monkeypatch.setenv("SAP_TODAY", "")

    assert Settings(_env_file=None).today() == date.today()
