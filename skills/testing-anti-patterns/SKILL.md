---
name: testing-anti-patterns
description: "Identify and fix testing mistakes: flaky, brittle, over-mocked tests."
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
    - test quality issue
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

# Testing Pattern Quality Skill

## Overview

This skill identifies and fixes common testing mistakes across unit, integration, and E2E test suites. Tests should verify behavior, be reliable, run fast, and fail for the right reasons.

**Scope:** This skill focuses on improving test quality and reliability. It complements `test-driven-development` by addressing what goes wrong with tests, complementing how to write them correctly from scratch.

**Out of scope:** Writing new tests from scratch (use `test-driven-development`), fixing fundamental architectural issues (use `systematic-refactoring`), or profiling test performance with external tools.

---

## Instructions

### Phase 1: SCAN

**Goal**: Identify quality issues present in the target test code.

**Step 1: Locate test files**

Use Grep/Glob to find test files in the relevant area. If user pointed to specific files, start there. Common patterns:
- Go: `*_test.go`
- Python: `test_*.py` or `*_test.py`
- JavaScript/TypeScript: `*.test.ts`, `*.spec.ts`, `*.test.js`, `*.spec.js`

**Step 2: Read CLAUDE.md**

Check for project-specific testing conventions before flagging quality issues. Some projects intentionally deviate from general best practices. This prevents false positives based on organizational standards.

**Step 3: Classify quality issues**

For each test file, scan for these 10 categories (detailed examples in `references/anti-pattern-catalog.md`):

| # | Pattern to Fix | Detection Signal |
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
## Pattern Quality Report

### [File:Line] - [Pattern Name]
- **Severity**: HIGH / MEDIUM / LOW
- **Issue**: [What is wrong]
- **Impact**: [Flaky / slow / false-confidence / maintenance burden]
```

**Gate**: At least one quality issue identified with file:line reference. Proceed only when gate passes.

### Phase 2: PRIORITIZE

**Goal**: Rank findings by impact to fix the most damaging patterns first.

**Priority order:**
1. **HIGH** - Flaky tests, order-dependent tests, ignored failures (erode trust in suite)
2. **MEDIUM** - Over-mocking, incomplete assertions, missing edge cases (false confidence)
3. **LOW** - Poor naming, over-specification, slow suites (maintenance burden)

**Constraint: Fix one pattern at a time.** Mechanical bulk fixes (applying the same pattern to 50 tests without running them) miss context-specific nuances and cause regressions. Fix one, verify it works, then move to the next.

**Constraint: Preserve test intent.** When fixing quality issues, maintain what the test was originally trying to verify. Preserve the original test coverage scope.

**Constraint: Prevent over-engineering.** Fix the specific quality issue identified; make targeted fixes to the specific anti-pattern or delete tests and write new ones from scratch. Institutional knowledge lives in the existing tests.

**Gate**: Findings ranked. User agrees on scope of fixes. Proceed only when gate passes.

### Phase 3: FIX

**Goal**: Apply targeted fixes to identified quality issues.

**Step 1: For each quality issue (highest priority first):**

```markdown
ISSUE: [Name]
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

**Constraint: Show real examples.** Point to actual code when identifying quality issues, not abstract descriptions. Check for rationalization — if a test breaks during refactoring, that test was relying on buggy behavior. Investigate and fix the root cause, investigate and fix the root cause.

**Constraint: Guide toward behavior testing.** Always recommend testing observable behavior, not implementation internals. For example:
- ISSUE: Test asserts on private fields → FIX: Test the public behavior that those fields enable
- ISSUE: Test spies on `_getUser()` → FIX: Test what happens when a user exists or doesn't exist
- ISSUE: Test checks exact regex → FIX: Test that validation succeeds/fails for representative inputs

Change only what is needed to fix the anti-pattern. Consult `references/fix-strategies.md` for language-specific patterns.

**Step 3: Run tests after each fix**

- Run the specific fixed test first to confirm it passes
- Run the full file or package to check for interactions
- If a fix makes a previously-passing test fail, the test was likely depending on buggy behavior — investigate before proceeding

**Gate**: Each fix verified individually. Tests pass after each change.

### Phase 4: VERIFY

**Goal**: Confirm all fixes work together and suite is healthier.

**Step 1**: Run full test suite — all pass

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

## Pattern Quality Catalog

This section documents the domain-specific anti-patterns this skill detects and fixes.

### Pattern 1: Test Observable Behavior

**What it looks like:** Tests assert on private fields, internal regex patterns, or spy on private methods.

**Why it's problematic:** Tests coupled to implementation details break whenever the implementation changes, even if public behavior is identical. This creates brittle tests that fail to reflect real-world usage.

**Example signals:**
- Test accesses `obj._privateField`
- Test mocks or spies on `_internalMethod()`
- Test asserts the exact regex used internally

**Fix:** Test the public behavior that those implementation details enable. If private fields matter, they matter because they affect what users see or experience.

### Pattern 2: Mock Only at Boundaries

**What it looks like:** Mock setup spans more than 50% of the test code. CSS selectors use nth-child or rely on brittle DOM structure.

**Why it's problematic:** Over-mocked tests verify mock wiring, not actual behavior. They miss real integration issues and break whenever the mocking structure changes.

**Example signals:**
- Test has 15 lines of setup and 5 lines of assertion
- Test uses `.querySelector('div:nth-child(3) > span')`
- Test mocks every dependency instead of using real implementations at I/O boundaries

**Fix:** Mock only at architectural boundaries (HTTP, DB, external services). Use real implementations for internal logic. For UI tests, select by semantic attributes (data-testid, role) instead of DOM structure.

### Pattern 3: Isolate Test State

**What it looks like:** Tests share mutable state, use class-level variables, or have numbered test names (test1, test2) suggesting sequence dependency.

**Why it's problematic:** Tests that pass in sequence but fail in parallel or random order hide bugs. The suite becomes unreliable — developers can't trust "all tests pass" locally if they fail in CI.

**Example signals:**
- Multiple tests modify a shared class-level variable
- Database is populated by test1, test2 depends on that state
- Test names: `test1_setup`, `test2_verify`, `test3_cleanup`

**Fix:** Each test owns its data. Use setup/teardown or test fixtures to isolate state. Run suite with `--shuffle` or `-random-order` to catch dependencies.

### Pattern 4: Assert Specific Values

**What it looks like:** Tests use assertions like `!= nil`, `> 0`, `toBeTruthy()` without checking specific values.

**Why it's problematic:** Incomplete assertions pass for many wrong reasons. A function that returns 999 (wrong) passes an `> 0` assertion. This gives false confidence — tests pass but miss bugs.

**Example signals:**
- `assert result != nil` (passes for any non-nil value)
- `assert response.status > 0` (passes for 404, 500, etc.)
- `expect(user).toBeTruthy()` (passes for any truthy user, even with wrong name)

**Fix:** Assert specific expected values:
- `assert.equal(result.name, "Alice")`
- `assert.equal(response.status, 200)`
- `expect(user.name).toBe("Alice")`

### Pattern 5: Assert Only What Matters

**What it looks like:** Tests assert on default values, exact timestamps, hardcoded IDs, or every field in a response.

**Why it's problematic:** Over-specified tests are fragile. When a default changes (legitimately), dozens of tests break even though behavior didn't change. Tests should specify only what matters for this test case.

**Example signals:**
- `assert.equal(user.createdAt, "2024-01-15T10:30:00Z")` (timestamp brittle to test time)
- `assert.equal(post.id, "uuid-1234-5678")` (hardcoded ID specific to this test)
- Test asserts `status`, `message`, `timestamp`, `userId`, `metadata` when only `status` matters

**Fix:** Assert only what matters. Use flexible matchers for timestamps and IDs:
- `expect(user.createdAt).toBeDefined()` or `toBeWithin(now, 1000ms)`
- `assert.truthy(post.id)` (just verify it exists)

### Pattern 6: Address or Remove Skipped Tests

**What it looks like:** Tests use `@skip`, `.skip`, `xit`, empty catch blocks, or `_ = err` (ignore error).

**Why it's problematic:** Skipped tests become permanent blind spots. Nobody remembers why they were skipped. Empty catch blocks hide real errors.

**Example signals:**
- `@skip` or `.skip()` with no expiration date
- `try { ...test code... } catch (e) {}` (silently ignore errors)
- `err := doSomething(); _ = err` (acknowledge but ignore)

**Fix:** Delete the test if no longer relevant, or unskip and fix it. Add a reason annotation with a date if skipping is truly necessary:
```go
t.Skip("TODO: fix timing issue (2024-01-15)")
```

### Pattern 7: Use Descriptive Test Names

**What it looks like:** Test names use sequential numbers (`test1`, `test2`), vague names (`testFunc`, `test_new`), or generic descriptions (`it('works')`, `it('handles case')`).

**Why it's problematic:** Poor names hide intent. Developers reading test output see `test1 failed` but have no idea what behavior broke. Good test names document expected behavior.

**Example signals:**
- `TestCreateUser1`, `TestCreateUser2`
- `test_new`, `testFunc`, `test_handle`
- `it('works')`, `it('handles case')`, `it('does something')`

**Fix:** Use descriptive names that describe the scenario and expected outcome:
- Go: `Test_CreateUser_WithValidEmail_ReturnsNewUser`
- Python: `test_create_user_with_valid_email_returns_new_user`
- JS: `it('creates a user when given a valid email')`

### Pattern 8: Cover Boundaries and Errors

**What it looks like:** Test suite covers only the happy path. No tests for empty inputs, null values, boundary conditions, errors, or large datasets.

**Why it's problematic:** Missing edge cases cause production bugs. The happy path works, but the code crashes on empty input, null reference, or boundary values.

**Example signals:**
- Only tests with valid input; no tests with empty/null
- No tests for negative numbers, zero, or max values
- No tests for error conditions (timeout, connection failure)

**Fix:** Add tests for:
- **Empty**: empty string, empty array, empty object
- **Null**: null input, missing required field
- **Boundary**: zero, max value, min value, off-by-one
- **Error**: timeout, network failure, permission denied
- **Large**: very large arrays, deep nesting

### Pattern 9: Optimize Test Speed

**What it looks like:** Full database reset between every test. No parallelization. Fixture data shared instead of created per-test. Tests wait on actual time.

**Why it's problematic:** Slow tests discourage running locally. Developers skip tests before committing, bugs slip through. CI builds take hours, slowing iteration.

**Example signals:**
- Each test: `DROP TABLE users; INSERT INTO users ...` (30s per test)
- Sequential execution with no parallelization
- Tests use `time.Sleep(1000)` to wait for something

**Fix:**
- Use transactions that rollback instead of dropping tables
- Run tests in parallel: `go test -parallel 8`, `pytest -n auto`
- Create fixtures once, reference per-test: fixture factories, test-specific data builders
- Replace waits with condition checks: `waitFor(() => element.textContent)` instead of `sleep(1000)`

### Pattern 10: Ensure Deterministic Tests

**What it looks like:** Tests use `sleep()`, `time.Sleep()`, `setTimeout()` or unsynchronized goroutines. Tests pass locally but fail randomly in CI.

**Why it's problematic:** Flaky tests erode trust in the test suite. Developers cannot tell if a failure is real or just timing. Teams start ignoring test failures — the worst outcome.

**Example signals:**
- `time.Sleep(100 * time.Millisecond)` to wait for goroutine
- `setTimeout(() => { ...assert... }, 500)` hoping it's ready
- Tests pass locally but fail in CI (slower machines, resource contention)

**Fix:**
- Replace `sleep()` with explicit waits: `waitFor()`, `sync.WaitGroup`, channels
- Inject fake clocks or time control: `time.Now()` should be mockable
- Synchronize goroutines with channels or `sync.WaitGroup`, not timing
- Tests must be deterministic: same input → same output, regardless of machine speed

---

## Error Handling

### Error: "Cannot Determine if Pattern is a Quality Issue"

Cause: Context-dependent — pattern may be valid in specific situations

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
4. Preserve what each test covers

### Error: "Suite Has Hundreds of Quality Issues"

Cause: Systemic test quality issues, not individual mistakes

Solution:
1. Fix issues incrementally, focusing on highest severity first
2. Focus on HIGH severity items only (flaky, order-dependent)
3. Recommend adopting TDD going forward to prevent new quality issues
4. Suggest incremental cleanup strategy (fix on touch, not bulk rewrite)

---

## References

### Quick Reference Table

| Pattern to Fix | Symptom | Fix |
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

Strict TDD prevents most quality issues:
1. **RED phase** catches incomplete assertions (test must fail first)
2. **GREEN phase minimum** prevents over-specification
3. **Watch failure** confirms you test behavior, not mocks
4. **Incremental cycles** prevent test interdependence
5. **Refactor phase** reveals tests coupled to implementation

If you find quality issues in a codebase, check if TDD discipline slipped.

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/pattern-catalog.md`: Detailed code examples for all 10 anti-patterns (Go, Python, JavaScript)
- `${CLAUDE_SKILL_DIR}/references/fix-strategies.md`: Language-specific fix patterns and tooling
- `${CLAUDE_SKILL_DIR}/references/blind-spot-taxonomy.md`: 6-category taxonomy of what high-coverage test suites commonly miss (concurrency, state, boundaries, security, integration, resilience)
- `${CLAUDE_SKILL_DIR}/references/load-test-scenarios.md`: 6 load test scenario types (smoke, load, stress, spike, soak, breakpoint) with configurations and critical endpoint priorities
