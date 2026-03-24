---
name: universal-quality-gate
description: |
  Multi-language code quality gate with auto-detection and language-specific
  linters. Use when user asks to "run quality checks", "quality gate",
  "lint all", "check everything", "pre-commit checks", or "is this code
  ready to commit". Use for verifying code quality across polyglot repos.
  Do NOT use for single-language linting (use code-linting) or comprehensive
  code review (use systematic-code-review).
version: 2.0.0
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
  category: code-quality
---

# Universal Quality Gate Skill

Language-agnostic code quality checking system. Automatically detects project languages via marker files and runs appropriate linters, formatters, and static analysis tools for each detected language.

## Operator Context

This skill operates as an operator for multi-language code quality enforcement, configuring Claude's behavior to run comprehensive quality checks across any codebase. It implements a **Detect, Check, Report** pattern with graceful degradation for unavailable tools.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default skill behaviors.
- **Over-Engineering Prevention**: Only run tools that are configured and available. Do not add new tools, languages, or checks unless explicitly requested. Keep quality checks focused on what is already defined in language_registry.json.
- **Auto-detect languages**: Scan for marker files (go.mod, package.json, pyproject.toml, Cargo.toml, etc.)
- **Show complete output**: Display full linter output, never summarize as "no issues"
- **Graceful degradation**: Skip unavailable tools without failing the entire gate
- **Non-blocking for optional tools**: Only fail on required tool failures

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it.
- **Temporary File Cleanup**: Remove any temporary files or cache files created during quality gate execution at task completion.
- **Check all detected languages**: Run tools for every language found
- **Include pattern checks**: Scan for anti-patterns (silent except, debug prints, TODOs)
- **Verbose output**: Show file paths and line numbers for all issues
- **Exit with status code**: Return non-zero if any required check fails

### Optional Behaviors (OFF unless enabled)
- **Fix mode**: Auto-fix issues instead of just reporting (`--fix`)
- **Staged only**: Only check git staged files (`--staged`)
- **Single language**: Focus on one language only (`--lang python`)
- **Skip patterns**: Disable pattern matching (`--no-patterns`)

## What This Skill CAN Do
- Auto-detect project languages from marker files and run all configured linters
- Run language-specific lint, format, type-check, and security tools
- Auto-fix safe issues when `--fix` flag is used
- Check only staged files for faster pre-commit validation
- Report issues with file paths, line numbers, and severity
- Gracefully skip unavailable tools while still running available ones

## What This Skill CANNOT Do
- Install missing linter tools (reports them as skipped)
- Catch logic bugs, race conditions, or architectural problems (use tests and code review)
- Replace comprehensive code review (use systematic-code-review)
- Add new languages without registry configuration (use language_registry.json)
- Override project-specific linter configurations

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

### Step 1: Run Quality Gate

Execute the quality gate check:

```bash
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py
```

Common options:
```bash
# Fix issues automatically
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --fix

# Only check staged files
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --staged

# Verbose output
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py -v

# Check specific language only
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --lang python
```

### Step 2: Interpret Results

**Success Output:**
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

**Failure Output:**
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

### Step 3: Fix Issues

Run with `--fix` to auto-correct fixable issues, then re-run to verify:

```bash
# Auto-fix
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py --fix

# Verify fixes
python3 ~/.claude/skills/universal-quality-gate/scripts/run_quality_gate.py
```

### Step 4: Review and Commit

After quality gate passes:
1. Review auto-fix changes with `git diff`
2. Run project tests to catch logic regressions
3. Commit with descriptive message

**Gate**: Quality gate passes with zero required-tool failures. Proceed only when gate passes.

---

## Examples

### Example 1: Pre-Commit Check
User says: "Check if this code is ready to commit"
Actions:
1. Run quality gate with `--staged` to check only staged files
2. Review output for failures and warnings
3. Use `--fix` for auto-fixable issues, manually fix the rest
4. Re-run quality gate to confirm all checks pass
Result: Clean quality gate, ready to commit

### Example 2: Full Repo Audit
User says: "Run quality checks on everything"
Actions:
1. Run quality gate without flags to scan all detected languages
2. Review per-language tool results and pattern matches
3. Triage issues by severity: required-tool failures first, then warnings
4. Fix issues in batches by language, re-run after each batch
Result: Full codebase quality report with actionable issues

---

## Adding New Languages

Add support through the language registry, not by editing the script:

```json
// hooks/lib/language_registry.json
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

The script automatically picks up new entries from the registry.

---

## Error Handling

### Error: "No files to check"
**Cause**: No changed files detected or no language markers found in project
**Solution**:
1. Verify you are in the correct project directory
2. Check that marker files exist (go.mod, package.json, etc.)
3. If checking staged files, ensure files are staged with `git add`

### Error: "Tool not found"
**Cause**: Required linter tool is not installed on the system
**Solution**:
1. Check which tools are missing from the output
2. Install the tool (e.g., `pip install ruff`, `go install golangci-lint`)
3. Or mark the tool as optional in language_registry.json

### Error: "Command timed out"
**Cause**: Tool taking longer than 60-second timeout, often due to large file sets
**Solution**:
1. Use `--staged` to check only changed files
2. Use `--lang` to check one language at a time
3. Check for infinite loops or very large generated files in the project

### Error: "Configuration file conflict"
**Cause**: Conflicting linter configs (e.g., eslint and biome both configured)
**Solution**:
1. Check which tools the project actually uses
2. Disable the unused tool in language_registry.json
3. Ensure project CLAUDE.md specifies preferred tools

---

## Anti-Patterns

### Anti-Pattern 1: Running Without Verifying Prerequisites
**What it looks like**: Running quality gate and getting "Tool not found" for every language
**Why wrong**: Incomplete results give false confidence. Skipped checks mean unchecked code.
**Do instead**: Verify required tools are installed for detected languages before relying on results.

### Anti-Pattern 2: Ignoring Failed Checks
**What it looks like**: Quality gate reports failures, user commits anyway without review
**Why wrong**: Defeats the purpose of quality gates. Introduces known issues into the codebase.
**Do instead**: Review all reported issues. Use `--fix` for auto-fixable issues, then manually address remaining ones.

### Anti-Pattern 3: Full Scan for Small Changes
**What it looks like**: Changed one file, running full quality gate on 1,000+ files across 5 languages
**Why wrong**: Wastes time, surfaces unrelated issues from old code, slows development.
**Do instead**: Use `--staged` to check only changed files, or `--lang` to target the relevant language.

### Anti-Pattern 4: Blind Auto-Fix Without Review
**What it looks like**: Running `--fix` then immediately committing without `git diff`
**Why wrong**: Auto-fix can change code behavior unexpectedly. No human verification of changes.
**Do instead**: Run `--fix`, review the diff, verify changes are correct, then commit with a descriptive message.

### Anti-Pattern 5: Treating Quality Gate as Complete Verification
**What it looks like**: Quality gate passes, user skips tests and code review
**Why wrong**: Quality gates catch syntax and style issues, not logic errors, race conditions, or architectural problems.
**Do instead**: Use quality gate as one layer. Also run tests, perform code review, and consider domain-specific checks.

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

This skill uses the shared quality gate library from `hooks/lib/` for on-demand code quality checking.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase gate standards

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "All tools passed, code is ready" | Linters catch style, not logic | Run tests and review code too |
| "Tool was skipped, probably fine" | Skipped tool = unchecked category | Install tool or accept the gap explicitly |
| "Just formatting issues, not real problems" | Inconsistent formatting causes merge conflicts | Fix formatting before commit |
| "Too many files to check, skip it" | Partial checks give false confidence | Use --staged for focused checking |
