"""The confirmation gate: confirm once, expiry, cancel, re-validation, audit."""

from datetime import timedelta

import pytest

from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
from app.db import store
from app.db.models import utcnow
from app.db.session import audit_rows
from tests.test_exporter import FakeKicadCli


@pytest.fixture
def conversation(engine):
    return store.create_conversation(engine)


def open_action(engine, conversation, kind, **payload):
    return store.create_action(
        engine, conversation_id=conversation, run_id=None, kind=kind, payload=payload
    )


def confirm(action_id, settings, engine, sap, **kw):
    return confirm_action(
        action_id, settings=settings, engine=engine, sap=sap, runner=FakeKicadCli(), **kw
    )


CREATE = {
    "department": "HW",
    "design_number": "HL-HW-26-0042",
    "revision": "C",
    "name": "Bead Drill Controller",
    "designer": "C. Velazquez",
}


def test_reserve_runs_once_and_is_audited(settings, engine, sap, fake_sap, conversation):
    action = open_action(
        engine,
        conversation,
        "reserve_number",
        department="HW",
        name="Bead Counter",
        designer="C. Velazquez",
    )

    outcome = confirm(action.id, settings, engine, sap)

    assert outcome.ok
    assert outcome.action.status == "confirmed"
    assert outcome.action.result["design_number"] == "HL-HW-26-0050"
    [row] = audit_rows(engine)
    assert (row.action, row.design_number, row.revision) == (
        "number_reserved",
        "HL-HW-26-0050",
        "A",
    )
    with pytest.raises(ActionNotPending) as again:
        confirm(action.id, settings, engine, sap)
    assert again.value.reason == "already_confirmed"
    assert len(fake_sap.reservations) == 1


def test_create_uses_sap_values_and_writes_the_files(settings, engine, sap, conversation):
    action = open_action(engine, conversation, "create_design", **CREATE)

    outcome = confirm(action.id, settings, engine, sap)

    assert outcome.ok, outcome.action.result
    result = outcome.action.result
    assert result["folder"] == "HW/HL-HW-26-0042/C"
    assert result["sap_material"] == "000000000040001234"
    folder = settings.designs_root / "HW" / "HL-HW-26-0042" / "C"
    assert (folder / "HL-HW-26-0042_C.kicad_pro").exists()
    [row] = audit_rows(engine)
    assert row.details["action_id"] == action.id
    assert row.details["sap_status"] == "IN_WORK"


def test_confirm_validates_again(settings, engine, sap, conversation, fake_sap):
    # The card said C, but meanwhile revision C was created in SAP.
    action = open_action(engine, conversation, "create_design", **CREATE)
    fake_sap.designs["HL-HW-26-0042"]["_revs"].append("C")

    outcome = confirm(action.id, settings, engine, sap)

    assert not outcome.ok
    assert outcome.error_kind == "validation"
    assert outcome.action.result["errors"][0]["code"] == "rev_reused"
    assert not settings.designs_root.exists()
    assert audit_rows(engine) == []


def test_tampered_payload_cant_escape_the_designs_root(settings, engine, sap, conversation):
    payload = CREATE | {"department": "..", "design_number": "../../etc"}
    action = open_action(engine, conversation, "create_design", **payload)

    outcome = confirm(action.id, settings, engine, sap)

    assert outcome.error_kind == "validation"
    assert not settings.designs_root.exists()


def test_blocked_design_cant_be_created(settings, engine, sap, conversation):
    payload = CREATE | {"design_number": "HL-HW-24-0003", "name": "Old Led Panel"}
    outcome = confirm(
        open_action(engine, conversation, "create_design", **payload).id, settings, engine, sap
    )
    assert [e["code"] for e in outcome.action.result["errors"]] == ["status_blocked"]


# --- new revision of an existing design (decision 0018) ---------------------------------


def test_a_name_other_than_sap_is_refused_at_confirm(settings, engine, sap, conversation):
    payload = CREATE | {"name": "Other Name"}
    outcome = confirm(
        open_action(engine, conversation, "create_design", **payload).id, settings, engine, sap
    )
    [error] = outcome.action.result["errors"]
    assert error["code"] == "name_differs_from_sap"
    assert (
        error["ref"] == "03-title-block#name-from-sap"
        and "Bead Drill Controller" in error["message"]
    )
    assert not (settings.designs_root / "HW" / "HL-HW-26-0042" / "C").exists()


def test_an_obsolete_design_is_refused_even_if_the_ui_is_bypassed(
    settings, engine, sap, conversation
):
    payload = CREATE | {
        "department": "EMB",
        "design_number": "HL-EMB-23-0002",
        "name": "Sensor Hub",
        "revision": "B",
    }
    outcome = confirm(
        open_action(engine, conversation, "create_design", **payload).id, settings, engine, sap
    )
    assert "status_obsolete" in [e["code"] for e in outcome.action.result["errors"]]
    assert not (settings.designs_root / "EMB").exists()


def test_new_revision_of_an_existing_design_uses_sap_name_and_is_audited(
    settings, engine, sap, conversation
):
    payload = CREATE | {"name": "bead  drill controller"}  # same name, other formatting
    outcome = confirm(
        open_action(engine, conversation, "create_design", **payload).id, settings, engine, sap
    )
    assert outcome.ok, outcome.action.result
    folder = settings.designs_root / "HW" / "HL-HW-26-0042" / "C"
    assert folder.is_dir()
    schematic = "".join(p.read_text(encoding="utf-8") for p in folder.rglob("*.kicad_sch"))
    assert '(title "Bead Drill Controller")' in schematic
    [row] = [r for r in audit_rows(engine) if r.action == "design_created"]
    assert (row.design_number, row.revision) == ("HL-HW-26-0042", "C")
    assert row.details["name"] == "Bead Drill Controller"


def test_sap_down_does_nothing(settings, engine, sap, fake_sap, conversation):
    fake_sap.maintenance = True
    action = open_action(engine, conversation, "create_design", **CREATE)

    outcome = confirm(action.id, settings, engine, sap)

    assert outcome.error_kind == "sap_unavailable"
    assert outcome.action.status == "failed"
    assert not settings.designs_root.exists()


def test_expired_action_cant_be_confirmed(settings, engine, sap, conversation):
    action = store.create_action(
        engine,
        conversation_id=conversation,
        run_id=None,
        kind="reserve_number",
        payload={"department": "HW", "name": "Bead Counter", "designer": "C. Velazquez"},
        now=utcnow() - store.ACTION_TTL - timedelta(seconds=1),
    )
    with pytest.raises(ActionNotPending) as raised:
        confirm(action.id, settings, engine, sap)
    assert raised.value.reason == "expired"


def test_cancelled_action_cant_be_confirmed(settings, engine, sap, conversation):
    action = open_action(engine, conversation, "create_design", **CREATE)
    assert cancel_action(action.id, engine=engine).status == "cancelled"
    with pytest.raises(ActionNotPending):
        confirm(action.id, settings, engine, sap)


def test_unknown_action(settings, engine, sap):
    with pytest.raises(ActionNotFound):
        confirm("nope", settings, engine, sap)


def test_outcome_is_added_to_the_conversation(settings, engine, sap, conversation):
    action = open_action(engine, conversation, "create_design", **CREATE)
    confirm(action.id, settings, engine, sap)

    [event] = store.get_messages(engine, conversation)
    assert event["role"] == "event"
    assert event["event"]["outcome"] == "done"
    assert event["event"]["folder"] == "HW/HL-HW-26-0042/C"


# --- revisions are recorded in SAP, SAP first (decision 0023, Q3/Q4) --------------------


def test_a_new_revision_is_recorded_in_sap_before_the_folder(
    settings, engine, sap, fake_sap, conversation
):
    action = open_action(engine, conversation, "create_design", **CREATE)

    outcome = confirm(action.id, settings, engine, sap)

    assert outcome.ok, outcome.action.result
    assert fake_sap.revisions_added == [
        {"DesignNumber": "HL-HW-26-0042", "Revision": "C", "CreatedBy": "C. Velazquez"}
    ]
    assert sap.get_design("HL-HW-26-0042").revisions[-1] == "C"
    [row] = audit_rows(engine)
    assert row.details["sap_revision_recorded"] is True


def test_revision_a_of_a_reserved_number_is_not_recorded_again(
    settings, engine, sap, fake_sap, conversation
):
    reserve = open_action(
        engine,
        conversation,
        "reserve_number",
        department="HW",
        name="Bead Counter",
        designer="C. Velazquez",
    )
    number = confirm(reserve.id, settings, engine, sap).action.result["design_number"]
    create = open_action(
        engine,
        conversation,
        "create_design",
        **{**CREATE, "design_number": number, "revision": "A", "name": "Bead Counter"},
    )

    assert confirm(create.id, settings, engine, sap).ok
    assert fake_sap.revisions_added == []


def test_sap_refusing_the_revision_writes_nothing(
    settings, engine, sap, fake_sap, conversation, monkeypatch
):
    from app.sap.client import SapError

    def refuse(*args):
        raise SapError("SAP backend system temporarily unavailable", status=503)

    monkeypatch.setattr(sap, "add_revision", refuse)
    action = open_action(engine, conversation, "create_design", **CREATE)

    outcome = confirm(action.id, settings, engine, sap)

    assert not outcome.ok and outcome.error_kind == "sap_unavailable"
    assert not (settings.designs_root / "HW" / "HL-HW-26-0042" / "C").exists()
    assert audit_rows(engine) == []


def test_an_existing_folder_is_refused_before_sap_is_written(
    settings, engine, sap, fake_sap, conversation, monkeypatch
):
    (settings.designs_root / "HW" / "HL-HW-26-0042" / "C").mkdir(parents=True)
    monkeypatch.setattr(
        "app.designs.v.revisions_on_disk", lambda *a: []
    )  # a race: the scan missed it
    action = open_action(engine, conversation, "create_design", **CREATE)

    outcome = confirm(action.id, settings, engine, sap)

    assert outcome.error_kind == "conflict"
    assert fake_sap.revisions_added == []


def test_a_deleted_revision_folder_never_frees_its_letter(settings, engine, sap, conversation):
    import shutil

    from app.designs import next_free_revision

    action = open_action(engine, conversation, "create_design", **CREATE)
    assert confirm(action.id, settings, engine, sap).ok
    shutil.rmtree(settings.designs_root / "HW" / "HL-HW-26-0042" / "C")  # e.g. the TTL cleanup

    record = sap.get_design("HL-HW-26-0042")
    assert next_free_revision(record, settings.designs_root) == "D"


def test_without_kicad_the_design_is_created_without_a_pdf(settings, engine, sap, conversation):
    def missing(command, **kw):
        raise FileNotFoundError(command[0])

    action = open_action(engine, conversation, "create_design", **CREATE)

    outcome = confirm_action(action.id, settings=settings, engine=engine, sap=sap, runner=missing)

    assert outcome.ok, outcome.action.result
    result = outcome.action.result
    assert result["pdf"] is False and result["folder"] == "HW/HL-HW-26-0042/C"
    [warning] = [w for w in result["warnings"] if w["code"] == "pdf_not_exported"]
    assert warning["params"] == {"variant": "not_installed"}
