"""The confirmation gate (invariant 2, decision 0003).

`POST /api/actions/{id}/confirm` is called by the user's click on a confirmation card.
It is the only endpoint that reserves a SAP number or creates design files; the model
can't reach it. Status codes: 200 done, 404 unknown, 409 already decided, 410 expired,
422 a rule is broken, 409 the folder exists, 502 SAP failed. A failed PDF export is not a
failure: the project is kept and the result has a `pdf_not_exported` warning (decision 0023).
The body is always the action with its result.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
from app.api.deps import EngineDep, RateLimited, RunnerDep, SapFactoryDep, SettingsDep
from app.db import store

router = APIRouter(prefix="/api/actions", tags=["actions"])

FAILURE_STATUS = {
    "validation": 422,
    "conflict": 409,
    "sap_unavailable": 502,
    "sap": 502,
}


def _not_pending(exc: ActionNotPending) -> JSONResponse:
    status = 410 if exc.reason == "expired" else 409
    return JSONResponse({"detail": exc.reason, "action": exc.action.to_dict()}, status_code=status)


@router.get("/{action_id}")
def get_action(action_id: str, engine: EngineDep) -> dict:
    action = store.get_action(engine, action_id)
    if action is None:
        raise HTTPException(404, "Action not found")
    return action.to_dict()


@router.post("/{action_id}/confirm", dependencies=[RateLimited])
def confirm(
    action_id: str,
    settings: SettingsDep,
    engine: EngineDep,
    sap_factory: SapFactoryDep,
    runner: RunnerDep,
) -> JSONResponse:
    try:
        with sap_factory() as sap:
            outcome = confirm_action(
                action_id, settings=settings, engine=engine, sap=sap, runner=runner
            )
    except ActionNotFound as exc:
        raise HTTPException(404, "Action not found") from exc
    except ActionNotPending as exc:
        return _not_pending(exc)
    status = 200 if outcome.ok else FAILURE_STATUS.get(outcome.error_kind or "", 500)
    return JSONResponse(outcome.action.to_dict(), status_code=status)


@router.post("/{action_id}/cancel", dependencies=[RateLimited])
def cancel(action_id: str, engine: EngineDep) -> JSONResponse:
    try:
        action = cancel_action(action_id, engine=engine)
    except ActionNotFound as exc:
        raise HTTPException(404, "Action not found") from exc
    except ActionNotPending as exc:
        return _not_pending(exc)
    return JSONResponse(action.to_dict())
