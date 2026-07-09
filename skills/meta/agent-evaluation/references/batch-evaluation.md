# Batch Evaluation Procedures

Use `score-component.py` once for the collection. Do not duplicate its checks with shell loops or normalize its raw 90-point maximum to 100.

## Phase 1: Structural Precheck

```bash
python3 scripts/score-component.py --all-agents --all-skills --json > /tmp/component-scores.json
```

The JSON document contains `results`, each with `total`, `max_total`, `grade`, and `checks`. Every check uses `earned` and `max` keys.

**Gate**: The command produced parseable JSON. Exit 1 means one or more components earned C or below; it does not mean the JSON is unusable. Exit 2 is an invocation error and blocks aggregation.

## Phase 2: Aggregate

Calculate:

- Agent and skill counts
- Grade distribution
- Mean and median percentage, computed as `total / max_total * 100`
- Frequency of failed or partial check names
- Secret findings when `--check-secrets` was requested

Compare components by percentage if maximums ever differ. Preserve raw totals in the report.

## Phase 3: Qualitative Sampling

Use the user's requested scope. For a full collection audit, inspect low scorers plus a representative sample from each grade. Check accuracy, usefulness, behavioral gaps, and unnecessary bulk. Cite file and line evidence. Do not add these judgments to the structural score.

## Phase 4: Report

Use `report-templates.md`. Include:

1. Raw total, maximum, percentage, and grade per component
2. Grade distribution and recurring deterministic failures
3. Qualitative findings in a separate section
4. Specific recommendations tied to evidence

The scorer's percentage grade bands are A 90-100, B 75-89, C 60-74, D 40-59, and F 0-39.
