"""HTTP API and the operator console.

Authentication is a demo stand-in: the `X-User-Id` header picks one of the synthetic
users (anna = operator, ben = viewer, clara = operator in another organisation). Real
authentication is a pre-pilot requirement (docs/02-build/threat-model.md).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, workflow
from .agent import InquiryAgent
from .config import Settings, load_settings
from .domain import User
from .providers import LLMProvider, make_provider
from .render import slot_display
from .seed import seed
from .state_machine import InquiryState, InvalidTransition, allowed_targets, to_mermaid
from .store import NotFound, Store
from .tools import ToolRegistry

WEB_DIR = Path(__file__).parent / "web"


class IngestBody(BaseModel):
    unit_id: str
    message: str = Field(min_length=1, max_length=5000)
    applicant_display_name: str | None = Field(default=None, max_length=80)
    contact_channel: str | None = "email"


class ApproveBody(BaseModel):
    final_text: str | None = Field(default=None, max_length=2500)
    override_reason: str | None = Field(default=None, max_length=300)


class RejectBody(BaseModel):
    reason_code: str = Field(default="rejected_by_operator", max_length=60)


class ManualReplyBody(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    slot_ids: list[str] = Field(default_factory=list, max_length=5)


class AcceptBody(BaseModel):
    slot_id: str


def _ensure_seeded(store: Store) -> None:
    try:
        store.list_users()
    except sqlite3.OperationalError:
        seed(store)


def create_app(settings: Settings | None = None, store: Store | None = None,
               provider: LLMProvider | None = None, tools: ToolRegistry | None = None) -> FastAPI:
    settings = settings or load_settings()
    if store is None:
        store = Store(settings.db_path)
        _ensure_seeded(store)
    provider = provider or make_provider(settings)
    tools = tools or ToolRegistry()
    agent = InquiryAgent(store, provider, settings, tools)

    app = FastAPI(title="Munich Rental Copilot — synthetic demo", version=__version__,
                  description="Human-in-the-loop inquiry-to-viewing copilot. "
                              "Synthetic data only. Not production-ready.")
    app.state.store, app.state.agent = store, agent

    @app.exception_handler(NotFound)
    def _not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Not found: {exc}"})

    @app.exception_handler(workflow.WorkflowError)
    def _workflow_error(_: Request, exc: workflow.WorkflowError) -> JSONResponse:
        body: dict[str, Any] = {"detail": str(exc)}
        if isinstance(exc, workflow.Rejected):
            body["findings"] = [f.model_dump() for f in exc.findings]
        return JSONResponse(status_code=exc.status, content=body)

    @app.exception_handler(InvalidTransition)
    def _invalid_transition(_: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    def current_user(x_user_id: str | None = Header(default=None)) -> User:
        if not x_user_id:
            raise HTTPException(status_code=401, detail="Send the X-User-Id header (demo users: anna, ben, clara).")
        try:
            return store.get_user(x_user_id)
        except NotFound as exc:
            raise HTTPException(status_code=401, detail="Unknown user") from exc

    def operator(user: User = Depends(current_user)) -> User:
        if user.role != "operator":
            raise HTTPException(status_code=403, detail="Only operators can do this. Viewers have read access only.")
        return user

    # ------------------------------------------------------------------ console
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    # ------------------------------------------------------------------ meta
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "data_mode": settings.data_mode, "provider": provider.name,
                "prompt_version": provider.prompt_version, "version": __version__}

    @app.get("/api/users")
    def users() -> list[dict[str, Any]]:
        return [u.model_dump() for u in store.list_users()]  # demo user switcher; synthetic users only

    @app.get("/api/me")
    def me(user: User = Depends(current_user)) -> dict[str, Any]:
        return user.model_dump()

    @app.get("/api/meta")
    def meta(_: User = Depends(current_user)) -> dict[str, Any]:
        return {
            "states": [s.value for s in InquiryState],
            "transitions": {s.value: sorted(t.value for t in allowed_targets(s)) for s in InquiryState},
            "mermaid": to_mermaid(),
            "tools": tools.permission_matrix(),
            "contract_version": "agent_output.v1",
            "provider": provider.name,
            "prompt_version": provider.prompt_version,
        }

    # ------------------------------------------------------------------ read
    @app.get("/api/units")
    def units(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        return [u.model_dump(mode="json") for u in store.list_units(user.org_id)]

    @app.get("/api/inquiries")
    def inquiries(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        items = []
        for inq in store.list_inquiries(user.org_id):
            run = store.latest_run(user.org_id, inq.inquiry_id) or {}
            draft = store.latest_draft(user.org_id, inq.inquiry_id)
            items.append({
                "inquiry_id": inq.inquiry_id, "unit_id": inq.unit_id, "received_at": inq.received_at.isoformat(),
                "applicant_display_name": inq.applicant_display_name, "state": inq.state.value,
                "preview": inq.message[:140], "erased": inq.erased_at is not None,
                "intent": run.get("intent"), "risk_flags": run.get("risk_flags", []),
                "escalation_required": run.get("escalation_required", False),
                "draft_status": draft.status if draft else None,
            })
        return items

    @app.get("/api/inquiries/{inquiry_id}")
    def inquiry_detail(inquiry_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        inq = store.get_inquiry(user.org_id, inquiry_id)
        unit = store.get_unit(user.org_id, inq.unit_id)
        draft = store.latest_draft(user.org_id, inquiry_id)
        language = "en" if (store.latest_run(user.org_id, inquiry_id) or {}).get("language") == "en" else "de"
        slots = [{**s.model_dump(mode="json"), "free": s.free, "display": slot_display(s.starts_at, language)}
                 for s in store.list_slots(user.org_id, inq.unit_id)]
        return {
            "inquiry": inq.model_dump(mode="json"),
            "unit": {"unit_id": unit.unit_id, "title": unit.title, "district": unit.district,
                     "facts": [f.model_dump(mode="json") for f in unit.facts]},
            "run": store.latest_run(user.org_id, inquiry_id),
            "draft": draft.model_dump(mode="json") if draft else None,
            "tasks": [t.model_dump(mode="json") for t in store.list_tasks(user.org_id, inquiry_id)],
            "audit": [e.model_dump(mode="json") for e in store.list_audit(user.org_id, inquiry_id)],
            "slots": slots,
            "allowed_next_states": sorted(s.value for s in allowed_targets(inq.state)),
        }

    @app.get("/api/audit")
    def audit_log(entity_id: str | None = None, user: User = Depends(current_user)) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in store.list_audit(user.org_id, entity_id)]

    # ------------------------------------------------------------------ actions
    @app.post("/api/inquiries", status_code=201)
    def ingest(body: IngestBody, user: User = Depends(operator)) -> dict[str, Any]:
        inq = workflow.ingest_inquiry(store, user, body.unit_id, body.message, body.applicant_display_name,
                                      body.contact_channel)
        return inq.model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/process")
    def process(inquiry_id: str, user: User = Depends(operator)) -> dict[str, Any]:
        return agent.process(user.org_id, inquiry_id).model_dump(mode="json")

    @app.post("/api/inquiries/process-all")
    def process_all(user: User = Depends(operator)) -> dict[str, Any]:
        done = [agent.process(user.org_id, i.inquiry_id).inquiry_id for i in store.list_inquiries(user.org_id)
                if i.state == InquiryState.INQUIRY_RECEIVED]
        return {"processed": done}

    @app.post("/api/drafts/{draft_id}/approve")
    def approve(draft_id: str, body: ApproveBody, user: User = Depends(operator)) -> dict[str, Any]:
        draft = workflow.approve_draft(store, user, draft_id, body.final_text, body.override_reason)
        return draft.model_dump(mode="json")

    @app.post("/api/drafts/{draft_id}/reject")
    def reject(draft_id: str, body: RejectBody, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.reject_draft(store, user, draft_id, body.reason_code).model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/manual-reply")
    def manual_reply(inquiry_id: str, body: ManualReplyBody, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.submit_manual_reply(store, user, inquiry_id, body.text, body.slot_ids).model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/mark-sent")
    def mark_sent(inquiry_id: str, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.mark_sent(store, user, inquiry_id).model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/accept-slot")
    def accept_slot(inquiry_id: str, body: AcceptBody, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.accept_slot(store, tools, user, inquiry_id, body.slot_id).model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/stop")
    def stop(inquiry_id: str, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.record_stop(store, tools, user, inquiry_id).model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/delete-data")
    def delete_data(inquiry_id: str, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.request_deletion(store, tools, user, inquiry_id).model_dump(mode="json")

    @app.post("/api/inquiries/{inquiry_id}/close")
    def close(inquiry_id: str, user: User = Depends(operator)) -> dict[str, Any]:
        return workflow.close_inquiry(store, user, inquiry_id).model_dump(mode="json")

    @app.post("/api/demo/reset")
    def reset(_: User = Depends(operator)) -> dict[str, str]:
        seed(store)
        return {"status": "reset", "data_mode": settings.data_mode}

    return app
