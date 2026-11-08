import json

import pytest
from pydantic import ValidationError

from rental_copilot.agent import InquiryAgent
from rental_copilot.domain import AgentOutput
from rental_copilot.evals import FaultyProvider
from rental_copilot.providers import MockProvider
from rental_copilot.state_machine import InquiryState, InvalidTransition
from rental_copilot.tools import ToolRegistry

S = InquiryState


def test_cost_question_gets_grounded_draft(agent, store):
    out = agent.process("ORG-A", "INQ-002")
    assert out.workflow_state == S.REPLY_HUMAN_REVIEW
    assert {f.field for f in out.property_facts_used} >= {"deposit_eur", "heating_included"}
    assert all(f.status == "verified" for f in out.property_facts_used)
    assert out.human_approval_required is True and out.external_send_allowed is False
    assert "4.350 €" in out.response_text
    assert store.latest_draft("ORG-A", "INQ-002").status == "pending_review"


def test_contract_cannot_claim_it_may_send():
    with pytest.raises(ValidationError):
        AgentOutput(inquiry_id="x", workflow_state=S.CLOSED, next_best_action="handle_manually",
                    decision_rationale="x", prompt_version="v", provider="p", external_send_allowed=True)


def test_stop_request_never_reaches_the_model(store, settings):
    class ExplodingProvider(MockProvider):
        def classify(self, *a, **k):
            raise AssertionError("model must not be called for a stop request")

    out = InquiryAgent(store, ExplodingProvider(), settings).process("ORG-A", "INQ-004")
    assert out.workflow_state == S.DO_NOT_CONTACT
    assert out.response_text is None and store.latest_draft("ORG-A", "INQ-004") is None
    assert store.contact_blocks("ORG-A", "APP-004") == {"opt_out"}


def test_later_inquiry_from_stopped_applicant_goes_to_human(agent):
    agent.process("ORG-A", "INQ-004")
    out = agent.process("ORG-A", "INQ-017")
    assert out.workflow_state == S.NEEDS_HUMAN_REVIEW and "contact_blocked" in out.risk_flags


def test_deletion_erases_content_and_keeps_audit_content_free(agent, store):
    original = store.get_inquiry("ORG-A", "INQ-005").message
    out = agent.process("ORG-A", "INQ-005")
    inquiry = store.get_inquiry("ORG-A", "INQ-005")
    assert out.workflow_state == S.DATA_DELETION_REQUESTED
    assert inquiry.message == "[erased]" and inquiry.applicant_display_name is None
    audit_dump = json.dumps([e.payload for e in store.list_audit("ORG-A")], ensure_ascii=False)
    assert original[:20] not in audit_dump


def test_prompt_injection_cannot_change_facts(agent):
    out = agent.process("ORG-A", "INQ-006")
    assert "prompt_injection_suspected" in out.risk_flags and out.escalation_required
    assert "900" not in out.response_text and "1.450 €" in out.response_text


def test_unknown_facts_stay_unknown(agent):
    out = agent.process("ORG-A", "INQ-009")  # area is conflicting on U-102
    assert "living_area_m2" in out.unknowns
    assert "78" not in out.response_text and "74" not in out.response_text


@pytest.mark.parametrize("inquiry_id,flag", [
    ("INQ-007", "unsolicited_documents"),
    ("INQ-008", "human_only_intent:negotiation_or_special_request"),
    ("INQ-010", "human_only_intent:legal_or_sensitive"),
    ("INQ-013", "sensitive_data_in_message:origin_or_nationality"),
    ("INQ-016", "ambiguous_opt_out"),
])
def test_human_only_cases_get_no_draft(agent, store, inquiry_id, flag):
    out = agent.process("ORG-A", inquiry_id)
    assert out.workflow_state == S.NEEDS_HUMAN_REVIEW
    assert flag in out.risk_flags
    assert store.latest_draft("ORG-A", inquiry_id) is None
    assert store.list_tasks("ORG-A", inquiry_id)


def test_tool_failure_escalates_without_endless_retry(store, settings):
    tools = ToolRegistry(unavailable={"check_viewing_availability"})
    out = InquiryAgent(store, MockProvider(), settings, tools).process("ORG-A", "INQ-001")
    assert out.workflow_state == S.NEEDS_HUMAN_REVIEW
    assert "tool_failure:check_viewing_availability" in out.risk_flags
    attempts = [e for e in store.list_audit("ORG-A", "INQ-001") if e.event_type == "tool_failed"]
    assert len(attempts) == 2


def test_hallucinated_draft_is_blocked(store, settings):
    provider = FaultyProvider(MockProvider(), "draft_hallucinate")
    out = InquiryAgent(store, provider, settings).process("ORG-A", "INQ-002")
    assert out.workflow_state == S.NEEDS_HUMAN_REVIEW and "draft_blocked" in out.risk_flags
    assert store.latest_draft("ORG-A", "INQ-002").status == "blocked"


def test_model_error_routes_to_human(store, settings):
    out = InquiryAgent(store, FaultyProvider(MockProvider(), "classify_error"), settings).process("ORG-A", "INQ-002")
    assert out.workflow_state == S.NEEDS_HUMAN_REVIEW and "model_error:injected_failure" in out.risk_flags


def test_inquiry_is_processed_only_once(agent):
    agent.process("ORG-A", "INQ-002")
    with pytest.raises(InvalidTransition):
        agent.process("ORG-A", "INQ-002")


def test_every_run_is_stored_and_matches_the_contract(agent, store):
    for inquiry in store.list_inquiries("ORG-A"):
        agent.process("ORG-A", inquiry.inquiry_id)
        stored = store.latest_run("ORG-A", inquiry.inquiry_id)
        assert stored is not None
        assert AgentOutput.model_validate(stored).contract_version == "agent_output.v1"
