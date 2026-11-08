# Metrics Tree (v0, 2026-11-08)

> **Authorship:** drafted by Claude (AI assistant). Targets are placeholders until a baseline is measured in concierge pilots.

## North star

**Confirmed viewings with complete, permitted applicant info per operator-hour** (per listing).

Why: it ties the product to the customer's real outcome (filled viewing slots) *and* to efficiency (operator hours), and it cannot be gamed by generating more text. It is only meaningful with real pilot data; on synthetic data we track the drivers.

```
North star: confirmed viewings per operator-hour
├── Speed
│   ├── time from inquiry received → approved reply
│   ├── unanswered-inquiry rate (questions or viewing requests with no reply within
│   │   the operator's target time — measures responsiveness, never "suitability")
│   └── time to fill viewing slots
├── Efficiency
│   ├── operator minutes per inquiry
│   ├── human-edit distance on drafts (how much the agent rewrites)
│   └── draft acceptance rate (approved without edits)
├── Quality
│   ├── inquiry classification accuracy
│   ├── % facts in drafts traced to fact sheet (evidence coverage)
│   ├── unsupported-claim rate
│   └── correct "unknown" rate (says unknown when fact missing)
└── Guardrails — any violation blocks shipping
    ├── messages sent without approval = 0
    ├── sensitive-attribute inference or proxy ranking = 0
    ├── cross-applicant data leak = 0
    ├── stop-request compliance = 100 %
    ├── deletion requests completed within policy window = 100 %
    └── prompt-injection success rate on red-team set = 0
```

## Business metrics (pilot stage)

| Metric | Why |
|---|---|
| Interviews → concierge pilot conversion | Is the pain real enough to give us a listing? |
| Concierge → paid pilot conversion | Willingness to pay |
| Active listings per customer per month | Usage frequency (core risk for this ICP) |
| Cost per processed inquiry (LLM + infra + manual ops) | Gross margin |
| Operator hours saved vs. baseline | Core value claim |

## Anti-metrics (do not optimise)

- number of generated drafts or messages;
- automation rate on its own;
- reply speed if accuracy drops.
