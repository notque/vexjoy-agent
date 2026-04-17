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
