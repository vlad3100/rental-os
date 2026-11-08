# Signal-Strength Rubric — v0, 2026-11-08

> **Authorship:** drafted by Claude (AI assistant). Purpose: score **one interview** consistently so we do not fall in love with polite people. Scores feed `interview-tracker.csv` and `scripts/score_discovery.py`.

## Principle

Compliments and future promises are cheap. Past behaviour, numbers, money already spent and commitments of **time, data or reputation** are expensive and therefore credible.

## Dimensions

| Code | Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| **P** | Pain intensity | No pain mentioned | General complaint ("it's a lot") | Specific recent pain with a consequence (late replies, lost good inquiry, overtime) | Specific pain **plus** quantified cost or lost business, and they already tried to fix it |
| **F** | Frequency *(derived, do not enter)* | < 3 lettings / year | 3–9 | 10–29 | ≥ 30 |
| **Q** | Evidence quality | Only opinions or hypotheticals | Rough estimates, not tied to a real listing | Numbers from the **last** listing | Numbers from the last listing **and** shown in records (inbox count, CRM report) or observed by us |
| **W** | Workaround spend | Nothing | Free tools, templates | Pays for a tool module or staff time explicitly for this | Pays significantly (assistant, working student, premium CRM module) specifically for inquiries/viewings |
| **B** | Buyer authority | No influence | Influencer | Co-decides | Decides alone and owns budget |
| **D** | Data access (legitimate) | No legitimate way to get inquiries | Portal web UI only | Email notifications or CRM export | CRM with export/API already in use |
| **R** | Complexity risk (3 = low) | Out of scope (commercial, social housing only) | Mostly furnished / temporary / WG | Mixed portfolio | Standard unfurnished long-term flats, standard tools |

### Commitment ladder (C, 0–4)

| C | Meaning | Example |
|---|---|---|
| 0 | Nothing or compliments | "Great idea, good luck!" |
| 1 | Passive interest | "Keep me posted." |
| 2 | Spends time or reputation | Books a follow-up, gives a referral, shares an anonymised inquiry sample |
| 3 | Gives access to a real workflow | Agrees to observation or concierge on a dated listing |
| 4 | Gives money or a written commitment | Paid pilot, signed letter of intent |

## Signal class (computed)

| Class | Rule |
|---|---|
| **Strong** | P ≥ 2 **and** Q ≥ 2 **and** C ≥ 3 |
| **Medium** | P ≥ 2 **and** Q ≥ 1 **and** C ≥ 1 (and not Strong) |
| **Negative** | P = 0, **or** they state the problem is solved well enough today |
| **Weak** | everything else |

Record negatives explicitly. Disconfirming evidence is as valuable as confirming evidence.

## False-positive patterns (score them down)

- "I would definitely use that" → future tense, C = 0.
- "Everybody in the industry has this problem" → not their own pain, P ≤ 1.
- Pain that belongs to someone else ("my assistant hates it") → note who owns the pain; B may be low.
- Enthusiasm about AI in general, not about this workflow.
- Numbers that change during the interview → Q ≤ 1.
- Agreeing to a pilot "sometime" without a listing or date → C = 1, not 3.

## Calibration

- Score right after the interview, before talking to anyone else.
- After interviews #3 and #8, both founders score two interviews independently and compare. Any dimension that differs by ≥ 2 points needs a clearer anchor here.
