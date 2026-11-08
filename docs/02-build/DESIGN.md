# Console Design — v0.1 (2026-11-08)

> Direction chosen by Claude (AI assistant) under the design-ops routing for the founder's own projects. Locked here so later sessions do not drift; change it deliberately.

## Problem and user

A letting agent clears dozens of inquiries per listing. The console must make one decision fast and safe: *can I send this reply?* The metric it serves: operator minutes per inquiry, without unsupported facts going out.

## Principle

One bold element: **the reply set as a letter with its evidence in the margin.** The draft uses a serif letter face; every fact it uses sits in the margin with its status and source, so checking a draft means scanning one column. Everything else is quiet.

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | #f5f6f3 | #121b1a | Page |
| `--surface` | #ffffff | #182322 | Panels, letter |
| `--ink` | #1c2830 | #e3ebe8 | Text |
| `--ink-2` | #4a5863 | #a7b5b1 | Secondary text |
| `--isar` | #1f6f6b | #56b8b0 | Primary action, focus, letter rule |
| `--verified` | #2e7d4f | #74c497 | Verified facts, booked viewings |
| `--extracted` | #9a5f0c | #e3aa55 | Unconfirmed facts, in-progress states, demo note |
| `--unknown` | #66727e | #98a5b1 | Unknown facts, stopped states |
| `--alert` | #ad3530 | #f0918a | Needs you, blocking findings, danger actions |

Type: Hanken Grotesk for the interface (15 px base), Source Serif 4 for applicant messages and the reply (16–17 px, line-height 1.6). Status is never colour alone: each state and fact status has a label next to its mark.

## Layout

Desktop: inbox list 360 px, detail pane fluid; letter and margin side by side (margin 300 px). Below 960 px the margin moves under the letter; below 760 px the list and the detail become two screens with a back button. No horizontal scroll at 375 px (measured: document scroll width 375 px at a 375 px viewport, 2026-11-08).

## Copy rules

Sentence case, plain verbs, no all-caps labels. Buttons say what happens ("Approve reply", "Mark as sent", "Erase applicant data"). Every state has a human label ("Needs you", "Draft ready for review", "Approved, not sent yet").
