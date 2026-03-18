---
name: code-linting
user-invocable: false
description: |
  Run Python (ruff) and JavaScript (Biome) linting, formatting, and code
  quality checks with auto-fix support. Use when code needs linting,
  formatting, or style checking before commits. Use for "lint", "format",
  "ruff", "biome", "code style", or "check quality". Do NOT use for
  comprehensive code review (use systematic-code-review).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
version: 2.0.0
---

# Code Linting Skill

Unified linting workflow for Python (ruff) and JavaScript (Biome).

## Operator Context

This skill operates as an operator for code quality enforcement, configuring Claude's behavior for consistent linting and formatting across Python and JavaScript codebases.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project-specific linting rules override defaults.
- **Over-Engineering Prevention**: Only run requested linters and fixes. Don't add custom rules, configuration changes, or additional tooling without explicit request.
- **Show complete linter output**: NEVER summarize as "no issues found" - display actual command output
- **Run both Python and JS linting**: When project has both languages, lint both (unless user specifies otherwise)
- **Use project-specific configs**: Always use pyproject.toml/biome.json settings, never override
- **Preserve line width settings**: Respect the line width configured in project tools

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- **Temporary File Cleanup**: Remove any temporary lint report files or cache files created during execution at task completion.
- **Auto-fix safe issues**: Apply `--fix` flag for formatting and import ordering issues
- **Check before commit**: Verify code passes linting before suggesting commit
- **Report all categories**: Show errors, warnings, and style issues together
- **Suggest manual fixes**: For issues that can't be auto-fixed, explain how to resolve

### Optional Behaviors (OFF unless enabled)
- **Strict mode**: Treat warnings as errors (fail on any issue)
- **Single language only**: Lint only Python or only JavaScript when requested
- **Format only**: Skip linting, only run formatting
- **Ignore specific rules**: Disable particular lint rules for edge cases

## What This Skill CAN Do
- Run ruff check/format for Python codebases
- Run Biome check/format for JavaScript/TypeScript codebases
- Auto-fix safe issues (import ordering, formatting)
- Show complete linter output for review
- Use project-specific configurations (pyproject.toml, biome.json)

## What This Skill CANNOT Do
- Override project linter configurations without explicit request
- Summarize linter output (must show full command output)
- Run linters for languages other than Python and JavaScript/TypeScript
- Fix complex logic issues (only style/formatting/import issues)
- Skip reading linter output before applying auto-fixes

## Error Handling

### Error: "ruff not found"
**Cause**: Virtual environment not activated or ruff not installed
**Solution**:
- Use virtual environment path: `./venv/bin/ruff` or `./env/bin/ruff`
- Or install globally: `pip install ruff`
- Or use pipx: `pipx run ruff check .`

### Error: "biome not found"
**Cause**: Biome not installed in project
**Solution**: Run `npx @biomejs/biome` to use npx-based execution

### Error: "Configuration file not found"
**Cause**: Running from wrong directory
**Solution**: cd to project root where pyproject.toml/biome.json exist

## Quick Reference

### Python (ruff)

```bash
# Navigate to your project
cd /path/to/your/project

# Check for issues (use project's venv if available)
ruff check .
# or with virtual env: ./venv/bin/ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .

# Check formatting only (no changes)
ruff format --check .
```

### JavaScript (Biome)

```bash
# Navigate to your project
cd /path/to/your/project

# Check for issues
npx @biomejs/biome check src/

# Auto-fix issues
npx @biomejs/biome check --write src/

# Format only
npx @biomejs/biome format --write src/
```

### Combined Commands (if Makefile configured)

```bash
make lint       # Check both Python and JS
make lint-fix   # Fix both Python and JS
```

## Configuration Files

| Tool | Config | Typical Line Width |
|------|--------|-------------------|
| ruff | pyproject.toml | 88-120 |
| biome | biome.json | 80-120 |

## Common Fixes

### Python
- Unused import (F401): Remove or use the import
- Import order (I001): Run `ruff check --fix`
- Line too long (E501): Break into multiple lines or adjust line-length config

### JavaScript
- noVar: Replace `var` with `let`/`const`
- useConst: Use `const` for unchanging values
- noDoubleEquals: Use `===` instead of `==`

## Anti-Patterns

### Anti-Pattern 1: Running Linter Without Reading Output

**What it looks like:**
```bash
$ ruff check .
$ # Immediately running --fix without reviewing issues
$ ruff check --fix .
```

**Why it's wrong:**
- May auto-fix issues that need manual review
- Misses understanding of what violations exist
- Can introduce unintended changes (e.g., removing imports still needed)

**Do this instead:**
1. Read the complete linter output first
2. Understand what violations exist and their severity
3. Decide which fixes are safe to automate
4. Apply targeted fixes or manual corrections

### Anti-Pattern 2: Applying Auto-Fixes Blindly

**What it looks like:**
```bash
$ ruff check --fix .
# All files changed
$ git add . && git commit -m "lint fixes"
# Didn't review what changed
```

**Why it's wrong:**
- Auto-fixes might remove imports you still need
- Could reformat code in ways that reduce readability for specific cases
- May introduce subtle bugs (e.g., changing variable shadowing)

**Do this instead:**
1. Run `ruff check --fix .`
2. Review the diff: `git diff`
3. Verify changes are correct and safe
4. Revert any problematic auto-fixes
5. Then commit with understanding of what changed

### Anti-Pattern 3: Summarizing Linter Output

**What it looks like:**
```
User: "Lint the code"
Assistant: "I ran the linter and found 3 issues. All fixed!"
```

**Why it's wrong:**
- User can't see what violations existed
- Can't verify fixes were appropriate
- Hides important details about code quality

**Do this instead:**
Show complete command output:
```bash
$ ruff check .
src/main.py:10:1: F401 [*] `os` imported but unused
src/utils.py:25:80: E501 Line too long (95 > 88 characters)
Found 2 errors.
[*] 1 fixable with the --fix flag

$ ruff check --fix .
Fixed 1 error:
src/main.py:10:1: F401 Removed unused import `os`
```

## Workflow

1. Run linter to check: `ruff check .` / `npx @biomejs/biome check src/`
2. **Review the complete output** to understand violations
3. Auto-fix what's safe: `ruff check --fix .`
4. **Review the diff** to verify auto-fixes are correct
5. Format code: `ruff format .`
6. Review remaining issues and fix manually
7. Commit and push
8. Check CI/GitHub Actions

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
