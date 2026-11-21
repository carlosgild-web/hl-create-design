"""Recording a new revision: only the next free letter, never for BLOCKED/OBSOLETE designs."""

from app.db import next_revision
from tests.conftest import assert_sap_error, fetch_token, svc


def add(client, token, number, rev, created_by="C. Velazquez"):
    body = {"DesignNumber": number, "Revision": rev, "CreatedBy": created_by}
    return client.post(svc("/RevisionSet"), json=body, headers={"x-csrf-token": token})


def test_the_next_revision_is_recorded_and_becomes_current(client):
    response = add(client, fetch_token(client), "HL-HW-26-0003", "C")

    assert response.status_code == 201, response.text
    d = response.json()["d"]
    assert (d["DesignNumber"], d["Revision"], d["CreatedBy"]) == (
        "HL-HW-26-0003",
        "C",
        "C. Velazquez",
    )
    assert response.headers["location"] == d["__metadata"]["uri"]
    design = client.get(svc("/DesignSet('HL-HW-26-0003')?$expand=Revisions")).json()["d"]
    assert design["CurrentRevision"] == "C"
    assert [r["Revision"] for r in design["Revisions"]["results"]] == ["A", "B", "C"]


def test_skipped_letters_are_skipped(client):
    # HL-HW-24-0007 has A..H: the next one is J, never I
    token = fetch_token(client)
    assert_sap_error(add(client, token, "HL-HW-24-0007", "I"), 400, "ZHL_PLM/022")
    assert add(client, token, "HL-HW-24-0007", "J").status_code == 201


def test_a_letter_is_never_recorded_twice_or_out_of_order(client):
    token = fetch_token(client)
    assert_sap_error(add(client, token, "HL-HW-26-0003", "B"), 400, "ZHL_PLM/021")
    error = assert_sap_error(add(client, token, "HL-HW-26-0003", "E"), 400, "ZHL_PLM/022")
    assert "expected C" in error["message"]["value"]


def test_blocked_and_obsolete_designs_get_no_new_revision(client):
    token = fetch_token(client)
    assert_sap_error(add(client, token, "HL-HW-24-0015", "C"), 400, "ZHL_PLM/020")  # BLOCKED
    assert_sap_error(add(client, token, "HL-HW-23-0004", "D"), 400, "ZHL_PLM/020")  # OBSOLETE
    assert add(client, token, "HL-HW-23-0011", "C").status_code == 201  # RELEASED is allowed


def test_unknown_design_is_404_and_csrf_is_required(client):
    assert_sap_error(add(client, fetch_token(client), "HL-HW-26-0999", "B"), 404, "ZHL_PLM/001")
    assert add(client, "wrong-token", "HL-HW-26-0003", "C").status_code == 403


def test_next_revision_runs_past_y_into_two_letters():
    assert next_revision([]) == "A"
    assert next_revision(["A", "B", "C", "D", "E", "F", "G", "H"]) == "J"
    assert next_revision(list("ABCDEFGHJKLMNPRTUVWY")) == "AA"
    assert next_revision([*"ABCDEFGHJKLMNPRTUVWY", "AA", "AB"]) == "AC"
