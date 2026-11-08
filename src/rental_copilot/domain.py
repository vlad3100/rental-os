"""Domain model and the agent output contract.

Design rules encoded here (not only in the prompt):
- A fact has an explicit status. Only `verified` facts with a value may appear in a reply.
- The agent output contract fixes `human_approval_required=True` and
  `external_send_allowed=False` as literal types: no code path can construct an
  output that claims it may send on its own.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .state_machine import InquiryState

Language = Literal["de", "en", "other"]


class FactStatus(StrEnum):
    VERIFIED = "verified"          # confirmed by the operator, has a source
    EXTRACTED = "extracted"        # read from a document, not yet confirmed
    USER_ENTERED = "user_entered"  # typed in by a user, no document
    INFERRED = "inferred"          # produced by a model; never usable as a fact
    UNKNOWN = "unknown"            # missing or conflicting


class FactKind(StrEnum):
    MONEY = "money"
    AREA = "area"
    COUNT = "count"
    BOOL = "bool"
    DATE = "date"
    TEXT = "text"


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True)

    fact_id: str
    unit_id: str
    field: str
    label_de: str
    label_en: str
    kind: FactKind
    value: str | None = None       # canonical value; German wording for text facts
    value_en: str | None = None    # English wording for text facts
    status: FactStatus
    source_ref: str | None = None  # e.g. "Exposé S. 1"
    note: str | None = None        # e.g. why a value is unknown

    @property
    def usable(self) -> bool:
        return self.status == FactStatus.VERIFIED and self.value is not None


class Unit(BaseModel):
    org_id: str
    unit_id: str
    title: str
    district: str
    facts: list[Fact] = Field(default_factory=list)
    is_synthetic: Literal[True] = True

    def fact(self, field: str) -> Fact | None:
        return next((f for f in self.facts if f.field == field), None)


class Intent(StrEnum):
    VIEWING_REQUEST = "viewing_request"
    AVAILABILITY_QUESTION = "availability_question"
    COST_QUESTION = "cost_question"
    PROPERTY_DETAIL_QUESTION = "property_detail_question"
    PROCESS_QUESTION = "process_question"
    INFO_SUBMISSION = "info_submission"
    GENERIC_OR_INCOMPLETE = "generic_or_incomplete"
    STOP_OR_DELETION_REQUEST = "stop_or_deletion_request"
    COMPLAINT_OR_HOSTILE = "complaint_or_hostile"
    NEGOTIATION_OR_SPECIAL_REQUEST = "negotiation_or_special_request"
    LEGAL_OR_SENSITIVE = "legal_or_sensitive"
    SPAM_OR_SCAM = "spam_or_scam"


# Intents the copilot never drafts a substantive answer for (concierge taxonomy v0).
HUMAN_ONLY_INTENTS = frozenset({
    Intent.INFO_SUBMISSION,
    Intent.STOP_OR_DELETION_REQUEST,
    Intent.COMPLAINT_OR_HOSTILE,
    Intent.NEGOTIATION_OR_SPECIAL_REQUEST,
    Intent.LEGAL_OR_SENSITIVE,
    Intent.SPAM_OR_SCAM,
})


class Inquiry(BaseModel):
    org_id: str
    inquiry_id: str
    unit_id: str
    received_at: datetime
    channel: str = "portal_email"
    applicant_ref: str                      # pseudonymous reference, never an email address
    applicant_display_name: str | None = None
    contact_channel: Literal["email", "phone", "address"] | None = None
    message: str
    state: InquiryState = InquiryState.INQUIRY_RECEIVED
    tool_failures: int = 0
    erased_at: datetime | None = None
    is_synthetic: Literal[True] = True


class Slot(BaseModel):
    org_id: str
    slot_id: str
    unit_id: str
    starts_at: datetime
    capacity: int = Field(gt=0)
    booked: int = 0

    @property
    def free(self) -> bool:
        return self.booked < self.capacity


class KnowledgeSnippet(BaseModel):
    """Approved, operator-owned wording (process rules, standard sentences)."""
    knowledge_id: str
    language: Literal["de", "en"]
    text: str


class User(BaseModel):
    user_id: str
    org_id: str
    display_name: str
    role: Literal["operator", "viewer"]


# ---------------------------------------------------------------- model I/O

class Classification(BaseModel):
    """What a provider must return for step 1 (classification). Validated, never trusted."""
    intent: Intent
    secondary_intents: list[Intent] = Field(default_factory=list, max_length=4)
    language: Language
    asked_fields: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=400)


class DraftProposal(BaseModel):
    """What a provider must return for step 2 (drafting). Validated and checked by guardrails."""
    response_text: str = Field(min_length=1, max_length=2500)
    fact_ids_used: list[str] = Field(default_factory=list, max_length=30)
    unknown_fields: list[str] = Field(default_factory=list, max_length=12)
    proposed_slot_ids: list[str] = Field(default_factory=list, max_length=5)
    knowledge_ids_used: list[str] = Field(default_factory=list, max_length=10)
    rationale: str = Field(max_length=400)


class DraftFact(BaseModel):
    fact_id: str
    field: str
    label: str
    value: str     # display value in the inquiry language, e.g. "1.450 €"
    sentence: str  # approved sentence rendered by code, e.g. "Die Kaltmiete beträgt 1.450 € im Monat."


class DraftSlot(BaseModel):
    slot_id: str
    starts_at: datetime
    display: str  # pre-formatted in the inquiry language; the model must copy it verbatim


class DraftRequest(BaseModel):
    """Everything the drafting step may use. Nothing else is in scope for the model."""
    message: str
    language: Language
    intent: Intent
    secondary_intents: list[Intent]
    asked_fields: list[str]
    usable_facts: list[DraftFact]
    unknown_fields: list[str]
    slots: list[DraftSlot]
    knowledge: list[KnowledgeSnippet]
    contact_channel_present: bool


# ---------------------------------------------------------------- guardrails

class Finding(BaseModel):
    code: str
    severity: Literal["block", "warn"]
    message: str


# ---------------------------------------------------------------- agent output contract

class FactUse(BaseModel):
    field: str
    value: str
    source_reference: str
    status: FactStatus
    confidence: float = Field(ge=0.0, le=1.0)


class ToolCallRecord(BaseModel):
    tool: str
    ok: bool
    error: str | None = None


NextAction = Literal[
    "review_and_approve_draft",
    "review_blocked_draft",
    "handle_manually",
    "stop_all_contact",
    "confirm_deletion_manually",
    "confirm_spam_and_close",
]


class AgentOutput(BaseModel):
    """Contract `agent_output.v1`. Changing it requires a new version and an eval run."""
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["agent_output.v1"] = "agent_output.v1"
    inquiry_id: str
    draft_id: str | None = None
    response_text: str | None = None
    language: Language = "other"
    workflow_state: InquiryState
    intent: Intent | None = None
    secondary_intents: list[Intent] = Field(default_factory=list)
    property_facts_used: list[FactUse] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    approved_knowledge_used: list[str] = Field(default_factory=list)
    proposed_slot_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    next_best_action: NextAction
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    guardrail_findings: list[Finding] = Field(default_factory=list)
    escalation_required: bool = False
    human_approval_required: Literal[True] = True
    external_send_allowed: Literal[False] = False
    decision_rationale: str = Field(max_length=600)
    prompt_version: str
    provider: str


DraftStatus = Literal["pending_review", "blocked", "approved", "rejected", "sent"]


class DraftRecord(BaseModel):
    draft_id: str
    org_id: str
    inquiry_id: str
    created_at: datetime
    author: Literal["agent", "operator"]
    status: DraftStatus
    text: str | None
    final_text: str | None = None
    fact_ids_used: list[str] = Field(default_factory=list)
    proposed_slot_ids: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    override_reason: str | None = None


class Task(BaseModel):
    task_id: str
    org_id: str
    inquiry_id: str | None
    kind: str
    reason: str
    created_at: datetime
    status: Literal["open", "done"] = "open"


class AuditEvent(BaseModel):
    event_id: int
    org_id: str
    at: datetime
    actor: str
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict
