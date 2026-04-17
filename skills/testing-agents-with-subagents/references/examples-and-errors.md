# Testing Agents With Subagents — Templates, Examples, and Error Handling

## Phase 1: Test Plan Template

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

## Phase 1: Subagent Dispatch Template

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

## Phase 1: Verbatim Result Capture Template

```markdown
## Test T1: Happy Path

**Input:**
{exact input provided}

**Expected Output:**
{what you expected}

**Actual Output:**
{verbatim output from agent — record verbatim}

**Result:** PASS / FAIL
**Failure Reason:** {if FAIL, exactly what was wrong}
```

## Phase 2: Failure Severity Triage

| Severity | Description | Priority |
|----------|-------------|----------|
| Critical | Agent produces wrong answers or harmful output | Fix first |
| High | Agent missing required output sections | Fix second |
| Medium | Agent formatting or structure issues | Fix third |
| Low | Agent phrasing or style inconsistencies | Fix last |

## Phase 2: Root Cause → Fix Approach

| Failure Type | Fix Approach |
|--------------|--------------|
| Missing output section | Add explicit instruction to include section |
| Wrong format | Add output schema with examples |
| Missing context handling | Add instructions for handling missing info |
| Incorrect classification | Add calibration examples |
| Hallucinated content | Add constraint to only use provided info |
| Agent asks questions instead of answering | Provide required context in prompt or add default handling |

## Phase 2: Fix Log Template

```markdown
## Fix Log

| Iteration | Change Made | Tests Passed | Tests Failed | Action |
|-----------|------------|-------------|-------------|--------|
| 1 | Added output schema | T1, T2 | T3 | Continue |
| 2 | Added error handling instruction | T1, T2, T3 | — | Green |
```

## Phase 3: Edge Case Categories

| Category | Test Cases |
|----------|------------|
| Empty Input | Empty string, whitespace only, no context |
| Large Input | Very long content, deeply nested structures |
| Unusual Input | Malformed data, unexpected formats |
| Ambiguous Input | Cases where correct behavior is unclear |

## Phase 3: Test Report Template

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
