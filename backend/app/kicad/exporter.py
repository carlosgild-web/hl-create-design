"""Run `kicad-cli` to export a schematic to PDF and SVG.

The path to the executable comes from `KICAD_CLI`. Every run has a timeout and its output
is captured, so a failure can be shown to the user and kept in the logs. The runner is
injectable so the tests don't need KiCad (the real export test is marked `kicad`).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_S = 120.0

Runner = Callable[..., subprocess.CompletedProcess[str]]


class ExportError(RuntimeError):
    """kicad-cli is missing, timed out, failed, or produced no file."""

    def __init__(self, message: str, *, command: Sequence[str] = (), log: str = "") -> None:
        super().__init__(message)
        self.command = list(command)
        self.log = log


@dataclass(frozen=True)
class ExportResult:
    pdf: Path
    svgs: tuple[Path, ...]
    log: str


def export_schematic(
    schematic: Path,
    output_dir: Path,
    *,
    kicad_cli: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    runner: Runner = subprocess.run,
) -> ExportResult:
    """Export `schematic` to `<output_dir>/<stem>.pdf` and one SVG per sheet."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf = output_dir / f"{schematic.stem}.pdf"
    logs = [
        _run(
            [kicad_cli, "sch", "export", "pdf", "--output", str(pdf), str(schematic)],
            runner,
            timeout_s,
        ),
        _run(
            [kicad_cli, "sch", "export", "svg", "--output", str(output_dir), str(schematic)],
            runner,
            timeout_s,
        ),
    ]
    log = "\n".join(logs)
    if not pdf.is_file():
        raise ExportError(f"kicad-cli wrote no PDF at {pdf}", log=log)
    svgs = tuple(sorted(output_dir.glob("*.svg")))
    if not svgs:
        raise ExportError(f"kicad-cli wrote no SVG in {output_dir}", log=log)
    return ExportResult(pdf=pdf, svgs=svgs, log=log)


def _run(command: list[str], runner: Runner, timeout_s: float) -> str:
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ExportError(
            f"kicad-cli not found at '{command[0]}'. Install KiCad 9 and set KICAD_CLI.",
            command=command,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ExportError(
            f"kicad-cli timed out after {timeout_s:g} s", command=command, log=_text(exc.output)
        ) from exc

    log = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0:
        raise ExportError(
            f"kicad-cli failed with exit code {completed.returncode}: {log[-500:]}",
            command=command,
            log=log,
        )
    return log


def _text(output: str | bytes | None) -> str:
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""
