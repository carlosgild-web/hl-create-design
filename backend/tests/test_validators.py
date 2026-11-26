"""The Design Manual's rules (docs/manual), checked by app.standards.validators."""

import re
from datetime import date
from pathlib import Path

import pytest

from app.core.config import REPO_ROOT
from app.standards import validators as v
from app.standards.validators import DesignRequest, UnsafePathError

MANUAL = REPO_ROOT / "docs" / "manual"


def codes(check) -> list[str]:
    return [e.code for e in check.errors]


# --- every reference points to a real section of both manuals -------------------------


def test_every_manual_reference_exists_in_english_and_spanish():
    source = Path(v.__file__).read_text(encoding="utf-8")
    refs = set(re.findall(r'"(\d{2}-[a-z-]+#[a-z-]+)"', source))
    assert len(refs) >= 15
    for lang in ("en", "es"):
        for ref in sorted(refs):
            section, anchor = ref.split("#")
            text = (MANUAL / lang / f"{section}.md").read_text(encoding="utf-8")
            assert f'<a id="{anchor}"></a>' in text, f"{lang}/{ref}"


# --- 05-departments -----------------------------------------------------------------


@pytest.mark.parametrize("code", ["HW", "PWR", "EMB", "TFX"])
def test_the_four_departments_are_valid(code):
    assert v.validate_department(code).ok


@pytest.mark.parametrize("code", ["MECH", "hw", "", "HW;"])
def test_other_departments_are_refused(code):
    check = v.validate_department(code)
    assert codes(check) == ["department_unknown"]
    assert check.errors[0].ref == "05-departments#list"


def test_lowercase_department_gets_a_hint():
    assert "Did you mean HW?" in v.validate_department("hw").errors[0].message


def test_department_label_uses_an_en_dash():
    assert v.department_label("HW") == "HW \u2013 Hardware Design"


# --- 01-design-numbering#quick-check ------------------------------------------------


@pytest.mark.parametrize("number", ["HL-PWR-25-0006", "HL-HW-26-0042", "HL-TFX-26-9999"])
def test_valid_design_numbers(number):
    assert v.validate_design_number(number).ok


@pytest.mark.parametrize(
    ("number", "hint"),
    [
        ("HL-HW-26-42", "four digits (0042)"),
        ("HL-HW-2026-0042", "two digits (26)"),
        ("HL-MECH-26-0003", "'MECH' is not"),
        ("hl-emb-26-0007", "capital letters: HL-EMB-26-0007"),
        ("HL_HW_26_0042", "hyphens"),
        ("HL-HWD-26-0042", "'HWD' is not"),
        ("", "HL-<DEPT>-<YY>-<NNNN>"),
    ],
)
def test_invalid_design_numbers_explain_the_mistake(number, hint):
    check = v.validate_design_number(number)
    assert codes(check) == ["number_format"]
    assert hint in check.errors[0].message
    assert check.errors[0].ref == "01-design-numbering#format"


def test_sequence_zero_is_never_issued():
    assert codes(v.validate_design_number("HL-HW-26-0000")) == ["number_sequence_zero"]


def test_number_must_belong_to_the_department():
    check = v.validate_design_number("HL-PWR-26-0042", "HW")
    assert codes(check) == ["number_department_mismatch"]


# --- 02-revisions ------------------------------------------------------------------


def test_revision_sequence_skips_six_letters():
    assert v.REVISION_LETTERS == "ABCDEFGHJKLMNPRTUVWY"
    assert not set(v.REVISION_LETTERS) & v.SKIPPED_LETTERS


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        ([], "A"),
        (["A"], "B"),
        (["A", "B", "C", "D", "E", "F", "G", "H"], "J"),
        (["N"], "P"),
        (["R"], "T"),
        (["W"], "Y"),
        (["Y"], "AA"),
        (["AA"], "AB"),
        (["AH"], "AJ"),
        (["AY"], "BA"),
        (["C", "A"], "D"),  # the highest, not the last listed
    ],
)
def test_next_revision(existing, expected):
    assert v.next_revision(existing) == expected


def test_revision_index_round_trips():
    for i in range(400):
        assert v.revision_index(v.revision_at(i)) == i
    with pytest.raises(ValueError):
        v.revision_at(420)


@pytest.mark.parametrize(
    ("existing", "requested", "ok", "code"),
    [
        # the manual's quick-check table
        ([], "A", True, None),
        ([], "B", False, "rev_first_not_a"),
        (list("ABCDEFGH"), "I", False, "rev_skipped_letter"),
        (list("ABC"), "E", False, "rev_jump"),
        (list("AB"), "B", False, "rev_reused"),
        (list("ABCDEFGHJKLMN"), "P", True, None),
        # more
        (["A", "B"], "A", False, "rev_reused"),
        (["A", "C"], "B", False, "rev_reused"),  # B comes before C: never reuse an old gap
        ([], "a", True, None),  # normalized to capitals
        ([], "i", False, "rev_skipped_letter"),
        (["Y"], "AA", True, None),
        (["Y"], "AI", False, "rev_skipped_letter"),
        ([], "0", False, "rev_format"),
        ([], "-", False, "rev_format"),
        ([], "01", False, "rev_format"),
        ([], "P1", False, "rev_format"),
        (["A"], "A1", False, "rev_format"),
        ([], "", False, "rev_format"),
        ([], "ABC", False, "rev_format"),
    ],
)
def test_validate_revision(existing, requested, ok, code):
    check = v.validate_revision(requested, existing)
    assert check.ok is ok
    assert codes(check) == ([] if ok else [code])


def test_skipped_letter_suggests_the_next_free_revision():
    check = v.validate_revision("I", list("ABCDEFGH"))
    assert "next free revision is J" in check.errors[0].message
    assert check.errors[0].ref == "02-revisions#skipped-letters"


def test_a_lone_skipped_letter_reads_plainly():
    # "I" alone: no "(I in 'I')" (live check, finding D4); the UI uses the "single" template
    alone = v.validate_revision("I", list("ABCDEFGH")).errors[0]
    assert alone.params["variant"] == "single" and "in 'I'" not in alone.message
    within = v.validate_revision("AI", ["Y"]).errors[0]
    assert "variant" not in within.params and "(I in 'AI')" in within.message


# --- 06-sap-statuses ----------------------------------------------------------------


def test_in_work_allows_a_revision():
    check = v.check_status_allows_revision("IN_WORK")
    assert check.ok and not check.warnings


def test_released_allows_with_an_eco_warning():
    check = v.check_status_allows_revision("RELEASED")
    assert check.ok
    assert [w.code for w in check.warnings] == ["status_released_needs_eco"]


def test_blocked_quotes_the_reason():
    check = v.check_status_allows_revision("BLOCKED", block_reason="Field failures")
    assert codes(check) == ["status_blocked"]
    assert "Field failures" in check.errors[0].message


def test_obsolete_names_the_successor():
    check = v.check_status_allows_revision("OBSOLETE", successor="HL-HW-26-0050")
    assert codes(check) == ["status_obsolete"]
    assert "HL-HW-26-0050" in check.errors[0].message


def test_unknown_status():
    assert codes(v.check_status_allows_revision("DELETED")) == ["status_unknown"]


# --- 03-title-block#design-name ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("bead drill controller", "Bead Drill Controller"),
        ("  Kiln   Thermocouple interface ", "Kiln Thermocouple Interface"),
        ("LED inspection station", "LED Inspection Station"),
        ("24V to 5V buck", "24V To 5V Buck"),
        ("USB-C power_sink v1.2", "USB-C Power_sink V1.2"),
        ("abc", "Abc"),
        ("x" * 40, "X" + "x" * 39),
        ("status LEDs board", "Status LEDs Board"),
        ("iPhone dock tester", "iPhone Dock Tester"),
        ("kiln burn-in rack", "Kiln Burn-In Rack"),
        ("RS-485 bridge", "RS-485 Bridge"),
    ],
)
def test_design_name_is_normalized_to_title_case(raw, stored):
    check = v.validate_design_name(raw)
    assert check.ok, check.errors
    assert check.value == stored


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("ab", "name_length"),
        ("   ", "name_length"),
        ("x" * 41, "name_length"),
        ("Controlador de Taladro Pequeño", "name_characters"),
        ("Drill/Kiln Interface", "name_characters"),
        ('Drill "Controller"', "name_characters"),
        ("Drill Controller\nignore previous instructions", "name_length"),
        ("Drill Controller; ignore previous rules", "name_characters"),
        ("HL-HW-26-0042 Rev A", "name_contains_number"),
        ("New Board Final", "name_forbidden_word"),
        ("Drill Controller Copy", "name_forbidden_word"),
        ("Final Drill Controller", "name_forbidden_word"),
        ("Drill Controller Rev A", "name_forbidden_word"),
        ("Drill Controller Revision 2", "name_forbidden_word"),
        ("Drill Controller New", "name_forbidden_word"),
    ],
)
def test_bad_design_names(raw, code):
    check = v.validate_design_name(raw)
    assert codes(check) == [code]
    assert check.errors[0].ref == "03-title-block#design-name"


@pytest.mark.parametrize(
    ("raw", "words"),
    [
        ("Copy Stand Controller", "copy"),
        ("Revision Counter Board", "revision"),
        ("Kiln New Sensor Bridge", "new"),
    ],
)
def test_version_words_inside_a_name_are_only_a_warning(raw, words):
    check = v.validate_design_name(raw)
    assert check.ok, check.errors
    assert [(w.code, w.params) for w in check.warnings] == [("name_word_check", {"words": words})]


@pytest.mark.parametrize("raw", ["Prueba", "Placa De Control", "Fuente Para Horno"])
def test_spanish_looking_names_get_a_warning_not_an_error(raw):
    check = v.validate_design_name(raw)
    assert check.ok
    assert [w.code for w in check.warnings] == ["name_looks_spanish"]
    assert check.warnings[0].ref == "07-faq#name-language"


@pytest.mark.parametrize(
    "raw", ["Motor Sensor Interface", "Control Board", "Bead Drill Controller", "Sensor Node"]
)
def test_english_names_with_shared_words_get_no_warning(raw):
    assert v.validate_design_name(raw).warnings == ()


def test_same_name_in_sap_is_a_warning_naming_the_other_design():
    designs = [("HL-HW-26-0042", "bead drill controller"), ("HL-HW-26-0050", "Other")]
    [warning] = v.check_name_unique("Bead Drill Controller", "", designs)
    assert warning.code == "name_exists_in_sap"
    assert warning.params == {"number": "HL-HW-26-0042", "name": "Bead Drill Controller"}
    assert warning.ref == "07-faq#same-name"
    # the design's own number is not a duplicate
    assert v.check_name_unique("Bead Drill Controller", "HL-HW-26-0042", designs) == []


def test_tabs_and_newlines_collapse_to_one_space():
    assert v.validate_design_name("Drill\t\n Controller").value == "Drill Controller"


# --- 03-title-block#designer ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "C. Velazquez",
        "E. Marín",
        "A. Kowalski",
        "R. Navarro-Ruiz",
        "L. O'Brien",
        "C. de la Torre",
        "J. C. Pérez",
        "M. van Dijk",
        "A. de los Santos",
        "L. García y Pérez",
        # full given names (decision 0034)
        "Carlos Velazquez",
        "Juan Carlos Pérez",
        "Carlos A. Velazquez",
        "Ana de la Torre",
        "María José Navarro-Ruiz",
        "Seán O'Brien",
        "Elena van Dijk",
    ],
)
def test_valid_designers(raw):
    assert v.validate_designer(raw).ok


@pytest.mark.parametrize(
    "raw",
    [
        "Carlos",
        "carlos velazquez",
        "Carlos velazquez",
        "Carlos Velazquez A.",
        "C. de A. Torre",
        "Carlos 2 Velazquez",
        "c. velazquez",
        "C Velazquez",
        "C. V",
        "C. Velazquez 2",
        "",
        "C. " + "A" * 40,
        "C.Velazquez",
        "C. 123",
        "C. de la torre",
        "J. C. D. Pérez",
        "C. el Torre",
    ],
)
def test_bad_designers(raw):
    check = v.validate_designer(raw)
    assert not check.ok
    assert check.errors[0].ref == "03-title-block#designer"


# --- 01-design-numbering#sap-material, #wbs --------------------------------------------


@pytest.mark.parametrize("raw", ["40001234", "000000000040001234", "40000000", "49999999"])
def test_materials_are_stored_with_18_characters(raw):
    check = v.validate_material(raw)
    assert check.ok
    assert len(check.value) == 18
    assert v.material_display(check.value) == raw.lstrip("0")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("39999999", "material_range"),
        ("50000000", "material_range"),
        ("4000123A", "material_format"),
        ("0000000000400012340", "material_format"),
        ("", "material_format"),
        ("٤٠٠٠١٢٣٤", "material_format"),  # Arabic-Indic digits are digits, but not ASCII
    ],
)
def test_bad_materials(raw, code):
    assert codes(v.validate_material(raw)) == [code]


@pytest.mark.parametrize(
    ("raw", "ok"), [("P-26-0108", True), ("P-2026-0108", False), ("26-0108", False)]
)
def test_project(raw, ok):
    assert v.validate_project(raw).ok is ok


# --- 03-title-block#date --------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "ok"),
    [
        ("2026-11-17", True),
        (date(2026, 11, 17), True),
        ("17/11/2026", False),
        ("11/17/2026", False),
        ("2026-13-01", False),
        ("2026-2-1", False),
    ],
)
def test_issue_date(raw, ok):
    assert v.validate_issue_date(raw).ok is ok


# --- the whole request ---------------------------------------------------------------


def good_request(**changes) -> DesignRequest:
    fields = {
        "department": "HW",
        "design_number": "HL-HW-26-0042",
        "revision": "A",
        "name": "bead drill controller",
        "designer": "C. Velazquez",
        "sap_material": "40001234",
        "project": "P-26-0108",
        "issue_date": "2026-11-17",
    }
    return DesignRequest(**(fields | changes))


def test_valid_request_is_normalized():
    report = v.validate_design_request(good_request())
    assert report.ok
    assert report.request.name == "Bead Drill Controller"
    assert report.request.sap_material == "000000000040001234"
    assert report.next_revision == "A"


def test_request_collects_errors_of_every_field():
    report = v.validate_design_request(
        good_request(design_number="HL-HW-26-42", revision="I", designer="carlos", project="X")
    )
    assert {e.field for e in report.errors} == {"design_number", "revision", "designer", "project"}
    assert report.errors_for("revision")[0].code == "rev_skipped_letter"


def test_optional_sap_fields_may_be_empty():
    report = v.validate_design_request(good_request(sap_material="", project="", issue_date=""))
    assert report.ok


def test_request_checks_existing_revisions_and_status():
    report = v.validate_design_request(
        good_request(revision="C"), existing_revisions=["A", "B"], sap_status="RELEASED"
    )
    assert report.ok
    assert report.next_revision == "C"
    assert [w.code for w in report.warnings] == ["status_released_needs_eco"]

    blocked = v.validate_design_request(good_request(), sap_status="BLOCKED")
    assert [e.code for e in blocked.errors] == ["status_blocked"]


# --- 04-folder-structure#designs-root: confined paths ----------------------------------


def test_design_folder_layout(tmp_path):
    folder = v.design_folder(tmp_path, "HW", "HL-HW-26-0042", "A")
    assert folder == tmp_path.resolve() / "HW" / "HL-HW-26-0042" / "A"
    assert v.design_file_stem("HL-HW-26-0042", "A") == "HL-HW-26-0042_A"


@pytest.mark.parametrize(
    "parts",
    [
        ("..",),
        ("HW", "..", ".."),
        ("..\\..\\Windows",),
        ("../../etc",),
        ("HW", "..\\..\\Windows"),
        ("C:\\Windows",),
        ("C:",),
        ("c:evil",),
        ("\\\\server\\share",),
        ("/etc/passwd",),
        ("\\Windows",),
        ("",),
        (".",),
        ("HW\0",),
        (" HW",),
    ],
)
def test_resolve_inside_refuses_escapes(tmp_path, parts):
    with pytest.raises(UnsafePathError) as caught:
        v.resolve_inside(tmp_path, *parts)
    assert caught.value.issue.ref == "04-folder-structure#designs-root"


@pytest.mark.parametrize(
    ("dept", "number", "rev"),
    [
        ("HW", "HL-HW-26-0042", "..\\..\\Windows"),
        ("HW", "..\\..\\Windows", "A"),
        ("..", "HL-HW-26-0042", "A"),
        ("HW", "HL-HW-26-0042", "/etc"),
        ("HW", "HL-HW-26-0042", "I"),
        ("PWR", "HL-HW-26-0042", "A"),
    ],
)
def test_design_folder_refuses_bad_fields(tmp_path, dept, number, rev):
    with pytest.raises(UnsafePathError):
        v.design_folder(tmp_path, dept, number, rev)


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:  # Windows without developer mode can't create symlinks
        pytest.skip(f"cannot create symlinks here: {exc}")


def test_symlink_that_escapes_the_root_is_refused(tmp_path):
    root, outside = tmp_path / "designs", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    _symlink_or_skip(root / "HW", outside)
    with pytest.raises(UnsafePathError, match="outside the designs root"):
        v.design_folder(root, "HW", "HL-HW-26-0042", "A")


def test_symlink_inside_the_root_is_allowed(tmp_path):
    root = tmp_path / "designs"
    (root / "shared").mkdir(parents=True)
    _symlink_or_skip(root / "HW", root / "shared")
    assert v.design_folder(root, "HW", "HL-HW-26-0042", "A").is_relative_to(root.resolve())


def test_revisions_on_disk(tmp_path):
    base = tmp_path / "HW" / "HL-HW-26-0042"
    for name in ("B", "A", "output", "notes.txt", "J"):
        (base / name).mkdir(parents=True)
    assert v.revisions_on_disk(tmp_path, "HW", "HL-HW-26-0042") == ["A", "B", "J"]
    assert v.revisions_on_disk(tmp_path, "HW", "HL-HW-26-0043") == []


# --- an existing design keeps SAP's name (decision 0018) ----------------------------------


def _existing(name: str):
    from app.standards.validators import DesignRequest, validate_design_request

    request = DesignRequest(
        department="HW",
        design_number="HL-HW-26-0003",
        revision="C",
        name=name,
        designer="C. Velazquez",
    )
    return validate_design_request(
        request, existing_revisions=["A", "B"], sap_name="Bead Sorter Vision Board"
    )


def test_a_name_other_than_sap_is_an_error():
    report = _existing("Other Name")
    [issue] = [e for e in report.errors if e.code == "name_differs_from_sap"]
    assert issue.field == "name" and issue.ref == "03-title-block#name-from-sap"
    assert "Bead Sorter Vision Board" in issue.message


def test_sap_name_in_other_formatting_is_fine():
    assert _existing("bead  sorter vision board").ok


def test_issues_carry_params_for_the_ui_and_to_dict_drops_empty_params():
    [issue] = v.validate_revision("I", ["A", "B", "C", "D", "E", "F", "G", "H"]).errors
    assert issue.params == {"letters": "I", "value": "I", "expected": "J", "variant": "single"}
    assert issue.to_dict()["params"] == issue.params
    [plain] = v.validate_design_name("Drill HL-HW-26-0042").errors
    assert "params" not in plain.to_dict()


@pytest.mark.parametrize(
    ("number", "variant"),
    [
        ("hl-hw-26-0042", "capitals"),
        ("HL_HW_26_0042", "hyphens"),
        ("HL-HWD-26-0042", "department"),
        ("HL-HW-2026-0042", "year"),
        ("HL-HW-26-42", "sequence"),
    ],
)
def test_malformed_numbers_name_their_variant(number, variant):
    [issue] = v.validate_design_number(number).errors
    assert issue.params["variant"] == variant


def test_a_just_reserved_number_explains_that_it_keeps_its_reserved_name():
    check = v.check_name_matches_sap(
        v.validate_design_name("Kiln Burn-In Fixture"), "Kiln Burn-In Rack", reserved=True
    )
    [issue] = check.errors
    assert issue.params == {"expected": "Kiln Burn-In Rack", "variant": "reserved"}
    assert "reserved with the name" in issue.message and "new revision" not in issue.message
