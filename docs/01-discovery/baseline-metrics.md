# Baseline Metrics — v0, 2026-11-08

> **Authorship:** drafted by Claude (AI assistant). **No baseline has been measured yet.** All tables below are empty on purpose.

## Why a baseline first

Without a measured "before", any later claim like "saves 50 % of time" is fiction. Measure at least **one real listing without our help** (records or observation) before the concierge changes anything.

## Evidence levels

| Level | Source | Trust |
|---|---|---|
| E1 | Self-report in an interview | Low — people misremember time |
| E2 | Records: inbox counts, CRM timestamps, calendar | Medium |
| E3 | Observation or time log kept during the work | High |

Always record the level next to the number. A KPI used in a pitch must be E2 or E3.

## Metric definitions

| ID | Metric | Formula / definition | Source | Level |
|---|---|---|---|---|
| B1 | Inquiries per listing | count of inquiries until listing paused/closed; also count in first 48 h | CRM / portal | E2 |
| B2 | Operator minutes on inquiries | sum of time-log minutes in categories *read, reply, follow-up* | time log | E3 |
| B3 | Minutes per inquiry | B2 / B1 | computed | E3 |
| B4 | Median time to first reply (h) | median of (first reply − inquiry received) | timestamps | E2 |
| B5 | Unanswered-inquiry rate | inquiries containing a question or viewing request that got **no reply within the agent's own target time** / all such inquiries | records | E2 |
| B6 | Repetitive share | share of inquiries whose main intent is in the top 5 taxonomy categories | sample of ≥ 50 inquiries, categories only | E2 |
| B7 | Viewing coordination minutes | time-log minutes in category *scheduling* | time log | E3 |
| B8 | Viewings offered / held / no-show rate | counts; no-show = booked but absent | calendar | E2 |
| B9 | Days to viewing slots filled | listing live → all planned slots booked | records | E2 |
| B10 | Days to signed lease | context only; many confounders, **not** our KPI | records | E2 |
| B11 | Factual errors sent | replies that stated a wrong fact (rent, size, date, amenity) | review of sent replies | E2 |

B5 deliberately avoids judging whether an applicant was "suitable". It measures responsiveness, not selection, so it cannot become a hidden ranking.

## Time-log template (concierge and baseline)

Kept by the person doing the work, one row per work block. Categories match the taxonomy in `concierge-playbook.md`.

| Date | Start | End | Minutes | Category (read / reply / follow-up / scheduling / admin) | Inquiries handled | Notes (no personal data) |
|---|---|---|---|---|---|---|
| | | | | | | |

## Baseline table (per listing)

| Listing ID (internal, no address) | Agency (INT-ID) | B1 | B1 48 h | B2 | B3 | B4 | B5 | B6 | B7 | B8 | B9 | B11 | Level | Confounders |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | | | | |

## Confounders to record every time

Season and weekday of go-live · rent level vs. district · listing quality (photos, completeness) · paid portal promotion · number of portals · group vs. individual viewings · staff availability that week.

## Sample-size honesty

1–3 listings give a **descriptive** baseline, not a statistically valid effect size. Report ranges and medians, name the confounders, and do not compute p-values on n = 3.
