"""Open a created project in the KiCad 9 GUI, and pack a revision folder as a zip.

Opening starts a desktop program on the machine that runs the backend, so it only makes
sense when that machine is the user's own (local mode). It never writes a file or calls
SAP: it is not a side effect behind the confirmation gate (decision 0019), but it still
runs only on the user's click and is audited.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

Launcher = Callable[[list[str]], object]


def _next_to_cli(kicad_cli: str, program: str) -> Path | None:
    """A KiCad program that sits next to `kicad-cli` (same install), or None."""
    found = shutil.which(kicad_cli)
    if found is None:
        return None
    name = f"{program}.exe" if sys.platform == "win32" else program
    path = Path(found).resolve().with_name(name)
    return path if path.is_file() else None


def kicad_gui(kicad_cli: str) -> Path | None:
    """The KiCad Project Manager next to `kicad-cli`, or None."""
    return _next_to_cli(kicad_cli, "kicad")


def kicad_schematic_editor(kicad_cli: str) -> Path | None:
    """KiCad's schematic editor (eeschema) next to `kicad-cli`, or None."""
    return _next_to_cli(kicad_cli, "eeschema")


def kicad_pcb_editor(kicad_cli: str) -> Path | None:
    """KiCad's PCB editor (pcbnew) next to `kicad-cli`, or None."""
    return _next_to_cli(kicad_cli, "pcbnew")


OpenTarget = Literal["schematic", "pcb"]
_EDITORS: dict[str, tuple[Callable[[str], Path | None], str]] = {
    "schematic": (kicad_schematic_editor, ".kicad_sch"),
    "pcb": (kicad_pcb_editor, ".kicad_pcb"),
}


def open_command(
    kicad_cli: str, folder: Path, stem: str, target: OpenTarget = "schematic"
) -> list[str] | None:
    """What "Open in KiCad" (decision 0030) and "Open PCB" (decision 0033) start: the
    schematic or PCB editor with the design's file, so the drawing and its title block are
    on screen at once. Both load the `.kicad_pro` next to the file, so the text variables
    are filled. Without the editor or the file: the Project Manager with the project, as
    before (decision 0019)."""
    find_editor, suffix = _EDITORS[target]
    editor = find_editor(kicad_cli)
    document = folder / f"{stem}{suffix}"
    if editor is not None and document.is_file():
        return [str(editor), str(document)]
    gui = kicad_gui(kicad_cli)
    project = folder / f"{stem}.kicad_pro"
    if gui is not None and project.is_file():
        return [str(gui), str(project)]
    return None


def can_open(kicad_cli: str, target: OpenTarget = "schematic") -> bool:
    find_editor, _ = _EDITORS[target]
    return find_editor(kicad_cli) is not None or kicad_gui(kicad_cli) is not None


def popen_detached(command: list[str]) -> subprocess.Popen[bytes]:
    """Start KiCad and return at once; it outlives the request (and the backend)."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(  # noqa: S603 - fixed program, a path inside DESIGNS_ROOT
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        start_new_session=sys.platform != "win32",
    )


def zip_folder(folder: Path, arcroot: str) -> bytes:
    """The revision folder as a zip (small: a few project files and the outputs). Only
    regular files that resolve inside `folder` are packed; symlinks are skipped."""
    base = folder.resolve()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(base.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(base):
                continue
            archive.write(path, f"{arcroot}/{path.relative_to(base).as_posix()}")
    return buffer.getvalue()
