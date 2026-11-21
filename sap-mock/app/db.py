"""SQLite storage for the mock SAP: departments, designs, revisions and number ranges.

The database is created and seeded from `seed/*.json` the first time the service starts;
delete the file to reset the demo. A reservation takes the next number of the department's
number range and the next material in one `BEGIN IMMEDIATE` transaction, so concurrent
requests never get the same number, and a failed reservation consumes nothing.
"""

import json
import sqlite3
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"

FIRST_REVISION = "A"
REVISION_LETTERS = "ABCDEFGHJKLMNPRTUVWY"  # I, O, Q, S, X and Z are never used
REVISABLE_STATUSES = frozenset({"IN_WORK", "RELEASED"})
SEQUENCE_MAX = 9_999  # NNNN in HL-<DEPT>-<YY>-<NNNN>
MATERIAL_MAX = 49_999_999  # end of the electronic assemblies range

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    code    TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    lead    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS default_wbs (
    department TEXT NOT NULL REFERENCES departments(code),
    year       INTEGER NOT NULL,
    wbs        TEXT NOT NULL,
    PRIMARY KEY (department, year)
);
CREATE TABLE IF NOT EXISTS designs (
    design_number TEXT PRIMARY KEY,
    department    TEXT NOT NULL REFERENCES departments(code),
    name          TEXT NOT NULL,
    status        TEXT NOT NULL
                  CHECK (status IN ('IN_WORK', 'RELEASED', 'BLOCKED', 'OBSOLETE')),
    material      TEXT NOT NULL UNIQUE,
    wbs           TEXT NOT NULL,
    created_on    TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    block_reason  TEXT,
    successor     TEXT
);
CREATE TABLE IF NOT EXISTS revisions (
    design_number TEXT NOT NULL REFERENCES designs(design_number),
    rev           TEXT NOT NULL,
    created_on    TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    PRIMARY KEY (design_number, rev)
);
-- SAP number ranges: the last sequence issued per department and year, and the last
-- material. Counters, not MAX() over designs, so a number is never issued twice.
CREATE TABLE IF NOT EXISTS number_ranges (
    department TEXT NOT NULL REFERENCES departments(code),
    year       INTEGER NOT NULL,
    last_seq   INTEGER NOT NULL,
    PRIMARY KEY (department, year)
);
CREATE TABLE IF NOT EXISTS material_range (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    last_material INTEGER NOT NULL
);
"""

# Revisions run A..Y, then AA, AB...: within one length they sort alphabetically in issue
# order (skipped letters don't change that), and a longer one is always later.
_DESIGN_SELECT = """
SELECT d.*,
       (SELECT r.rev FROM revisions r WHERE r.design_number = d.design_number
        ORDER BY LENGTH(r.rev) DESC, r.rev DESC LIMIT 1) AS current_revision
FROM designs d
"""

FILTERABLE_COLUMNS = frozenset({"department", "status", "design_number"})


class ReservationError(Exception):
    """SAP refused to reserve a number; `code` and `message` go to the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Database:
    def __init__(self, path: Path, seed_dir: Path = SEED_DIR) -> None:
        self.path = path
        self.seed_dir = seed_dir

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A connection in autocommit mode; write paths open their own transaction."""
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """`BEGIN IMMEDIATE`: takes the write lock up front, so read-then-write is atomic."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    # --- setup ---------------------------------------------------------------------

    def init(self) -> None:
        """Create the schema and load the seed if the database is empty."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
        with self.transaction() as conn:
            if conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
                self._seed(conn)

    def _seed(self, conn: sqlite3.Connection) -> None:
        departments = _load_json(self.seed_dir / "departments.json")["departments"]
        designs = _load_json(self.seed_dir / "designs.json")["designs"]

        for dept in departments:
            conn.execute(
                "INSERT INTO departments (code, name_en, name_es, lead) VALUES (?, ?, ?, ?)",
                (dept["code"], dept["name_en"], dept["name_es"], dept["lead"]),
            )
            conn.executemany(
                "INSERT INTO default_wbs (department, year, wbs) VALUES (?, ?, ?)",
                [(dept["code"], int(year), wbs) for year, wbs in dept["default_wbs"].items()],
            )

        last_seq: dict[tuple[str, int], int] = {}
        for d in designs:
            conn.execute(
                "INSERT INTO designs (design_number, department, name, status, material, wbs,"
                " created_on, created_by, block_reason, successor)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    d["design_number"],
                    d["department"],
                    d["name"],
                    d["status"],
                    d["material"],
                    d["wbs"],
                    d["created_on"],
                    d["created_by"],
                    d["block_reason"],
                    d["successor"],
                ),
            )
            conn.executemany(
                "INSERT INTO revisions (design_number, rev, created_on, created_by)"
                " VALUES (?, ?, ?, ?)",
                [
                    (d["design_number"], r["rev"], r["created_on"], r["created_by"])
                    for r in d["revisions"]
                ],
            )
            _, dept, yy, seq = d["design_number"].split("-")
            key = (dept, 2000 + int(yy))
            last_seq[key] = max(last_seq.get(key, 0), int(seq))

        conn.executemany(
            "INSERT INTO number_ranges (department, year, last_seq) VALUES (?, ?, ?)",
            [(dept, year, seq) for (dept, year), seq in last_seq.items()],
        )
        conn.execute(
            "INSERT INTO material_range (id, last_material) VALUES (1, ?)",
            (max(int(d["material"]) for d in designs),),
        )

    # --- reads ---------------------------------------------------------------------

    def get_design(self, design_number: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                _DESIGN_SELECT + " WHERE d.design_number = ?", (design_number,)
            ).fetchone()

    def list_designs(
        self, filters: Mapping[str, str], top: int | None = None, skip: int = 0
    ) -> list[sqlite3.Row]:
        """Designs ordered by number. `filters` maps column -> value (equality, AND)."""
        unknown = set(filters) - FILTERABLE_COLUMNS
        if unknown:
            raise ValueError(f"not filterable: {sorted(unknown)}")
        where = " AND ".join(f"d.{column} = ?" for column in filters)
        sql = _DESIGN_SELECT + (f" WHERE {where}" if where else "")
        sql += " ORDER BY d.design_number LIMIT ? OFFSET ?"
        params = [*filters.values(), -1 if top is None else top, skip]
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def revisions(self, design_numbers: Iterable[str]) -> dict[str, list[sqlite3.Row]]:
        """Revisions per design, oldest first."""
        numbers = list(design_numbers)
        result: dict[str, list[sqlite3.Row]] = {n: [] for n in numbers}
        if not numbers:
            return result
        marks = ", ".join("?" * len(numbers))
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM revisions WHERE design_number IN ({marks})"
                " ORDER BY design_number, rev",
                numbers,
            ).fetchall()
        for row in rows:
            result[row["design_number"]].append(row)
        return result

    def get_revision(self, design_number: str, rev: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM revisions WHERE design_number = ? AND rev = ?",
                (design_number, rev),
            ).fetchone()

    def list_departments(self, year: int) -> list[sqlite3.Row]:
        """Departments with their default project (WBS) for `year`, or NULL."""
        with self.connect() as conn:
            return conn.execute(
                "SELECT d.*, w.wbs AS default_wbs FROM departments d"
                " LEFT JOIN default_wbs w ON w.department = d.code AND w.year = ?"
                " ORDER BY d.rowid",
                (year,),
            ).fetchall()

    def get_department(self, code: str, year: int) -> sqlite3.Row | None:
        return next((d for d in self.list_departments(year) if d["code"] == code), None)

    # --- writes --------------------------------------------------------------------

    def reserve(self, department: str, name: str, created_by: str, today: date) -> str:
        """Reserve the next design number; returns it. Raises `ReservationError`."""
        year = today.year
        with self.transaction() as conn:
            known = conn.execute("SELECT 1 FROM departments WHERE code = ?", (department,))
            if known.fetchone() is None:
                raise ReservationError(
                    "ZHL_PLM/010", f"Department '{department}' does not exist in SAP"
                )

            wbs = conn.execute(
                "SELECT wbs FROM default_wbs WHERE department = ? AND year = ?",
                (department, year),
            ).fetchone()
            if wbs is None:
                raise ReservationError(
                    "ZHL_PLM/011",
                    f"No default project (WBS) for department {department} in {year};"
                    " contact Product Engineering",
                )

            row = conn.execute(
                "SELECT last_seq FROM number_ranges WHERE department = ? AND year = ?",
                (department, year),
            ).fetchone()
            seq = (row["last_seq"] if row else 0) + 1
            if seq > SEQUENCE_MAX:
                raise ReservationError(
                    "ZHL_PLM/012", f"Number range for {department} {year} is exhausted"
                )
            conn.execute(
                "INSERT INTO number_ranges (department, year, last_seq) VALUES (?, ?, ?)"
                " ON CONFLICT (department, year) DO UPDATE SET last_seq = excluded.last_seq",
                (department, year, seq),
            )

            material = (
                conn.execute("SELECT last_material FROM material_range WHERE id = 1").fetchone()[0]
                + 1
            )
            if material > MATERIAL_MAX:
                raise ReservationError(
                    "ZHL_PLM/013", "Material number range for electronic assemblies is exhausted"
                )
            conn.execute("UPDATE material_range SET last_material = ? WHERE id = 1", (material,))

            number = f"HL-{department}-{year % 100:02d}-{seq:04d}"
            conn.execute(
                "INSERT INTO designs (design_number, department, name, status, material, wbs,"
                " created_on, created_by) VALUES (?, ?, ?, 'IN_WORK', ?, ?, ?, ?)",
                (
                    number,
                    department,
                    name,
                    f"{material:018d}",
                    wbs["wbs"],
                    today.isoformat(),
                    created_by,
                ),
            )
            conn.execute(
                "INSERT INTO revisions (design_number, rev, created_on, created_by)"
                " VALUES (?, ?, ?, ?)",
                (number, FIRST_REVISION, today.isoformat(), created_by),
            )
        return number

    def add_revision(self, design_number: str, rev: str, created_by: str, today: date) -> None:
        """Record a new revision of a design. Only the next free letter, and only while the
        design is IN_WORK or RELEASED. Raises `ReservationError`."""
        with self.transaction() as conn:
            design = conn.execute(
                "SELECT status FROM designs WHERE design_number = ?", (design_number,)
            ).fetchone()
            if design is None:
                raise ReservationError("ZHL_PLM/001", f"Design {design_number} does not exist")
            if design["status"] not in REVISABLE_STATUSES:
                raise ReservationError(
                    "ZHL_PLM/020",
                    f"Design {design_number} is {design['status']}; no new revision allowed",
                )
            existing = [
                r["rev"]
                for r in conn.execute(
                    "SELECT rev FROM revisions WHERE design_number = ?", (design_number,)
                )
            ]
            if rev in existing:
                raise ReservationError(
                    "ZHL_PLM/021", f"Revision {rev} of {design_number} already exists"
                )
            expected = next_revision(existing)
            if rev != expected:
                raise ReservationError(
                    "ZHL_PLM/022",
                    f"Revision {rev} is not the next revision of {design_number}; expected "
                    f"{expected}",
                )
            conn.execute(
                "INSERT INTO revisions (design_number, rev, created_on, created_by)"
                " VALUES (?, ?, ?, ?)",
                (design_number, rev, today.isoformat(), created_by),
            )


def next_revision(existing: Iterable[str]) -> str:
    """The revision after the latest one: A..Y, then AA..YY."""
    n = len(REVISION_LETTERS)

    def index(rev: str) -> int:
        if len(rev) == 1:
            return REVISION_LETTERS.index(rev)
        return n * (1 + REVISION_LETTERS.index(rev[0])) + REVISION_LETTERS.index(rev[1])

    known = [index(r) for r in existing if r and all(c in REVISION_LETTERS for c in r)]
    following = max(known) + 1 if known else 0
    if following < n:
        return REVISION_LETTERS[following]
    first, second = divmod(following - n, n)
    return REVISION_LETTERS[first] + REVISION_LETTERS[second]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
