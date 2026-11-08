import pytest

from rental_copilot.state_machine import InquiryState
from rental_copilot.tools import ToolContext, ToolDenied, ToolRegistry

S = InquiryState


def ctx(store, inquiry_id="INQ-001", kind="system"):
    inquiry = store.get_inquiry("ORG-A", inquiry_id)
    return ToolContext(store, "ORG-A", f"{kind}:test", kind, inquiry)


def test_tool_denied_in_wrong_state_is_audited(store, tools):
    c = ctx(store)  # inquiry_received: facts are only readable after classification
    with pytest.raises(ToolDenied):
        tools.call("get_unit_facts", c)
    events = [e.event_type for e in store.list_audit("ORG-A", "INQ-001")]
    assert "tool_denied" in events


def test_booking_is_blocked_after_a_stop(store, tools):
    store.set_inquiry_state("ORG-A", "INQ-001", S.DO_NOT_CONTACT)
    with pytest.raises(ToolDenied):
        tools.call("book_viewing", ctx(store, kind="operator"), slot_id="S-101-1")


def test_agent_cannot_book(store, tools):
    store.set_inquiry_state("ORG-A", "INQ-001", S.VIEWING_PROPOSED)
    with pytest.raises(ToolDenied):
        tools.call("book_viewing", ctx(store, kind="system"), slot_id="S-101-1")


def test_booking_is_idempotent_and_respects_capacity(store, tools):
    store.set_inquiry_state("ORG-A", "INQ-001", S.VIEWING_PROPOSED)
    store.set_inquiry_state("ORG-A", "INQ-002", S.VIEWING_PROPOSED)
    first = tools.call("book_viewing", ctx(store, "INQ-001", "applicant"), slot_id="S-101-1")
    again = tools.call("book_viewing", ctx(store, "INQ-001", "applicant"), slot_id="S-101-1")
    other = tools.call("book_viewing", ctx(store, "INQ-002", "applicant"), slot_id="S-101-1")
    assert first.ok and first.data is True
    assert again.ok and again.data is False          # same booking twice: no duplicate
    assert not other.ok and "full" in other.error    # capacity 1


def test_booking_rejects_slot_of_another_unit(store, tools):
    store.set_inquiry_state("ORG-A", "INQ-001", S.VIEWING_PROPOSED)
    result = tools.call("book_viewing", ctx(store, kind="applicant"), slot_id="S-102-1")
    assert not result.ok and "another unit" in result.error


def test_transient_failure_is_retried_once_then_reported(store):
    registry = ToolRegistry(unavailable={"get_unit_facts"})
    store.set_inquiry_state("ORG-A", "INQ-001", S.INQUIRY_CLASSIFIED)
    result = registry.call("get_unit_facts", ctx(store))
    assert not result.ok
    failures = [e for e in store.list_audit("ORG-A", "INQ-001") if e.event_type == "tool_failed"]
    assert [e.payload["attempt"] for e in failures] == [1, 2]


def test_opt_out_is_idempotent(store, tools):
    assert tools.call("record_opt_out", ctx(store)).data is True
    assert tools.call("record_opt_out", ctx(store)).data is False
    assert store.contact_blocks("ORG-A", "APP-001") == {"opt_out"}


def test_permission_matrix_covers_every_tool(tools):
    names = {row["tool"] for row in tools.permission_matrix()}
    assert {"get_unit_facts", "check_viewing_availability", "book_viewing", "record_opt_out",
            "record_deletion_request", "create_human_review_task"} == names
