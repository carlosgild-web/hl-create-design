"""`GET /api/sap/designs` for the Start panel (decision 0018): read-only, through SapClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


@pytest.fixture
def api(settings, fake_sap):
    app.dependency_overrides[deps.settings_dep] = lambda: settings
    app.dependency_overrides[deps.sap_factory_dep] = lambda: fake_sap.client
    yield TestClient(app)
    app.dependency_overrides.clear()


def designs(api, **params):
    response = api.get("/api/sap/designs", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_lists_every_design_with_what_the_panel_needs(api):
    rows = {r["design_number"]: r for r in designs(api)}
    assert set(rows) == {"HL-EMB-23-0002", "HL-HW-24-0003", "HL-HW-26-0042", "HL-PWR-25-0007"}
    drill = rows["HL-HW-26-0042"]
    assert drill["name"] == "Bead Drill Controller" and drill["revisions"] == ["A", "B"]
    assert drill["next_free_revision"] == "C" and drill["selectable"] is True
    assert rows["HL-PWR-25-0007"]["selectable"] is True  # RELEASED: allowed, with an ECO
    assert rows["HL-HW-24-0003"]["selectable"] is False
    assert rows["HL-HW-24-0003"]["block_reason"] == "Supplier part discontinued"
    assert rows["HL-EMB-23-0002"]["successor"] == "HL-EMB-25-0011"


def test_filters_by_department_status_and_text(api):
    assert [r["design_number"] for r in designs(api, department="HW", status="IN_WORK")] == [
        "HL-HW-26-0042"
    ]
    assert [r["design_number"] for r in designs(api, q="drill")] == ["HL-HW-26-0042"]
    assert [r["design_number"] for r in designs(api, q="emb-23")] == ["HL-EMB-23-0002"]
    assert designs(api, q="nothing like this") == []


def test_rejects_unknown_filters_and_long_text(api):
    assert api.get("/api/sap/designs", params={"department": "XX"}).status_code == 422
    assert api.get("/api/sap/designs", params={"status": "DELETED"}).status_code == 422
    assert api.get("/api/sap/designs", params={"q": "x" * 41}).status_code == 422


def test_sap_down_answers_503_with_the_known_payload(api, fake_sap):
    fake_sap.fail_next = 10
    response = api.get("/api/sap/designs")
    assert response.status_code == 503
    assert response.json()["code"] == "sap_unavailable"
    assert response.json()["ref"] == "06-sap-statuses#sap-unavailable"


def test_one_design_or_404(api):
    assert api.get("/api/sap/designs/HL-HW-26-0042").json()["next_free_revision"] == "C"
    assert api.get("/api/sap/designs/HL-HW-26-0999").status_code == 404


def test_next_free_revision_agrees_with_validation_for_every_design(api, settings):
    # a revision folder on disk that SAP does not know yet moves the next free one on
    (settings.designs_root / "HW" / "HL-HW-26-0042" / "C").mkdir(parents=True)
    for row in designs(api):
        fields = {"department": row["department"], "design_number": row["design_number"]}
        checked = api.post("/api/validate", json={"fields": fields}).json()
        assert row["next_free_revision"] == checked["next_free_revision"], row["design_number"]
    assert (
        next(r for r in designs(api) if r["design_number"] == "HL-HW-26-0042")["next_free_revision"]
        == "D"
    )


def test_the_list_writes_nothing(api, settings, fake_sap):
    designs(api)
    assert fake_sap.posts == []
    assert not settings.designs_root.exists() or not any(settings.designs_root.iterdir())


def test_sap_down_gives_the_panel_a_code_and_sap_text(api, fake_sap):
    fake_sap.maintenance = True

    response = api.get("/api/sap/designs", params={"lang": "es"})

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "sap_unavailable"
    assert body["params"]["sap_code"] == "ZHL_GW/003"
    assert fake_sap.requests[-1].headers["sap-language"] == "ES"
