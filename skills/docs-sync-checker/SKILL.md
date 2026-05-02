---
name: docs-sync-checker
description: "Detect documentation drift against filesystem state."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "check doc drift"
    - "sync documentation"
    - "stale docs"
    - "documentation drift"
    - "README outdated"
  category: documentation
  pairs_with:
    - generate-claudemd
    - codebase-overview
---

# Documentation Sync Checker Skill

Deterministic 4-phase drift detector: Scan, Cross-Reference, Detect, Report. Compares filesystem against README entries. Produces a sync score (percentage of tools documented) and actionable fix suggestions per issue.

Checks presence, absence, and version alignment only -- not description quality, content generation, merge conflicts, cross-references, or drift timing. Suggested fixes use YAML descriptions verbatim.

Optional flags: `--auto-fix` (experimental, explicit opt-in), `--strict` (exit code 1 on issues), `--format json` (machine-readable for CI/CD).

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| documentation work | `documentation-structure.md` | Loads detailed guidance from `documentation-structure.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| tasks related to this reference | `integration-guide.md` | Loads detailed guidance from `integration-guide.md`. |
| tasks related to this reference | `markdown-formats.md` | Loads detailed guidance from `markdown-formats.md`. |
| tasks related to this reference | `sync-rules.md` | Loads detailed guidance from `sync-rules.md`. |

## Instructions

### Phase 1: SCAN

**Goal**: Discover all skills, agents, and commands in the filesystem. All discovery must be deterministic -- no AI judgment on content quality.

**Step 1: Run the scan script**

```bash
python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root $HOME/vexjoy-agent
```

**Step 2: Validate discovery results**

Skills (`skills/*/SKILL.md`):
- File has opening `---` and closing `---` YAML delimiters
- YAML contains `name`, `description`, and `version` fields
- `name` field matches directory name

Agents (`agents/*.md`):
- Valid YAML frontmatter with `name` field
- Filename (without .md) matches YAML `name` value

Commands (`commands/**/*.md`):
- File exists as markdown in commands/ directory
- Namespaced commands in subdirectories detected

**Step 3: Count and verify**

```markdown
## Scan Results
Skills found: [N]
Agents found: [N]
Commands found: [N]
YAML errors: [N] (must be 0 to proceed)
```

**Gate**: All tools discovered, all YAML valid, counts >0 for each type.

### Phase 2: CROSS-REFERENCE

**Goal**: Extract documented tools from README files and compare with discovered tools.

**Step 1: Run the documentation parser**

```bash
python3 skills/docs-sync-checker/scripts/parse_docs.py --repo-root $HOME/vexjoy-agent --scan-results /tmp/scan_results.json
```

**Step 2: Parse each documentation file**

These five files only:

| File | Format | What to Extract |
|------|--------|-----------------|
| `skills/README.md` | Markdown table | Name, Description, Command, Hook columns |
| `agents/README.md` | Table or list | Name, Description fields |
| `commands/README.md` | Markdown list | /command-name - Description items |
| `README.md` | Inline references | Pattern-match `skill: X`, `/command`, `agent-name` |
| `docs/REFERENCE.md` | Section headers | `### tool-name` headers with descriptions |

**Step 3: Build documented-tools registry**

For each documentation file, collect tool names found: `{file -> [tool_names]}` for Phase 3 comparison.

**Step 4: Verify parse completeness**

- All 5 files found and parsed (warn if missing)
- No parse errors on table/list structures
- Tool names extracted from each file

**Gate**: All documentation files parsed without errors.

### Phase 3: DETECT

**Goal**: Compare discovered tools with documented tools.

**Step 1: Compute set differences**

For each tool type and its primary documentation file:
- `missing = filesystem_tools - documented_tools` (exist but undocumented)
- `stale = documented_tools - filesystem_tools` (documented but deleted -- users waste time on non-existent tools)

**Step 2: Check version consistency**

For tools in both sets, compare YAML `version` vs documented version. YAML is authoritative.

**Step 3: Categorize and assign severity**

| Category | Condition | Severity |
|----------|-----------|----------|
| Missing Entry | In filesystem, not in primary README | HIGH |
| Stale Entry | In README, not in filesystem | MEDIUM |
| Version Mismatch | YAML version differs from documented | LOW |
| Incomplete Entry | Documentation missing required fields | LOW |

**Step 4: Record issue details**

Per issue: tool type, name, path, affected documentation file(s), severity, suggested fix.

**Gate**: All issues categorized with severity.

### Phase 4: REPORT

**Goal**: Generate human-readable report with actionable fixes. Report facts concisely. Target 100% sync score.

**Step 1: Run the report generator**

```bash
python3 skills/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --output /tmp/sync-report.md
```

**Step 2: Verify report structure**

Required sections:

1. **Summary** -- Total tools, issue counts by severity, sync score
   ```
   sync_score = (total_tools - total_issues) / total_tools * 100
   ```

2. **HIGH Priority: Missing Entries** -- Exact markdown row/item to add per missing tool

3. **MEDIUM Priority: Stale Entries** -- File and line to remove per stale tool

4. **LOW Priority: Version Mismatches** -- YAML version (authoritative) vs documented version

5. **Files Checked** -- Each documentation file with tool count parsed

**Step 3: Validate actionability**

Every issue must have a concrete fix. No "review manually" without specifying what and where. Fixes should enable single-commit resolution.

**Step 4: Report format for missing entries**

For each missing skill:
```markdown
| skill-name | Description from YAML | `skill: skill-name` | - |
```

For each missing agent:
```markdown
| agent-name | Description from YAML |
```

For each missing command:
```markdown
- `/command-name` - Description from command file
```

**Step 5: Cleanup**

Remove helper scripts and debug outputs created during execution.

**Gate**: Report generated with actionable suggestions for every issue.

### Examples

#### Example 1: New Skill Missing from README
User created `skills/my-new-skill/SKILL.md` but forgot to update `skills/README.md`.
1. SCAN discovers `my-new-skill`
2. CROSS-REFERENCE parses skills/README.md, does not find it
3. DETECT flags HIGH severity missing entry
4. REPORT suggests exact table row to add

#### Example 2: Removed Agent Still Documented
User deleted `agents/old-agent.md` but README still lists it.
1. SCAN does not find `old-agent`
2. CROSS-REFERENCE finds it in agents/README.md
3. DETECT flags MEDIUM severity stale entry
4. REPORT suggests removing the row

#### Example 3: Version Bump Without Doc Update
User updated `version: 2.0.0` in SKILL.md but docs still show `1.5.0`.
1. SCAN reads YAML version as 2.0.0
2. CROSS-REFERENCE reads documented version as 1.5.0
3. DETECT flags LOW severity version mismatch
4. REPORT suggests updating version

#### Example 4: Batch Changes After Refactor
User created 3 new skills and deleted 2 old ones.
1. SCAN discovers 3 new, does not find 2 removed
2. CROSS-REFERENCE finds 2 stale + 3 absent entries
3. DETECT flags 3 HIGH (missing) + 2 MEDIUM (stale)
4. REPORT provides exact rows to add and identifies rows to remove

## Error Handling

### Error: "YAML Parse Error"
Cause: Invalid frontmatter -- missing `---` delimiters, tabs instead of spaces, or missing required fields
Solution:
1. Check file has opening `---` on line 1 and closing `---` after YAML block
2. Verify no tab characters in YAML (spaces only)
3. Confirm required fields present: `name`, `description`, `version`
4. Validate manually: `head -20 {file_path}`

### Error: "Documentation File Not Found"
Cause: Expected README file does not exist
Solution:
1. Verify --repo-root path is correct
2. Check that skills/README.md, agents/README.md, commands/README.md exist
3. If legitimately missing, create placeholder with expected table/list header
4. Re-run scan

### Error: "No Tools Discovered"
Cause: Wrong --repo-root path, empty directories, or no SKILL.md files
Solution:
1. Verify repo root path
2. Confirm skills/, agents/, commands/ directories exist and are not empty
3. Check that skill directories contain SKILL.md
4. Run with --debug for verbose output

### Error: "Markdown Parse Error"
Cause: Table missing separator row, mismatched column counts, or malformed list items
Solution:
1. Check table has header, separator (`|---|---|`), and data rows
2. Verify all rows have same column count
3. For lists, verify consistent format: `- /command - Description`
4. See `references/markdown-formats.md` for format specifications

---

## References
- `${CLAUDE_SKILL_DIR}/references/documentation-structure.md`: Documentation file matrix, required fields per location, cross-reference requirements
- `${CLAUDE_SKILL_DIR}/references/markdown-formats.md`: Expected table/list formats for each README file, parsing rules, common formatting errors
- `${CLAUDE_SKILL_DIR}/references/sync-rules.md`: Synchronization rules, severity levels, deprecation handling, namespace rules
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Before/after examples for adding, removing, updating, and batch documentation changes
- `${CLAUDE_SKILL_DIR}/references/integration-guide.md`: CI/CD setup, pre-commit hooks, auto-fix mode, JSON output, workflow integration
