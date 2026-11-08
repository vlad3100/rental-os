"""Operator actions: the human half of human-in-the-loop.

Every action follows the same order: permission → state check → tool (if any) →
transition → audit. Approving a draft re-runs the guardrails on the final text; a human
can override a blocking finding only by writing down a reason, which is audited.
The system never sends: "mark sent" records that the operator sent the approved text
from their own mailbox or portal.
"""
from __future__ import annotations

from typing import Any

from .audit import audit
from .domain import DraftRecord, DraftSlot, Finding, Inquiry, User
from .guardrails import check_draft, detect_language, has_block
from .render import slot_display
from .state_machine import ActorKind, InquiryState, InvalidTransition, check_transition
from .store import Store, new_id, utcnow
from .tools import ToolContext, ToolDenied, ToolRegistry

S = InquiryState


class WorkflowError(Exception):
    status = 409


class Forbidden(WorkflowError):
    status = 403


class Conflict(WorkflowError):
    status = 409


class Rejected(WorkflowError):
    """Guardrails blocked a human-written text and no override reason was given."""
    status = 422

    def __init__(self, findings: list[Finding]):
        super().__init__("Guardrails blocked this text. Fix it, or give an override reason.")
        self.findings = findings


def _actor(user: User) -> str:
    return f"operator:{user.user_id}"


def _require_operator(user: User) -> None:
    if user.role != "operator":
        raise Forbidden("Only operators can do this. Viewers have read access only.")


def _move(store: Store, inquiry: Inquiry, dst: InquiryState, actor: str, kind: ActorKind) -> None:
    src = inquiry.state
    try:
        check_transition(src, dst, kind)
    except InvalidTransition as exc:
        raise Conflict(str(exc)) from exc
    store.set_inquiry_state(inquiry.org_id, inquiry.inquiry_id, dst)
    inquiry.state = dst
    audit(store, inquiry.org_id, actor, "state_changed", "inquiry", inquiry.inquiry_id,
          from_state=src.value, to_state=dst.value)


def _tool(store: Store, tools: ToolRegistry, inquiry: Inquiry, actor: str, kind: ActorKind, name: str,
          **args: Any) -> Any:
    ctx = ToolContext(store, inquiry.org_id, actor, kind, inquiry)
    try:
        result = tools.call(name, ctx, **args)
    except ToolDenied as exc:
        raise Conflict(str(exc)) from exc
    if not result.ok:
        raise Conflict(result.error or f"{name} failed")
    return result.data


def _check_human_text(store: Store, inquiry: Inquiry, text: str, fact_ids: list[str],
                      slot_ids: list[str]) -> list[Finding]:
    unit = store.get_unit(inquiry.org_id, inquiry.unit_id)
    language = detect_language(inquiry.message)
    slots = [s for s in store.list_slots(inquiry.org_id, inquiry.unit_id) if s.slot_id in slot_ids]
    draft_slots = [DraftSlot(slot_id=s.slot_id, starts_at=s.starts_at, display=slot_display(s.starts_at, language))
                   for s in slots]
    knowledge = store.list_knowledge(inquiry.org_id, language)
    return check_draft(text, unit=unit, fact_ids_used=fact_ids, slots=draft_slots, knowledge=knowledge,
                       expected_language=language)


# ------------------------------------------------------------------ intake (synthetic)
def ingest_inquiry(store: Store, user: User, unit_id: str, message: str, display_name: str | None = None,
                   contact_channel: str | None = "email") -> Inquiry:
    _require_operator(user)
    store.get_unit(user.org_id, unit_id)  # NotFound for units of other organisations
    message = message.strip()
    if not 1 <= len(message) <= 5000:
        raise Conflict("Message must be between 1 and 5,000 characters.")
    if contact_channel not in (None, "email", "phone", "address"):
        raise Conflict("contact_channel must be email, phone, address or empty.")
    inquiry = Inquiry(org_id=user.org_id, inquiry_id=new_id("INQ"), unit_id=unit_id, received_at=utcnow(),
                      applicant_ref=new_id("APP"), applicant_display_name=display_name or None,
                      contact_channel=contact_channel, message=message)  # type: ignore[arg-type]
    store.add_inquiry(inquiry)
    audit(store, user.org_id, _actor(user), "inquiry_ingested", "inquiry", inquiry.inquiry_id, actor_role=user.role)
    return inquiry


# ------------------------------------------------------------------ review
def approve_draft(store: Store, user: User, draft_id: str, final_text: str | None = None,
                  override_reason: str | None = None) -> DraftRecord:
    _require_operator(user)
    draft = store.get_draft(user.org_id, draft_id)
    inquiry = store.get_inquiry(user.org_id, draft.inquiry_id)
    if draft.status != "pending_review" or inquiry.state != S.REPLY_HUMAN_REVIEW:
        raise Conflict(f"Draft is {draft.status} and inquiry is {inquiry.state.value}; nothing to approve.")
    text = (final_text if final_text is not None else draft.text or "").strip()
    if not text:
        raise Conflict("The reply text is empty.")
    edited = text != (draft.text or "").strip()
    findings = draft.findings
    if edited:
        fact_ids = draft.fact_ids_used if draft.author == "agent" else \
            [f.fact_id for f in store.get_unit(user.org_id, inquiry.unit_id).facts if f.usable]
        findings = _check_human_text(store, inquiry, text, fact_ids, draft.proposed_slot_ids)
    override = bool(override_reason and override_reason.strip())
    if has_block(findings) and not override:
        raise Rejected(findings)
    draft.status, draft.final_text, draft.findings = "approved", text, findings
    draft.reviewed_by, draft.reviewed_at = user.user_id, utcnow()
    draft.override_reason = override_reason.strip() if override else None
    store.save_draft(draft)
    _move(store, inquiry, S.REPLY_APPROVED, _actor(user), "operator")
    audit(store, user.org_id, _actor(user), "draft_approved", "inquiry", inquiry.inquiry_id, draft_id=draft_id,
          edited=edited, override=override, finding_codes=[f.code for f in findings])
    return draft


def reject_draft(store: Store, user: User, draft_id: str, reason_code: str = "rejected_by_operator") -> DraftRecord:
    _require_operator(user)
    draft = store.get_draft(user.org_id, draft_id)
    inquiry = store.get_inquiry(user.org_id, draft.inquiry_id)
    if draft.status != "pending_review":
        raise Conflict(f"Draft is {draft.status}; only pending drafts can be rejected.")
    draft.status, draft.reviewed_by, draft.reviewed_at = "rejected", user.user_id, utcnow()
    store.save_draft(draft)
    _move(store, inquiry, S.NEEDS_HUMAN_REVIEW, _actor(user), "operator")
    audit(store, user.org_id, _actor(user), "draft_rejected", "inquiry", inquiry.inquiry_id, draft_id=draft_id,
          reason_code=reason_code[:60])
    return draft


def submit_manual_reply(store: Store, user: User, inquiry_id: str, text: str,
                        slot_ids: list[str] | None = None) -> DraftRecord:
    """An operator writes the reply (e.g. for human-only intents). It still gets checked."""
    _require_operator(user)
    inquiry = store.get_inquiry(user.org_id, inquiry_id)
    if inquiry.state != S.NEEDS_HUMAN_REVIEW:
        raise Conflict(f"Manual replies are for inquiries in needs_human_review (now {inquiry.state.value}).")
    if store.contact_blocks(user.org_id, inquiry.applicant_ref):
        raise Conflict("This applicant has a stop or deletion record. Do not reply.")
    text = text.strip()
    if not 1 <= len(text) <= 2500:
        raise Conflict("Reply must be between 1 and 2,500 characters.")
    unit = store.get_unit(user.org_id, inquiry.unit_id)
    fact_ids = [f.fact_id for f in unit.facts if f.usable]
    free = {s.slot_id for s in store.list_slots(user.org_id, inquiry.unit_id) if s.free}
    slot_ids = [s for s in (slot_ids or []) if s in free]
    findings = _check_human_text(store, inquiry, text, fact_ids, slot_ids)
    draft = DraftRecord(draft_id=new_id("DRAFT"), org_id=user.org_id, inquiry_id=inquiry_id, created_at=utcnow(),
                        author="operator", status="pending_review", text=text, fact_ids_used=fact_ids,
                        proposed_slot_ids=slot_ids, findings=findings)
    store.save_draft(draft)
    _move(store, inquiry, S.REPLY_HUMAN_REVIEW, _actor(user), "operator")
    audit(store, user.org_id, _actor(user), "draft_created", "inquiry", inquiry_id, draft_id=draft.draft_id,
          draft_status=draft.status, finding_codes=[f.code for f in findings])
    return draft


# ------------------------------------------------------------------ after approval
def mark_sent(store: Store, user: User, inquiry_id: str) -> Inquiry:
    _require_operator(user)
    inquiry = store.get_inquiry(user.org_id, inquiry_id)
    draft = store.latest_draft(user.org_id, inquiry_id)
    if inquiry.state != S.REPLY_APPROVED or draft is None or draft.status != "approved":
        raise Conflict("Only an approved reply can be marked as sent.")
    draft.status = "sent"
    store.save_draft(draft)
    dst = S.VIEWING_PROPOSED if draft.proposed_slot_ids else S.CONVERSATION_ACTIVE
    _move(store, inquiry, dst, _actor(user), "operator")
    audit(store, user.org_id, _actor(user), "reply_marked_sent", "inquiry", inquiry_id, draft_id=draft.draft_id)
    return inquiry


def accept_slot(store: Store, tools: ToolRegistry, user: User, inquiry_id: str, slot_id: str,
                as_applicant: bool = True) -> Inquiry:
    """Record that the applicant accepted a proposed slot (simulated in the demo)."""
    _require_operator(user)
    inquiry = store.get_inquiry(user.org_id, inquiry_id)
    draft = store.latest_draft(user.org_id, inquiry_id)
    if inquiry.state != S.VIEWING_PROPOSED or draft is None or slot_id not in draft.proposed_slot_ids:
        raise Conflict("This slot was not proposed to this applicant.")
    kind: ActorKind = "applicant" if as_applicant else "operator"
    actor = f"applicant:{inquiry.applicant_ref}" if as_applicant else _actor(user)
    new_booking = _tool(store, tools, inquiry, actor, kind, "book_viewing", slot_id=slot_id)
    _move(store, inquiry, S.VIEWING_CONFIRMED, actor, kind)
    audit(store, user.org_id, actor, "viewing_confirmed", "inquiry", inquiry_id, slot_id=slot_id,
          new_booking=bool(new_booking))
    return inquiry


# ------------------------------------------------------------------ stop, deletion, close
def record_stop(store: Store, tools: ToolRegistry, user: User, inquiry_id: str) -> Inquiry:
    _require_operator(user)
    inquiry = store.get_inquiry(user.org_id, inquiry_id)
    _tool(store, tools, inquiry, _actor(user), "operator", "record_opt_out")
    _move(store, inquiry, S.DO_NOT_CONTACT, _actor(user), "operator")
    return inquiry


def request_deletion(store: Store, tools: ToolRegistry, user: User, inquiry_id: str) -> Inquiry:
    _require_operator(user)
    inquiry = store.get_inquiry(user.org_id, inquiry_id)
    _tool(store, tools, inquiry, _actor(user), "operator", "record_deletion_request")
    _move(store, inquiry, S.DATA_DELETION_REQUESTED, _actor(user), "operator")
    return store.get_inquiry(user.org_id, inquiry_id)


def close_inquiry(store: Store, user: User, inquiry_id: str) -> Inquiry:
    _require_operator(user)
    inquiry = store.get_inquiry(user.org_id, inquiry_id)
    _move(store, inquiry, S.CLOSED, _actor(user), "operator")
    return inquiry
