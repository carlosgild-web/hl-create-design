"""The service's error texts in English and Spanish, like an SAP message class (decision 0027).

SAP Gateway answers in the logon language: the `sap-language` URL parameter or header
(`ES`, `EN`; SAP's one-letter keys `S` and `E` too), else `Accept-Language`, else English.
An error keeps its code and parameters and gets its text when the response is built, so a
caller that asks in Spanish reads Spanish. Codes not listed here (technical request errors)
answer in English only.
"""

from collections.abc import Mapping

from starlette.requests import Request

LANGUAGES = ("en", "es")

MESSAGES: dict[str, dict[str, str]] = {
    # Gateway
    "ZHL_GW/001": {
        "en": "Logon failed: wrong user or password",
        "es": "Fallo de inicio de sesión: usuario o contraseña incorrectos",
    },
    "ZHL_GW/002": {
        "en": "CSRF token validation failed",
        "es": "Falló la validación del token CSRF",
    },
    "ZHL_GW/003": {
        "en": "SAP system is in maintenance; try again later",
        "es": "El sistema SAP está en mantenimiento; inténtalo más tarde",
    },
    "ZHL_GW/004": {
        "en": "SAP backend system temporarily unavailable",
        "es": "El sistema SAP no está disponible en este momento",
    },
    # PLM service
    "ZHL_PLM/001": {
        "en": "Design {design} does not exist",
        "es": "El diseño {design} no existe",
    },
    "ZHL_PLM/002": {
        "en": "Department {department} does not exist",
        "es": "El departamento {department} no existe",
    },
    "ZHL_PLM/003": {
        "en": "Revision {revision} of design {design} does not exist",
        "es": "La revisión {revision} del diseño {design} no existe",
    },
    "ZHL_PLM/010": {
        "en": "Department '{department}' does not exist in SAP",
        "es": "El departamento '{department}' no existe en SAP",
    },
    "ZHL_PLM/011": {
        "en": "No default project (WBS) for department {department} in {year};"
        " contact Product Engineering",
        "es": "No hay proyecto (WBS) por defecto para el departamento {department} en {year};"
        " contacta con Ingeniería de Producto",
    },
    "ZHL_PLM/012": {
        "en": "Number range for {department} {year} is exhausted",
        "es": "El rango de números de {department} {year} está agotado",
    },
    "ZHL_PLM/013": {
        "en": "Material number range for electronic assemblies is exhausted",
        "es": "El rango de números de material para conjuntos electrónicos está agotado",
    },
    "ZHL_PLM/020": {
        "en": "Design {design} is {status}; no new revision allowed",
        "es": "El diseño {design} está en {status}; no se permiten revisiones nuevas",
    },
    "ZHL_PLM/021": {
        "en": "Revision {revision} of {design} already exists",
        "es": "La revisión {revision} de {design} ya existe",
    },
    "ZHL_PLM/022": {
        "en": "Revision {revision} is not the next revision of {design}; expected {expected}",
        "es": "La revisión {revision} no es la siguiente de {design}; se esperaba {expected}",
    },
}

_KEYS = {"en": "en", "e": "en", "es": "es", "s": "es"}


def text(code: str, language: str = "en", params: Mapping[str, object] | None = None) -> str:
    """The text of `code` in `language` (English when the code or language is unknown)."""
    templates = MESSAGES[code]
    return templates.get(language, templates["en"]).format(**(params or {}))


def localize(code: str, message: str, language: str, params: Mapping[str, object] | None) -> str:
    """`message` in `language` when the catalog has `code`; otherwise `message` as it is."""
    if language == "en" or code not in MESSAGES:
        return message
    try:
        return text(code, language, params)
    except (KeyError, IndexError):  # a raise site without the template's parameters
        return message


def request_language(request: Request) -> str:
    """The logon language of a request: `sap-language` (parameter, then header), then the
    first `Accept-Language` entry, else English."""
    raw = request.query_params.get("sap-language") or request.headers.get("sap-language")
    if not raw:
        raw = request.headers.get("accept-language", "").split(",")[0].split(";")[0]
        raw = raw.split("-")[0]
    return _KEYS.get(raw.strip().lower(), "en")
