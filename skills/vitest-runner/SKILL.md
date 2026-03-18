---
name: vitest-runner
description: |
  Run Vitest tests and parse results into actionable output. Use WHEN
  user needs to run JavaScript/TypeScript tests in a Vitest-configured
  project, verify test suites pass, or get structured failure reports.
  Use for "run tests", "vitest", "check if tests pass", or "test results".
  Do NOT use for Jest/Mocha projects, installing dependencies, writing
  new tests, or auto-fixing failing assertions.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
---

# Vitest Test Runner Skill

## Operator Context

This skill operates as an operator for Vitest test execution, configuring Claude's behavior for running tests and parsing results into actionable reports.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before running tests
- **Over-Engineering Prevention**: Only run tests; do not auto-fix failures unless explicitly requested
- **Complete Output**: Show full test output including all failures, never summarize away details
- **Non-Interactive Execution**: Always use `npx vitest run` (not bare `npx vitest` which starts watch mode)
- **Exit Code Respect**: Accurately report pass/fail status based on process exit code

### Default Behaviors (ON unless disabled)
- **Parse Failures**: Extract and format failing test names, errors, and stack traces
- **File Grouping**: Organize results by test file
- **Duration Reporting**: Show test execution times
- **Verbose Reporter**: Use `--reporter=verbose` for detailed output

### Optional Behaviors (OFF unless enabled)
- **Coverage Mode**: Run with `--coverage` flag when user requests coverage
- **Filter Tests**: Run specific test files or name patterns via `--grep`
- **Snapshot Update**: Run with `--update` when user requests snapshot updates

## What This Skill CAN Do
- Run Vitest tests on any Vitest-configured project
- Parse test results into structured, actionable failure reports
- Filter tests by file path, describe block, or test name pattern
- Run tests with coverage reporting
- Report flaky tests when results are inconsistent

## What This Skill CANNOT Do
- Auto-fix tests or modify test code to make tests pass
- Install dependencies (will not run npm install)
- Create or modify vitest.config.ts
- Run non-Vitest test frameworks (Jest, Mocha, Playwright)

---

## Instructions

### Step 1: Verify Vitest Project

Confirm vitest is available before running:

```bash
# Check for vitest configuration
ls vitest.config.* vite.config.* 2>/dev/null
grep -q "vitest" package.json && echo "vitest found in package.json"
```

If no vitest configuration found, stop and inform the user.

### Step 2: Run Tests

Execute Vitest in run mode (non-watch):

```bash
npx vitest run --reporter=verbose 2>&1
```

For specific files or patterns:

```bash
npx vitest run path/to/test.ts 2>&1
npx vitest run --grep "pattern" 2>&1
```

For coverage:

```bash
npx vitest run --coverage 2>&1
```

### Step 3: Parse Output

For each test result, extract:
- **Test file**: Path to the test file
- **Test name**: Full test path (describe > it)
- **Status**: PASS / FAIL / SKIP
- **Duration**: Time taken
- **Error**: Assertion error and stack trace for failures

### Step 4: Present Results

Format output as structured report:

```
=== Vitest Test Results ===

Status: PASS / FAIL (X passed, Y failed, Z skipped)

Failures:
---------
FAIL src/utils/__tests__/helpers.test.ts > parseData > handles null input
  AssertionError: expected null to equal { data: [] }
  - Expected: { data: [] }
  + Received: null
  at src/utils/__tests__/helpers.test.ts:25:10

Summary:
--------
Test Files: 12 passed, 2 failed (14 total)
Tests:      45 passed, 3 failed, 2 skipped (50 total)
Duration:   4.23s
```

---

## Error Handling

### Error: "Cannot find vitest"
Cause: Vitest not installed or node_modules missing
Solution: Check `grep vitest package.json` for presence, then advise user to run `npm install` or `npm install -D vitest`

### Error: "No test files found"
Cause: Test file patterns don't match vitest.config include/exclude globs
Solution: Verify test files exist with correct naming (*.test.ts, *.spec.ts) and check vitest.config include patterns

### Error: "Test environment not found"
Cause: Missing jsdom or happy-dom dependency for DOM tests
Solution: Check vitest.config.ts environment setting; advise installing `@testing-library/jest-dom` or `jsdom` as devDependency

### Error: "Out of memory" (large test suites)
Cause: Too many tests running in shared thread pool
Solution: Run tests in batches by directory, use `--pool=forks` for memory isolation, or `--shard=N/M` for splitting

---

## Anti-Patterns

### Anti-Pattern 1: Running Watch Mode
**What it looks like**: Running `npx vitest` without the `run` subcommand
**Why wrong**: Watch mode is interactive and will never complete in a non-interactive shell
**Do instead**: Always use `npx vitest run`

### Anti-Pattern 2: Hiding Failures
**What it looks like**: Reporting "3 tests failed" without showing which tests or why
**Why wrong**: Users need full failure details (test name, error, stack trace) to fix tests
**Do instead**: Show complete failure output for every failing test

### Anti-Pattern 3: Auto-Fixing Test Assertions
**What it looks like**: Seeing a failing assertion and updating the expected value to match actual
**Why wrong**: The test might be correct and the implementation wrong; needs user judgment
**Do instead**: Present the failure clearly, let user decide if test or code needs fixing

### Anti-Pattern 4: Running Without Project Context
**What it looks like**: Running `npx vitest run` in a directory without package.json
**Why wrong**: Vitest needs project context, dependencies, and configuration
**Do instead**: Verify package.json exists and vitest is configured before running

---

## References

This skill uses these shared patterns:
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Tests probably pass" | Assumption, not evidence | Run the tests |
| "Only one test failed, not important" | Every failure is signal | Report all failures completely |
| "I'll fix the assertion to make it pass" | May hide real bugs | Present failure, let user decide |
| "No need to show stack traces" | Stack traces locate the problem | Always include stack traces |
