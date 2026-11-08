# Prompt Changelog

Every prompt change gets a new version id, an entry here and an eval run before it ships. The version id is written into every agent output and audit event, so any draft can be traced to the exact prompt.

| Version | File | Date | Change | Eval |
|---|---|---|---|---|
| `inquiry-v1` | `src/rental_copilot/prompts/inquiry_v1.md` | 2026-11-08 | Initial: instruction hierarchy, untrusted-message delimiters, 12-intent taxonomy, drafting rules (verified facts only, cite fact ids, unknowns stay open, slots verbatim, stage-A data only, no legal statements, promises, pressure, other applicants or protected traits, neutral greeting) | Not yet run against Claude (needs cost approval) |
| `mock-rules-v1` | `src/rental_copilot/providers/mock.py` | 2026-11-08 | Deterministic keyword rules and templates for offline runs | 40/40 on `cases_v1` 1.0.0 (written together, see report caveat) |
