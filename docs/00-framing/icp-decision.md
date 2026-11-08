# ICP Decision Memo (v0, 2026-11-08)

> **Authorship:** drafted by Claude (AI assistant) at the founder's request. Scores are **judgement before any interview**, not data. Revisit after interview #10.

## Decision

- **Primary ICP:** small Munich letting agencies / Makler (Segment B), 1–10 staff, ≥20 residential rental placements per year.
- **Wedge:** inquiry-to-viewing for one active listing, human-approved.
- **Secondary:** professional private landlords (Segment C) — for fast concierge learning, not the business case.
- **Later expansion:** small Hausverwaltung (Segment A).
- **Rejected for now:** furnished/relocation operators (Segment D).

## Scoring (1 = bad, 5 = good)

| Criterion | A: Hausverwaltung | B: Makler/agency | C: Pro landlord | D: Furnished/relocation |
|---|---|---|---|---|
| Pain intensity & frequency | 3 | **5** | 3 | 4 |
| Clear economic buyer | 3 | **5** | 5 | 4 |
| Reachability in Munich | 2 | 4 | 4 | 3 |
| Willingness to pay | 4 | 3 | 2 | 4 |
| Data accessibility | 2 | 4 | 4 | 3 |
| Workflow repeatability | 4 | **5** | 2 | 4 |
| Legal/safety risk (5 = low) | 3 | 3 | 3 | 2 |
| Fit for a two-person team | 2 | 4 | 4 | 2 |
| Time to first paid pilot | 2 | 4 | 4 | 3 |
| **Total** | **25** | **37** | **31** | **29** |

## Why B

- Leasing **is** their job: the inquiry flood repeats on every listing → the workflow is frequent and measurable.
- One person decides and buys; short sales cycle compared with Hausverwaltung.
- They already hold exposés and inquiry emails → data exists without scraping.
- Munich demand statistics (S4, S5) suggest high inquiry volume, which is where AI triage pays off.

## Why not the others (yet)

- **A — Hausverwaltung:** letting is often a side task (many focus on WEG/administration); legacy software and stricter security expectations slow a two-person team. Good expansion target once we have audit logs and a DPA.
- **C — Pro landlords:** easy to reach, but they let units rarely → low frequency, low ARPU, high support load. Use them for concierge tests.
- **D — Furnished/relocation:** temporary-use and Zweckentfremdung questions, plus heavy operations (cleaning, check-in). Too much legal and service scope for v1.

## What would change this decision

- Interviews show < 2 h/listing of inquiry work for B → wedge is weak; test listing-intake instead.
- B agencies already solve this inside onOffice/Propstack (S7) and are satisfied → pivot to integration/plugin or to A.
- Bestellerprinzip (S8) makes B unwilling to pay anything → test C willingness, or per-listing pricing paid by owners.
- A lawyer says permitted-information requests cannot be standardised (L1) → narrow to routine Q&A + scheduling only.

## Biggest threat to this choice

Incumbent broker CRMs already advertise AI features and lead scoring (S7). Our differentiation must be **narrower and safer**: grounded replies, explicit unknowns, approval gate, AGG-safe design, audit trail — or an integration into their tools rather than a replacement.
