---
name: vitest-runner
description: "Run Vitest tests and parse results into actionable output."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "run vitest"
    - "JavaScript tests"
    - "TypeScript tests"
    - "vite tests"
    - "vitest output"
  category: testing
  pairs_with:
    - test-driven-development
    - typescript-check
    - e2e-testing
---

# Vitest Test Runner Skill

## Overview

Runs Vitest tests and parses results into structured reports. Executes in non-interactive mode, extracts failure details (test name, assertion error, stack trace), and organizes results by file with timing. Use when tests need running and results need reporting — not for test installation, creation, modification, or auto-fixing.

---

## Instructions

### Step 1: Verify Vitest Project

Confirm Vitest is installed before running. This skill handles only Vitest — not Jest, Mocha, or Playwright.

```bash
# Check for vitest configuration
ls vitest.config.* vite.config.* 2>/dev/null
grep -q "vitest" package.json && echo "vitest found in package.json"
```

If no configuration found, stop and inform the user. Do not install dependencies or configure Vitest.

### Step 2: Run Tests in Non-Interactive Mode

Always use `run` subcommand — bare `npx vitest` starts watch mode, which never completes in a non-interactive shell.

```bash
npx vitest run --reporter=verbose 2>&1
```

For specific files or patterns:

```bash
npx vitest run path/to/test.ts 2>&1
npx vitest run --grep "pattern" 2>&1
```

For coverage (when requested):

```bash
npx vitest run --coverage 2>&1
```

### Step 3: Respect Exit Codes and Parse Complete Output

Exit code is source of truth: 0 = pass, nonzero = fail. Never assume pass from partial output. Show all failures completely.

Extract per test:
- **Test file**: Path
- **Test name**: Full path (describe > it)
- **Status**: PASS / FAIL / SKIP
- **Duration**: Time taken
- **Error detail**: Complete assertion error and stack trace (do not abbreviate)

### Step 4: Format Results as Structured Report

Group failures by test file with complete error details.

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
Cause: Vitest not installed or node_modules missing.
This skill does not install dependencies.
Solution: Check `grep vitest package.json`, then `npm install` or `npm install -D vitest`. Re-run after.

### Error: "No test files found"
Cause: Test file patterns don't match vitest.config include/exclude globs.
Solution: Verify files use correct naming (*.test.ts, *.spec.ts, etc.) and match vitest.config patterns. Show user the config.

### Error: "Test environment not found"
Cause: Missing jsdom or happy-dom dependency for DOM tests.
Solution: Check vitest.config.ts environment setting. Install required devDependency: `npm install -D jsdom` or `npm install -D happy-dom`.

### Error: "Out of memory" (large test suites)
Cause: Too many tests in shared thread pool.
Solution: Run in batches by directory (`npx vitest run src/unit/`), use `--pool=forks` for memory isolation, or `--shard=1/N` to split the suite.

---

## References

- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Key Constraints

**Do not auto-fix tests.** Report failures completely; do not fix them. The test may be correct and the implementation wrong.

**Always use `npx vitest run`, not bare `npx vitest`.** Watch mode is incompatible with non-interactive execution.

**Show all failures completely.** Stack traces, assertion details, and test names are essential. Never abbreviate failure output.

**Respect exit codes as source of truth.** Exit code 0 = pass, nonzero = fail. Do not rely on partial output.
