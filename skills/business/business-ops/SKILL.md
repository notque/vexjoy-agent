---
name: business-ops
description: "Business operations: strategy, technology, growth, competitive intelligence, support, finance, HR, legal, operations, sales, productivity, product management."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - "business strategy"
    - "build vs buy"
    - "vendor evaluation"
    - "competitive analysis"
    - "market landscape"
    - "brand strategy"
    - "pricing strategy"
    - "hiring plan"
    - "team structure"
    - "budget allocation"
    - "revenue model"
    - "go to market"
    - "product roadmap strategy"
    - "investor pitch"
    - "partnership evaluation"
    - "operational efficiency"
    - "customer acquisition cost"
    - "unit economics"
    - "business model"
    - "market fit"
  not_for: "micro library choices (use decision-helper), writing content, SEO of specific posts, or tactical marketing competitive analysis (use marketing) — this is executive strategy, not campaign execution. Code security audits, vulnerability scanning, or auth-flow reviews (use security) — only financial/accounting audit and SOX compliance. Code performance review (use reviewer-code) — this covers people performance reviews and HR operations. Software task specs, requirements, or plan-lifecycle management (use planning) — this skill prioritizes and tracks work, not specs. UX design methodology, wireframes, or accessibility audits (use design) — this handles product strategy, roadmaps, user research for feature prioritization."
  complexity: Medium
  category: decision-support
  pairs_with:
    - content
    - data
---

# Business Operations

Thirteen modes covering executive strategy through daily productivity. Classify
the request into one mode, load its reference, follow that reference's framework.

## Mode Detection

| Mode | Signal | Framework |
|------|--------|-----------|
| **STRATEGY** | Market entry, partnerships, resource allocation, "should we" | FRAME -> ANALYZE -> DECIDE |
| **TECHNOLOGY** | Build vs buy, vendor, SaaS, tech stack | TCO analysis -> Vendor scoring -> Decision |
| **GROWTH** | Audience, SEO, brand, community, channel | Segment -> Channel-score -> Plan |
| **COMPETITIVE** | Competitor, market landscape, differentiation | Map landscape -> Position -> Track |
| **EVALUATION** | Feasibility, ROI, go/no-go, effort estimate | Feasibility score -> ROI model -> Verdict |
| **SUPPORT** | Ticket triage, response, KB article, escalation | TRIAGE/RESPOND/KB/ESCALATE/RESEARCH |
| **FINANCE** | Journal entry, reconciliation, variance, SOX | CLASSIFY -> GATHER -> PRODUCE -> VERIFY |
| **HR** | Recruiting, performance review, compensation, hiring | DEFINE -> PIPELINE/EVALUATE -> DOCUMENT |
| **LEGAL** | Contract review, compliance, NDA, DSGVO, GoBD | INTAKE -> ANALYZE -> FLAG -> OUTPUT |
| **OPERATIONS** | Runbook, process docs, risk, vendor, change mgmt | SCOPE -> AUTHOR/ASSESS -> VERIFY |
| **SALES** | Call prep, pipeline, outreach, forecast | RESEARCH -> PREPARE/ANALYZE -> OUTPUT |
| **PRODUCTIVITY** | Task management, daily plan, meeting, standup | CAPTURE -> DECOMPOSE -> PRIORITIZE |
| **PRODUCT** | Feature spec, PRD, roadmap, user research, metrics | UNDERSTAND -> GATHER -> GENERATE |

If the request spans modes, pick the primary. Note the secondary.

---

## Shared Workflow

1. Classify the request into exactly one mode from the table.
2. Load the mode's reference file (see Deep References). Each reference
   contains full framework, sub-modes, phases, and deeper reference pointers.
3. Follow the reference's instructions. Do not improvise a framework when one
   exists.
4. Every mode's top-level reference also specifies an LLM failure-modes
   guardrail file. Load it alongside the main reference.

---

## Executive Modes (STRATEGY, TECHNOLOGY, GROWTH, COMPETITIVE, EVALUATION)

Load `references/csuite.md` for the full C-suite framework. All five modes
share the same 3-phase pattern:

**Phase 1: FRAME** -- Convert the question into a structured decision. Name the
actual decision (users present symptoms; the real decision is broader). Identify
irreversibility. Set time horizon. List 2-4 options. State what makes it hard.

**Phase 2: ANALYZE** -- Per option: upside (best realistic + expected), downside
(worst realistic + recovery + irreversible losses), requirements, opportunity
cost. Separate facts from assumptions. Quantify.

**Phase 3: DECIDE** -- Score options via weighted criteria. Present verdict with
driving factors, risk mitigations, and reversibility assessment. Load
mode-specific deep references for scoring matrices.

---

## Support Mode

Load `references/customer-support.md`. Five sub-modes: TRIAGE (classify ticket,
assign priority P1-P4, route), RESPOND (draft calibrated reply with tone
matching emotional state), KB (convert resolution into publish-ready article),
ESCALATE (build structured brief with impact assessment), RESEARCH (investigate
history with confidence scoring).

Key guardrail: never fabricate ticket history, resolution steps, or customer
quotes.

---

## Finance Mode

Load `references/finance.md`. Six sub-modes: JOURNAL ENTRY, RECONCILIATION,
VARIANCE, STATEMENTS, AUDIT/SOX, CLOSE. All output is working material for
qualified professionals -- not financial advice.

Key guardrails: never fabricate account codes, balances, or transaction details.
Source all numbers from user-provided data. Always state GAAP/IFRS basis.

---

## HR Mode

Load `references/hr.md`. Nine sub-modes: RECRUITING, PERFORMANCE, COMPENSATION,
OFFER, INTERVIEW, ONBOARDING, ORG-PLANNING, PEOPLE-ANALYTICS, POLICY.

Key guardrails: source compensation data from user-provided or public databases.
Focus on skills, behaviors, outcomes -- not demographics. Include legal review
disclaimer on binding language. Ask for jurisdiction before compliance advice.
Minimize PII retention.

---

## Legal Mode

Load `references/legal.md`. Six sub-modes: CONTRACT (clause-by-clause
GREEN/YELLOW/RED analysis), COMPLIANCE (regulation checklist with German
compliance for DSGVO/GoBD/TDDDG), NDA (triage classification), RISK (severity x
likelihood matrix), WRITING (structured legal documents), VENDOR (agreement
inventory and gap analysis).

Key guardrail: analysis support only, not legal advice. All binding language
needs qualified counsel review. Load `references/legal/german-business-compliance.md`
for German-specific regulation.

---

## Operations Mode

Load `references/operations.md`. Nine sub-modes: RUNBOOK, RISK, VENDOR,
PROCESS, CHANGE, CAPACITY, COMPLIANCE, STATUS, OPTIMIZE.

Key patterns: RUNBOOK uses SCOPE -> AUTHOR -> VERIFY with prerequisite
checklists. RISK produces severity x likelihood matrices. CHANGE follows
RFC -> REVIEW -> IMPLEMENT -> VERIFY. All operations docs require rollback
procedures.

---

## Sales Mode

Load `references/sales.md`. Seven sub-modes: CALL-PREP, PIPELINE, OUTREACH,
COMPETITIVE, FORECAST, CALL-SUMMARY, RESEARCH.

Key patterns: CALL-PREP researches prospect then builds agenda with questions.
PIPELINE applies health scoring and flags stale deals. OUTREACH personalizes
from research (never generic templates). FORECAST uses weighted probability
with scenario analysis.

---

## Productivity Mode

Load `references/productivity.md`. Six sub-modes: TASK (decompose and
prioritize), PLAN (daily/weekly time blocks), MEETING (optimize or eliminate),
STATUS (structured updates), REVIEW (weekly retrospective), GOAL (OKRs).

Key patterns: vertical slicing for task decomposition (shippable slices, not
horizontal layers). 1/2/4-hour time buckets. Tasks over 4 hours need
decomposition.

---

## Product Mode

Load `references/product-management.md`. Eight sub-modes: SPEC (PRD with
acceptance criteria), ROADMAP (Now/Next/Later prioritization), STAKEHOLDER
(structured updates), RESEARCH (synthesis with thematic analysis), COMPETITIVE
(battle cards), METRICS (funnel/cohort/retention analysis), SPRINT (backlog
grooming with capacity), BRAINSTORM (Socratic exploration).

---

## Error Handling

| Error | Response |
|-------|----------|
| Too many options (5+) | Eliminate obviously inferior first. Get to 2-4. |
| Not enough information | Identify 2-3 critical unknowns. Recommend research sprint. |
| Analysis paralysis | Reversibility test. If reversible, recommend best option with checkpoint. |
| Emotional attachment | Name the pattern. Ask: stress-test, or genuinely evaluate? |

---

## Deep References

All references contain >100 lines of domain-specific frameworks, templates, and
guardrails. Load on demand per mode.

| Mode | Primary | Sub-references |
|------|---------|----------------|
| STRATEGY | `references/csuite.md` | `references/strategic-frameworks.md`, `references/decision-matrices.md` |
| TECHNOLOGY | `references/csuite.md` | `references/tco-framework.md`, `references/vendor-evaluation.md` |
| GROWTH | `references/csuite.md` | `references/audience-segmentation.md`, `references/channel-evaluation.md` |
| COMPETITIVE | `references/csuite.md` | `references/competitive-mapping.md`, `references/market-positioning.md` |
| EVALUATION | `references/csuite.md` | `references/feasibility-scoring.md`, `references/roi-frameworks.md` |
| SUPPORT | `references/customer-support.md` | `references/customer-support/*.md` |
| FINANCE | `references/finance.md` | `references/finance/*.md` |
| HR | `references/hr.md` | `references/hr/*.md` |
| LEGAL | `references/legal.md` | `references/legal/*.md` |
| OPERATIONS | `references/operations.md` | `references/operations/*.md` |
| SALES | `references/sales.md` | `references/sales/*.md` |
| PRODUCTIVITY | `references/productivity.md` | `references/productivity/*.md` |
| PRODUCT | `references/product-management.md` | `references/product-management/*.md` |
| Cross-cutting | `references/content-funnel.md`, `references/trend-analysis.md`, `references/risk-assessment.md`, `references/estimation-techniques.md`, `references/migration-planning.md` | Shared frameworks |
