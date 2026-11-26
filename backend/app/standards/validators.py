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
from dataclasses import field as dataclass_field
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

# --- results ---------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """One broken rule (an error) or one thing to tell the user (a warning).

    `message` is English: the model, the traces and the logs read it. The UI shows the
    user's language from `code` and `params` (decision 0022): the template
    `issue.<code>` in `frontend/src/i18n/messages.ts`, or `issue.<code>.<variant>` when
    `params["variant"]` is set, filled in with the other params.
    """

    field: str
    code: str
    message: str
    ref: str  # manual section and anchor, e.g. "02-revisions#skipped-letters"
    params: dict[str, str] = dataclass_field(default_factory=dict, compare=False, hash=False)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "ref": self.ref,
        }
        if self.params:
            out["params"] = dict(self.params)
        return out


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
# The Spanish names, as SAP has them (sap-mock/seed/departments.json): for the UI and the
# assistant, which match a department named in either language.
DEPARTMENTS_ES: dict[str, str] = {
    "HW": "Diseño de Hardware",
    "PWR": "Electrónica de Potencia",
    "EMB": "Placas Embebidas",
    "TFX": "Utillajes de Prueba",
}


def validate_department(code: str) -> FieldCheck:
    code = code.strip()
    if code in DEPARTMENTS:
        return _check(code)
    suggest = code.upper() in DEPARTMENTS
    hint = f" Did you mean {code.upper()}?" if suggest else ""
    params = {"value": code, "departments": ", ".join(DEPARTMENTS)}
    if suggest:
        params |= {"variant": "suggest", "suggestion": code.upper()}
    return _check(
        code,
        Issue(
            "department",
            "department_unknown",
            f"'{code}' is not an Electronics Engineering department. "
            f"Use one of {', '.join(DEPARTMENTS)}.{hint}",
            "05-departments#list",
            params,
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
        message, params = _why(number)
        return _check(number, Issue("design_number", "number_format", message, ref, params))
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
                {"number": number, "owner": match.group(1), "department": department},
            ),
        )
    return _check(number)


def _why(number: str) -> tuple[str, dict[str, str]]:
    """Explain the most likely mistake in a malformed design number: the English message
    and the params of its `number_format` variant."""
    expected = "The format is HL-<DEPT>-<YY>-<NNNN>, for example HL-HW-26-0042."
    if number != number.upper() and DESIGN_NUMBER_RE.match(number.upper()):
        upper = number.upper()
        return (
            f"Write the design number in capital letters: {upper}. {expected}",
            {"variant": "capitals", "upper": upper},
        )
    if "_" in number or " " in number:
        return f"Use hyphens, without spaces or underscores. {expected}", {"variant": "hyphens"}
    loose = _NUMBER_LOOSE_RE.match(number.upper())
    if loose:
        dept, year, seq = loose.groups()
        if dept not in DEPARTMENTS:
            return (
                f"'{dept}' is not an Electronics Engineering department. {expected}",
                {"variant": "department", "dept": dept},
            )
        if len(year) != 2:
            return (
                f"The year has two digits ({year[-2:]}). {expected}",
                {"variant": "year", "year": year[-2:]},
            )
        if len(seq) != 4:
            sequence = seq.zfill(4)[-4:]
            return (
                f"The sequence has four digits ({sequence}). {expected}",
                {"variant": "sequence", "sequence": sequence},
            )
    return expected, {}


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


def revisions_in_use(sap_revisions: Iterable[str], on_disk: Iterable[str]) -> list[str]:
    """The revisions that count as created (02-revisions#never-reuse), from SAP and disk.

    Reserving a number records revision A in SAP before its folder exists
    (02-revisions#first-revision). So while SAP has only revision A and no revision
    folder exists yet, A is still free for its first folder. Every other revision that
    SAP knows stays used, even without a folder: it may have been abandoned.
    """
    sap = {r.strip().upper() for r in sap_revisions}
    disk = {r.strip().upper() for r in on_disk}
    if sap == {FIRST_REVISION} and not disk:
        sap = set()
    return sorted(sap | disk, key=lambda r: revision_index(r) or 0)


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
        return _check(rev, Issue("revision", "rev_format", message, ref, {"value": rev}))

    skipped = sorted(SKIPPED_LETTERS.intersection(rev))
    if skipped:
        letters = ", ".join(skipped)
        expected = next_revision(existing)
        # "I" alone needs no "(I in 'I')": the plain sentence, as variant "single".
        single = rev == letters
        where = "" if single else f" ({letters} in '{rev}')"
        return _check(
            rev,
            Issue(
                "revision",
                "rev_skipped_letter",
                f"The letters I, O, Q, S, X and Z are never used{where}. "
                f"The next free revision is {expected}.",
                "02-revisions#skipped-letters",
                {"letters": letters, "value": rev, "expected": expected}
                | ({"variant": "single"} if single else {}),
            ),
        )

    if rev in existing:
        expected = next_revision(existing)
        return _check(
            rev,
            Issue(
                "revision",
                "rev_reused",
                f"Revision {rev} already exists, and a letter is never reused. "
                f"The next free revision is {expected}.",
                "02-revisions#never-reuse",
                {"value": rev, "expected": expected},
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
                    {"value": rev},
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
                {"value": rev, "latest": existing[-1], "expected": expected}
                | ({"variant": "older"} if older else {}),
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
        blocked = {"variant": "reason", "reason": block_reason} if block_reason else {}
        return _check(
            status,
            Issue(
                "status",
                "status_blocked",
                "The design is BLOCKED by Product Engineering; no new revision can be created."
                f"{reason} Contact Product Engineering.",
                "06-sap-statuses#blocked",
                blocked,
            ),
        )
    if status == "OBSOLETE":
        hint = f" Work on the successor {successor} instead." if successor else ""
        obsolete = {"variant": "successor", "successor": successor} if successor else {}
        return _check(
            status,
            Issue(
                "status",
                "status_obsolete",
                "The design is OBSOLETE and no longer built; no new revision can be created."
                f"{hint}",
                "06-sap-statuses#obsolete",
                obsolete,
            ),
        )
    return _check(
        status,
        Issue(
            "status",
            "status_unknown",
            f"Unknown SAP status '{status}'.",
            "06-sap-statuses#overview",
            {"status": status},
        ),
    )


def check_known_in_sap(design_number: str, found: bool) -> FieldCheck:
    """01-design-numbering#issued-by-sap: only numbers that SAP issued can be used."""
    if found:
        return _check(design_number)
    return _check(
        design_number,
        Issue(
            "design_number",
            "number_not_in_sap",
            f"{design_number} doesn't exist in SAP. Only SAP issues design numbers: reserve a "
            "new number, or check that you typed an existing one correctly.",
            "01-design-numbering#issued-by-sap",
            {"number": design_number},
        ),
    )


# --- design name: 03-title-block#design-name ------------------------------------------

NAME_MIN, NAME_MAX = 3, 40
_NAME_CHARS_RE = re.compile(r"^[A-Za-z0-9 ._-]+$")
_NAME_HAS_NUMBER_RE = re.compile(r"\bHL[-_ ]?[A-Z]{2,4}[-_ ]?\d", re.IGNORECASE)
# Version words (decision 0022). An error when they modify the whole name: "New"/"Final"
# first, "New"/"Final"/"Copy" last, or "Rev"/"Revision" + a letter or digit ("Rev A").
# Anywhere else only a warning, so "Copy Stand Controller" and "Revision Counter Board" pass.
_NAME_VERSION_WORDS = frozenset({"new", "final", "copy", "rev", "revision"})
_NAME_LEADING_MODIFIERS = frozenset({"new", "final"})
_NAME_TRAILING_MODIFIERS = frozenset({"new", "final", "copy"})
_NAME_REVISION_TAG_RE = re.compile(r"\b(rev|revision)[ ._-]*([a-z]{1,2}|\d+)\b", re.IGNORECASE)
# Common Spanish words in board names; two of them, or a one-word name that is one, look
# Spanish (07-faq#name-language). A warning only: "Control Board" is English too.
_SPANISH_TEXT = (
    "de del la el los las para con sin y placa tarjeta fuente controlador prueba "
    "pruebas nueva nuevo sensores taladro horno potencia alimentacion "
    "medidor medicion lector interfaz modulo banco utillaje contador pantalla"
)
_SPANISH_WORDS = frozenset(_SPANISH_TEXT.split())


def collapse_spaces(text: str) -> str:
    """Remove spaces at the start and the end, and turn repeated spaces into one."""
    return " ".join(text.split())


def _title_word(word: str) -> str:
    # Written with capitals on purpose: "LED", "24V", "USB-C", "LEDs", "iPhone".
    if word.isupper() or any(c.isupper() for c in word[1:]):
        return word
    return "-".join(part[:1].upper() + part[1:].lower() for part in word.split("-"))


def title_case(name: str) -> str:
    """Capitalize each word and each part of a hyphenated word (`burn-in` -> `Burn-In`);
    keep words written with capitals (`LED`, `24V`, `LEDs`, `iPhone`)."""
    return " ".join(_title_word(w) for w in name.split())


def _version_words(name: str) -> tuple[list[str], list[str]]:
    """(errors, warnings): the version words that modify the whole name, and the others."""
    words = [w.lower().strip("._-") for w in name.split()]
    errors: set[str] = set()
    if words and words[0] in _NAME_LEADING_MODIFIERS:
        errors.add(words[0])
    if words and words[-1] in _NAME_TRAILING_MODIFIERS:
        errors.add(words[-1])
    errors |= {m.group(1).lower() for m in _NAME_REVISION_TAG_RE.finditer(name)}
    warnings = (set(words) & _NAME_VERSION_WORDS) - errors
    return sorted(errors), sorted(warnings)


def _looks_spanish(name: str) -> bool:
    words = [w.lower().strip("._-") for w in name.split()]
    spanish = [w for w in words if w in _SPANISH_WORDS]
    return len(spanish) >= 2 or (len(words) == 1 and bool(spanish))


def validate_design_name(raw: str) -> FieldCheck:
    name = title_case(collapse_spaces(raw))
    ref = "03-title-block#design-name"
    bad = sorted({c for c in name if not _NAME_CHARS_RE.match(c)})
    if bad:
        chars = " ".join(repr(c) for c in bad)
        return _check(
            name,
            Issue(
                "name",
                "name_characters",
                "The design name may contain only letters A-Z, digits, spaces and - _ . "
                f"(no accents or other symbols). Not allowed: {chars}.",
                ref,
                {"chars": chars},
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
                {"min": str(NAME_MIN), "max": str(NAME_MAX), "length": str(len(name))},
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
    errors, maybe = _version_words(name)
    if errors:
        words = ", ".join(errors)
        return _check(
            name,
            Issue(
                "name",
                "name_forbidden_word",
                f"Don't use words like {words} in the name; describe the "
                "function, for example 'Kiln Thermocouple Interface'.",
                ref,
                {"words": words},
            ),
        )
    warnings: list[Issue] = []
    if maybe:
        words = ", ".join(maybe)
        warnings.append(
            Issue(
                "name",
                "name_word_check",
                f"Check that '{words}' describes the function and isn't a version word; "
                "versions go in the revision.",
                ref,
                {"words": words},
            )
        )
    if _looks_spanish(name):
        warnings.append(
            Issue(
                "name",
                "name_looks_spanish",
                "The name looks Spanish. Design names are in English, because they go to SAP "
                "and to supplier documents; Spanish text can go in the description.",
                "07-faq#name-language",
            )
        )
    return _check(name, warnings=warnings)


def _name_key(name: str) -> str:
    return title_case(collapse_spaces(name)).lower()


def check_name_unique(
    name: str, design_number: str, designs: Iterable[tuple[str, str]]
) -> list[Issue]:
    """07-faq#same-name: a warning when another SAP design (`(number, name)` pairs) has the
    same name. Never an error: the number identifies a design, not its name."""
    key = _name_key(name)
    for number, other in designs:
        if number != design_number and other and _name_key(other) == key:
            return [
                Issue(
                    "name",
                    "name_exists_in_sap",
                    f"{number} in SAP already has the name '{title_case(other)}'. If the new "
                    "board can replace it, make a new revision of that number instead.",
                    "07-faq#same-name",
                    {"number": number, "name": title_case(other)},
                )
            ]
    return []


# --- description: 03-title-block#description ------------------------------------------

DESCRIPTION_MAX = 60


def validate_description(raw: str) -> FieldCheck:
    """Optional, one line on the title block. Any printable text (accents too), but not
    `${...}`: KiCad would read it as a text variable and print another field there."""
    text = collapse_spaces(raw)
    ref = "03-title-block#description"
    if any(not c.isprintable() for c in text):
        return _check(
            text,
            Issue(
                "description",
                "description_characters",
                "The description is one line of plain text, without tabs or control characters.",
                ref,
            ),
        )
    if "${" in text:
        return _check(
            text,
            Issue(
                "description",
                "description_variable",
                "The description can't contain '${': KiCad would read it as a text variable.",
                ref,
            ),
        )
    if len(text) > DESCRIPTION_MAX:
        return _check(
            text,
            Issue(
                "description",
                "description_length",
                f"The description has at most {DESCRIPTION_MAX} characters; it has {len(text)}.",
                ref,
                {"max": str(DESCRIPTION_MAX), "length": str(len(text))},
            ),
        )
    return _check(text)


# --- designer: 03-title-block#designer ------------------------------------------------

DESIGNER_MAX = 40
MAX_INITIALS = 2
# Given names, then a surname (decision 0034). A given name is a full name ("Carlos") or an
# initial with a period ("C."), mixed freely ("Carlos A. Velazquez", "J. C. Pérez"), at most
# two initials. Letters with accents, apostrophes and hyphens are allowed; digits are not.
# Name words start with a capital and have at least two letters. Surname particles may be
# lowercase ("C. de la Torre", "Ana van Dijk"); the last word is a capitalized surname.
_INITIAL_RE = re.compile(r"^[^\W\d_]\.$")
_NAME_WORD_RE = re.compile(r"^[^\W\d_]+(?:['\-][^\W\d_]+)*$")
SURNAME_PARTICLES = frozenset(
    {"de", "del", "la", "las", "los", "y", "van", "von", "der", "den", "da", "do", "dos"}
)


def _is_initial(word: str) -> bool:
    return bool(_INITIAL_RE.match(word)) and word[0].isupper()


def _is_name(word: str) -> bool:
    return bool(_NAME_WORD_RE.match(word)) and len(word) >= 2 and word[0].isupper()


def _designer_ok(designer: str) -> bool:
    words = designer.split(" ")
    if len(words) < 2:
        return False
    first, *middle, last = words
    if not (_is_initial(first) or _is_name(first)) or not _is_name(last):
        return False
    initials = int(_is_initial(first))
    after_particle = False
    for word in middle:
        if _is_initial(word):
            if after_particle:  # "C. de A. Torre": initials belong to the given names
                return False
            initials += 1
        elif word in SURNAME_PARTICLES:
            after_particle = True
        elif not _is_name(word):
            return False
    return initials <= MAX_INITIALS


def validate_designer(raw: str) -> FieldCheck:
    designer = collapse_spaces(raw)
    ref = "03-title-block#designer"
    if len(designer) > DESIGNER_MAX:
        return _check(
            designer,
            Issue(
                "designer",
                "designer_length",
                f"The designer has at most {DESIGNER_MAX} characters.",
                ref,
                {"max": str(DESIGNER_MAX)},
            ),
        )
    if not _designer_ok(designer):
        return _check(
            designer,
            Issue(
                "designer",
                "designer_format",
                "Write the designer as a first name or initials, then the surname, names "
                "starting with a capital: Carlos Velazquez, C. Velazquez, "
                "J. C. Pérez, C. de la Torre.",
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
                {"material": material_display(value)},
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
    description: str = ""


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


def check_name_matches_sap(
    name: FieldCheck, sap_name: str, *, reserved: bool = False
) -> FieldCheck:
    """An existing design keeps SAP's name: a new revision can't rename the material
    (03-title-block#name-from-sap). Compared after the usual formatting. `reserved`: the
    number was just reserved (SAP has only revision A and no folder exists yet)."""
    expected = title_case(collapse_spaces(sap_name))
    if not name.value or name.value == expected:
        return name
    message = (
        f"This number was reserved with the name '{expected}', and a design keeps its SAP "
        "name. Use that name, or reserve a new number for the new name."
        if reserved
        else f"This design is called '{expected}' in SAP, and a new revision keeps that name. "
        "For a different name, ask for a new design number."
    )
    issue = Issue(
        "name",
        "name_differs_from_sap",
        message,
        "03-title-block#name-from-sap",
        {"expected": expected} | ({"variant": "reserved"} if reserved else {}),
    )
    return FieldCheck(name.value, (*name.errors, issue), name.warnings)


def validate_design_request(
    request: DesignRequest,
    *,
    existing_revisions: Iterable[str] = (),
    sap_status: str | None = None,
    block_reason: str | None = None,
    successor: str | None = None,
    sap_name: str | None = None,
    sap_reserved: bool = False,
) -> ValidationReport:
    """Check every field. Optional SAP fields are checked only when they are given;
    `sap_name` is the name of the design in SAP when the number exists there."""
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
    if request.description.strip():
        checks["description"] = validate_description(request.description)
    if sap_name is not None and request.name.strip():
        checks["name"] = check_name_matches_sap(checks["name"], sap_name, reserved=sap_reserved)
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
        description=value("description"),
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
                {"value": revision},
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
