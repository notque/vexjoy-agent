# Testing Patterns Reference

Detailed patterns for agent testing using subagent dispatch.

## Pattern 1: Dispatch and Capture

Basic pattern for running a single test case:

```
# 1. Dispatch agent with test input
Task(
  prompt="""
  Review this Python function for issues:

  ```python
  def get_user(id):
      return db.execute(f"SELECT * FROM users WHERE id = {id}")
  ```
  """,
  subagent_type="reviewer-security"
)

# 2. Capture output verbatim

# 3. Compare to expected output
Expected: CRITICAL SQL injection finding
Actual: {what agent actually returned}
```

## Pattern 2: Negative Testing

Verify agent handles invalid inputs correctly:

```
# Test with missing required context
Task(
  prompt="""
  Review this code.
  """,
  subagent_type="reviewer-security"
)

# Expected: Agent should request more context or handle gracefully
# NOT: Agent should hallucinate code to review
```

## Pattern 3: Consistency Testing

Verify agent produces consistent outputs:

```
# Run same input 3 times
for i in 1..3:
  Task(prompt=same_input, subagent_type=agent)
  capture output[i]

# Compare outputs
# Structure should be identical
# Key findings should match
# Minor phrasing variation acceptable
```

## Pattern 4: A/B Comparison Testing

Compare agent variants:

```
# Use agent-comparison skill for formal A/B testing
# Or simple side-by-side:

Task(prompt=test_input, subagent_type="agent-v1")
capture output_v1

Task(prompt=test_input, subagent_type="agent-v2")
capture output_v2

# Compare quality, structure, correctness
```

## Pattern 5: Routing Verification

Verify correct agent is selected:

```
# Test routing logic by examining which agent handles request
# Check routing metadata matches behavior

# Example: "Review this Go code" should route to Go expert
# Example: "Check security of this API" should route to security reviewer
```

## Test Scenarios

### Scenario: Testing New Agents

Verify a new agent produces correct outputs for its intended purpose.

| Category | Purpose | Example |
|----------|---------|---------|
| Happy Path | Agent handles ideal input correctly | Valid code for code reviewer |
| Error Cases | Agent handles invalid input gracefully | Malformed input, missing context |
| Edge Cases | Agent handles boundary conditions | Empty input, very large input |
| Output Schema | Agent produces expected structure | Required sections present |

### Scenario: Testing Skill Invocation

- Skill triggers on expected phrases
- Skill produces expected output format
- Skill handles errors appropriately
- Skill follows its documented workflow

### Scenario: Testing Agent Interactions

- Correct agent selected for request
- Agent handoffs work correctly
- No conflicts between parallel agents
- Aggregated results are consistent

### Scenario: Testing Error Handling

- Invalid input handling
- Missing context handling
- Tool failures (simulated)
- Timeout behavior

### Scenario: Testing Output Format

- Required sections present
- Correct markdown formatting
- Expected fields populated
- No placeholder text

## Minimum Test Cases by Agent Type

| Agent Type | Minimum Tests | Required Coverage |
|------------|---------------|-------------------|
| Reviewer agents | 6 | 2 real issues, 2 clean, 1 edge, 1 ambiguous |
| Implementation agents | 5 | 2 typical, 1 complex, 1 minimal, 1 error |
| Analysis agents | 4 | 2 standard, 1 edge, 1 malformed |

## Test Report Template

```markdown
# Agent Test Report: {agent-name}

**Date:** {date}
**Version Tested:** {agent version}
**Tester:** Claude Code (testing-agents-with-subagents skill)

## Summary

| Metric | Result |
|--------|--------|
| Test Cases Run | N |
| Passed | N |
| Failed | N |
| Pass Rate | N% |

## Test Results

### T1: {test name}
- Status: PASS/FAIL
- Input: {input}
- Expected: {expected}
- Actual: {actual}
- Notes: {any observations}

[Continue for all tests]

## Issues Found

1. {Issue description} - Severity: HIGH/MEDIUM/LOW

## Recommendations

1. {Specific fix needed}

## Verdict

READY FOR DEPLOYMENT / NEEDS FIXES / REQUIRES REVIEW
```

## Eval Harness Integration

For agents with YAML-based eval tasks, use the eval harness for automated multi-trial testing:

```bash
# List agents with eval tasks
python evals/harness.py skill-test --list-agents

# Run eval tasks for an agent (default: 3 trials per task)
python evals/harness.py skill-test python-general-engineer

# Run with more trials for higher confidence
python evals/harness.py skill-test python-general-engineer --trials 5

# Output in different formats
python evals/harness.py skill-test python-general-engineer --format json
python evals/harness.py skill-test python-general-engineer --format markdown

# Save results to file
python evals/harness.py skill-test python-general-engineer -o results/agent-test.md
```

**When to use eval harness vs manual testing:**

| Scenario | Approach |
|----------|----------|
| Agent has YAML eval tasks | Use `skill-test` command |
| Agent is new, no eval tasks yet | Manual testing with Task tool |
| Quick iteration during development | Manual testing |
| Pre-deployment validation | Use `skill-test` with `--trials 5` |
| Creating regression tests | Create YAML task, then use harness |

**Creating eval tasks for agents:**

Add task YAML files to `evals/tasks/{category}/` with `execution.agent` set to your agent name. See `evals/task_schema.yaml` for the full schema.
