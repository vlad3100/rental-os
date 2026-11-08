# Domain Model — v0.1 (2026-11-08)

> Written by Claude (AI assistant). Source of truth: `src/rental_copilot/schema.sql` and `domain.py`.

## Entities implemented

| Entity | Key fields | Lifecycle / notes |
|---|---|---|
| Organization | org_id, name, is_synthetic (= 1) | Tenant boundary |
| User | user_id, org_id, role (operator, viewer) | Demo users only |
| Unit | unit_id, org_id, title, district | No street address stored |
| Fact | field, kind, value, value_en, **status**, source_ref, note, recorded_at | See statuses below; one row per field and unit |
| Knowledge snippet | knowledge_id, language, text | Operator-approved wording |
| Inquiry | inquiry_id, unit_id, received_at, applicant_ref (pseudonymous), display name, contact channel type, message, **state**, tool_failures, erased_at | State machine in `state_machine.py` |
| Slot / Booking | slot_id, starts_at, capacity · (slot_id, inquiry_id) | Booking is idempotent by primary key |
| Draft | author (agent, operator), status (pending_review, blocked, approved, rejected, sent), text, final_text, fact_ids_used, proposed_slot_ids, findings, reviewer, override_reason | — |
| Agent run | output_json (`agent_output.v1`) | One per agent pass |
| Task | kind, reason, status | Human work items |
| Contact block | applicant_ref, kind (opt_out, deletion) | Suppression list |
| Audit event | actor, event_type, entity, allow-listed payload | Append-only by convention |

Not yet implemented from the Milestone 3 list: Listing and ListingVersion, Document and DocumentFact (extraction), Application, multi-message Conversation, ComplianceCheck, MoveInChecklist, MaintenanceRequest, Vendor, ConsentRecord, RetentionPolicy. Evaluation cases live in `evals/cases_v1.json`.

## Fact statuses

| Status | Meaning | Usable in a reply? |
|---|---|---|
| `verified` | Confirmed by the operator, has a source (DB constraint) | Yes |
| `extracted` | Read from a document, not confirmed | No — treated as unknown |
| `user_entered` | Typed in, no document | No |
| `inferred` | Produced by a model; must carry a note and a source (DB constraint) | Never |
| `unknown` | Missing or conflicting; value must be empty (DB constraint) | No — the reply says it is not confirmed |

## Data classification

| Data | Class | Stored | Retention assumption (to confirm, L2) |
|---|---|---|---|
| Unit facts, slots, approved wording | Business data, public once listed | Yes | Life of the listing |
| Applicant display name, message | Personal data | Yes, erasable | Until letting is closed + policy period |
| Contact channel | Only the type (email, phone, address) | Yes | As above |
| Applicant reference | Pseudonymous id | Yes, also in the suppression list | Suppression entries kept to honour stops |
| Sensitive characteristics mentioned by applicants | Special-category or AGG-relevant | Only inside the message text; flagged, never extracted into fields | Erased with the message |
| Audit events | Operational, no content | Yes | Longer than personal data (content-free) |

## Permissions by role

| Action | Operator | Viewer | Copilot (system) | Applicant (simulated) |
|---|---|---|---|---|
| Read inbox, drafts, history | Yes | Yes | No | No |
| Run the copilot | Yes | No | No | No |
| Approve, reject, write reply, mark sent, close | Yes | No | No | No |
| Book a proposed slot | Yes (recording it) | No | No | Yes (accepting) |
| Stop contact, request deletion | Yes | No | Yes (from detected requests) | Yes |
| Read fact sheet via tools | Yes | No | Yes (after classification) | No |
