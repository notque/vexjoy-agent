# Evaluation Report Templates

Use the scorer's raw `total/max_total` and grade. Do not normalize to 100 or add qualitative points.

## Single Item

````markdown
# Evaluation Report: {name}

**Type**: Agent | Skill
**Evaluated**: {YYYY-MM-DD HH:MM}
**Structural Score**: {total}/{max_total} ({grade}; {percentage}%)

## Structural Precheck

| Check | Status | Earned | Max | Detail |
|---|---|---:|---:|---|
| {checks[*].name} | {checks[*].status} | {checks[*].earned} | {checks[*].max} | {checks[*].detail} |

**Secret penalty**: {secret_penalty}

## Qualitative Findings

### High
- **{file}:{line}**: {finding and impact}

### Medium
- **{file}:{line}**: {finding and impact}

### Low
- **{file}:{line}**: {finding and impact}

## Recommendations

1. **{Action}**: {specific guidance}

## Raw Output

```json
{score-component.py JSON result}
```
````

## Collection Summary

```markdown
# Collection Evaluation Summary

**Date**: {YYYY-MM-DD}
**Agents**: {count}
**Skills**: {count}
**Average structural percentage**: {percentage}%

## Grade Distribution

| Grade | Agents | Skills |
|---|---:|---:|
| A (90-100%) | {count} | {count} |
| B (75-89%) | {count} | {count} |
| C (60-74%) | {count} | {count} |
| D (40-59%) | {count} | {count} |
| F (0-39%) | {count} | {count} |

## Results

| Component | Type | Total | Max | Percentage | Grade | Primary issue |
|---|---|---:|---:|---:|:---:|---|
| {file} | {type} | {total} | {max_total} | {percentage}% | {grade} | {issue} |

## Common Qualitative Findings

| Finding | Count | Affected components |
|---|---:|---|
| {finding} | {count} | {files} |
```

## Quick Check

```markdown
# Quick Check: {name}

**Structural Score**: {total}/{max_total} ({grade}; {percentage}%)

| Check | Status | Earned/Max | Detail |
|---|---|---:|---|
| {name} | {status} | {earned}/{max} | {detail} |

**Top qualitative issue**: {evidence-backed issue or "None found"}
```

## Comparison

```markdown
# Comparison: {name1} vs {name2}

| Aspect | {name1} | {name2} |
|---|---:|---:|
| Structural score | {total}/{max_total} | {total}/{max_total} |
| Percentage | {percentage}% | {percentage}% |
| Grade | {grade} | {grade} |
| High qualitative findings | {count} | {count} |

## Recommendation

{Which component better fits the stated use and why.}
```
