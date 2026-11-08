# Munich Rental Copilot — Product Brief (v0, 2026-11-08)

> **Authorship:** drafted by Claude (AI assistant) at the founder's request. **Not yet reviewed or validated by the founder; zero customer interviews so far.** Every number is tagged `[assumption]`, `[source Sx]` (see `sources.md`) or `[interview]`.
> **Status:** hypothesis document. Not legal advice. Not production-ready.

## 1. Problem statement

Small Munich letting agents receive far more inquiries per rental listing than they can read `[assumption, directional support: S4, S5]`. Today they triage by hand across portal inboxes, email and spreadsheets, answer the same questions repeatedly, and coordinate viewings by phone or email. The result: hours lost per listing, missed or late replies to suitable applicants, inconsistent and hard-to-audit communication, and legal exposure (AGG, DSGVO, GEG ad fields) when staff improvise `[assumption]`.

**One-line version:** *"For a Munich letting agent, getting from 'listing is live' to 'confirmed viewings with complete applicants' costs too many hours and creates avoidable mistakes."*

## 2. Who

| Role | Hypothesis |
|---|---|
| **Primary customer** | Small letting agency / Makler in Munich, 1–10 staff, ≥20 residential rental placements per year `[assumption]` |
| **Economic buyer** | Agency owner / managing partner |
| **Daily user** | Agent or assistant who runs the listing inbox and books viewings |
| **Property type** | Ordinary unfurnished residential flats, long-term lease (Wohnraummiete). **Excluded in v1:** furnished/temporary, WG, commercial, social housing |
| **Secondary (learning only)** | Professional private landlords with 2–50 units — faster to reach, used for concierge tests |

## 3. Exact workflow (the wedge)

**Inquiry-to-viewing for one active listing.**

Start: listing is live on a portal (published manually by the agent).
End: the agent has a list of confirmed viewing slots with applicants who supplied the permitted information.

1. Agent creates the unit record from an exposé and structured details → **verified fact sheet** (each fact has status and source).
2. Inquiries arrive (v1: synthetic; pilot: forwarded portal email notifications or CSV export — **no scraping**).
3. Copilot classifies each inquiry: routine question / viewing request / incomplete / off-topic / stop or deletion request / needs human.
4. Copilot drafts a reply grounded only in the fact sheet and approved templates; unknown facts stay unknown.
5. Before a viewing, Copilot asks only for **name and one contact channel** — stage A of the DSK guidance v2.0 `[source S12]`. Later-stage information is out of v1 scope; lawyer to confirm (L1).
6. Copilot proposes viewing slots from the agent's simulated calendar.
7. **Agent approves every outgoing message** and sends it manually (v1).
8. Everything is logged: inputs, model output, evidence used, approval, final text.

**Not in the wedge:** choosing tenants, ranking applicants, rent legality, lease drafting, move-in, maintenance.

## 4. Pain, workaround, cost

- **Pain:** volume + repetition + coordination + compliance anxiety `[assumption]`.
- **Current workaround:** portal inbox, Outlook/Gmail, copy-paste templates, Excel or broker CRM (onOffice, Propstack, FlowFact `[source S7]`), phone calls, sometimes "first N inquiries only". Some CRMs already send the first reply automatically, e.g. automatic exposé dispatch `[source S14]`, so our value has to sit after that first reply.
- **Cost formula (fill with interview data):**

  `hours_per_listing = inquiries_read × min_per_inquiry/60 + viewing_coordination_hours`
  `annual_cost = hours_per_listing × listings_per_year × loaded_hourly_cost`

  **Illustrative only** `[assumption]`: 150 inquiries × 1.5 min ≈ 3.75 h + 2 h coordination ≈ 5.75 h/listing; × 40 listings × €45/h ≈ **€10k/year** per agency. If interviews show < 2 h/listing, the wedge is weak.

## 5. Why AI assistance fits

- High-volume, short, semi-structured text in German and English → classification and drafting are strengths of LLMs.
- Answers can be **grounded** in a small, verifiable fact sheet → hallucination is checkable.
- Every external action can stay human-approved → low autonomy, low blast radius.
- Rules that must not fail (stop requests, deletion, no sensitive inference, approval gate) live in **code**, not the model.

## 6. Product boundary and non-goals

Is: a human-in-the-loop drafting and triage copilot for one listing workflow.

Is **not** (v1): a marketplace or portal replacement · a scraper · tenant-selection or scoring engine · legal/rent-legality advice · SCHUFA/credit decisions · auto-sender · property-management ERP · maintenance or move-in tool · voice product.

## 7. Feature classification

| Feature | Class |
|---|---|
| Unit fact sheet with fact status + source | must_have |
| Inquiry classification + grounded reply drafts | must_have |
| Request for missing stage-A info (name + one contact channel, S12) | must_have |
| Viewing slot proposal (simulated calendar) | must_have |
| Human approval gate, audit log, stop/deletion handling | must_have |
| Deterministic mock LLM provider (works offline) | must_have |
| Listing draft DE/EN from fact sheet | should_have |
| Missing-information report for the listing | should_have |
| GEG ad-field checklist | later (after L4) |
| Neutral applicant summary for human review | later (after L1) |
| Rent-reference information | later |
| Move-in, maintenance, voice | later |
| Applicant scoring / ranking | **reject** |
| Auto-sending messages | **reject in v1** |

## 8. Success criteria

**Validation (before building beyond the baseline agent):**
- ≥ 10 interviews with ICP; ≥ 6 report ≥ 2 h inquiry/viewing work per listing `[target]`.
- ≥ 3 agencies agree to a concierge pilot on a real listing; ≥ 1 agrees to pay (any amount) `[target]`.

**Synthetic product quality (v1):**
- 0 messages leave without approval; 0 sensitive-attribute inferences; 0 cross-applicant data leaks (hard gates).
- ≥ 95 % of facts in drafts trace to the fact sheet; unsupported-claim rate ≤ 2 % on the eval set `[target]`.
- Inquiry classification ≥ 90 % on the eval set `[target]`.

**Pilot (only with real, consented data):** operator time per listing −50 % vs. measured baseline; no increase in missed suitable inquiries.

## 9. User journey (v1, synthetic)

```
Agent uploads exposé ─► reviews fact sheet (fixes unknowns) ─► listing goes live (manually)
   ─► inquiries arrive in Copilot inbox ─► Copilot classifies + drafts
   ─► agent approves / edits / rejects each draft ─► agent sends manually
   ─► applicant picks a slot ─► agent confirms ─► viewing list ready
   ─► stop/deletion requests handled at any point (code-enforced)
```

## 10. Product principles (short)

1. One workflow before many features.
2. Evidence before generation; unknown beats invented.
3. Human approval before any external action.
4. Code enforces safety; the model drafts.
5. Facts, inferences and unknowns are different data types.
6. No applicant scoring, no sensitive inference.
7. Legal questions are escalated, never guessed.
8. Every AI feature ships with an eval.
9. Operator hours saved beat AI novelty.
10. Works (degraded) without the model.

## 11. What is simulated and what is not claimed

- All properties, owners, applicants and messages in v1 are **synthetic**.
- No customer has used the product. No interviews done yet.
- Market numbers are public/vendor statistics, not validation.
- Any future pilot data will be labelled and stored separately from synthetic data.

## 12. Assumptions and risks

See `assumptions.md` and `risk-register.md`. ICP rationale: `icp-decision.md`. Metrics: `metrics-tree.md`.
