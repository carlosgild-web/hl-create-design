# H&L mock SAP

A **mock** of an SAP Gateway OData v2 service, `ZHL_PLM_DESIGN_SRV`, for the Create Design
demo. It looks up designs and departments and reserves new design numbers.
It is not a real SAP and contains no SAP code. The company, people and designs are fictional.

The backend talks to it only through `SapClient` (invariant 4). Pointing `SAP_BASE_URL` at a
real system with a matching service would, in principle, be the only change.
Why it is shaped like this: [decision 0004](../docs/decisions/0004-mock-sap-odata-v2.md).

## Run

```bash
cd sap-mock
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8100
pytest -q && ruff check . && ruff format --check .
```

On first start the service creates `DATA_DIR/sap_mock.db` and loads `seed/*.json`
(4 departments, 30 designs). **To reset the demo, stop the service and delete that file.**

## Configuration

Read from environment variables or the repo's `.env` (see `.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `SAP_USER` / `SAP_PASSWORD` | `demo` / `demo` | Basic auth credentials the mock accepts (the backend sends the same ones) |
| `DATA_DIR` | `./data` | Folder of `sap_mock.db` |
| `SAP_TODAY` | empty (today) | Pins the mock's date, so new numbers keep the demo's year ([decision 0007](../docs/decisions/0007-pinned-sap-date.md)) |
| `SAP_LATENCY_MS` | `0` | Delay added to every OData request |
| `SAP_FAIL_RATE` | `0` | Share of OData requests (0–1) answered with 503 |
| `SAP_MAINTENANCE` | `false` | Every OData request answers 503 with `Retry-After` |

The chaos switches run before authentication and before any data is touched, so a failed
request never reserves a number. `/health` needs no auth and ignores them.

## Endpoints

Service root: `/sap/opu/odata/sap/ZHL_PLM_DESIGN_SRV`. All of it needs Basic auth.

| Method and path | What it does |
|---|---|
| `GET /` | Service document; also where clients fetch the CSRF token |
| `GET /$metadata` | EDMX (XML) for the three entity sets |
| `GET /DesignSet` | Designs, ordered by number. `$filter`, `$top`, `$skip`, `$expand=Revisions` |
| `GET /DesignSet('HL-HW-24-0007')` | One design. `$expand=Revisions` inlines the revisions |
| `GET /DesignSet('HL-HW-24-0007')/Revisions` | The design's revisions, oldest first |
| `GET /RevisionSet(DesignNumber='…',Revision='B')` | One revision |
| `GET /DepartmentSet`, `GET /DepartmentSet('HW')` | Departments with this year's default project (WBS) |
| `POST /DesignSet` | Reserve the next number. Needs the CSRF token |
| `GET /health` | Liveness probe (outside the service, no auth) |

**Payloads** follow OData v2 JSON: `{"d": {...}}` for an entity, `{"d": {"results": [...]}}`
for a collection, `__metadata` with the entity's URI and type, dates as `/Date(ms)/`
(UTC midnight), and `""` for empty strings, as ABAP has no null strings.
Materials always have 18 digits (`000000000040001071`); the title block drops the zeros.

**Reserving a number.** The body is `{"Department", "Name", "CreatedBy"}`; other fields are
ignored because SAP issues them. In one SQLite transaction the mock takes:
- the next value of the department's number range for the year (`HL-HW-26-0042` for the
  first HW reservation on the seed data), never reused, also after a failure;
- the next material (`000000000040001236` first);
- the department's default project for the year;
- status `IN_WORK` and revision `A`, dated today.

It answers `201 Created` with the new design and a `Location` header. The name is stored as
sent: the company rules (title case, allowed characters) are checked by the backend's
validators before it calls SAP.

## Try it with curl

Use a POSIX shell (Git Bash on Windows; in PowerShell call `curl.exe`, not `curl`).

```bash
SAP=http://localhost:8100/sap/opu/odata/sap/ZHL_PLM_DESIGN_SRV

# Look up a design (rev H, so its next revision skips I)
curl -s -u demo:demo "$SAP/DesignSet('HL-HW-24-0007')?\$format=json"

# Its revisions inline
curl -s -u demo:demo "$SAP/DesignSet('HL-HW-24-0007')?\$expand=Revisions"

# Filter and page (-G with --data-urlencode encodes the spaces and quotes)
curl -s -u demo:demo -G "$SAP/DesignSet" \
  --data-urlencode "\$filter=Department eq 'HW' and Status eq 'IN_WORK'" \
  --data-urlencode '$top=3'

# Departments and their default project for this year
curl -s -u demo:demo "$SAP/DepartmentSet"

# The service description
curl -s -u demo:demo "$SAP/\$metadata"
```

Reserving a number takes the CSRF handshake, like a real Gateway: fetch a token with a GET,
keep the session cookie, and send both with the POST.

```bash
# 1. Fetch the token; the cookie jar keeps the session cookie
TOKEN=$(curl -s -u demo:demo -c jar.txt -D - -o /dev/null -H "x-csrf-token: Fetch" "$SAP/" \
  | tr -d '\r' | awk -F': ' 'tolower($1)=="x-csrf-token" {print $2}')

# 2. Reserve: 201 Created, Location: .../DesignSet('HL-HW-26-0042')
curl -s -i -u demo:demo -b jar.txt -X POST "$SAP/DesignSet" \
  -H "x-csrf-token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"Department": "HW", "Name": "Bead Drill Controller", "CreatedBy": "C. Velazquez"}'
```

And the failures:

```bash
curl -s -i "$SAP/DesignSet"                                      # 401, no credentials
curl -s -i -u demo:demo -X POST "$SAP/DesignSet" -d '{}'         # 403, x-csrf-token: Required
curl -s -i -u demo:demo "$SAP/DesignSet('HL-HW-26-9999')"        # 404, ZHL_PLM/001
SAP_MAINTENANCE=true uvicorn app.main:app --port 8100            # then any call: 503
```

## Errors

Every error uses the SAP Gateway error body:

```json
{"error": {"code": "ZHL_PLM/001",
           "message": {"lang": "en", "value": "Design HL-HW-26-9999 does not exist"},
           "innererror": {"transactionid": "A673…", "timestamp": "20261117164637",
                          "errordetails": [{"code": "ZHL_PLM/001", "message": "…",
                                            "severity": "error", "target": ""}]}}}
```

The codes are invented for the mock (message classes `ZHL_GW` for the gateway layer and
`ZHL_PLM` for the design service):

| HTTP | Code | When |
|---|---|---|
| 401 | `ZHL_GW/001` | Missing or wrong Basic credentials (`WWW-Authenticate` is set) |
| 403 | `ZHL_GW/002` | CSRF token missing, wrong, or from another session (`x-csrf-token: Required`) |
| 503 | `ZHL_GW/003` | `SAP_MAINTENANCE` is on (`Retry-After: 300`) |
| 503 | `ZHL_GW/004` | Random failure from `SAP_FAIL_RATE` |
| 400 | `ZHL_GW/005` | Invalid query option or body |
| 404 | `ZHL_GW/006` | No such resource (unknown entity set or path) |
| 404 | `ZHL_PLM/001` | Design not found |
| 404 | `ZHL_PLM/002` | Department not found |
| 404 | `ZHL_PLM/003` | Revision not found |
| 400 | `ZHL_PLM/010` | Reserve: the department doesn't exist |
| 400 | `ZHL_PLM/011` | Reserve: no default project for the department this year |
| 400 | `ZHL_PLM/012` | Reserve: the number range for the department and year is exhausted |
| 400 | `ZHL_PLM/013` | Reserve: the material range is exhausted |

## What the mock leaves out

Only the subset that Create Design needs. Compared with a real SAP Gateway:

- JSON only. A real service answers Atom XML unless asked for `$format=json`; the mock
  answers JSON by default and rejects other formats.
- `$filter` supports `<Property> eq '<value>'` joined with `and`, on `Department`,
  `Status` and `DesignNumber`. No `$orderby`, `$select`, `$inlinecount` or `$batch`.
- `RevisionSet` can be read by key, but not listed; use the `Revisions` navigation.
- No updates or deletes. Status changes belong to Product Engineering
  ([manual 06](../docs/manual/en/06-sap-statuses.md#who-changes)).
- One user. CSRF tokens live in memory and are lost on restart, like a new SAP session.
