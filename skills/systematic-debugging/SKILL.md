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
success-criteria:
  - "Bug is reproducible with a specific test or command"
  - "Root cause identified with evidence (not speculation)"
  - "Fix verified by running the reproduction step"
  - "No regressions in related test suite"
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

---

## Persistent Debug File Protocol

Debugging sessions lose all state on context reset — hypotheses, eliminated causes, evidence, and next actions vanish. This protocol creates a structured file that survives resets and lets a new session resume without re-investigating eliminated causes.

### File: `.debug-session.md`

Create this file at the start of every debug investigation. It has three section types with strict mutation rules:

| Section Type | Sections | Mutation Rule | WHY |
|-------------|----------|---------------|-----|
| IMMUTABLE | Symptoms, Reproduction Steps | Write once at session start, never modify | These are the ground truth. If they change, it's a different bug. Editing them mid-investigation causes you to lose track of the original problem. |
| APPEND-ONLY | Evidence, Eliminated Hypotheses | Add new entries, never remove or edit existing ones | Removing entries lets future sessions re-investigate dead ends. The whole point is to accumulate knowledge, not revise it. |
| OVERWRITE | Current Hypothesis, Next Action | Replace on each iteration | These represent the live state of the investigation. Old values are captured in Evidence/Eliminated when they're tested. |

### Template

```markdown
# Debug Session: [Brief Description]
<!-- Created: [timestamp] -->

## Symptoms (IMMUTABLE — do not edit after initial capture)
- [Exact error message or behavior]
- [Environment: OS, language version, dependencies]
- [How discovered: test failure, user report, monitoring alert]

## Reproduction Steps (IMMUTABLE — do not edit after initial capture)
1. [Step 1]
2. [Step 2]
3. [Expected vs actual result]

## Evidence (APPEND-ONLY — add new entries, never remove or edit)
- [timestamp] [observation]: [what was found and where]

## Eliminated Hypotheses (APPEND-ONLY — add new entries, never remove or edit)
- [timestamp] [hypothesis]: [evidence that refuted it]

## Current Hypothesis (OVERWRITE — replace each iteration)
**Hypothesis**: [specific, testable statement]
**Supporting evidence**: [what points to this]
**Test plan**: [how to confirm or refute]

## Next Action (OVERWRITE — replace each iteration)
[Exactly what to do next — specific enough that a new session can execute it cold]
```

### Critical Rule: Update BEFORE Acting

Update `.debug-session.md` BEFORE taking any debugging action, not after. WHY: If context resets mid-action, the file shows what was about to happen and what has already been ruled out. A post-action update means a reset loses the most recent work.

The workflow is:
1. Write your hypothesis and next action to the file
2. Execute the action
3. Append the result to Evidence (or Eliminated Hypotheses if refuted)
4. Update Current Hypothesis and Next Action for the next iteration
5. Repeat

### Resuming From a Reset

When starting a debug session, check for an existing `.debug-session.md`:
1. Read the file completely
2. Do NOT re-investigate anything listed in Eliminated Hypotheses
3. Resume from the Current Hypothesis and Next Action
4. If Next Action was partially completed, verify its state before continuing

---

## Debug Knowledge Base

Resolved debug sessions create compounding value when their findings are recorded for future investigations. This protocol maintains an append-only knowledge base of resolved bugs.

### File: `.debug-knowledge-base.md`

After resolving a bug (Phase 4 VERIFY passes), append an entry:

```markdown
## [Date] [Brief Description]
**Keywords**: [comma-separated terms for matching: error messages, component names, symptom descriptions]
**Symptom**: [What was observed]
**Root Cause**: [What was actually wrong]
**Resolution**: [What fixed it]
**Files**: [Which files were involved]
```

### Lookup Protocol

At the start of every new debug investigation (Phase 1: REPRODUCE), before forming any hypotheses:

1. Check if `.debug-knowledge-base.md` exists in the project root
2. If it exists, search for keyword matches against the current symptom signature (error messages, component names, behavioral descriptions)
3. Matches are **hypothesis candidates**, not confirmed diagnoses — the same symptom can have different root causes in different contexts
4. List any matches in the Evidence section of `.debug-session.md` with the note: "Prior resolution found — verify applicability before assuming same root cause"

WHY this is append-only and match-based (not a lookup table): Bugs are contextual. An "undefined is not a function" error in module A may have a completely different root cause than the same error in module B. The knowledge base accelerates hypothesis formation — it does not replace the 4-phase process.

---

## Analysis Paralysis Guard

This skill uses the [Analysis Paralysis Guard](../shared-patterns/analysis-paralysis-guard.md).
If 5+ consecutive Read/Grep/Glob calls occur without an Edit/Write/Bash action,
STOP and explain what you are looking for and why before proceeding.

### Debugging-Specific Addition
- After explaining, justification for continued reading MUST be recorded in `.debug-session.md` under the Current Hypothesis section — not just stated verbally. This creates an audit trail of investigation decisions that survives context resets.
