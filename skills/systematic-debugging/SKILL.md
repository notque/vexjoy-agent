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
promoted_to: pipelines/systematic-debugging
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
success-criteria:
  - "Bug is reproducible with a specific test or command"
  - "Root cause identified with evidence (not speculation)"
  - "Fix verified by running the reproduction step"
  - "No regressions in related test suite"
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

> **Note**: This skill has been promoted to a pipeline. See `pipelines/systematic-debugging/SKILL.md` for the phase-gated version.

# Systematic Debugging Skill

Evidence-based root cause analysis through four phases: Reproduce, Isolate, Identify, Verify. Every phase produces testable evidence before advancing to the next, because skipping phases leads to whack-a-mole debugging where symptoms get masked instead of causes getting fixed.

## Instructions

### Phase 1: REPRODUCE

**Goal**: Establish consistent reproduction before attempting any fix.

Read and follow the repository's CLAUDE.md before starting, because project-specific constraints (test commands, build steps, environment setup) affect how you reproduce and fix bugs.

**Step 1: Check for prior knowledge**

Search for `.debug-knowledge-base.md` in the project root. If it exists, search for keyword matches against the current symptoms (error messages, component names, behavioral descriptions). Matches are hypothesis candidates, not confirmed diagnoses — list them in Evidence with the note: "Prior resolution found — verify applicability before assuming same root cause." Also search for similar bugs in the codebase and git history, because the same bug pattern often recurs in related code paths.

**Step 2: Create the debug session file**

Create `.debug-session.md` at the start of every investigation, because debugging sessions lose all state on context reset and this file lets a new session resume without re-investigating eliminated causes.

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

The mutation rules matter:
- **IMMUTABLE** sections (Symptoms, Reproduction Steps): Write once at session start, never modify. These are ground truth. If they change, it's a different bug.
- **APPEND-ONLY** sections (Evidence, Eliminated Hypotheses): Add new entries, never remove or edit existing ones. Removing entries lets future sessions re-investigate dead ends.
- **OVERWRITE** sections (Current Hypothesis, Next Action): Replace on each iteration. Old values get captured in Evidence/Eliminated when tested.

**Step 3: Document the bug**

```markdown
## Bug: [Brief Description]
Expected: [What should happen]
Actual: [What actually happens]
Environment: [OS, language version, dependencies]
```

**Step 4: Create minimal reproduction**

Strip to the smallest possible test case that shows the bug — remove unrelated code, use the smallest dataset that triggers the failure, and isolate from external services where possible. Minimal reproduction matters because large reproductions hide the actual trigger behind noise, making isolation harder.

Do not skip reproduction even if you think you can see the bug in the code, because visual inspection misses edge cases, timing dependencies, and interaction effects that only surface when the code actually runs.

**Step 5: Verify consistency**

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

Use bisection to narrow down the failure point, because linear scanning wastes time on large codebases. Test components in combinations to find the minimal failing set:
- A alone -> PASS/FAIL?
- A + B -> PASS/FAIL?
- A + B + C -> PASS/FAIL?

When adding a component causes failure, that component (or its interaction) contains the bug.

When needed, use `git bisect` to find the breaking commit — this is especially effective when the bug is a recent regression and the commit history is clean.

**Step 3: Trace execution path**

Add targeted logging at decision points in the suspect component. Run and analyze:
- Where does execution diverge from expected?
- What values are unexpected at critical points?
- Are exceptions being caught silently?

When needed for domain-specific isolation:
- **Performance bugs**: Run a profiler to identify bottlenecks in the suspect code path.
- **Slow queries**: Use EXPLAIN to analyze database query execution plans.
- **API issues**: Capture network traffic to see what's actually being sent and received.

**Gate**: Identified smallest code path and input that reproduces the bug. Proceed only when gate passes.

### Phase 3: IDENTIFY

**Goal**: Determine exact root cause through hypothesis testing.

Update `.debug-session.md` BEFORE taking any debugging action, not after — because if context resets mid-action, the file shows what was about to happen and what has already been ruled out.

The workflow for each iteration:
1. Write your hypothesis and next action to the file
2. Execute the action
3. Append the result to Evidence (or Eliminated Hypotheses if refuted)
4. Update Current Hypothesis and Next Action for the next iteration
5. Repeat

**Step 1: Form hypothesis**

```markdown
## Hypothesis: [Specific, testable statement]
Evidence: [What observations support this]
Test: [How to confirm or refute]
```

Every hypothesis must be tested with concrete evidence, because "probably" is not "proven" — untested assumptions lead to fixes that mask symptoms while leaving root causes intact.

**Step 2: Test hypothesis**

Design a single, targeted experiment. Make exactly one change per test, because multiple simultaneous changes make it impossible to determine which one had the effect. Run it. Document result as CONFIRMED or REFUTED.

If REFUTED: Form new hypothesis based on what you learned. Return to Step 1.

Every modification must be based on evidence from isolation, because random changes — even educated guesses — can mask symptoms while leaving the root cause in place, and you cannot explain why a random fix works.

**Step 3: Inspect suspect code**

Code inspection checklist:
- [ ] Off-by-one errors?
- [ ] Null/None values unhandled?
- [ ] Exceptions caught silently?
- [ ] Race conditions possible?
- [ ] Resources released properly?
- [ ] Input assumptions violated?

**Step 4: Verify root cause with targeted fix**

Make the smallest possible change that addresses the identified cause. Fix only the bug — no speculative improvements, no "while I'm here" refactoring, because unrelated changes obscure what actually fixed the bug and introduce untested modifications. Test against reproduction.

**Gate**: Root cause identified with evidence. Targeted fix resolves the issue. Can explain WHY bug occurred. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm fix works and doesn't introduce regressions.

**Step 1**: Run original reproduction steps -> all pass

**Step 2**: Test edge cases (empty input, boundary values, null, maximum)

**Step 3**: Run full test suite -> no regressions. Run the full suite, not just the specific test, because fixes that pass the target test but break related functionality are not fixes — "tests pass" for one test is not the same as "no regressions."

**Step 4**: Test related functionality using similar patterns

**Step 5**: When warranted, create a regression test for this specific bug to prevent it from recurring:

```python
def test_regression_[issue]():
    """Root cause: [what was wrong]. Fix: [what changed]."""
    result = fixed_function(trigger_input)
    assert result == expected
```

**Step 6**: Clean up temporary artifacts — remove debug logs, profiling output, and any temporary instrumentation added during investigation, because leftover debug code in production is a maintenance hazard.

**Step 7**: Document fix summary

```markdown
## Fix Summary
Bug: [description]
Root Cause: [exact cause]
Fix: [changes made]
Files: [modified files]
Testing: reproduction passes, edge cases pass, full suite passes
```

Document the root cause and fix clearly, because an unexplained `git commit -m "Fixed bug"` means the bug will reappear and no institutional knowledge is preserved.

**Step 8**: Record to knowledge base

After Phase 4 passes, append an entry to `.debug-knowledge-base.md`:

```markdown
## [Date] [Brief Description]
**Keywords**: [comma-separated terms: error messages, component names, symptom descriptions]
**Symptom**: [What was observed]
**Root Cause**: [What was actually wrong]
**Resolution**: [What fixed it]
**Files**: [Which files were involved]
```

This knowledge base is append-only and match-based (not a lookup table) because bugs are contextual — the same error message in different modules may have completely different root causes. The knowledge base accelerates hypothesis formation but does not replace the 4-phase process.

**Gate**: All verification steps pass. Fix is complete.

### Resuming From a Context Reset

When starting a debug session, check for an existing `.debug-session.md`:
1. Read the file completely
2. Do NOT re-investigate anything listed in Eliminated Hypotheses
3. Resume from the Current Hypothesis and Next Action
4. If Next Action was partially completed, verify its state before continuing

### Analysis Paralysis Guard

If 5+ consecutive Read/Grep/Glob calls occur without an Edit/Write/Bash action, STOP and explain what you are looking for and why before proceeding. Record the justification in `.debug-session.md` under Current Hypothesis — not just stated verbally — because this creates an audit trail of investigation decisions that survives context resets.

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
2. If fix exposed other bugs -> apply 4-phase process to each
3. If API changed -> restore compatibility or update all callers

### Error: "Root Cause Still Unclear After Isolation"
Cause: Isolation not narrow enough, or multiple contributing factors
Solution:
1. Return to Phase 2 with narrower scope
2. Add logging at lower abstraction levels
3. Use debugger to step through execution
4. Consult `references/debugging-patterns.md` for common patterns

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/debugging-patterns.md`: Common bug patterns by category
- `${CLAUDE_SKILL_DIR}/references/tools.md`: Language-specific debugging tools
- `${CLAUDE_SKILL_DIR}/references/isolation-techniques.md`: Advanced isolation strategies
