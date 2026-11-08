# Milestone 1 — Customer discovery and concierge workflow

**Status:** toolkit drafted (v0, 2026-11-08). **All files were drafted by Claude (AI assistant) at the founder's request and have not been reviewed by the founder. No interviews, observations or concierge runs have happened yet.**

## Files

| File | Purpose |
|---|---|
| [interview-script-de.md](interview-script-de.md) | German interview guide (main) incl. variants for landlords, adjacent operators, tenants |
| [interview-script-en.md](interview-script-en.md) | English version, same question numbers |
| [interview-notes-template.md](interview-notes-template.md) | One file per interview |
| [signal-strength-rubric.md](signal-strength-rubric.md) | How to score one interview (P, Q, W, B, D, R, commitment ladder C) |
| [icp-scoring-model.md](icp-scoring-model.md) | Weights, segment metrics, decision rules |
| [interview-tracker.csv](interview-tracker.csv) | One row per interview — **anonymised, no names** |
| [../../scripts/score_discovery.py](../../scripts/score_discovery.py) | Computes scores, segment summary and decision rules |
| [workflow-map.md](workflow-map.md) | Current-state hypothesis, DSK stage model, future state, measurement points |
| [baseline-metrics.md](baseline-metrics.md) | Metric definitions, evidence levels, time-log template |
| [concierge-playbook.md](concierge-playbook.md) | Manual wedge: levels, hard rules, procedure, taxonomy, fact sheet, edit log |
| [outreach-messages.md](outreach-messages.md) | DE/EN messages, channel priority, legal note |
| [pilot-offer.md](pilot-offer.md) | One-page pilot offer DE/EN, price hypothesis, prerequisites |
| [discovery-synthesis.md](discovery-synthesis.md) | Empty template — fill only from real interviews |

## Data rules for this folder

- The repository holds **no personal data**. Contact names, emails, the do-not-contact list and raw notes that could identify someone live in a private place outside the repository (for example a private spreadsheet).
- The tracker uses interview IDs (INT-001 …) only.
- Synthetic rows (ID prefix `SYNTH-`) are refused by the script in the real tracker; demo data exists only in memory (`--demo`).

## Commands

```bash
python3 scripts/score_discovery.py            # score real interviews
python3 scripts/score_discovery.py --demo     # see how it works with synthetic data
```

## Exit criteria for Milestone 1

- [ ] ≥ 10 Segment-B interviews and ≥ 5 adjacent interviews, notes filed, tracker filled
- [ ] ≥ 1 observation (L0) of a real inquiry peak
- [ ] ≥ 1 concierge listing (L1) with time log, edit log and report — after L6 is answered
- [ ] Baseline table filled with evidence levels
- [ ] `discovery-synthesis.md` written, decision recorded (KEEP / NARROW / SWITCH / RETHINK)
- [ ] Lawyer questions L1, L2, L3, L5, L6 asked

Only after this does Milestone 2 (repository and architecture) start for real. Product code before that point would be built on guesses.

## Contribution log

| Artifact | Drafted by | Reviewed by founder | Validated by data |
|---|---|---|---|
| All Milestone 1 files and `scripts/score_discovery.py` | Claude (AI) | no | no |
| Script tested on synthetic and invalid input | Claude (AI), 2026-11-08 | no | — |
