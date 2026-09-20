---
name: business-ops
description: "Business decision support for finance, HR, legal/compliance, operations, sales, support, product, and vendor or investment choices. Use when business-domain controls, calculations, or failure modes matter; not for generic planning or writing."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit]
routing:
  triggers: ["build vs buy", "vendor evaluation", "business strategy", "journal entry", "reconciliation", "variance analysis", "hiring plan", "compensation", "contract review", "compliance", "sales pipeline", "support escalation", "product metrics"]
  not_for: "Generic writing, personal productivity, software architecture, code review, or marketing copy. Use the specialist skill for those tasks."
  complexity: Medium
  category: decision-support
---

# Business Operations

Use this skill only for business-domain knowledge that changes the result. Apply ordinary analysis directly; load one reference when its controls or formulas are relevant:

- Finance or accounting: [finance-controls.md](references/finance-controls.md)
- Contracts, privacy, employment, or regulated claims: [legal-people-controls.md](references/legal-people-controls.md)
- Support incidents, operational changes, vendors, or migrations: [operational-controls.md](references/operational-controls.md)
- Sales forecasts, product metrics, investment, or build/buy: [commercial-decisions.md](references/commercial-decisions.md)

## Shared contract

- Separate sourced facts, assumptions, calculations, and recommendations. Never invent transactions, account codes, customer history, contract text, benchmark data, quotes, or market evidence.
- Ask only for missing inputs that can change the decision. Show formulas and units so the user can replace assumptions.
- Treat legal, tax, accounting, compensation, and regulatory outputs as review material. Identify jurisdiction, reporting basis, and effective date where they matter; verify current law or standards from authoritative sources.
- State what evidence would reverse a recommendation and the next review point.
