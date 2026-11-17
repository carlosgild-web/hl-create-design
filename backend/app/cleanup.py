"""Delete old generated designs (the demo's `DESIGNS_ROOT` cleanup).

Removes revision folders `<root>/<DEPT>/<DesignNumber>/<Rev>` whose last change is older
than the limit, then the design and department folders left empty. Every path is
resolved inside `DESIGNS_ROOT` first and symlinks are never followed (invariant 3);
each removed revision writes an audit row (invariant 8).
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from app.db.session import write_audit
from app.standards.validators import UnsafePathError, resolve_inside


@dataclass(frozen=True)
class Removed:
    department: str
    design_number: str
    revision: str


def _latest_change(folder: Path) -> float:
    return max(p.stat().st_mtime for p in (folder, *folder.rglob("*")) if not p.is_symlink())


def cleanup_designs(
    root: Path, engine: Engine, *, older_than_hours: float, now: float | None = None
) -> list[Removed]:
    if older_than_hours <= 0 or not root.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - older_than_hours * 3600
    removed: list[Removed] = []
    for dept in sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()):
        for design in sorted(p for p in dept.iterdir() if p.is_dir() and not p.is_symlink()):
            for rev in sorted(p for p in design.iterdir() if p.is_dir() and not p.is_symlink()):
                try:
                    target = resolve_inside(root, dept.name, design.name, rev.name)
                except UnsafePathError:
                    continue  # never touch anything that does not resolve inside the root
                if _latest_change(target) >= cutoff:
                    continue
                shutil.rmtree(target)
                removed.append(Removed(dept.name, design.name, rev.name))
                write_audit(
                    engine,
                    action="design_cleaned",
                    actor="cleanup",
                    design_number=design.name,
                    revision=rev.name,
                    details={"older_than_hours": older_than_hours},
                )
            if not any(design.iterdir()):
                design.rmdir()
        if not any(dept.iterdir()):
            dept.rmdir()
    return removed
