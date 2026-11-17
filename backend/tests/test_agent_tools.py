"""The agent's tools: read tools explain, gated tools only open cards."""

import json

import pytest

from app.agent.tools import ToolContext, ToolRegistry
from app.db import store
from app.llm.base import ToolCall


@pytest.fixture
def ctx(settings, engine, sap, manual):
    conversation = store.create_conversation(engine)
    return ToolContext(
        settings=settings, sap=sap, manual=manual, engine=engine, conversation_id=conversation
    )


@pytest.fixture
def registry():
    return ToolRegistry()


def run(registry, ctx, tool, /, **arguments):
    return registry.execute(ToolCall("t1", tool, arguments), ctx)


def test_specs_are_plain_json_schemas(registry):
    specs = {s.name: s for s in registry.specs}
    assert set(specs) == {
        "search_design_manual",
        "validate_design_request",
        "sap_get_design",
        "sap_list_departments",
        "check_design_folder",
        "propose_form_values",
        "request_reserve_number",
        "request_create_design",
    }
    schema = specs["request_create_design"].parameters
    assert schema["type"] == "object"
    assert set(schema["required"]) == {
        "department",
        "design_number",
        "revision",
        "name",
        "designer",
    }
    assert all("anyOf" not in p and "title" not in p for p in schema["properties"].values())


def test_search_manual_returns_citable_passages(registry, ctx):
    result = run(registry, ctx, "search_design_manual", query="skipped letters revision")
    sources = [p["source"] for p in result.content["passages"]]
    assert "02-revisions#skipped-letters" in sources
    json.loads(result.for_model())  # the model gets valid JSON


def test_validate_reports_only_given_fields_and_lists_missing(registry, ctx):
    result = run(registry, ctx, "validate_design_request", department="HW", revision="I")

    content = result.content
    assert content["ok"] is False
    assert [e["code"] for e in content["errors"]] == ["rev_skipped_letter"]
    assert content["errors"][0]["ref"] == "02-revisions#skipped-letters"
    assert content["missing"] == ["design_number", "name", "designer"]


def test_validate_uses_the_sap_revisions(registry, ctx):
    result = run(
        registry,
        ctx,
        "validate_design_request",
        department="HW",
        design_number="HL-HW-26-0042",
        revision="B",
    )
    assert [e["code"] for e in result.content["errors"]] == ["rev_reused"]
    assert result.content["next_free_revision"] == "C"
    assert result.content["sap"]["status"] == "IN_WORK"


def test_validate_blocked_design_is_an_error_with_reason(registry, ctx):
    result = run(
        registry,
        ctx,
        "validate_design_request",
        department="HW",
        design_number="HL-HW-24-0003",
        revision="C",
    )
    [error] = result.content["errors"]
    assert error["code"] == "status_blocked"
    assert "Supplier part discontinued" in error["message"]


def test_validate_unknown_number_must_come_from_sap(registry, ctx):
    result = run(registry, ctx, "validate_design_request", design_number="HL-HW-26-0999")
    assert [e["code"] for e in result.content["errors"]] == ["number_not_in_sap"]


def test_validate_with_sap_down_still_checks_the_rules(registry, ctx, fake_sap):
    fake_sap.maintenance = True
    result = run(
        registry, ctx, "validate_design_request", design_number="HL-HW-26-0042", revision="Q"
    )
    assert result.content["sap_unavailable"]["ref"] == "06-sap-statuses#sap-unavailable"
    assert [e["code"] for e in result.content["errors"]] == ["rev_skipped_letter"]


def test_sap_get_design_explains_obsolete(registry, ctx):
    result = run(registry, ctx, "sap_get_design", design_number="HL-EMB-23-0002")
    assert result.content["new_revision_allowed"] is False
    assert "HL-EMB-25-0011" in result.content["status_notes"][0]["message"]


def test_sap_get_design_rejects_a_malformed_number_without_calling_sap(registry, ctx, fake_sap):
    result = run(registry, ctx, "sap_get_design", design_number="HW-42")
    assert result.content["found"] is False
    assert fake_sap.requests == []


def test_check_folder_refuses_path_tricks(registry, ctx):
    result = run(
        registry, ctx, "check_design_folder", department="..", design_number="HL-HW-26-0042"
    )
    assert result.content["inside_root"] is False


def test_check_folder_reports_the_next_revision_on_disk(registry, ctx, settings):
    (settings.designs_root / "HW" / "HL-HW-26-0042" / "A").mkdir(parents=True)
    result = run(
        registry, ctx, "check_design_folder", department="HW", design_number="HL-HW-26-0042"
    )
    assert result.content["revisions_on_disk"] == ["A"]
    assert result.content["folder"] == "HW/HL-HW-26-0042/B"
    assert result.content["exists"] is False


def test_propose_form_values_is_a_ui_event(registry, ctx):
    result = run(registry, ctx, "propose_form_values", department="HW", name="Bead Counter")
    assert result.event == {
        "type": "form_proposal",
        "fields": {"department": "HW", "name": "Bead Counter"},
    }


def test_reserve_opens_a_card_and_calls_no_sap(registry, ctx, fake_sap, engine):
    result = run(
        registry,
        ctx,
        "request_reserve_number",
        department="HW",
        name="bead counter",
        designer="C. Velazquez",
    )

    assert result.content["status"] == "pending_confirmation"
    action = store.get_action(engine, result.content["action_id"])
    assert action.status == "pending"
    assert action.payload == {
        "department": "HW",
        "name": "Bead Counter",
        "designer": "C. Velazquez",
    }
    assert fake_sap.posts == []


def test_create_opens_a_card_with_sap_values_and_writes_nothing(registry, ctx, settings):
    result = run(
        registry,
        ctx,
        "request_create_design",
        department="HW",
        design_number="HL-HW-26-0042",
        revision="C",
        name="Bead Drill Controller",
        designer="C. Velazquez",
    )
    payload = result.content["values"]
    assert payload["sap_material"] == "000000000040001234"
    assert payload["project"] == "P-26-0108"
    assert result.event["type"] == "pending_action"
    assert not settings.designs_root.exists()


def test_create_with_errors_opens_no_card(registry, ctx, engine):
    result = run(
        registry,
        ctx,
        "request_create_design",
        department="HW",
        design_number="HL-HW-26-0042",
        revision="A",
        name="Bead Drill Controller",
        designer="C. Velazquez",
    )
    assert result.content["ok"] is False
    assert result.event is None
    assert store.list_actions(engine, ctx.conversation_id) == []


def test_only_one_card_per_kind_per_run(registry, ctx, engine):
    args = {"department": "HW", "name": "Bead Counter", "designer": "C. Velazquez"}
    first = run(registry, ctx, "request_reserve_number", **args)
    second = run(registry, ctx, "request_reserve_number", **args)

    assert first.ok and not second.ok
    assert second.content["error"]["code"] == "card_already_open"
    assert len(store.list_actions(engine, ctx.conversation_id)) == 1


def test_bad_arguments_and_unknown_tools_are_errors_for_the_model(registry, ctx):
    assert run(registry, ctx, "rm_rf").content["error"]["code"] == "unknown_tool"
    assert run(registry, ctx, "sap_get_design").content["error"]["code"] == "invalid_arguments"
    invalid = registry.execute(ToolCall("t", "sap_get_design", {"__invalid__": "{"}), ctx)
    assert invalid.content["error"]["code"] == "invalid_arguments"
    too_long = run(registry, ctx, "search_design_manual", query="x" * 500)
    assert too_long.content["error"]["code"] == "invalid_arguments"
