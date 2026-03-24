---
name: test-driven-development
user-invocable: false
description: |
  RED-GREEN-REFACTOR cycle with strict phase gates. Write failing test first,
  implement minimum code to pass, then refactor while keeping tests green.
  Use when implementing new features, fixing bugs with test-first approach,
  improving test coverage, or when user mentions TDD. Use for "TDD", "test
  first", "red green refactor", "write tests", or "implement with tests".
  Do NOT use for debugging existing failures (use systematic-debugging) or
  for refactoring without new tests (use systematic-refactoring).
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
---

# Test-Driven Development (TDD) Skill

## Purpose
Enforce the RED-GREEN-REFACTOR cycle for all code changes. This skill ensures tests are written BEFORE implementation code, verifies tests fail for the right reasons, and maintains test coverage through disciplined development cycles.

## Operator Context

This skill operates as an operator for test-driven development workflows, configuring Claude's behavior for disciplined test-first coding practices.

### Hardcoded Behaviors (Always Apply)

These behaviors are non-negotiable for correct TDD practice:

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default TDD behaviors.
- **Over-Engineering Prevention**: Only implement what's directly tested. Keep code simple and focused. No speculative features or flexibility that wasn't asked for. First make it work, then make it right.
- **RED phase is mandatory**: ALWAYS write the test BEFORE any implementation code
- **Verify test failure**: MUST run test and show failure output before implementing
- **Failure reason validation**: MUST confirm test fails for the CORRECT reason (not syntax errors)
- **Show complete output**: NEVER summarize test results - show full test runner output
- **Minimum implementation**: Write ONLY enough code to make the test pass (no gold-plating)
- **Commit discipline**: Tests and implementation committed together in atomic units

### Default Behaviors (ON unless disabled)

Active by default to maintain quality:

- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- **Temporary File Cleanup**: Remove temporary test files, coverage reports, or debug outputs created during TDD cycles at task completion. Keep only files explicitly needed for the project.
- **Run tests after each change**: Execute test suite after every code modification
- **Test improvement suggestions**: Recommend better assertions, edge cases, test organization
- **Coverage awareness**: Track which code paths are tested, suggest missing coverage
- **Refactoring validation**: Ensure tests remain green during refactoring steps
- **Test naming conventions**: Enforce descriptive test names that explain behavior

### Optional Behaviors (OFF unless enabled)

Advanced testing capabilities available on request:

- **Property-based testing**: Generate tests with random/fuzzed inputs (Go: testing/quick, Python: hypothesis)
- **Mutation testing**: Verify test quality by introducing bugs
- **Benchmark tests**: Performance regression testing
- **Table-driven tests**: Convert multiple similar tests to data-driven approach
- **Test parallelization**: Run independent tests concurrently for speed

## What This Skill CAN Do
- Guide RED-GREEN-REFACTOR cycles for any language (Go, Python, JavaScript)
- Enforce phase gates: test must fail before implementation
- Validate test failure reasons (syntax errors vs missing implementation)
- Guide refactoring while maintaining green tests
- Provide language-specific testing commands and patterns

## What This Skill CANNOT Do
- Write implementation before tests (violates TDD principle)
- Skip the RED phase or proceed without verified test failure
- Implement features not covered by a test
- Approve passing tests without checking failure reason
- Skip running tests after each change

## Instructions

### TDD Workflow: RED-GREEN-REFACTOR Cycle

#### Step 1: Write a Failing Test (RED Phase)

**PHASE GATE: Do NOT proceed to GREEN phase until:**
- [ ] Test file is created and saved
- [ ] Test has been executed
- [ ] Test output shows FAILURE (not syntax/import error)
- [ ] Failure message indicates missing implementation

**BEFORE writing any implementation code:**

1. **Understand the requirement**: Clarify what behavior needs to be implemented
2. **Write the test first**: Create test that describes the desired behavior
3. **Use descriptive test names**: Test name should explain what is being tested
4. **Write minimal test setup**: Only create fixtures/mocks needed for THIS test
5. **Assert expected behavior**: Use specific assertions (not just "no error")

**Run the test:**
```bash
go test ./... -v -run TestNewFeature          # Go
pytest tests/test_feature.py::test_name -v    # Python
npm test -- --testNamePattern="new feature"   # JavaScript
```

#### Step 2: Verify Test Fails for the RIGHT Reason (RED Verification)

**CRITICAL: Run the test and confirm it fails:**

1. **Execute test command** (show full output)
2. **Verify failure reason**: Test should fail because feature not implemented, NOT:
   - Syntax errors
   - Import errors
   - Wrong test setup
   - Unrelated failures

**Expected RED output indicators:**
- Go: `--- FAIL: TestFeatureName` with expected vs actual mismatch
- Python: `AssertionError` or `AttributeError: module has no attribute`
- JavaScript: `Expected X but received undefined`

**If test fails for WRONG reason:**
- Fix the test setup/syntax
- Re-run until it fails for the RIGHT reason (missing implementation)

#### Step 3: Write MINIMUM Code to Pass (GREEN Phase)

**PHASE GATE: Do NOT proceed to REFACTOR phase until:**
- [ ] Implementation code is written
- [ ] Test has been executed again
- [ ] Test output shows PASS
- [ ] No other tests have been broken

**Implement ONLY enough code to make THIS test pass:**

1. **Minimal implementation**: Simplest code that satisfies the test
2. **No extra features**: Don't implement behavior not covered by tests
3. **Hardcoded values are OK initially**: First make it work, then make it right

#### Step 4: Verify Test Passes (GREEN Verification)

**Run test and confirm it passes:**

1. **Execute test command** (show full output)
2. **Verify PASS status**: Test should now succeed
3. **Check for warnings**: Note any deprecation warnings or issues

**If test still fails:**
- Review implementation logic
- Check test assertions are correct
- Debug until test passes

#### Step 5: Refactor While Keeping Tests Green (REFACTOR Phase)

**PHASE GATE: Do NOT mark task complete until:**
- [ ] All refactoring changes are saved
- [ ] Full test suite has been executed
- [ ] ALL tests pass (not just the new one)
- [ ] Code quality has been evaluated against checklist below

**REFACTORING DECISION CRITERIA** (evaluate each):
| Criterion | Check | Action if YES |
|-----------|-------|---------------|
| Duplication | Same logic in 2+ places? | Extract to shared function |
| Naming | Names unclear or misleading? | Rename for clarity |
| Length | Function >20 lines? | Extract sub-functions |
| Complexity | Nested conditionals >2 deep? | Simplify or extract |
| Reusability | Could other code use this? | Extract to module |

**Improve code quality without changing behavior:**

1. **Run full test suite BEFORE refactoring**: Establish green baseline
2. **Refactor incrementally**: Extract functions, rename for clarity, remove duplication
3. **Run tests after EACH refactoring step**: Ensure tests stay green
4. **Refactor tests too**: Improve test readability and maintainability

#### Step 6: Commit Atomic Changes

**Commit test and implementation together:**

1. **Review changes**: Verify test + implementation are complete
2. **Run full test suite**: Ensure nothing broke
3. **Commit with descriptive message**

## Error Handling

### Common TDD Mistakes and Solutions

#### Error: "Test passes before implementation"
**Symptom**: Test shows PASS in RED phase

**Causes:**
- Test is testing the wrong thing
- Implementation already exists elsewhere
- Test assertions are too weak (always true)

**Solution:**
1. Review test assertions - are they specific enough?
2. Verify test is actually calling the code under test
3. Check for existing implementation of the feature
4. Strengthen assertions to actually verify behavior

#### Error: "Test fails for wrong reason"
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

#### Error: "Tests pass but feature doesn't work"
**Symptom**: Tests green but manual testing shows bugs

**Causes:**
- Tests don't cover actual usage
- Test mocks don't match real behavior
- Edge cases not tested

**Solution:**
1. Review test coverage - what's missing?
2. Add integration tests alongside unit tests
3. Test with real data, not just mocks
4. Add edge case tests (empty input, null, extremes)

#### Error: "Refactoring breaks tests"
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

## Language-Specific Testing Commands

| Language | Run One Test | Run All | With Coverage |
|----------|-------------|---------|---------------|
| Go | `go test -v -run TestName ./pkg` | `go test ./...` | `go test -cover ./...` |
| Python | `pytest tests/test_file.py::test_fn -v` | `pytest` | `pytest --cov=src` |
| JavaScript | `npm test -- --testNamePattern="name"` | `npm test` | `npm test -- --coverage` |

## Testing Best Practices

### Assertion Guidelines

**Use specific assertions:**
- `assert result == 42` (specific value)
- `assert error.message.contains("invalid")` (specific content)
- NOT `assert result != nil` (too weak)
- NOT `assert len(result) > 0` (not specific enough)

**Test one concept per test:**
- Each test should verify ONE behavior
- If test name needs "and", split into multiple tests
- Makes failures easier to diagnose

### Arrange-Act-Assert Pattern

```python
def test_feature():
    # Arrange: Set up test data
    input_data = create_test_data()

    # Act: Execute the code under test
    result = function_under_test(input_data)

    # Assert: Verify expected behavior
    assert result.status == "success"
```

## Common Anti-Patterns

### Anti-Pattern 1: Skipping the RED Phase

**Wrong -- writing implementation first:**
```python
# Writing implementation first
def calculate_total(items):
    return sum(item.price for item in items)

# Then writing test after
def test_calculate_total():
    items = [Item(price=10), Item(price=20)]
    assert calculate_total(items) == 30
```

**Why it's wrong:**
- Can't verify test actually catches bugs (never saw it fail)
- Test might be passing for wrong reasons
- Risk of writing tests that match buggy implementation

**Correct -- RED then GREEN:**
```python
# 1. Write test FIRST (RED phase)
def test_calculate_total():
    items = [Item(price=10), Item(price=20)]
    assert calculate_total(items) == 30
# Run test -> fails with "NameError: name 'calculate_total' is not defined"

# 2. Implement minimum code (GREEN phase)
def calculate_total(items):
    return sum(item.price for item in items)
# Run test -> passes
```

### Anti-Pattern 2: Testing Implementation Details

**Wrong -- testing internals:**
```go
func TestParser_UsesCorrectRegex(t *testing.T) {
    parser := NewParser()
    // Testing internal regex pattern - breaks on refactor
    assert.Equal(t, `\d{3}-\d{3}-\d{4}`, parser.phoneRegex)
}
```

**Why it's wrong:**
- Test breaks when refactoring internal implementation
- Doesn't verify actual behavior users care about
- Makes refactoring painful (tests should enable it)

**Correct -- testing behavior:**
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

### Anti-Pattern 3: Writing Multiple Features Without Tests

**Wrong -- implementing everything at once:**
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

**Why it's wrong:**
- Lost the TDD cycle discipline completely
- Can't verify each feature worked incrementally
- No design feedback from tests

**Correct -- one cycle per feature:**
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

### Anti-Pattern 4: Over-Engineering in GREEN Phase

**Wrong -- test requires simple addition but implementation over-engineers:**
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

**Why it's wrong:**
- Implementing features not covered by tests
- Violates "minimum code to pass" principle
- Hard to maintain untested code paths

**Correct -- implement only what's tested:**
```go
// Implement ONLY what's needed to pass
type Calculator struct{}

func (c *Calculator) Add(a, b int) int {
    return a + b
}
// Add complexity ONLY when a test requires it
```

## Reference Files
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Language-specific TDD examples (Go, Python, JavaScript)

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Anti-Rationalization (Testing)](../shared-patterns/anti-rationalization-testing.md) - Testing-specific rationalizations
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I know what the test should be, let me just code it" | Skipping RED means test may not catch bugs | Write test, run it, see it fail first |
| "Test passes, implementation is correct" | Passing test may be too weak | Check assertions are specific enough |
| "Simple feature, no need for TDD cycle" | Simple features have edge cases too | One RED-GREEN-REFACTOR per feature |
| "I'll add more tests after the feature works" | Retro-fitted tests miss design feedback | Write tests BEFORE implementation |
