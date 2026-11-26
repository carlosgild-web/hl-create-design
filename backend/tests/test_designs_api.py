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
    assert fake_sap.revisions_added == []
    assert fake_sap.posts == []  # the card's check only reads SAP
    assert audit_rows(deps.engine_dep(settings)) == []


def test_the_card_carries_the_warnings_before_confirm(api):
    reserve = {"department": "HW", "name": "Prueba", "designer": "C. Velazquez"}
    action = api.post("/api/actions", json={"kind": "reserve_number", "payload": reserve}).json()
    assert [w["code"] for w in action["payload"]["warnings"]] == ["name_looks_spanish"]

    released = {"department": "PWR", "design_number": "HL-PWR-25-0007", "designer": "C. Velazquez"}
    card = api.post("/api/actions", json={"kind": "create_design", "payload": released}).json()
    assert "status_released_needs_eco" in [w["code"] for w in card["payload"]["warnings"]]


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


def test_validate_warns_when_another_sap_design_has_the_same_name(api):
    result = validate(api, department="HW", name="bead drill controller")
    assert result["ok"]
    [warning] = [w for w in result["warnings"] if w["code"] == "name_exists_in_sap"]
    assert warning["params"] == {"number": "HL-HW-26-0042", "name": "Bead Drill Controller"}
    assert warning["ref"] == "07-faq#same-name"
    # the design's own number is not a duplicate of itself
    own = validate(
        api, department="HW", design_number="HL-HW-26-0042", name="Bead Drill Controller"
    )
    assert not [w for w in own["warnings"] if w["code"] == "name_exists_in_sap"]


def test_the_same_name_hint_is_skipped_when_sap_fails(api, fake_sap):
    fake_sap.maintenance = True
    result = validate(api, department="HW", name="Bead Drill Controller")
    assert result["ok"] and result["warnings"] == []


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


# --- suggestions before typing (decision 0017, block F) ---------------------------------


def test_validate_suggests_the_number_prefix_for_the_department(api):
    from datetime import date

    result = validate(api, department="PWR")
    assert result["suggest"] == {"design_number_prefix": f"HL-PWR-{date.today().year % 100:02d}-"}
    assert "suggest" not in validate(api, department="XX")


def test_validate_suggests_the_next_free_revision(api):
    result = validate(api, department="HW", design_number="HL-HW-26-0042")
    assert result["suggest"]["revision"] == result["next_free_revision"] == "C"


@pytest.mark.parametrize(("lang", "header"), [("es", "ES"), (None, "EN")])
def test_confirm_asks_sap_in_the_ui_language(api, fake_sap, lang, header):
    # Decision 0027: SAP's refusal text comes in the language the user reads.
    action = api.post("/api/actions", json={"kind": "create_design", "payload": CREATE}).json()
    fake_sap.requests.clear()

    params = {"lang": lang} if lang else {}
    assert api.post(f"/api/actions/{action['id']}/confirm", params=params).status_code == 200

    assert fake_sap.requests
    assert {r.headers["sap-language"] for r in fake_sap.requests} == {header}


def test_a_sap_refusal_gives_the_ui_its_code_and_text(api, fake_sap):
    fake_sap.maintenance = True
    action = api.post("/api/actions", json={"kind": "create_design", "payload": CREATE}).json()

    response = api.post(f"/api/actions/{action['id']}/confirm", params={"lang": "es"})

    assert response.status_code == 502
    result = response.json()["result"]
    assert result["error_kind"] == "sap_unavailable"
    assert result["params"] == {
        "sap_code": "ZHL_GW/003",
        "detail": "SAP system is in maintenance; try again later",
    }


def test_pcb_preview_serves_the_board(api):
    """Decision 0033: the board's PDF and SVG, apart from the schematic's."""
    action = api.post("/api/actions", json={"kind": "create_design", "payload": CREATE}).json()
    api.post(f"/api/actions/{action['id']}/confirm")

    pdf = api.get("/api/designs/HW/HL-HW-26-0042/C/pcb.pdf")
    svg = api.get("/api/designs/HW/HL-HW-26-0042/C/pcb.svg")
    schematic = api.get("/api/designs/HW/HL-HW-26-0042/C/preview.svg")

    assert pdf.status_code == 200 and pdf.content.endswith(b"pcb")
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml"
    assert b'id="pcb"' in svg.content
    assert b'id="pcb"' not in schematic.content


@pytest.mark.parametrize(
    "path",
    [
        "/api/designs/HW/HL-HW-26-0042/Z/pcb.pdf",
        "/api/designs/HW/HL-HW-26-0042/C/pcb.png",
        "/api/designs/..%2F..%2Fx/HL-HW-26-0042/C/pcb.svg",
    ],
)
def test_pcb_preview_refuses_unknown_and_unsafe_paths(api, path):
    assert api.get(path).status_code in {404, 422}
