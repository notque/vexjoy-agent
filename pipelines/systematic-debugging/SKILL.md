---
name: systematic-debugging
description: |
  Evidence-based 5-phase debugging pipeline with mandatory reproduction, testing,
  and learning gates: OBSERVE, HYPOTHESIZE, TEST, FIX, RECORD. Use when user
  reports a bug, tests are failing, code introduced regressions, or production
  issues need investigation. Use for "debug", "fix bug", "why is this failing",
  "root cause", or "tests broken". Do NOT use for feature requests, refactoring,
  or performance optimization without a specific bug symptom.
version: 2.0.0
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
success-criteria:
  - "Bug is reproducible with a specific test or command"
  - "Root cause identified with evidence (not speculation)"
  - "Fix verified by running the reproduction step"
  - "No regressions in related test suite"
  - "Debug pattern recorded to learning.db"
routing:
  triggers:
    - "debug"
    - "find root cause"
    - "reproduce bug"
    - "fix this bug"
    - "this is broken"
    - "not working"
    - "why is this broken"
    - "getting an error"
    - "unexpected behavior"
    - "investigate error"
  category: process
---

# Systematic Debugging Pipeline

> **Promoted from**: `skills/systematic-debugging/SKILL.md` (original 4-phase skill)

Evidence-based 5-phase debugging pipeline with mandatory gates between each phase. No phase may be skipped. Each phase produces artifacts that survive context resets.

## Operator Context

This pipeline operates as an operator for systematic debugging workflows, configuring Claude's behavior for rigorous, evidence-based root cause analysis. It implements the **Iterative Refinement** architectural pattern -- form hypothesis, test, refine, verify -- with **Domain Intelligence** embedded in the debugging methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before debugging
- **Over-Engineering Prevention**: Fix only the bug. No speculative improvements, no "while I'm here" changes
- **Reproduce First**: NEVER attempt fixes before creating reliable reproduction
- **No Random Changes**: Every modification must be based on evidence from isolation
- **Evidence Required**: Every hypothesis must be tested with concrete evidence
- **Verify Fixes**: Confirm fix works AND doesn't introduce regressions
- **Phase Gates Enforced**: Each phase must pass its gate before the next begins

### Default Behaviors (ON unless disabled)
- **Minimal Reproduction**: Create smallest possible test case that shows bug
- **Bisection Strategy**: Use binary search to narrow down failure point
- **One Change at a Time**: Never make multiple changes simultaneously
- **Document Findings**: Log all observations, hypotheses, and test results
- **Related Issues Check**: Search for similar bugs in codebase and git history
- **Temporary File Cleanup**: Remove debug logs and profiling output at completion
- **Persistent Debug File**: Maintain `.debug-session.md` for context-reset resilience

### Optional Behaviors (OFF unless enabled)
- **Regression Test Creation**: Write automated test for this specific bug
- **Git Bisect**: Use `git bisect` to find breaking commit
- **Performance Profiling**: Run profiler to identify bottlenecks
- **Database Query Analysis**: Use EXPLAIN for slow query debugging
- **Network Tracing**: Capture traffic for API debugging

## What This Pipeline CAN Do
- Systematically find root causes through evidence-based investigation
- Create minimal reproductions that isolate the exact failure
- Distinguish between symptoms and root causes
- Verify fixes don't introduce regressions
- Document findings for future reference
- Record patterns to learning.db for future sessions

## What This Pipeline CANNOT Do
- Fix bugs without first reproducing them
- Make speculative changes without evidence
- Optimize performance (use performance-optimization-engineer instead)
- Refactor code (use systematic-refactoring instead)
- Skip any of the 5 phases

---

## Instructions

### Phase 1: OBSERVE

**Goal**: Reproduce the bug, collect error messages, stack traces, and environmental context.

**Artifact**: `debug-observations.md`

**Step 1: Document the bug**

```markdown
## Bug: [Brief Description]
Expected: [What should happen]
Actual: [What actually happens]
Environment: [OS, language version, dependencies]
```

**Step 2: Create minimal reproduction**
- Strip to essentials -- remove unrelated code
- Use smallest dataset that shows the bug
- Isolate from external services where possible

**Step 3: Verify consistency**

Run reproduction **3 times**. If inconsistent, identify variables (timing, randomness, concurrency) and add controls to make it deterministic.

**Step 4: Check knowledge base**

At the start of every new debug investigation, before forming any hypotheses:
1. Check if `.debug-knowledge-base.md` exists in the project root
2. If it exists, search for keyword matches against the current symptom signature
3. Matches are **hypothesis candidates**, not confirmed diagnoses
4. List any matches in `debug-observations.md` with the note: "Prior resolution found -- verify applicability before assuming same root cause"

**Step 5: Create persistent debug file**

Create `.debug-session.md` with immutable Symptoms and Reproduction Steps sections. This file survives context resets.

| Section Type | Sections | Mutation Rule |
|-------------|----------|---------------|
| IMMUTABLE | Symptoms, Reproduction Steps | Write once at session start, never modify |
| APPEND-ONLY | Evidence, Eliminated Hypotheses | Add new entries, never remove or edit existing ones |
| OVERWRITE | Current Hypothesis, Next Action | Replace on each iteration |

**GATE**: Bug reproduces 100% with documented steps. `debug-observations.md` exists with symptoms, environment, and reproduction steps. Proceed only when gate passes.

---

### Phase 2: HYPOTHESIZE

**Goal**: Generate 3-5 candidate root causes ranked by likelihood.

**Artifact**: Updated `debug-observations.md` with hypotheses section.

**Step 1: List components involved in the failure**

```markdown
## Components
1. [Component A] - [Role]
2. [Component B] - [Role]
3. [Component C] - [Role]
```

**Step 2: Binary search to narrow scope**

Test components in combinations to find minimal failing set:
- A alone -> PASS/FAIL?
- A + B -> PASS/FAIL?
- A + B + C -> PASS/FAIL?

When adding a component causes failure, that component (or its interaction) contains the bug.

**Step 3: Trace execution path**

Add targeted logging at decision points in the suspect component. Run and analyze:
- Where does execution diverge from expected?
- What values are unexpected at critical points?
- Are exceptions being caught silently?

**Step 4: Form ranked hypotheses**

```markdown
## Hypothesis: [Specific, testable statement]
Evidence: [What observations support this]
Test: [How to confirm or refute]
Likelihood: [HIGH/MEDIUM/LOW]
```

Generate 3-5 hypotheses. Rank by likelihood based on evidence gathered so far.

**Step 5: Update persistent debug file**

Write current top hypothesis and next action to `.debug-session.md` BEFORE taking any debugging action.

**GATE**: At least 3 hypotheses documented with supporting evidence and test plans. Identified smallest code path and input that reproduces the bug. Proceed only when gate passes.

---

### Phase 3: TEST

**Goal**: Write the minimal reproduction test, verify it fails (red).

**Step 1: Write reproduction test**

Create a test that captures the exact bug behavior:

```python
def test_regression_[issue]():
    """Root cause: [hypothesis]. Fix: [pending]."""
    result = buggy_function(trigger_input)
    assert result == expected  # This should FAIL
```

**Step 2: Test each hypothesis**

For each hypothesis (highest likelihood first):

```markdown
## Testing: [Hypothesis]
Experiment: [What I did]
Result: CONFIRMED / REFUTED
Evidence: [What I observed]
```

If REFUTED: Move to next hypothesis. Append to Eliminated Hypotheses in `.debug-session.md`.
If CONFIRMED: Proceed to Phase 4.

**Step 3: Code inspection checklist**

For the confirmed hypothesis area:
- [ ] Off-by-one errors?
- [ ] Null/None values unhandled?
- [ ] Exceptions caught silently?
- [ ] Race conditions possible?
- [ ] Resources released properly?
- [ ] Input assumptions violated?

**GATE**: Reproduction test exists and is RED (failing). Root cause hypothesis confirmed with evidence. Can explain WHY bug occurred. Proceed only when gate passes.

---

### Phase 4: FIX

**Goal**: Implement fix, verify test turns green.

**Step 1: Make the smallest possible fix**

Address only the confirmed root cause. No speculative improvements.

**Step 2: Verify reproduction test passes**

Run the reproduction test. It must turn GREEN.

**Step 3: Test edge cases**

Test boundary values, empty input, null, maximum values.

**Step 4: Run full test suite**

Verify no regressions. ALL tests must pass.

**Step 5: Test related functionality**

Check similar patterns that might share the same root cause.

**Step 6: Document fix summary**

```markdown
## Fix Summary
Bug: [description]
Root Cause: [exact cause]
Fix: [changes made]
Files: [modified files]
Testing: reproduction passes, edge cases pass, full suite passes
```

**GATE**: Reproduction test is GREEN. Full test suite passes with zero regressions. Fix is minimal and addresses only the confirmed root cause. Proceed only when gate passes.

---

### Phase 5: RECORD

**Goal**: Update learning database with pattern and fix for future sessions.

**Step 1: Record to knowledge base**

Append entry to `.debug-knowledge-base.md`:

```markdown
## [Date] [Brief Description]
**Keywords**: [comma-separated terms: error messages, component names, symptom descriptions]
**Symptom**: [What was observed]
**Root Cause**: [What was actually wrong]
**Resolution**: [What fixed it]
**Files**: [Which files were involved]
```

**Step 2: Update learning.db**

Record the bug pattern and fix to the learning database for automated future lookup.

**Step 3: Clean up**

- Remove `.debug-session.md` (investigation complete)
- Remove temporary debug logs and profiling output
- Keep only the regression test and knowledge base entry

**Output**: `[learning] Bug pattern recorded.`

**GATE**: Knowledge base entry exists with keywords, symptom, root cause, and resolution. `.debug-session.md` cleaned up. Temporary files removed.

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
1. If tests expected buggy behavior -> update tests
2. If fix exposed other bugs -> apply 5-phase process to each
3. If API changed -> restore compatibility or update all callers

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
**Do instead**: Form hypothesis -> test -> confirm/refute -> iterate

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
**Do instead**: Document root cause, fix, and create regression test. Complete Phase 5.

---

## Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can see the bug, no need to reproduce" | Visual inspection misses edge cases | Run reproduction 3 times |
| "This is probably the fix" | Probably != proven | Form hypothesis, test with evidence |
| "Tests pass, must be fixed" | Specific test != full suite | Run full test suite |
| "Simple change, no need to verify" | Simple changes cause complex regressions | Complete Phase 4 |
| "No need to record, I'll remember" | Context resets lose everything | Complete Phase 5 |

---

## Analysis Paralysis Guard

If 5+ consecutive Read/Grep/Glob calls occur without an Edit/Write/Bash action,
STOP and explain what you are looking for and why before proceeding.

After explaining, justification for continued reading MUST be recorded in `.debug-session.md` under the Current Hypothesis section -- not just stated verbally. This creates an audit trail of investigation decisions that survives context resets.

---

## References

This pipeline uses these shared patterns:
- [Anti-Rationalization](../../skills/shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../../skills/shared-patterns/verification-checklist.md) - Pre-completion checks

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/debugging-patterns.md`: Common bug patterns by category
- `${CLAUDE_SKILL_DIR}/references/tools.md`: Language-specific debugging tools
- `${CLAUDE_SKILL_DIR}/references/isolation-techniques.md`: Advanced isolation strategies
