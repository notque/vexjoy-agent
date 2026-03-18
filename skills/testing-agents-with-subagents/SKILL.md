---
name: testing-agents-with-subagents
description: |
  RED-GREEN-REFACTOR testing for agents: dispatch subagents with known inputs,
  capture verbatim outputs, verify against expectations. Use when creating,
  modifying, or validating agents and skills. Use for "test agent", "validate
  agent", "verify agent works", or pre-deployment checks. Do NOT use for
  feature requests, simple prompt edits without behavioral impact, or agents
  with no structured output to verify.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
---

# Testing Agents With Subagents

## Operator Context

This skill operates as an operator for agent testing workflows, configuring Claude's behavior for systematic agent validation. It applies **TDD methodology to agent development** — RED (observe failures), GREEN (fix agent definition), REFACTOR (edge cases and robustness) — with subagent dispatch as the execution mechanism.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before testing
- **Over-Engineering Prevention**: Only test what's directly needed. No elaborate test harnesses or infrastructure. Keep test cases focused and minimal.
- **Verbatim Output Capture**: Document exact agent outputs. NEVER summarize or paraphrase.
- **Isolated Execution**: Each test runs in a fresh subagent to avoid context pollution
- **Evidence-Based Claims**: Every claim about agent behavior MUST be backed by actual test execution
- **No Self-Exemption**: You cannot decide an agent doesn't need testing. Human partner must confirm exemptions.

### Default Behaviors (ON unless disabled)
- **Multi-Case Testing**: Run at least 3 test cases per agent (success, failure, edge case)
- **Output Schema Validation**: Verify agent output matches expected structure and required sections
- **Consistency Testing**: Run same input 2+ times to verify deterministic behavior
- **Regression Testing**: After fixes, re-run ALL previous test cases before declaring green
- **Temporary File Cleanup**: Remove test files and artifacts at completion. Keep only files needed for documentation.
- **Document Findings**: Log all observations, hypotheses, and test results in structured format

### Optional Behaviors (OFF unless enabled)
- **A/B Testing**: Compare agent variants using agent-comparison skill
- **Performance Benchmarking**: Measure response time and token usage
- **Stress Testing**: Test with large inputs, many iterations, concurrent requests
- **Eval Harness Integration**: Use `evals/harness.py skill-test` for YAML-based automated testing

## What This Skill CAN Do
- Systematically validate agents through RED-GREEN-REFACTOR test cycles
- Dispatch subagents with controlled inputs and capture verbatim outputs
- Distinguish between output structure issues and behavioral correctness issues
- Verify fixes don't introduce regressions across the full test suite
- Test routing logic, skill invocation, and multi-agent workflows

## What This Skill CANNOT Do
- Deploy agents without completing all three test phases
- Substitute reading agent prompts for executing actual test runs
- Make claims about agent behavior without evidence from subagent dispatch
- Evaluate agent quality structurally (use agent-evaluation instead)
- Skip the RED phase even when "the fix is obvious"

---

## Instructions

### Phase 0: PREPARE — Understand the Agent

**Goal**: Read the agent definition and understand what it claims to do before writing tests.

**Step 1: Read the agent file**

```bash
# Read agent definition
cat agents/{agent-name}.md

# Read any referenced skills
cat skills/{skill-name}/SKILL.md
```

**Step 2: Identify testable claims**

Extract concrete, testable behaviors from the agent definition:
- What inputs does it accept?
- What output structure does it produce?
- What routing triggers should activate it?
- What error conditions does it handle?
- What skills does it invoke?

**Step 3: Determine minimum test count**

| Agent Type | Minimum Tests | Required Coverage |
|------------|---------------|-------------------|
| Reviewer agents | 6 | 2 real issues, 2 clean, 1 edge, 1 ambiguous |
| Implementation agents | 5 | 2 typical, 1 complex, 1 minimal, 1 error |
| Analysis agents | 4 | 2 standard, 1 edge, 1 malformed |
| Routing/orchestration | 4 | 2 correct route, 1 ambiguous, 1 invalid |

No gate — this phase is preparation. Move directly to Phase 1.

### Phase 1: RED — Observe Current Behavior

**Goal**: Run agent with test inputs and document exact current behavior before any changes.

**Step 1: Define test plan**

```markdown
## Test Plan: {agent-name}

**Agent Purpose:** {what the agent does}
**Agent File:** agents/{agent-name}.md
**Date:** {date}

**Test Cases:**

| ID | Input | Expected Output | Validates |
|----|-------|-----------------|-----------|
| T1 | {input} | {expected} | Happy path |
| T2 | {input} | {expected} | Error handling |
| T3 | {input} | {expected} | Edge case |
```

Write the test plan to a file before executing. This creates a reproducible baseline.

**Step 2: Dispatch subagent with test inputs**

Use the Task tool to dispatch the agent:

```
Task(
  prompt="""
  [Test input for the agent]

  Context: [Any required context]

  {Include the actual problem/request the agent should handle}
  """,
  subagent_type="{agent-name}"
)
```

**Step 3: Capture results verbatim**

```markdown
## Test T1: Happy Path

**Input:**
{exact input provided}

**Expected Output:**
{what you expected}

**Actual Output:**
{verbatim output from agent — do not summarize}

**Result:** PASS / FAIL
**Failure Reason:** {if FAIL, exactly what was wrong}
```

**Step 4: Identify failure patterns**
- Which test categories fail (happy path, error, edge)?
- Are failures structural (missing sections) or behavioral (wrong answers)?
- Do failures correlate with input characteristics?

**Gate**: All test cases executed. Exact outputs captured verbatim. Failures documented with specific issues identified. Proceed only when gate passes.

### Phase 2: GREEN — Fix Agent Definition

**Goal**: Update agent definition until all test cases pass. One fix at a time.

**Step 1: Prioritize failures**

Triage failures by severity:

| Severity | Description | Priority |
|----------|-------------|----------|
| Critical | Agent produces wrong answers or harmful output | Fix first |
| High | Agent missing required output sections | Fix second |
| Medium | Agent formatting or structure issues | Fix third |
| Low | Agent phrasing or style inconsistencies | Fix last |

**Step 2: Diagnose root cause**

| Failure Type | Fix Approach |
|--------------|--------------|
| Missing output section | Add explicit instruction to include section |
| Wrong format | Add output schema with examples |
| Missing context handling | Add instructions for handling missing info |
| Incorrect classification | Add calibration examples |
| Hallucinated content | Add constraint to only use provided info |
| Agent asks questions instead of answering | Provide required context in prompt or add default handling |

**Step 3: Make one fix at a time**

Change one thing in the agent definition. Re-run ALL test cases. Document which tests now pass/fail.

Never make multiple fixes simultaneously — you cannot determine which change was effective. This is the same principle as debugging: one variable at a time.

**Step 4: Iterate until green**

Repeat Step 3 until all test cases pass. If a fix causes a previously passing test to fail, revert and try a different approach.

Track fix iterations:

```markdown
## Fix Log

| Iteration | Change Made | Tests Passed | Tests Failed | Action |
|-----------|------------|-------------|-------------|--------|
| 1 | Added output schema | T1, T2 | T3 | Continue |
| 2 | Added error handling instruction | T1, T2, T3 | — | Green |
```

**Gate**: All test cases pass. No regressions from previously passing tests. Can explain what each fix changed and why. Proceed only when gate passes.

### Phase 3: REFACTOR — Edge Cases and Robustness

**Goal**: Verify agent handles boundary conditions and produces consistent outputs.

**Step 1: Add edge case tests**

| Category | Test Cases |
|----------|------------|
| Empty Input | Empty string, whitespace only, no context |
| Large Input | Very long content, deeply nested structures |
| Unusual Input | Malformed data, unexpected formats |
| Ambiguous Input | Cases where correct behavior is unclear |

**Step 2: Run consistency tests**

Run the same input 3 times. Outputs should be consistent:
- Same structure
- Same key findings (for analysis agents)
- Acceptable variation in phrasing only

If inconsistent: add more explicit instructions to the agent definition. Re-test.

**Step 3: Run regression suite**

Re-run ALL test cases (original + edge cases) to confirm nothing broke during refactoring.

**Step 4: Document final test report**

```markdown
## Test Report: {agent-name}

| Metric | Result |
|--------|--------|
| Test Cases Run | N |
| Passed | N |
| Failed | N |
| Pass Rate | N% |

## Verdict
READY FOR DEPLOYMENT / NEEDS FIXES / REQUIRES REVIEW
```

**Gate**: Edge cases handled. Consistency verified. Full suite green. Test report documented. Fix is complete.

---

## Examples

### Example 1: Testing a New Reviewer Agent
User says: "Test the new reviewer-security agent"
Actions:
1. Define 6 test cases: 2 real issues, 2 clean code, 1 edge case, 1 ambiguous (RED)
2. Dispatch subagent for each, capture verbatim outputs (RED)
3. Fix agent definition for any failures, re-run all tests (GREEN)
4. Add edge cases (empty input, malformed code), verify consistency (REFACTOR)
Result: Agent passes all tests, report documents pass rate and verdict

### Example 2: Testing After Agent Modification
User says: "I updated the golang-general-engineer, make sure it still works"
Actions:
1. Run existing test cases against modified agent (RED)
2. Compare outputs to previous baseline (RED)
3. Fix any regressions introduced by the modification (GREEN)
4. Test edge cases to verify robustness not degraded (REFACTOR)
Result: Agent modification validated, no regressions confirmed

### Example 3: Testing Routing Logic
User says: "Verify the /do router sends Go requests to the right agent"
Actions:
1. Define test cases: "Review this Go code", "Fix this .go file", "Write a goroutine" (RED)
2. Dispatch each through router, verify correct agent handles it (RED)
3. Fix routing triggers if wrong agent selected (GREEN)
4. Test ambiguous inputs like "Review this code" with mixed-language context (REFACTOR)
Result: Routing validated for all trigger phrases, ambiguous cases documented

---

## Error Handling

### Error: "Agent type not found"
Cause: Agent not registered or name misspelled
Solution:
1. Verify agent file exists: `ls agents/{agent-name}.md`
2. Check YAML frontmatter has correct `name` field
3. Restart Claude Code to pick up new agents

### Error: "Inconsistent outputs across runs"
Cause: Agent produces different results for same input
Solution:
1. Document the inconsistency — this is a valid finding
2. Add more explicit instructions to agent definition
3. Re-test consistency after fix
4. Determine if variation is acceptable (phrasing) or problematic (structure/findings)

### Error: "Subagent timeout"
Cause: Agent taking too long to respond
Solution:
1. Simplify test input to reduce processing
2. Check agent isn't in an infinite loop or excessive tool use
3. Increase timeout if agent legitimately needs more time

### Error: "Agent asks questions instead of answering"
Cause: Agent needs clarification that test input did not provide
Solution:
1. This may be correct behavior — agent properly requesting context
2. Update test input to provide the required context
3. Or update agent definition to handle ambiguity with defaults
4. Document whether questioning behavior is acceptable for this agent type

---

## Anti-Patterns

### Anti-Pattern 1: Testing Without Capturing Exact Output
**What it looks like**: "Tested the agent, it looks good."
**Why wrong**: No evidence of what was tested. Cannot reproduce or verify results. Subjective assessment instead of objective evidence.
**Do instead**: Capture verbatim output for every test case. Document input, expected, actual, and result.

### Anti-Pattern 2: Testing Only Happy Path
**What it looks like**: "Tested with one example, it worked."
**Why wrong**: Agents fail on edge cases most often. One test proves almost nothing. False confidence in agent quality.
**Do instead**: Minimum 3-6 test cases per agent covering success, failure, edge, and ambiguous inputs.

### Anti-Pattern 3: Skipping Re-test After Fixes
**What it looks like**: "Fixed the issue, should work now."
**Why wrong**: Fix might have broken other tests. No verification fix actually works. Regression bugs slip through.
**Do instead**: Re-run ALL test cases after any change. Only mark green when full suite passes.

### Anti-Pattern 4: Reading Prompts Instead of Running Agents
**What it looks like**: "Checked that agent prompt has the right sections."
**Why wrong**: Reading a prompt is not executing an agent. Prompt structure does not guarantee behavior. Must verify actual output.
**Do instead**: Test what the agent DOES, not what the prompt SAYS. Execute with real inputs via Task tool.

### Anti-Pattern 5: Self-Exempting from Testing
**What it looks like**: "This agent is simple, doesn't need testing." or "Simple change, no need to re-test."
**Why wrong**: Simple agents can still fail. Small changes can break behavior. You cannot self-determine exemptions from testing.
**Do instead**: Get human partner confirmation for exemptions. When in doubt, test. Document why testing was skipped if approved.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) — Prevents shortcut rationalizations
- [Anti-Rationalization: Testing](../shared-patterns/anti-rationalization-testing.md) — Testing-specific rationalization blocks
- [Verification Checklist](../shared-patterns/verification-checklist.md) — Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Agent prompt looks correct" | Reading prompt ≠ executing agent | Dispatch subagent and capture output |
| "Tested manually in conversation" | Not reproducible, no baseline | Use Task tool for formal dispatch |
| "Only a small change" | Small changes can break agent behavior | Run full test suite |
| "Will monitor in production" | Production monitoring ≠ pre-deployment testing | Complete RED-GREEN-REFACTOR first |
| "Based on working template" | Template correctness ≠ instance correctness | Test this specific agent |

### Integration
- `agent-comparison`: A/B test agent variants
- `agent-evaluation`: Structural quality checks
- `test-driven-development`: TDD principles applied to agents

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/testing-patterns.md`: Dispatch patterns, test scenarios, eval harness integration
