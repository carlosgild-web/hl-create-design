"""A stand-in for `subprocess.run` that writes the files kicad-cli would (tests and evals)."""

from __future__ import annotations

import subprocess
from pathlib import Path


class FakeKicadCli:
    """Stands in for `subprocess.run`: records commands and writes the files kicad-cli would."""

    def __init__(self, returncode=0, write_files=True, raises=None):
        self.returncode, self.write_files, self.raises = returncode, write_files, raises
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        assert kwargs["timeout"] > 0 and kwargs["capture_output"] and not kwargs["check"]
        if self.raises:
            raise self.raises
        output, source = Path(command[command.index("--output") + 1]), Path(command[-1])
        if self.write_files and self.returncode == 0:
            if command[1] == "pcb":  # --mode-single: --output is the file itself
                output.write_bytes(
                    b"%PDF-1.5 fake pcb" if command[3] == "pdf" else b'<svg id="pcb"/>'
                )
            elif command[3] == "pdf":
                output.write_bytes(b"%PDF-1.5 fake")
            else:
                (output / f"{source.stem}.svg").write_text("<svg/>", encoding="utf-8")
        return subprocess.CompletedProcess(command, self.returncode, "Plotted.", "")
