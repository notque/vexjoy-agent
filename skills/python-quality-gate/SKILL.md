---
name: python-quality-gate
description: |
  Run Python quality checks with ruff, pytest, mypy, and bandit in
  deterministic order. Use WHEN user requests "quality gate", "lint",
  "verify code quality", "check python", or "pre-commit check". Use for
  pre-merge validation, CI/CD gating, or comprehensive code quality
  reports. Do NOT use for single-tool runs (run tool directly), debugging
  runtime bugs (use systematic-debugging), refactoring (use
  systematic-refactoring), or architecture review.
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
agent: python-general-engineer
routing:
  force_route: true
  triggers:
    - "Python quality"
    - "ruff check"
    - "bandit scan"
    - "mypy check"
    - "python lint"
    - "quality gate"
    - "check python"
    - "pre-commit check"
  category: code-quality
---

# Python Quality Gate Skill

## Operator Context

This skill operates as an operator for Python code quality validation workflows, configuring Claude's behavior for automated quality assurance. It runs four tools in deterministic order: ruff, pytest, mypy, bandit.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Only validate code. Never add tools, features, or flexibility not requested
- Run all available quality tools in fixed order: ruff check, ruff format, mypy, pytest, bandit
- Show complete command output with exact file paths and line numbers (never summarize)
- Exit with non-zero status if any critical check fails
- Categorize issues by severity: critical, high, medium, low

### Default Behaviors (ON unless disabled)
- **Report Facts**: Show command output rather than describing it. No self-congratulation.
- **Temporary File Cleanup**: Remove intermediate outputs at completion. Keep final report only if requested.
- Group errors by type and file for readability
- Show suggested auto-fix commands when available
- Calculate and display quality metrics (error counts, coverage percentages)
- Check formatting compliance with ruff format

### Optional Behaviors (OFF unless enabled)
- Auto-fix issues with `--fix` flag (requires explicit request)
- Install missing quality tools automatically
- Modify pyproject.toml or configuration files
- Save report to file with `--output {file}` flag
- Skip specific tools with `--skip-mypy`, `--skip-bandit`, `--skip-tests` flags

## What This Skill CAN Do
- Run all four quality tools in deterministic order with structured output
- Categorize issues by severity and provide auto-fix commands
- Generate structured markdown reports with actionable suggestions
- Calculate pass/fail status based on configurable thresholds
- Detect project configuration from pyproject.toml

## What This Skill CANNOT Do
- Debug runtime bugs (use systematic-debugging)
- Refactor code or make architectural changes (use systematic-refactoring)
- Replace running a single tool when that is all the user needs
- Auto-fix without explicit user confirmation

---

## Prerequisites

### Required Tools
```bash
pip install ruff pytest pytest-cov
```

### Optional Tools (recommended)
```bash
pip install mypy bandit
```

### Expected Project Structure
```
project/
├── pyproject.toml          # Ruff, pytest, mypy config
├── src/ or app/            # Source code
│   └── *.py
├── tests/ or test/         # Test files
│   └── test_*.py
└── .python-version         # Optional Python version
```

See `references/pyproject-template.toml` for complete configuration template.

---

## Instructions

### Phase 1: Detection and Setup

**Step 1: Detect project configuration**

```bash
ls -la pyproject.toml setup.py setup.cfg mypy.ini .python-version 2>/dev/null
```

Identify Python version target, ruff config, pytest config, mypy config from pyproject.toml.

**Step 2: Detect source and test directories**

```bash
ls -d src/ app/ lib/ 2>/dev/null || echo "Source: current directory"
ls -d tests/ test/ 2>/dev/null || echo "Tests: not found"
```

**Step 3: Verify tool availability**

```bash
ruff --version
pytest --version
mypy --version || echo "mypy not installed (optional)"
bandit --version || echo "bandit not installed (optional)"
```

If ruff or pytest are missing, STOP. These are required:
```
ERROR: Required tool not found: {tool_name}
Install with: pip install ruff pytest pytest-cov
```

**Gate**: ruff and pytest available. Project structure identified. Proceed only when gate passes.

### Phase 2: Execute Quality Checks

Run all checks in order, capturing full output for each.

**Step 1: Ruff linting**

```bash
ruff check . --output-format=grouped
```

**Step 2: Ruff formatting check**

```bash
ruff format --check .
```

**Step 3: Type checking with mypy** (if installed)

```bash
mypy . --ignore-missing-imports --show-error-codes
```

Skip and note in report if mypy is not installed.

**Step 4: Run test suite**

```bash
pytest -v --tb=short --cov=src --cov-report=term-missing
```

If no tests directory exists, skip and note in report.

**Step 5: Security scanning with bandit** (if installed)

```bash
bandit -r src/ -ll --format=screen
```

Skip and note in report if bandit is not installed.

**Gate**: All available tools have been run. Full output captured. Proceed to analysis.

### Phase 3: Categorize and Analyze

**Step 1: Categorize issues by severity**

See `references/tool-commands.md` for complete severity classification tables.

Summary of severity levels:
- **Critical**: F errors (pyflakes), E9xx (syntax), undefined names, test failures, high-severity security
- **High**: E501, E711/E712, F841, N8xx, arg-type/assignment mypy errors
- **Medium**: W warnings, C4xx, no-untyped-def mypy errors
- **Low**: SIM suggestions, UP upgrade suggestions

**Step 2: Count auto-fixable issues**

```bash
ruff check . --statistics
```

Issues marked with `[*]` are auto-fixable.

**Step 3: Determine overall status**

FAIL if:
- Any ruff F errors or test failures
- Any high-severity bandit issues
- Mypy errors exceed 10 (configurable)
- Test coverage below 80% (if coverage enabled)

PASS otherwise.

**Gate**: All issues categorized. Pass/fail determined. Proceed to report.

### Phase 4: Generate Report

Format a structured markdown report. See `references/report-template.md` for the full template.

The report MUST include:
1. Overall PASS/FAIL status
2. Summary table (each tool's status and issue count)
3. Total issues and auto-fixable count
4. Detailed results per tool (issues grouped by severity)
5. Critical issues requiring attention with file:line references
6. Auto-fix commands section

Print the complete report to stdout. Never summarize or truncate.

If `--output {file}` flag provided, also write report to file.

**Gate**: Report generated and displayed. Task complete.

---

## Auto-Fix Mode

When user explicitly requests auto-fix:

```bash
ruff check . --fix
ruff format .
```

After auto-fix, show diff and re-run quality gate to verify:
```bash
git diff
```

ALWAYS warn that auto-fix modifies files in place.

---

## Examples

### Example 1: Pre-Merge Quality Check
User says: "Run quality checks before I merge this PR"
Actions:
1. Detect project config and available tools (Phase 1)
2. Run ruff check, ruff format, mypy, pytest, bandit in order (Phase 2)
3. Categorize 12 issues: 0 critical, 3 high, 9 medium (Phase 3)
4. Generate report showing PASSED with 3 high-priority suggestions (Phase 4)
Result: Structured report with actionable fix commands

### Example 2: Quality Gate Failure
User says: "Check code quality on the payments module"
Actions:
1. Detect config, find src/payments/ directory (Phase 1)
2. Run all tools -- pytest shows 2 failures, ruff finds F401 errors (Phase 2)
3. Categorize: 2 critical (test failures), 1 critical (undefined name), 5 medium (Phase 3)
4. Generate FAILED report with critical issues listed first (Phase 4)
Result: FAILED status with prioritized fix list, auto-fix commands for 5 medium issues

---

## Error Handling

### Error: "ruff: command not found"
**Cause**: Ruff is not installed in the current environment
**Solution**: Install with `pip install ruff`. Do not proceed without ruff -- exit with status 2.

### Error: "Tests failed with exit code 1"
**Cause**: pytest found test failures
**Solution**: This is expected behavior, not a tool error. Parse output, include failure details in report, mark overall status as FAILED, continue with remaining checks.

### Error: "No Python files found"
**Cause**: Running from wrong directory or not a Python project
**Solution**: Verify location with `ls pyproject.toml src/ tests/`. Run from project root.

### Error: "Mypy cache corruption"
**Cause**: Stale or corrupted .mypy_cache directory
**Solution**: Clear cache with `rm -rf .mypy_cache` and retry. If mypy continues to fail, skip type checking and note in report.

---

## Anti-Patterns

### Anti-Pattern 1: Auto-Fix Without Review
**What it looks like**: Running `ruff --fix` blindly without reviewing changes
**Why wrong**: Auto-fix can change code semantics (import removal, reformatting)
**Do instead**: Run check-only first, review issues, confirm auto-fix, then `git diff`

### Anti-Pattern 2: Ignoring Critical Issues for Style Fixes
**What it looks like**: Fixing line lengths while undefined names exist
**Why wrong**: Critical issues (F errors, test failures) break functionality; style issues do not
**Do instead**: Fix critical first, high second, use auto-fix for bulk style issues

### Anti-Pattern 3: Skipping Tests to "Make Gate Pass"
**What it looks like**: Using `--skip-tests` to get a passing status
**Why wrong**: Tests verify functionality. Skipping them hides broken code.
**Do instead**: Fix failing tests. Only skip optional tools (mypy, bandit) if genuinely unneeded.

### Anti-Pattern 4: Wrong Tool for the Job
**What it looks like**: Running quality gate to debug a runtime bug
**Why wrong**: Linting finds style issues, not logical bugs
**Do instead**: Use systematic-debugging for runtime bugs, quality gate for pre-commit validation

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Linting passed, code is correct" | Linting finds style issues, not logic bugs | Run tests too |
| "Tests pass, no need for type checking" | Tests check behavior, types check contracts | Run mypy if available |
| "Auto-fix is safe, just run it" | Auto-fix can remove used imports, change semantics | Review changes with git diff |
| "Only style issues, skip the report" | Style issues hide real problems in noise | Generate full report, prioritize by severity |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/tool-commands.md`: Severity classifications, expected output formats, CLI flags
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Full structured report template
- `${CLAUDE_SKILL_DIR}/references/pyproject-template.toml`: Complete ruff, pytest, mypy, bandit configuration
