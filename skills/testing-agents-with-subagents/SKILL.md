---
name: testing-agents-with-subagents
description: "Test agents via subagents: known inputs, captured outputs, verification."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "test agents"
    - "agent testing"
    - "subagent testing"
    - "validate agent"
    - "agent test harness"
  category: testing
  pairs_with:
    - agent-evaluation
    - subagent-driven-development
---

# Testing Agents With Subagents

## Overview

Applies TDD methodology to agent development -- RED (observe failures), GREEN (fix agent definition), REFACTOR (edge cases and robustness) -- with subagent dispatch as the execution mechanism.

Test what the agent DOES, not what the prompt SAYS. Evidence-based verification only: capture exact outputs from subagent dispatch. Always test via the Task tool rather than reading prompts.

Minimum test counts by agent type:

| Agent Type | Min Tests | Required Coverage |
|------------|-----------|-------------------|
| Reviewer | 6 | 2 real issues, 2 clean, 1 edge, 1 ambiguous |
| Implementation | 5 | 2 typical, 1 complex, 1 minimal, 1 error |
| Analysis | 4 | 2 standard, 1 edge, 1 malformed |
| Routing/orchestration | 4 | 2 correct route, 1 ambiguous, 1 invalid |

No agent is simple enough to skip testing -- get human confirmation before exempting any agent. Each test runs in a fresh subagent to avoid context pollution. After any fix, re-run ALL test cases. One fix at a time.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| example-driven tasks, errors | `examples-and-errors.md` | Loads detailed guidance from `examples-and-errors.md`. |
| implementation patterns | `testing-patterns.md` | Loads detailed guidance from `testing-patterns.md`. |

## Instructions

### Phase 0: PREPARE -- Understand the Agent

**Goal**: Read the agent definition and understand what it claims to do before writing tests.

**Step 1: Read the agent file**

```bash
# Read agent definition
cat agents/{agent-name}.md

# Read any referenced skills
cat skills/{skill-name}/SKILL.md
```

**Step 2: Identify testable claims** -- Extract concrete behaviors: inputs accepted, output structure, routing triggers, error conditions, skills invoked.

**Step 3: Determine minimum test count** -- Use the table above.

No gate -- preparation only. Move to Phase 1.

### Phase 1: RED -- Observe Current Behavior

**Goal**: Run agent with test inputs and document exact current behavior before any changes.

**Step 1: Define test plan** -- Write to a file before executing. See `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md` for template.

**Step 2: Dispatch subagent with test inputs** -- Use Task tool (see dispatch template in `references/examples-and-errors.md`). Each test in a fresh subagent to prevent context pollution.

**Step 3: Capture results verbatim** -- Document exact agent outputs. See template in `references/examples-and-errors.md`.

**Step 4: Identify failure patterns** -- Which categories fail? Structural (missing sections) or behavioral (wrong answers)? Correlate with input characteristics.

**Gate**: All test cases executed. Exact outputs captured verbatim. Failures documented with specific issues. Proceed only when gate passes.

### Phase 2: GREEN -- Fix Agent Definition

**Goal**: Update agent definition until all test cases pass. One fix at a time.

**Step 1: Prioritize failures** -- Triage by severity (Critical/High/Medium/Low). See `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`.

**Step 2: Diagnose root cause** -- Map failure type to fix approach. See `references/examples-and-errors.md`.

**Step 3: Make one fix at a time** -- Change one thing. Re-run ALL test cases. Document which tests now pass/fail. One fix at a time -- you cannot determine which change was effective.

**Step 4: Iterate until green** -- Repeat Step 3 until all pass. If a fix causes regression, revert and try differently. Track iterations using Fix Log template in `references/examples-and-errors.md`.

**Gate**: All test cases pass. No regressions. Can explain what each fix changed and why. Proceed only when gate passes.

### Phase 3: REFACTOR -- Edge Cases and Robustness

**Goal**: Verify agent handles boundary conditions and produces consistent outputs.

**Step 1: Add edge case tests** -- See Edge Case Categories in `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md` (Empty / Large / Unusual / Ambiguous inputs).

**Step 2: Run consistency tests** -- Same input 3 times. Outputs must have same structure, same key findings. Acceptable variation in phrasing only. If inconsistent: add more explicit instructions, re-test.

**Step 3: Run regression suite** -- Re-run ALL test cases (original + edge cases).

**Step 4: Document final test report** -- See template in `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`.

**Gate**: Edge cases handled. Consistency verified. Full suite green. Test report documented. Fix is complete.

---

## Error Handling

See `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md` for: agent-type-not-found, inconsistent-outputs, subagent-timeout, agent-asks-questions.

---

## References

### Integration
- `agent-comparison`: A/B test agent variants
- `agent-evaluation`: Structural quality checks
- `test-driven-development`: TDD principles applied to agents

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/testing-patterns.md`: Dispatch patterns, test scenarios, eval harness integration
- `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`: Worked examples and error handling
