"""The endpoints behind the Phase 5 UI: form-opened actions, recent designs, previews."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.db.session import audit_rows
from app.main import app
from tests.test_exporter import FakeKicadCli

CREATE = {
    "department": "HW",
    "design_number": "HL-HW-26-0042",
    "revision": "C",
    "name": "Bead Drill Controller",
    "designer": "C. Velazquez",
}


@pytest.fixture
def api(settings, fake_sap):
    app.dependency_overrides[deps.settings_dep] = lambda: settings
    app.dependency_overrides[deps.sap_factory_dep] = lambda: fake_sap.client
    app.dependency_overrides[deps.runner_dep] = FakeKicadCli
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_departments(api):
    codes = [d["code"] for d in api.get("/api/departments").json()]
    assert codes == ["HW", "PWR", "EMB", "TFX"]


def test_proposing_from_the_form_executes_nothing(api, settings, fake_sap):
    response = api.post("/api/actions", json={"kind": "create_design", "payload": CREATE})

    assert response.status_code == 201
    action = response.json()
    assert action["status"] == "pending"
    assert not settings.designs_root.exists() or not any(settings.designs_root.iterdir())
    assert fake_sap.reservations == []
    assert audit_rows(deps.engine_dep(settings)) == []


def test_form_action_goes_through_the_same_gate(api, settings):
    action = api.post("/api/actions", json={"kind": "create_design", "payload": CREATE}).json()

    done = api.post(f"/api/actions/{action['id']}/confirm")

    assert done.status_code == 200
    assert done.json()["result"]["folder"] == "HW/HL-HW-26-0042/C"
    assert api.post(f"/api/actions/{action['id']}/confirm").status_code == 409


def test_unknown_kind_and_conversation_are_refused(api):
    assert api.post("/api/actions", json={"kind": "delete_all", "payload": {}}).status_code == 422
    missing = api.post(
        "/api/actions", json={"kind": "create_design", "payload": {}, "conversation_id": "nope"}
    )
    assert missing.status_code == 404


def test_recent_designs_lists_created_ones_newest_first(api):
    assert api.get("/api/designs").json() == []
    for rev in ("C", "D"):
        action = api.post(
            "/api/actions", json={"kind": "create_design", "payload": CREATE | {"revision": rev}}
        ).json()
        assert api.post(f"/api/actions/{action['id']}/confirm").status_code == 200

    recent = api.get("/api/designs").json()

    assert [d["revision"] for d in recent] == ["D", "C"]
    assert recent[0]["name"] == "Bead Drill Controller"
    assert recent[0]["department"] == "HW"


def test_preview_serves_the_pdf_and_svg(api):
    action = api.post("/api/actions", json={"kind": "create_design", "payload": CREATE}).json()
    api.post(f"/api/actions/{action['id']}/confirm")

    pdf = api.get("/api/designs/HW/HL-HW-26-0042/C/preview.pdf")
    svg = api.get("/api/designs/HW/HL-HW-26-0042/C/preview.svg")

    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml"


@pytest.mark.parametrize(
    "path",
    [
        "/api/designs/HW/HL-HW-26-0042/Z/preview.pdf",
        "/api/designs/HW/HL-HW-26-0042/C/preview.png",
        "/api/designs/..%2F..%2Fx/HL-HW-26-0042/C/preview.pdf",
        "/api/designs/HW/..%5C..%5CWindows/C/preview.pdf",
        "/api/designs/C%3A/HL-HW-26-0042/C/preview.pdf",
    ],
)
def test_preview_refuses_unknown_and_unsafe_paths(api, path):
    assert api.get(path).status_code in {404, 422}


# --- inline validation (decision 0017, block B) -----------------------------------------


def validate(api, **fields):
    response = api.post("/api/validate", json={"fields": fields})
    assert response.status_code == 200
    return response.json()


def test_validate_reports_a_skipped_revision_letter_with_its_manual_ref(api):
    result = validate(api, revision="I")
    [error] = result["errors"]
    assert error["field"] == "revision" and error["code"] == "rev_skipped_letter"
    assert error["ref"] == "02-revisions#skipped-letters"
    assert result["normalized"] == {"revision": "I"}  # never silently replaced


def test_validate_matches_the_assistant_tool(api, settings, fake_sap, engine, manual):
    from app.agent.tools import DesignFieldsArgs, ToolContext, validate_design_request
    from app.db import store

    fields = {"department": "HW", "design_number": "HL-HW-26-0042", "revision": "B"}
    with fake_sap.client() as sap:
        ctx = ToolContext(
            settings=settings,
            sap=sap,
            manual=manual,
            engine=engine,
            conversation_id=store.create_conversation(engine),
        )
        tool = validate_design_request(DesignFieldsArgs(**fields), ctx).content

    assert validate(api, **fields) == tool
    assert tool["sap"]["wbs"] and tool["next_free_revision"] == "C"


def test_validate_normalizes_and_writes_nothing(api, settings, fake_sap):
    result = validate(api, name="bead  sorter vision board", designer="c.  velazquez")
    assert result["normalized"]["name"] == "Bead Sorter Vision Board"
    assert not settings.designs_root.exists() or not any(settings.designs_root.iterdir())
    assert fake_sap.reservations == []
    assert audit_rows(deps.engine_dep(settings)) == []


def test_validate_with_nothing_filled_is_quiet(api):
    assert validate(api) == {
        "ok": True,
        "normalized": {},
        "errors": [],
        "warnings": [],
        "missing": [],
    }


def test_cards_from_the_form_show_the_stored_values(api):
    payload = {**CREATE, "name": "bead  sorter vision board", "revision": "c"}
    action = api.post("/api/actions", json={"kind": "create_design", "payload": payload}).json()
    assert action["payload"]["name"] == "Bead Sorter Vision Board"
    assert action["payload"]["revision"] == "C"


def test_departments_have_spanish_names(api):
    hw = api.get("/api/departments").json()[0]
    assert hw == {"code": "HW", "name": "Hardware Design", "name_es": "Diseño de Hardware"}
