"""Inquiry workflow state machine — the single source of truth for what may happen next.

The model never moves an inquiry between states. The agent and the API call
`transition()`, which rejects anything not listed here. Docs and the UI read the
same table (`rental-copilot states` prints it as Mermaid), so they cannot drift.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

ActorKind = Literal["system", "operator", "applicant"]


class InquiryState(StrEnum):
    INQUIRY_RECEIVED = "inquiry_received"
    INQUIRY_CLASSIFIED = "inquiry_classified"
    REPLY_DRAFT_READY = "reply_draft_ready"
    REPLY_HUMAN_REVIEW = "reply_human_review"
    REPLY_APPROVED = "reply_approved"
    CONVERSATION_ACTIVE = "conversation_active"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    VIEWING_PROPOSED = "viewing_proposed"
    VIEWING_CONFIRMED = "viewing_confirmed"
    DO_NOT_CONTACT = "do_not_contact"
    DATA_DELETION_REQUESTED = "data_deletion_requested"
    TOOL_FAILURE = "tool_failure"
    CLOSED = "closed"


S = InquiryState

# Ordinary transitions. A failed tool is never retried by changing state: the tool
# registry retries once, then the inquiry goes to tool_failure → needs_human_review.
TRANSITIONS: dict[InquiryState, frozenset[InquiryState]] = {
    S.INQUIRY_RECEIVED: frozenset({S.INQUIRY_CLASSIFIED, S.NEEDS_HUMAN_REVIEW, S.TOOL_FAILURE}),
    S.INQUIRY_CLASSIFIED: frozenset({S.REPLY_DRAFT_READY, S.NEEDS_HUMAN_REVIEW, S.TOOL_FAILURE}),
    S.REPLY_DRAFT_READY: frozenset({S.REPLY_HUMAN_REVIEW, S.NEEDS_HUMAN_REVIEW}),
    S.REPLY_HUMAN_REVIEW: frozenset({S.REPLY_APPROVED, S.NEEDS_HUMAN_REVIEW}),
    S.NEEDS_HUMAN_REVIEW: frozenset({S.REPLY_HUMAN_REVIEW, S.CLOSED}),
    S.REPLY_APPROVED: frozenset({S.CONVERSATION_ACTIVE, S.VIEWING_PROPOSED}),
    S.CONVERSATION_ACTIVE: frozenset({S.NEEDS_HUMAN_REVIEW, S.CLOSED}),
    S.VIEWING_PROPOSED: frozenset({S.VIEWING_CONFIRMED, S.CONVERSATION_ACTIVE, S.NEEDS_HUMAN_REVIEW}),
    S.VIEWING_CONFIRMED: frozenset({S.CLOSED}),
    S.TOOL_FAILURE: frozenset({S.NEEDS_HUMAN_REVIEW}),
    S.DO_NOT_CONTACT: frozenset({S.CLOSED}),
    S.DATA_DELETION_REQUESTED: frozenset({S.CLOSED}),
    S.CLOSED: frozenset(),
}

# A valid stop request is accepted wherever contact is still possible.
STOP_ALLOWED_FROM = frozenset(set(S) - {S.DO_NOT_CONTACT, S.DATA_DELETION_REQUESTED, S.CLOSED})
# A deletion request is honoured from every state, including closed ones.
DELETION_ALLOWED_FROM = frozenset(set(S) - {S.DATA_DELETION_REQUESTED})

# Transitions only a human operator may trigger. The agent ("system") cannot approve,
# send, close or take over a human-review case on its own.
HUMAN_ONLY = frozenset({
    (S.REPLY_HUMAN_REVIEW, S.REPLY_APPROVED),
    (S.NEEDS_HUMAN_REVIEW, S.REPLY_HUMAN_REVIEW),
    (S.NEEDS_HUMAN_REVIEW, S.CLOSED),
    (S.REPLY_APPROVED, S.CONVERSATION_ACTIVE),
    (S.REPLY_APPROVED, S.VIEWING_PROPOSED),
    (S.CONVERSATION_ACTIVE, S.CLOSED),
    (S.VIEWING_CONFIRMED, S.CLOSED),
    (S.DO_NOT_CONTACT, S.CLOSED),
    (S.DATA_DELETION_REQUESTED, S.CLOSED),
})
# Accepting a proposed slot comes from the (simulated) applicant or an operator recording it.
APPLICANT_OR_OPERATOR = frozenset({(S.VIEWING_PROPOSED, S.VIEWING_CONFIRMED)})


class InvalidTransition(Exception):
    def __init__(self, src: InquiryState, dst: InquiryState, reason: str):
        super().__init__(f"{src.value} → {dst.value} not allowed: {reason}")
        self.src, self.dst, self.reason = src, dst, reason


def allowed_targets(src: InquiryState) -> frozenset[InquiryState]:
    targets = set(TRANSITIONS[src])
    if src in STOP_ALLOWED_FROM:
        targets.add(S.DO_NOT_CONTACT)
    if src in DELETION_ALLOWED_FROM:
        targets.add(S.DATA_DELETION_REQUESTED)
    return frozenset(targets)


def check_transition(src: InquiryState, dst: InquiryState, actor: ActorKind) -> None:
    """Raise InvalidTransition unless `actor` may move an inquiry from `src` to `dst`."""
    if dst not in allowed_targets(src):
        raise InvalidTransition(src, dst, "not in the transition table")
    pair = (src, dst)
    if pair in HUMAN_ONLY and actor != "operator":
        raise InvalidTransition(src, dst, f"only an operator may do this (actor: {actor})")
    if pair in APPLICANT_OR_OPERATOR and actor not in ("applicant", "operator"):
        raise InvalidTransition(src, dst, "needs the applicant's acceptance or an operator")
    if actor == "applicant" and pair not in APPLICANT_OR_OPERATOR and dst not in (
        S.DO_NOT_CONTACT, S.DATA_DELETION_REQUESTED
    ):
        raise InvalidTransition(src, dst, "applicants can only accept a slot, stop contact or request deletion")


def to_mermaid() -> str:
    lines = ["stateDiagram-v2", f"    [*] --> {S.INQUIRY_RECEIVED.value}"]
    for src, targets in TRANSITIONS.items():
        for dst in sorted(targets, key=lambda s: s.value):
            label = " : operator" if (src, dst) in HUMAN_ONLY else ""
            lines.append(f"    {src.value} --> {dst.value}{label}")
    lines.append(f"    {S.CLOSED.value} --> [*]")
    notes = {
        S.DO_NOT_CONTACT: "reachable from every state where contact is still possible",
        S.DATA_DELETION_REQUESTED: "reachable from every state, including closed",
    }
    for state, text in notes.items():
        lines.append(f"    note right of {state.value}\n        {text}\n    end note")
    return "\n".join(lines)


def to_markdown_table() -> str:
    rows = ["| From | Allowed next states | Operator-only |", "|---|---|---|"]
    for src in S:
        targets = sorted(allowed_targets(src), key=lambda s: s.value)
        human = sorted(dst.value for dst in targets if (src, dst) in HUMAN_ONLY)
        rows.append(f"| `{src.value}` | {', '.join(f'`{t.value}`' for t in targets) or '— (terminal)'} | "
                    f"{', '.join(f'`{h}`' for h in human) or '—'} |")
    return "\n".join(rows)
