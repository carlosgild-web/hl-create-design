"""Every rule message reaches the user in their language (decision 0022).

The validators send `code` + `params` with an English `message`; the UI renders the
template `issue.<code>[.<variant>]` from `frontend/src/i18n/messages.ts`. These tests read
that file and check: every code in `validators.py` has an EN and an ES template, and every
issue the validators actually produce finds its template and fills all its placeholders.
"""

from __future__ import annotations

import re

import pytest

from app.core.config import REPO_ROOT
from app.designs import pdf_not_exported
from app.kicad.exporter import ExportError
from app.standards import validators as v

MESSAGES = (REPO_ROOT / "frontend" / "src" / "i18n" / "messages.ts").read_text(encoding="utf-8")
# The modules that build user-facing issues.
SOURCES = "".join(
    (REPO_ROOT / "backend" / "app" / path).read_text(encoding="utf-8")
    for path in ("standards/validators.py", "designs.py")
)
_ENTRY_RE = re.compile(r"'(issue\.[a-z_.]+)': '((?:[^'\\]|\\.)*)'")
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _templates(start: str, end: str) -> dict[str, str]:
    block = MESSAGES[MESSAGES.index(start) :]
    block = block[: block.index(end)]
    return dict(_ENTRY_RE.findall(block))


TEMPLATES = {
    "en": _templates("const en = {", "} as const"),
    "es": _templates("const es: Record<MessageKey, string> = {", "\n}\n"),
}
# `Issue("field", "code", ...)`, also `Issue("field", "code_a" if x else "code_b", ...)`.
_CODE_RE = re.compile(r'Issue\(\s*"[a-z_]+",\s*"([a-z_]+)"(?:\s+if \w+ else "([a-z_]+)")?')
CODES = {code for pair in _CODE_RE.findall(SOURCES) for code in pair if code}


def _key(issue: v.Issue) -> str:
    variant = issue.params.get("variant")
    return f"issue.{issue.code}.{variant}" if variant else f"issue.{issue.code}"


def produced() -> list[v.Issue]:
    """One of every issue the validators can produce, variants included."""
    existing = ["A", "B", "C"]
    checks = [
        v.validate_department("hw"),
        v.validate_department("XYZ"),
        *(v.validate_design_number(n) for n in ("hl-hw-26-0042", "HL HW 26 0042")),
        *(v.validate_design_number(n) for n in ("HL-ABC-26-0042", "HL-HW-2026-0042")),
        v.validate_design_number("HL-HW-26-42"),
        v.validate_design_number("nonsense"),
        v.validate_design_number("HL-HW-26-0000"),
        v.validate_design_number("HL-HW-26-0042", "PWR"),
        v.check_known_in_sap("HL-HW-26-0099", found=False),
        v.validate_revision("A1"),
        v.validate_revision("I", existing),
        v.validate_revision("B", existing),
        v.validate_revision("A", ["A", "B", "C", "D"][1:]),
        v.validate_revision("C"),
        v.validate_revision("F", existing),
        v.check_status_allows_revision("RELEASED"),
        v.check_status_allows_revision("BLOCKED"),
        v.check_status_allows_revision("BLOCKED", block_reason="Field returns"),
        v.check_status_allows_revision("OBSOLETE"),
        v.check_status_allows_revision("OBSOLETE", successor="HL-HW-26-0050"),
        v.check_status_allows_revision("ARCHIVED"),
        v.validate_design_name("Controlador Pequeño"),
        v.validate_design_name("ab"),
        v.validate_design_name("Drill HL-HW-26-0042"),
        v.validate_design_name("Drill Controller Copy"),
        v.validate_design_name("Copy Stand Controller"),
        v.validate_design_name("Prueba"),
        v.check_name_matches_sap(v.validate_design_name("Other Name"), "Bead Drill Controller"),
        v.check_name_matches_sap(v.validate_design_name("Other"), "Kiln Rack", reserved=True),
        v.validate_description("bell\x07here"),
        v.validate_description("${COMMENT1}"),
        v.validate_description("x" * 61),
        v.validate_designer("C. " + "A" * 40),
        v.validate_designer("carlos"),
        v.validate_material("12ab"),
        v.validate_material("50000000"),
        v.validate_project("P-1"),
        v.validate_issue_date("17/11/2026"),
    ]
    issues = [i for c in checks for i in (*c.errors, *c.warnings)]
    issues += v.check_name_unique(
        "Bead Drill Controller", "", [("HL-HW-26-0042", "Bead Drill Controller")]
    )
    issues.append(v.UnsafePathError("outside").issue)
    missing = ExportError("kicad-cli not found")
    missing.__cause__ = FileNotFoundError("kicad-cli")
    issues += [pdf_not_exported(missing), pdf_not_exported(ExportError("exit code 1"))]
    return issues


ISSUES = produced()


def test_the_battery_covers_every_code_the_backend_builds():
    assert CODES, "no codes found in validators.py"
    assert {i.code for i in ISSUES} == CODES


@pytest.mark.parametrize("lang", ["en", "es"])
def test_every_code_has_a_template(lang):
    missing = sorted(f"issue.{c}" for c in CODES if f"issue.{c}" not in TEMPLATES[lang])
    assert not missing


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("issue", ISSUES, ids=lambda i: _key(i))
def test_every_issue_finds_its_template_and_fills_every_placeholder(lang, issue):
    template = TEMPLATES[lang].get(_key(issue))
    assert template, f"no {lang} template {_key(issue)}"
    needed = set(_PLACEHOLDER_RE.findall(template)) - {"variant"}
    assert needed <= set(issue.params), (needed - set(issue.params), template)


def test_english_and_spanish_have_the_same_keys():
    assert set(TEMPLATES["en"]) == set(TEMPLATES["es"])
