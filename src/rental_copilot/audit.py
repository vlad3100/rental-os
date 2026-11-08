"""Audit trail with an allow-list.

Only the keys below can reach the audit log. Message text, draft text, names and
contact data are dropped by construction, so an inquiry can be erased later without
the audit trail still holding its content.
"""
from __future__ import annotations

from typing import Any

from .store import Store

ALLOWED_KEYS = frozenset({
    "tool", "attempt", "ok", "error", "from_state", "to_state", "intent", "secondary_intents", "confidence",
    "language", "risk_flags", "finding_codes", "draft_id", "draft_status", "provider", "prompt_version",
    "contract_version", "slot_id", "reason_code", "edited", "override", "task_kind", "fact_ids",
    "unknown_fields", "latency_ms", "input_tokens", "output_tokens", "next_best_action", "escalation_required",
    "actor_role", "new_booking",
})


def audit(store: Store, org_id: str, actor: str, event_type: str, entity_type: str, entity_id: str,
          **payload: Any) -> None:
    safe = {k: v for k, v in payload.items() if k in ALLOWED_KEYS}
    dropped = sorted(set(payload) - ALLOWED_KEYS)
    if dropped:
        safe["dropped_keys"] = dropped  # key names only, never values
    store.add_audit(org_id, actor, event_type, entity_type, entity_id, safe)
