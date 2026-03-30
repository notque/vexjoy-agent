---
name: test-driven-development
user-invocable: false
description: "RED-GREEN-REFACTOR cycle with strict phase gates for TDD."
version: 2.0.0
success-criteria:
  - "Failing test written before implementation code"
  - "All new tests pass after implementation"
  - "No pre-existing tests broken"
  - "Refactor phase completed without changing test outcomes"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
routing:
  triggers:
    - "TDD"
    - "test first"
    - "red green refactor"
    - "write tests first"
    - "test-driven"
    - "start with failing test"
    - "tests before code"
  category: testing
---

# Test-Driven Development (TDD) Skill

Enforce the RED-GREEN-REFACTOR cycle for all code changes. Tests are written before implementation code, verified to fail for the right reasons, and maintained through disciplined development cycles.

## Instructions

Before starting any TDD cycle, read and follow repository CLAUDE.md files. Project instructions override default TDD behaviors because local conventions (test frameworks, directory layout, naming) vary across codebases.

### Phase 1: Write a Failing Test (RED)

The test MUST exist and fail before any implementation code is written, because seeing the test fail first proves it can actually detect the bug or missing feature. A test that has never been seen failing provides no evidence that it tests anything meaningful.

**Steps:**

1. **Understand the requirement** -- clarify what behavior needs to be implemented
2. **Write the test first** -- create a test that describes the desired behavior
3. **Use descriptive test names** -- the test name should read as a specification of behavior (e.g., `TestCalculateTotal_WithEmptyCart_ReturnsZero`), because vague names like `TestCalc` make failures impossible to diagnose without reading the test body
4. **Write minimal test setup** -- only create fixtures/mocks needed for THIS test
5. **Assert expected behavior** -- use specific assertions (not just "no error"), because weak assertions like `assert result != nil` pass for wrong reasons and provide false confidence

Use specific assertions:
- `assert result == 42` (specific value)
- `assert error.message.contains("invalid")` (specific content)
- NOT `assert result != nil` (too weak -- passes even when result is garbage)
- NOT `assert len(result) > 0` (not specific enough -- passes with wrong data)

Test one concept per test. If the test name needs "and", split into multiple tests, because multi-assertion tests produce ambiguous failures.

Follow the Arrange-Act-Assert pattern:

```python
def test_feature():
    # Arrange: Set up test data
    input_data = create_test_data()

    # Act: Execute the code under test
    result = function_under_test(input_data)

    # Assert: Verify expected behavior
    assert result.status == "success"
```

**Optional techniques** (use when explicitly requested):
- **Property-based testing**: Generate tests with random/fuzzed inputs (Go: `testing/quick`, Python: `hypothesis`)
- **Table-driven tests**: Convert multiple similar tests to data-driven approach when 3+ tests share the same structure

**Run the test:**
```bash
go test ./... -v -run TestNewFeature          # Go
pytest tests/test_feature.py::test_name -v    # Python
npm test -- --testNamePattern="new feature"   # JavaScript
```

Show the full test runner output -- never summarize test results, because summarization hides warnings, partial failures, and unexpected output that reveal problems early.

#### RED Phase Gate

Do NOT proceed to the GREEN phase until all of these are true:
- [ ] Test file is created and saved
- [ ] Test has been executed
- [ ] Test output shows FAILURE (not syntax/import error)
- [ ] Failure message indicates missing implementation

### Phase 2: Verify Failure Reason (RED Verification)

The test must fail because the feature is not implemented, NOT because of syntax errors, import errors, wrong test setup, or unrelated failures. A test that fails for the wrong reason proves nothing about the missing feature and will pass for the wrong reason after implementation.

1. **Execute test command** and show the complete output
2. **Verify failure reason** -- confirm the error matches expected missing-implementation patterns:
   - Go: `--- FAIL: TestFeatureName` with expected vs actual mismatch
   - Python: `AssertionError` or `AttributeError: module has no attribute`
   - JavaScript: `Expected X but received undefined`

**If the test fails for the WRONG reason:**
- Fix the test setup/syntax
- Re-run until it fails for the RIGHT reason (missing implementation)
- Do NOT proceed until the failure clearly indicates "this feature does not exist yet"

### Phase 3: Implement Minimum Code (GREEN)

Write ONLY enough code to make the failing test pass. Implement nothing beyond what the test demands, because untested code paths are invisible liabilities -- they cannot be verified, they rot silently, and they complicate future refactoring.

1. **Minimal implementation** -- the simplest code that satisfies the test
2. **No extra features** -- do not implement behavior not covered by tests. First make it work, then make it right
3. **Hardcoded values are OK initially** -- a hardcoded return that passes the test is better than a generic algorithm that also handles untested cases

Wrong (over-engineering in GREEN phase):
```go
// Test only requires simple addition
func TestCalculator_AddTwoNumbers(t *testing.T) {
    calc := NewCalculator()
    result := calc.Add(2, 3)
    assert.Equal(t, 5, result)
}

// But implementation adds unnecessary complexity
type Calculator struct {
    operations map[string]func(float64, float64) float64
    precision  int
    history    []Operation
}
```

Correct (implement only what is tested):
```go
type Calculator struct{}

func (c *Calculator) Add(a, b int) int {
    return a + b
}
// Add complexity ONLY when a test requires it
```

### Phase 4: Verify Test Passes (GREEN Verification)

Run the test and show the complete output. Never summarize -- the full output reveals warnings, deprecation notices, and timing issues that summaries hide.

1. **Execute test command** and display all output
2. **Verify PASS status**
3. **Run the full test suite** -- not just the new test, because a change that makes one test pass while breaking another is not progress. Run tests after every code modification to catch regressions immediately

```bash
go test ./... -v                    # Go - all tests
pytest -v                           # Python - all tests
npm test                            # JavaScript - all tests
```

**If the test still fails:**
- Review implementation logic
- Check test assertions are correct
- Debug until the test passes

#### GREEN Phase Gate

Do NOT proceed to the REFACTOR phase until all of these are true:
- [ ] Implementation code is written
- [ ] New test has been executed and shows PASS
- [ ] Full test suite has been executed
- [ ] No other tests have been broken

### Phase 5: Refactor (REFACTOR)

Improve code quality without changing behavior. Run the full test suite before refactoring to establish a green baseline, because you need proof that any future failure was caused by your refactoring, not by a pre-existing issue.

**Refactoring decision criteria** (evaluate each):

| Criterion | Check | Action if YES |
|-----------|-------|---------------|
| Duplication | Same logic in 2+ places? | Extract to shared function |
| Naming | Names unclear or misleading? | Rename for clarity |
| Length | Function >20 lines? | Extract sub-functions |
| Complexity | Nested conditionals >2 deep? | Simplify or extract |
| Reusability | Could other code use this? | Extract to module |

1. **Run full test suite BEFORE refactoring** -- establish green baseline
2. **Refactor incrementally** -- extract functions, rename for clarity, remove duplication
3. **Run tests after EACH refactoring step** -- ensure tests stay green after every individual change, because large refactoring batches make it impossible to identify which change broke the test
4. **Refactor tests too** -- improve test readability and maintainability. Suggest better assertions, edge cases, and test organization where they would strengthen coverage

Test behavior, not implementation details. Tests coupled to internals break on refactoring and defeat its purpose:

Wrong (testing internals):
```go
func TestParser_UsesCorrectRegex(t *testing.T) {
    parser := NewParser()
    // Testing internal regex pattern -- breaks on refactor
    assert.Equal(t, `\d{3}-\d{3}-\d{4}`, parser.phoneRegex)
}
```

Correct (testing behavior):
```go
func TestParser_ValidPhoneNumber_ParsesCorrectly(t *testing.T) {
    parser := NewParser()
    result, err := parser.ParsePhone("123-456-7890")
    assert.NoError(t, err)
    assert.Equal(t, "1234567890", result.Digits())
}

func TestParser_InvalidPhoneNumber_ReturnsError(t *testing.T) {
    parser := NewParser()
    _, err := parser.ParsePhone("invalid")
    assert.Error(t, err)
    assert.Contains(t, err.Error(), "invalid phone format")
}
```

Track which code paths are tested and suggest missing coverage, because untested paths are invisible to the refactoring safety net.

**Optional techniques** (use when explicitly requested):
- **Mutation testing**: Verify test quality by introducing bugs -- if mutating code does not break a test, that test is too weak
- **Benchmark tests**: Performance regression testing to ensure refactoring does not degrade speed
- **Test parallelization**: Run independent tests concurrently for speed

#### REFACTOR Phase Gate

Do NOT mark the task complete until all of these are true:
- [ ] All refactoring changes are saved
- [ ] Full test suite has been executed
- [ ] ALL tests pass (not just the new one)
- [ ] Code quality has been evaluated against the criteria table above

### Phase 6: Commit

Commit the test and implementation together as an atomic unit, because separating them creates a window where the repository is in an inconsistent state -- either tests exist for unimplemented code, or code exists without its test coverage.

1. **Review changes** -- verify test + implementation are complete
2. **Run full test suite** -- ensure nothing broke
3. **Commit with descriptive message**

After committing, clean up any temporary test files, coverage reports, or debug outputs created during the TDD cycle. Keep only files explicitly needed for the project.

Report facts without self-congratulation. Show command output rather than describing it.

### Cycle Discipline

Each feature gets its own RED-GREEN-REFACTOR cycle. Do not batch multiple features into one cycle:

Wrong (implementing everything at once):
```javascript
// Implementing many features at once without tests
class UserManager {
  createUser(data) { /* complex logic */ }
  updateUser(id, data) { /* complex logic */ }
  deleteUser(id) { /* complex logic */ }
  validateUser(user) { /* complex logic */ }
}
// Then one giant test for everything
```

Correct (one cycle per feature):
```javascript
// Cycle 1: Create user (RED -> GREEN -> REFACTOR)
it('should create user with valid data', () => {
    const manager = new UserManager()
    const user = manager.createUser({ name: 'Alice', email: 'alice@example.com' })
    expect(user.id).toBeDefined()
    expect(user.name).toBe('Alice')
})
// Implement createUser() to pass, then move to next cycle

// Cycle 2: Validate user (RED -> GREEN -> REFACTOR)
it('should reject user with invalid email', () => {
    const manager = new UserManager()
    expect(() => manager.createUser({ name: 'Bob', email: 'invalid' }))
      .toThrow('Invalid email format')
})
// Add validation to make test pass
```

## Reference Material

### Language-Specific Testing Commands

| Language | Run One Test | Run All | With Coverage |
|----------|-------------|---------|---------------|
| Go | `go test -v -run TestName ./pkg` | `go test ./...` | `go test -cover ./...` |
| Python | `pytest tests/test_file.py::test_fn -v` | `pytest` | `pytest --cov=src` |
| JavaScript | `npm test -- --testNamePattern="name"` | `npm test` | `npm test -- --coverage` |

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/examples.md`: Language-specific TDD examples (Go, Python, JavaScript)

## Error Handling

### Test passes before implementation (RED phase)

**Symptom**: Test shows PASS in RED phase

**Causes:**
- Test is testing the wrong thing
- Implementation already exists elsewhere
- Test assertions are too weak (always true)

**Solution:**
1. Review test assertions -- are they specific enough?
2. Verify test is actually calling the code under test
3. Check for existing implementation of the feature
4. Strengthen assertions to actually verify behavior

### Test fails for wrong reason (RED phase)

**Symptom**: Syntax errors, import errors, setup failures in RED phase

**Causes:**
- Test setup incomplete
- Missing dependencies
- Incorrect import paths

**Solution:**
1. Fix syntax/import errors first
2. Set up necessary fixtures/mocks
3. Verify test file structure matches project conventions
4. Re-run until test fails for RIGHT reason (missing feature)

### Tests pass but feature does not work

**Symptom**: Tests green but manual testing shows bugs

**Causes:**
- Tests do not cover actual usage
- Test mocks do not match real behavior
- Edge cases not tested

**Solution:**
1. Review test coverage -- what is missing?
2. Add integration tests alongside unit tests
3. Test with real data, not just mocks
4. Add edge case tests (empty input, null, extremes)

### Refactoring breaks tests

**Symptom**: Tests fail after refactoring

**Causes:**
- Tests coupled to implementation details
- Brittle assertions (checking internals not behavior)
- Large refactoring without incremental steps

**Solution:**
1. Test behavior, not implementation details
2. Refactor in smaller steps
3. Run tests after each micro-refactoring
4. Update tests if API contract legitimately changed
