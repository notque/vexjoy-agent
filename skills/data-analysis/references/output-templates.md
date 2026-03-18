# Output Templates

Templates for common analysis types. Each template specifies the structure for `analysis-report.md` tailored to the analysis pattern.

---

## A/B Test Evaluation

Use when comparing two (or more) experimental variants with a defined control.

```markdown
# A/B Test Analysis Report

## Headline
[One sentence: does the test variant win, lose, or is the result inconclusive?]

## Test Design
- **Hypothesis**: [What was being tested]
- **Control (A)**: [Description]
- **Variant (B)**: [Description]
- **Primary metric**: [Metric name and definition]
- **Sample**: Control N=[X], Variant N=[Y]
- **Test duration**: [Start - End]
- **Minimum detectable effect**: [MDE used in test design]

## Results

### Primary Metric
| Group | Value | 95% CI | N |
|-------|-------|--------|---|
| Control (A) | [value] | [lower - upper] | [N] |
| Variant (B) | [value] | [lower - upper] | [N] |
| **Difference** | **[value]** | **[lower - upper]** | |

- Statistical significance: [p-value]
- Effect size: [Cohen's d or relative change]
- Practical significance: [Above/Below minimum actionable threshold]

### Secondary Metrics (if applicable)
| Metric | Control | Variant | Difference | 95% CI | Significant? |
|--------|---------|---------|------------|--------|-------------|
| [name] | [value] | [value] | [diff] | [CI] | [Yes/No] |

### Segment Breakdown (if applicable)
| Segment | Control | Variant | Difference | N (per group) |
|---------|---------|---------|------------|---------------|
| [name] | [value] | [value] | [diff] | [N] |

*Note: [N] segments tested. [Correction method] applied. [N] significant after correction.*

## Rigor Checks
- Sample adequacy: [PASS/FAIL]
- Group balance: [Ratio and assessment]
- Time window: [Complete/Gaps noted]
- Multiple testing: [Method if applicable]

## Limitations
- [Limitation 1]
- [Limitation 2]

## Recommendation
[Ship / Do not ship / Extend test -- with rationale tied to evidence thresholds]

## What Would Increase Confidence
- [Suggestion 1]
- [Suggestion 2]
```

---

## Trend Analysis

Use when examining how a metric changes over time.

```markdown
# Trend Analysis Report

## Headline
[One sentence: what is the trend and what does it mean for the decision?]

## Trend Summary
- **Metric**: [Name and definition]
- **Period**: [Start - End]
- **Granularity**: [Daily / Weekly / Monthly]
- **Overall direction**: [Increasing / Decreasing / Flat / Volatile]
- **Rate of change**: [Average period-over-period change with CI]

## Trend Data

### Overall
| Period | Value | Change | Change % |
|--------|-------|--------|----------|
| [period] | [value] | [abs change] | [pct change] |

### By Segment (if applicable)
| Segment | Start Value | End Value | Overall Change | Trend |
|---------|-------------|-----------|----------------|-------|
| [name] | [value] | [value] | [change] | [direction] |

## Pattern Detection
- **Seasonality**: [Detected / Not detected -- pattern description]
- **Structural breaks**: [Any abrupt changes in trend? When?]
- **Outliers**: [Periods that deviate significantly from trend]

## Drivers
[What is driving the trend? Segment decomposition showing which segments contribute most to the overall change.]

| Segment | Contribution to Overall Change |
|---------|-------------------------------|
| [name] | [pct of total change] |

## Limitations
- [Limitation 1: e.g., "Seasonality not fully controlled -- only 1 year of data"]
- [Limitation 2: e.g., "External factors (pricing change in March) may confound trend"]

## Recommendation
[Action tied to the decision frame from Phase 1]

## What Would Increase Confidence
- [More time periods to control for seasonality]
- [Additional segmentation to isolate drivers]
```

---

## Distribution Profiling

Use when understanding the shape and characteristics of a metric's distribution.

```markdown
# Distribution Analysis Report

## Headline
[One sentence: what does the distribution tell us about the decision?]

## Distribution Summary
- **Metric**: [Name and definition]
- **Sample**: N=[count]
- **Period**: [Time window]

## Key Statistics
| Statistic | Value |
|-----------|-------|
| Mean | [value] |
| Median | [value] |
| Std Dev | [value] |
| Min | [value] |
| Max | [value] |
| p25 | [value] |
| p75 | [value] |
| p90 | [value] |
| p95 | [value] |
| p99 | [value] |
| Skewness | [value -- interpretation] |

## Distribution Shape
- **Type**: [Normal / Right-skewed / Bimodal / Long-tailed / Uniform]
- **Key characteristic**: [What is notable about this distribution?]
- **Mean vs Median gap**: [If large, indicates skew -- report which is more appropriate]

## Percentile Analysis
[For performance/latency data, focus on tail behavior]

| Percentile | Value | Within Threshold? |
|------------|-------|-------------------|
| p50 | [value] | [Yes/No] |
| p90 | [value] | [Yes/No] |
| p95 | [value] | [Yes/No] |
| p99 | [value] | [Yes/No] |

## Segments (if applicable)
| Segment | Mean | Median | p99 | N |
|---------|------|--------|-----|---|
| [name] | [value] | [value] | [value] | [count] |

## Outlier Analysis
- **Outlier definition**: [Method: >3 std dev / IQR / domain-specific]
- **Count**: [N outliers of M total ([pct]%)]
- **Impact on mean**: [Mean with outliers vs without]
- **Investigation**: [What outliers represent -- errors? genuine extremes?]

## Limitations
- [Limitation 1]
- [Limitation 2]

## Recommendation
[Action tied to the decision frame]
```

---

## Cohort Comparison

Use when comparing groups defined by a shared characteristic (sign-up date, plan tier, geography).

```markdown
# Cohort Comparison Report

## Headline
[One sentence: how do cohorts differ and what does it mean?]

## Cohort Definitions
| Cohort | Definition | N |
|--------|-----------|---|
| [name] | [selection criteria] | [count] |

## Comparison Fairness Assessment
- Same time window: [Yes/No -- details]
- Same population base: [Yes/No -- details]
- Known confounders: [List]
- Survivorship bias: [Risk level and mitigation]

## Results

### Primary Metric
| Cohort | Value | 95% CI | N |
|--------|-------|--------|---|
| [name] | [value] | [lower - upper] | [count] |

### Pairwise Comparisons
| Comparison | Difference | 95% CI | Significant? | Practically Significant? |
|-----------|-----------|--------|-------------|------------------------|
| A vs B | [diff] | [CI] | [Yes/No] | [Yes/No -- vs threshold] |

*[N] pairwise comparisons performed. [Correction method] applied.*

## Cohort Behavior Over Time (if temporal)
| Period | Cohort A | Cohort B | Gap |
|--------|----------|----------|-----|
| [period] | [value] | [value] | [diff] |

[Is the gap widening, narrowing, or stable?]

## Limitations
- [Limitation 1]
- [Limitation 2]

## Recommendation
[Action tied to the decision frame]
```

---

## Funnel Analysis

Use when measuring drop-off through a sequence of steps.

```markdown
# Funnel Analysis Report

## Headline
[One sentence: where is the biggest drop-off and what does it mean?]

## Funnel Definition
- **Entry**: [First step and its definition]
- **Exit**: [Last step / conversion event]
- **Time window**: [Period analyzed]
- **Population**: [Who is included]

## Funnel Steps
| Step | Count | Rate from Previous | Rate from Entry | Drop-off |
|------|-------|-------------------|-----------------|----------|
| [Step 1] | [N] | -- | 100% | -- |
| [Step 2] | [N] | [pct] | [pct] | [pct dropped] |
| [Step 3] | [N] | [pct] | [pct] | [pct dropped] |
| [Final] | [N] | [pct] | [pct] | [pct dropped] |

**Overall conversion**: [Entry to Final pct]

## Biggest Drop-off
- **Step**: [Where the largest drop occurs]
- **Drop rate**: [Percentage]
- **Volume**: [Absolute number of users lost]
- **Context**: [Why this might be happening -- if data supports it]

## By Segment (if applicable)
| Segment | Entry | Final | Conversion | vs Overall |
|---------|-------|-------|------------|-----------|
| [name] | [N] | [N] | [pct] | [+/- vs overall] |

## Limitations
- [Limitation 1: e.g., "Cannot distinguish intentional exits from errors"]
- [Limitation 2]

## Recommendation
[Where to focus optimization efforts, tied to decision frame]
```

---

## Anomaly Investigation

Use when investigating unexpected spikes, drops, or deviations in metrics.

```markdown
# Anomaly Investigation Report

## Headline
[One sentence: what happened, when, and what caused it?]

## Anomaly Summary
- **Metric**: [Name]
- **Normal range**: [Expected value or range]
- **Anomaly value**: [Observed value]
- **Deviation**: [How far from normal -- Z-score or percentage]
- **When**: [Date/time range]
- **Duration**: [How long the anomaly lasted]

## Timeline
| Time | Value | Status |
|------|-------|--------|
| [before] | [normal value] | Normal |
| [onset] | [value] | Anomaly begins |
| [peak] | [value] | Peak deviation |
| [recovery] | [value] | Returns to normal |

## Root Cause Analysis
### Correlated Events
| Event | Timing | Correlation |
|-------|--------|-------------|
| [deployment/change/incident] | [time] | [Likely/Possible/Unlikely] |

### Segment Isolation
| Segment | Affected? | Severity |
|---------|-----------|----------|
| [name] | [Yes/No] | [Magnitude] |

[Which segments are affected narrows the possible causes.]

## Impact Assessment
- **Duration**: [How long]
- **Magnitude**: [Quantified impact -- revenue lost, users affected, etc.]
- **Scope**: [How widespread -- single endpoint vs system-wide]

## Limitations
- [Limitation 1]

## Recommendation
[Action to prevent recurrence, tied to decision frame]
```
