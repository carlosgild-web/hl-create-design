"""Open in KiCad, the project zip and the file locations (decision 0019)."""

from __future__ import annotations

import io
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.db.session import audit_rows
from app.main import app
from tests.test_designs_api import CREATE
from tests.test_exporter import FakeKicadCli

BASE = "/api/designs/HW/HL-HW-26-0042/C"
EXE = ".exe" if sys.platform == "win32" else ""


def fake_install(tmp_path, gui: bool = True) -> str:
    """A KiCad bin folder: kicad-cli, and the GUI next to it when `gui`."""
    bin_dir = tmp_path / "kicad" / "bin"
    bin_dir.mkdir(parents=True)
    names = [f"kicad-cli{EXE}"] + ([f"kicad{EXE}"] if gui else [])
    for name in names:
        (bin_dir / name).write_bytes(b"")
        (bin_dir / name).chmod(0o755)
    return str(bin_dir / f"kicad-cli{EXE}")


@pytest.fixture
def launched():
    return []


@pytest.fixture
def api(settings, fake_sap, launched, tmp_path):
    settings.kicad_cli = fake_install(tmp_path)
    app.dependency_overrides[deps.settings_dep] = lambda: settings
    app.dependency_overrides[deps.sap_factory_dep] = lambda: fake_sap.client
    app.dependency_overrides[deps.runner_dep] = FakeKicadCli
    app.dependency_overrides[deps.launcher_dep] = lambda: launched.append
    client = TestClient(app)
    action = client.post("/api/actions", json={"kind": "create_design", "payload": CREATE}).json()
    assert client.post(f"/api/actions/{action['id']}/confirm").status_code == 200
    yield client
    app.dependency_overrides.clear()


def test_files_says_where_the_project_is(api, settings):
    files = api.get(f"{BASE}/files").json()
    folder = (settings.designs_root / "HW" / "HL-HW-26-0042" / "C").resolve()
    assert files["folder"] == str(folder)
    assert files["project_file"] == str(folder / "HL-HW-26-0042_C.kicad_pro")
    assert files["can_open"] is True


def test_open_starts_the_gui_with_the_project_and_audits(api, settings, launched):
    response = api.post(f"{BASE}/open")

    assert response.status_code == 200
    [(program, project)] = launched
    assert program.endswith(f"kicad{EXE}") and project.endswith("HL-HW-26-0042_C.kicad_pro")
    opened = [r for r in audit_rows(deps.engine_dep(settings)) if r.action == "design_opened"]
    assert [(r.design_number, r.revision) for r in opened] == [("HL-HW-26-0042", "C")]


def test_open_is_refused_when_turned_off_or_without_a_gui(api, settings, launched, tmp_path):
    settings.kicad_open_enabled = False
    assert api.get(f"{BASE}/files").json()["can_open"] is False
    assert api.post(f"{BASE}/open").status_code == 409

    settings.kicad_open_enabled = True
    settings.kicad_cli = fake_install(tmp_path / "nogui", gui=False)
    assert api.get(f"{BASE}/files").json()["can_open"] is False
    assert api.post(f"{BASE}/open").status_code == 409
    assert launched == []


def test_zip_holds_the_revision_folder(api):
    response = api.get(f"{BASE}/project.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="HL-HW-26-0042_C.zip"' in response.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert "HL-HW-26-0042_C/HL-HW-26-0042_C.kicad_pro" in names
    assert "HL-HW-26-0042_C/output/HL-HW-26-0042_C.pdf" in names


@pytest.mark.parametrize("tail", ["files", "project.zip", "open"])
@pytest.mark.parametrize(
    "design",
    [
        "HW/HL-HW-26-0042/D",  # not created
        "..%2F..%2Fx/HL-HW-26-0042/C",
        "HW/..%5C..%5CWindows/C",
        "C%3A/HL-HW-26-0042/C",
    ],
)
def test_unknown_and_unsafe_designs_are_404(api, launched, design, tail):
    url = f"/api/designs/{design}/{tail}"
    response = api.post(url) if tail == "open" else api.get(url)
    # 405: a decoded `../` no longer matches the route at all; refused either way
    assert response.status_code in {404, 405, 422}
    assert launched == []
