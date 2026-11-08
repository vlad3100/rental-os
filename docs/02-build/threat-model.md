# Threat Model and Known Limitations — v0.1 (2026-11-08)

> Written by Claude (AI assistant). Not a security review. Not legal advice. v0.1 must not process real personal data.

## Assets

Applicant personal data (names, contact channel, message content) · integrity of the fact sheet · the operator's decisions · the audit trail · the organisation boundary between customers.

## Trust boundaries

| Source | Trust |
|---|---|
| Applicant message | **Untrusted.** Data only, delimited for the model, never instructions |
| Model output | **Untrusted.** Validated against schemas, then checked by guardrails |
| Operator | Trusted for decisions, but their final text is checked again; overrides are audited |
| Viewer | Read-only |
| Another organisation | No access; every query filters by `org_id` |
| Model provider | Third party (processor); not used with real data in v0.1 |

## Threats, mitigations, gaps

| Threat | Mitigation in v0.1 | Gap / next step |
|---|---|---|
| Prompt injection in an inquiry | Delimiters; instruction hierarchy in the prompt; injection flag; code-enforced facts and numbers; model cannot change state or call tools | Pattern list is small; add red-team cases per release |
| Injection via uploaded documents | No document upload in v0.1 | Needed before document extraction (Milestone 5+) |
| Hallucinated property facts | Verified-facts-only context; number guardrail; unverified-fact guardrail; unknowns stay unknown | Non-numeric claims ("quiet street") rely on prompt + review; add claim checks |
| Missed stop request | Rule detection before the model; model intent as backup; suppression list | Regex coverage is German/English only and incomplete; log misses in pilot |
| Incomplete deletion | Erases message, name, drafts, run outputs, bookings; audit has no content | Copies outside the system (portal inbox, mailbox, backups, provider logs) are a manual task |
| Cross-tenant data leak | `org_id` filter on every query; tests | No row-level security; add when moving to PostgreSQL |
| Discriminatory output | No scoring; sensitive topics human-only; protected-trait check on drafts; neutral greeting | Pattern list is heuristic; needs anti-discrimination eval set and legal review (L1) |
| Early collection of application data | Draft check for document requests before viewing (DSK stage model) | Wording-based; lawyer to confirm the stage model applies to agents (L1) |
| Unauthorised action | Role check (operator vs viewer); tool permissions by state and actor; operator-only transitions | Demo header auth: anyone who can reach the server can claim a user |
| Sending without approval | No send capability exists; contract fixes `external_send_allowed = false` | — |
| XSS in the console | Every dynamic string escaped in `app.js` | No Content-Security-Policy header yet |
| SQL injection | Parameterised queries only | — |
| Data at rest | Synthetic only | No encryption at rest; SQLite file on disk |
| Model provider data handling | Not used with real data | Before pilot: DPA, retention terms, EU processing options, subprocessor list (L2) |
| Cost or availability attack | Two model calls per inquiry maximum; mock default | No rate limiting |
| Fonts from Google Fonts | Cosmetic; falls back to system fonts | Self-host fonts before a pilot (IP addresses go to Google) |

## Readiness checklist before any real data

- [ ] Lawyer answers L1–L6 (`docs/00-framing/sources.md`), incl. AGG, DSGVO roles, UWG outreach, § 34c GewO
- [ ] Data-processing agreement with each pilot customer; provider DPA and retention terms
- [ ] Real authentication and per-user accounts; remove the demo header
- [ ] PostgreSQL with encryption at rest, backups, migrations; separate pilot database
- [ ] Retention job (delete applicant data after the policy period)
- [ ] Content-Security-Policy, rate limiting, self-hosted fonts
- [ ] Live model eval run reviewed; red-team set extended; anti-discrimination cases added
- [ ] Incident procedure (who is told, how fast, what is logged)
