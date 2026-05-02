---
name: code-cleanup
description: "Detect stale TODOs, unused imports, and dead code."
user-invocable: false
argument-hint: "[<path-or-scope>]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
triggers:
  - "code cleanup"
  - "find small improvements"
  - "fix neglected issues"
  - "clean up code"
  - "quality of life fixes"
  - "find TODOs"
  - "stale comments"
  - "unused imports"
  - "technical debt scan"
routing:
  triggers:
    - "find dead code"
    - "stale TODOs"
    - "unused imports"
    - "clean up"
    - "tidy code"
    - "remove dead code"
    - "find unused"
  category: code-quality
  pairs_with:
    - code-linting
    - universal-quality-gate
    - comment-quality
---

# Code Cleanup Skill

Scan for 9 categories of technical debt (TODOs, unused imports, dead code, missing type hints, deprecated functions, naming inconsistencies, high complexity, duplicate code, missing docstrings). Prioritize by impact/effort ratio with time estimates. Generate structured reports with exact file:line references. Apply safe auto-fixes with explicit permission.

### Examples

**Focused cleanup** -- "Clean up the API handlers in src/api/". Scan src/api/ for all 9 categories, prioritize (5 unused imports auto-fixable, 2 stale TODOs >90d, 1 high-complexity function), present tiered report.

**Broad debt scan** -- "What's the state of technical debt?". Identify languages and source dirs, run all scans, group 47 findings into Quick Wins (12), Important (8), Polish (27) with effort estimates.

**Auto-fix request** -- "Fix all unused imports and sort them". Verify tools available, scan F401/I001 only, report 23 unused imports across 8 files, user confirms, apply, test, show diff.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `report-template.md` | Loads detailed guidance from `report-template.md`. |
| tasks related to this reference | `scan-commands.md` | Loads detailed guidance from `scan-commands.md`. |
| tasks related to this reference | `tools.md` | Loads detailed guidance from `tools.md`. |

## Instructions

### Phase 1: SCOPE

**Goal**: Determine scan scope and verify tooling.

**Step 1: Read project context**
- Check for CLAUDE.md, .gitignore, pyproject.toml, go.mod, package.json -- read and follow repository CLAUDE.md first
- Identify primary languages and structure

**Step 2: Determine scan scope**
- User specified directory/type: use exactly that
- User specified only type (e.g., "find unused imports"): scan all source dirs for that type
- Vague request ("clean up code"): ask for target area -- unfocused scans produce overwhelming noise
- Always exclude: vendor/, node_modules/, .venv/, build/, dist/, generated/, .git/
- Respect .gitignore patterns

**Step 3: Verify tool availability**

```bash
command -v ruff && echo "ruff: available" || echo "ruff: MISSING (pip install ruff)"
command -v vulture && echo "vulture: available" || echo "vulture: MISSING (pip install vulture)"
command -v gocyclo && echo "gocyclo: available" || echo "gocyclo: MISSING (go install github.com/fzipp/gocyclo/cmd/gocyclo@latest)"
command -v goimports && echo "goimports: available" || echo "goimports: MISSING (go install golang.org/x/tools/cmd/goimports@latest)"
```

If critical tools missing, offer partial scan. grep and git blame are always available.

**Gate**: Scope defined, languages identified, tool availability known.

### Phase 2: SCAN

**Goal**: Detect all cleanup opportunities using deterministic tools.

Run applicable scans. See `references/scan-commands.md` for full command reference.

**Core scans (all languages)**:
1. **Stale TODOs**: grep TODO/FIXME/HACK/XXX, age every match with git blame -- a 180-day-old TODO about a data race differs fundamentally from yesterday's "TODO: add test"
2. **Unused imports**: ruff (Python), goimports (Go)
3. **Dead code**: vulture (Python), staticcheck (Go)
4. **Complexity**: radon (Python), gocyclo (Go)

**Extended scans (if tools available)**:
5. Missing type hints (ruff --select ANN)
6. Deprecated function usage (staticcheck, grep)
7. Naming inconsistencies (grep for violations)
8. Duplicate code (pylint --enable=duplicate-code)
9. Missing docstrings (ruff --select D)

Collect all output with exact file:line references. For each scan record: finding count, files affected, auto-fixable status.

If a tool is unavailable, note as skipped and continue.

**Gate**: All applicable scans complete with raw output.

### Phase 3: PRIORITIZE

**Goal**: Rank by impact/effort ratio and categorize.

**Step 1: Assign impact and effort**

| Issue Type | Impact | Effort | Priority |
|------------|--------|--------|----------|
| Stale TODOs (>90 days) | High | Low | 8 |
| Unused imports | Medium | Trivial | 10 |
| Deprecated functions | High | Medium | 6 |
| High complexity (>20) | High | High | 5 |
| Dead code | Medium | Low | 7 |
| Missing type hints | Medium | Medium | 5 |
| Duplicate code | High | High | 5 |
| Missing docstrings | Medium | Medium | 5 |
| Naming inconsistencies | Low | Medium | 3 |
| Magic numbers | Low | Low | 5 |

**Step 2: Group into tiers**
- **Quick Wins** (high priority, low effort): Unused imports, stale TODOs, dead code -- auto-fixable first
- **Important** (high impact, medium+ effort): Deprecated functions, high complexity, duplicates
- **Polish** (lower impact): Missing types, docstrings, naming, magic numbers

**Step 3: Estimate effort per tier**

| Issue Type | Time per Instance |
|------------|-------------------|
| Unused imports | 1-2 min (auto-fix) |
| Stale TODOs | 5-15 min |
| Dead code removal | 5-10 min |
| Magic numbers | 2-5 min |
| Missing type hints | 10-20 min/function |
| Missing docstrings | 5-15 min/function |
| Naming fixes | 10-30 min/violation |
| High complexity refactor | 30-120 min/function |
| Duplicate elimination | 30-90 min/instance |
| Deprecated replacement | 15-60 min/usage |

Multiply by instance count for tier totals.

**Gate**: All findings categorized and prioritized with effort estimates.

### Phase 4: REPORT

**Goal**: Present findings in structured, actionable format.

Defaults to read-only. Do not modify files.

Generate report:
1. Executive summary (total issues, tier counts, estimated effort)
2. Quick Wins with auto-fix commands
3. Important issues with suggestions
4. Polish items by type
5. Files sorted by issue count

See `references/report-template.md` for template.

Print complete report to stdout. If `--output {file}` provided, also write to file.

Each finding includes: exact file:line, 3 lines of context, specific fix or auto-fix command, auto-fixable status.

Remove intermediate scan outputs. Keep only final report.

**Gate**: Report delivered with all findings and actionable suggestions.

### Phase 5: FIX (Optional -- explicit permission only)

**Goal**: Apply safe, deterministic fixes.

Never auto-enter this phase -- user expected a report, not modifications.

**Step 1: Confirm scope**

```markdown
Will apply these auto-fixes:
- Remove {N} unused imports across {N} files
- Sort imports in {N} files
- Format {N} files

{N} files will be modified. Proceed? (y/n)
```

**Step 2: Apply auto-fixes (most safe first)**

```bash
# Python
ruff check . --select F401,I001 --fix
ruff format .

# Go
goimports -w .
gofmt -w .
go mod tidy
```

Only safe fixes. Keep variable names, function structure, and semantics unchanged.

**Step 3: Validate**

```bash
# Python
pytest
ruff check .

# Go
go test ./...
go build ./...
golangci-lint run
```

**Step 4: Show diff**

```bash
git diff --stat
git diff
```

```markdown
## Fix Results
- Files modified: {N}
- Imports removed: {N}
- Tests: PASS ({N} tests)
- Lint: CLEAN

Review diff above. Commit when satisfied.
```

**Step 5: Handle failures**

If tests fail after auto-fix:
1. Roll back ALL changes: `git checkout .`
2. Report which test(s) failed and why
3. Suggest incremental fixes (one file at a time) with testing between each

Keep repository in working state.

**Gate**: All fixes applied, tests pass, diff shown. Repository clean and working.

---

## Error Handling

### Error: "Required analysis tool not found"
Cause: ruff, vulture, gocyclo, etc. not installed
Solution: Report missing tools with install commands. Offer partial scan. grep/git blame always available.

### Error: "Not a git repository"
Cause: Cannot use git blame for TODO aging
Solution: Continue but mark all TODO ages "unknown". Warn age-based triage unavailable.

### Error: "Tests fail after auto-fix"
Cause: Auto-fix changed behavior tests depend on
Solution: Roll back (`git checkout .`), report failures, suggest file-by-file incremental fixes.

### Error: "Permission denied modifying files"
Cause: Read-only, locked, or no write permission
Solution: Respect permission boundary. Report unmodifiable files. Provide commands for manual execution.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/scan-commands.md`: Language-specific scan commands and expected output
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Full structured report template
- `${CLAUDE_SKILL_DIR}/references/tools.md`: Tool installation, versions, and capabilities
