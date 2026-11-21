"""Error texts in the caller's logon language (`sap-language`, decision 0027)."""

import re

import pytest

from app.messages import MESSAGES, text
from tests.conftest import assert_sap_error, fetch_token, make_settings, svc

BLOCKED = "HL-HW-24-0015"


def add(client, token, number, rev, **headers):
    body = {"DesignNumber": number, "Revision": rev, "CreatedBy": "C. Velazquez"}
    return client.post(svc("/RevisionSet"), json=body, headers={"x-csrf-token": token, **headers})


@pytest.mark.parametrize("code", sorted(MESSAGES))
def test_every_text_has_english_and_spanish_with_the_same_parameters(code):
    fields = {lang: set(re.findall(r"{(\w+)}", MESSAGES[code][lang])) for lang in ("en", "es")}
    assert fields["en"] == fields["es"]


@pytest.mark.parametrize(
    ("headers", "query", "lang"),
    [
        ({"sap-language": "ES"}, "", "es"),
        ({"sap-language": "S"}, "", "es"),
        ({}, "?sap-language=es", "es"),
        ({"accept-language": "es-ES,es;q=0.9"}, "", "es"),
        ({"sap-language": "EN", "accept-language": "es"}, "", "en"),
        ({}, "", "en"),
    ],
)
def test_the_logon_language_comes_from_sap_language_then_accept_language(
    client, headers, query, lang
):
    response = client.get(svc(f"/DesignSet('HL-HW-26-0999'){query}"), headers=headers)

    error = assert_sap_error(response, 404, "ZHL_PLM/001", lang)
    assert error["message"]["value"] == text("ZHL_PLM/001", lang, {"design": "HL-HW-26-0999"})


def test_a_refused_revision_answers_in_spanish(client):
    response = add(client, fetch_token(client), BLOCKED, "C", **{"sap-language": "ES"})

    error = assert_sap_error(response, 400, "ZHL_PLM/020", "es")
    assert error["message"]["value"] == (
        f"El diseño {BLOCKED} está en BLOCKED; no se permiten revisiones nuevas"
    )
    assert error["innererror"]["errordetails"][0]["message"] == error["message"]["value"]


def test_maintenance_answers_in_spanish(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_maintenance=True))

    response = client.get(svc("/DesignSet"), headers={"sap-language": "ES"})

    error = assert_sap_error(response, 503, "ZHL_GW/003", "es")
    assert "mantenimiento" in error["message"]["value"]


def test_a_technical_error_stays_in_english(client):
    response = client.get(svc("/DesignSet?$format=xml"), headers={"sap-language": "ES"})

    assert_sap_error(response, 400, "ZHL_GW/005", "en")
