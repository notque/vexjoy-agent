---
name: python-quality-gate
description: "Python quality checks: ruff, pytest, mypy, bandit in deterministic order."
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
    - "python quality gate"
    - "check python"
    - "pre-commit check"
  category: code-quality
  pairs_with:
    - code-linting
    - test-driven-development
---

# Python Quality Gate Skill

Run four quality tools in deterministic order -- ruff, pytest, mypy, bandit -- and produce a structured pass/fail report with severity-categorized issues and auto-fix commands.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `report-template.md` | Loads detailed guidance from `report-template.md`. |
| tasks related to this reference | `tool-commands.md` | Loads detailed guidance from `tool-commands.md`. |

## Instructions

### Phase 1: Detection and Setup

**Step 1: Read CLAUDE.md and detect project config.**

Read repository CLAUDE.md first. Then detect config:

```bash
ls -la pyproject.toml setup.py setup.cfg mypy.ini .python-version 2>/dev/null
```

Identify Python version, ruff/pytest/mypy config from pyproject.toml. Only validate -- never add tools or features not requested.

**Step 2: Detect source and test directories.**

```bash
ls -d src/ app/ lib/ 2>/dev/null || echo "Source: current directory"
ls -d tests/ test/ 2>/dev/null || echo "Tests: not found"
```

**Step 3: Verify tool availability.**

```bash
ruff --version
pytest --version
mypy --version || echo "mypy not installed (optional)"
bandit --version || echo "bandit not installed (optional)"
```

If ruff or pytest missing, STOP: `pip install ruff pytest pytest-cov`. Do not install automatically or modify config unless explicitly asked.

**Gate**: ruff and pytest available. Project structure identified.

### Phase 2: Execute Quality Checks

Run all checks in fixed order. Show complete command output with exact file paths and line numbers -- never summarize tool output.

**Step 1: Ruff linting.** `ruff check . --output-format=grouped`

**Step 2: Ruff formatting.** `ruff format --check .`

**Step 3: Mypy** (if installed). `mypy . --ignore-missing-imports --show-error-codes`. Skip if unavailable, note in report. Tests check behavior; types check contracts -- both needed.

**Step 4: Pytest.** `pytest -v --tb=short --cov=src --cov-report=term-missing`. Skip if no tests directory, note in report. Never skip tests to manufacture a passing status.

**Step 5: Bandit** (if installed). `bandit -r src/ -ll --format=screen`. Skip if unavailable. Linting finds style, not logic/security bugs.

**Gate**: All available tools run. Full output captured.

### Phase 3: Categorize and Analyze

**Step 1: Categorize issues by severity.**

See `references/tool-commands.md` for complete severity classification tables.

Summary of severity levels:
- **Critical**: F errors (pyflakes), E9xx (syntax), undefined names, test failures, high-severity security
- **High**: E501, E711/E712, F841, N8xx, arg-type/assignment mypy errors
- **Medium**: W warnings, C4xx, no-untyped-def mypy errors
- **Low**: SIM suggestions, UP upgrade suggestions

Prioritize critical over style. Fix critical first, high second; auto-fix for bulk style only after.

**Step 2: Count auto-fixable.** `ruff check . --statistics`. Issues with `[*]` are auto-fixable.

**Step 3: Determine status.** FAIL if: any F errors, test failures, high-severity bandit, mypy errors >10, coverage <80%. PASS otherwise.

**Gate**: All issues categorized. Pass/fail determined.

### Phase 4: Generate Report

Format a structured markdown report. See `references/report-template.md` for the full template.

The report MUST include:
1. Overall PASS/FAIL status
2. Summary table (each tool's status and issue count)
3. Total issues and auto-fixable count
4. Detailed results per tool (issues grouped by severity, then grouped by type and file for readability)
5. Critical issues requiring attention with file:line references
6. Auto-fix commands section
7. Quality metrics: error counts and coverage percentages

Report facts -- raw output, never summarized. No self-congratulation. Full report even for style-only issues. Print to stdout. If `--output {file}` provided, also write to file. Clean up temp files.

**Gate**: Report generated. Task complete.

### Auto-Fix Mode (only when explicitly requested)

Never run without explicit confirmation -- `ruff --fix` can change semantics (import removal, reformatting).

```bash
ruff check . --fix
ruff format .
git diff  # show changes for review
```

Then re-run quality gate to verify.

## Error Handling

| Error | Solution |
|-------|----------|
| `ruff: command not found` | `pip install ruff`. Do not proceed without it. |
| Tests failed (exit code 1) | Expected. Include failures in report, mark FAILED, continue remaining checks. |
| No Python files found | Verify: `ls pyproject.toml src/ tests/`. Run from project root. |
| Mypy cache corruption | `rm -rf .mypy_cache` and retry. If still failing, skip and note. |

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/tool-commands.md`: Severity classifications, expected output formats, CLI flags
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Full structured report template
- `${CLAUDE_SKILL_DIR}/references/pyproject-template.toml`: Complete ruff, pytest, mypy, bandit configuration
