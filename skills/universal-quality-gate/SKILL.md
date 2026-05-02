---
name: universal-quality-gate
description: "Multi-language code quality gate with auto-detection and linters."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "quality gate"
    - "lint check"
    - "multi-language lint"
    - "code quality check"
    - "language-agnostic lint"
  category: code-quality
  pairs_with:
    - code-linting
    - verification-before-completion
---

# Universal Quality Gate Skill

Language-agnostic code quality checking. Auto-detects project languages via marker files and runs appropriate linters, formatters, and static analysis.

**Pattern**: Detect, Check, Report.

**Key Principles:**
- Read repository CLAUDE.md first -- project instructions override defaults
- Only run configured tools -- do not add new tools or checks unless explicitly requested
- Show complete output -- never summarize as "no issues"
- Graceful degradation -- skip unavailable tools without failing the gate
- Fail only on required tools

---

## Supported Languages

| Language | Marker Files | Tools |
|----------|--------------|-------|
| Python | pyproject.toml, requirements.txt | ruff, mypy, bandit |
| Go | go.mod | gofmt, golangci-lint, go vet |
| JavaScript | package.json | eslint, biome |
| TypeScript | tsconfig.json | tsc, eslint, biome |
| Rust | Cargo.toml | clippy, cargo fmt |
| Ruby | Gemfile | rubocop |
| Java | pom.xml, build.gradle | PMD |
| Shell | *.sh, *.bash | shellcheck |
| YAML | *.yml, *.yaml | yamllint |
| Markdown | *.md | markdownlint |

## Instructions

### Step 1: Execute Quality Gate

```bash
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py
```

Auto-detects languages, runs tools, reports full output with file paths and line numbers, returns zero if all required tools pass.

### Step 2: Choose Your Flow

**Pre-commit** (fastest):
```bash
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --staged
```

**Auto-fix** (when issues found):
```bash
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --fix
```
Then re-run Step 1 to verify.

**Single language**:
```bash
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --lang python
```

**Verbose**:
```bash
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py -v
```

### Step 3: Interpret Results

**PASSED:**
```
============================================================
 Quality Gate: PASSED
============================================================

Languages: python, javascript
Files: 15

Tool Results:
  [+] python/lint: passed
  [+] python/format: passed
  [-] python/typecheck: skipped (Optional tool not installed)
  [+] javascript/lint: passed
  [+] javascript/format: passed

Quality gate passed: 4/5 tools OK (1 skipped)
```
Skipped optional tools do not block.

**FAILED:**
```
============================================================
 Quality Gate: FAILED
============================================================

Languages: python, go
Files: 8

Tool Results:
  [X] python/lint: FAILED
      hooks/example.py:42:1: F841 local variable 'x' is assigned but never used
      hooks/example.py:56:1: F401 'os' imported but unused
  [+] python/format: passed
  [+] go/format: passed
  [X] go/lint: FAILED
      main.go:15:2: S1000: should use for range instead of for select

Pattern Matches:
  [WARNING] hooks/example.py:78: Silent exception handler - add explanatory comment

Quality gate failed: 2 tool(s) reported issues, 1 error pattern(s)
```
Review [X] failures first. [WARNING] pattern matches are informational.

### Step 4: Resolve Issues

**Auto-fixable**: Run with `--fix`, review with `git diff`, re-run Step 1, commit.

**Manual**: Review each issue, edit files, re-run Step 1, commit.

### Step 5: Commit

Once gate passes: run project tests, commit with descriptive message, proceed to PR/merge.

---

## Extending with New Languages

Modify `hooks/lib/language_registry.json`:

```json
{
  "new_language": {
    "extensions": [".ext"],
    "markers": ["config.file"],
    "tools": {
      "lint": {
        "cmd": "linter {files}",
        "fix_cmd": "linter --fix {files}",
        "description": "Language linter",
        "required": true
      }
    }
  }
}
```

Automatically detected on next run.

---

## Error Handling

### Error: "No files to check"
Cause: No changed files or no language markers found.
Solution: Verify correct directory. Check marker files exist. If using `--staged`, ensure files are staged. Empty projects: expected -- add source files first.

### Error: "Tool not found" / "Required tool not installed"
Cause: Required linter not installed.
Solution: Install the tool:
- Python: `pip install ruff mypy bandit`
- Go: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
- JavaScript: `npm install --save-dev eslint biome`
- Rust: `cargo install clippy`

Alternative: Mark tool as optional in `language_registry.json`.

### Error: "Command timed out"
Cause: Tool exceeds 60s timeout.
Solution: Use `--staged` for changed files only, `--lang` for single language, check for large generated files (.gitignore them).

### Error: "Configuration file conflict"
Cause: Multiple conflicting linter configs (e.g., .eslintrc and biome.json).
Solution: Check which tools the project uses. Mark unused tool as optional or disable it. Consult CLAUDE.md for preferences.

### Pattern Match Warnings
`[WARNING]` entries are informational, not gate failures. Use `--no-patterns` to skip pattern scanning.

### Graceful Degradation
Optional tools appear as `[-] skipped`. Gate still passes. Install tool and re-run if checks needed.

---

## Architecture

```
hooks/lib/
  quality_gate.py        # Shared core library
  language_registry.json # Language configurations

skills/universal-quality-gate/
  SKILL.md               # This file
  scripts/
    run_quality_gate.py  # Skill entry point (thin wrapper)
```

Uses shared quality gate library from `hooks/lib/`.

---

## References

- Language configurations: `hooks/lib/language_registry.json`
- `code-linting`: Single-language lint/format
- `systematic-code-review`: Comprehensive review beyond linting
- `test-driven-development`: Full validation with tests

Quality gates catch syntax and style issues. They do not replace unit/integration tests, code review, or domain-specific validation.
