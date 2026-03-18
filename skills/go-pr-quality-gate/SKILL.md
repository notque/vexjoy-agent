---
name: go-pr-quality-gate
description: |
  Run Go quality checks via make check with intelligent error categorization
  and actionable fix suggestions. Use when user requests "run quality checks",
  "check PR quality", "verify code quality", or "run make check". Use before
  creating commits or during PR review. Do NOT use for non-Go repositories,
  repositories without a Makefile, or manual linter invocation.
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
---

# Go PR Quality Gate Skill

## Operator Context

This skill operates as an operator for Go quality validation workflows, configuring Claude's behavior for automated code quality checking. It implements the **Deterministic Execution** pattern -- `make check` is the single source of truth, the skill parses and categorizes output into actionable feedback.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Only run the checks requested. No speculative analysis, no additional tooling beyond what `make check` provides
- **Deterministic Execution**: Always use `make check` as the single source of truth. No custom check orchestration or tool selection logic
- **Exit Code Fidelity**: Report exact exit codes and status from make. Never mask or modify build tool results
- **Validate First**: Always validate repository prerequisites (go.mod, Makefile) before running checks
- **Incremental Fixes**: Apply one category of fixes at a time, re-run checks after each

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show exact error messages and locations. Be concise but informative
- **Temporary File Cleanup**: Remove temporary analysis files and debug logs at completion. Keep only files needed for user review
- **Error Categorization**: Group errors by type (linting, tests, build) with actionable fix suggestions
- **Coverage Reporting**: Extract and report test coverage percentage from check output
- **Progressive Output**: Stream progress updates as checks run

### Optional Behaviors (OFF unless enabled)
- **Verbose Debug Mode**: Available via `--verbose` flag for troubleshooting
- **Custom Coverage Thresholds**: Available via `--min-coverage` flag for stricter validation
- **JSON-Only Output**: Available via `--format json` for automation pipelines

## What This Skill CAN Do
- Run `make check` and parse results into categorized, actionable output
- Categorize linting, test, and build errors by type and severity
- Extract coverage percentages from test output
- Suggest make targets for common fix patterns (goimports, tidy-deps, license-headers)
- Validate repository prerequisites (go.mod, Makefile, git)
- Generate structured JSON reports for automation

## What This Skill CANNOT Do
- Fix code automatically -- identifies issues and suggests make targets only
- Run custom linters -- only works with linters configured in the repository's `make check` target
- Modify Makefile -- requires an existing `make check` target
- Run checks incrementally -- executes full `make check` suite, not individual file checks
- Interpret business logic errors -- provides technical categorization, not domain debugging

---

## Instructions

### Prerequisites
- Go repository with `go.mod` at root
- Repository has `Makefile` with `check` target
- Works best with Makefile-based build workflow repositories

### Step 1: Validate Repository Context

Run the validation script to check prerequisites:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --validate-only
```

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

### Step 2: Run Quality Checks

Execute comprehensive quality gate:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py
```

The script will:
1. Run `make check` (static analysis + tests)
2. Parse output for errors and coverage
3. Categorize any failures
4. Generate actionable report with fix suggestions

For verbose progress output:
```bash
python3 ~/.claude/skills/go-pr-quality-gate/scripts/quality_checker.py --verbose
```

### Step 3: Interpret Results

#### Success Scenario

Success output format:
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
2. Report coverage percentage
3. Suggest next steps: view detailed coverage (`open build/cover.html`), create commit, or run specific checks

#### Failure Scenario

Failure output format:
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
5. **Suggest incremental fixes**: one make target at a time

### Step 4: Apply Suggested Fixes

For common error patterns, run suggested make targets one at a time:

```bash
# Fix import formatting
make goimports

# Fix dependency issues
make tidy-deps

# Add/update license headers
make license-headers
```

After each fix, re-run quality checks (Step 2) to verify resolution.

**Gate**: All checks pass (exit code 0). Coverage meets baseline. No linting errors. All tests pass.

### Step 5: Detailed Investigation (Optional)

For complex failures, use specific make targets:

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

---

## Examples

### Example 1: Clean Quality Check
User says: "Run quality checks before I create a PR"
Actions:
1. Validate repository context (Step 1)
2. Run `make check` via quality_checker.py (Step 2)
3. Report all checks passed with coverage percentage (Step 3)
4. Suggest creating commit
Result: Clean quality gate, ready for PR

### Example 2: Linting Failures with Auto-Fix
User says: "Check code quality"
Actions:
1. Validate, run checks -- import and license errors found
2. Report categorized errors with fix commands
3. Run `make goimports` then `make license-headers`
4. Re-run checks to verify resolution
Result: Issues fixed incrementally, all checks pass

### Example 3: Test Failures
User says: "Why are the checks failing?"
Actions:
1. Run quality checks -- test failures detected
2. Report failing test names and packages
3. Suggest running specific test with verbose output for details
4. After user fixes, re-run to verify
Result: Test failures identified with actionable debug steps

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

## Anti-Patterns

### Anti-Pattern 1: Running Checks Without Validation
**What it looks like**: Immediately running quality_checker.py without checking for go.mod and Makefile
**Why wrong**: Fails with cryptic errors. Wastes time debugging environment instead of code quality.
**Do instead**: Always run Step 1 validation first. The `--validate-only` flag exists for this purpose.

### Anti-Pattern 2: Fixing All Errors Simultaneously
**What it looks like**: "I see 15 linting errors, let me fix them all at once across multiple files"
**Why wrong**: Multiple concurrent changes are hard to review. If one fix is wrong, all changes need rollback. Cannot verify which fix resolved which error.
**Do instead**: Apply one category of fixes at a time. Run `make goimports`, re-run checks, then fix next category.

### Anti-Pattern 3: Bypassing make check with Individual Tools
**What it looks like**: Running golangci-lint, go test, go vet separately instead of `make check`
**Why wrong**: Bypasses repository's configured quality gates. May miss checks the Makefile includes. Different projects have different configurations.
**Do instead**: Always use `make check` as single source of truth. Only run individual make targets for focused investigation after a check fails.

### Anti-Pattern 4: Ignoring Coverage in Results
**What it looks like**: "All tests pass!" without mentioning that coverage dropped from 85% to 45%
**Why wrong**: Coverage regression indicates untested code paths. New code without tests reduces overall quality.
**Do instead**: Always report coverage percentage. Highlight changes if baseline is known. Use `--min-coverage` for threshold enforcement.

### Anti-Pattern 5: Over-Explaining Linter Errors
**What it looks like**: Writing paragraphs about Go error handling philosophy when errcheck reports an unchecked return
**Why wrong**: User asked for quality check, not a tutorial. The script already provides fix suggestions. Delays actionable response.
**Do instead**: Report the specific error with location, show the fix suggestion from script output, explain only if the user asks.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "make check is slow, I'll just run go vet" | Skips configured quality gates | Run full `make check` |
| "Coverage is fine, no need to report it" | Hides regression information | Always report coverage |
| "I know what the error is, skip validation" | Assumptions miss prerequisites | Validate repository first |
| "One big fix is faster than incremental" | Can't verify individual fixes | Fix one category at a time |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/common-lint-errors.json`: Linter descriptions, severities, and fix suggestions
- `${CLAUDE_SKILL_DIR}/references/makefile-targets.json`: Available make targets and when to use them
- `${CLAUDE_SKILL_DIR}/references/expert-review-patterns.md`: Manual review patterns beyond automated linting
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Detailed usage examples with expected output
