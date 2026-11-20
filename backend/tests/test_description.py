"""The optional design description (decision 0019): rules, title block, audit, form check."""

import pytest

from app.db.session import audit_rows, get_engine
from app.designs import check_fields, create_design, normalize_payload
from app.kicad.renderer import TitleBlock, title_block_sexpr
from app.standards import validators as v
from tests.test_create_design import TODAY, request, settings  # noqa: F401 (fixture)


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("  Six-axis   stepper drive ", "Six-axis stepper drive"),
        ("Accionamiento de seis ejes, versión C", "Accionamiento de seis ejes, versión C"),
        ("x" * v.DESCRIPTION_MAX, "x" * v.DESCRIPTION_MAX),
    ],
)
def test_valid_descriptions_are_tidied(raw, value):
    check = v.validate_description(raw)
    assert check.ok and check.value == value


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("x" * (v.DESCRIPTION_MAX + 1), "description_length"),
        ("shows ${HL_DESIGNER} instead", "description_variable"),
        ("bell\x07", "description_characters"),
    ],
)
def test_invalid_descriptions_cite_the_manual(raw, code):
    [issue] = v.validate_description(raw).errors
    assert (issue.field, issue.code, issue.ref) == (
        "description",
        code,
        "03-title-block#description",
    )


def test_title_block_writes_comment_1_only_when_given():
    block = TitleBlock("HL-HW-26-0042", "A", "Bead Drill Controller", "2026-11-17", "C. V", "HW")
    assert "comment" not in title_block_sexpr(block)
    described = TitleBlock(**{**block.__dict__, "description": 'Drive "B" \\ (6 axes)'})
    assert '(comment 1 "Drive \\"B\\" \\\\ (6 axes)")' in title_block_sexpr(described)


def test_created_design_carries_the_description(settings):  # noqa: F811
    created = create_design(
        request(description="  Six-axis  stepper drive "),
        settings=settings,
        today=TODAY,
        export=False,
    )
    schematic = created.project.schematic_file.read_text(encoding="utf-8")
    assert '(comment 1 "Six-axis stepper drive")' in schematic
    [row] = audit_rows(get_engine(settings.data_dir))
    assert row.details["description"] == "Six-axis stepper drive"


def test_check_fields_checks_it_but_never_asks_for_it(tmp_path):
    def lookup(_):
        return None, None

    content = check_fields({"name": "Bead Drill Controller"}, tmp_path, lookup)
    assert "description" not in content["missing"]
    bad = check_fields({"description": "${TITLE}"}, tmp_path, lookup)
    assert [e["code"] for e in bad["errors"]] == ["description_variable"]


def test_the_card_shows_the_description_as_stored():
    assert normalize_payload({"description": "  two   spaces "})["description"] == "two spaces"
