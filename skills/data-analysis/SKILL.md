---
name: data-analysis
description: "Decision-first data analysis with statistical rigor gates."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
context: fork
routing:
  triggers:
    - analyze data
    - data analysis
    - CSV
    - dataset
    - metrics
    - trend
    - cohort
    - A/B test
    - statistical
    - distribution
    - correlation
    - KPI
    - funnel
    - experiment results
    - "data insights"
    - "statistical analysis"
    - "CSV analysis"
    - "explore dataset"
  pairs_with:
    - workflow
    - codebase-analyzer
  complexity: medium
  category: analysis
---

# Data Analysis Skill

Every analysis begins with the decision being supported, works backward to the evidence required, then touches data. **Analysis without a decision is just arithmetic.**

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `preferred-patterns.md` | Loads detailed guidance from `preferred-patterns.md`. |
| example-driven tasks | `compute-examples.md` | Loads detailed guidance from `compute-examples.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| tasks related to this reference | `output-templates.md` | Loads detailed guidance from `output-templates.md`. |
| tasks related to this reference | `rigor-gates.md` | Loads detailed guidance from `rigor-gates.md`. |
| example-driven tasks | `worked-examples.md` | Loads detailed guidance from `worked-examples.md`. |

## Instructions

### Phase 1: FRAME (Frame the decision before touching data)

**Goal**: Establish what decision this analysis supports and what evidence would change it.

Starting with data before the decision context is the most common analytical failure. Complete framing even when the user says they "just want numbers."

**Step 1: Identify the decision**
- What specific decision does this analysis support?
- Who is the decision-maker?
- What are their options? (Option A vs. B vs. do nothing)
- What is the default action if no analysis is performed?

If the user cannot articulate a decision, ask: "What will you do differently based on this analysis?" If "nothing", switch to Exploratory Mode and label all output as exploratory. Exploratory Mode still applies rigor gates but makes no causal claims.

**Step 2: Define evidence requirements**
- What evidence would favor Option A over Option B?
- Minimum evidence threshold for changing the default action?
- Deal-breakers? (e.g., "If churn exceeds 5%, we switch vendors regardless of cost")

**Step 3: Save the frame artifact**

Save `analysis-frame.md` using the template from `references/output-templates.md`.

**GATE**: Decision identified, options enumerated, evidence requirements written to file. If no decision articulated, explicitly switch to Exploratory Mode and document. Proceed only when gate passes.

---

### Phase 2: DEFINE (Lock metrics before loading data)

**Goal**: Define exactly what will be measured, how, and over what population. Write definitions to file before any data is loaded.

Defining metrics after seeing data enables choosing definitions that produce favorable results. Locking first makes the analysis auditable.

**Step 1: Define metrics**

For each metric:
- **Name**: Clear, unambiguous label
- **Formula**: Exact computation (numerator/denominator for rates, aggregation for summaries)
- **Population**: Who/what is included and excluded
- **Time window**: Start, end, granularity (daily/weekly/monthly)
- **Segments**: How data will be sliced

**Step 2: Define comparison groups** (if applicable)
- **Group A/B**: Definition and selection criteria
- **Fairness check**: Same population and time window?

**Step 3: Define success criteria**
- Meaningful result threshold?
- Minimum sample size per segment?
- One-tailed or two-tailed question?

**Step 4: Save definitions artifact**

Save `metric-definitions.md` using the template from `references/output-templates.md`.

**GATE**: All metrics defined with formulas and populations. Definitions saved. Comparison fairness checks documented if applicable. Proceed only when gate passes.

**Immutability rule**: Once Phase 3 begins, definitions are locked. If data reveals an unworkable definition, return to Phase 2, update, and document the change and reason. Silent definition changes are p-hacking.

---

### Phase 3: EXTRACT (Load data. Assess quality. No interpretation.)

**Goal**: Load data, profile quality, determine adequacy. No interpretation in this phase.

Combining loading and interpretation causes confirmation bias. Extracting first forces confrontation with quality issues before they distort conclusions.

**Step 1: Detect available tools**

See `references/compute-examples.md` for tool detection code. If pandas unavailable, fall back to `csv.DictReader` + `statistics` module.

**Step 2: Load and inspect data**

Profile: row count, column names/types, missing values per column (absolute and %), date range, unique values for categoricals, distribution stats for numerics (min, max, mean, median, stdev).

**Step 3: Assess data quality**

Apply the Sample Adequacy gate (see `references/rigor-gates.md` Gate 1):

| Check | Minimum | Action if Failed |
|-------|---------|------------------|
| Row count vs. population | Report sample fraction | State "N of M", warn if <5% coverage |
| Time window completeness | No gaps >10% of window | Identify gaps, adjust window or note limitation |
| Segment minimums | 30+ observations per segment | Merge small segments or exclude with disclosure |
| Missing value rate | <20% per critical column | Impute with disclosure or exclude column |

**Step 4: Save quality report**

Save `data-quality-report.md` using the template from `references/output-templates.md`.

**GATE**: Data loaded, quality report saved, all four adequacy checks assessed. If quality fails, document affected analyses and remediation. Proceed only when gate passes or failures documented as limitations.

---

### Phase 4: ANALYZE (Compute metrics. Apply rigor gates.)

**Goal**: Compute metrics per locked definitions, applying statistical rigor gates. Report confidence intervals, not point estimates -- "3-7% lift" is useful; "5% lift" implies false precision.

**Step 1: Compute primary metrics**

Calculate each metric using the exact Phase 2 formula. See `references/compute-examples.md` for stdlib and pandas patterns including Wilson score confidence intervals.

**Step 2: Apply Comparison Fairness gate** (if comparing groups)

Before interpreting any comparison (see `references/rigor-gates.md` Gate 2):
- Same time window for all groups
- Same population definition
- Known confounders documented
- Survivorship bias checked

**Step 3: Apply Multiple Testing Correction** (if testing multiple hypotheses)

See `references/rigor-gates.md` Gate 3 and `references/compute-examples.md`. Report all segments tested -- if you test 10 segments, one will likely show significance by chance.

**Step 4: Apply Practical Significance gate**

See `references/rigor-gates.md` Gate 4:
- Report effect size alongside statistical significance
- Report confidence intervals, not just point estimates
- Assess whether effect exceeds minimum actionable threshold from Phase 2
- Provide base rate context: "from 2.1% to 2.3%" not just "+10% lift"

**Step 5: Save analysis results**

Save `analysis-results.md` using the template from `references/output-templates.md`.

**GATE**: All metrics computed. Rigor gates applied and documented. Violations remediated or recorded as limitations. Proceed only when gate passes.

---

### Phase 5: CONCLUDE (Lead with insights. Return to the decision.)

**Goal**: Translate results into a decision-oriented report. Lead with what the data says about the decision, not computation details. Decision-maker reads Phase 5; auditor reads Phases 2-4.

**Step 1: State the headline finding**

One sentence addressing the decision from Phase 1:
- "The data supports Option A: churn in the test group is 2.3% lower (95% CI: 1.1-3.5%) than control, exceeding the 1% threshold."
- "The data is inconclusive: conversion improved 0.8%, but CI (-0.2% to 1.8%) includes zero."
- "The data supports neither option: both segments show identical retention within measurement error."

**Step 2: Present supporting evidence**

Key metrics in order of importance:
1. Primary metric with confidence interval
2. Secondary metrics that reinforce or qualify
3. Segment breakdowns if revealing important variation

**Step 3: State limitations explicitly**

Wide confidence intervals ARE the finding (insufficient data), not a formatting problem to hide.

**Step 4: Return to the decision**

- Does evidence meet the Phase 1 threshold?
- Deal-breakers triggered?
- Recommended action with stated confidence?
- What additional data would increase confidence?

**Step 5: Save final report**

Save `analysis-report.md` using the template from `references/output-templates.md`.

**GATE**: Report saved with headline, limitations, and recommendation tied to the decision. All artifacts referenced. Analysis complete.

---

## Reference Loading

| Signal | Load |
|--------|------|
| Phase 3 or 4 -- computing metrics, applying gates | `references/rigor-gates.md` |
| Phase 3 or 4 -- Python code for tool detection, CI computation | `references/compute-examples.md` |
| Any phase -- saving an artifact file | `references/output-templates.md` |
| Working examples of the full 5-phase flow | `references/worked-examples.md` |
| Data parse failure, segment size issue, definition revision | `references/error-handling.md` |
| Anti-pattern recognition (p-hacking, survivorship bias, etc.) | `references/preferred-patterns.md` |

---

## References

- **Rigor Gates**: `references/rigor-gates.md` - Statistical gate documentation with examples
- **Output Templates**: `references/output-templates.md` - Phase artifact templates and analysis type templates
- **Compute Examples**: `references/compute-examples.md` - Python computation patterns for extraction and analysis
- **Worked Examples**: `references/worked-examples.md` - Three end-to-end examples (A/B test, trend, distribution)
- **Error Handling**: `references/error-handling.md` - Error recovery procedures and blocker criteria
- **Anti-Patterns**: `references/preferred-patterns.md` - Extended pattern catalog with code examples
