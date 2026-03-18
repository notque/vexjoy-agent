---
name: systematic-debugging
description: |
  Evidence-based 4-phase root cause analysis: Reproduce, Isolate, Identify,
  Verify. Use when user reports a bug, tests are failing, code introduced
  regressions, or production issues need investigation. Use for "debug",
  "fix bug", "why is this failing", "root cause", or "tests broken". Do NOT
  use for feature requests, refactoring, or performance optimization without
  a specific bug symptom.
version: 2.0.0
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
---

# Systematic Debugging Skill

## Operator Context

This skill operates as an operator for systematic debugging workflows, configuring Claude's behavior for rigorous, evidence-based root cause analysis. It implements the **Iterative Refinement** architectural pattern — form hypothesis, test, refine, verify — with **Domain Intelligence** embedded in the debugging methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before debugging
- **Over-Engineering Prevention**: Fix only the bug. No speculative improvements, no "while I'm here" changes
- **Reproduce First**: NEVER attempt fixes before creating reliable reproduction
- **No Random Changes**: Every modification must be based on evidence from isolation
- **Evidence Required**: Every hypothesis must be tested with concrete evidence
- **Verify Fixes**: Confirm fix works AND doesn't introduce regressions

### Default Behaviors (ON unless disabled)
- **Minimal Reproduction**: Create smallest possible test case that shows bug
- **Bisection Strategy**: Use binary search to narrow down failure point
- **One Change at a Time**: Never make multiple changes simultaneously
- **Document Findings**: Log all observations, hypotheses, and test results
- **Related Issues Check**: Search for similar bugs in codebase and git history
- **Temporary File Cleanup**: Remove debug logs and profiling output at completion

### Optional Behaviors (OFF unless enabled)
- **Regression Test Creation**: Write automated test for this specific bug
- **Git Bisect**: Use `git bisect` to find breaking commit
- **Performance Profiling**: Run profiler to identify bottlenecks
- **Database Query Analysis**: Use EXPLAIN for slow query debugging
- **Network Tracing**: Capture traffic for API debugging

## What This Skill CAN Do
- Systematically find root causes through evidence-based investigation
- Create minimal reproductions that isolate the exact failure
- Distinguish between symptoms and root causes
- Verify fixes don't introduce regressions
- Document findings for future reference

## What This Skill CANNOT Do
- Fix bugs without first reproducing them
- Make speculative changes without evidence
- Optimize performance (use performance-optimization-engineer instead)
- Refactor code (use systematic-refactoring instead)
- Skip any of the 4 phases

---

## Instructions

### Phase 1: REPRODUCE

**Goal**: Establish consistent reproduction before attempting any fix.

**Step 1: Document the bug**

```markdown
## Bug: [Brief Description]
Expected: [What should happen]
Actual: [What actually happens]
Environment: [OS, language version, dependencies]
```

**Step 2: Create minimal reproduction**
- Strip to essentials — remove unrelated code
- Use smallest dataset that shows the bug
- Isolate from external services where possible

**Step 3: Verify consistency**

Run reproduction **3 times**. If inconsistent, identify variables (timing, randomness, concurrency) and add controls to make it deterministic.

**Gate**: Bug reproduces 100% with documented steps. Proceed only when gate passes.

### Phase 2: ISOLATE

**Goal**: Reduce search space by eliminating irrelevant code paths.

**Step 1: List components involved in the failure**

```markdown
## Components
1. [Component A] - [Role]
2. [Component B] - [Role]
3. [Component C] - [Role]
```

**Step 2: Binary search**

Test components in combinations to find minimal failing set:
- A alone → PASS/FAIL?
- A + B → PASS/FAIL?
- A + B + C → PASS/FAIL?

When adding a component causes failure, that component (or its interaction) contains the bug.

**Step 3: Trace execution path**

Add targeted logging at decision points in the suspect component. Run and analyze:
- Where does execution diverge from expected?
- What values are unexpected at critical points?
- Are exceptions being caught silently?

**Gate**: Identified smallest code path and input that reproduces the bug. Proceed only when gate passes.

### Phase 3: IDENTIFY

**Goal**: Determine exact root cause through hypothesis testing.

**Step 1: Form hypothesis**

```markdown
## Hypothesis: [Specific, testable statement]
Evidence: [What observations support this]
Test: [How to confirm or refute]
```

**Step 2: Test hypothesis**

Design a single, targeted experiment. Run it. Document result as CONFIRMED or REFUTED.

If REFUTED: Form new hypothesis based on what you learned. Return to Step 1.

**Step 3: Inspect suspect code**

Code inspection checklist:
- [ ] Off-by-one errors?
- [ ] Null/None values unhandled?
- [ ] Exceptions caught silently?
- [ ] Race conditions possible?
- [ ] Resources released properly?
- [ ] Input assumptions violated?

**Step 4: Verify root cause with targeted fix**

Make the smallest possible change that addresses the identified cause. Test against reproduction.

**Gate**: Root cause identified with evidence. Targeted fix resolves the issue. Can explain WHY bug occurred.

### Phase 4: VERIFY

**Goal**: Confirm fix works and doesn't introduce regressions.

**Step 1**: Run original reproduction steps → all pass

**Step 2**: Test edge cases (empty input, boundary values, null, maximum)

**Step 3**: Run full test suite → no regressions

**Step 4**: Test related functionality using similar patterns

**Step 5**: Create regression test (if optional behavior enabled)

```python
def test_regression_[issue]():
    """Root cause: [what was wrong]. Fix: [what changed]."""
    result = fixed_function(trigger_input)
    assert result == expected
```

**Step 6**: Document fix summary

```markdown
## Fix Summary
Bug: [description]
Root Cause: [exact cause]
Fix: [changes made]
Files: [modified files]
Testing: reproduction passes, edge cases pass, full suite passes
```

**Gate**: All verification steps pass. Fix is complete.

---

## Examples

### Example 1: Test Failure
User says: "Tests are failing after my last commit"
Actions:
1. Run failing tests, capture output (REPRODUCE)
2. Identify which test(s) fail, isolate to single test (ISOLATE)
3. Trace test execution, form hypothesis about failure (IDENTIFY)
4. Fix and verify all tests pass (VERIFY)
Result: Root cause found, fix verified, no regressions

### Example 2: Production Bug
User says: "Users are getting 500 errors on the checkout page"
Actions:
1. Reproduce the 500 error locally with same inputs (REPRODUCE)
2. Isolate to specific handler/middleware/service (ISOLATE)
3. Identify which code path raises the error (IDENTIFY)
4. Fix, test edge cases, verify no regressions (VERIFY)
Result: Production fix with regression test

---

## Error Handling

### Error: "Cannot Reproduce Bug"
Cause: Environmental differences, timing-dependent, or randomness
Solution:
1. Match environment exactly (OS, versions, dependencies)
2. Look for race conditions or async timing issues
3. Introduce determinism (fixed seeds, mocked time)
4. If intermittent: add monitoring to catch it in-flight

### Error: "Fix Breaks Other Tests"
Cause: Tests relied on buggy behavior, or fix changed API contract
Solution:
1. If tests expected buggy behavior → update tests
2. If fix exposed other bugs → apply 4-phase process to each
3. If API changed → restore compatibility or update all callers

### Error: "Root Cause Still Unclear After Isolation"
Cause: Isolation not narrow enough, or multiple contributing factors
Solution:
1. Return to Phase 2 with narrower scope
2. Add logging at lower abstraction levels
3. Use debugger to step through execution
4. Consult `references/debugging-patterns.md` for common patterns

---

## Anti-Patterns

### Anti-Pattern 1: Fixing Without Reproducing
**What it looks like**: "Let me add better error handling" before seeing the actual error
**Why wrong**: Can't verify fix works, may fix wrong issue
**Do instead**: Complete Phase 1 first. Always.

### Anti-Pattern 2: Random Changes Without Evidence
**What it looks like**: "Maybe if I change this timeout..." without data
**Why wrong**: May mask symptom while leaving root cause. Can't explain why it works.
**Do instead**: Form hypothesis → test → confirm/refute → iterate

### Anti-Pattern 3: Multiple Changes at Once
**What it looks like**: Adding null check + fixing loop + wrapping in try/catch simultaneously
**Why wrong**: Can't determine which change fixed it. Introduces unnecessary code.
**Do instead**: One change, one test. Repeat until fixed.

### Anti-Pattern 4: Insufficient Verification
**What it looks like**: "Specific test passes, ship it!" without running full suite
**Why wrong**: May have introduced regressions or missed edge cases
**Do instead**: Complete all Phase 4 steps before declaring done.

### Anti-Pattern 5: Undocumented Root Cause
**What it looks like**: `git commit -m "Fixed bug"` with no explanation
**Why wrong**: Bug will reappear. No institutional knowledge preserved.
**Do instead**: Document root cause, fix, and create regression test.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can see the bug, no need to reproduce" | Visual inspection misses edge cases | Run reproduction 3 times |
| "This is probably the fix" | Probably ≠ proven | Form hypothesis, test with evidence |
| "Tests pass, must be fixed" | Specific test ≠ full suite | Run full test suite |
| "Simple change, no need to verify" | Simple changes cause complex regressions | Complete Phase 4 |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/debugging-patterns.md`: Common bug patterns by category
- `${CLAUDE_SKILL_DIR}/references/tools.md`: Language-specific debugging tools
- `${CLAUDE_SKILL_DIR}/references/isolation-techniques.md`: Advanced isolation strategies
