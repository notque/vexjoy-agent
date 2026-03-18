# Evaluation Report Templates

Standard templates for agent/skill evaluation reports.

## Single Item Report Template

```markdown
# Evaluation Report: {name}

**Type**: Agent | Skill
**Evaluated**: {YYYY-MM-DD HH:MM}
**Evaluator**: agent-evaluation skill v1.0.0
**Overall Score**: {score}/100 ({grade})

---

## Executive Summary

{One paragraph summary of quality and key findings}

---

## Structural Validation

| Component | Status | Score | Notes |
|-----------|--------|-------|-------|
| YAML front matter | {PASS/FAIL} | {X}/10 | {details} |
| Operator Context | {PASS/FAIL} | {X}/20 | {details} |
| Examples | {PASS/FAIL/N/A} | {X}/10 | {details} |
| Error Handling | {PASS/FAIL} | {X}/10 | {details} |
| Reference Files | {PASS/FAIL/N/A} | {X}/10 | {details} |
| Validation Script | {PASS/FAIL/N/A} | {X}/10 | {details} |

**Structural Score**: {X}/{max}

---

## Content Depth Analysis

| Metric | Value |
|--------|-------|
| Main file lines | {X} |
| Reference lines | {X} |
| Total lines | {X} |
| Depth grade | {EXCELLENT/GOOD/ADEQUATE/THIN/INSUFFICIENT} |

**Depth Score**: {X}/30

---

## Issues Found

### HIGH Priority
{numbered list of critical issues}

### MEDIUM Priority
{numbered list of moderate issues}

### LOW Priority
{numbered list of minor issues}

---

## Recommendations

1. **{Action}**: {Specific guidance}
2. **{Action}**: {Specific guidance}
3. **{Action}**: {Specific guidance}

---

## Comparison to Collection

| Metric | This Item | Collection Average |
|--------|-----------|-------------------|
| Overall Score | {X}/100 | {X}/100 |
| Structural Score | {X}% | {X}% |
| Depth Score | {X}/30 | {X}/30 |
| Percentile | {X}th | - |

---

## Raw Test Output

<details>
<summary>Click to expand test output</summary>

```
{actual command output from evaluation}
```

</details>
```

## Collection Summary Template

```markdown
# Collection Evaluation Summary

**Date**: {YYYY-MM-DD}
**Evaluator**: agent-evaluation skill v1.0.0

---

## Overview

| Metric | Value |
|--------|-------|
| Total Agents | {X} |
| Total Skills | {X} |
| Average Score | {X}/100 |
| Operator Model Coverage | {X}% |

---

## Score Distribution

### Agents

| Grade | Count | Percentage |
|-------|-------|------------|
| A (90-100) | {X} | {X}% |
| B (80-89) | {X} | {X}% |
| C (70-79) | {X} | {X}% |
| D (60-69) | {X} | {X}% |
| F (<60) | {X} | {X}% |

### Skills

| Grade | Count | Percentage |
|-------|-------|------------|
| A (90-100) | {X} | {X}% |
| B (80-89) | {X} | {X}% |
| C (70-79) | {X} | {X}% |
| D (60-69) | {X} | {X}% |
| F (<60) | {X} | {X}% |

---

## Top Performers

### Agents
1. {name}: {score}/100
2. {name}: {score}/100
3. {name}: {score}/100

### Skills
1. {name}: {score}/100
2. {name}: {score}/100
3. {name}: {score}/100

---

## Areas of Excellence

### Structural Quality
- {X}% have complete Operator Context sections
- {X}% have comprehensive error handling
- {X}% have validation scripts (skills)

### Content Depth
- {X}% exceed 1500 lines (EXCELLENT depth)
- {X}% have substantive reference files
- Average total lines: {X}

### Best Practices Observed
1. {observed_pattern_1}
2. {observed_pattern_2}
3. {observed_pattern_3}

---

## Needs Improvement

### Agents
1. {name}: {score}/100 - {primary issue}
2. {name}: {score}/100 - {primary issue}

### Skills
1. {name}: {score}/100 - {primary issue}
2. {name}: {score}/100 - {primary issue}

---

## Common Issues

| Issue | Occurrences | Affected Items |
|-------|-------------|----------------|
| {issue} | {X} | {list} |
| {issue} | {X} | {list} |
| {issue} | {X} | {list} |

---

## Recommendations

### Immediate Actions (HIGH priority)
1. {action}
2. {action}

### Short-term Improvements (MEDIUM priority)
1. {action}
2. {action}

### Long-term Enhancements (LOW priority)
1. {action}
2. {action}

---

## Trend Analysis

{If historical data available, show score trends over time}

---

## Appendix: Full Scores

### Agents

| Name | Structural | Depth | Total | Grade |
|------|------------|-------|-------|-------|
| {name} | {X}/70 | {X}/30 | {X}/100 | {grade} |
| ... | ... | ... | ... | ... |

### Skills

| Name | Structural | Depth | Total | Grade |
|------|------------|-------|-------|-------|
| {name} | {X}/70 | {X}/30 | {X}/100 | {grade} |
| ... | ... | ... | ... | ... |
```

## Quick Check Template

For rapid evaluations:

```markdown
# Quick Check: {name}

**Score**: {X}/100 | **Grade**: {grade}

## Pass/Fail
- [x] YAML front matter
- [x] Operator Context
- [ ] Error Handling (MISSING)
- [x] Content depth

## Top Issue
{Single most important finding}

## Quick Fix
{Single most impactful action}
```

## Comparison Template

For comparing two items:

```markdown
# Comparison: {name1} vs {name2}

| Aspect | {name1} | {name2} | Winner |
|--------|---------|---------|--------|
| Overall Score | {X}/100 | {X}/100 | {name} |
| Structural | {X}/70 | {X}/70 | {name} |
| Depth | {X}/30 | {X}/30 | {name} |
| Operator Model | {Complete/Partial} | {Complete/Partial} | {name} |

## Key Differences

1. {difference}
2. {difference}

## Recommendation

{Which to use and when}
```
