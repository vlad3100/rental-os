"""Tool registry: every action with a side effect or data access goes through here.

For each call the registry checks, in code:
1. the tool exists;
2. the inquiry is in a state where the tool is allowed;
3. the actor kind (system / operator / applicant) may use it;
then executes it, retries a *transient* failure exactly once, and writes an audit event.
A denied call raises ToolDenied: in this design a denial is a bug or an attack, not a
normal outcome, so it must surface loudly.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .audit import audit
from .domain import Inquiry, Slot, Task, ToolCallRecord, Unit
from .state_machine import DELETION_ALLOWED_FROM, STOP_ALLOWED_FROM, ActorKind, InquiryState
from .store import NotFound, Store

S = InquiryState


class ToolDenied(PermissionError):
    pass


class ToolUnavailable(RuntimeError):
    """Transient failure (timeout, outage). Retried once, then escalated."""


@dataclass
class ToolContext:
    store: Store
    org_id: str
    actor: str             # e.g. "system:agent", "operator:anna"
    actor_kind: ActorKind
    inquiry: Inquiry


@dataclass(frozen=True)
class ToolSpec:
    name: str
    purpose: str
    allowed_states: frozenset[InquiryState]
    allowed_actors: frozenset[str]
    side_effect: bool
    retryable: bool
    fn: Callable[..., Any]


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None
    record: ToolCallRecord | None = None


# ------------------------------------------------------------------ tool implementations
def _get_unit_facts(ctx: ToolContext) -> Unit:
    return ctx.store.get_unit(ctx.org_id, ctx.inquiry.unit_id)


def _check_viewing_availability(ctx: ToolContext, limit: int = 3) -> list[Slot]:
    if not 1 <= limit <= 5:
        raise ValueError("limit must be between 1 and 5")
    free = [s for s in ctx.store.list_slots(ctx.org_id, ctx.inquiry.unit_id) if s.free]
    return free[:limit]


def _book_viewing(ctx: ToolContext, slot_id: str) -> bool:
    slot = ctx.store.get_slot(ctx.org_id, slot_id)
    if slot.unit_id != ctx.inquiry.unit_id:
        raise ValueError("slot belongs to another unit")
    if ctx.store.contact_blocks(ctx.org_id, ctx.inquiry.applicant_ref):
        raise ValueError("applicant has a stop or deletion record")
    return ctx.store.book_slot(ctx.org_id, slot_id, ctx.inquiry.inquiry_id)


def _record_opt_out(ctx: ToolContext) -> bool:
    return ctx.store.add_contact_block(ctx.org_id, ctx.inquiry.applicant_ref, "opt_out")


def _record_deletion_request(ctx: ToolContext) -> bool:
    ctx.store.add_contact_block(ctx.org_id, ctx.inquiry.applicant_ref, "deletion")
    ctx.store.erase_inquiry(ctx.org_id, ctx.inquiry.inquiry_id)
    return True


def _create_human_review_task(ctx: ToolContext, kind: str, reason: str) -> Task:
    if len(reason) > 300:
        raise ValueError("reason too long")
    return ctx.store.add_task(ctx.org_id, ctx.inquiry.inquiry_id, kind, reason)


_ALL_ACTIVE = frozenset(set(S) - {S.CLOSED})
_SYSTEM_OPERATOR = frozenset({"system", "operator"})

DEFAULT_TOOLS: list[ToolSpec] = [
    ToolSpec("get_unit_facts", "Read the unit's fact sheet with fact statuses and sources.",
             frozenset({S.INQUIRY_CLASSIFIED, S.NEEDS_HUMAN_REVIEW, S.REPLY_HUMAN_REVIEW}),
             _SYSTEM_OPERATOR, side_effect=False, retryable=True, fn=_get_unit_facts),
    ToolSpec("check_viewing_availability", "List free viewing slots for the unit (max 5).",
             frozenset({S.INQUIRY_CLASSIFIED, S.NEEDS_HUMAN_REVIEW, S.CONVERSATION_ACTIVE}),
             _SYSTEM_OPERATOR, side_effect=False, retryable=True, fn=_check_viewing_availability),
    ToolSpec("book_viewing", "Book a proposed slot after the applicant accepted it. Idempotent.",
             frozenset({S.VIEWING_PROPOSED}),
             frozenset({"applicant", "operator"}), side_effect=True, retryable=False, fn=_book_viewing),
    ToolSpec("record_opt_out", "Record a stop request; blocks further contact. Idempotent.",
             STOP_ALLOWED_FROM, frozenset({"system", "operator", "applicant"}),
             side_effect=True, retryable=True, fn=_record_opt_out),
    ToolSpec("record_deletion_request", "Erase the inquiry's personal content and block contact.",
             DELETION_ALLOWED_FROM, frozenset({"system", "operator", "applicant"}),
             side_effect=True, retryable=True, fn=_record_deletion_request),
    ToolSpec("create_human_review_task", "Open a task for a human operator.",
             _ALL_ACTIVE, _SYSTEM_OPERATOR, side_effect=True, retryable=True, fn=_create_human_review_task),
]


@dataclass
class ToolRegistry:
    specs: dict[str, ToolSpec] = field(default_factory=lambda: {s.name: s for s in DEFAULT_TOOLS})
    unavailable: set[str] = field(default_factory=set)  # fault injection for tests and evals

    def call(self, name: str, ctx: ToolContext, **args: Any) -> ToolResult:
        spec = self.specs.get(name)
        if spec is None:
            raise ToolDenied(f"unknown tool {name!r}")
        reason = None
        if ctx.inquiry.state not in spec.allowed_states:
            reason = f"state {ctx.inquiry.state.value}"
        elif ctx.actor_kind not in spec.allowed_actors:
            reason = f"actor {ctx.actor_kind}"
        if reason:
            audit(ctx.store, ctx.org_id, ctx.actor, "tool_denied", "inquiry", ctx.inquiry.inquiry_id,
                  tool=name, error=reason)
            raise ToolDenied(f"{name} not allowed ({reason})")

        attempts = 2 if spec.retryable else 1
        last_error = "unknown error"
        for attempt in range(1, attempts + 1):
            try:
                if name in self.unavailable:
                    raise ToolUnavailable(f"{name} is unavailable")
                data = spec.fn(ctx, **args)
            except ToolUnavailable as exc:
                last_error = str(exc)
                audit(ctx.store, ctx.org_id, ctx.actor, "tool_failed", "inquiry", ctx.inquiry.inquiry_id,
                      tool=name, attempt=attempt, error=last_error)
                continue
            except (ValueError, NotFound) as exc:  # invalid input: retrying cannot help
                audit(ctx.store, ctx.org_id, ctx.actor, "tool_rejected", "inquiry", ctx.inquiry.inquiry_id,
                      tool=name, attempt=attempt, error=str(exc))
                return ToolResult(ok=False, error=str(exc), record=ToolCallRecord(tool=name, ok=False, error=str(exc)))
            audit(ctx.store, ctx.org_id, ctx.actor, "tool_called", "inquiry", ctx.inquiry.inquiry_id,
                  tool=name, attempt=attempt, ok=True)
            return ToolResult(ok=True, data=data, record=ToolCallRecord(tool=name, ok=True))
        return ToolResult(ok=False, error=last_error, record=ToolCallRecord(tool=name, ok=False, error=last_error))

    def permission_matrix(self) -> list[dict[str, Any]]:
        return [{"tool": s.name, "purpose": s.purpose, "side_effect": s.side_effect, "retryable": s.retryable,
                 "actors": sorted(s.allowed_actors), "states": sorted(st.value for st in s.allowed_states)}
                for s in self.specs.values()]
