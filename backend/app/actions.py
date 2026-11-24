"""Execute or cancel a pending action: the only place where side effects happen
(invariant 2, decision 0003). Called by `POST /api/actions/{id}/confirm` after the user's
click, and by the developer CLI's `confirm` command.

Before anything happens the values are checked again with the validators and the SAP
record is read fresh, so a confirmed card can't skip a rule or use stale data. The
outcome is stored on the action, written to the audit log (invariant 8) and added to the
conversation as a backend event, so the assistant reports what actually happened.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Engine

from app.agent.prompts import event_message
from app.core.config import Settings
from app.db import store
from app.db.session import write_audit
from app.designs import DesignValidationError, create_design
from app.kicad.exporter import Runner
from app.kicad.renderer import DesignFolderExistsError
from app.sap.client import SapClient, SapError
from app.standards import validators as v
from app.standards.validators import DesignRequest, UnsafePathError


class ActionNotFound(LookupError):
    pass


class ActionNotPending(RuntimeError):
    """Already confirmed, cancelled, running or expired."""

    def __init__(self, action: store.ActionRecord, reason: str) -> None:
        super().__init__(reason)
        self.action = action
        self.reason = reason  # "expired" | "already_<status>"


@dataclass(frozen=True)
class ActionOutcome:
    action: store.ActionRecord
    ok: bool
    error_kind: str | None = None  # validation | sap_unavailable | sap | conflict | internal


def _issue_dict(issue: v.Issue) -> dict[str, Any]:
    return issue.to_dict()


def _not_pending(engine: Engine, action_id: str) -> ActionNotPending:
    action = store.get_action(engine, action_id)
    if action is None:
        raise ActionNotFound(action_id)
    reason = "expired" if action.status == "pending" else f"already_{action.status}"
    return ActionNotPending(action, reason)


def confirm_action(
    action_id: str,
    *,
    settings: Settings,
    engine: Engine,
    sap: SapClient,
    runner: Runner = subprocess.run,
    export: bool = True,
    today: date | None = None,
) -> ActionOutcome:
    if store.get_action(engine, action_id) is None:
        raise ActionNotFound(action_id)
    if not store.claim_action(engine, action_id, to="executing"):
        raise _not_pending(engine, action_id)
    action = store.get_action(engine, action_id)
    assert action is not None

    try:
        if action.kind == "reserve_number":
            result = _reserve(action, sap, engine)
        elif action.kind == "create_design":
            result = _create(action, settings, engine, sap, runner, export, today)
        else:
            result = {"ok": False, "error_kind": "unknown", "message": f"Unknown {action.kind}"}
    except Exception as exc:  # never leave an action stuck in "executing"
        result = {
            "ok": False,
            "error_kind": "internal",
            "message": str(exc),
            "params": {"detail": str(exc)},
        }
        _finish(engine, action, result)
        raise
    return _finish(engine, action, result)


def cancel_action(action_id: str, *, engine: Engine) -> store.ActionRecord:
    if store.get_action(engine, action_id) is None:
        raise ActionNotFound(action_id)
    if not store.claim_action(engine, action_id, to="cancelled"):
        raise _not_pending(engine, action_id)
    action = store.get_action(engine, action_id)
    assert action is not None
    _add_event(engine, action, {"ok": False, "cancelled": True})
    return action


# --- the two side effects ------------------------------------------------------------


def _reserve(action: store.ActionRecord, sap: SapClient, engine: Engine) -> dict[str, Any]:
    p = action.payload
    checks = [
        v.validate_department(p.get("department", "")),
        v.validate_design_name(p.get("name", "")),
        v.validate_designer(p.get("designer", "")),
    ]
    errors = [e for c in checks for e in c.errors]
    if errors:
        return _validation_failure(errors)
    department, name, designer = (c.value for c in checks)
    try:
        design = sap.reserve_number(department, name, designer)
    except SapError as exc:
        return _sap_failure(exc)
    write_audit(
        engine,
        action="number_reserved",
        actor=designer,
        design_number=design.design_number,
        revision=design.current_revision or v.FIRST_REVISION,
        details={
            "name": design.name,
            "department": design.department,
            "sap_material": design.material,
            "project": design.wbs,
            "action_id": action.id,
        },
    )
    return {
        "ok": True,
        "design_number": design.design_number,
        "department": design.department,
        "name": design.name,
        "revision": design.current_revision or v.FIRST_REVISION,
        "sap_material": design.material,
        "project": design.wbs,
        "status": design.status,
    }


def _create(
    action: store.ActionRecord,
    settings: Settings,
    engine: Engine,
    sap: SapClient,
    runner: Runner,
    export: bool,
    today: date | None,
) -> dict[str, Any]:
    p = action.payload
    request = DesignRequest(
        department=p.get("department", ""),
        design_number=p.get("design_number", ""),
        revision=p.get("revision", ""),
        name=p.get("name", ""),
        designer=p.get("designer", ""),
        description=p.get("description", "") or "",
    )
    number = v.validate_design_number(request.design_number, request.department)
    if not number.ok:
        return _validation_failure(list(number.errors))
    try:
        record = sap.get_design(number.value)
    except SapError as exc:
        return _sap_failure(exc)
    try:
        created = create_design(
            request,
            settings=settings,
            export=export,
            today=today,
            engine=engine,
            runner=runner,
            sap=record,
            require_sap=True,
            audit_details={"action_id": action.id},
            record_revision=sap.add_revision,
        )
    except DesignValidationError as exc:
        return _validation_failure(list(exc.report.errors))
    except UnsafePathError as exc:
        return _validation_failure([exc.issue])
    except DesignFolderExistsError as exc:
        return {
            "ok": False,
            "error_kind": "conflict",
            "message": f"{exc} Nothing was overwritten.",
            "ref": "04-folder-structure#revision-folders",
            "params": {"folder": exc.folder},
        }
    except SapError as exc:  # SAP refused the new revision: nothing was written
        return _sap_failure(exc)
    req = created.request
    return {
        "ok": True,
        "design_number": req.design_number,
        "revision": req.revision,
        "name": req.name,
        "folder": created.relative_folder,
        "pdf": created.export is not None,
        "sap_material": req.sap_material,
        "project": req.project,
        "warnings": [_issue_dict(w) for w in created.warnings],
        "audit_id": created.audit_id,
    }


# --- outcome -------------------------------------------------------------------------


def _validation_failure(errors: list[v.Issue]) -> dict[str, Any]:
    return {
        "ok": False,
        "error_kind": "validation",
        "message": "The values break a rule of the Design Manual; nothing was done.",
        "params": {},
        "errors": [_issue_dict(e) for e in errors],
    }


def _sap_failure(exc: SapError) -> dict[str, Any]:
    if exc.unavailable:
        return {
            "ok": False,
            "error_kind": "sap_unavailable",
            "message": f"SAP is not available ({exc.message}); nothing was done. Try again later.",
            "ref": "06-sap-statuses#sap-unavailable",
            "params": {"sap_code": exc.code, "detail": exc.message},
        }
    return {
        "ok": False,
        "error_kind": "sap",
        "message": f"SAP refused: {exc.code} {exc.message}",
        "params": {"sap_code": exc.code, "detail": exc.message},
    }


def _add_event(engine: Engine, action: store.ActionRecord, result: dict[str, Any]) -> None:
    event = {"action_id": action.id, "kind": action.kind, **result}
    status = "cancelled" if result.get("cancelled") else ("done" if result["ok"] else "failed")
    event["outcome"] = status
    store.append_messages(
        engine,
        action.conversation_id,
        [{"role": "event", "content": event_message(event), "event": event}],
    )


def _finish(engine: Engine, action: store.ActionRecord, result: dict[str, Any]) -> ActionOutcome:
    status = "confirmed" if result["ok"] else "failed"
    store.finish_action(engine, action.id, status=status, result=result)
    _add_event(engine, action, result)
    final = store.get_action(engine, action.id)
    assert final is not None
    return ActionOutcome(final, ok=result["ok"], error_kind=result.get("error_kind"))
