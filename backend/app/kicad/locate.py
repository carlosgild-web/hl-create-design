"""Find kicad-cli when `KICAD_CLI` is left at its default, and say what KiCad enables.

The KiCad 9 installers don't put `kicad-cli` on the `PATH` (Windows and macOS), so a fresh
clone with `KICAD_CLI=kicad-cli` found no KiCad even where it was installed: no PDF, no
preview and no Open in KiCad, with no clear message (decision 0035). When the setting is the
bare default and `PATH` doesn't have it, the standard install folders are tried. An explicit
path is never replaced by a guess: if it is wrong, the messages name it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_KICAD_CLI = "kicad-cli"
KICAD_DOWNLOAD_URL = "https://www.kicad.org/download/"


def install_candidates(env: Mapping[str, str], platform: str) -> list[Path]:
    """Where the KiCad 9 installers put kicad-cli, most common first."""
    if platform == "win32":
        roots = [
            (env.get("ProgramFiles") or env.get("PROGRAMFILES"), "KiCad"),
            (env.get("LOCALAPPDATA"), "Programs/KiCad"),  # per-user install (winget)
            (env.get("ProgramW6432"), "KiCad"),
        ]
        return [Path(root) / sub / "9.0" / "bin" / "kicad-cli.exe" for root, sub in roots if root]
    if platform == "darwin":
        return [Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")]
    return [
        Path("/usr/bin/kicad-cli"),
        Path("/usr/local/bin/kicad-cli"),
        Path("/snap/bin/kicad-cli"),
    ]


def resolve_kicad_cli(
    configured: str,
    *,
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    is_file: Callable[[Path], bool] = Path.is_file,
) -> str:
    """`configured` if it runs as is; for the bare default, else the first installed
    kicad-cli in the standard folders; else `configured` unchanged."""
    if which(configured) or configured != DEFAULT_KICAD_CLI:
        return configured
    for candidate in install_candidates(
        os.environ if env is None else env, platform or sys.platform
    ):
        if is_file(candidate):
            return str(candidate)
    return configured


@dataclass(frozen=True)
class KicadStatus:
    """What the app can do with the KiCad it found (start-up message, UI notice)."""

    found: bool
    path: str
    version: str
    can_export: bool
    can_open: bool
    can_open_pcb: bool
    download_url: str = KICAD_DOWNLOAD_URL

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=8)
def kicad_version(kicad_cli: str) -> str:
    """`kicad-cli version` ("9.0.8"), or "" when it doesn't run. Cached per path."""
    try:
        done = subprocess.run(  # noqa: S603 - the configured kicad-cli, no shell
            [kicad_cli, "version"], capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def kicad_status(kicad_cli: str, open_enabled: bool) -> KicadStatus:
    from app.kicad.launcher import can_open  # launcher imports nothing from here

    found_at = shutil.which(kicad_cli)
    path = str(Path(found_at)) if found_at else ""
    found = bool(path)
    return KicadStatus(
        found=found,
        path=path or kicad_cli,
        version=kicad_version(path) if found else "",
        can_export=found,
        can_open=found and open_enabled and can_open(kicad_cli),
        can_open_pcb=found and open_enabled and can_open(kicad_cli, "pcb"),
    )
