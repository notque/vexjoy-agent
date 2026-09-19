---
name: data
description: "Data analysis and reference enrichment."
user-invocable: true
argument-hint: "<dataset-or-component-name> [--decompose]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Agent
routing:
  triggers:
    - "analyze data"
    - "data analysis"
    - "CSV"
    - "dataset"
    - "metrics"
    - "trend"
    - "cohort"
    - "A/B test"
    - "statistical"
    - "distribution"
    - "correlation"
    - "KPI"
    - "funnel"
    - "experiment results"
    - "data insights"
    - "statistical analysis"
    - "CSV analysis"
    - "explore dataset"
    - "enrich references"
    - "improve reference depth"
    - "generate references"
    - "add reference files"
    - "reference enrichment"
    - "decompose skill"
    - "extract references"
  not_for: "database schema (agents handle directly), code review (use review)"
  pairs_with:
    - workflow
    - assessment
  complexity: medium
  category: analysis
---

# Data Skill

Two modes. Match the request to a section.

| Signal | Mode |
|--------|------|
| Analyze data, CSV, metrics, A/B test, trend, KPI, funnel, distribution | A. Data Analysis |
| Enrich references, generate references, decompose skill, improve depth | B. Reference Enrichment |

---

## A. Data Analysis

Every analysis starts with the decision it supports, works backward to evidence
required, then touches the data. Analysis without a decision is arithmetic.

### Phase 1: FRAME

Establish what decision this analysis supports.

1. Identify the decision, decision-maker, options, and default action if no analysis is done.
2. If the user cannot articulate a decision, ask: "What will you do differently based on this analysis?" If exploratory, switch to Exploratory Mode (apply rigor gates, make no causal claims).
3. Define evidence requirements: what evidence favors each option, minimum threshold for changing the default, deal-breakers.
4. Save `analysis-frame.md`.

**Gate**: Decision identified, options enumerated, evidence requirements saved.

### Phase 2: DEFINE

Lock metric definitions before loading data. Defining after seeing data enables cherry-picking.

For each metric: name, exact formula (numerator/denominator), population (included/excluded), time window, segments. For comparisons: define groups and verify fairness.

Save `metric-definitions.md`. Definitions are locked once Phase 3 starts. If data reveals a definition is unworkable, return here, update, and document the change.

**Gate**: All metrics defined with formulas and populations.

### Phase 3: EXTRACT

Load data. Assess quality. No interpretation.

1. **Detect tools**: try `import pandas`; fall back to `csv.DictReader` + `statistics`.
2. **Profile**: row count, column types, missing values, date range, distribution stats.
3. **Quality checks** (load `references/rigor-gates.md` Gate 1):

| Check | Minimum | If failed |
|-------|---------|-----------|
| Sample fraction | Report N of M | Warn if <5% coverage |
| Time window | No gaps >10% | Adjust or note limitation |
| Segment size | 30+ per segment | Merge small segments or exclude |
| Missing rate | <20% per critical column | Impute with disclosure or exclude |

4. Save `data-quality-report.md`.

**Gate**: Data loaded, quality assessed, failures documented as limitations.

### Phase 4: ANALYZE

Compute metrics per Phase 2 definitions. Report confidence intervals, not point estimates.

1. **Compute** using exact formulas. Wilson score CI for proportions.
2. **Fairness gate** (comparisons): same time window, same population, confounders documented, survivorship checked (load `references/rigor-gates.md` Gate 2).
3. **Multiple testing** (6+ comparisons): apply Bonferroni (threshold = 0.05/N). Report all segments tested (Gate 3).
4. **Practical significance**: report effect size alongside statistical significance. Base-rate context ("from 2.1% to 2.3%", not "+10% lift") (Gate 4).
5. Save `analysis-results.md`.

**Gate**: All metrics computed. Rigor gates applied.

### Phase 5: CONCLUDE

Lead with insights. Return to the decision.

1. **Headline finding**: one sentence addressing the Phase 1 decision.
2. **Supporting evidence**: primary metric with CI, secondary metrics, segment breakdowns.
3. **Limitations**: wide CIs are the finding, not a formatting problem.
4. **Decision mapping**: does evidence meet threshold? Deal-breakers triggered? Recommended action? Additional data needed?
5. Save `analysis-report.md` (load `references/output-templates.md` for analysis-type templates).

**Gate**: Report saved with headline, limitations, recommendation tied to decision.

### Error Handling (Data Analysis)

| Error | Recovery |
|-------|----------|
| No decision context | Ask "What will you do differently?" Switch to Exploratory if none. |
| Parse failure | Try utf-8, latin-1, utf-8-sig. Detect delimiter. Max 3 attempts. |
| Insufficient segment data (<30) | Merge small segments, remove segmentation, or accept with disclosure. |
| Metrics changed after seeing data | Return to Phase 2, document changes. Max 2 revisions. |
| Wide CI on primary metric | State: "Data does not support a confident decision." Suggest more data. |

---

## B. Reference Enrichment

Enrich agent/skill reference files from Level 0-2 to Level 3+, or decompose bloated body files by extracting domain content into references.

### Phase 0: DECOMPOSE (when `--decompose` or "extract references")

Extract domain-heavy content from a bloated SKILL.md into reference files.

1. Run `python3 scripts/detect-decomposition-targets.py --skill {name}` (or `--agent`).
2. If no extractable blocks, report "nothing to decompose" and stop.
3. Snapshot: `cp {path} /tmp/decomp-before-{name}.md`.
4. For each block: create reference file, remove from body (MOVE, not copy), add loading table entry.
5. Retain in body: frontmatter, overview, phase workflow, loading table, error handling.
6. Validate: `python3 scripts/validate-decomposition.py --before /tmp/decomp-before-{name}.md --after {path} --refs {refs_dir}/`.
7. If fails: restore from snapshot. If passes: `python3 scripts/validate-references.py --skill {name}`.

Load `references/decomposition-prompt.md` for the autonomous decomposition prompts.

**Gate**: Validation passes. Body reduced. All extracted content in references.

### Phase 1: DISCOVER

1. Run `python3 scripts/gap-analyzer.py --agent {name}` (or `--skill`).
2. Read the component's .md and existing references. Map coverage.
3. Compare stated domains against covered domains. Output gap report.

**Gate**: At least one gap identified. If Level 3 already, stop.

### Phase 2: RESEARCH

For each gap: identify version-specific patterns, failure modes with detection commands (`grep -rn "pattern"`), error-fix mappings, project conventions. Dispatch up to 5 parallel research agents per sub-domain.

**Gate**: Each gap has 10+ concrete findings (version numbers, function names, grep patterns). Generic advice does not count.

### Phase 3: COMPILE

Create one reference file per sub-domain (max 500 lines) following `references/reference-file-template.md`. Include: overview, pattern table with version ranges, failure mode table with detection commands, error-fix mappings.

**Do-pairing rule**: every failure mode needs a "Do instead" counterpart. No bare negative blocks.

Validate: `python3 scripts/validate-references.py --agent {name}` and `--check-do-framing`. Both must exit 0. Then run `condense` on each file.

**Gate**: Each file 80-500 lines. Both validations pass.

### Phase 4: VALIDATE

**Tier 1**: `python3 scripts/audit-reference-depth.py --agent {name} --json`. Level must be 3.
**Tier 2**: Apply `references/quality-rubric.md`. For each pattern: detection command present? Would a reviewer using only this file produce Level 3 output?

**Gate**: Both tiers pass. Max 2 loops per gap before flagging for manual review.

### Phase 5: INTEGRATE

1. Add/update loading table in the component body.
2. Validate: `python3 scripts/validate-references.py --agent {name}` and `python3 -m pytest scripts/tests/test_reference_loading.py -k {name} -v`.
3. Stage changes.

**Gate**: Validation passes. Report level change (was N, now M) and new file list.

### Error Handling (Reference Enrichment)

| Error | Recovery |
|-------|----------|
| Gap analyzer fails | Check both `agents/` and `skills/` directories. |
| Phase 2 gate fails (<10 findings) | Domain may be narrow. Flag for manual enrichment. |
| Phase 4 still below Level 3 | Files too generic. Target Phase 2 at weakest section. |
| Decomposition validation fails | Restore from snapshot. Check for partial extractions. |

---

## Deep References

All references are >100 lines of domain-specific content. Load as directed by sections above.

| Signal | Reference | Lines |
|--------|-----------|-------|
| Phase 3-4: statistical gates, sample adequacy, fairness | `references/rigor-gates.md` | 378 |
| Phase 5: report templates (A/B, trend, distribution, cohort) | `references/output-templates.md` | 489 |
| Failure mode recognition (p-hacking, survivorship, Simpson's) | `references/preferred-patterns.md` | 240 |
| Classifying reference depth Level 0-3 | `references/quality-rubric.md` | 173 |
| Writing new reference files | `references/reference-file-template.md` | 166 |
| Running headless decomposition | `references/decomposition-prompt.md` | 205 |
| Running headless enrichment | `references/enrichment-prompt.md` | 117 |
