"""The backend serves the built UI at `/` without shadowing the API."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend


def build(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "a.js").write_text("x=1")
    (tmp_path.parent / "secret.txt").write_text("secret")
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, str]:
        return {"ok": "yes"}

    assert mount_frontend(app, tmp_path)
    return TestClient(app)


def test_serves_index_assets_and_spa_fallback(tmp_path):
    client = build(tmp_path)

    assert "app" in client.get("/").text
    assert client.get("/assets/a.js").text == "x=1"
    assert "app" in client.get("/some/client/route").text


def test_api_is_not_shadowed(tmp_path):
    client = build(tmp_path)

    assert client.get("/api/ping").json() == {"ok": "yes"}
    assert client.get("/api/missing").status_code == 404


def test_cannot_read_outside_the_folder(tmp_path):
    client = build(tmp_path)

    assert "secret" not in client.get("/%2e%2e/secret.txt").text
    assert "secret" not in client.get("/..%2fsecret.txt").text


def test_no_build_means_no_mount(tmp_path):
    assert mount_frontend(FastAPI(), tmp_path) is False
