"""Inquiry agent: one bounded pass from `inquiry_received` to a reviewable draft or a human task.

The control flow is code, not a free-running model loop. The model is called at most twice
(classify, then draft) and only proposes. Order of authority:

    deterministic rules  →  state machine  →  permissioned tools  →  model proposal  →  guardrails  →  human

Stop and deletion requests are handled before any model call. Human-only intents, low
confidence, tool failures, invalid model output and blocked drafts all end in
`needs_human_review` with a task. Nothing is ever sent by the system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .audit import audit
from .catalog import FIELDS, label
from .config import Settings
from .domain import (
    HUMAN_ONLY_INTENTS,
    AgentOutput,
    Classification,
    DraftFact,
    DraftRecord,
    DraftRequest,
    DraftSlot,
    FactUse,
    Finding,
    Inquiry,
    Intent,
    NextAction,
    ToolCallRecord,
    Unit,
)
from .guardrails import (
    check_draft,
    detect_language,
    detect_prompt_injection,
    detect_sensitive,
    detect_stop_or_deletion,
    has_block,
)
from .providers.base import LLMProvider, ProviderError
from .render import display_value, fact_sentence, slot_display
from .state_machine import InquiryState, InvalidTransition, check_transition
from .store import Store, new_id, utcnow
from .tools import ToolContext, ToolRegistry, ToolResult

S = InquiryState
ACTOR = "system:agent"

HUMAN_REASONS: dict[Intent, str] = {
    Intent.INFO_SUBMISSION: "Applicant sent documents or personal details that are not needed at this stage "
                            "(DSK stage model). Do not file them; decide on deletion under the retention policy.",
    Intent.STOP_OR_DELETION_REQUEST: "The model sees a possible stop or deletion request that the rules did not "
                                     "catch. Check and act.",
    Intent.COMPLAINT_OR_HOSTILE: "Complaint or hostile message. Reply personally.",
    Intent.NEGOTIATION_OR_SPECIAL_REQUEST: "Negotiation or special request. Needs the agent's or owner's decision.",
    Intent.LEGAL_OR_SENSITIVE: "Legal question or sensitive personal topic. Reply personally; no legal advice; "
                               "equal treatment applies (AGG).",
    Intent.SPAM_OR_SCAM: "Looks like spam or a scam. Confirm and close without replying.",
}


@dataclass
class _Run:
    inquiry: Inquiry
    language: str = "other"
    classification: Classification | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def flag(self, *names: str) -> None:
        for name in names:
            if name not in self.flags:
                self.flags.append(name)


class InquiryAgent:
    def __init__(self, store: Store, provider: LLMProvider, settings: Settings, tools: ToolRegistry | None = None):
        self.store = store
        self.provider = provider
        self.settings = settings
        self.tools = tools or ToolRegistry()

    # ------------------------------------------------------------------ helpers
    def _audit(self, run: _Run, event_type: str, **payload: Any) -> None:
        audit(self.store, run.inquiry.org_id, ACTOR, event_type, "inquiry", run.inquiry.inquiry_id, **payload)

    def _move(self, run: _Run, dst: InquiryState) -> None:
        src = run.inquiry.state
        check_transition(src, dst, "system")
        self.store.set_inquiry_state(run.inquiry.org_id, run.inquiry.inquiry_id, dst)
        run.inquiry.state = dst
        self._audit(run, "state_changed", from_state=src.value, to_state=dst.value)

    def _tool(self, run: _Run, name: str, **args: Any) -> ToolResult:
        ctx = ToolContext(self.store, run.inquiry.org_id, ACTOR, "system", run.inquiry)
        result = self.tools.call(name, ctx, **args)
        if result.record:
            run.tool_calls.append(result.record)
        if not result.ok:
            self.store.add_tool_failure(run.inquiry.org_id, run.inquiry.inquiry_id)
        return result

    def _task(self, run: _Run, kind: str, reason: str) -> None:
        self._tool(run, "create_human_review_task", kind=kind, reason=reason)

    def _finish(self, run: _Run, next_action: NextAction, rationale: str, escalate: bool,
                **extra: Any) -> AgentOutput:
        cls = run.classification
        output = AgentOutput(
            inquiry_id=run.inquiry.inquiry_id,
            workflow_state=run.inquiry.state,
            language=run.language,  # type: ignore[arg-type]
            intent=cls.intent if cls else None,
            secondary_intents=cls.secondary_intents if cls else [],
            confidence=cls.confidence if cls else 0.0,
            next_best_action=next_action,
            tool_calls=run.tool_calls,
            risk_flags=run.flags,
            escalation_required=escalate,
            decision_rationale=rationale[:600],
            prompt_version=self.provider.prompt_version,
            provider=self.provider.name,
            **extra,
        )
        self.store.save_run(run.inquiry.org_id, run.inquiry.inquiry_id, output.model_dump(mode="json"))
        self._audit(run, "agent_output", intent=output.intent.value if output.intent else None,
                    next_best_action=next_action, risk_flags=run.flags, escalation_required=escalate,
                    to_state=run.inquiry.state.value, contract_version=output.contract_version)
        return output

    def _to_human(self, run: _Run, kind: str, reason: str, rationale: str,
                  next_action: NextAction = "handle_manually") -> AgentOutput:
        self._move(run, S.NEEDS_HUMAN_REVIEW)
        self._task(run, kind, reason)
        return self._finish(run, next_action, rationale, escalate=True)

    def _tool_failure(self, run: _Run, tool: str) -> AgentOutput:
        run.flag(f"tool_failure:{tool}")
        self._move(run, S.TOOL_FAILURE)
        self._move(run, S.NEEDS_HUMAN_REVIEW)
        self._task(run, "tool_failure", f"Tool {tool} failed after one retry. Handle manually or retry later.")
        return self._finish(run, "handle_manually", f"Required tool {tool} failed after one retry; no draft.",
                            escalate=True)

    def _model_error(self, run: _Run, step: str, exc: Exception) -> AgentOutput:
        code = getattr(exc, "code", "invalid_output")
        run.flag(f"model_error:{code}")
        self._audit(run, "model_call", tool=step, ok=False, error=code, provider=self.provider.name)
        return self._to_human(run, "model_error", f"The model step '{step}' failed ({code}). Handle manually.",
                              f"Model step {step} failed ({code}); routed to a human.")

    # ------------------------------------------------------------------ main entry point
    def process(self, org_id: str, inquiry_id: str) -> AgentOutput:
        inquiry = self.store.get_inquiry(org_id, inquiry_id)
        if inquiry.state != S.INQUIRY_RECEIVED:
            raise InvalidTransition(inquiry.state, S.INQUIRY_CLASSIFIED, "inquiry was already processed")
        run = _Run(inquiry=inquiry, language=detect_language(inquiry.message))
        text = inquiry.message
        self._audit(run, "agent_started", provider=self.provider.name, prompt_version=self.provider.prompt_version)

        # 1. Stop and deletion requests: decided by code, before any model sees the text.
        signal = detect_stop_or_deletion(text)
        if signal and signal.kind == "deletion":
            run.flag("deletion_request")
            self._tool(run, "record_deletion_request")
            self._move(run, S.DATA_DELETION_REQUESTED)
            self._task(run, "confirm_deletion", "Applicant asked for data deletion. Content erased here; confirm to "
                                                "the applicant and delete other copies (e.g. portal inbox).")
            return self._finish(run, "confirm_deletion_manually",
                                "Deletion request detected by rule; personal content erased before any model call.",
                                escalate=True)
        if signal and signal.kind == "opt_out":
            run.flag("opt_out")
            self._tool(run, "record_opt_out")
            self._move(run, S.DO_NOT_CONTACT)
            return self._finish(run, "stop_all_contact",
                                "Stop request detected by rule; contact blocked, no draft, no model call.",
                                escalate=False)
        if signal and signal.kind == "ambiguous_opt_out":
            run.flag("ambiguous_opt_out")
            return self._to_human(run, "ambiguous_stop_request",
                                  "Message contains a conditional stop request. Decide whether to reply or stop.",
                                  "Conditional stop request detected by rule; a human decides. No draft.")

        # 2. An earlier stop or deletion for this applicant blocks automatic drafting.
        if self.store.contact_blocks(org_id, inquiry.applicant_ref):
            run.flag("contact_blocked")
            return self._to_human(run, "contact_blocked",
                                  "This applicant has an earlier stop or deletion record. Check before any reply.",
                                  "Applicant has a suppression record; no draft.")

        # 3. Inbound risk signals become flags; they never stop code-enforced checks later.
        if detect_prompt_injection(text):
            run.flag("prompt_injection_suspected")
        for kind in detect_sensitive(text):
            run.flag(f"sensitive_data_in_message:{kind}")
        if run.language == "other":
            run.flag("unsupported_language")
            return self._to_human(run, "unsupported_language", "Message is not in German or English.",
                                  "Language outside the v1 scope (German, English).")

        # 4. Classification (model proposal, validated).
        try:
            classification, stats = self.provider.classify(text, list(FIELDS))
        except (ProviderError, ValueError) as exc:
            return self._model_error(run, "classify", exc)
        self._audit(run, "model_call", tool="classify", ok=True, latency_ms=stats.latency_ms,
                    input_tokens=stats.input_tokens, output_tokens=stats.output_tokens, provider=self.provider.name,
                    prompt_version=self.provider.prompt_version)
        run.classification = classification
        if classification.language in ("de", "en"):
            run.language = classification.language
        self._move(run, S.INQUIRY_CLASSIFIED)
        self._audit(run, "classified", intent=classification.intent.value, confidence=classification.confidence,
                    secondary_intents=[i.value for i in classification.secondary_intents], language=run.language)

        # 5. Routing rules in code.
        intent = classification.intent
        if intent in HUMAN_ONLY_INTENTS:
            run.flag(f"human_only_intent:{intent.value}")
            if intent == Intent.INFO_SUBMISSION:
                run.flag("unsolicited_documents")
            next_action: NextAction = "confirm_spam_and_close" if intent == Intent.SPAM_OR_SCAM else "handle_manually"
            return self._to_human(run, intent.value, HUMAN_REASONS[intent],
                                  f"Intent {intent.value} is human-only by policy; no draft.", next_action)
        if classification.confidence < self.settings.confidence_threshold:
            run.flag("low_confidence")
            return self._to_human(run, "low_confidence", "The copilot is unsure what the applicant wants.",
                                  f"Confidence {classification.confidence:.2f} is below the threshold "
                                  f"{self.settings.confidence_threshold:.2f}; no draft.")

        # 6. Evidence through permissioned tools.
        facts_result = self._tool(run, "get_unit_facts")
        if not facts_result.ok:
            return self._tool_failure(run, "get_unit_facts")
        unit: Unit = facts_result.data
        wants_viewing = Intent.VIEWING_REQUEST in (intent, *classification.secondary_intents)
        free_slots: list[Any] = []
        if wants_viewing:
            slots_result = self._tool(run, "check_viewing_availability", limit=3)
            if not slots_result.ok:
                return self._tool_failure(run, "check_viewing_availability")
            free_slots = slots_result.data
            if not free_slots:
                run.flag("no_viewing_slots")
                self._task(run, "add_viewing_slots", "Viewing requested but no free slots. Add slots in the calendar.")

        # 7. Drafting (model proposal) from verified evidence only.
        language = run.language
        asked = [f for f in classification.asked_fields if unit.fact(f) is not None]
        unknown = [f for f in asked if not unit.fact(f).usable]  # type: ignore[union-attr]
        usable = [f for f in unit.facts if f.usable]
        knowledge = self.store.list_knowledge(inquiry.org_id, language)
        slots = [DraftSlot(slot_id=s.slot_id, starts_at=s.starts_at, display=slot_display(s.starts_at, language))
                 for s in free_slots]
        request = DraftRequest(
            message=text, language=language, intent=intent,  # type: ignore[arg-type]
            secondary_intents=classification.secondary_intents, asked_fields=asked,
            usable_facts=[DraftFact(fact_id=f.fact_id, field=f.field, label=label(f.field, language),
                                    value=display_value(f, language), sentence=fact_sentence(f, language))
                          for f in usable],
            unknown_fields=unknown, slots=slots, knowledge=knowledge,
            contact_channel_present=inquiry.contact_channel is not None,
        )
        try:
            proposal, stats = self.provider.draft(request)
        except (ProviderError, ValueError) as exc:
            return self._model_error(run, "draft", exc)
        self._audit(run, "model_call", tool="draft", ok=True, latency_ms=stats.latency_ms,
                    input_tokens=stats.input_tokens, output_tokens=stats.output_tokens, provider=self.provider.name,
                    prompt_version=self.provider.prompt_version)

        # 8. Guardrails on the proposal (code).
        used_knowledge = [k for k in knowledge if k.knowledge_id in proposal.knowledge_ids_used]
        findings = check_draft(proposal.response_text, unit=unit, fact_ids_used=proposal.fact_ids_used,
                               slots=slots, knowledge=used_knowledge, expected_language=language)  # type: ignore[arg-type]
        offered = {s.slot_id for s in slots}
        invented_slots = [s for s in proposal.proposed_slot_ids if s not in offered]
        if invented_slots:
            findings.append(Finding(
                code="unknown_slot", severity="block",
                message=f"Draft proposes slots that were not offered: {', '.join(invented_slots)}."))
        unacknowledged = [f for f in unknown if f not in proposal.unknown_fields]
        if unacknowledged:
            findings.append(Finding(code="unknown_not_acknowledged", severity="warn",
                                    message=f"Unknown fields not acknowledged: {', '.join(unacknowledged)}."))
        if wants_viewing and slots and not proposal.proposed_slot_ids:
            findings.append(Finding(code="viewing_without_slots", severity="warn",
                                    message="Viewing requested but the draft proposes no slot."))

        blocked = has_block(findings)
        draft = DraftRecord(
            draft_id=new_id("DRAFT"), org_id=inquiry.org_id, inquiry_id=inquiry.inquiry_id, created_at=utcnow(),
            author="agent", status="blocked" if blocked else "pending_review", text=proposal.response_text,
            fact_ids_used=proposal.fact_ids_used,
            proposed_slot_ids=[s for s in proposal.proposed_slot_ids if s in offered], findings=findings,
        )
        self._move(run, S.REPLY_DRAFT_READY)
        self.store.save_draft(draft)
        self._audit(run, "draft_created", draft_id=draft.draft_id, draft_status=draft.status,
                    finding_codes=[f.code for f in findings], fact_ids=proposal.fact_ids_used, unknown_fields=unknown)

        if blocked:
            run.flag("draft_blocked")
            self._move(run, S.NEEDS_HUMAN_REVIEW)
            self._task(run, "review_blocked_draft", "Guardrails blocked the draft. Rewrite it or reply manually.")
            next_best: NextAction = "review_blocked_draft"
        else:
            self._move(run, S.REPLY_HUMAN_REVIEW)
            next_best = "review_and_approve_draft"

        by_id = {f.fact_id: f for f in unit.facts}
        used = [by_id[i] for i in dict.fromkeys(proposal.fact_ids_used) if i in by_id and by_id[i].usable]
        fact_uses = [FactUse(field=f.field, value=display_value(f, language), source_reference=f.source_ref or "",
                             status=f.status, confidence=1.0) for f in used]
        evidence = [f"{f.fact_id} ({f.source_ref})" for f in used] + [f"slot:{s}" for s in draft.proposed_slot_ids]
        unknowns = sorted(set(unknown) | {f for f in proposal.unknown_fields if f in FIELDS})
        escalate = blocked or any(f.startswith(("prompt_injection", "sensitive_data")) for f in run.flags)
        rationale = (f"Intent {intent.value} ({classification.confidence:.2f}). Draft uses {len(used)} verified "
                     f"facts; {len(unknowns)} unknown field(s) left open; {len(draft.proposed_slot_ids)} slot(s) "
                     f"proposed; {sum(f.severity == 'block' for f in findings)} blocking finding(s). "
                     "Human approval required before sending.")
        return self._finish(run, next_best, rationale, escalate, draft_id=draft.draft_id,
                            response_text=proposal.response_text, property_facts_used=fact_uses, unknowns=unknowns,
                            evidence_references=evidence,
                            approved_knowledge_used=[k.knowledge_id for k in used_knowledge],
                            proposed_slot_ids=draft.proposed_slot_ids, guardrail_findings=findings)
