"""The backend for the browser tests: the real app with two stand-ins.

- The model is a scripted `FakeClient`: one chat turn fills the form, looks the design
  up in SAP and opens a confirmation card. No Ollama, no key.
- `kicad-cli` is a stub that writes a small PDF and SVG, so the test needs no KiCad.

SAP is the real mock service (started by Playwright next to this process).
Run: python harness.py   (env: E2E_DATA_DIR, E2E_PORT, SAP_BASE_URL)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data_dir = Path(os.environ.get("E2E_DATA_DIR", ROOT / "e2e" / ".tmp" / "backend"))
shutil.rmtree(data_dir, ignore_errors=True)
os.environ.update(
    DATA_DIR=str(data_dir),
    DESIGNS_ROOT=str(data_dir / "designs"),
    LLM_PROVIDER="fake",
    SAP_BASE_URL=os.environ.get("SAP_BASE_URL", "http://127.0.0.1:8190"),
)
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn  # noqa: E402

from app.api import deps  # noqa: E402
from app.llm.fake import FakeClient, call, say  # noqa: E402
from app.main import app  # noqa: E402

FIELDS = {
    "department": "HW",
    "design_number": "HL-HW-26-0003",
    "revision": "C",
    "name": "Bead Sorter Vision Board",
    "designer": "C. Velazquez",
}

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="297" height="210" viewBox="0 0 297 210">'
    '<rect width="297" height="210" fill="white"/><text x="10" y="20">HL-HW-26-0003 C</text></svg>'
)


def script() -> FakeClient:
    return FakeClient(
        [
            call("propose_form_values", **FIELDS),
            call("sap_get_design", design_number=FIELDS["design_number"]),
            call("request_create_design", **FIELDS),
            say("I filled the form and opened a card. Please confirm it."),
        ]
    )


def stub_kicad_cli(command, **kwargs):
    output, schematic = Path(command[command.index("--output") + 1]), Path(command[-1])
    if command[3] == "pdf":
        output.write_bytes(b"%PDF-1.5 stub")
    else:
        (output / f"{schematic.stem}.svg").write_text(SVG, encoding="utf-8")
    return subprocess.CompletedProcess(command, 0, "Plotted.", "")


app.dependency_overrides[deps.llm_factory_dep] = lambda: script
app.dependency_overrides[deps.runner_dep] = lambda: stub_kicad_cli

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("E2E_PORT", "8191")))
