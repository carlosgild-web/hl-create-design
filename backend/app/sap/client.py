"""`SapClient`: the only way the backend talks to SAP (invariant 4).

It speaks the OData v2 dialect of an SAP Gateway service (`ZHL_PLM_DESIGN_SRV`), so the
mock in `sap-mock/` could be replaced by a real system:

- basic auth on every request, and a cookie jar: the CSRF token is bound to the
  `SAP_SESSIONID_*` session cookie;
- before a POST, `GET` with `x-csrf-token: Fetch`; a 403 with `x-csrf-token: Required`
  (token expired) fetches a new token and retries once;
- payloads are `{"d": {...}}`, dates are `/Date(ms)/`, errors are the Gateway error body.

Retries: a GET is retried on 503 and on network errors. A POST is retried only when the
server certainly didn't process it (a 503 from the gateway, or a connection that never
opened), because a reservation that ran twice would waste a number. A maintenance 503
(`Retry-After`) is not retried.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx

SERVICE_ROOT = "/sap/opu/odata/sap/ZHL_PLM_DESIGN_SRV"
CSRF_HEADER = "x-csrf-token"
DEFAULT_TIMEOUT_S = 10.0
DESIGN_NOT_FOUND = "ZHL_PLM/001"
MAINTENANCE = "ZHL_GW/003"

_DATE_RE = re.compile(r"^/Date\((-?\d+)(?:[+-]\d+)?\)/$")


# --- results ---------------------------------------------------------------------


@dataclass(frozen=True)
class SapDesign:
    design_number: str
    department: str
    name: str
    status: str
    material: str
    wbs: str
    current_revision: str
    created_on: date | None
    created_by: str
    block_reason: str
    successor: str
    revisions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_number": self.design_number,
            "department": self.department,
            "name": self.name,
            "status": self.status,
            "material": self.material,
            "wbs": self.wbs,
            "current_revision": self.current_revision,
            "created_on": self.created_on.isoformat() if self.created_on else "",
            "created_by": self.created_by,
            "block_reason": self.block_reason,
            "successor": self.successor,
            "revisions": list(self.revisions),
        }


@dataclass(frozen=True)
class SapDepartment:
    code: str
    name_en: str
    name_es: str
    lead: str
    default_wbs: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name_en": self.name_en,
            "name_es": self.name_es,
            "lead": self.lead,
            "default_wbs": self.default_wbs,
        }


class SapError(Exception):
    """SAP answered with an error, or didn't answer. `code` is the SAP message code
    (for example `ZHL_PLM/010`), or `HTTP` / `NETWORK` when there is none."""

    def __init__(self, message: str, *, status: int | None = None, code: str = "HTTP") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code

    @property
    def unavailable(self) -> bool:
        """SAP is down or unreachable (06-sap-statuses#sap-unavailable)."""
        return self.status in (502, 503, 504) or self.code == "NETWORK"


# --- client ----------------------------------------------------------------------


class SapClient:
    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        retries: int = 2,
        backoff_s: float = 0.3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(user, password),
            timeout=timeout,
            transport=transport,
            headers={"accept": "application/json"},
        )
        self._retries = retries
        self._backoff_s = backoff_s
        self._token: str | None = None

    def __enter__(self) -> SapClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # --- reads -----------------------------------------------------------------------

    def get_design(self, design_number: str) -> SapDesign | None:
        """The design with its revisions, or None when SAP doesn't know the number."""
        try:
            data = self._get(
                f"{SERVICE_ROOT}/DesignSet({_key(design_number)})",
                params={"$format": "json", "$expand": "Revisions"},
            )
        except SapError as exc:
            if exc.status == 404 and exc.code == DESIGN_NOT_FOUND:
                return None
            raise
        return _design(data["d"])

    def list_departments(self) -> list[SapDepartment]:
        data = self._get(f"{SERVICE_ROOT}/DepartmentSet", params={"$format": "json"})
        return [_department(row) for row in data["d"]["results"]]

    # --- writes ----------------------------------------------------------------------

    def reserve_number(self, department: str, name: str, created_by: str) -> SapDesign:
        """Reserve the next design number of `department`. SAP issues the number, the
        material and the WBS, and records revision A. Not idempotent."""
        body = {"Department": department, "Name": name, "CreatedBy": created_by}
        url = f"{SERVICE_ROOT}/DesignSet"
        for refreshed in (False, True):
            token = self._csrf_token(refresh=refreshed)
            response = self._send(
                "POST", url, json=body, headers={CSRF_HEADER: token}, safe_to_repeat=False
            )
            if response.status_code == 403 and _csrf_required(response) and not refreshed:
                continue
            data = _json_or_raise(response)
            return _design(data["d"])
        raise AssertionError("unreachable")  # pragma: no cover

    # --- transport -------------------------------------------------------------------

    def _csrf_token(self, *, refresh: bool = False) -> str:
        if self._token is None or refresh:
            response = self._send(
                "GET", SERVICE_ROOT, params={"$format": "json"}, headers={CSRF_HEADER: "Fetch"}
            )
            _json_or_raise(response)
            token = response.headers.get(CSRF_HEADER)
            if not token:
                raise SapError("SAP returned no CSRF token.", status=response.status_code)
            self._token = token
        return self._token

    def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        return _json_or_raise(self._send("GET", url, params=params))

    def _send(self, method: str, url: str, *, safe_to_repeat: bool = True, **kw: Any):
        attempt = 0
        while True:
            try:
                response = self._http.request(method, url, **kw)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                error = SapError(f"SAP is not reachable: {exc}", code="NETWORK")
            except httpx.HTTPError as exc:
                if not safe_to_repeat:
                    raise SapError(
                        f"No answer from SAP ({exc}); the request may have been processed.",
                        code="NETWORK",
                    ) from exc
                error = SapError(f"No answer from SAP: {exc}", code="NETWORK")
            else:
                if not _retryable(response):
                    return response
                error = None
            attempt += 1
            if attempt > self._retries:
                if error is not None:
                    raise error
                return response
            time.sleep(self._backoff_s * attempt)


# --- parsing ---------------------------------------------------------------------


def _key(value: str) -> str:
    """An OData string key literal: quotes doubled."""
    return "'" + value.replace("'", "''") + "'"


def _retryable(response: httpx.Response) -> bool:
    if response.status_code != 503:
        return False
    return _error_code(response) != MAINTENANCE


def _csrf_required(response: httpx.Response) -> bool:
    return response.headers.get(CSRF_HEADER, "").lower() == "required"


def _error_code(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return "HTTP"


def _json_or_raise(response: httpx.Response) -> dict[str, Any]:
    if response.is_success:
        return response.json()
    code, message = "HTTP", response.reason_phrase or f"HTTP {response.status_code}"
    try:
        error = response.json()["error"]
        code = str(error.get("code") or code)
        message = str((error.get("message") or {}).get("value") or message)
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    raise SapError(message, status=response.status_code, code=code)


def parse_odata_date(value: str) -> date | None:
    """`/Date(1763337600000)/` -> 2025-11-17. Empty or malformed -> None."""
    match = _DATE_RE.match(value or "")
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=UTC).date()


def _design(d: dict[str, Any]) -> SapDesign:
    revisions = d.get("Revisions") or {}
    revs = tuple(r["Revision"] for r in revisions.get("results", ()))
    return SapDesign(
        design_number=d["DesignNumber"],
        department=d.get("Department", ""),
        name=d.get("Name", ""),
        status=d.get("Status", ""),
        material=d.get("Material", ""),
        wbs=d.get("Wbs", ""),
        current_revision=d.get("CurrentRevision", ""),
        created_on=parse_odata_date(d.get("CreatedOn", "")),
        created_by=d.get("CreatedBy", ""),
        block_reason=d.get("BlockReason", ""),
        successor=d.get("Successor", ""),
        revisions=revs,
    )


def _department(d: dict[str, Any]) -> SapDepartment:
    return SapDepartment(
        code=d["Code"],
        name_en=d.get("NameEn", ""),
        name_es=d.get("NameEs", ""),
        lead=d.get("Lead", ""),
        default_wbs=d.get("DefaultWbs", ""),
    )
