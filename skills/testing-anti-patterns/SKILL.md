---
name: testing-anti-patterns
description: |
  Identify and fix common testing mistakes across unit, integration, and E2E
  test suites. Use when tests are flaky, brittle, over-mocked, order-dependent,
  slow, poorly named, or providing false confidence. Use for "test smell",
  "fragile test", "flaky test", "over-mocking", "test anti-pattern", or
  "skipped tests". Do NOT use for writing new tests from scratch (use
  test-driven-development), refactoring architecture (use systematic-refactoring),
  or performance profiling without a specific test quality symptom.
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
routing:
  triggers:
    - flaky test
    - brittle test
    - test smell
    - test anti-pattern
    - slow tests
    - skipped test
    - test depends on order
    - over-mocking
    - fragile test
    - testing implementation details
  pairs_with:
    - test-driven-development
    - go-testing
    - vitest-runner
  complementary: test-driven-development
---

# Testing Anti-Patterns Skill

## Operator Context

This skill operates as an operator for test quality assessment, configuring Claude's behavior for identifying and fixing common testing mistakes. It provides "negative knowledge" -- patterns to AVOID. It complements `test-driven-development` by focusing on what goes wrong, not just what to do right.

**Core principle:** Tests should verify behavior, be reliable, run fast, and fail for the right reasons.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files
- **Over-Engineering Prevention**: Fix the specific anti-pattern; do not rewrite the entire test suite
- **Preserve Test Intent**: When fixing anti-patterns, maintain what the test was trying to verify
- **Show Real Examples**: Point to actual code when identifying anti-patterns, not abstract descriptions
- **Behavior Over Implementation**: Always guide toward testing observable behavior, not internals

### Default Behaviors (ON unless disabled)
- **Communication**: Report anti-patterns with specific file:line references and concrete fixes
- **Severity Classification**: Distinguish critical (flaky, order-dependent) from minor (naming) issues
- **Quick Wins First**: Suggest fixes that improve reliability immediately
- **One Pattern at a Time**: Address each anti-pattern individually with before/after

### Optional Behaviors (OFF unless enabled)
- **Full Suite Audit**: Scan entire test suite for anti-patterns (can be slow)
- **Refactoring Mode**: Apply fixes automatically rather than just identifying them
- **Metrics Collection**: Count anti-patterns by category for reporting

## What This Skill CAN Do
- Identify specific anti-patterns in test code with file:line references
- Provide concrete before/after examples for fixes
- Prioritize fixes by impact (flaky > order-dependent > slow > naming)
- Explain WHY a pattern is problematic
- Suggest incremental improvements without rewriting suites

## What This Skill CANNOT Do
- Fix fundamental architectural issues (use `systematic-refactoring`)
- Write new tests from scratch (use `test-driven-development`)
- Profile test performance (use actual profilers)
- Guarantee test correctness (anti-patterns can exist in "working" tests)
- Skip identification and jump straight to rewriting

---

## Instructions

### Phase 1: SCAN

**Goal**: Identify anti-patterns present in the target test code.

**Step 1: Locate test files**

Use Grep/Glob to find test files in the relevant area. If user pointed to specific files, start there. Common patterns:
- Go: `*_test.go`
- Python: `test_*.py` or `*_test.py`
- JavaScript/TypeScript: `*.test.ts`, `*.spec.ts`, `*.test.js`, `*.spec.js`

**Step 2: Read CLAUDE.md**

Check for project-specific testing conventions before flagging anti-patterns. Some projects intentionally deviate from general best practices.

**Step 3: Classify anti-patterns**

For each test file, scan for these 10 categories (detailed examples in `references/anti-pattern-catalog.md`):

| # | Anti-Pattern | Detection Signal |
|---|-------------|-----------------|
| 1 | Testing implementation details | Asserts on private fields, internal regex, spy on private methods |
| 2 | Over-mocking / brittle selectors | Mock setup > 50% of test code, CSS nth-child selectors |
| 3 | Order-dependent tests | Shared mutable state, class-level variables, numbered test names |
| 4 | Incomplete assertions | `!= nil`, `> 0`, `toBeTruthy()`, no value checks |
| 5 | Over-specification | Exact timestamps, hardcoded IDs, asserting every default field |
| 6 | Ignored failures | `@skip`, `.skip`, `xit`, empty catch blocks, `_ = err` |
| 7 | Poor naming | `testFunc2`, `test_new`, `it('works')`, `it('handles case')` |
| 8 | Missing edge cases | Only happy path, no empty/null/boundary/error tests |
| 9 | Slow test suites | Full DB reset per test, no parallelization, no fixture sharing |
| 10 | Flaky tests | `sleep()`, `time.Sleep()`, `setTimeout()`, unsynchronized goroutines |

**Step 4: Document findings**

```markdown
## Anti-Pattern Report

### [File:Line] - [Anti-Pattern Name]
- **Severity**: HIGH / MEDIUM / LOW
- **Issue**: [What is wrong]
- **Impact**: [Flaky / slow / false-confidence / maintenance burden]
```

**Gate**: At least one anti-pattern identified with file:line reference. Proceed only when gate passes.

### Phase 2: PRIORITIZE

**Goal**: Rank findings by impact to fix the most damaging patterns first.

**Priority order:**
1. **HIGH** - Flaky tests, order-dependent tests, ignored failures (erode trust in suite)
2. **MEDIUM** - Over-mocking, incomplete assertions, missing edge cases (false confidence)
3. **LOW** - Poor naming, over-specification, slow suites (maintenance burden)

**Gate**: Findings ranked. User agrees on scope of fixes. Proceed only when gate passes.

### Phase 3: FIX

**Goal**: Apply targeted fixes to identified anti-patterns.

**Step 1: For each anti-pattern (highest priority first):**

```markdown
ANTI-PATTERN: [Name]
Location: [file:line]
Issue: [What is wrong]
Impact: [Flaky/slow/false-confidence/maintenance burden]

Current:
[problematic code snippet]

Fixed:
[improved code snippet]

Priority: [HIGH/MEDIUM/LOW]
```

**Step 2: Apply fix**
- Change only what is needed to fix the anti-pattern
- Preserve the original test's intent and coverage
- One anti-pattern fix at a time
- Consult `references/fix-strategies.md` for language-specific patterns

**Step 3: Run tests after each fix**
- Run the specific fixed test first to confirm it passes
- Run the full file or package to check for interactions
- If a fix makes a previously-passing test fail, the test was likely depending on buggy behavior -- investigate before proceeding

**Gate**: Each fix verified individually. Tests pass after each change.

### Phase 4: VERIFY

**Goal**: Confirm all fixes work together and suite is healthier.

**Step 1**: Run full test suite -- all pass

**Step 2**: Verify previously-flaky tests are now deterministic (run 3x if applicable)
- Go: `go test -count=3 -run TestFixed ./...`
- Python: `pytest --count=3 tests/test_fixed.py`
- JS: Run test file 3 times sequentially

**Step 3**: Confirm no test was accidentally deleted or skipped
- Compare test count before and after fixes
- Search for any new `@skip` or `.skip` annotations introduced

**Step 4**: Summary report

```markdown
## Fix Summary
Anti-patterns fixed: [count]
Files modified: [list]
Tests affected: [count]
Suite status: all passing / [details]
Remaining issues: [any deferred items]
```

**Gate**: Full suite passes. All fixes verified. Summary delivered.

---

## Examples

### Example 1: Flaky Test Investigation
User says: "This test passes locally but fails randomly in CI"
Actions:
1. Scan test for timing dependencies -- find `sleep(500)` (SCAN)
2. Classify as Anti-Pattern 10: Flaky Test, severity HIGH (PRIORITIZE)
3. Replace `sleep()` with `waitFor()` or inject fake clock (FIX)
4. Run test 10x to confirm determinism, run full suite (VERIFY)
Result: Flaky test replaced with deterministic wait

### Example 2: Over-Mocked Test Suite
User says: "Every small refactor breaks dozens of tests"
Actions:
1. Scan for mock density -- find tests with 5+ mocks each (SCAN)
2. Classify as Anti-Pattern 2: Over-mocking, severity MEDIUM (PRIORITIZE)
3. Replace mocks with real implementations at I/O boundaries (FIX)
4. Verify suite passes, confirm refactoring no longer breaks tests (VERIFY)
Result: Tests verify behavior instead of mock wiring

### Example 3: False Confidence
User says: "Tests all pass but we keep finding bugs in production"
Actions:
1. Scan for incomplete assertions (`!= nil`, `toBeTruthy`) and missing edge cases (SCAN)
2. Classify as Anti-Patterns 4+8, severity MEDIUM (PRIORITIZE)
3. Add specific value assertions, add edge case tests (FIX)
4. Verify new assertions catch known production bugs (VERIFY)
Result: Tests now catch real issues before deployment

### Example 4: Order-Dependent Suite
User says: "Tests pass in sequence but fail when run in parallel or random order"
Actions:
1. Scan for shared mutable state, class-level variables, global DB mutations (SCAN)
2. Classify as Anti-Pattern 3: Order Dependence, severity HIGH (PRIORITIZE)
3. Give each test its own setup/teardown, remove shared state (FIX)
4. Run suite with randomized order 3x, confirm all pass (VERIFY)
Result: Tests are self-contained and parallelizable

### Example 5: Skipped Test Audit
User says: "We have 40 skipped tests, are any still relevant?"
Actions:
1. Grep for `@skip`, `.skip`, `xit`, `@pytest.mark.skip` across suite (SCAN)
2. Classify each: outdated (delete), still relevant (fix), environment-specific (document) (PRIORITIZE)
3. Delete dead tests, unskip and fix relevant ones, add reason annotations (FIX)
4. Verify suite passes with formerly-skipped tests re-enabled (VERIFY)
Result: No unexplained skips remain; suite coverage restored

---

## Error Handling

### Error: "Cannot Determine if Pattern is Anti-Pattern"
Cause: Context-dependent -- pattern may be valid in specific situations
Solution:
1. Check if the test has a comment explaining the unusual approach
2. Consider the testing layer (unit vs integration vs E2E)
3. If mock-heavy test is for a unit with many dependencies, suggest integration test instead
4. When in doubt, flag as MEDIUM and explain trade-offs

### Error: "Fix Changes Test Behavior"
Cause: Anti-pattern was masking an actual test gap or testing wrong thing
Solution:
1. Identify what the test was originally trying to verify
2. Write the correct assertion for that behavior
3. If original behavior was wrong, note it as a separate finding
4. Do not silently change what a test covers

### Error: "Suite Has Hundreds of Anti-Patterns"
Cause: Systemic test quality issues, not individual mistakes
Solution:
1. Do NOT attempt to fix everything at once
2. Focus on HIGH severity items only (flaky, order-dependent)
3. Recommend adopting TDD going forward to prevent new anti-patterns
4. Suggest incremental cleanup strategy (fix on touch, not bulk rewrite)

---

## Anti-Patterns (Meta)

### Anti-Pattern 1: Rewriting Instead of Fixing
**What it looks like**: Deleting the entire test and writing a new one from scratch
**Why wrong**: Loses institutional knowledge of what was being tested; may reduce coverage
**Do instead**: Preserve intent, fix the specific anti-pattern, keep test focused

### Anti-Pattern 2: Fixing Style Without Fixing Substance
**What it looks like**: Renaming `test1` to `test_creates_user` but not fixing the incomplete assertion inside
**Why wrong**: Cosmetic improvement without reliability gain
**Do instead**: Fix reliability issues first (assertions, flakiness), then naming

### Anti-Pattern 3: Adding Tests Without Removing Anti-Patterns
**What it looks like**: Writing new good tests alongside existing bad ones
**Why wrong**: Bad tests still produce false confidence and maintenance burden
**Do instead**: Fix or delete the anti-pattern test, then add proper coverage if needed

### Anti-Pattern 4: Bulk Fixing Without Verification
**What it looks like**: Applying the same fix pattern to 50 tests without running them
**Why wrong**: Mechanical fixes miss context-specific nuances; may break tests
**Do instead**: Fix one, verify, fix next. Batch only after pattern is proven safe.

---

## References

### Quick Reference Table

| Anti-Pattern | Symptom | Fix |
|-------------|---------|-----|
| Testing implementation | Test breaks on refactor | Test behavior, not internals |
| Over-mocking | Mock setup > test logic | Integration test or mock only I/O |
| Order dependence | Tests fail in isolation | Each test owns its data |
| Incomplete assertions | `assert result != nil` | Assert specific expected values |
| Over-specification | Asserts on defaults/timestamps | Assert only what matters for this test |
| Ignored failures | `@skip`, empty catch | Delete or fix immediately |
| Poor naming | `testFunc2` | `Test{What}_{When}_{Expected}` |
| Missing edge cases | Only happy path | empty, null, boundary, error, large |
| Slow suite | 30s+ for simple tests | Parallelize, share fixtures, rollback |
| Flaky tests | Random failures | Control time, synchronize, no sleep |

### Red Flags During Review
- `@skip`, `@ignore`, `xit`, `.skip` without expiration date
- `time.sleep()`, `setTimeout()` in test code
- Test names with sequential numbers (`test1`, `test2`)
- Global mutable state accessed by multiple tests
- Mock setup spanning 20+ lines
- Empty catch blocks in tests
- Assertions like `!= nil`, `> 0`, `toBeTruthy()` without value checks

### TDD Relationship
Strict TDD prevents most anti-patterns:
1. **RED phase** catches incomplete assertions (test must fail first)
2. **GREEN phase minimum** prevents over-specification
3. **Watch failure** confirms you test behavior, not mocks
4. **Incremental cycles** prevent test interdependence
5. **Refactor phase** reveals tests coupled to implementation

If you find anti-patterns in a codebase, check if TDD discipline slipped.

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The test passes, so it's fine" | Passing with anti-patterns gives false confidence | Evaluate assertion quality, not just pass/fail |
| "We can fix test quality later" | Anti-patterns compound; flaky tests erode trust daily | Fix HIGH severity items now, defer LOW |
| "Just skip the flaky test for now" | Skipped tests become permanent blind spots | Diagnose root cause, fix or delete |
| "Mocking everything is faster" | Over-mocking tests mock wiring, not behavior | Mock only at architectural boundaries |
| "One big test covers everything" | Monolithic tests are fragile and hard to debug | Split into focused, independent tests |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/anti-pattern-catalog.md`: Detailed code examples for all 10 anti-patterns (Go, Python, JavaScript)
- `${CLAUDE_SKILL_DIR}/references/fix-strategies.md`: Language-specific fix patterns and tooling
- `${CLAUDE_SKILL_DIR}/references/blind-spot-taxonomy.md`: 6-category taxonomy of what high-coverage test suites commonly miss (concurrency, state, boundaries, security, integration, resilience)
- `${CLAUDE_SKILL_DIR}/references/load-test-scenarios.md`: 6 load test scenario types (smoke, load, stress, spike, soak, breakpoint) with configurations and critical endpoint priorities
