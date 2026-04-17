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
