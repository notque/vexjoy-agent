# Python Quality Gate - Report Template

Use this template when generating the structured quality gate report. Replace all `{placeholder}` values with actual data.

---

```markdown
# Python Quality Gate Results

## Overall Status: {PASSED | FAILED}

**Executed**: {timestamp}
**Python Version**: {version}
**Tools**: ruff {version}, pytest {version}, mypy {version}, bandit {version}

---

## Summary

| Check | Status | Issues |
|-------|--------|--------|
| Ruff Linting | {PASS | FAIL} | {N errors} |
| Ruff Formatting | {PASS | FAIL} | {N files need formatting} |
| Type Checking | {PASS | FAIL | SKIP} | {N errors} |
| Tests | {PASS | FAIL | SKIP} | {N failed} |
| Security | {PASS | FAIL | SKIP} | {N issues} |

**Total Issues**: {N}
**Auto-fixable**: {N}

---

## Detailed Results

### Linting (ruff check)

**Status**: {PASS | FAIL}
**Files Checked**: {N}
**Total Issues**: {N}

#### By Severity
- **Critical** (F, E9xx): {N}
- **High** (E5xx, E7xx, N): {N}
- **Medium** (W, C4): {N}
- **Low** (SIM, UP): {N}

#### Auto-fixable
{N} issues can be fixed automatically with:
```bash
ruff check . --fix
```

#### Top Issues
1. {error_code} {description}: {N} occurrences
2. {error_code} {description}: {N} occurrences
3. {error_code} {description}: {N} occurrences

{If no issues: All linting checks passed}

---

### Formatting (ruff format)

**Status**: {PASS | FAIL}

{If issues:}
**Files needing formatting**: {N}

To fix:
```bash
ruff format .
```

{If passed: All files correctly formatted ({N} files checked)}

---

### Type Checking (mypy)

**Status**: {PASS | FAIL | SKIPPED}

{If run:}
**Files Checked**: {N}
**Errors Found**: {N}

#### By Category
- **Critical**: {N} (name-defined, call-arg, return-value)
- **High**: {N} (arg-type, assignment, attr-defined)
- **Medium**: {N} (no-untyped-def, no-any-return)

{If skipped: Type checking skipped: mypy not installed}

---

### Tests (pytest)

**Status**: {PASS | FAIL | SKIPPED}

{If run:}
**Total Tests**: {N}
**Passed**: {N}
**Failed**: {N}
**Skipped**: {N}

#### Test Coverage
- **Overall**: {N%}
- **Missing Coverage**: {N} lines

{If failed tests:}
#### Failed Tests
```
{List failed test names and short failure reasons}
```

{If skipped: Tests skipped: no tests/ directory found}

---

### Security (bandit)

**Status**: {PASS | FAIL | SKIPPED}

{If run:}
**Lines Scanned**: {N}
**Total Issues**: {N}

#### By Severity
- **High**: {N}
- **Medium**: {N}
- **Low**: {N}

{If skipped: Security scanning skipped: bandit not installed}

---

## Issues Requiring Attention

### Critical (Must Fix Before Merge)

{If any:}
1. **{file}:{line}**: {error code} {message}
   Suggested fix: {specific fix command or code change}

{If none: No critical issues found}

### High Priority (Should Fix)

{List high-priority issues with line numbers and suggestions}

---

## Auto-Fix Commands

{If auto-fixable issues:}
Run these commands to fix {N} issues:

```bash
# Fix linting issues (modifies files)
ruff check . --fix

# Fix formatting issues (modifies files)
ruff format .

# Fix import sorting
ruff check . --select I --fix
```

Review changes after auto-fix: `git diff`

---

**Report generated**: {timestamp}
```
