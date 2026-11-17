"""Reserving a number: next sequence per department and year, atomic, never reused."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.db import Database, ReservationError
from app.odata import INVALID_REQUEST, odata_date
from tests.conftest import (
    TODAY,
    assert_sap_error,
    fetch_token,
    make_settings,
    reserve,
    svc,
)

FIRST_NEW_MATERIAL = 40_001_236  # highest seeded material + 1


def test_reserve_returns_201_with_the_next_number_material_and_wbs(client):
    response = reserve(client, fetch_token(client))

    assert response.status_code == 201, response.text
    d = response.json()["d"]
    assert d["DesignNumber"] == "HL-HW-26-0042"
    assert d["Material"] == f"{FIRST_NEW_MATERIAL:018d}"
    assert d["Wbs"] == "P-26-0108"  # HW default project for 2026
    assert d["Status"] == "IN_WORK"
    assert d["CurrentRevision"] == "A"
    assert d["Name"] == "Bead Drill Controller"
    assert d["CreatedBy"] == "C. Velazquez"
    assert d["CreatedOn"] == odata_date(TODAY)
    assert response.headers["location"] == d["__metadata"]["uri"]


def test_reserved_design_can_be_read_back_with_revision_a(client):
    location = reserve(client, fetch_token(client)).headers["location"]

    d = client.get(location + "?$expand=Revisions").json()["d"]

    assert d["DesignNumber"] == "HL-HW-26-0042"
    assert [r["Revision"] for r in d["Revisions"]["results"]] == ["A"]
    assert d["Revisions"]["results"][0]["CreatedOn"] == odata_date(TODAY)


def test_sequence_increments_per_department_and_material_is_global(client):
    token = fetch_token(client)

    first = reserve(client, token).json()["d"]
    second = reserve(client, token, Name="LED Status Panel").json()["d"]
    power = reserve(client, token, Department="PWR", Name="Kiln Heater Driver").json()["d"]

    assert first["DesignNumber"] == "HL-HW-26-0042"
    assert second["DesignNumber"] == "HL-HW-26-0043"
    assert power["DesignNumber"].startswith("HL-PWR-26-")
    assert power["Wbs"] == "P-26-0112"
    materials = [int(d["Material"]) for d in (first, second, power)]
    assert materials == [FIRST_NEW_MATERIAL, FIRST_NEW_MATERIAL + 1, FIRST_NEW_MATERIAL + 2]


def test_reserved_numbers_appear_in_the_filtered_list(client):
    reserve(client, fetch_token(client))

    response = client.get(svc("/DesignSet?$filter=DesignNumber eq 'HL-HW-26-0042'"))

    assert [d["DesignNumber"] for d in response.json()["d"]["results"]] == ["HL-HW-26-0042"]


def test_name_is_stored_as_sent_without_surrounding_spaces(client):
    # Title case is the backend's rule (validators.py); SAP stores what it gets.
    d = reserve(client, fetch_token(client), Name="  bead drill controller ").json()["d"]

    assert d["Name"] == "bead drill controller"


def test_invalid_bodies_are_400_and_consume_no_number(client):
    token = fetch_token(client)
    long_name = "X" * 41
    bad_requests = [
        {"Name": long_name},
        {"Name": "   "},
        {"Department": ""},
        {"CreatedBy": ""},
    ]
    for body in bad_requests:
        assert_sap_error(reserve(client, token, **body), 400, INVALID_REQUEST)
    missing = client.post(
        svc("/DesignSet"), json={"Department": "HW"}, headers={"x-csrf-token": token}
    )
    assert_sap_error(missing, 400, INVALID_REQUEST)
    not_json = client.post(svc("/DesignSet"), content="nope", headers={"x-csrf-token": token})
    assert_sap_error(not_json, 400, INVALID_REQUEST)

    assert reserve(client, token).json()["d"]["DesignNumber"] == "HL-HW-26-0042"


def test_unknown_department_is_rejected_by_sap(client):
    token = fetch_token(client)

    error = assert_sap_error(reserve(client, token, Department="MECH"), 400, "ZHL_PLM/010")

    assert "MECH" in error["message"]["value"]
    assert reserve(client, token).json()["d"]["DesignNumber"] == "HL-HW-26-0042"


def test_numbers_sent_by_the_client_are_ignored(client):
    d = reserve(
        client,
        fetch_token(client),
        DesignNumber="HL-HW-26-0001",
        Material="000000000040000001",
        Status="RELEASED",
    ).json()["d"]

    assert d["DesignNumber"] == "HL-HW-26-0042"
    assert d["Material"] == f"{FIRST_NEW_MATERIAL:018d}"
    assert d["Status"] == "IN_WORK"


def test_year_without_a_default_project_is_rejected(make_client, tmp_path):
    client = make_client(make_settings(tmp_path, sap_today=date(2027, 1, 4)))

    error = assert_sap_error(reserve(client, fetch_token(client)), 400, "ZHL_PLM/011")

    assert "Product Engineering" in error["message"]["value"]


# --- the database layer ------------------------------------------------------------------


def test_new_year_starts_the_sequence_at_0001(db):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO default_wbs (department, year, wbs) VALUES ('HW', 2027, 'P-27-0003')"
        )

    number = db.reserve("HW", "Bead Drill Controller", "C. Velazquez", date(2027, 1, 4))

    assert number == "HL-HW-27-0001"
    assert db.get_design(number)["wbs"] == "P-27-0003"
    # 2026 is untouched.
    assert db.reserve("HW", "LED Status Panel", "C. Velazquez", TODAY) == "HL-HW-26-0042"


def test_concurrent_reservations_never_share_a_number(db):
    def one(i: int) -> str:
        return db.reserve("HW", f"Board {i:02d}", "C. Velazquez", TODAY)

    with ThreadPoolExecutor(max_workers=10) as pool:
        numbers = list(pool.map(one, range(20)))

    assert sorted(numbers) == [f"HL-HW-26-{seq:04d}" for seq in range(42, 62)]
    materials = sorted(int(db.get_design(n)["material"]) for n in numbers)
    assert materials == list(range(FIRST_NEW_MATERIAL, FIRST_NEW_MATERIAL + 20))


def test_state_survives_a_restart_and_the_seed_loads_once(settings, db, seed_designs):
    db.reserve("HW", "Bead Drill Controller", "C. Velazquez", TODAY)

    restarted = Database(settings.db_path)
    restarted.init()

    assert len(restarted.list_designs({})) == len(seed_designs) + 1
    assert restarted.reserve("HW", "LED Status Panel", "C. Velazquez", TODAY) == "HL-HW-26-0043"


def test_a_failed_reservation_rolls_back_everything(db):
    # Material range exhausted: the sequence must not move either.
    with db.transaction() as conn:
        conn.execute("UPDATE material_range SET last_material = 49999999")

    try:
        db.reserve("HW", "Bead Drill Controller", "C. Velazquez", TODAY)
    except ReservationError as exc:
        assert exc.code == "ZHL_PLM/013"
    else:
        raise AssertionError("expected ReservationError")

    with db.connect() as conn:
        row = conn.execute(
            "SELECT last_seq FROM number_ranges WHERE department = 'HW' AND year = 2026"
        ).fetchone()
    assert row["last_seq"] == 41


def test_exhausted_number_range_is_rejected(db):
    with db.transaction() as conn:
        conn.execute(
            "UPDATE number_ranges SET last_seq = 9999 WHERE department = 'HW' AND year = 2026"
        )

    try:
        db.reserve("HW", "Bead Drill Controller", "C. Velazquez", TODAY)
    except ReservationError as exc:
        assert exc.code == "ZHL_PLM/012"
    else:
        raise AssertionError("expected ReservationError")
