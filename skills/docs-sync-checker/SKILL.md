---
name: docs-sync-checker
description: |
  Deterministic 4-phase documentation drift detector: Scan, Cross-Reference,
  Detect, Report. Use when skills/agents/commands are added, removed, or
  renamed, when README files seem outdated, or before committing documentation
  changes. Use for "check docs", "sync README", "documentation audit", or
  "stale entries". Do NOT use for writing documentation content, improving
  descriptions, or generating new README files.
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
---

# Documentation Sync Checker Skill

## Operator Context

This skill operates as an operator for documentation synchronization workflows, configuring Claude's behavior for automated drift detection between filesystem tools and their README entries. It implements deterministic scanning and comparison -- no AI judgment on content quality, only presence/absence/version verification.

The 4-phase workflow (Scan, Cross-Reference, Detect, Report) ensures systematic coverage. Each phase has a gate that must pass before proceeding. The skill produces a sync score (percentage of tools properly documented) and actionable fix suggestions for every detected issue.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Only scan, compare, and report. No speculative features
- **Deterministic Scanning**: File existence, YAML parsing, and markdown extraction must be deterministic
- **Documentation File Locations**: Check specific files: skills/README.md, agents/README.md, commands/README.md, README.md, docs/REFERENCE.md
- **Sync Rules**: Skills in skills/README.md, agents in agents/README.md, commands in commands/README.md

### Default Behaviors (ON unless disabled)
- **Concise Reporting**: Report facts without self-congratulation; show data, not descriptions
- **Temporary File Cleanup**: Remove helper scripts and debug outputs at task completion
- **Stale Entry Detection**: Flag documented tools that no longer exist in the filesystem
- **Version Mismatch Detection**: Compare YAML frontmatter versions with documented versions
- **Severity Assignment**: HIGH for missing entries, MEDIUM for stale entries, LOW for version mismatches

### Optional Behaviors (OFF unless enabled)
- **Auto-Fix Mode**: Automatically add missing documentation entries (--auto-fix)
- **Strict Mode**: Exit with error code if sync issues found (--strict)
- **JSON Output**: Machine-readable report for CI/CD pipelines (--format json)

## What This Skill CAN Do
- Discover all skills (skills/*/SKILL.md), agents (agents/*.md), and commands (commands/**/*.md)
- Parse YAML frontmatter and extract name, description, version fields
- Parse markdown tables and lists from README files using deterministic parsing
- Detect missing entries (tool exists in filesystem, not documented in README)
- Detect stale entries (documented in README, tool no longer in filesystem)
- Detect version mismatches (YAML version differs from documented version)
- Generate actionable sync reports with exact suggested fixes (markdown rows to add/remove)
- Handle namespaced commands (commands/code/cleanup.md -> /code cleanup)
- Calculate sync score as percentage of tools properly documented
- Support strict mode for CI/CD integration (exit code 1 on issues)

## What This Skill CANNOT Do
- Judge whether descriptions are accurate or helpful (presence only, not quality)
- Generate or improve documentation content (uses YAML description verbatim)
- Resolve markdown merge conflicts in documentation files
- Validate cross-references or internal links between documents
- Track when documentation drift occurred (point-in-time snapshot only)
- Fix semantic inconsistencies between descriptions in different files
- Automatically fix documentation without human review (auto-fix is experimental, requires explicit opt-in)
- **Reason**: This skill is deterministic scanning and comparison. Content generation and quality assessment require different skills.

---

## Instructions

### Phase 1: SCAN

**Goal**: Discover all skills, agents, and commands in the repository filesystem.

**Step 1: Run the scan script**

```bash
python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root $HOME/claude-code-toolkit
```

**Step 2: Validate discovery results**

For each tool type, verify:

Skills (`skills/*/SKILL.md`):
- File has opening `---` and closing `---` YAML delimiters
- YAML contains `name`, `description`, and `version` fields
- `name` field matches directory name (e.g., `skills/code-linting/` has `name: code-linting`)

Agents (`agents/*.md`):
- File has valid YAML frontmatter with `name` field
- Filename (without .md) matches YAML `name` value

Commands (`commands/**/*.md`):
- File exists as markdown in commands/ directory
- Namespaced commands in subdirectories (e.g., `commands/code/cleanup.md`) are detected

**Step 3: Count and verify**

```markdown
## Scan Results
Skills found: [N]
Agents found: [N]
Commands found: [N]
YAML errors: [N] (must be 0 to proceed)
```

**Gate**: All tools discovered, all YAML valid, counts >0 for each type. Do NOT proceed until gate passes.

### Phase 2: CROSS-REFERENCE

**Goal**: Extract documented tools from README files and compare with discovered tools.

**Step 1: Run the documentation parser**

```bash
python3 skills/docs-sync-checker/scripts/parse_docs.py --repo-root $HOME/claude-code-toolkit --scan-results /tmp/scan_results.json
```

**Step 2: Parse each documentation file**

| File | Format | What to Extract |
|------|--------|-----------------|
| `skills/README.md` | Markdown table | Name, Description, Command, Hook columns |
| `agents/README.md` | Table or list | Name, Description fields |
| `commands/README.md` | Markdown list | /command-name - Description items |
| `README.md` | Inline references | Pattern-match `skill: X`, `/command`, `agent-name` |
| `docs/REFERENCE.md` | Section headers | `### tool-name` headers with descriptions |

**Step 3: Build documented-tools registry**

For each documentation file, collect the set of tool names found. This creates a mapping of `{file -> [tool_names]}` that Phase 3 will compare against the filesystem scan.

**Step 4: Verify parse completeness**

- All 5 documentation files found and parsed (warn if any missing)
- No parse errors on table/list structures
- Tool names extracted from each file

**Gate**: All documentation files parsed without errors. Do NOT proceed until gate passes.

### Phase 3: DETECT

**Goal**: Compare discovered tools with documented tools to identify drift.

**Step 1: Compute set differences**

For each tool type and its primary documentation file:
- `missing = filesystem_tools - documented_tools` (tools that exist but are not documented)
- `stale = documented_tools - filesystem_tools` (documented tools that no longer exist)

**Step 2: Check version consistency**

For tools that appear in both sets, compare:
- YAML `version` field vs. documented version (if version is documented)
- Flag mismatches where YAML is authoritative source of truth

**Step 3: Categorize and assign severity**

| Category | Condition | Severity |
|----------|-----------|----------|
| Missing Entry | Tool in filesystem, not in primary README | HIGH |
| Stale Entry | Tool in README, not in filesystem | MEDIUM |
| Version Mismatch | YAML version differs from documented | LOW |
| Incomplete Entry | Documentation missing required fields | LOW |

**Step 4: Record issue details**

For each issue, capture: tool type, tool name, tool path, affected documentation file(s), severity, and suggested fix action.

**Gate**: All issues categorized with severity. Do NOT proceed until gate passes.

### Phase 4: REPORT

**Goal**: Generate human-readable report with actionable fix suggestions.

**Step 1: Run the report generator**

```bash
python3 skills/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --output /tmp/sync-report.md
```

**Step 2: Verify report structure**

Report must include these sections:

1. **Summary** -- Total tools, issue counts by severity, sync score
   ```
   sync_score = (total_tools - total_issues) / total_tools * 100
   ```

2. **HIGH Priority: Missing Entries** -- For each missing tool, provide the exact markdown row/item to add to the appropriate README file

3. **MEDIUM Priority: Stale Entries** -- For each stale tool, identify the file and line to remove

4. **LOW Priority: Version Mismatches** -- For each mismatch, show YAML version (authoritative) vs. documented version

5. **Files Checked** -- List each documentation file with count of tools parsed from it

**Step 3: Validate actionability**

Every issue in the report must have a concrete suggested fix. No issue should say "review manually" without specifying what to review and where.

**Step 4: Report format for missing entries**

For each missing skill, generate a suggested table row:
```markdown
| skill-name | Description from YAML | `skill: skill-name` | - |
```

For each missing agent, generate a suggested table row:
```markdown
| agent-name | Description from YAML |
```

For each missing command, generate a suggested list item:
```markdown
- `/command-name` - Description from command file
```

**Gate**: Report generated with actionable suggestions for every issue.

---

## Examples

### Example 1: New Skill Missing from README
User created `skills/my-new-skill/SKILL.md` but forgot to update `skills/README.md`.
Actions:
1. SCAN discovers `my-new-skill` in filesystem
2. CROSS-REFERENCE parses skills/README.md, does not find `my-new-skill`
3. DETECT flags as HIGH severity missing entry
4. REPORT suggests exact table row to add to skills/README.md

### Example 2: Removed Agent Still Documented
User deleted `agents/old-agent.md` but `agents/README.md` still lists it.
Actions:
1. SCAN does not find `old-agent` in filesystem
2. CROSS-REFERENCE finds `old-agent` in agents/README.md
3. DETECT flags as MEDIUM severity stale entry
4. REPORT suggests removing the row from agents/README.md

### Example 3: Version Bump Without Doc Update
User updated `version: 2.0.0` in `skills/code-linting/SKILL.md` but `docs/REFERENCE.md` still shows `Version: 1.5.0`.
Actions:
1. SCAN reads YAML version as 2.0.0
2. CROSS-REFERENCE reads documented version as 1.5.0 from docs/REFERENCE.md
3. DETECT flags as LOW severity version mismatch
4. REPORT suggests updating version line in docs/REFERENCE.md to 2.0.0

### Example 4: Batch Changes After Refactor
User created 3 new skills and deleted 2 old ones in a refactoring PR.
Actions:
1. SCAN discovers 3 new skills in filesystem, does not find 2 removed skills
2. CROSS-REFERENCE finds 2 stale entries and 3 absent entries in skills/README.md
3. DETECT flags 3 HIGH (missing) + 2 MEDIUM (stale) issues
4. REPORT provides exact table rows to add and identifies rows to remove

---

## Error Handling

### Error: "YAML Parse Error"
Cause: Invalid frontmatter -- missing `---` delimiters, tabs instead of spaces, or missing required fields
Solution:
1. Check file has opening `---` on line 1 and closing `---` after YAML block
2. Verify no tab characters in YAML (spaces only)
3. Confirm required fields present: `name`, `description`, `version`
4. Validate manually: `head -20 {file_path}` and check syntax

### Error: "Documentation File Not Found"
Cause: Expected README file does not exist at expected path
Solution:
1. Verify --repo-root path is correct
2. Check that skills/README.md, agents/README.md, commands/README.md exist
3. If file is legitimately missing, create a placeholder with the expected table/list header
4. Re-run scan after creating placeholder

### Error: "No Tools Discovered"
Cause: Wrong --repo-root path, empty directories, or no SKILL.md files
Solution:
1. Verify the repo root path points to the correct repository
2. Confirm skills/, agents/, commands/ directories exist and are not empty
3. Check that skill directories contain SKILL.md (not just other files)
4. Run with --debug flag for verbose discovery output

### Error: "Markdown Parse Error"
Cause: Table missing separator row, mismatched column counts, or malformed list items
Solution:
1. Check table has header row, separator row (`|---|---|`), and data rows
2. Verify all rows have the same number of pipe-delimited columns
3. For lists, verify consistent format: `- /command - Description`
4. See `references/markdown-formats.md` for complete format specifications

---

## Anti-Patterns

### Anti-Pattern 1: Creating Tools Without Documentation
**What it looks like**: `git commit -m "Add new skill"` without updating skills/README.md
**Why wrong**: Documentation drifts from reality; users cannot discover the tool
**Do instead**: Run docs-sync-checker before committing; add tool AND documentation in same commit

### Anti-Pattern 2: Removing Tools, Leaving Documentation
**What it looks like**: `rm -rf skills/old-skill` followed by commit, but README still lists it
**Why wrong**: Users waste time trying to invoke non-existent tools; erodes trust in docs
**Do instead**: Remove tool files AND documentation entries together in one commit

### Anti-Pattern 3: Manual Edits Without Validation
**What it looks like**: Hand-editing README tables without running sync checker afterward
**Why wrong**: Typos in tool names create phantom entries (documented but non-existent)
**Do instead**: Always validate with docs-sync-checker after manual documentation edits

### Anti-Pattern 4: Ignoring Sync Failures in CI
**What it looks like**: `continue-on-error: true` on the sync check step in GitHub Actions
**Why wrong**: Documentation drift accumulates; the check becomes meaningless
**Do instead**: Run with --strict and let the build fail; fix docs before merging

### Anti-Pattern 5: Updating Version Without Syncing Documentation
**What it looks like**: Bumping `version: 2.0.0` in YAML frontmatter, committing without checking docs
**Why wrong**: Version mismatch creates confusion about which version is deployed; users reference wrong version
**Do instead**: Update YAML version, run sync checker, update all documentation locations in one commit

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I'll update the README later" | Later never comes; drift accumulates | Update docs in the same commit |
| "It's just one missing entry" | One missing entry erodes trust in all docs | Fix immediately |
| "The sync score is still 90%" | 90% means 1 in 10 tools is undocumented | Target 100% |
| "CI will catch it" | Only if CI is configured and not ignored | Verify locally first |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/documentation-structure.md`: Documentation file matrix, required fields per location, cross-reference requirements
- `${CLAUDE_SKILL_DIR}/references/markdown-formats.md`: Expected table/list formats for each README file, parsing rules, common formatting errors
- `${CLAUDE_SKILL_DIR}/references/sync-rules.md`: Synchronization rules, severity levels, deprecation handling, namespace rules
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Before/after examples for adding, removing, updating, and batch documentation changes
- `${CLAUDE_SKILL_DIR}/references/integration-guide.md`: CI/CD setup, pre-commit hooks, auto-fix mode, JSON output, workflow integration
