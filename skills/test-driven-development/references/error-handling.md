# TDD Error Handling

Common TDD failure modes with symptoms, causes, and solutions. Loaded when diagnosing a stuck cycle.

## Test passes before implementation (RED phase)

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

## Test fails for wrong reason (RED phase)

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

## Tests pass but feature does not work

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

## Refactoring breaks tests

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
