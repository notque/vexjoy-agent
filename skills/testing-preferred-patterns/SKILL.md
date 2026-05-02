---
name: testing-preferred-patterns
description: "Identify and fix testing mistakes: flaky, brittle, over-mocked tests."
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
  category: testing
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
    - go-patterns
    - vitest-runner
  complementary: test-driven-development
---

# Testing Pattern Quality Skill

## Overview

Identifies and fixes common testing mistakes across unit, integration, and E2E suites. Tests should verify behavior, be reliable, run fast, and fail for the right reasons.

**Scope:** Test quality and reliability. Complements `test-driven-development` (how to write tests correctly from scratch).

**Out of scope:** Writing new tests (use `test-driven-development`), fixing architectural issues (use `systematic-refactoring`), profiling with external tools.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `preferred-pattern-catalog.md` | Loads detailed guidance from `preferred-pattern-catalog.md`. |
| tasks related to this reference | `blind-spot-taxonomy.md` | Loads detailed guidance from `blind-spot-taxonomy.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| fixing review feedback | `fix-strategies.md` | Loads detailed guidance from `fix-strategies.md`. |
| tests | `load-test-scenarios.md` | Loads detailed guidance from `load-test-scenarios.md`. |
| tasks related to this reference | `quality-catalog.md` | Loads detailed guidance from `quality-catalog.md`. |
| tasks related to this reference | `quick-reference.md` | Loads detailed guidance from `quick-reference.md`. |

## Instructions

### Phase 1: SCAN

**Goal**: Identify quality issues in target test code.

**Step 1: Locate test files** -- Grep/Glob for test files. If user pointed to specific files, start there. Patterns: `*_test.go`, `test_*.py`/`*_test.py`, `*.test.ts`/`*.spec.ts`/`*.test.js`/`*.spec.js`.

**Step 2: Read CLAUDE.md** -- Check project-specific testing conventions before flagging issues. Some projects intentionally deviate from general best practices.

**Step 3: Classify quality issues** -- Scan each file for these 10 categories (detailed examples in `references/preferred-pattern-catalog.md`):

| # | Pattern to Fix | Detection Signal |
|---|-------------|-----------------|
| 1 | Testing implementation details | Asserts on private fields, spy on private methods |
| 2 | Over-mocking / brittle selectors | Mock setup > 50% of test code, CSS nth-child |
| 3 | Order-dependent tests | Shared mutable state, class-level variables |
| 4 | Incomplete assertions | `!= nil`, `> 0`, `toBeTruthy()`, no value checks |
| 5 | Over-specification | Exact timestamps, hardcoded IDs, every default field |
| 6 | Ignored failures | `@skip`, `.skip`, `xit`, empty catch, `_ = err` |
| 7 | Poor naming | `testFunc2`, `test_new`, `it('works')` |
| 8 | Missing edge cases | Only happy path, no empty/null/boundary/error tests |
| 9 | Slow test suites | Full DB reset per test, no parallelization |
| 10 | Flaky tests | `sleep()`, `time.Sleep()`, unsynchronized goroutines |

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

**Goal**: Rank findings by impact.

**Priority order:**
1. **HIGH** - Flaky tests, order-dependent, ignored failures (erode trust)
2. **MEDIUM** - Over-mocking, incomplete assertions, missing edge cases (false confidence)
3. **LOW** - Poor naming, over-specification, slow suites (maintenance burden)

**Constraint: Fix one pattern at a time.** Bulk fixes miss context-specific nuances and cause regressions.

**Constraint: Preserve test intent.** Maintain original test coverage scope.

**Constraint: Prevent over-engineering.** Fix the specific issue or delete and rewrite. Institutional knowledge lives in existing tests.

**Gate**: Findings ranked. User agrees on scope. Proceed only when gate passes.

### Phase 3: FIX

**Goal**: Apply targeted fixes to identified issues.

**Step 1: For each issue (highest priority first):**

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

**Step 2: Apply fix** -- Point to actual code, not abstract descriptions. Guide toward behavior testing:
- Test asserts on private fields -> Test the public behavior those fields enable
- Test spies on `_getUser()` -> Test what happens when user exists or doesn't
- Test checks exact regex -> Test that validation succeeds/fails for representative inputs

Change only what fixes the anti-pattern. Consult `references/fix-strategies.md` for language-specific patterns.

**Step 3: Run tests after each fix** -- Run fixed test first, then full file/package. If a fix breaks a previously-passing test, investigate before proceeding.

**Gate**: Each fix verified individually. Tests pass after each change.

### Phase 4: VERIFY

**Goal**: Confirm all fixes work together.

**Step 1**: Run full test suite -- all pass.

**Step 2**: Run previously-flaky tests 3x:
- Go: `go test -count=3 -run TestFixed ./...`
- Python: `pytest --count=3 tests/test_fixed.py`
- JS: Run test file 3 times sequentially

**Step 3**: Confirm no test accidentally deleted or skipped. Compare test count before/after. Search for new `@skip`/`.skip` annotations.

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

See `references/quality-catalog.md` for all 10 anti-patterns (signals, why problematic, fixes).

---

## Error Handling

See `references/error-handling.md` for ambiguous patterns, fixes that change behavior, and suites with hundreds of issues.

---

## References

See `references/quick-reference.md` for quick reference table, red flags, and TDD relationship notes.

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/quality-catalog.md`: All 10 anti-patterns
- `${CLAUDE_SKILL_DIR}/references/error-handling.md`: Ambiguous patterns and large-scale cleanup
- `${CLAUDE_SKILL_DIR}/references/quick-reference.md`: Quick reference, red flags, TDD relationship
- `${CLAUDE_SKILL_DIR}/references/preferred-pattern-catalog.md`: Code examples for all 10 anti-patterns (Go, Python, JavaScript)
- `${CLAUDE_SKILL_DIR}/references/fix-strategies.md`: Language-specific fix patterns
- `${CLAUDE_SKILL_DIR}/references/blind-spot-taxonomy.md`: 6-category taxonomy of what high-coverage suites miss (concurrency, state, boundaries, security, integration, resilience)
- `${CLAUDE_SKILL_DIR}/references/load-test-scenarios.md`: 6 load test scenario types with configurations
