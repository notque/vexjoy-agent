# Anti-Rationalization: Testing

Testing-specific patterns to prevent rationalized test skipping or incomplete coverage.

## Base Patterns

See [anti-rationalization-core.md](./anti-rationalization-core.md) for universal patterns.

## Testing-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Tests are slow" | Slow tests > broken prod | **Run them anyway** |
| "Happy path works" | Users find edge cases | **Test error paths** |
| "Edge case is unlikely" | Unlikely ≠ Impossible | **Test it** |
| "Mocking is hard" | Hard ≠ Optional | **Write the mock** |
| "Code is simple" | Simple code can have bugs | **Test it** |
| "Already tested similar" | Similar ≠ Same | **Test this specific code** |
| "Unit tests are enough" | Integration can still fail | **Integration tests too** |
| "Works on my machine" | CI environment differs | **Verify in CI** |
| "Refactor, behavior same" | Refactors can change behavior | **Run all tests** |
| "Test would be trivial" | Trivial tests catch regressions | **Write it anyway** |
| "Feature is internal only" | Internal users deserve quality | **Test it** |
| "Will add tests later" | Later never comes | **Tests before merge** |

## TDD RED Phase Enforcement

The RED phase (failing test first) is NON-NEGOTIABLE:

| Rationalization | Why Wrong | Required |
|-----------------|-----------|----------|
| "I know what to write" | Test might not fail correctly | **Write test, see it fail** |
| "Test is obvious" | Obvious tests can be wrong | **Verify failure message** |
| "Faster to code first" | Leads to tests that can't fail | **RED before GREEN** |

RED phase checklist:
- [ ] Test written before implementation
- [ ] Test runs and FAILS
- [ ] Failure message is clear and correct
- [ ] Test fails for the RIGHT reason

## Coverage Rationalizations

| Claim | Reality Check |
|-------|---------------|
| "90% coverage" | What's in the 10%? |
| "All functions tested" | Are edge cases tested? |
| "Integration tests cover it" | Unit tests catch different bugs |
| "E2E tests cover it" | E2E is slow, unit tests are fast |

## Test Quality vs Quantity

Bad tests rationalize coverage:

| Bad Pattern | Why Bad | Better |
|-------------|---------|--------|
| Test that can't fail | Provides false confidence | Assert meaningful things |
| Test implementation details | Breaks on refactor | Test behavior |
| Duplicate tests | Maintenance burden | One test per behavior |
| Flaky tests | Erode trust | Fix or delete |

## Boundary Testing Requirements

MUST test boundaries:

| Type | Boundaries |
|------|------------|
| Numbers | 0, 1, max, negative, overflow |
| Strings | empty, null, unicode, very long |
| Arrays | empty, single, many, duplicates |
| Dates | now, past, future, boundaries |
| Files | missing, empty, large, permissions |
