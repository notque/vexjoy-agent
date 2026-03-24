---
name: data-analysis
description: |
  Decision-first data analysis with statistical rigor gates. Use when
  analyzing CSV, JSON, database exports, API responses, logs, or any
  structured data to support a business decision. Handles: trend analysis,
  cohort comparison, A/B test evaluation, distribution profiling, anomaly
  detection. Do NOT use for codebase analysis (use codebase-analyzer),
  codebase exploration (use explore-pipeline), or ML model training.
version: 1.0.0
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
    - explore-pipeline
    - codebase-analyzer
    - research-to-article
  complexity: medium
  category: analysis
---

# Data Analysis Skill

## Operator Context

This skill operates as an operator for decision-first data analysis, configuring Claude's behavior for structured analytical reasoning with statistical rigor. It implements a **Decision-First Framework** -- every analysis begins with the decision being supported, works backward to the evidence required, and only then touches the data. This prevents the common failure mode where analysis produces impressive summaries that answer the wrong question.

Core thesis: **"Analysis without a decision is just arithmetic."**

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default behaviors.
- **Over-Engineering Prevention**: Analyze what was asked. No speculative analyses, no "while I'm at it" tangents into unrelated metrics.
- **Decision-First Ordering**: ALWAYS establish the decision context (Phase 1) before loading data (Phase 3). Starting with data produces technically correct but practically useless analysis because the patterns found may not map to the decision-maker's options.
- **Separate Extraction from Interpretation**: Phase 3 (EXTRACT) loads and profiles data. Phase 4 (ANALYZE) interprets it. Never combine these steps. Combining them causes confirmation bias -- you see what you expect instead of what the data shows.
- **Metric Definitions Are Immutable**: Once Phase 2 (DEFINE) is complete and data loading begins, metric definitions cannot change silently. If they must change, re-enter Phase 2 and document why. This prevents the common anti-pattern of adjusting definitions to produce favorable results (p-hacking by another name).
- **Uncertainty Quantification**: Report confidence intervals, not point estimates. "3-7% lift" is useful; "5% lift" is misleading because it implies false precision.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Lead with insights, not methods. The decision-maker needs "Revenue is declining 3% month-over-month, driven by churning mid-tier accounts" -- not "I performed a linear regression on the time series data using OLS estimation."
- **Artifact Trail**: Save artifacts at every phase. Context is ephemeral; files persist. Each phase produces a named artifact that can be audited later.
- **Graceful Tool Degradation**: Detect pandas/matplotlib availability via try/except. Use them when available, fall back to stdlib (csv, json, statistics, collections) when not. Analysis quality must be identical -- only presentation differs.
- **Statistical Rigor Gates**: Apply all four rigor gates during Phase 4. Violations must be remediated or documented as explicit limitations. See `references/rigor-gates.md` for detailed gate documentation.

### Optional Behaviors (OFF unless enabled)
- **Visualization Output**: Generate matplotlib charts saved as PNG when matplotlib is available and user requests visual output.
- **Multi-Dataset Joins**: Join across multiple data files when analysis requires cross-referencing (e.g., user events + revenue data).
- **Exploratory Mode**: Skip Phase 1 framing when the user explicitly asks for open-ended exploration ("just show me what's interesting"). Still apply rigor gates and label all findings as exploratory.

## What This Skill CAN Do
- Analyze structured data (CSV, JSON, SQLite exports, log files) to support specific business decisions
- Profile data quality: row counts, missing values, outliers, date range coverage, type distributions
- Compute summary statistics with confidence intervals using Python stdlib or pandas
- Compare groups (cohorts, A/B variants, time periods) with statistical rigor checks
- Detect trends, distributions, anomalies, and correlations with appropriate caveats
- Produce decision-oriented reports that lead with insights and state limitations explicitly

## What This Skill CANNOT Do
- **Machine learning**: No model training, prediction, or hyperparameter tuning. That is a separate capability.
- **Real-time monitoring**: This is batch analysis of snapshot data, not live stream processing.
- **Database querying**: The skill analyzes data already extracted. It does not connect to databases or APIs. The user provides the data file.
- **Codebase analysis**: Use codebase-analyzer for code convention discovery. This skill analyzes business/operational data.
- **Automated recurring reports**: Each analysis is a one-shot investigation. Scheduled analysis requires separate automation.

---

## Instructions

### Phase 1: FRAME (Do NOT touch data before framing the decision)

**Goal**: Establish what decision this analysis supports and what evidence would change it.

**Why this phase exists**: Starting with data before establishing the decision context is the single most common analytical failure. The analyst finds interesting patterns and presents them, but the decision-maker cannot act because the patterns do not map to their options. Framing first ensures every computation serves the decision.

**Step 1: Identify the decision**
- What specific decision does this analysis support?
- Who is the decision-maker?
- What are their options? (Option A vs. Option B vs. do nothing)
- What is the current default action if no analysis is performed?

If the user does not articulate a decision, ask: "What will you do differently based on this analysis?" If the answer is "nothing" or "I just want to see the data," switch to Exploratory Mode (optional behavior) and label all output as exploratory.

**Step 2: Define evidence requirements**
- What evidence would favor Option A over Option B?
- What is the minimum evidence threshold for changing the default action?
- Are there deal-breakers? (e.g., "If churn exceeds 5%, we switch vendors regardless of cost")

**Step 3: Save the frame artifact**

Save `analysis-frame.md`:
```markdown
# Analysis Frame

## Decision
[What decision is being supported]

## Decision-Maker
[Who will act on this analysis]

## Options
- Option A: [description]
- Option B: [description]
- Default (no action): [what happens if we don't decide]

## Evidence Requirements
- Favors Option A if: [condition]
- Favors Option B if: [condition]
- Minimum threshold: [what bar must be cleared]

## Deal-Breakers
- [condition that forces a specific option regardless]
```

**GATE**: Decision identified, options enumerated, evidence requirements written to file. If the user cannot articulate a decision, explicitly switch to Exploratory Mode and document this in the frame. Proceed only when gate passes.

---

### Phase 2: DEFINE (Lock metrics before loading data)

**Goal**: Define exactly what will be measured, how, and over what population. Write definitions to file before any data is loaded.

**Why this phase exists**: Defining metrics after seeing data enables (consciously or not) choosing definitions that produce favorable results. Locking definitions first makes the analysis auditable -- anyone can verify whether the definitions were followed.

**Step 1: Define metrics**

For each metric:
- **Name**: Clear, unambiguous label
- **Formula**: Exact computation (numerator/denominator for rates, aggregation method for summaries)
- **Population**: Who/what is included and excluded
- **Time window**: Start date, end date, granularity (daily/weekly/monthly)
- **Segments**: How data will be sliced (by region, cohort, plan tier, etc.)

**Step 2: Define comparison groups** (if applicable)

For each comparison:
- **Group A**: Definition and selection criteria
- **Group B**: Definition and selection criteria
- **Fairness check**: Are groups drawn from the same population and time window?

**Step 3: Define success criteria**

- What threshold constitutes a meaningful result?
- What is the minimum sample size per segment?
- Is this a one-tailed or two-tailed question?

**Step 4: Save definitions artifact**

Save `metric-definitions.md`:
```markdown
# Metric Definitions

## Metrics
### [Metric Name]
- Formula: [exact computation]
- Population: [inclusion/exclusion criteria]
- Time window: [start - end, granularity]
- Segments: [how data is sliced]

## Comparison Groups (if applicable)
### Group A: [Name]
- Selection: [criteria]
### Group B: [Name]
- Selection: [criteria]
- Fairness: [same population? same time window?]

## Success Criteria
- Minimum meaningful effect: [threshold]
- Minimum sample per segment: [N]
- Test type: [one-tailed / two-tailed / descriptive only]
```

**GATE**: All metrics defined with formulas and populations. Definitions saved to file. If this is a comparison analysis, fairness checks documented. Proceed only when gate passes.

**Immutability rule**: Once Phase 3 begins, these definitions are locked. If the data reveals that a definition is unworkable (e.g., the column doesn't exist), return to Phase 2, update the definition, and document the change and its reason. Do not silently adjust.

---

### Phase 3: EXTRACT (Load data. Assess quality. No interpretation.)

**Goal**: Load the data, profile its quality, and determine whether it is adequate for the planned analysis. Do NOT interpret results during this phase.

**Why extraction is separate from analysis**: Combining loading and interpretation causes confirmation bias. When you compute a metric and interpret it in the same breath, you see what you expect. Extracting first forces you to confront data quality issues (missing values, unexpected distributions, date gaps) before they silently distort your conclusions.

**Step 1: Detect available tools**

```python
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
```

If pandas is unavailable, fall back to `csv.DictReader` + `statistics` module. Analysis quality must be identical.

**Step 2: Load and inspect data**

Profile the dataset:
- Row count
- Column names and inferred types
- Missing value count per column (absolute and percentage)
- Date range (if temporal data)
- Unique value counts for categorical columns
- Basic distribution stats for numeric columns (min, max, mean, median, stdev)

**Step 3: Assess data quality**

Apply the Sample Adequacy gate (see `references/rigor-gates.md` Gate 1):

| Check | Minimum | Action if Failed |
|-------|---------|------------------|
| Row count vs. population | Report sample fraction | State "N of M" and warn if <5% coverage |
| Time window completeness | No gaps >10% of window | Identify gaps, adjust window or note limitation |
| Segment minimums | 30+ observations per segment | Merge small segments or exclude with disclosure |
| Missing value rate | <20% per critical column | Impute with disclosure or exclude column |

**Step 4: Save quality report**

Save `data-quality-report.md`:
```markdown
# Data Quality Report

## Dataset Overview
- Source: [file path / description]
- Rows: [N]
- Columns: [N]
- Date range: [start - end]

## Column Profiles
| Column | Type | Non-null | Missing % | Unique | Notes |
|--------|------|----------|-----------|--------|-------|
| [name] | [type] | [count] | [pct] | [count] | [flags] |

## Quality Assessment
- [ ] Sample adequate (N=[count], population=[est])
- [ ] Time window complete (gaps: [none / list])
- [ ] Segment minimums met ([list segments below 30])
- [ ] Missing values acceptable ([list columns above 20%])

## Quality Issues
[List any issues that affect planned analysis]

## Data Ready: [YES / NO - with reason]
```

**GATE**: Data loaded, quality report saved, all four adequacy checks assessed. If data quality fails, document which analyses are affected and whether remediation is possible (merge segments, narrow time window, exclude columns). Proceed only when gate passes or failures are documented as limitations.

---

### Phase 4: ANALYZE (Compute metrics. Apply rigor gates.)

**Goal**: Compute metrics per the locked definitions from Phase 2, applying statistical rigor gates at every step.

**Step 1: Compute primary metrics**

Calculate each metric defined in Phase 2 using the exact formula specified. Use Python stdlib or pandas as available:

```python
# stdlib approach
import csv, statistics, collections, math

with open(data_file) as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Example: conversion rate with confidence interval
successes = sum(1 for r in rows if r['converted'] == '1')
total = len(rows)
rate = successes / total
# Wilson score interval for proportions
z = 1.96  # 95% CI
denominator = 1 + z**2 / total
centre = (rate + z**2 / (2 * total)) / denominator
spread = z * math.sqrt((rate * (1 - rate) + z**2 / (4 * total)) / total) / denominator
ci_lower = centre - spread
ci_upper = centre + spread
```

```python
# pandas approach (when available)
import pandas as pd

df = pd.read_csv(data_file)
rate = df['converted'].mean()
# Bootstrap CI or Wilson as above
```

**Step 2: Apply Comparison Fairness gate** (if comparing groups)

Before interpreting any group comparison, verify (see `references/rigor-gates.md` Gate 2):
- Same time window for all groups
- Same population definition for all groups
- Known confounders identified and documented
- Survivorship bias checked

**Step 3: Apply Multiple Testing Correction** (if testing multiple hypotheses)

See `references/rigor-gates.md` Gate 3:

| Scenario | Correction |
|----------|------------|
| 2-5 comparisons | Report all p-values, flag that they are unadjusted |
| 6+ comparisons | Apply Bonferroni: adjusted threshold = 0.05 / N |
| Exploratory sweep | Label as exploratory, make no causal claims |

**Step 4: Apply Practical Significance gate**

See `references/rigor-gates.md` Gate 4:
- Report effect size alongside statistical significance
- Report confidence intervals, not just point estimates
- Assess whether the effect exceeds the minimum actionable threshold from Phase 2
- Provide base rate context: "from 2.1% to 2.3%" not just "+10% lift"

**Step 5: Save analysis results**

Save `analysis-results.md`:
```markdown
# Analysis Results

## Metrics
### [Metric Name]
- Value: [point estimate]
- 95% CI: [lower - upper]
- Sample: N=[count]

## Comparisons (if applicable)
### [Group A] vs [Group B]
- Group A: [metric] = [value] (N=[count])
- Group B: [metric] = [value] (N=[count])
- Difference: [absolute] ([relative]%)
- 95% CI of difference: [lower - upper]
- Practical significance: [above/below minimum threshold]

## Rigor Gate Results
- [ ] Sample Adequacy: [PASS / FAIL - details]
- [ ] Comparison Fairness: [PASS / FAIL / N/A - details]
- [ ] Multiple Testing: [PASS / FAIL / N/A - details]
- [ ] Practical Significance: [PASS / FAIL - details]

## Rigor Violations (if any)
[List violations and their impact on conclusions]
```

**GATE**: All defined metrics computed. Rigor gates applied and results documented. Violations either remediated or recorded as limitations. Proceed only when gate passes.

---

### Phase 5: CONCLUDE (Lead with insights. Return to the decision.)

**Goal**: Translate analytical results into a decision-oriented report. Lead with what the data says, not how you computed it.

**Why this phase is separate**: Phase 4 produces numbers. Phase 5 produces meaning. Separating them prevents the analyst from burying the insight under methodology. The decision-maker reads Phase 5; the auditor reads Phases 2-4.

**Step 1: State the headline finding**

One sentence that directly addresses the decision from Phase 1:
- "The data supports Option A: churn in the test group is 2.3% lower (95% CI: 1.1-3.5%) than control, exceeding the 1% threshold for switching."
- "The data is inconclusive: while conversion improved by 0.8%, the confidence interval (-0.2% to 1.8%) includes zero."
- "The data supports neither option: both segments show identical retention within measurement error."

**Step 2: Present supporting evidence**

Summarize the key metrics that support the headline, in order of importance:
1. Primary metric with confidence interval
2. Secondary metrics that reinforce or qualify
3. Segment breakdowns if they reveal important variation

**Step 3: State limitations explicitly**

- What the data does NOT tell you
- Rigor gate violations and their implications
- Known confounders that could not be controlled
- Sample limitations (size, coverage, time window)

**Step 4: Return to the decision**

Explicitly map findings back to the decision frame:
- Does the evidence meet the minimum threshold from Phase 1?
- Are there deal-breakers triggered?
- What is the recommended action, with stated confidence?
- What additional data would increase confidence?

**Step 5: Save final report**

Save `analysis-report.md`:
```markdown
# Analysis Report

## Headline
[One sentence: what the data says about the decision]

## Decision Context
[Recap from Phase 1 frame]

## Key Findings
1. [Primary finding with CI]
2. [Supporting finding]
3. [Qualifying finding or important segment variation]

## Limitations
- [Limitation 1]
- [Limitation 2]

## Recommendation
[Action recommendation with confidence level]

## What Would Increase Confidence
- [Additional data or analysis that would help]

---

## Appendix: Methodology
- Data source: [file]
- Rows analyzed: [N]
- Time window: [range]
- Tools: [pandas/stdlib]
- Metrics: See metric-definitions.md
- Quality: See data-quality-report.md
- Detailed results: See analysis-results.md
```

**GATE**: Report saved with headline finding, limitations, and explicit recommendation tied back to the decision. All artifact files referenced. Analysis complete.

---

## Examples

### Example 1: A/B Test Evaluation
User says: "Evaluate this A/B test - here's the CSV of results"
Actions:
1. FRAME: "Should we ship variant B?" Options: ship B, keep A, extend test. Evidence: conversion lift >1% with 95% CI excluding zero.
2. DEFINE: Conversion = orders/visitors per variant. Time: test period. Segments: mobile/desktop.
3. EXTRACT: Load CSV, profile 45k rows, check group sizes balanced, verify no date gaps.
4. ANALYZE: Variant B conversion 4.2% vs A 3.9%. Difference 0.3% (CI: -0.1% to 0.7%). Fails practical significance -- CI includes zero.
5. CONCLUDE: "Data is inconclusive. The observed 0.3% lift has a confidence interval that includes zero. Recommend extending the test for 2 more weeks to reach adequate power."

### Example 2: Trend Analysis
User says: "What's happening with our monthly revenue? Here's 2 years of data."
Actions:
1. FRAME: "Is revenue growth slowing, and should we invest in acquisition?" Options: increase spend, maintain, cut.
2. DEFINE: Revenue = sum of invoice amounts per month. Growth = month-over-month %. Segments: new vs returning customers.
3. EXTRACT: Load 24 months, verify no missing months, check for outliers (December spike).
4. ANALYZE: Overall +2.1%/mo but returning customer revenue flat. All growth from new customers. Seasonality adjusted.
5. CONCLUDE: "Revenue growth is entirely acquisition-driven. Returning customer revenue has been flat for 8 months, suggesting a retention problem. Recommend investigating churn before increasing acquisition spend."

### Example 3: Distribution Profiling
User says: "Our API response times feel slow. Here's a week of latency data."
Actions:
1. FRAME: "Do we need to optimize the API?" Options: optimize, add caching, do nothing. Threshold: p99 >500ms warrants action.
2. DEFINE: Latency = request duration in ms. Segments: by endpoint, by hour. Key metrics: p50, p95, p99.
3. EXTRACT: Load 1.2M requests, check for timestamp gaps, identify endpoints.
4. ANALYZE: p50=45ms (fine), p99=890ms (exceeds threshold). /search endpoint contributes 73% of p99 violations. Peak hours 2x worse.
5. CONCLUDE: "p99 latency exceeds the 500ms threshold, concentrated in /search during peak hours. Recommend optimizing /search specifically rather than system-wide caching."

---

## Error Handling

### Error: "No decision context provided"
**Cause**: User provides data without stating what decision it supports ("just analyze this CSV").
**Solution**: Ask "What will you do differently based on this analysis?" If truly exploratory, switch to Exploratory Mode -- apply rigor gates but label all findings as exploratory with no causal claims.

### Error: "Data file cannot be parsed"
**Cause**: Malformed CSV, unexpected encoding, mixed delimiters, or binary file.
**Solution**:
1. Try common encodings: utf-8, latin-1, utf-8-sig
2. Detect delimiter: comma, tab, semicolon, pipe
3. If JSON: validate structure, identify if it's array-of-objects or nested
4. If still failing: ask user for format details. Do not guess.

### Error: "Insufficient data for planned segments"
**Cause**: Metric definitions specify segments (by region, by tier) but some segments have <30 observations.
**Solution**:
1. Report which segments are below minimum
2. Options: merge small segments into "Other", remove segmentation, or accept reduced confidence with disclosure
3. Return to Phase 2 to adjust definitions if needed, documenting the change

### Error: "Metrics changed after seeing data"
**Cause**: Analyst realizes original definitions don't work after loading data (column doesn't exist, wrong granularity).
**Solution**: This is expected and acceptable IF handled properly:
1. Return explicitly to Phase 2
2. Document what changed and why
3. Save updated metric-definitions.md with change log
4. Do NOT silently adjust -- the change must be visible in the artifact trail

---

## Anti-Patterns

### Data-First Analysis
**What it looks like**: Loading the CSV immediately and computing summary statistics before asking what decision the analysis supports.
**Why wrong**: Produces technically correct summaries that answer the wrong question. The analyst finds "interesting patterns" that don't map to the decision-maker's options. Hours of work, zero actionable insight.
**Do instead**: Complete Phase 1 (FRAME) before touching Phase 3 (EXTRACT). If the user pushes back, explain: "I want to make sure we compute the right metrics. What will you do differently based on this analysis?"

### Point Estimates Without Uncertainty
**What it looks like**: "Conversion rate is 4.2%" with no confidence interval, sample size, or context.
**Why wrong**: 4.2% from 100 observations means something very different from 4.2% from 100,000 observations. Without uncertainty bounds, the decision-maker cannot judge reliability. A 4.2% rate with CI [1.1%, 7.3%] is very different from 4.2% with CI [4.0%, 4.4%].
**Do instead**: Always report confidence intervals: "4.2% (95% CI: 3.8-4.6%, N=12,400)".

### Silent Definition Changes
**What it looks like**: Defining "active users" as "logged in last 30 days" in Phase 2, then computing it as "logged in last 7 days" in Phase 4 because the data only has 7-day granularity.
**Why wrong**: This is p-hacking. Changing definitions after seeing data -- even for practical reasons -- invalidates the pre-registration. If the change is benign, it should be documented. If it is not documented, there is no way to audit whether it was benign.
**Do instead**: Return to Phase 2, update the definition, document the reason, then proceed.

### Cherry-Picked Segments
**What it looks like**: "Conversion improved in the 25-34 age group!" without reporting all other age groups or applying multiple testing correction.
**Why wrong**: If you test 10 segments, one will likely show significance by chance (5% false positive rate per test). Reporting only the significant one is misleading.
**Do instead**: Report all segments tested. Apply Bonferroni correction for 6+ comparisons. Label exploratory findings as exploratory.

### Methods-First Communication
**What it looks like**: "I performed a chi-squared test on the contingency table of conversion outcomes stratified by experimental group, yielding a test statistic of 4.12 with 1 degree of freedom..."
**Why wrong**: The decision-maker needs the insight, not the methodology. Leading with methods buries the finding under jargon. The methodology belongs in the appendix for auditors.
**Do instead**: Lead with the insight: "Variant B converts 12% better than A (95% CI: 3-21%). The effect is statistically significant and exceeds our 5% threshold for shipping." Put methodology in the appendix.

---

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../shared-patterns/anti-rationalization-core.md) for universal patterns.

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The user just wants numbers, skip framing" | Numbers without decision context are not actionable. The user may not know they need framing -- that is exactly why the skill enforces it. | Complete Phase 1. Ask "What will you do differently?" |
| "This sample is probably big enough" | "Probably" is not a statistical assessment. Small samples produce wide CIs that cannot support decisions. | Check the actual sample size against the adequacy gate. Report N and CI. |
| "The metric definition is close enough" | Close enough in a numerator or denominator can flip a conclusion. A/B tests have been decided on the wrong metric because "daily active" vs "monthly active" seemed interchangeable. | Use the exact definition from Phase 2. If it must change, return to Phase 2. |
| "This one significant segment is the real finding" | Cherry-picking the significant result from many tests is textbook p-hacking. The one segment may be a false positive. | Report all segments. Apply multiple testing correction. Label as exploratory if warranted. |
| "CIs are too wide, just report the point estimate" | Wide CIs ARE the finding -- they mean the data is insufficient to support a decision. Hiding this misleads the decision-maker. | Report the CI. State that the data is insufficient. Recommend more data. |
| "The analysis is complex, the user won't understand limitations" | Hiding limitations is more misleading than explaining them. Simple language makes limitations accessible. | State limitations in plain language. "We cannot be confident because..." |

---

## Blocker Criteria

STOP and ask the user (do NOT proceed autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| No decision context and user resists framing | Analysis without purpose wastes effort | "Help me understand: what will change based on this analysis?" |
| Data format unclear | Parsing errors corrupt analysis | "What format is this data in? What do the columns represent?" |
| Critical columns have >50% missing values | Analysis on mostly-missing data is unreliable | "Column X is 60% missing. Should we exclude it or is there another data source?" |
| Metric definitions contradict each other | Conflicting definitions produce conflicting results | "Metric A and B use different definitions of 'active user'. Which should we standardize on?" |
| Results are ambiguous (CI spans zero for primary metric) | User needs to know the data is inconclusive | State clearly: "The data does not support a confident decision. Here are options for getting more data." |

### Never Guess On
- Column semantics (what does "status" mean? what values are valid?)
- Population definitions (who is included/excluded from the analysis)
- Business thresholds (what constitutes a "meaningful" change)
- Causal claims (correlation is not causation -- do not imply otherwise)

---

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts to parse a data file before asking the user for format help
- Maximum 2 definition revisions in Phase 2 before flagging scope concern
- Maximum 3 rigor gate remediation attempts before documenting as limitation

### Recovery Protocol
1. **Detection**: Phase cycling (returning to Phase 2 repeatedly), growing artifact count without convergence, same error recurring
2. **Intervention**: Simplify the analysis scope. Drop segments, reduce metrics to the single most important one, narrow time window.
3. **Prevention**: Frame the decision tightly in Phase 1. Fewer options = fewer metrics = faster convergence.

---

## References

For detailed information:
- **Rigor Gates**: [references/rigor-gates.md](references/rigor-gates.md) - Detailed statistical gate documentation with examples
- **Output Templates**: [references/output-templates.md](references/output-templates.md) - Templates for different analysis types (A/B test, trend, distribution, cohort)
- **Anti-Patterns**: [references/anti-patterns.md](references/anti-patterns.md) - Extended anti-pattern catalog with code examples

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
