---
name: code-linting
user-invocable: false
description: "Run Python (ruff) and JavaScript (Biome) linting."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
routing:
  triggers:
    - "lint code"
    - "run ruff"
    - "run biome"
    - "format code"
    - "lint errors"
  category: code-quality
  pairs_with:
    - code-cleanup
    - universal-quality-gate
    - python-quality-gate
---

# Code Linting Skill

Unified linting for Python (ruff) and JavaScript (Biome). Covers check, format, and auto-fix. Only Python and JS/TS -- other languages out of scope.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Python violations, ruff rules, F401/E711/B006/UP errors | `ruff-rules-reference.md` | Routes to the matching deep reference |
| ruff not found, pyproject.toml config, ruff version differences | `ruff-rules-reference.md` | Routes to the matching deep reference |
| JavaScript/TypeScript violations, Biome rules, noVar/useConst/noDoubleEquals | `biome-rules-reference.md` | Routes to the matching deep reference |
| biome not found, biome.json config, migrating from ESLint | `biome-rules-reference.md` | Routes to the matching deep reference |
| Linting CI failures, format check vs lint check differences | `biome-rules-reference.md` | Routes to the matching deep reference |

## Instructions

### 1. Read Project Configuration

Read repository CLAUDE.md first for project-specific rules -- those override all defaults. Locate config files (`pyproject.toml` for ruff, `biome.json` for Biome). Use configs as-is; never override line width, rule sets, or project settings.

### 2. Detect Languages and Run Checks

Lint both Python and JS/TS if both present, unless user requests a single language.

```bash
# Python
ruff check .
# or: ./venv/bin/ruff check .

# JavaScript/TypeScript
npx @biomejs/biome check src/
```

**Always show complete linter output.** Never summarize or describe secondhand.

### 3. Review Output Before Fixing

Read full output and understand violations before applying fixes. Jumping to `--fix` risks removing needed imports or reducing readability.

### 4. Apply Auto-Fixes

Safe categories only: formatting, import ordering, style issues.

```bash
# Python
ruff check --fix .
ruff format .

# JavaScript/TypeScript
npx @biomejs/biome check --write src/
npx @biomejs/biome format --write src/
```

Only run requested linters/fixes. Do not add custom rules or tooling unless asked.

### 5. Review the Diff

```bash
git diff
```

Auto-fixes can remove needed imports, hurt readability, or introduce bugs. Revert problematic changes.

### 6. Fix Remaining Issues Manually

**Python common fixes:**
- F401 (unused import): Remove or use
- I001 (import order): `ruff check --fix`
- E501 (line too long): Break lines or adjust config

**JavaScript common fixes:**
- noVar: Replace `var` with `let`/`const`
- useConst: Use `const` for unchanging values
- noDoubleEquals: Use `===` instead of `==`

### 7. Verify Before Commit

```bash
ruff check .
ruff format --check .
npx @biomejs/biome check src/
```

Report output factually.

### 8. Clean Up

Remove temporary lint report or cache files.

### Combined Commands (if Makefile configured)

```bash
make lint       # Check both
make lint-fix   # Fix both
```

### Configuration Reference

| Tool | Config | Typical Line Width |
|------|--------|-------------------|
| ruff | pyproject.toml | 88-120 |
| biome | biome.json | 80-120 |

### Optional Modes

- **Strict mode**: Treat warnings as errors -- enable when requested
- **Format only**: Skip linting, only format -- enable when requested
- **Ignore specific rules**: Disable particular rules -- enable when requested

## Error Handling

### Error: "ruff not found"
**Cause**: Venv not activated or ruff not installed
**Solution**: Use `./venv/bin/ruff` or `./env/bin/ruff`. Or `pip install ruff`. Or `pipx run ruff check .`

### Error: "biome not found"
**Cause**: Not installed
**Solution**: `npx @biomejs/biome` for npx-based execution

### Error: "Configuration file not found"
**Cause**: Wrong directory
**Solution**: cd to project root where pyproject.toml/biome.json exist

## Reference Loading

| Task type | Reference file |
|-----------|---------------|
| Python violations, ruff rules, F401/E711/B006/UP | `references/ruff-rules-reference.md` |
| ruff not found, pyproject.toml config, versions | `references/ruff-rules-reference.md` |
| JS/TS violations, Biome rules, noVar/useConst/noDoubleEquals | `references/biome-rules-reference.md` |
| biome not found, biome.json config, ESLint migration | `references/biome-rules-reference.md` |
| CI failures, format vs lint check differences | `references/ruff-rules-reference.md` + `references/biome-rules-reference.md` |

## References

- [ruff documentation](https://docs.astral.sh/ruff/)
- [Biome documentation](https://biomejs.dev/)
