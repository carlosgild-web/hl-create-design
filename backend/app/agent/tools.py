"""The assistant's tools (PLAN §4). The model can read and propose; it can't act.

- Read tools ask the deterministic validators, SAP (through `SapClient`), the manual
  index and the designs folder. The validators decide (invariant 1).
- `propose_form_values` fills the form on screen; the user can still edit it.
- The gated tools `request_create_design` and `request_reserve_number` only record a
  pending action and return its id. The side effect happens in
  `POST /api/actions/{id}/confirm`, after the user's click (invariant 2, decision 0003).

A run may open at most one confirmation card per kind, so text that talks the model into
"create 10 designs" ends with one card and no files (invariant 7).

Each tool returns a JSON-serializable dict: exactly what the model sees.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Engine

from app.core.config import Settings
from app.db import store
from app.designs import check_design_request
from app.llm.base import ToolCall, ToolSpec
from app.sap.client import SapClient, SapDesign, SapError
from app.standards import validators as v
from app.standards.manual_search import ManualIndex
from app.standards.validators import DesignRequest, Issue, UnsafePathError

FREE_TEXT_MAX = 200
GATED_TOOLS = frozenset({"request_create_design", "request_reserve_number"})
FORM_FIELDS = ("department", "design_number", "revision", "name", "designer")


# --- context and results -------------------------------------------------------------


@dataclass
class ToolContext:
    settings: Settings
    sap: SapClient
    manual: ManualIndex
    engine: Engine
    conversation_id: str
    run_id: int | None = None
    language: str = "en"
    opened_actions: dict[str, str] = field(default_factory=dict)  # kind -> action id


@dataclass(frozen=True)
class ToolResult:
    """`content` goes back to the model; `event` (optional) goes to the UI."""

    content: dict[str, Any]
    ok: bool = True
    event: dict[str, Any] | None = None

    def for_model(self) -> str:
        return json.dumps(self.content, ensure_ascii=False)


def _issue(issue: Issue) -> dict[str, str]:
    return {"field": issue.field, "code": issue.code, "message": issue.message, "ref": issue.ref}


def _error(code: str, message: str, ref: str | None = None) -> ToolResult:
    content: dict[str, Any] = {"error": {"code": code, "message": message}}
    if ref:
        content["error"]["ref"] = ref
    return ToolResult(content, ok=False)


def _sap_error(exc: SapError) -> ToolResult:
    if exc.unavailable:
        return _error(
            "sap_unavailable",
            f"SAP is not available right now ({exc.message}). Nothing was checked in SAP; "
            "try again later.",
            "06-sap-statuses#sap-unavailable",
        )
    return _error("sap_error", f"SAP answered {exc.code}: {exc.message}")


# --- argument models -----------------------------------------------------------------


class _Args(BaseModel):
    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True, str_strip_whitespace=True)


def _text(description: str) -> Any:
    return Field(default="", max_length=FREE_TEXT_MAX, description=description)


class SearchManualArgs(_Args):
    query: str = Field(min_length=1, max_length=FREE_TEXT_MAX, description="Keywords to look up")
    language: Literal["en", "es", ""] = Field(
        default="", description="Language of the passages: 'en' or 'es' (the user's language)"
    )


class DesignFieldsArgs(_Args):
    department: str = _text("Department code: HW, PWR, EMB or TFX")
    design_number: str = _text("Design number, e.g. HL-HW-26-0042")
    revision: str = _text("Revision letter, e.g. A")
    name: str = _text("Design name, e.g. Bead Drill Controller")
    designer: str = _text("Designer as initial and surname, e.g. C. Velazquez")


class DesignNumberArgs(_Args):
    design_number: str = Field(min_length=1, max_length=40, description="e.g. HL-HW-26-0042")


class NoArgs(_Args):
    pass


class FolderArgs(_Args):
    department: str = Field(max_length=10, description="Department code, e.g. HW")
    design_number: str = Field(max_length=40, description="e.g. HL-HW-26-0042")
    revision: str = Field(default="", max_length=4, description="Revision letter (optional)")


class ReserveArgs(_Args):
    department: str = Field(max_length=10, description="Department code: HW, PWR, EMB or TFX")
    name: str = Field(max_length=FREE_TEXT_MAX, description="Design name")
    designer: str = Field(max_length=FREE_TEXT_MAX, description="Designer, e.g. C. Velazquez")


class CreateArgs(_Args):
    department: str = Field(max_length=10, description="Department code")
    design_number: str = Field(max_length=40, description="Design number reserved in SAP")
    revision: str = Field(max_length=4, description="Revision letter")
    name: str = Field(max_length=FREE_TEXT_MAX, description="Design name")
    designer: str = Field(max_length=FREE_TEXT_MAX, description="Designer, e.g. C. Velazquez")


# --- read tools ----------------------------------------------------------------------


def search_design_manual(args: SearchManualArgs, ctx: ToolContext) -> ToolResult:
    passages = ctx.manual.search(args.query, lang=args.language or ctx.language)
    if not passages:
        return ToolResult({"passages": [], "note": "No passage matched; try other keywords."})
    return ToolResult({"passages": [p.to_dict() for p in passages]})


def _sap_lookup(ctx: ToolContext, number: str) -> tuple[SapDesign | None, ToolResult | None]:
    try:
        return ctx.sap.get_design(number), None
    except SapError as exc:
        return None, _sap_error(exc)


def validate_design_request(args: DesignFieldsArgs, ctx: ToolContext) -> ToolResult:
    """Check the fields given so far. Missing fields are listed, not reported as errors."""
    given = {name: getattr(args, name) for name in FORM_FIELDS if getattr(args, name)}
    if not given:
        return _error("no_fields", "Pass at least one field to check.")
    request = DesignRequest(**{name: given.get(name, "") for name in FORM_FIELDS})

    sap: SapDesign | None = None
    sap_note: dict[str, Any] | None = None
    number_ok = v.validate_design_number(request.design_number, request.department or None).ok
    if request.design_number and number_ok:
        sap, failure = _sap_lookup(ctx, request.design_number.strip())
        if failure is not None:
            sap_note = failure.content["error"]

    try:
        report = check_design_request(
            request,
            ctx.settings.designs_root,
            sap=sap,
            require_sap=bool(request.design_number and number_ok and sap_note is None),
        )
    except UnsafePathError as exc:
        return ToolResult({"ok": False, "errors": [_issue(exc.issue)]})

    # Without a design number the revision can only be checked for its format.
    sequence_codes = {"rev_first_not_a", "rev_jump", "rev_reused"}
    errors = [
        _issue(e)
        for e in report.errors
        if (e.field in given or e.field == "status")
        and not ("design_number" not in given and e.code in sequence_codes)
    ]
    content: dict[str, Any] = {
        "ok": not errors,
        "normalized": {k: getattr(report.request, k) for k in given},
        "errors": errors,
        "warnings": [_issue(w) for w in report.warnings],
        "missing": [name for name in FORM_FIELDS if name not in given],
    }
    if "design_number" in given:
        content["next_free_revision"] = report.next_revision
    if sap is not None:
        content["sap"] = {"status": sap.status, "material": sap.material, "wbs": sap.wbs}
    if sap_note is not None:
        content["sap_unavailable"] = sap_note
    return ToolResult(content)


def sap_get_design(args: DesignNumberArgs, ctx: ToolContext) -> ToolResult:
    check = v.validate_design_number(args.design_number)
    if not check.ok:
        return ToolResult({"found": False, "errors": [_issue(e) for e in check.errors]})
    design, failure = _sap_lookup(ctx, check.value)
    if failure is not None:
        return failure
    if design is None:
        unknown = v.check_known_in_sap(check.value, found=False)
        return ToolResult({"found": False, "errors": [_issue(e) for e in unknown.errors]})
    content: dict[str, Any] = {"found": True, "design": design.to_dict()}
    status = v.check_status_allows_revision(
        design.status, block_reason=design.block_reason or None, successor=design.successor or None
    )
    content["new_revision_allowed"] = status.ok
    content["status_notes"] = [_issue(i) for i in (*status.errors, *status.warnings)]
    return ToolResult(content)


def sap_list_departments(_: NoArgs, ctx: ToolContext) -> ToolResult:
    try:
        departments = ctx.sap.list_departments()
    except SapError as exc:
        return _sap_error(exc)
    return ToolResult({"departments": [d.to_dict() for d in departments]})


def check_design_folder(args: FolderArgs, ctx: ToolContext) -> ToolResult:
    dept, number = args.department.upper(), args.design_number.upper()
    try:
        on_disk = v.revisions_on_disk(ctx.settings.designs_root, dept, number)
        rev = args.revision.upper() or v.next_revision(on_disk)
        folder = v.design_folder(ctx.settings.designs_root, dept, number, rev)
    except UnsafePathError as exc:
        return ToolResult({"inside_root": False, "errors": [_issue(exc.issue)]})
    return ToolResult(
        {
            "inside_root": True,
            "folder": f"{dept}/{number}/{rev}",
            "exists": folder.exists(),
            "revisions_on_disk": on_disk,
            "next_free_revision_on_disk": v.next_revision(on_disk),
            "note": "SAP may know more revisions than the folders; validate_design_request "
            "checks both.",
        }
    )


# --- UI tool -------------------------------------------------------------------------


def propose_form_values(args: DesignFieldsArgs, _: ToolContext) -> ToolResult:
    fields = {name: getattr(args, name) for name in FORM_FIELDS if getattr(args, name)}
    if not fields:
        return _error("no_fields", "Pass at least one field to fill in.")
    return ToolResult(
        {"shown_to_user": True, "fields": fields, "note": "The user can edit these values."},
        event={"type": "form_proposal", "fields": fields},
    )


# --- gated tools ---------------------------------------------------------------------


def _one_card_per_kind(kind: str, ctx: ToolContext) -> ToolResult | None:
    if kind in ctx.opened_actions:
        return _error(
            "card_already_open",
            f"A confirmation card for {kind} is already open in this turn "
            f"(action {ctx.opened_actions[kind]}). Only one per turn; wait for the user.",
        )
    return None


def _open_card(kind: str, payload: dict[str, Any], ctx: ToolContext, summary: str) -> ToolResult:
    action = store.create_action(
        ctx.engine,
        conversation_id=ctx.conversation_id,
        run_id=ctx.run_id,
        kind=kind,
        payload=payload,
    )
    ctx.opened_actions[kind] = action.id
    return ToolResult(
        {
            "action_id": action.id,
            "status": "pending_confirmation",
            "values": payload,
            "note": f"Nothing has happened yet. A card asks the user to confirm: {summary}. "
            "Do not say it is done; the result arrives after the user's click.",
        },
        event={"type": "pending_action", "action": action.to_dict()},
    )


def request_reserve_number(args: ReserveArgs, ctx: ToolContext) -> ToolResult:
    if (blocked := _one_card_per_kind("reserve_number", ctx)) is not None:
        return blocked
    checks = {
        "department": v.validate_department(args.department),
        "name": v.validate_design_name(args.name),
        "designer": v.validate_designer(args.designer),
    }
    errors = [_issue(e) for c in checks.values() for e in c.errors]
    if errors:
        return ToolResult({"ok": False, "errors": errors, "note": "No card was opened."})
    payload = {name: check.value for name, check in checks.items()}
    return _open_card(
        "reserve_number",
        payload,
        ctx,
        f"reserve a new {payload['department']} number for '{payload['name']}'",
    )


def request_create_design(args: CreateArgs, ctx: ToolContext) -> ToolResult:
    if (blocked := _one_card_per_kind("create_design", ctx)) is not None:
        return blocked
    request = DesignRequest(**{name: getattr(args, name) for name in FORM_FIELDS})
    number_ok = v.validate_design_number(request.design_number, request.department).ok
    sap, failure = _sap_lookup(ctx, request.design_number.strip()) if number_ok else (None, None)
    if failure is not None:
        return failure
    try:
        report = check_design_request(
            request, ctx.settings.designs_root, sap=sap, require_sap=number_ok
        )
    except UnsafePathError as exc:
        return ToolResult({"ok": False, "errors": [_issue(exc.issue)], "note": "No card opened."})
    if not report.ok:
        return ToolResult(
            {
                "ok": False,
                "errors": [_issue(e) for e in report.errors],
                "next_free_revision": report.next_revision,
                "note": "No card was opened. Explain the errors to the user.",
            }
        )
    req = report.request
    payload = {name: getattr(req, name) for name in FORM_FIELDS}
    payload |= {"sap_material": req.sap_material, "project": req.project}
    payload["warnings"] = [_issue(w) for w in report.warnings]
    return _open_card(
        "create_design",
        payload,
        ctx,
        f"create {req.design_number} revision {req.revision} '{req.name}'",
    )


# --- registry ------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[_Args]
    run: Callable[[Any, ToolContext], ToolResult]

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, _schema(self.args))


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    """A plain JSON schema (no titles, no anyOf) that small models handle well."""
    schema = model.model_json_schema()
    properties = {}
    for name, prop in schema.get("properties", {}).items():
        clean = {k: val for k, val in prop.items() if k in ("type", "description", "enum")}
        if "enum" in clean:
            clean["enum"] = [e for e in clean["enum"] if e != ""]
        properties[name] = clean
    return {"type": "object", "properties": properties, "required": schema.get("required", [])}


TOOLS: tuple[Tool, ...] = (
    Tool(
        "search_design_manual",
        "Search the company Design Manual. Returns passages with a source id to cite, "
        "like [02-revisions#skipped-letters].",
        SearchManualArgs,
        search_design_manual,
    ),
    Tool(
        "validate_design_request",
        "Check design fields against the company rules and SAP. Pass only the fields the "
        "user gave. Returns errors and warnings with manual references, and the next "
        "free revision.",
        DesignFieldsArgs,
        validate_design_request,
    ),
    Tool(
        "sap_get_design",
        "Look up a design number in SAP: status, material, project (WBS), revisions.",
        DesignNumberArgs,
        sap_get_design,
    ),
    Tool(
        "sap_list_departments",
        "List the departments in SAP with their codes, names and leads.",
        NoArgs,
        sap_list_departments,
    ),
    Tool(
        "check_design_folder",
        "Check the design folder: its path inside the designs root, whether it exists, "
        "and the revision folders on disk.",
        FolderArgs,
        check_design_folder,
    ),
    Tool(
        "propose_form_values",
        "Fill fields of the form on the user's screen. The user can edit them.",
        DesignFieldsArgs,
        propose_form_values,
    ),
    Tool(
        "request_reserve_number",
        "Ask the user to confirm reserving a NEW design number in SAP. Opens a "
        "confirmation card; nothing is reserved until the user clicks Confirm.",
        ReserveArgs,
        request_reserve_number,
    ),
    Tool(
        "request_create_design",
        "Ask the user to confirm creating the KiCad project for a design revision. Opens a "
        "confirmation card; nothing is created until the user clicks Confirm.",
        CreateArgs,
        request_create_design,
    ),
)


class ToolRegistry:
    def __init__(self, tools: tuple[Tool, ...] = TOOLS) -> None:
        self._tools = {t.name: t for t in tools}

    @property
    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    def execute(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            names = ", ".join(self._tools)
            return _error("unknown_tool", f"There is no tool '{call.name}'. Tools: {names}.")
        if "__invalid__" in call.arguments:
            return _error("invalid_arguments", "The arguments were not valid JSON.")
        try:
            args = tool.args.model_validate(call.arguments)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
                for e in exc.errors()
            )
            return _error("invalid_arguments", problems)
        try:
            return tool.run(args, ctx)
        except SapError as exc:
            return _sap_error(exc)
