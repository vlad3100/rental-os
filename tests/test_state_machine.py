import pytest

from rental_copilot.state_machine import (
    TRANSITIONS,
    InquiryState,
    InvalidTransition,
    allowed_targets,
    check_transition,
    to_mermaid,
)

S = InquiryState


def test_every_state_has_a_row():
    assert set(TRANSITIONS) == set(S)


def test_happy_path_is_allowed_for_the_right_actors():
    check_transition(S.INQUIRY_RECEIVED, S.INQUIRY_CLASSIFIED, "system")
    check_transition(S.INQUIRY_CLASSIFIED, S.REPLY_DRAFT_READY, "system")
    check_transition(S.REPLY_DRAFT_READY, S.REPLY_HUMAN_REVIEW, "system")
    check_transition(S.REPLY_HUMAN_REVIEW, S.REPLY_APPROVED, "operator")
    check_transition(S.REPLY_APPROVED, S.VIEWING_PROPOSED, "operator")
    check_transition(S.VIEWING_PROPOSED, S.VIEWING_CONFIRMED, "applicant")


@pytest.mark.parametrize("src,dst", [
    (S.INQUIRY_RECEIVED, S.VIEWING_CONFIRMED),       # cannot book from a fresh inquiry
    (S.INQUIRY_RECEIVED, S.REPLY_APPROVED),          # cannot skip review
    (S.DO_NOT_CONTACT, S.REPLY_DRAFT_READY),         # no outreach after a stop
    (S.DO_NOT_CONTACT, S.INQUIRY_RECEIVED),
    (S.DATA_DELETION_REQUESTED, S.REPLY_HUMAN_REVIEW),
    (S.CLOSED, S.REPLY_DRAFT_READY),
    (S.TOOL_FAILURE, S.INQUIRY_CLASSIFIED),          # no silent retry loop through states
])
def test_invalid_transitions_raise(src, dst):
    with pytest.raises(InvalidTransition):
        check_transition(src, dst, "operator")


def test_the_agent_cannot_approve_or_send():
    with pytest.raises(InvalidTransition, match="only an operator"):
        check_transition(S.REPLY_HUMAN_REVIEW, S.REPLY_APPROVED, "system")
    with pytest.raises(InvalidTransition):
        check_transition(S.REPLY_APPROVED, S.CONVERSATION_ACTIVE, "system")


def test_applicant_can_only_accept_stop_or_delete():
    with pytest.raises(InvalidTransition):
        check_transition(S.REPLY_HUMAN_REVIEW, S.REPLY_APPROVED, "applicant")
    check_transition(S.CONVERSATION_ACTIVE, S.DO_NOT_CONTACT, "applicant")


def test_stop_is_reachable_while_contact_is_possible_and_deletion_always():
    for state in S:
        assert (S.DATA_DELETION_REQUESTED in allowed_targets(state)) == (state != S.DATA_DELETION_REQUESTED)
    assert S.DO_NOT_CONTACT in allowed_targets(S.VIEWING_CONFIRMED)
    assert S.DO_NOT_CONTACT not in allowed_targets(S.CLOSED)
    assert allowed_targets(S.DO_NOT_CONTACT) == {S.CLOSED, S.DATA_DELETION_REQUESTED}


def test_mermaid_lists_every_state():
    diagram = to_mermaid()
    for state in S:
        assert state.value in diagram
