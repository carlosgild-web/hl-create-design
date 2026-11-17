"""The company rules of the Design Manual (`docs/manual/`), as deterministic checks.

Invariant 1: these functions decide whether a design request is valid; the assistant only
explains their results. Every error and warning carries a reference to the manual section
that states the rule, as `<section>#<anchor>` (for example `02-revisions#skipped-letters`),
so the explanation can cite it.

Nothing here does I/O except `resolve_inside`, which resolves paths (and so follows
symlinks) to keep every write inside `DESIGNS_ROOT` (invariant 3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath

# --- results ---------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """One broken rule (an error) or one thing to tell the user (a warning)."""

    field: str
    code: str
    message: str
    ref: str  # manual section and anchor, e.g. "02-revisions#skipped-letters"


@dataclass(frozen=True)
class FieldCheck:
    """The normalized value of one field and what is wrong with it."""

    value: str
    errors: tuple[Issue, ...] = ()
    warnings: tuple[Issue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def _check(value: str, *errors: Issue, warnings: Iterable[Issue] = ()) -> FieldCheck:
    return FieldCheck(value=value, errors=tuple(errors), warnings=tuple(warnings))


# --- departments: 05-departments ----------------------------------------------------

DEPARTMENTS: dict[str, str] = {
    "HW": "Hardware Design",
    "PWR": "Power Electronics",
    "EMB": "Embedded Boards",
    "TFX": "Test Fixtures",
}


def validate_department(code: str) -> FieldCheck:
    code = code.strip()
    if code in DEPARTMENTS:
        return _check(code)
    hint = f" Did you mean {code.upper()}?" if code.upper() in DEPARTMENTS else ""
    return _check(
        code,
        Issue(
            "department",
            "department_unknown",
            f"'{code}' is not an Electronics Engineering department. "
            f"Use one of {', '.join(DEPARTMENTS)}.{hint}",
            "05-departments#list",
        ),
    )


def department_label(code: str) -> str:
    """The department as the title block shows it: `HW – Hardware Design`."""
    return f"{code} – {DEPARTMENTS[code]}"


# --- design number: 01-design-numbering#format ----------------------------------------

DESIGN_NUMBER_RE = re.compile(r"^HL-(HW|PWR|EMB|TFX)-(\d{2})-(\d{4})$")
_NUMBER_LOOSE_RE = re.compile(r"^HL-([A-Z]+)-(\d+)-(\d+)$")


def validate_design_number(number: str, department: str | None = None) -> FieldCheck:
    """Check the format, and that the number belongs to `department` when given."""
    number = number.strip()
    ref = "01-design-numbering#format"
    match = DESIGN_NUMBER_RE.match(number)
    if not match:
        return _check(number, Issue("design_number", "number_format", _why(number), ref))
    if match.group(3) == "0000":
        return _check(
            number,
            Issue(
                "design_number",
                "number_sequence_zero",
                "The sequence runs from 0001 to 9999; 0000 is never issued.",
                ref,
            ),
        )
    if department is not None and department in DEPARTMENTS and match.group(1) != department:
        return _check(
            number,
            Issue(
                "design_number",
                "number_department_mismatch",
                f"{number} belongs to department {match.group(1)}, not {department}.",
                ref,
            ),
        )
    return _check(number)


def _why(number: str) -> str:
    """Explain the most likely mistake in a malformed design number."""
    expected = "The format is HL-<DEPT>-<YY>-<NNNN>, for example HL-HW-26-0042."
    if number != number.upper() and DESIGN_NUMBER_RE.match(number.upper()):
        return f"Write the design number in capital letters: {number.upper()}. {expected}"
    if "_" in number or " " in number:
        return f"Use hyphens, without spaces or underscores. {expected}"
    loose = _NUMBER_LOOSE_RE.match(number.upper())
    if loose:
        dept, year, seq = loose.groups()
        if dept not in DEPARTMENTS:
            return f"'{dept}' is not an Electronics Engineering department. {expected}"
        if len(year) != 2:
            return f"The year has two digits ({year[-2:]}). {expected}"
        if len(seq) != 4:
            return f"The sequence has four digits ({seq.zfill(4)[-4:]}). {expected}"
    return expected


# --- revisions: 02-revisions --------------------------------------------------------

REVISION_LETTERS = "ABCDEFGHJKLMNPRTUVWY"
SKIPPED_LETTERS = frozenset("IOQSXZ")
FIRST_REVISION = "A"


def revision_index(rev: str) -> int | None:
    """Position of `rev` in the sequence A..Y, AA..YY (0-based), or None if not a revision."""
    letters = REVISION_LETTERS
    if len(rev) == 1 and rev in letters:
        return letters.index(rev)
    if len(rev) == 2 and rev[0] in letters and rev[1] in letters:
        return len(letters) * (1 + letters.index(rev[0])) + letters.index(rev[1])
    return None


def revision_at(index: int) -> str:
    """The revision at `index` of the sequence (inverse of `revision_index`)."""
    n = len(REVISION_LETTERS)
    if index < n:
        return REVISION_LETTERS[index]
    first, second = divmod(index - n, n)
    if first >= n:
        raise ValueError("beyond the last two-letter revision YY")
    return REVISION_LETTERS[first] + REVISION_LETTERS[second]


def next_revision(existing: Iterable[str]) -> str:
    """02-revisions#next-revision: the letter after the highest revision that exists."""
    indexes = [i for r in existing if (i := revision_index(r.strip().upper())) is not None]
    return revision_at(max(indexes) + 1) if indexes else FIRST_REVISION


def validate_revision(rev: str, existing: Iterable[str] = ()) -> FieldCheck:
    """Check a requested revision against the sequence and the revisions that exist.

    `existing` are the revisions ever created for the design (SAP and the folders). The
    value is normalized to capitals; `i` is still reported as a skipped letter.
    """
    rev = rev.strip().upper()
    existing = sorted({r.strip().upper() for r in existing}, key=lambda r: revision_index(r) or 0)

    if not re.fullmatch(r"[A-Z]{1,2}", rev):
        message = (
            f"'{rev}' is not a revision. Revisions are letters: A, B, C... "
            "There is no revision 0, -, 01 or P1, and no sub-revisions such as A1."
        )
        ref = "02-revisions#first-revision" if rev else "02-revisions#sequence"
        return _check(rev, Issue("revision", "rev_format", message, ref))

    skipped = sorted(SKIPPED_LETTERS.intersection(rev))
    if skipped:
        letters = ", ".join(skipped)
        expected = next_revision(existing)
        return _check(
            rev,
            Issue(
                "revision",
                "rev_skipped_letter",
                f"The letters I, O, Q, S, X and Z are never used ({letters} in '{rev}'). "
                f"The next free revision is {expected}.",
                "02-revisions#skipped-letters",
            ),
        )

    if rev in existing:
        return _check(
            rev,
            Issue(
                "revision",
                "rev_reused",
                f"Revision {rev} already exists, and a letter is never reused. "
                f"The next free revision is {next_revision(existing)}.",
                "02-revisions#never-reuse",
            ),
        )

    expected = next_revision(existing)
    if rev != expected:
        if not existing:
            return _check(
                rev,
                Issue(
                    "revision",
                    "rev_first_not_a",
                    f"A new design starts at revision {FIRST_REVISION}, not {rev}.",
                    "02-revisions#first-revision",
                ),
            )
        older = (revision_index(rev) or 0) < (revision_index(expected) or 0)
        return _check(
            rev,
            Issue(
                "revision",
                "rev_reused" if older else "rev_jump",
                (
                    f"Revision {rev} comes before the existing {existing[-1]}; "
                    f"letters are never reused. The next free revision is {expected}."
                    if older
                    else f"Don't jump ahead: after {existing[-1]} comes {expected}, not {rev}."
                ),
                "02-revisions#never-reuse" if older else "02-revisions#next-revision",
            ),
        )
    return _check(rev)


# --- SAP status: 06-sap-statuses ----------------------------------------------------


def check_status_allows_revision(
    status: str, *, block_reason: str | None = None, successor: str | None = None
) -> FieldCheck:
    """02-revisions#revisions-and-status: may a new revision be created in this status?"""
    if status == "IN_WORK":
        return _check(status)
    if status == "RELEASED":
        warning = Issue(
            "status",
            "status_released_needs_eco",
            "The design is RELEASED: the company process requires an ECO number before the "
            "new revision is released. Create Design doesn't check it; tell your lead.",
            "06-sap-statuses#released",
        )
        return _check(status, warnings=[warning])
    if status == "BLOCKED":
        reason = f" Reason in SAP: {block_reason}." if block_reason else ""
        return _check(
            status,
            Issue(
                "status",
                "status_blocked",
                "The design is BLOCKED by Product Engineering; no new revision can be created."
                f"{reason} Contact Product Engineering.",
                "06-sap-statuses#blocked",
            ),
        )
    if status == "OBSOLETE":
        hint = f" Work on the successor {successor} instead." if successor else ""
        return _check(
            status,
            Issue(
                "status",
                "status_obsolete",
                "The design is OBSOLETE and no longer built; no new revision can be created."
                f"{hint}",
                "06-sap-statuses#obsolete",
            ),
        )
    return _check(
        status,
        Issue(
            "status",
            "status_unknown",
            f"Unknown SAP status '{status}'.",
            "06-sap-statuses#overview",
        ),
    )


# --- design name: 03-title-block#design-name ------------------------------------------

NAME_MIN, NAME_MAX = 3, 40
_NAME_CHARS_RE = re.compile(r"^[A-Za-z0-9 ._-]+$")
_NAME_FORBIDDEN_WORDS = frozenset({"new", "final", "copy", "rev", "revision"})
_NAME_HAS_NUMBER_RE = re.compile(r"\bHL[-_ ]?[A-Z]{2,4}[-_ ]?\d", re.IGNORECASE)


def collapse_spaces(text: str) -> str:
    """Remove spaces at the start and the end, and turn repeated spaces into one."""
    return " ".join(text.split())


def title_case(name: str) -> str:
    """Capitalise each word; keep words already written in capitals (`LED`, `24V`)."""
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:].lower() for w in name.split())


def validate_design_name(raw: str) -> FieldCheck:
    name = title_case(collapse_spaces(raw))
    ref = "03-title-block#design-name"
    bad = sorted({c for c in name if not _NAME_CHARS_RE.match(c)})
    if bad:
        return _check(
            name,
            Issue(
                "name",
                "name_characters",
                "The design name may contain only letters A-Z, digits, spaces and - _ . "
                f"(no accents or other symbols). Not allowed: {' '.join(repr(c) for c in bad)}.",
                ref,
            ),
        )
    if not NAME_MIN <= len(name) <= NAME_MAX:
        return _check(
            name,
            Issue(
                "name",
                "name_length",
                f"The design name needs {NAME_MIN} to {NAME_MAX} characters; it has {len(name)}.",
                ref,
            ),
        )
    if _NAME_HAS_NUMBER_RE.search(name):
        return _check(
            name,
            Issue(
                "name",
                "name_contains_number",
                "Don't put the design number in the name; describe the function.",
                ref,
            ),
        )
    words = {w.lower().strip("._-") for w in name.split()}
    forbidden = sorted(words & _NAME_FORBIDDEN_WORDS)
    if forbidden:
        return _check(
            name,
            Issue(
                "name",
                "name_forbidden_word",
                f"Don't use words like {', '.join(forbidden)} in the name; describe the "
                "function, for example 'Kiln Thermocouple Interface'.",
                ref,
            ),
        )
    return _check(name)


# --- designer: 03-title-block#designer ------------------------------------------------

DESIGNER_MAX = 40
# Initial, period, space, surname. Letters with accents are allowed; digits are not.
_DESIGNER_RE = re.compile(r"^([^\W\d_])\. ([^\W\d_](?:[^\W\d_]|['\- ])*[^\W\d_])$")


def validate_designer(raw: str) -> FieldCheck:
    designer = collapse_spaces(raw)
    ref = "03-title-block#designer"
    match = _DESIGNER_RE.match(designer)
    if len(designer) > DESIGNER_MAX:
        return _check(
            designer,
            Issue(
                "designer",
                "designer_length",
                f"The designer has at most {DESIGNER_MAX} characters.",
                ref,
            ),
        )
    if not match or not match.group(1).isupper() or not match.group(2)[0].isupper():
        return _check(
            designer,
            Issue(
                "designer",
                "designer_format",
                "Write the designer as initial, period, space and surname, as in the company "
                "directory: C. Velazquez.",
                ref,
            ),
        )
    return _check(designer)


# --- SAP material and project: 01-design-numbering#sap-material, #wbs --------------------

MATERIAL_LENGTH = 18
MATERIAL_MIN, MATERIAL_MAX = 40_000_000, 49_999_999
WBS_RE = re.compile(r"^P-\d{2}-\d{4}$")


def validate_material(raw: str) -> FieldCheck:
    """Accept the 18-character form or the short one; normalize to 18 characters."""
    raw = raw.strip()
    ref = "01-design-numbering#sap-material"
    if not raw.isdigit() or len(raw) > MATERIAL_LENGTH or not raw.isascii():
        return _check(
            raw,
            Issue(
                "sap_material",
                "material_format",
                "The SAP material number has only digits: 18 with leading zeros "
                "(000000000040001234) or without them (40001234).",
                ref,
            ),
        )
    value = raw.zfill(MATERIAL_LENGTH)
    if not MATERIAL_MIN <= int(value) <= MATERIAL_MAX:
        return _check(
            value,
            Issue(
                "sap_material",
                "material_range",
                f"{material_display(value)} is outside the range for electronic assemblies "
                "(40000000 to 49999999).",
                ref,
            ),
        )
    return _check(value)


def material_display(material: str) -> str:
    """The material as documents show it: without leading zeros."""
    return material.lstrip("0") or "0"


def validate_project(raw: str) -> FieldCheck:
    project = raw.strip()
    if WBS_RE.match(project):
        return _check(project)
    return _check(
        project,
        Issue(
            "project",
            "project_format",
            "The project (WBS element) has the format P-<YY>-<NNNN>, for example P-26-0108.",
            "01-design-numbering#wbs",
        ),
    )


# --- date: 03-title-block#date ------------------------------------------------------

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_issue_date(raw: str | date) -> FieldCheck:
    if isinstance(raw, date):
        return _check(raw.isoformat())
    text = raw.strip()
    error = Issue(
        "issue_date",
        "date_format",
        "Write the date in ISO 8601 format, YYYY-MM-DD: 2026-11-17.",
        "03-title-block#date",
    )
    if not _ISO_DATE_RE.match(text):
        return _check(text, error)
    try:
        date.fromisoformat(text)
    except ValueError:
        return _check(text, error)
    return _check(text)


# --- the whole request --------------------------------------------------------------


@dataclass(frozen=True)
class DesignRequest:
    """The fields a user enters to create a design revision."""

    department: str
    design_number: str
    revision: str
    name: str
    designer: str
    sap_material: str = ""
    project: str = ""
    issue_date: str | date = ""


@dataclass(frozen=True)
class ValidationReport:
    """The normalized request plus every error and warning, per field."""

    request: DesignRequest
    errors: tuple[Issue, ...] = ()
    warnings: tuple[Issue, ...] = ()
    next_revision: str = FIRST_REVISION

    @property
    def ok(self) -> bool:
        return not self.errors

    def errors_for(self, name: str) -> list[Issue]:
        return [e for e in self.errors if e.field == name]


def validate_design_request(
    request: DesignRequest,
    *,
    existing_revisions: Iterable[str] = (),
    sap_status: str | None = None,
    block_reason: str | None = None,
    successor: str | None = None,
) -> ValidationReport:
    """Check every field. Optional SAP fields are checked only when they are given."""
    existing = list(existing_revisions)
    checks: dict[str, FieldCheck] = {
        "department": validate_department(request.department),
        "design_number": validate_design_number(request.design_number, request.department),
        "revision": validate_revision(request.revision, existing),
        "name": validate_design_name(request.name),
        "designer": validate_designer(request.designer),
    }
    if request.sap_material.strip():
        checks["sap_material"] = validate_material(request.sap_material)
    if request.project.strip():
        checks["project"] = validate_project(request.project)
    if request.issue_date:
        checks["issue_date"] = validate_issue_date(request.issue_date)
    if sap_status is not None:
        checks["status"] = check_status_allows_revision(
            sap_status, block_reason=block_reason, successor=successor
        )

    def value(name: str, default: str = "") -> str:
        return checks[name].value if name in checks else default

    normalized = DesignRequest(
        department=value("department"),
        design_number=value("design_number"),
        revision=value("revision"),
        name=value("name"),
        designer=value("designer"),
        sap_material=value("sap_material"),
        project=value("project"),
        issue_date=value("issue_date"),
    )
    return ValidationReport(
        request=normalized,
        errors=tuple(e for c in checks.values() for e in c.errors),
        warnings=tuple(w for c in checks.values() for w in c.warnings),
        next_revision=next_revision(existing),
    )


# --- paths: 04-folder-structure#designs-root ------------------------------------------


class UnsafePathError(ValueError):
    """A path that would leave DESIGNS_ROOT (invariant 3)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.issue = Issue("path", "path_outside_root", message, "04-folder-structure#designs-root")


def _check_component(part: str) -> None:
    """One folder or file name: no separators, drives, `..`, or absolute paths."""
    if not part or part.strip() != part:
        raise UnsafePathError(f"Empty or padded path component {part!r}.")
    if "\0" in part or any(ord(c) < 32 for c in part):
        raise UnsafePathError(f"Control characters in path component {part!r}.")
    win, posix = PureWindowsPath(part), PurePosixPath(part)
    if win.drive or win.root or posix.root:
        raise UnsafePathError(f"Absolute path or drive letter {part!r}; paths stay in the root.")
    if "/" in part or "\\" in part or ":" in part:
        raise UnsafePathError(f"Path separator in component {part!r}.")
    if part in {".", ".."}:
        raise UnsafePathError(f"Relative component {part!r}; '..' would leave the root.")


def resolve_inside(root: Path, *parts: str) -> Path:
    """Join `parts` under `root` and prove that the result stays inside it.

    Each part must be a single plain name. The joined path is resolved, so symlinks are
    followed: a link inside the root that points outside it is refused too.
    """
    for part in parts:
        _check_component(part)
    base = root.resolve()
    target = base.joinpath(*parts).resolve()
    if not target.is_relative_to(base):
        raise UnsafePathError(f"{'/'.join(parts)} resolves outside the designs root.")
    return target


def design_folder(root: Path, department: str, design_number: str, revision: str) -> Path:
    """04-folder-structure#layout: `<root>/<DEPT>/<DesignNumber>/<Rev>`, checked and confined."""
    errors = [
        *validate_department(department).errors,
        *validate_design_number(design_number, department).errors,
    ]
    if revision_index(revision) is None:
        errors.append(
            Issue(
                "revision",
                "rev_format",
                f"'{revision}' is not a revision.",
                "02-revisions#sequence",
            )
        )
    if errors:
        raise UnsafePathError("; ".join(e.message for e in errors))
    return resolve_inside(root, department, design_number, revision)


def design_file_stem(design_number: str, revision: str) -> str:
    """04-folder-structure#file-names: `<DesignNumber>_<Rev>`."""
    return f"{design_number}_{revision}"


def revisions_on_disk(root: Path, department: str, design_number: str) -> list[str]:
    """The revision folders that exist for a design, in sequence order.

    A lower bound of the revisions ever created: SAP also knows abandoned ones.
    """
    folder = resolve_inside(root, department, design_number)
    if not folder.is_dir():
        return []
    revs = [p.name for p in folder.iterdir() if p.is_dir() and revision_index(p.name) is not None]
    return sorted(revs, key=lambda r: revision_index(r) or 0)
