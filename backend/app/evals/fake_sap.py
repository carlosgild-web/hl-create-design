"""An in-memory SAP Gateway for tests and the agent evals, served to the real `SapClient` through
`httpx.MockTransport`: basic auth, the CSRF handshake bound to a session cookie, OData v2
payloads and error bodies, and switches for 503s and maintenance."""

from __future__ import annotations

import base64
import json
import re
import secrets
from datetime import UTC, date, datetime
from urllib.parse import unquote

import httpx

from app.sap.client import SERVICE_ROOT, SapClient

USER, PASSWORD = "demo", "demo"
COOKIE = "SAP_SESSIONID_HLM_100"
WBS = {"HW": "P-26-0108", "PWR": "P-26-0112", "EMB": "P-26-0115", "TFX": "P-26-0121"}


def odata_date(day: str) -> str:
    d = date.fromisoformat(day)
    return f"/Date({int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)})/"


def _design(number, dept, name, status, material, wbs, revs, block="", successor=""):
    return {
        "DesignNumber": number,
        "Department": dept,
        "Name": name,
        "Status": status,
        "Material": material,
        "Wbs": wbs,
        "CurrentRevision": revs[-1] if revs else "",
        "CreatedOn": odata_date("2026-03-02"),
        "CreatedBy": "E. Marín",
        "BlockReason": block,
        "Successor": successor,
        "_revs": list(revs),
    }


def seed() -> dict[str, dict]:
    designs = [
        _design(
            "HL-HW-26-0042",
            "HW",
            "Bead Drill Controller",
            "IN_WORK",
            "000000000040001234",
            "P-26-0108",
            ["A", "B"],
        ),
        _design(
            "HL-PWR-25-0007",
            "PWR",
            "Main Power Board",
            "RELEASED",
            "000000000040000777",
            "P-25-0081",
            ["A"],
        ),
        _design(
            "HL-HW-24-0003",
            "HW",
            "Old Led Panel",
            "BLOCKED",
            "000000000040000303",
            "P-24-0052",
            ["A", "B"],
            block="Supplier part discontinued",
        ),
        _design(
            "HL-EMB-23-0002",
            "EMB",
            "Sensor Hub",
            "OBSOLETE",
            "000000000040000202",
            "P-23-0036",
            ["A"],
            successor="HL-EMB-25-0011",
        ),
    ]
    return {d["DesignNumber"]: d for d in designs}


class FakeSap:
    def __init__(self) -> None:
        self.designs = seed()
        self.sessions: dict[str, str] = {}  # session id -> csrf token
        self.next_seq = 50
        self.next_material = 40009001
        self.fail_next = 0  # answer this many requests with 503 (backend unavailable)
        self.maintenance = False
        self.slow_next = 0  # time out this many requests (no answer within the client timeout)
        self.requests: list[httpx.Request] = []
        self.reservations: list[dict] = []

    # --- helpers for tests -----------------------------------------------------------

    def client(self, **kw) -> SapClient:
        kw.setdefault("backoff_s", 0)
        return SapClient(
            "http://sap.test", USER, PASSWORD, transport=httpx.MockTransport(self), **kw
        )

    def expire_tokens(self) -> None:
        self.sessions = {sid: "expired" for sid in self.sessions}

    @property
    def posts(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == "POST"]

    # --- the gateway -----------------------------------------------------------------

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.slow_next:
            self.slow_next -= 1
            raise httpx.ReadTimeout("SAP did not answer in time", request=request)
        if self.maintenance:
            return self._error(503, "ZHL_GW/003", "SAP system is in maintenance; try again later")
        if self.fail_next:
            self.fail_next -= 1
            return self._error(503, "ZHL_GW/004", "SAP backend system temporarily unavailable")
        if not self._authenticated(request):
            return self._error(401, "ZHL_GW/001", "Logon failed: wrong user or password")

        session = request.headers.get("cookie", "")
        match = re.search(rf"{COOKIE}=(\w+)", session)
        session_id = match.group(1) if match else None
        token = request.headers.get("x-csrf-token", "")

        if request.method == "POST" and (not session_id or self.sessions.get(session_id) != token):
            return self._error(
                403, "ZHL_GW/002", "CSRF token validation failed", {"x-csrf-token": "Required"}
            )
        response = self._route(request)
        if request.method == "GET" and token.lower() == "fetch" and response.status_code < 400:
            session_id = session_id or secrets.token_hex(8)
            self.sessions[session_id] = secrets.token_hex(12)
            response.headers["x-csrf-token"] = self.sessions[session_id]
            response.headers["set-cookie"] = f"{COOKIE}={session_id}; Path=/; HttpOnly"
        return response

    def _authenticated(self, request: httpx.Request) -> bool:
        scheme, _, param = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "basic":
            return False
        return base64.b64decode(param).decode() == f"{USER}:{PASSWORD}"

    def _route(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        if not path.startswith(SERVICE_ROOT):
            return self._error(404, "ZHL_GW/006", "Resource not found")
        rest = path[len(SERVICE_ROOT) :]
        if rest in ("", "/"):
            return self._ok({"d": {"EntitySets": ["DesignSet", "DepartmentSet"]}})
        if rest == "/DepartmentSet":
            rows = [
                {
                    "Code": code,
                    "NameEn": name,
                    "NameEs": name,
                    "Lead": "E. Marín",
                    "DefaultWbs": WBS[code],
                }
                for code, name in (
                    ("HW", "Hardware Design"),
                    ("PWR", "Power Electronics"),
                    ("EMB", "Embedded Boards"),
                    ("TFX", "Test Fixtures"),
                )
            ]
            return self._ok({"d": {"results": rows}})
        match = re.fullmatch(r"/DesignSet\('((?:[^']|'')*)'\)", rest)
        if match and request.method == "GET":
            number = match.group(1).replace("''", "'")
            design = self.designs.get(number)
            if design is None:
                return self._error(404, "ZHL_PLM/001", f"Design {number} does not exist")
            expand = request.url.params.get("$expand") == "Revisions"
            return self._ok({"d": self._entity(design, expand)})
        if rest == "/DesignSet" and request.method == "POST":
            return self._reserve(json.loads(request.content))
        return self._error(404, "ZHL_GW/006", "Resource not found")

    def _reserve(self, body: dict) -> httpx.Response:
        dept = body.get("Department", "")
        if dept not in WBS:
            return self._error(400, "ZHL_PLM/010", f"Department '{dept}' does not exist in SAP")
        number = f"HL-{dept}-26-{self.next_seq:04d}"
        self.next_seq += 1
        material = f"{self.next_material:018d}"
        self.next_material += 1
        design = _design(number, dept, body["Name"], "IN_WORK", material, WBS[dept], ["A"])
        design["CreatedBy"] = body["CreatedBy"]
        self.designs[number] = design
        self.reservations.append(body)
        return self._ok({"d": self._entity(design, expand=False)}, status=201)

    @staticmethod
    def _entity(design: dict, expand: bool) -> dict:
        entity = {k: v for k, v in design.items() if not k.startswith("_")}
        entity["Revisions"] = (
            {
                "results": [
                    {"DesignNumber": design["DesignNumber"], "Revision": r} for r in design["_revs"]
                ]
            }
            if expand
            else {"__deferred": {"uri": "..."}}
        )
        return entity

    @staticmethod
    def _ok(payload: dict, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=payload, headers={"dataserviceversion": "2.0"})

    @staticmethod
    def _error(status: int, code: str, message: str, headers: dict | None = None):
        body = {"error": {"code": code, "message": {"lang": "en", "value": message}}}
        return httpx.Response(status, json=body, headers=headers or {})
