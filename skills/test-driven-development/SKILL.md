---
name: test-driven-development
user-invocable: false
description: "RED-GREEN-REFACTOR cycle with strict phase gates for TDD."
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
  pairs_with:
    - verification-before-completion
    - testing-preferred-patterns
    - vitest-runner
---

# Test-Driven Development (TDD) Skill

Enforce RED-GREEN-REFACTOR for all code changes. Tests written before implementation, verified to fail for the right reasons, maintained through disciplined cycles.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| tasks related to this reference | `phase-guidance.md` | Loads detailed guidance from `phase-guidance.md`. |

## Instructions

Read and follow repository CLAUDE.md files before starting any TDD cycle. Local conventions (test frameworks, directory layout, naming) override defaults.

Full phase guidance (steps, rationale, code examples, language commands) lives in [references/phase-guidance.md](references/phase-guidance.md). Load when you need detailed instructions. Sections below are the lean phase skeleton plus mandatory gates.

### Phase 1: Write a Failing Test (RED)

Write a test describing desired behavior before any implementation. Use specific assertions, descriptive names, Arrange-Act-Assert, one concept per test. Run the test and show full output. Details: [references/phase-guidance.md](references/phase-guidance.md).

#### RED Phase Gate

Proceed to GREEN only after all true:
- [ ] Test file created and saved
- [ ] Test executed
- [ ] Output shows FAILURE (not syntax/import error)
- [ ] Failure message indicates missing implementation

### Phase 2: Verify Failure Reason (RED Verification)

The test must fail because the feature is not implemented, NOT because of syntax errors, import errors, wrong test setup, or unrelated failures. Expected patterns and recovery steps: [references/phase-guidance.md](references/phase-guidance.md).

### Phase 3: Implement Minimum Code (GREEN)

Write ONLY enough code to make the failing test pass. No extra features. Hardcoded values OK initially. Details: [references/phase-guidance.md](references/phase-guidance.md).

### Phase 4: Verify Test Passes (GREEN Verification)

Run the test and full suite; show complete output. Never summarize. Debug guidance: [references/phase-guidance.md](references/phase-guidance.md).

#### GREEN Phase Gate

Proceed to REFACTOR only after all true:
- [ ] Implementation code written
- [ ] New test executed and shows PASS
- [ ] Full test suite executed
- [ ] No other tests broken

### Phase 5: Refactor (REFACTOR)

Improve code quality without changing behavior. Establish green baseline first, refactor incrementally, run tests after every step. Test behavior, not internals. Decision criteria and examples: [references/phase-guidance.md](references/phase-guidance.md).

#### REFACTOR Phase Gate

Mark complete only after all true:
- [ ] All refactoring changes saved
- [ ] Full test suite executed
- [ ] ALL tests pass (not just the new one)
- [ ] Code quality evaluated against criteria table

### Phase 6: Commit

Commit test and implementation together as atomic unit. Run full suite, commit with descriptive message, clean up temporary files. Report facts without self-congratulation.

### Cycle Discipline

Each feature gets its own RED-GREEN-REFACTOR cycle. Do not batch multiple features into one cycle. Examples: [references/phase-guidance.md](references/phase-guidance.md).

## Reference Material

- [references/phase-guidance.md](references/phase-guidance.md) -- Full phase steps, rationale, code examples, Arrange-Act-Assert, language-specific testing commands
- [references/error-handling.md](references/error-handling.md) -- Symptoms, causes, solutions for stuck cycles
- [references/examples.md](references/examples.md) -- Language-specific TDD examples (Go, Python, JavaScript)

## Error Handling

Load [references/error-handling.md](references/error-handling.md) when a cycle is stuck. Covers: test passes before implementation, test fails for wrong reason, tests pass but feature does not work, refactoring breaks tests.
