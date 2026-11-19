# Explicit Output Contract

Every testing task MUST produce output in this exact structure. Missing sections are not acceptable.

```
1. SCOPE: files/modules tested, framework used, language/runtime
2. TEST INVENTORY: table with columns: test name | behavior tested | assertion type
3. COVERAGE: before/after numbers with BOTH line and branch coverage
4. GAPS: behaviors NOT tested, with justification for each omission
5. VERDICT: SUFFICIENT / INSUFFICIENT / NEEDS_REVIEW
```

**VERDICT criteria:**
- **SUFFICIENT**: 80%+ line AND branch coverage, all public functions have 3+ test cases, all STOP checks passed
- **INSUFFICIENT**: Any coverage below 80%, public functions missing test cases, STOP checks not completed
- **NEEDS_REVIEW**: Coverage met but adversarial review found potential gaps, or test environment limitations prevented full verification

## Full Output Template

```markdown
## Testing Implementation: [Component/Feature]

### 1. SCOPE

- **Files tested**: [list]
- **Framework**: [name + version]
- **Language/Runtime**: [e.g., TypeScript 5.x / Node 20]

### 2. TEST INVENTORY

| Test Name | Behavior Tested | Assertion Type |
|-----------|----------------|----------------|
| `test_add_positive_numbers` | Addition of two positive integers | Equality (exact value) |
| `test_add_zero` | Addition with zero operand | Equality (exact value) |
| `test_add_negative` | Addition with negative numbers | Equality (exact value) |
| `test_add_overflow` | Integer overflow handling | Throws / Error type |

### 3. COVERAGE

| Metric | Before | After |
|--------|--------|-------|
| Lines | X% | Y% |
| Branches | X% | Y% |
| Functions | X% | Y% |
| Statements | X% | Y% |

### 4. GAPS

| Untested Behavior | Justification |
|-------------------|---------------|
| [behavior] | [why it was omitted] |

### 5. VERDICT

**[SUFFICIENT / INSUFFICIENT / NEEDS_REVIEW]**

[1-2 sentence justification]

### Test Execution

```bash
npm run test              # Run all tests
npm run test:coverage     # With coverage report
npm run test:e2e          # E2E tests only
```
```

## Hard Gate Patterns

These patterns violate testing best practices. If encountered:
1. STOP — Pause implementation
2. REPORT — Explain the issue
3. FIX — Use correct approach

| Pattern | Why Blocked | Correct Approach |
|---------|---------------|------------------|
| Arbitrary setTimeout in tests | Masks timing issues, slows tests | Use proper `waitFor` with conditions |
| Shared mutable state between tests | Tests fail in isolation | Each test has own setup/teardown |
| Testing private/internal APIs | Breaks on refactoring | Test public API and user behavior |
| No assertions in tests | Test passes but validates nothing | Strong, specific assertions required |
| Skipping tests (test.skip) | Hides failing or flaky tests | Fix or remove the test |
| Line coverage only (no branch) | Misses conditional logic paths | Always report and enforce branch coverage |
| More than 10 lines in test body | Test is doing too much | Split into multiple focused tests |
| Assertion without message | Failure output is unhelpful | State expected behavior in assertion message |
