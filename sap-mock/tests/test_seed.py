"""The seed data must follow the company rules in docs/manual (sections in comments).

The mock SAP doesn't import the backend (decision 0004), so the rules are written out
here. backend/app/standards/validators.py is the authoritative implementation (Phase 3).
"""

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parents[1] / "seed"
TODAY = date(2026, 11, 17)  # seed snapshot date

# 01-design-numbering#format, #sap-material, #wbs
NUMBER_RE = re.compile(r"^HL-(HW|PWR|EMB|TFX)-(\d{2})-(\d{4})$")
MATERIAL_MIN, MATERIAL_MAX = 40_000_000, 49_999_999
WBS_RE = re.compile(r"^P-\d{2}-\d{4}$")
# 02-revisions#sequence, #skipped-letters
REVISION_LETTERS = "ABCDEFGHJKLMNPRTUVWY"
SKIPPED_LETTERS = set("IOQSXZ")
# 03-title-block#design-name, #designer
NAME_RE = re.compile(r"^[A-Za-z0-9 ._-]{3,40}$")
DESIGNER_RE = re.compile(r"^[A-ZÁÉÍÓÚÑ]\. [A-ZÁÉÍÓÚÑ][A-Za-zÀ-ÿ' -]+$")
# 06-sap-statuses#overview
STATUSES = {"IN_WORK", "RELEASED", "BLOCKED", "OBSOLETE"}


def _load(name: str) -> dict:
    return json.loads((SEED / name).read_text(encoding="utf-8"))


DEPARTMENTS = _load("departments.json")["departments"]
DESIGNS = _load("designs.json")["designs"]
BY_NUMBER = {d["design_number"]: d for d in DESIGNS}


def title_case(name: str) -> str:
    """03-title-block#design-name: capitalise each word, keep words written in capitals."""
    words = name.split()
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:].lower() for w in words)


def design_ids(design: dict) -> str:
    return design["design_number"]


# --- the whole data set ----------------------------------------------------------


def test_departments_are_the_four_of_the_manual():
    assert [d["code"] for d in DEPARTMENTS] == ["HW", "PWR", "EMB", "TFX"]
    for dept in DEPARTMENTS:
        assert dept["name_en"] and dept["name_es"]
        assert DESIGNER_RE.match(dept["lead"])
        for year, wbs in dept["default_wbs"].items():
            assert WBS_RE.match(wbs)
            assert wbs[2:4] == year[2:], f"{dept['code']} {year}: {wbs} has the wrong year"


def test_thirty_designs_with_unique_numbers_and_materials():
    assert len(DESIGNS) == 30
    assert len(BY_NUMBER) == 30
    assert len({d["material"] for d in DESIGNS}) == 30


def test_every_department_and_status_is_covered():
    assert {d["department"] for d in DESIGNS} == {"HW", "PWR", "EMB", "TFX"}
    assert {d["status"] for d in DESIGNS} == STATUSES
    for dept in ("HW", "PWR", "EMB", "TFX"):
        assert {d["status"] for d in DESIGNS if d["department"] == dept} == STATUSES, dept


def test_sequence_follows_reservation_order_per_department_and_year():
    # 01-design-numbering#sequence: SAP issues the next free value.
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for d in DESIGNS:
        _, dept, yy, _ = d["design_number"].split("-")
        groups[(dept, yy)].append(d)
    for key, designs in groups.items():
        by_number = sorted(designs, key=lambda d: d["design_number"])
        by_date = sorted(designs, key=lambda d: d["created_on"])
        assert by_number == by_date, f"{key}: numbers were not issued in date order"


def test_default_wbs_is_used_for_each_department_and_year_seeded():
    default = {d["code"]: d["default_wbs"] for d in DEPARTMENTS}
    for d in DESIGNS:
        assert "20" + d["design_number"].split("-")[2] in default[d["department"]]


def test_seed_covers_the_demo_scenarios():
    # Next HW number in 2026 is HL-HW-26-0042, the example used across the docs.
    hw_26 = [d for d in DESIGNS if d["design_number"].startswith("HL-HW-26-")]
    assert max(int(d["design_number"][-4:]) for d in hw_26) == 41
    # A design whose next revision skips a letter (H -> J).
    assert any(d["status"] == "IN_WORK" and d["revisions"][-1]["rev"] == "H" for d in DESIGNS)
    # A design whose history already skipped I.
    assert any("J" in [r["rev"] for r in d["revisions"]] for d in DESIGNS)


# --- each design -------------------------------------------------------------------


@pytest.mark.parametrize("design", DESIGNS, ids=design_ids)
def test_design_number_format_and_year(design):
    match = NUMBER_RE.match(design["design_number"])
    assert match, "01-design-numbering#format"
    dept, yy, seq = match.groups()
    assert dept == design["department"]
    assert int(seq) >= 1
    # 01-design-numbering#year: YY is the reservation year.
    assert design["created_on"][2:4] == yy


@pytest.mark.parametrize("design", DESIGNS, ids=design_ids)
def test_material_and_wbs(design):
    material = design["material"]
    assert len(material) == 18 and material.isdigit(), "18 digits with leading zeros"
    assert MATERIAL_MIN <= int(material) <= MATERIAL_MAX, "electronic assemblies range"
    assert WBS_RE.match(design["wbs"])


@pytest.mark.parametrize("design", DESIGNS, ids=design_ids)
def test_name_and_designer(design):
    name = design["name"]
    assert NAME_RE.match(name), "03-title-block#design-name: 3-40 allowed characters"
    assert name == title_case(name), "stored in title case"
    assert name == " ".join(name.split()), "no leading, trailing or repeated spaces"
    assert design["design_number"] not in name
    assert DESIGNER_RE.match(design["created_by"]), "03-title-block#designer"


@pytest.mark.parametrize("design", DESIGNS, ids=design_ids)
def test_revisions_follow_the_sequence(design):
    revs = [r["rev"] for r in design["revisions"]]
    # 02-revisions#first-revision, #next-revision, #skipped-letters
    assert revs == list(REVISION_LETTERS[: len(revs)])
    assert not SKIPPED_LETTERS & set(revs)

    dates = [date.fromisoformat(r["created_on"]) for r in design["revisions"]]
    assert dates[0] == date.fromisoformat(design["created_on"])
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)
    assert dates[-1] <= TODAY
    for r in design["revisions"]:
        assert DESIGNER_RE.match(r["created_by"])


@pytest.mark.parametrize("design", DESIGNS, ids=design_ids)
def test_status_details(design):
    status = design["status"]
    assert status in STATUSES
    # 06-sap-statuses#blocked: SAP shows the reason.
    assert bool(design["block_reason"]) == (status == "BLOCKED")
    # 06-sap-statuses#obsolete: SAP names the successor.
    assert bool(design["successor"]) == (status == "OBSOLETE")
    if status == "OBSOLETE":
        successor = BY_NUMBER[design["successor"]]
        assert successor["status"] != "OBSOLETE"
        assert successor["department"] == design["department"]
        assert successor["created_on"] > design["created_on"]
