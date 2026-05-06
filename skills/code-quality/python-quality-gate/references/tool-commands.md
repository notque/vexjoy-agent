# Python Quality Gate - Tool Commands & Severity Reference

Quick reference for tool invocations, expected output formats, and issue severity classifications.

## Tool Commands

### Ruff (Linting)

```bash
# Check with grouped output
ruff check . --output-format=grouped

# Check formatting without modifying
ruff format --check .

# Count issues with auto-fix availability
ruff check . --statistics

# Auto-fix (modifies files)
ruff check . --fix
ruff format .

# Fix only import sorting
ruff check . --select I --fix
```

### Pytest

```bash
# Standard run with coverage
pytest -v --tb=short --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_module.py -v --tb=short

# Run with markers
pytest -m "not slow" -v --tb=short
```

### Mypy

```bash
# Standard run
mypy . --ignore-missing-imports --show-error-codes

# Clear cache and retry (for corruption)
rm -rf .mypy_cache && mypy . --ignore-missing-imports --show-error-codes
```

### Bandit

```bash
# Standard security scan
bandit -r src/ -ll --format=screen

# JSON output for parsing
bandit -r src/ -ll --format=json
```

---

## Severity Classifications

### Ruff Issue Severity

| Severity | Rule Codes | Description |
|----------|-----------|-------------|
| **Critical** | F (pyflakes), E9xx | Undefined names, unused imports, syntax errors |
| **High** | E501, E711, E712, F841, N8xx | Line length, None comparisons, unused vars, naming |
| **Medium** | W503, W504, E203, C4xx | Line breaks, whitespace, comprehension improvements |
| **Low** | SIM1xx, UP0xx | Simplification suggestions, syntax upgrades |

### Mypy Issue Severity

| Severity | Error Codes | Description |
|----------|------------|-------------|
| **Critical** | name-defined, call-arg, return-value | Undefined name, wrong args, return mismatch |
| **High** | arg-type, assignment, attr-defined | Type mismatch, incompatible assignment, missing attr |
| **Medium** | no-untyped-def, no-any-return, var-annotated | Missing annotations, Any returns |

### Bandit Issue Severity

| Severity | Description | Action |
|----------|-------------|--------|
| **High** | Immediate security risks (hardcoded passwords, SQL injection) | Must fix before merge |
| **Medium** | Potential security issues (binding all interfaces, weak crypto) | Should fix |
| **Low** | Security best practice suggestions (subprocess usage) | Consider fixing |

---

## Expected Output Formats

### Ruff Check (grouped)

```
src/module.py:
  10:5  E501  Line too long (125 > 120)
  15:1  F401  'os' imported but unused
  23:9  E701  Multiple statements on one line

tests/test_module.py:
  5:1   F811  Redefinition of unused 'test_func'
```

### Ruff Format Check

```
Would reformat: src/module.py
Would reformat: tests/test_helper.py
2 files would be reformatted, 15 files left unchanged
```

### Ruff Statistics

```
45 E501  [*] Line too long
12 F401  [*] `module` imported but unused
8  I001  [*] Import block is un-sorted or un-formatted
[*] 65 fixable with the `--fix` option.
```

Issues marked `[*]` are auto-fixable.

### Mypy

```
src/module.py:45: error: Argument 1 to "process" has incompatible type "str"; expected "int"  [arg-type]
src/utils.py:12: error: Function is missing a return type annotation  [no-untyped-def]
Found 2 errors in 2 files (checked 18 source files)
```

### Pytest

```
tests/test_module.py::test_basic PASSED
tests/test_module.py::test_edge_case FAILED
tests/test_utils.py::test_helper PASSED

---------- coverage: platform linux, python 3.11.5 -----------
Name                Stmts   Miss  Cover   Missing
-------------------------------------------------
src/__init__.py         2      0   100%
src/module.py          45      3    93%   23-25
src/utils.py           18      0   100%
-------------------------------------------------
TOTAL                  65      3    95%
```

### Bandit

```
[bandit]
>> Issue: [B605:start_process_with_a_shell] Starting a process with a shell
   Severity: Low   Confidence: High
   Location: src/runner.py:45

>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   Location: src/server.py:12
```

---

## Pass/Fail Thresholds

| Condition | Result |
|-----------|--------|
| Any ruff F errors | FAIL |
| Any test failures | FAIL |
| Any high-severity bandit issues | FAIL |
| Mypy errors > 10 | FAIL |
| Test coverage < 80% (if coverage enabled) | FAIL |
| All checks pass with no critical/high issues | PASS |
