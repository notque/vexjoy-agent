---
name: data
description: "Analyze datasets, metrics, experiments, funnels, cohorts, trends, and distributions with explicit estimands, provenance, and decision thresholds. Not for maintaining skill reference files."
user-invocable: true
argument-hint: "<dataset-or-question>"
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Agent]
routing:
  triggers:
    - "analyze data"
    - "CSV analysis"
    - "experiment results"
    - "A/B test"
    - "trend"
    - "cohort"
    - "funnel"
    - "distribution"
    - "correlation"
    - "KPI"
  not_for: "database schema work, code review, or skill/reference maintenance"
  pairs_with: [workflow, assessment]
  complexity: medium
  category: analysis
---

# Data analysis

Start from the decision or exploratory question, not a preferred result. Preserve
the source data and perform transformations in reproducible code. Never silently
change a metric, population, time window, exclusion, missing-data policy, or test
after observing the answer.

## Contract

Before analysis, record the smallest useful frame:

- decision and default action, or an explicit `exploratory` label;
- estimand: outcome, population, unit of analysis, time window, and contrast;
- metric formulas and inclusion/exclusion rules;
- threshold at which evidence would change the action;
- available data, provenance, and known collection changes.

If the user only wants descriptive exploration, proceed without inventing a
decision. Separate observations, hypotheses, and causal claims in the output.

## Inspect before computing

Profile schema, row count, entity keys, duplicates, missingness, time coverage,
units, impossible values, and join cardinality. Verify that aggregation does not
mix grains. For comparisons, verify exposure assignment, population definitions,
overlapping time windows, sample-ratio anomalies, censoring, attrition, and known
confounders. A failed quality check changes the analysis or becomes an explicit
limitation; it is not a footnote added after a confident conclusion.

Treat missingness according to its mechanism and decision impact, not a universal
percentage cutoff. Do not merge small segments merely to reach an arbitrary
sample size. Report the observed `n`, uncertainty, and why the chosen method is
valid for that design.

## Compute

Retain the code used for every reported statistic. Keep the analysis unit intact:
paired data stays paired, repeated observations are not independent samples, and
ratio numerators and denominators must use the declared grain. Report baseline
levels and absolute changes whenever reporting relative changes.

For experiments, preserve the predeclared primary outcome and analysis unit.
Check assignment integrity before treatment effects. Account for all tested
hypotheses using the correction or error-rate policy appropriate to the analysis
plan; label unplanned subgroup searches exploratory. Statistical significance
does not replace effect size, uncertainty, or the user's practical threshold.

Do not infer causality from observational association without an identification
strategy and its assumptions. If those assumptions are not defensible, state the
association and plausible alternatives.

## Stress-test the result

Run only checks capable of changing the decision: alternative defensible
definitions, missing-data bounds, influential points, segment reversals,
seasonality, selection effects, and sensitivity to model assumptions. Do not
search specifications until one becomes favorable. When an analysis definition
must change, preserve both versions and explain why.

## Deliver

Lead with the result in decision terms. Include:

1. estimate, uncertainty interval, sample size, and units;
2. the baseline and absolute effect where a relative effect is shown;
3. whether the prespecified action threshold was crossed;
4. data-quality and design limitations that could reverse the conclusion;
5. reproducible inputs, definitions, and transformations;
6. the next measurement most likely to reduce decision uncertainty.

An inconclusive result is a result. Do not turn a wide interval, failed integrity
check, or underidentified design into a directional recommendation.

Write files only when the user requests artifacts or the surrounding workflow
already owns an output path. Otherwise return the analysis inline. Never stage or
commit results merely because the analysis completed.
