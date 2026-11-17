"""kicad-cli runner: commands, timeouts and failures, with a fake runner (no KiCad)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.evals.fake_kicad import FakeKicadCli  # noqa: F401 (other tests import it from here)
from app.kicad.exporter import ExportError, export_schematic


def test_exports_pdf_and_svg(tmp_path):
    schematic = tmp_path / "HL-HW-26-0042_A.kicad_sch"
    fake = FakeKicadCli()

    result = export_schematic(schematic, tmp_path / "output", kicad_cli="kicad-cli", runner=fake)

    assert result.pdf == tmp_path / "output" / "HL-HW-26-0042_A.pdf"
    assert [p.name for p in result.svgs] == ["HL-HW-26-0042_A.svg"]
    assert fake.commands[0][:4] == ["kicad-cli", "sch", "export", "pdf"]
    assert fake.commands[1][:4] == ["kicad-cli", "sch", "export", "svg"]
    assert "Plotted." in result.log


def test_missing_kicad_cli_explains_the_setting(tmp_path):
    fake = FakeKicadCli(raises=FileNotFoundError())
    with pytest.raises(ExportError, match="set KICAD_CLI"):
        export_schematic(tmp_path / "x.kicad_sch", tmp_path, kicad_cli="nope", runner=fake)


def test_timeout(tmp_path):
    fake = FakeKicadCli(raises=subprocess.TimeoutExpired("kicad-cli", 5, output=b"half"))
    with pytest.raises(ExportError, match="timed out") as caught:
        export_schematic(
            tmp_path / "x.kicad_sch", tmp_path, kicad_cli="k", runner=fake, timeout_s=5
        )
    assert caught.value.log == "half"


def test_failure_keeps_the_log(tmp_path):
    fake = FakeKicadCli(returncode=3)
    with pytest.raises(ExportError, match="exit code 3") as caught:
        export_schematic(tmp_path / "x.kicad_sch", tmp_path, kicad_cli="k", runner=fake)
    assert caught.value.log == "Plotted."
    assert caught.value.command[0] == "k"


def test_success_without_files_is_a_failure(tmp_path):
    fake = FakeKicadCli(write_files=False)
    with pytest.raises(ExportError, match="no PDF"):
        export_schematic(tmp_path / "x.kicad_sch", tmp_path, kicad_cli="k", runner=fake)


@pytest.mark.kicad
def test_real_kicad_cli_exports_the_template(tmp_path):
    """Runs only where kicad-cli is installed (the KiCad container CI job)."""
    from app.core.config import REPO_ROOT

    cli = get_settings().kicad_cli
    if not shutil.which(cli) and not Path(cli).is_file():
        pytest.skip(f"kicad-cli not available at {cli}")
    template = REPO_ROOT / "kicad" / "template"
    for name in ("hl_template.kicad_pro", "hl_template.kicad_sch", "hl_title_block.kicad_wks"):
        shutil.copyfile(template / name, tmp_path / name)

    result = export_schematic(
        tmp_path / "hl_template.kicad_sch", tmp_path / "output", kicad_cli=cli
    )

    assert result.pdf.read_bytes().startswith(b"%PDF")
    assert result.svgs
