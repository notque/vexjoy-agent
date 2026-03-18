# Agent A/B Comparison Report Template

Use this template when generating comparison reports in Phase 4.

## Template

```markdown
# Agent A/B Comparison Report

**Test Date**: {date}
**Full Agent**: {name} ({lines} lines, ~{tokens} prompt tokens)
**Compact Agent**: {name} ({lines} lines, ~{tokens} prompt tokens)
**Prompt Size Reduction**: {percentage}%

---

## Executive Summary

| Metric | Full Agent | Compact Agent | Winner |
|--------|------------|---------------|--------|
| Simple task pass rate | X% | X% | |
| Complex task pass rate | X% | X% | |
| Avg quality score | X/25 | X/25 | |
| Total session tokens | Xk | Xk | |
| Effective cost | Xk | Xk | |
| Bug count | X | X | |

**Verdict**: {1-2 sentence summary of which agent is better and why}

---

## Simple Task Results

### Task: {name}

| Metric | Full | Compact |
|--------|------|---------|
| Tests pass | X/X | X/X |
| Quality score | X/25 | X/25 |
| Session tokens | Xk | Xk |

**Observations**: {brief notes on any differences}

[Repeat for each simple task]

---

## Complex Task Results

### Task: {name}

| Metric | Full | Compact |
|--------|------|---------|
| Tests pass | X/X | X/X |
| Race conditions | X | X |
| Quality score | X/25 | X/25 |
| Session tokens | Xk | Xk |
| Retry cycles | X | X |

**Key Differences**:
- {Observation 1: specific quality difference}
- {Observation 2: specific bug or pattern missed}

**Bugs Found in Full Agent**:
1. {Bug description} - Impact: {impact}

**Bugs Found in Compact Agent**:
1. {Bug description} - Impact: {impact}

[Repeat for each complex task]

---

## Token Economics Analysis

Agent prompts are a one-time cost per session. The real cost comes from reasoning, code generation, debugging, and retries on every turn.

### Per-Task Token Breakdown

| Task | Full Agent | Compact Agent | Difference |
|------|------------|---------------|------------|
| {task 1} | Xk | Xk | {+/-}X% |
| {task 2} | Xk | Xk | {+/-}X% |
| **Total** | **Xk** | **Xk** | **{+/-}X%** |

### Effective Cost (with bug penalty)

| Agent | Raw Tokens | Bug Count | Penalty | Effective Cost |
|-------|-----------|-----------|---------|----------------|
| Full | Xk | X | X% | Xk |
| Compact | Xk | X | X% | Xk |

### Economics Pattern

**Large agent, low churn**:
- High initial cost (~X tokens)
- Low per-turn reasoning (patterns already present)
- Fewer retries (gets it right initially)
- Less debugging (examples prevent common errors)

**Small agent, high churn**:
- Low initial cost (~X tokens)
- High per-turn reasoning (must derive patterns)
- More retries (trial and error)
- More debugging (hits edge cases)

---

## Quality Comparison

### Full Agent Score Card

| Criterion | Task 1 | Task 2 | Task 3 | Avg |
|-----------|--------|--------|--------|-----|
| Correctness | X/5 | X/5 | X/5 | X |
| Error Handling | X/5 | X/5 | X/5 | X |
| Idioms | X/5 | X/5 | X/5 | X |
| Documentation | X/5 | X/5 | X/5 | X |
| Testing | X/5 | X/5 | X/5 | X |
| **Total** | X/25 | X/25 | X/25 | X |

### Compact Agent Score Card

| Criterion | Task 1 | Task 2 | Task 3 | Avg |
|-----------|--------|--------|--------|-----|
| Correctness | X/5 | X/5 | X/5 | X |
| Error Handling | X/5 | X/5 | X/5 | X |
| Idioms | X/5 | X/5 | X/5 | X |
| Documentation | X/5 | X/5 | X/5 | X |
| Testing | X/5 | X/5 | X/5 | X |
| **Total** | X/25 | X/25 | X/25 | X |

---

## Conclusions

1. {Primary conclusion about which agent is better overall}
2. {Key finding about token economics}
3. {Insight about quality vs efficiency tradeoff}

---

## Recommendations

- **Use full agent when**: {scenario where full agent is better choice}
- **Use compact agent when**: {scenario where compact agent is acceptable}
- **Future testing**: {suggestions for additional benchmarks}

---

## Raw Data

### Directory Structure
{tree output of benchmark directory}

### Test Execution Logs
{abbreviated test output for each agent/task combination}
```
