"""Basic auth and the CSRF token handshake, as an SAP Gateway does them."""

import base64

import pytest

from app.odata import CSRF_FAILED, LOGON_FAILED
from app.security import SESSION_COOKIE
from tests.conftest import assert_sap_error, fetch_token, reserve, svc


def test_health_needs_no_auth(make_client, settings):
    client = make_client(settings, auth=None)

    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Basic " + base64.b64encode(b"demo:wrong").decode(),
        "Basic " + base64.b64encode(b"admin:demo").decode(),
        "Basic " + base64.b64encode(b"demo").decode(),  # no colon
        "Basic not-base64!",
        "Bearer demo",
    ],
)
def test_service_needs_valid_basic_auth(make_client, settings, authorization):
    client = make_client(settings, auth=None)
    headers = {"authorization": authorization} if authorization else {}

    response = client.get(svc("/DesignSet"), headers=headers)

    assert_sap_error(response, 401, LOGON_FAILED)
    assert response.headers["www-authenticate"].startswith("Basic realm=")


def test_unauthenticated_fetch_gets_no_token(make_client, settings):
    client = make_client(settings, auth=None)

    response = client.get(svc("/"), headers={"x-csrf-token": "Fetch"})

    assert response.status_code == 401
    assert "x-csrf-token" not in response.headers
    assert SESSION_COOKIE not in response.cookies


def test_fetch_returns_a_token_and_a_session_cookie(client):
    response = client.get(svc("/"), headers={"x-csrf-token": "Fetch"})

    assert response.status_code == 200
    assert len(response.headers["x-csrf-token"]) >= 20
    assert SESSION_COOKIE in response.cookies


def test_fetching_again_in_the_same_session_returns_the_same_token(client):
    assert fetch_token(client) == fetch_token(client)


def test_get_without_fetch_returns_no_token(client):
    response = client.get(svc("/DesignSet"))

    assert "x-csrf-token" not in response.headers


def test_post_without_token_is_403_and_asks_for_one(client):
    fetch_token(client)  # a session exists, but the POST doesn't send the token

    response = client.post(svc("/DesignSet"), json={"Department": "HW"})

    assert_sap_error(response, 403, CSRF_FAILED)
    assert response.headers["x-csrf-token"] == "Required"


def test_post_with_a_wrong_token_is_403(client):
    fetch_token(client)

    assert_sap_error(reserve(client, "not-the-token"), 403, CSRF_FAILED)


def test_post_with_fetch_instead_of_a_token_is_403(client):
    fetch_token(client)

    assert_sap_error(reserve(client, "Fetch"), 403, CSRF_FAILED)


def test_token_without_its_session_cookie_is_403(client):
    token = fetch_token(client)
    client.cookies.clear()

    assert_sap_error(reserve(client, token), 403, CSRF_FAILED)


def test_token_from_another_session_is_403(make_client, settings):
    alice = make_client(settings)
    bob = make_client(settings)
    alice_token = fetch_token(alice)
    fetch_token(bob)

    assert_sap_error(reserve(bob, alice_token), 403, CSRF_FAILED)


def test_token_is_rejected_when_the_credentials_change(client):
    token = fetch_token(client)
    client.auth = ("demo", "wrong")

    assert_sap_error(reserve(client, token), 401, LOGON_FAILED)


def test_a_token_works_for_several_posts_in_its_session(client):
    token = fetch_token(client)

    assert reserve(client, token).status_code == 201
    assert reserve(client, token).status_code == 201


def test_tokens_do_not_survive_a_restart(make_client, settings):
    first = make_client(settings)
    token = fetch_token(first)
    restarted = make_client(settings)
    restarted.cookies = first.cookies

    assert_sap_error(reserve(restarted, token), 403, CSRF_FAILED)
