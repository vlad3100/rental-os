# Concierge Playbook — Inquiry-to-Viewing, done by hand (v0, 2026-11-08)

> **Authorship:** drafted by Claude (AI assistant). **Not legal advice.** Items marked L1, L2, L6 need a German data-protection / Mietrecht lawyer before the first concierge with real data.

## Purpose

Do the wedge manually for one real listing **before writing product code**, in order to:

1. learn the real workflow (correct `workflow-map.md`);
2. measure a baseline and an assisted run (`baseline-metrics.md`);
3. produce the first product artefacts by hand: **fact sheet, inquiry taxonomy, reply templates, edit log** — these become the v1 data model, prompts and evaluation cases;
4. test willingness to pay with a real service, not a slide.

## Concierge levels

| Level | What happens | Data handling | Allowed in M1? |
|---|---|---|---|
| **L0 — Observation** | Sit with the agent for 2–3 hours during an inquiry peak; keep a time log | Founder sees data but records only counts, categories, durations | **Yes** — with a signed confidentiality undertaking |
| **L1 — Assisted drafting** | Founder works in the agency's own inbox/CRM, under the agency's instruction; drafts replies from the fact sheet and templates; the agent approves and sends | Data never leaves agency systems; **no LLM on real data** | **Yes**, after the legal role is clarified (L6) |
| **L2 — Copilot with real data** | Our software processes real inquiries | Requires EU LLM provider with DPA, AVV with the agency, security review | **No** — earliest after Milestone 15 |

## Hard rules (all levels)

1. **No real applicant or owner data in ChatGPT, Claude or any other LLM.** Synthetic data only for AI work.
2. **Nothing leaves agency systems:** no screenshots, exports, forwarding to private email, photos of screens.
3. **No fake inquiries** to real listings ("mystery shopping"). It is deceptive and adds load to the very inbox we want to relieve.
4. The founder **never conducts viewings, never selects or rejects applicants, never communicates decisions.**
5. Before a viewing, ask applicants only for **name and one contact channel** (DSK stage A, `workflow-map.md` §2). Never request stage-B or stage-C information early.
6. **Unsolicited documents** (salary slips, SCHUFA, ID copies): do not open further, do not file them; flag to the agent, who decides under the agency's retention policy (L2).
7. Stop or deletion requests go to the agent **immediately** and are logged (time, category, action taken — no content).
8. Notes contain counts, categories, durations and anonymised paraphrases only.
9. Any data incident (wrong recipient, data copied by mistake): stop, tell the agent the same day, write it down. The agency decides on notification duties.

## Legal prerequisites (before L1)

- Signed confidentiality undertaking (Verschwiegenheitserklärung).
- Clarify the founder's role: acting under the agency's authority like a temporary helper (Art. 29 DSGVO) or as a processor (Art. 28 DSGVO, needs an AVV)? → **L6**.
- Confirm that drafting replies under the agency's instruction does not require a § 34c GewO licence for us (expectation: no, the agency remains the broker) → **L3**.
- Agency confirms that its own privacy notice for applicants covers the workflow.

## Procedure (one listing, 2–3 weeks)

### Before go-live
1. **Kickoff (30 min):** scope, rules above, the agency's target reply time, who approves, how stop/deletion requests are handled.
2. **Baseline:** collect B1, B4, B8 (and B2/B7 if logged) from the agency's **previous** comparable listing — counts and timestamps only.
3. **Fact sheet:** build it from the exposé with the template below. Every field gets a status and a source. The agent confirms → `verified`. Only verified facts may be used in replies.
4. **Reply templates:** write DE/EN templates for the top categories (start with 1–5 of the taxonomy). The agent approves them once.

### During the inquiry peak (2 sessions per day)
5. Categorise each inquiry with the taxonomy (primary intent, optional secondary, language).
6. Draft a reply from template + fact sheet. If a needed fact is `unknown`, use the "we will clarify" variant — **never guess**.
7. Route human-only categories (9–11) to the agent without drafting a substantive answer.
8. Agent approves, edits or rejects; the agent sends. Log every edit in the **edit log**.
9. Propose viewing slots from the agent's calendar; confirm; send reminders the agent approves.
10. Keep the time log (`baseline-metrics.md`) for every session.
11. Collect **unanswerable questions** → after the agent answers them, add the fact to the fact sheet as `verified`.

### After the listing
12. **Debrief (30 min):** compare against baseline; ask Q24 (value) again with real numbers; ask for referral and permission to quote anonymised numbers.
13. Write the concierge report (outline below).

## Inquiry taxonomy v0

Language (de / en / other) is recorded separately. One primary intent per inquiry, optional secondary.

| # | Category | Definition | Synthetic example | Default handling | Human only? |
|---|---|---|---|---|---|
| 1 | viewing_request | Asks for a viewing | „Ich würde die Wohnung gern besichtigen. Wann wäre ein Termin möglich?“ | Offer slots; ask name + one contact channel if missing | no |
| 2 | availability_question | Move-in date, still available | "From when is the flat available?" | Answer from fact sheet | no |
| 3 | cost_question | Rent, service charges, heating, deposit | „Sind die Heizkosten in den Nebenkosten enthalten?“ | Answer from fact sheet; unknown → clarify | no |
| 4 | property_detail_question | Size, floor, lift, balcony, kitchen, parking, pets policy | „Gibt es einen Aufzug und ein Kellerabteil?“ | Answer from fact sheet; unknown → clarify | no |
| 5 | process_question | How viewings and applications work | "How does the application process work?" | Answer from approved process text | no |
| 6 | info_submission | Applicant sends personal information or documents | „Anbei meine Gehaltsnachweise und die SCHUFA-Auskunft.“ | Flag; do not process documents not yet required (rule 6) | agent decides |
| 7 | generic_or_incomplete | No clear question ("Interested!") | „Hallo, Interesse!“ | Short reply with key facts + viewing process | no |
| 8 | stop_or_deletion_request | Asks to stop contact or delete data | „Bitte löschen Sie meine Daten.“ | Stop all drafts; hand to agent immediately; log | **yes** |
| 9 | complaint_or_hostile | Complaint, frustration, insults | „Warum antwortet hier niemand?“ | Hand to agent; no defensive auto-text | **yes** |
| 10 | negotiation_or_special_request | Rent negotiation, subletting, early move-in, exceptions | "Could the rent be 100 euros lower?" | Hand to agent | **yes** |
| 11 | legal_or_sensitive | Legal questions (e.g. rent brake), discrimination, health, family or other sensitive topics | „Ist die Miete nach der Mietpreisbremse zulässig?“ | Hand to agent; never answer legal questions | **yes** |
| 12 | spam_or_scam | Ads, phishing, obviously automated messages | — | Flag; no reply | agent confirms |

Edge case to watch: messages that mix a routine question with a stop request (e.g. "Answer this, then delete my data") → category 8 wins.

## Fact sheet template (one per unit)

Status values: `verified` (agent confirmed) · `extracted` (from a document, not yet confirmed) · `user_entered` (typed in, no document) · `unknown`.

| Field | Value | Status | Source (document, page) | Confirmed by / date |
|---|---|---|---|---|
| Unit ID (internal) | | | | |
| District (Stadtbezirk) | | | | |
| Cold rent (Kaltmiete), EUR | | | | |
| Service charge prepayment, EUR | | | | |
| Heating costs included? | | | | |
| Deposit (Kaution), EUR | | | | |
| Living area, m² | | | | |
| Rooms | | | | |
| Floor / lift | | | | |
| Balcony / terrace | | | | |
| Fitted kitchen | | | | |
| Bathroom (bath / shower / window) | | | | |
| Cellar / storage | | | | |
| Parking (and price) | | | | |
| Heating type | | | | |
| Energy certificate: type (demand / consumption) | | | | |
| Energy certificate: final energy, kWh/(m²·a) | | | | |
| Energy certificate: main energy carrier | | | | |
| Energy certificate: year of construction | | | | |
| Energy certificate: efficiency class | | | | |
| Available from | | | | |
| Lease type (open-ended, graduated rent, index rent, minimum term) | | | | |
| Pets policy | | | | |
| Viewing format and rules | | | | |

Conflicting values (e.g. 62 m² in the exposé, 58 m² in the floor plan) stay `unknown` with both sources noted until the agent decides.

## Reply-template rules

- Placeholders may only be filled from `verified` fact-sheet fields.
- Every template has an "unknown" variant: „Das kläre ich und melde mich.“ / "I'll check and get back to you."
- No promises about selection chances, no urgency ("many people interested — decide now"), no statements about other applicants.
- Ask only for name and one contact channel before a viewing.
- Same facts in DE and EN; translation must not add or drop facts.

## Edit log (one row per agent edit)

| Inquiry # | Category | Edit type (fact fix / tone / length / added info / removed claim / language / rejected) | Why (agent's words, no personal data) |
|---|---|---|---|
| | | | |

The edit log is the most valuable output: every row is a future evaluation case or guardrail.

## Stop conditions

Stop the concierge immediately if: the agent asks; a data incident happens; a lawyer flags a problem; the work drifts into selection or decisions.

## Concierge report outline

1. Listing context (no address) and dates · 2. Baseline vs. assisted numbers with evidence levels · 3. Category distribution · 4. Unanswerable questions and fact-sheet gaps · 5. Edit-log patterns · 6. Incidents and near misses · 7. Agent's value statement and price reaction · 8. What we would automate first, and what never.
