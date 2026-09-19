---
name: code-quality
description: "Code quality: cleanup, linting, formatting, quality gates."
user-invocable: true
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
  not_for: "code review with findings (use review), security scanning (use security)"
  triggers:
    - "code cleanup"
    - "clean up code"
    - "find dead code"
    - "stale TODOs"
    - "unused imports"
    - "remove dead code"
    - "find unused"
    - "tidy code"
    - "lint code"
    - "run ruff"
    - "run biome"
    - "format code"
    - "lint errors"
    - "Python quality"
    - "ruff check"
    - "bandit scan"
    - "mypy check"
    - "python lint"
    - "python quality gate"
    - "check python"
    - "pre-commit check"
    - "quality gate"
    - "lint check"
    - "multi-language lint"
    - "code quality check"
    - "technical debt scan"
  category: code-quality
  pairs_with:
    - review
    - testing
    - comment-quality
---

# Code Quality

Four modes. Select by request signal:

| Signal | Mode |
|--------|------|
| Dead code, stale TODOs, unused imports, technical debt | Cleanup |
| Lint Python/JS/TS, run ruff, run biome, format code | Linting |
| Python quality checks, ruff+pytest+mypy+bandit | Python Quality Gate |
| Multi-language quality gate, general "quality check" | Universal Quality Gate |

Default: Python-specific requests run Python Quality Gate. General requests run Universal Quality Gate.

---

## Mode A: Cleanup

Scan for 9 categories of technical debt: stale TODOs, unused imports, dead code, missing type hints, deprecated functions, naming inconsistencies, high complexity, duplicate code, missing docstrings. Follow `references/code-cleanup.md` for the full 3-phase workflow (SCOPE, SCAN, REPORT).

Key principles:
- Read CLAUDE.md first for project conventions
- Scan only what was requested; ask for a target rather than scanning everything
- Exclude vendor/, node_modules/, .venv/, build/, dist/, generated/, .git/
- Prioritize findings by impact/effort: Quick Wins (auto-fixable, <5 min) > Important (bugs, security) > Polish (style)
- Apply auto-fixes only with explicit user permission; check first, fix, review diff, rerun checks

---

## Mode B: Linting

Check or fix Python with Ruff and JavaScript/TypeScript with Biome. Read project instructions, `pyproject.toml`, and `biome.json` first; preserve configured rules.

| Task | Python | JavaScript/TypeScript |
|------|--------|----------------------|
| Check | `ruff check .` | `npx @biomejs/biome check src/` |
| Format check | `ruff format --check .` | Included in Biome check |
| Fix lint | `ruff check --fix .` | `npx @biomejs/biome check --write src/` |
| Format | `ruff format .` | `npx @biomejs/biome format --write src/` |

Use project environment (`./venv/bin/ruff`). If configured, use `make lint` or `make lint-fix`. Check first; apply fixes only within requested scope. Review `git diff`, undo incorrect fixes, rerun checks. Do not change rules or install new tooling to get a pass.

Common fixes: F401 = remove/use import. I001 = sort imports. E501 = shorten lines. Biome `noVar` = use let/const. `useConst` = mark unchanged bindings.

---

## Mode C: Python Quality Gate

Run checks in order. Read repository configuration first; project commands and thresholds override defaults.

**Detect**: Find `pyproject.toml`, `setup.py`, `.python-version`. Check tool availability: ruff and pytest required; mypy and bandit optional unless project requires them.

**Execute**:

| Order | Command | Condition |
|-------|---------|-----------|
| 1 | `ruff check . --output-format=grouped` | Required |
| 2 | `ruff format --check .` | Required |
| 3 | `mypy . --ignore-missing-imports --show-error-codes` | If available |
| 4 | `pytest -v --tb=short --cov=src --cov-report=term-missing` | Coverage only when configured |
| 5 | `bandit -r src/ -ll --format=screen` | If available |

Run all checks even after one fails. Do not skip tests to get a pass.

**Assess**: Prioritize syntax/undefined errors, failing tests, security findings before style. Report per-tool status with actionable file:line diagnostics.

**Fix**: When authorized, run `ruff check . --fix` and `ruff format .`, review diff, rerun checks.

---

## Mode D: Universal Quality Gate

Auto-detect languages and run configured checks. Read repository instructions first.

```bash
python3 ~/.claude/skills/code-quality/universal-quality-gate/scripts/run_quality_gate.py
```

Options: `--staged` (pre-commit), `--lang python` (single language), `--fix` (apply fixes), `-v` (verbose).

Language detection uses `hooks/lib/language_registry.json`:

| Language | Markers | Tools |
|----------|---------|-------|
| Python | pyproject.toml, requirements.txt | ruff, mypy, bandit |
| Go | go.mod | gofmt, golangci-lint, go vet |
| JavaScript | package.json | eslint, biome |
| TypeScript | tsconfig.json | tsc, eslint, biome |
| Rust | Cargo.toml | clippy, cargo fmt |
| Shell | *.sh | shellcheck |

A gate pass means required tools passed; it does not prove tests, builds, or business behavior passed.

---

## Deep References

Load on demand when the signal matches.

| Signal | Reference | Content |
|--------|-----------|---------|
| Full cleanup workflow (9 categories) | `references/code-cleanup.md` | 3-phase cleanup: SCOPE, SCAN, REPORT |
| Language-specific scan commands | `references/cleanup-scan-commands.md` | Per-language commands and expected output |
| Cleanup report formatting | `references/cleanup-report-template.md` | Structured report template |
| Ruff rules, F401/E711/B006 | `references/ruff-rules-reference.md` | Ruff rule reference by category |
| Biome rules, ESLint migration | `references/biome-rules-reference.md` | Biome rule reference by category |
| Python quality tool commands | `references/python-tool-commands.md` | Detailed tool command options |
| Python quality report | `references/python-report-template.md` | Structured report template |
| pyproject.toml template | `references/pyproject-template.toml` | Tool configuration template |
