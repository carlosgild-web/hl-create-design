"""Reading the OData service: payload shape, lookups, $filter/$top/$skip, $metadata, 404."""

from datetime import date
from xml.etree import ElementTree

import pytest

from app.odata import (
    DEPARTMENT_NOT_FOUND,
    DESIGN_NOT_FOUND,
    INVALID_REQUEST,
    RESOURCE_NOT_FOUND,
    REVISION_NOT_FOUND,
    odata_date,
)
from tests.conftest import assert_sap_error, make_settings, svc


def test_odata_date_is_milliseconds_since_epoch_at_utc_midnight():
    assert odata_date("2025-11-17") == "/Date(1763337600000)/"
    assert odata_date(date(1970, 1, 1)) == "/Date(0)/"


def test_service_document_lists_the_entity_sets(client):
    response = client.get(svc("/"))

    assert response.status_code == 200
    assert response.headers["dataserviceversion"] == "2.0"
    assert response.json() == {"d": {"EntitySets": ["DesignSet", "RevisionSet", "DepartmentSet"]}}
    assert client.get(svc()).json() == response.json()


def test_metadata_is_an_edmx_document(client):
    response = client.get(svc("/$metadata"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    root = ElementTree.fromstring(response.content)
    edm = "{http://schemas.microsoft.com/ado/2008/09/edm}"
    sets = {e.get("Name") for e in root.iter(f"{edm}EntitySet")}
    assert sets == {"DesignSet", "RevisionSet", "DepartmentSet"}
    design = next(e for e in root.iter(f"{edm}EntityType") if e.get("Name") == "Design")
    properties = {p.get("Name") for p in design.iter(f"{edm}Property")}
    entity = client.get(svc("/DesignSet('HL-HW-24-0007')")).json()["d"]
    assert properties == set(entity) - {"__metadata", "Revisions"}


# --- one design ------------------------------------------------------------------------


def test_get_design_returns_the_entity_in_odata_v2_shape(client, seed_designs):
    seed = next(d for d in seed_designs if d["design_number"] == "HL-HW-24-0007")

    response = client.get(svc("/DesignSet('HL-HW-24-0007')?$format=json"))

    assert response.status_code == 200
    d = response.json()["d"]
    uri = "http://testserver" + svc("/DesignSet('HL-HW-24-0007')")
    assert d["__metadata"] == {"id": uri, "uri": uri, "type": "ZHL_PLM_DESIGN_SRV.Design"}
    assert d["DesignNumber"] == "HL-HW-24-0007"
    assert d["Department"] == "HW"
    assert d["Name"] == seed["name"]
    assert d["Status"] == "IN_WORK"
    assert d["Material"] == seed["material"] and len(d["Material"]) == 18
    assert d["Wbs"] == seed["wbs"]
    assert d["CurrentRevision"] == "H"  # the next revision skips I (02-revisions)
    assert d["CreatedOn"] == odata_date(seed["created_on"])
    assert d["CreatedBy"] == seed["created_by"]
    assert d["BlockReason"] == "" and d["Successor"] == ""
    assert d["Revisions"] == {"__deferred": {"uri": uri + "/Revisions"}}


def test_url_encoded_key_quotes_work(client):
    response = client.get(svc("/DesignSet(%27HL-HW-24-0007%27)"))

    assert response.status_code == 200
    assert response.json()["d"]["DesignNumber"] == "HL-HW-24-0007"


def test_expand_revisions_inlines_them_oldest_first(client, seed_designs):
    seed = next(d for d in seed_designs if d["design_number"] == "HL-HW-24-0007")

    d = client.get(svc("/DesignSet('HL-HW-24-0007')?$expand=Revisions")).json()["d"]

    revisions = d["Revisions"]["results"]
    assert [r["Revision"] for r in revisions] == [r["rev"] for r in seed["revisions"]]
    first = revisions[0]
    assert first["__metadata"]["type"] == "ZHL_PLM_DESIGN_SRV.Revision"
    assert first["CreatedOn"] == odata_date(seed["revisions"][0]["created_on"])
    assert first["CreatedBy"] == seed["revisions"][0]["created_by"]


def test_revisions_navigation_matches_expand(client):
    expanded = client.get(svc("/DesignSet('HL-HW-24-0007')?$expand=Revisions")).json()
    navigated = client.get(svc("/DesignSet('HL-HW-24-0007')/Revisions")).json()

    assert navigated["d"]["results"] == expanded["d"]["Revisions"]["results"]


def test_revision_by_key_follows_its_metadata_uri(client):
    revisions = client.get(svc("/DesignSet('HL-HW-24-0007')/Revisions")).json()["d"]["results"]
    uri = revisions[1]["__metadata"]["uri"]

    response = client.get(uri)

    assert response.status_code == 200
    assert response.json()["d"]["Revision"] == "B"


def test_blocked_and_obsolete_designs_carry_reason_and_successor(client, seed_designs):
    for seed in seed_designs:
        if seed["status"] not in ("BLOCKED", "OBSOLETE"):
            continue
        d = client.get(svc(f"/DesignSet('{seed['design_number']}')")).json()["d"]
        assert d["Status"] == seed["status"]
        assert d["BlockReason"] == (seed["block_reason"] or "")
        assert d["Successor"] == (seed["successor"] or "")


def test_unknown_design_is_404_with_sap_error_body(client):
    error = assert_sap_error(client.get(svc("/DesignSet('HL-HW-26-9999')")), 404, DESIGN_NOT_FOUND)
    assert "HL-HW-26-9999" in error["message"]["value"]
    assert_sap_error(
        client.get(svc("/DesignSet('HL-HW-26-9999')/Revisions")), 404, DESIGN_NOT_FOUND
    )


def test_unknown_revision_is_404(client):
    response = client.get(svc("/RevisionSet(DesignNumber='HL-HW-24-0007',Revision='Z')"))

    assert_sap_error(response, 404, REVISION_NOT_FOUND)


def test_unknown_entity_set_is_404_with_sap_error_body(client):
    assert_sap_error(client.get(svc("/MaterialSet")), 404, RESOURCE_NOT_FOUND)


# --- collections -----------------------------------------------------------------------


def test_design_set_lists_all_designs_ordered_by_number(client, seed_designs):
    results = client.get(svc("/DesignSet")).json()["d"]["results"]

    numbers = [d["DesignNumber"] for d in results]
    assert numbers == sorted(d["design_number"] for d in seed_designs)


def test_filter_by_department(client, seed_designs):
    response = client.get(svc("/DesignSet?$filter=Department eq 'HW'&$format=json"))

    numbers = {d["DesignNumber"] for d in response.json()["d"]["results"]}
    assert numbers == {d["design_number"] for d in seed_designs if d["department"] == "HW"}


def test_filter_by_department_and_status(client, seed_designs):
    response = client.get(svc("/DesignSet?$filter=Department eq 'EMB' and Status eq 'RELEASED'"))

    numbers = {d["DesignNumber"] for d in response.json()["d"]["results"]}
    expected = {
        d["design_number"]
        for d in seed_designs
        if d["department"] == "EMB" and d["status"] == "RELEASED"
    }
    assert numbers == expected and numbers


def test_filter_with_no_match_is_an_empty_list(client):
    response = client.get(svc("/DesignSet?$filter=DesignNumber eq 'HL-HW-26-9999'"))

    assert response.status_code == 200
    assert response.json() == {"d": {"results": []}}


def test_top_and_skip_page_through_the_results(client):
    everything = client.get(svc("/DesignSet?$filter=Department eq 'HW'")).json()["d"]["results"]

    page = client.get(svc("/DesignSet?$filter=Department eq 'HW'&$top=3&$skip=2")).json()

    assert page["d"]["results"] == everything[2:5]
    assert client.get(svc("/DesignSet?$top=0")).json() == {"d": {"results": []}}


def test_expand_on_the_collection(client):
    results = client.get(svc("/DesignSet?$top=2&$expand=Revisions")).json()["d"]["results"]

    assert all(d["Revisions"]["results"] for d in results)


@pytest.mark.parametrize(
    "query",
    [
        "$filter=Name eq 'Bead Drill Controller'",  # not a filterable property
        "$filter=Department ne 'HW'",  # only eq
        "$filter=Department eq HW",  # unquoted literal
        "$filter=Department eq 'HW' or Department eq 'PWR'",  # only and
        "$filter=Department eq 'HW' and Department eq 'PWR'",  # same property twice
        "$filter=substringof('Drill', Name)",
        "$top=-1",
        "$top=ten",
        "$format=xml",
        "$expand=Material",
    ],
)
def test_unsupported_query_options_are_400(client, query):
    assert_sap_error(client.get(svc(f"/DesignSet?{query}")), 400, INVALID_REQUEST)


# --- departments -----------------------------------------------------------------------


def test_department_set_has_the_four_departments_with_this_years_wbs(client):
    results = client.get(svc("/DepartmentSet")).json()["d"]["results"]

    assert [d["Code"] for d in results] == ["HW", "PWR", "EMB", "TFX"]
    hw = results[0]
    assert hw["NameEn"] == "Hardware Design"
    assert hw["NameEs"] == "Diseño de Hardware"
    assert hw["Lead"] == "E. Marín"
    assert hw["DefaultWbs"] == "P-26-0108"  # SAP_TODAY is in 2026
    assert hw["__metadata"]["type"] == "ZHL_PLM_DESIGN_SRV.Department"


def test_department_by_key(client):
    d = client.get(svc("/DepartmentSet('PWR')")).json()["d"]

    assert d["Code"] == "PWR"
    assert d["DefaultWbs"] == "P-26-0112"


def test_department_wbs_is_empty_in_a_year_without_a_default_project(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_today=date(2027, 1, 4)))

    assert client.get(svc("/DepartmentSet('HW')")).json()["d"]["DefaultWbs"] == ""


def test_unknown_department_is_404(client):
    assert_sap_error(client.get(svc("/DepartmentSet('MECH')")), 404, DEPARTMENT_NOT_FOUND)
