# Decision Log

> Entries D-001 onwards were proposed and implemented by Claude (AI assistant) on 2026-11-08; D-000 is the founder's decision. Each entry says when to revisit it.

| ID | Date | Decision | Why | Alternatives rejected | Revisit when |
|---|---|---|---|---|---|
| D-000 | 2026-11-08 | **Founder: build v0.1 now, in parallel with discovery** instead of after 10 interviews | Need a tangible result; the synthetic v1 is required anyway | Discovery first (Milestone 1 exit criteria) | Interview #5: if the wedge is weak, re-scope before building more |
| D-001 | 2026-11-08 | Python 3.11, FastAPI, Pydantic, SQLite with plain SQL, vanilla JS console | Readable, testable, no hidden behaviour; plain SQL shows every query | LangChain/LangGraph (hides the loop), React (build step), SQLAlchemy (more indirection) | Before a real pilot: PostgreSQL, migrations |
| D-002 | 2026-11-08 | Bounded two-call pipeline (classify, draft), not a free tool-using agent loop | The task is narrow; a fixed pipeline is predictable, cheap and evaluable | Model-driven tool loop | When a workflow genuinely needs open-ended steps |
| D-003 | 2026-11-08 | State machine in code with operator-only transitions | The model must not approve, send or close | Prompt-only rules | Never relaxed for approval/sending |
| D-004 | 2026-11-08 | Stop and deletion handled by rules before any model call; the model's `stop_or_deletion_request` intent is a second net | A missed opt-out is the most damaging failure | Model-only detection | When rule misses show up in pilot logs |
| D-005 | 2026-11-08 | Facts carry a status; only `verified` facts with a source are usable; enforced by a DB constraint | "Unknown beats invented" | Free-text property descriptions | — |
| D-006 | 2026-11-08 | Deterministic number check: every number in a draft must come from a cited verified fact, an offered slot or approved text | Cheap, exact, explainable; catches the worst hallucination class | LLM-as-judge for factuality | Add a model-based check only for non-numeric claims |
| D-007 | 2026-11-08 | Before a viewing, ask only for name and one contact channel | DSK guidance v2.0 (Jan 2026) stage model | Collecting full application packs early | Lawyer answer to L1 |
| D-008 | 2026-11-08 | No applicant scoring; six human-only intents (documents, stop, complaint, negotiation, legal/sensitive, spam) | AGG and trust; selection stays human | Ranking or "fit" scores | Never for scoring; list may grow |
| D-009 | 2026-11-08 | The system never sends; the operator sends and clicks "mark as sent" | Removes the biggest blast radius in v1 | Auto-send for low-risk intents | After a pilot shows near-zero edits on a category, test risk-based approval as an experiment |
| D-010 | 2026-11-08 | Mock provider is the default; Claude is optional: `claude-opus-5-5`, effort `medium` set explicitly, structured outputs, `fallbacks: "default"`, outputs re-validated | Runs offline, reproducible, free; real model behind the same interface | Real model only | After a live eval run with cost approval |
| D-011 | 2026-11-08 | Audit payload allow-list; erasure keeps a content-free trail | Deletion must be complete; audit must survive | Logging raw messages | — |
| D-012 | 2026-11-08 | Synthetic-only mode enforced in config and by `CHECK (is_synthetic = 1)` | Synthetic and real data must never mix silently | A flag only in docs | When pilot mode is designed (separate database) |
| D-013 | 2026-11-08 | Demo authentication via `X-User-Id` header | Enough to demonstrate roles and tenant isolation | Real auth now | Before any real data |
| D-014 | 2026-11-08 | Guardrails run again on the operator's final text; a block needs a written override reason | Humans make mistakes too; overrides must be explainable | Trust any human edit | If overrides become routine, the rule or the fact sheet is wrong |
| D-015 | 2026-11-08 | Greeting without name or form of address | Never infer gender from names | "Sehr geehrte Frau …" | If customers insist: use the applicant's own stated form of address only |
