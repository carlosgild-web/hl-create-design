"""Finding kicad-cli when KICAD_CLI is the bare default, and the KiCad status (decision 0035)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import cli
from app.api import deps
from app.core.config import Settings
from app.kicad.locate import KICAD_DOWNLOAD_URL, resolve_kicad_cli
from app.main import app
from tests.test_open_design import fake_install

WIN_ENV = {"ProgramFiles": r"C:\Program Files", "LOCALAPPDATA": r"C:\Users\ana\AppData\Local"}


def never(_: str) -> None:
    return None


def only(*paths: Path):
    return lambda path: path in paths


def test_kicad_cli_on_the_path_is_kept():
    assert resolve_kicad_cli("kicad-cli", which=lambda _: "/usr/bin/kicad-cli") == "kicad-cli"


def test_windows_all_users_install_is_found():
    found = Path(r"C:\Program Files") / "KiCad" / "9.0" / "bin" / "kicad-cli.exe"
    resolved = resolve_kicad_cli(
        "kicad-cli", env=WIN_ENV, platform="win32", which=never, is_file=only(found)
    )
    assert resolved == str(found)


def test_windows_per_user_install_is_found():
    """winget and the per-user installer: what the downloaded copy missed."""
    found = Path(WIN_ENV["LOCALAPPDATA"]) / "Programs/KiCad" / "9.0" / "bin" / "kicad-cli.exe"
    resolved = resolve_kicad_cli(
        "kicad-cli", env=WIN_ENV, platform="win32", which=never, is_file=only(found)
    )
    assert resolved == str(found)


def test_macos_app_bundle_is_found():
    found = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
    resolved = resolve_kicad_cli("kicad-cli", platform="darwin", which=never, is_file=only(found))
    assert resolved == str(found)


def test_nothing_installed_keeps_the_default():
    resolved = resolve_kicad_cli(
        "kicad-cli", env=WIN_ENV, platform="win32", which=never, is_file=lambda _: False
    )
    assert resolved == "kicad-cli"


def test_an_explicit_path_is_never_replaced_by_a_guess():
    resolved = resolve_kicad_cli(
        r"D:\tools\kicad-cli.exe",
        env=WIN_ENV,
        platform="win32",
        which=never,
        is_file=lambda _: True,
    )
    assert resolved == r"D:\tools\kicad-cli.exe"


def test_settings_can_turn_the_search_off():
    assert Settings(_env_file=None, kicad_autodetect=False).kicad_cli == "kicad-cli"


def status(settings) -> dict:
    app.dependency_overrides[deps.settings_dep] = lambda: settings
    try:
        return TestClient(app).get("/api/kicad").json()
    finally:
        app.dependency_overrides.clear()


def test_status_without_kicad_says_what_is_missing(settings):
    settings.kicad_cli = "no-such-kicad-cli"

    body = status(settings)

    assert body["found"] is False and body["can_export"] is False
    assert body["can_open"] is False and body["can_open_pcb"] is False
    assert body["download_url"] == KICAD_DOWNLOAD_URL


def test_status_with_kicad(settings, tmp_path, monkeypatch):
    settings.kicad_cli = fake_install(tmp_path, editor=True)
    monkeypatch.setattr("app.kicad.locate.kicad_version", lambda _: "9.0.8")

    body = status(settings)

    assert body["found"] is True and body["version"] == "9.0.8"
    assert body["can_export"] and body["can_open"] and body["can_open_pcb"]
    assert Path(body["path"]) == Path(settings.kicad_cli)


def test_status_respects_open_turned_off(settings, tmp_path, monkeypatch):
    settings.kicad_cli = fake_install(tmp_path, editor=True)
    settings.kicad_open_enabled = False
    monkeypatch.setattr("app.kicad.locate.kicad_version", lambda _: "9.0.8")

    body = status(settings)

    assert body["can_export"] is True and body["can_open"] is False


def test_kicad_check_explains_what_needs_kicad(settings, capsys):
    settings.kicad_cli = "no-such-kicad-cli"

    assert cli.main(["kicad-check"], settings) == 0

    out = capsys.readouterr().out
    assert "KiCad 9 was not found." in out
    assert "Open PCB" in out and KICAD_DOWNLOAD_URL in out
    assert "KICAD_CLI is set to no-such-kicad-cli" in out


def test_kicad_check_names_the_kicad_it_found(settings, tmp_path, capsys, monkeypatch):
    settings.kicad_cli = fake_install(tmp_path, editor=True)
    monkeypatch.setattr("app.kicad.locate.kicad_version", lambda _: "9.0.8")

    assert cli.main(["kicad-check"], settings) == 0

    assert "KiCad 9.0.8 found:" in capsys.readouterr().out
