# Risk Register (v0, 2026-11-08)

> **Authorship:** drafted by Claude (AI assistant). Likelihood (L) and impact (I): 1–5, judgement only.

| ID | Risk | Type | L | I | Mitigation | Owner | Trigger to revisit |
|---|---|---|---|---|---|---|---|
| R1 | Inquiry work is not painful enough (< 2 h/listing) | Product | 3 | 5 | Measure in first 5 interviews; pivot wedge if weak | Founder | Interview #5 |
| R2 | Incumbent CRMs (onOffice, Propstack) already cover it well enough | Market | 4 | 4 | Competitor check; position as narrow/safe add-on or integration | Founder | Competitor review |
| R3 | No legitimate way to ingest portal inquiries (no API, no scraping) | Technical/legal | 3 | 5 | Start with forwarded emails/CSV; verify portal APIs (S11) | Tech partner | Before pilot |
| R4 | AGG discrimination exposure via replies, info requests or summaries | Legal/ethical | 2 | 5 | No scoring; stage-based info requests per DSK guidance v2.0 (S12); anti-discrimination evals; lawyer L1 | Founder | Before any applicant feature |
| R5 | DSGVO: processing applicant data with an LLM provider | Legal/privacy | 3 | 5 | Synthetic only in v1; EU provider + DPA; minimisation; retention policy; L2 | Founder | Before real data |
| R6 | Fabricated property facts in replies (rent, size, availability) | Quality | 3 | 4 | Grounding in fact sheet; deterministic fact checker; unknowns explicit | Tech partner | Eval run |
| R7 | Prompt injection via inquiries or uploaded exposés | Security | 3 | 4 | Treat all inputs as data; tool permissions in code; red-team set | Tech partner | Eval run |
| R8 | Low willingness to pay (Bestellerprinzip squeezes broker margins) | Business | 3 | 4 | Ask about current spend; test per-listing price | Founder | Interview #10 |
| R9 | Message sent externally without approval | Safety | 1 | 5 | No send tool in v1; approval gate in state machine | Tech partner | Any architecture change |
| R10 | Founder time split (discovery vs. building) delays both | Execution | 4 | 3 | Weekly time budget; discovery has priority until wedge is validated | Founder | Weekly review |
| R11 | Overclaiming in portfolio (synthetic presented as real) | Reputation | 2 | 4 | Authorship labels; contribution matrix; synthetic tag on every metric | Founder | Every artifact |
| R12 | Rent-brake / GEG rules change or misinterpreted (S1, S6) | Legal | 3 | 3 | No rent-legality feature in v1; checklist only after L4 | Founder | Before listing checklist |
| R13 | Compliance by design (stage-A data only before viewings, S12) clashes with agencies' habit of collecting full application packs early | Product/sales | 3 | 3 | Ask Q11 in interviews; position as risk reduction; never weaken the rule to win a deal | Founder | Interview #5 |
