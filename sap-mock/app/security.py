"""Basic auth and the CSRF token handshake of an SAP Gateway.

1. `GET` with `x-csrf-token: Fetch` returns a token in the `x-csrf-token` response header
   and sets a session cookie.
2. A modifying request (`POST`, ...) must send that token and the session cookie.
   Otherwise the answer is 403 with `x-csrf-token: Required`, and the client fetches again.

Tokens live in memory, so they are lost when the mock restarts, like a new SAP session.
"""

import base64
import binascii
import secrets
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.config import Settings
from app.messages import request_language
from app.odata import CSRF_FAILED, LOGON_FAILED, error_response, is_service_path

SESSION_COOKIE = "SAP_SESSIONID_HLM_100"
CSRF_HEADER = "x-csrf-token"
MODIFYING_METHODS = frozenset({"POST", "PUT", "PATCH", "MERGE", "DELETE"})
REALM = 'Basic realm="H&L mock SAP"'


class CsrfStore:
    """Session id -> (user, token). Bounded: the oldest sessions are dropped first."""

    def __init__(self, max_sessions: int = 1000) -> None:
        self._sessions: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self._max_sessions = max_sessions

    def issue(self, session_id: str | None, user: str) -> tuple[str, str]:
        """The session's token (a new session if needed); returns (session_id, token)."""
        if session_id is not None and session_id in self._sessions:
            owner, token = self._sessions[session_id]
            if owner == user:
                return session_id, token
        session_id = secrets.token_urlsafe(24)
        token = secrets.token_urlsafe(24)
        self._sessions[session_id] = (user, token)
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)
        return session_id, token

    def is_valid(self, session_id: str | None, user: str, token: str | None) -> bool:
        if session_id is None or not token:
            return False
        entry = self._sessions.get(session_id)
        if entry is None:
            return False
        owner, expected = entry
        return owner == user and secrets.compare_digest(token.encode(), expected.encode())


def authenticate(request: Request, settings: Settings) -> str | None:
    """The user name if the Basic credentials match the configured demo user."""
    scheme, _, param = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(param, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    user, separator, password = decoded.partition(":")
    if not separator:
        return None
    user_ok = secrets.compare_digest(user.encode(), settings.sap_user.encode())
    password_ok = secrets.compare_digest(
        password.encode(), settings.sap_password.get_secret_value().encode()
    )
    return user if user_ok and password_ok else None


async def gateway(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """HTTP middleware for the OData service paths: auth, CSRF, `dataserviceversion`."""
    if not is_service_path(request.url.path):
        return await call_next(request)

    settings: Settings = request.app.state.settings
    store: CsrfStore = request.app.state.csrf
    user = authenticate(request, settings)
    if user is None:
        return error_response(
            401,
            LOGON_FAILED,
            "Logon failed: wrong user or password",
            headers={"WWW-Authenticate": REALM},
            language=request_language(request),
        )

    session_id = request.cookies.get(SESSION_COOKIE)
    sent_token = request.headers.get(CSRF_HEADER)
    if request.method in MODIFYING_METHODS and not store.is_valid(session_id, user, sent_token):
        return error_response(
            403,
            CSRF_FAILED,
            "CSRF token validation failed",
            headers={CSRF_HEADER: "Required"},
            language=request_language(request),
        )

    response = await call_next(request)
    response.headers["dataserviceversion"] = "2.0"
    wants_token = (sent_token or "").lower() == "fetch"
    if request.method == "GET" and wants_token and response.status_code < 400:
        session_id, token = store.issue(session_id, user)
        response.headers[CSRF_HEADER] = token
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="strict")
    return response
