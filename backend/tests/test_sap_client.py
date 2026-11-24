"""SapClient against the in-memory gateway: payloads, CSRF, retries, errors."""

from datetime import date

import httpx
import pytest

from app.sap.client import SapClient, SapError, parse_odata_date


def test_get_design_parses_the_odata_entity_with_revisions(sap):
    design = sap.get_design("HL-HW-26-0042")

    assert design is not None
    assert design.status == "IN_WORK"
    assert design.material == "000000000040001234"
    assert design.wbs == "P-26-0108"
    assert design.revisions == ("A", "B")
    assert design.created_on == date(2026, 3, 2)


def test_unknown_design_is_none(sap):
    assert sap.get_design("HL-HW-26-9999") is None


def test_list_departments(sap):
    codes = [d.code for d in sap.list_departments()]
    assert codes == ["HW", "PWR", "EMB", "TFX"]


def test_reserve_fetches_a_csrf_token_and_keeps_the_session_cookie(sap, fake_sap):
    design = sap.reserve_number("HW", "Bead Counter", "C. Velazquez")

    assert design.design_number == "HL-HW-26-0050"
    assert design.current_revision == "A"
    fetch, post = fake_sap.requests[-2], fake_sap.requests[-1]
    assert fetch.headers["x-csrf-token"] == "Fetch"
    assert post.headers["x-csrf-token"] != "Fetch"
    assert "SAP_SESSIONID_HLM_100=" in post.headers["cookie"]


def test_expired_token_is_fetched_again_once(sap, fake_sap):
    sap.reserve_number("HW", "First", "C. Velazquez")
    fake_sap.expire_tokens()

    second = sap.reserve_number("HW", "Second", "C. Velazquez")

    assert second.design_number == "HL-HW-26-0051"
    assert len(fake_sap.reservations) == 2


def test_get_is_retried_on_a_backend_503(sap, fake_sap):
    fake_sap.fail_next = 2
    assert sap.get_design("HL-HW-26-0042") is not None


def test_gives_up_after_the_retries(sap, fake_sap):
    fake_sap.fail_next = 5
    with pytest.raises(SapError) as raised:
        sap.get_design("HL-HW-26-0042")
    assert raised.value.unavailable
    assert raised.value.code == "ZHL_GW/004"


def test_maintenance_is_not_retried(sap, fake_sap):
    fake_sap.maintenance = True
    with pytest.raises(SapError) as raised:
        sap.list_departments()
    assert raised.value.unavailable
    assert len(fake_sap.requests) == 1


def test_sap_error_body_becomes_code_and_message(sap):
    with pytest.raises(SapError) as raised:
        sap.reserve_number("XX", "Bead Counter", "C. Velazquez")
    assert raised.value.code == "ZHL_PLM/010"
    assert "XX" in raised.value.message


def test_wrong_password_is_a_logon_error(fake_sap):
    client = SapClient("http://sap.test", "demo", "wrong", transport=httpx.MockTransport(fake_sap))
    with pytest.raises(SapError) as raised:
        client.list_departments()
    assert raised.value.status == 401


def test_post_is_not_repeated_after_a_read_timeout():
    posts = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"d": {}}, headers={"x-csrf-token": "t"})
        posts.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    client = SapClient("http://sap.test", "u", "p", transport=httpx.MockTransport(handler))
    with pytest.raises(SapError) as raised:
        client.reserve_number("HW", "Bead Counter", "C. Velazquez")
    assert "may have been processed" in raised.value.message
    assert len(posts) == 1


def test_unreachable_sap_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = SapClient(
        "http://sap.test", "u", "p", transport=httpx.MockTransport(handler), backoff_s=0
    )
    with pytest.raises(SapError) as raised:
        client.get_design("HL-HW-26-0042")
    assert raised.value.unavailable


def test_parse_odata_date():
    assert parse_odata_date("/Date(1763337600000)/") == date(2025, 11, 17)
    assert parse_odata_date("") is None


# --- list_designs (decision 0018) ---------------------------------------------------------


def test_list_designs_returns_all_with_revisions_ordered_by_number(sap):
    designs = sap.list_designs()
    numbers = [d.design_number for d in designs]
    assert numbers == sorted(numbers) and "HL-HW-26-0042" in numbers
    drill = next(d for d in designs if d.design_number == "HL-HW-26-0042")
    assert drill.revisions == ("A", "B") and drill.name == "Bead Drill Controller"


def test_list_designs_filters_by_department_and_status(sap, fake_sap):
    designs = sap.list_designs(department="HW", status="BLOCKED")
    assert [d.design_number for d in designs] == ["HL-HW-24-0003"]
    assert designs[0].block_reason == "Supplier part discontinued"
    params = fake_sap.requests[-1].url.params
    assert params["$filter"] == "Department eq 'HW' and Status eq 'BLOCKED'"
    assert params["$expand"] == "Revisions"


def test_list_designs_rejects_unknown_filters_before_calling_sap(sap, fake_sap):
    before = len(fake_sap.requests)
    with pytest.raises(ValueError):
        sap.list_designs(department="HW' or 1 eq 1")
    with pytest.raises(ValueError):
        sap.list_designs(status="DELETED")
    assert len(fake_sap.requests) == before


def test_list_designs_when_sap_is_down(sap, fake_sap):
    fake_sap.fail_next = 5
    with pytest.raises(SapError) as err:
        sap.list_designs()
    assert err.value.unavailable
