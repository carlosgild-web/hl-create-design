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

Launcher = Callable[[list[str]], object]


def kicad_gui(kicad_cli: str) -> Path | None:
    """The KiCad GUI that sits next to `kicad-cli` (same install), or None."""
    found = shutil.which(kicad_cli)
    if found is None:
        return None
    name = "kicad.exe" if sys.platform == "win32" else "kicad"
    gui = Path(found).resolve().with_name(name)
    return gui if gui.is_file() else None


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
