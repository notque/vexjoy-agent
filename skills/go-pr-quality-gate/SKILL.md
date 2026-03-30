---
name: go-pr-quality-gate
description: "Run Go quality checks via make check."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
agent: golang-general-engineer
routing:
  triggers:
    - "Go quality"
    - "make check"
    - "Go lint"
  category: code-quality
---

# Go PR Quality Gate Skill

Run `make check` as the single source of truth for Go code quality, parse the output into categorized errors, and suggest actionable fixes. The skill identifies issues and suggests make targets -- it does not fix code automatically, run custom linters, modify Makefiles, run checks incrementally on single files, or interpret business logic errors.

## Instructions

### Step 1: Read Repository CLAUDE.md

Read and follow the repository's CLAUDE.md before doing anything else. It may contain project-specific quality requirements or overrides.

### Step 2: Validate Repository Context

Never skip validation, even if you think you know what the error is -- assumptions miss prerequisites and waste time debugging the environment instead of code quality.

Run the validation script to check prerequisites:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --validate-only
```

The repository needs:
- `go.mod` at root (Go module)
- `Makefile` with a `check` target
- A git repository

Expected success output:
```json
{
  "status": "valid",
  "repository": "/path/to/repo",
  "has_gomod": true,
  "has_makefile": true,
  "is_gomakefilemaker": true
}
```

If validation fails:
- **"Not a Go repository"**: Navigate to a directory with `go.mod`
- **"Makefile not found"**: Repository may need a Makefile-based build workflow setup
- **"Not in git repository"**: Initialize git or navigate to repo root

**Gate**: Validation returns `"status": "valid"`. Proceed only when gate passes.

### Step 3: Run Quality Checks

Always use `make check` through the script -- never bypass it by running golangci-lint, go test, or go vet individually. Different projects configure their quality gates differently, and running tools directly skips whatever the Makefile includes.

Execute the quality gate:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py
```

The script will:
1. Run `make check` (static analysis + tests)
2. Parse output for errors and coverage
3. Categorize any failures
4. Generate an actionable report with fix suggestions

For verbose progress output:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --verbose
```

### Step 4: Interpret Results

Report facts: exact error messages, file locations, exit codes, and coverage percentages. Do not editorialize or self-congratulate on passing checks.

#### Success Scenario

```json
{
  "status": "success",
  "coverage": "87.3%",
  "checks_passed": ["static-check", "test", "coverage"],
  "summary": "All quality checks passed"
}
```

When successful:
1. Acknowledge passing checks
2. Report coverage percentage -- always include it, because silently dropping coverage hides regressions
3. Suggest next steps: view detailed coverage (`open build/cover.html`), create commit, or run specific checks

#### Failure Scenario

```json
{
  "status": "failed",
  "exit_code": 2,
  "errors": {
    "linting": [{"linter": "errcheck", "file": "pkg/api/handler.go", "line": 45, "message": "Error return value not checked", "severity": "high"}],
    "tests": [{"package": "github.com/example/pkg/service", "test": "TestProcessRequest", "error": "expected 200, got 500"}]
  },
  "fix_commands": ["make goimports", "make tidy-deps"]
}
```

When failures occur:
1. **Categorize errors** by type (linting, tests, build, license)
2. **Group linting errors** by linter name (errcheck, gosec, govet, etc.)
3. **Show actionable fixes** using the structured output:
   - Import issues: `make goimports`
   - Dependency issues: `make tidy-deps`
   - License headers: `make license-headers`
   - Specific linter guidance: check `references/common-lint-errors.json`
4. **Provide context**: file paths, line numbers, error descriptions
5. **Report exact exit codes** from make -- never mask or modify them

Keep explanations brief. Report the specific error with its location and the fix suggestion from script output. Only explain further if the user asks -- a quality check is not a tutorial.

### Step 5: Apply Fixes Incrementally

Fix one category at a time. Applying 15 fixes across multiple files simultaneously makes it impossible to verify which fix resolved which error, and if one fix is wrong, everything needs rollback.

For common error patterns, run suggested make targets one at a time:

```bash
# Fix import formatting
make goimports

# Fix dependency issues
make tidy-deps

# Add/update license headers
make license-headers
```

After each fix, re-run quality checks (Step 3) to verify resolution before moving to the next category.

**Gate**: All checks pass (exit code 0). Coverage meets baseline. No linting errors. All tests pass.

### Step 6: Detailed Investigation (Optional)

For complex failures, use specific make targets to isolate the problem:

```bash
# Run only static analysis
make static-check

# Run only tests
make test

# Run specific test with verbose output
go test -v -run TestSpecificTest ./pkg/service

# View HTML coverage report
open build/cover.html
```

Only use individual make targets for focused investigation after `make check` has failed -- not as a substitute for it.

### Advanced Options

Custom coverage threshold enforcement:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --min-coverage 80.0
```

JSON output for automation pipelines:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --format json
```

Combined options for thorough debugging:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --min-coverage 80.0 --verbose
```

### Cleanup

Remove temporary analysis files and debug logs at completion. Keep only files needed for user review.

---

## Error Handling

### Error: "make: *** [check] Error 2"
Cause: One or more quality checks failed (linting, tests, or build)
Solution:
1. Review error categorization in JSON output
2. Apply suggested fixes from `fix_commands` array
3. Check `references/common-lint-errors.json` for specific linter guidance
4. Re-run checks after each fix

### Error: "golangci-lint: command not found"
Cause: Static analysis tools not installed on the system
Solution:
1. Install via package manager: `brew install golangci-lint`
2. Or use project's install script if available
3. Verify with: `golangci-lint --version`

### Error: "coverage: 0.0% of statements"
Cause: No test files exist, or test packages have no executable tests
Solution:
1. Verify test files exist: look for `*_test.go` files
2. Verify tests run independently: `make test`
3. Check that test functions follow `Test` naming convention

### Error: Script Times Out
Cause: Tests hang, infinite loops, or blocking external dependencies
Solution:
1. Run individual targets to isolate: `make static-check`, `make test`
2. Check for hanging tests or external service dependencies
3. Run specific test in isolation: `go test -v -run TestName ./pkg/...`

---

## References

- `${CLAUDE_SKILL_DIR}/references/common-lint-errors.json`: Linter descriptions, severities, and fix suggestions
- `${CLAUDE_SKILL_DIR}/references/makefile-targets.json`: Available make targets and when to use them
- `${CLAUDE_SKILL_DIR}/references/expert-review-patterns.md`: Manual review patterns beyond automated linting
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Detailed usage examples with expected output
