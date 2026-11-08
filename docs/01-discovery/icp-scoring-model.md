# ICP Scoring Model — v0, 2026-11-08

> **Authorship:** drafted by Claude (AI assistant). Turns interview scores into a segment decision. Implemented in `scripts/score_discovery.py` so the calculation is reproducible and not re-done by hand. Weights and thresholds are **judgement** — change them only with a note in the change log below, and never after looking at results to make a favourite segment win.

## 1. Interview fit score (0–100)

`fit = 100 × Σ weight_i × (score_i / max_i)`

| Dimension | Weight | Max | Why this weight |
|---|---|---|---|
| P pain | 0.25 | 3 | Without pain nothing else matters |
| C commitment | 0.20 | 4 | Behaviour beats opinion |
| F frequency | 0.15 | 3 | Recurring revenue and learning need repetition |
| W workaround spend | 0.15 | 3 | Proxy for willingness to pay |
| B buyer authority | 0.10 | 3 | Sales speed |
| D data access | 0.10 | 3 | No data, no product (and no scraping) |
| R complexity (3 = low) | 0.05 | 3 | Legal/ops load for a two-person team |

**Evidence factor:** if Q ≤ 1, the fit score counts at **50 %** (`evidence_weighted_fit = fit × 0.5`). Opinions are not discarded, but they cannot carry a decision.

## 2. Segment metrics (from all interviews in a segment)

| Metric | Source column |
|---|---|
| n interviews | count |
| mean evidence-weighted fit | computed |
| median inquiries on last listing | `inquiries_last_listing` |
| median hours on last listing (inquiries + viewing coordination) | `hours_last_listing` |
| share of Strong signals | computed class |
| commitments ≥ 3 (observation/concierge/paid) | `C` |
| median monthly tool spend (EUR) | `monthly_tool_spend_eur` |

## 3. Link to the M0 ICP criteria

| M0 criterion (`../00-framing/icp-decision.md`) | Updated by |
|---|---|
| Pain intensity & frequency | P, F, median hours, median inquiries |
| Clear economic buyer | B |
| Reachability | outreach conversion (tracked in the private contact list) |
| Willingness to pay | W, Q24 answers, C = 4 |
| Data accessibility | D |
| Workflow repeatability | F |
| Legal/safety risk | R, risks noted |
| Time to first paid pilot | C ≥ 3 count, days from interview to concierge |

## 4. Decision rules (apply after ≥ 10 Segment-B interviews)

| Decision | Rule |
|---|---|
| **KEEP** wedge and segment B | median hours ≥ 2 **and** Strong share ≥ 30 % **and** ≥ 3 interviews with C ≥ 3 |
| **NARROW** wedge | Pain confirmed (median hours ≥ 2) but ≥ 60 % of the time sits in one step (e.g. only scheduling) → build only that step first |
| **SWITCH** segment | Another segment with n ≥ 5 has a mean evidence-weighted fit ≥ 10 points higher than B |
| **RETHINK** | median hours < 1 **and** Strong share < 10 % |
| **NOT ENOUGH DATA** | fewer than 10 Segment-B interviews, or more than half with Q ≤ 1 |

If two rules fire, discuss them explicitly in `discovery-synthesis.md`; do not pick the convenient one.

## 5. Limits of this model

- 10–15 interviews give direction, not statistics.
- Self-selection: people who accept an interview are more likely to feel the pain.
- Hours are mostly self-reported until concierge measurement (see `baseline-metrics.md`).
- The model cannot see competitors' satisfaction directly; Q16–Q19 and negatives cover that.

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-11-08 | v0 created | — |
