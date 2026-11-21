"""`GET /api/manual/...`: one indexed passage, read-only (decision 0026)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def api():
    return TestClient(app)


def test_a_cited_passage_is_served_in_both_languages(api):
    en = api.get("/api/manual/en/02-revisions/skipped-letters").json()
    assert en["source"] == "02-revisions#skipped-letters" and en["lang"] == "en"
    assert "I" in en["text"] and en["heading"]
    es = api.get("/api/manual/es/02-revisions/skipped-letters").json()
    assert es["lang"] == "es" and es["heading"] != en["heading"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/manual/en/02-revisions/no-such-anchor",
        "/api/manual/en/..%2F..%2Fbackend/app",
        "/api/manual/en/../../.env",
    ],
)
def test_only_indexed_passages_are_served(api, path):
    assert api.get(path).status_code == 404


def test_unknown_language_is_refused(api):
    assert api.get("/api/manual/fr/02-revisions/skipped-letters").status_code == 422
