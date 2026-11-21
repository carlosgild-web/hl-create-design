"""The demo assistant: a rule-based `LLMClient` for when no model is connected (decision 0025).

`LLM_PROVIDER=demo`, and where `auto` and the Groq fallback end when neither Groq nor
Ollama works. It is not AI: it reads the conversation and replies through the same tools
and the same loop as a real model, so the rules, SAP and the confirmation cards behave as
usual. `FakeClient` stays the scripted test double.

Each call decides from what this turn already holds, most recent first:
1. A card was opened: tell the user to review it and click Confirm.
2. `validate_design_request` answered: explain its errors with their manual refs, or open
   the card when the values are complete and valid, or ask for what is missing.
3. A manual search answered (the backend's pre-retrieval, decision 0024, or its own):
   reply with the top passage's first sentences and its `[source]`.
4. Nothing yet: take the values a sentence names (department, number, revision,
   designer, a name in quotes) and call `propose_form_values` + `validate_design_request`;
   or search the manual for a question; or explain what the demo can do.

Validity is never decided here (invariant 1): the tools decide, and a card opens only
after `validate_design_request` said ok. Free text is only matched as data (invariant 7).
"""

from __future__ import annotations

import itertools
import json
import re
from typing import Any

from app.llm.base import ChatTurn, LLMClient, Message, ToolCall, ToolSpec
from app.standards.validators import DEPARTMENTS, DEPARTMENTS_ES

_ids = itertools.count(1)

_FIELDS = ("department", "design_number", "revision", "name", "designer", "description")

TEXT: dict[str, dict[str, str]] = {
    "en": {
        "prefix": "(Demo assistant) ",
        "help": (
            "No AI model is connected, so I follow simple rules. I can answer questions about "
            "the rules and the app from the Design Manual (ask with a question mark), and fill "
            "the form from a sentence that names a department, a design number "
            "(HL-HW-26-0042), a revision (rev C), a designer (C. Velazquez) and a name in "
            'quotes ("Kiln Burn-In Rack"). When the values are valid I open the confirmation '
            "card. You can always fill the form yourself."
        ),
        "not_found": "I can't find that in the Design Manual. Try other words.",
        "card": "The card is open: check the values and click Confirm. Nothing happens before.",
        "errors": "The form's checks found a problem:",
        "missing": "Values so far are fine. Still missing: {fields}.",
        "filled": "I filled what you gave me.",
    },
    "es": {
        "prefix": "(Asistente de demostración) ",
        "help": (
            "No hay ningún modelo de IA conectado, así que sigo reglas sencillas. Puedo "
            "responder preguntas sobre las reglas y la app con el Manual de Diseño (pregunta "
            "con signos de interrogación) y rellenar el formulario con una frase que nombre un "
            "departamento, un número de diseño (HL-HW-26-0042), una revisión (rev C), un "
            "diseñador (C. Velazquez) y un nombre entre comillas («Kiln Burn-In Rack»). "
            "Cuando los valores son válidos abro la tarjeta de confirmación. Siempre puedes "
            "rellenar el formulario tú."
        ),
        "not_found": "No encuentro eso en el Manual de Diseño. Prueba con otras palabras.",
        "card": (
            "La tarjeta está abierta: revisa los valores y pulsa Confirmar. Antes no pasa nada."
        ),
        "errors": "Las comprobaciones del formulario encontraron un problema:",
        "missing": "Lo que hay está bien. Falta: {fields}.",
        "filled": "Rellené lo que me diste.",
    },
}
FIELD_NAMES = {
    "en": {
        "department": "department",
        "design_number": "design number (or Get SAP number)",
        "revision": "revision",
        "name": "design name",
        "designer": "designer",
    },
    "es": {
        "department": "departamento",
        "design_number": "número de diseño (u Obtener número SAP)",
        "revision": "revisión",
        "name": "nombre del diseño",
        "designer": "diseñador",
    },
}

_LANGUAGE_RE = re.compile(r"Answer in the user's language \((\w+)\)")
_CHAT_RE = re.compile(r'<user_data kind="chat">\n(.*?)\n</user_data>', re.DOTALL)
_FORM_RE = re.compile(
    r'<user_data kind="form">\nCurrent form values: (.*?)\n</user_data>', re.DOTALL
)
# Loose on purpose: "HL-HW-0042" or "hl-hw-26-42" go to the validator, which explains them.
_NUMBER_RE = re.compile(r"\bHL[-_ ][A-Za-z]{1,5}(?:[-_ ]\d{1,4}){1,2}\b", re.IGNORECASE)
_REVISION_RE = re.compile(r"\b(?:rev|revision|revisión)\.?\s+([A-Za-z]{1,2})\b", re.IGNORECASE)
_DESIGNER_RE = re.compile(
    r"\b([A-Z]\.(?: [A-Z]\.)? (?:(?:de|del|la|las|los|van|von|y) )*[A-ZÁÉÍÓÚÑ][\w'-]+)"
)
_QUOTED_RE = re.compile(r"[\"“«]([^\"”»]{3,40})[\"”»]")
_NAME_LABEL_RE = re.compile(
    r"\b(?:name|named|nombre)\s*[:=]\s*([A-Za-z0-9 ._-]{3,40}?)(?:[.,;]|$)", re.I
)
# "controller board for the drilling machine" -> "Drilling Machine Controller"
_BOARD_FOR_RE = re.compile(r"\b(\w+) board for (?:the )?([\w -]+?) machine\b", re.IGNORECASE)
_DEPARTMENT_WORDS = {
    "hardware": "HW",
    "power": "PWR",
    "potencia": "PWR",
    "embedded": "EMB",
    "embebida": "EMB",
    "embebidas": "EMB",
    "embebido": "EMB",
    "fixture": "TFX",
    "fixtures": "TFX",
    "utillaje": "TFX",
    "utillajes": "TFX",
}
# "Reserve a Hardware number for Drill Controller, …"
_NUMBER_FOR_RE = re.compile(r"\bnumber for (?:the )?([A-Z][\w-]*(?: [A-Z][\w-]*){0,5})")
_DEPARTMENT_LABEL_RE = re.compile(r"\b(?:department|departamento)\s*[:=]?\s*([^\s,;]+)", re.I)
_NAME_SEGMENT_RE = re.compile(r"[A-Z][A-Za-z0-9-]*(?: [A-Z0-9][A-Za-z0-9-]*){1,5}")
# A request that uses the values already in the form ("Create the new revision, please").
_REQUEST_RE = re.compile(
    r"^\s*(create|make|reserve|get|open|crea|crear|haz|reserva|reservar|dame|abre)\b", re.I
)
_LOOKUP_RE = re.compile(r"\b(look ?up|status|sap|busca|estado|consulta)\b", re.I)
# Asking for the list ("Which departments are there?"), not about one ("Which department do
# I pick?" is a rule question for the manual).
_DEPARTMENTS_Q_RE = re.compile(
    r"\b(which|what|list)\b.*\bdepartments\b|\bdepartments\b.*\b(exist|are there)\b"
    r"|\bqu[eé] departamentos\b|\bcu[aá]les son los departamentos\b",
    re.I,
)
_MARKDOWN_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")  # [text](link) -> text


def _call(tool: str, /, **arguments: Any) -> ToolCall:
    return ToolCall(f"demo_{next(_ids)}", tool, arguments)


def extract_fields(text: str) -> dict[str, str]:
    """The form values a sentence names. Only matching: the tools check them."""
    fields: dict[str, str] = {}
    lowered = text.lower()
    # Codes inside a design number don't name the department: the user's own word does,
    # and the validator then reports a mismatch ("HL-HW-… for Power Electronics").
    outside_number = _NUMBER_RE.sub(" ", text)
    for code in DEPARTMENTS:
        if re.search(rf"\b{code}\b", outside_number):
            fields["department"] = code
    for code, name in (*DEPARTMENTS.items(), *DEPARTMENTS_ES.items()):
        if name.lower() in lowered:
            fields.setdefault("department", code)
    for word in re.findall(r"\w+", lowered):
        if word in _DEPARTMENT_WORDS:
            fields.setdefault("department", _DEPARTMENT_WORDS[word])
    if labelled_dept := _DEPARTMENT_LABEL_RE.search(text):
        raw = labelled_dept.group(1)
        word = _DEPARTMENT_WORDS.get(
            raw.lower(), raw.upper() if raw.upper() in DEPARTMENTS else raw
        )
        fields["department"] = word  # as written: the validator says if it isn't one
    if number := _NUMBER_RE.search(text):
        fields["design_number"] = number.group(0)  # as written: the validator decides
        code = re.split(r"[-_ ]", number.group(0))[1].upper()
        if code in DEPARTMENTS:
            fields.setdefault("department", code)
    if revision := _REVISION_RE.search(text):
        fields["revision"] = revision.group(1).upper()
    designer = _DESIGNER_RE.search(text)
    if designer:
        fields["designer"] = designer.group(1)
    if quoted := _QUOTED_RE.search(text):
        fields["name"] = quoted.group(1).strip()
    elif labelled := _NAME_LABEL_RE.search(text):
        fields["name"] = labelled.group(1).strip()
    elif for_name := _NUMBER_FOR_RE.search(text):
        fields["name"] = for_name.group(1)
    elif board := _BOARD_FOR_RE.search(text):
        fields["name"] = f"{board.group(2)} machine {board.group(1)}".title()
    elif name := _name_segment(text, designer.group(1) if designer else ""):
        fields["name"] = name
    return fields


def _name_segment(text: str, designer: str) -> str:
    """A comma-separated part that looks like a design name: 2-6 capitalized words, no
    number, not the designer, not a department ("…, Bead Drill Controller, C. Velazquez.")."""
    departments = {n.lower() for n in (*DEPARTMENTS.values(), *DEPARTMENTS_ES.values())}
    for part in re.split(r"[,;]", text):
        part = part.strip().rstrip(".")
        if not _NAME_SEGMENT_RE.fullmatch(part) or part.lower() in departments:
            continue
        if designer and designer in part:
            continue
        return part
    return ""


def _snippet(text: str, limit: int = 260) -> str:
    """The first sentences of a manual passage, as plain text."""
    lines = [ln.strip().lstrip("-*").strip() for ln in text.splitlines()]
    plain = _MARKDOWN_RE.sub(r"\1", " ".join(ln for ln in lines if ln and not ln.startswith("|")))
    plain = plain.replace("**", "").replace("`", "")
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", plain):
        if re.match(r"(See|Ver) \S+", sentence):  # a cross-reference: the citation covers it
            continue
        if out and len(out) + len(sentence) > limit:
            break
        out = f"{out} {sentence}".strip()
        if len(out) >= limit // 2:
            break
    return out


class DemoClient(LLMClient):
    provider = "demo"
    model = "rules"

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        lang = _language(messages)
        text = TEXT[lang]
        start = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        user = messages[start].content if start >= 0 else ""
        chat_match = _CHAT_RE.search(user)
        said = chat_match.group(1) if chat_match else user
        form = _form(user)
        results = [
            (m.name or "", _json(m.content)) for m in messages[start + 1 :] if m.role == "tool"
        ]
        offered = {t.name for t in tools}

        def say(body: str) -> ChatTurn:
            return ChatTurn(content=text["prefix"] + body)

        if any(r.get("status") == "pending_confirmation" for _, r in results):
            return say(text["card"])

        validated = [r for name, r in results if name == "validate_design_request"]
        if validated:
            return self._after_validation(validated[-1], form, offered, lang, say)

        done = {name: r for name, r in results}
        if "sap_list_departments" in done:
            return say(_departments(done["sap_list_departments"], lang))
        if "sap_get_design" in done:
            return say(_design_summary(done["sap_get_design"], lang))

        question = said.strip().endswith("?") or said.strip().startswith("¿")
        fields = extract_fields(said)
        asks_departments = bool(question and _DEPARTMENTS_Q_RE.search(said))
        if (
            asks_departments
            and not fields.get("design_number")
            and "sap_list_departments" in offered
        ):
            return ChatTurn(tool_calls=(_call("sap_list_departments"),))

        searched = [r for name, r in results if name == "search_design_manual"]
        if searched:
            passages = searched[-1].get("passages") or []
            if not passages:
                return say(text["not_found"])
            top = passages[0]
            return say(f"{_snippet(top.get('text', ''))} [{top.get('source', '')}]")

        number_only = fields.get("design_number") and not fields.get("revision")
        if number_only and (question or _LOOKUP_RE.search(said)) and "sap_get_design" in offered:
            return ChatTurn(
                tool_calls=(_call("sap_get_design", design_number=fields["design_number"]),)
            )
        if fields and {"propose_form_values", "validate_design_request"} <= offered:
            check = {k: v for k, v in {**form, **fields}.items() if k in _FIELDS and v}
            return ChatTurn(
                tool_calls=(
                    _call("propose_form_values", **fields),
                    _call("validate_design_request", **check),
                )
            )
        in_form = {k: v for k, v in form.items() if k in _FIELDS and v}
        if in_form and _REQUEST_RE.search(said) and "validate_design_request" in offered:
            return ChatTurn(tool_calls=(_call("validate_design_request", **in_form),))
        if question and "search_design_manual" in offered:
            query = said.strip()[:200]
            return ChatTurn(tool_calls=(_call("search_design_manual", query=query, language=lang),))
        return say(text["help"])

    @staticmethod
    def _after_validation(result, form, offered, lang, say) -> ChatTurn:
        text = TEXT[lang]
        errors = result.get("errors") or []
        if errors:
            lines = " ".join(f"{e.get('message', '')} [{e.get('ref', '')}]" for e in errors[:3])
            return say(f"{text['errors']} {lines}")
        values = {**form, **(result.get("normalized") or {})}
        missing = [f for f in result.get("missing") or [] if not values.get(f)]
        if not missing and "request_create_design" in offered:
            args = {k: values.get(k, "") for k in _FIELDS}
            return ChatTurn(tool_calls=(_call("request_create_design", **args),))
        reserve = ("department", "name", "designer")
        new_mode = form.get("mode", "new") == "new"
        # New design: only SAP's number (and its revision A) is missing -> reservation card.
        if (
            new_mode
            and "design_number" in missing
            and set(missing) <= {"design_number", "revision"}
            and all(values.get(f) for f in reserve)
            and "request_reserve_number" in offered
        ):
            return ChatTurn(
                tool_calls=(_call("request_reserve_number", **{f: values[f] for f in reserve}),)
            )
        if missing:
            names = ", ".join(FIELD_NAMES[lang].get(f, f) for f in missing)
            return say(f"{text['filled']} {text['missing'].format(fields=names)}")
        return say(text["filled"])


def _departments(result: dict[str, Any], lang: str) -> str:
    rows = result.get("departments") or []
    if not rows:
        return _failure(result, lang)
    label = "Departamentos en SAP" if lang == "es" else "Departments in SAP"
    name_key = "name_es" if lang == "es" else "name_en"
    items = "; ".join(
        f"{d.get('code', '')} {d.get(name_key) or d.get('name', '')} ({d.get('lead', '')})"
        for d in rows
    )
    return f"{label}: {items}."


def _design_summary(result: dict[str, Any], lang: str) -> str:
    design = result.get("design")
    if not result.get("found") or not isinstance(design, dict):
        return _failure(result, lang)
    revisions = ", ".join(design.get("revisions") or []) or "–"
    label = "revisiones" if lang == "es" else "revisions"
    summary = (
        f"{design.get('design_number', '')}: {design.get('name', '')}, "
        f"{design.get('status', '')}, {label} {revisions}."
    )
    notes = " ".join(
        f"{n.get('message', '')} [{n.get('ref', '')}]" for n in result.get("status_notes") or []
    )
    return f"{summary} {notes}".strip()


def _failure(result: dict[str, Any], lang: str) -> str:
    """A tool's error, with its manual ref when it has one (e.g. SAP unavailable)."""
    if isinstance(result.get("errors"), list) and result["errors"]:
        return " ".join(
            f"{e.get('message', '')} [{e.get('ref', '')}]" for e in result["errors"][:3]
        )
    error = result.get("error") or result
    message = error.get("message") or ("Sin resultado." if lang == "es" else "No result.")
    ref = error.get("ref")
    return f"{message} [{ref}]" if ref else str(message)


def _language(messages: list[Message]) -> str:
    for m in messages:
        if m.role == "system" and (match := _LANGUAGE_RE.search(m.content)):
            return "es" if match.group(1) == "Spanish" else "en"
    return "en"


def _form(user: str) -> dict[str, str]:
    match = _FORM_RE.search(user)
    data = _json(match.group(1)) if match else {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def _json(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}
