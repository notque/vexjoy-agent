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
    - toolkit
    - assessment
---

# Documentation Sync Checker Skill

Deterministic 4-phase drift detector that compares the filesystem against each tool type's primary doc: `docs/skills.md`, `docs/routing-map.md`, and `docs/REFERENCE.md`. Each phase (Scan, Cross-Reference, Detect, Report) has a gate that must pass before proceeding. The skill produces a sync score (percentage of tools properly documented) and actionable fix suggestions for every detected issue.

This skill checks documentation presence and absence only -- it does not judge description quality, generate documentation content, resolve merge conflicts, validate cross-references, or track when drift occurred. Suggested fixes use YAML descriptions verbatim; content generation and quality assessment require different skills.

Report flags: `--strict` (exit code 1 on issues), `--format json` (machine-readable output).

---

## Instructions

### Phase 1: SCAN

**Goal**: Discover all skills, agents, and commands in the repository filesystem. All discovery (file existence checks, YAML parsing, markdown extraction) must be deterministic -- no AI judgment on content quality.

**Step 1: Run the scan script**

```bash
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root $HOME/vexjoy-agent --output /tmp/scan_results.json
```

**Step 2: Validate discovery results**

For each tool type, verify:

Skills (`skills/**/SKILL.md`):
- File has opening `---` and closing `---` YAML delimiters
- YAML contains non-empty `name` and `description` fields
- `name` field matches directory name (e.g., `skills/code-quality/code-quality/` has `name: code-quality`)
- A skill with `promoted_to`, or one reached through a symlink (private), is scanned but not expected in the catalog

Agents (`agents/*.md`):
- File has valid YAML frontmatter with `name` field; a file without frontmatter (`agents/base-instructions.md`) is not an agent
- Filename (without .md) matches YAML `name` value

Commands (`commands/**/*.md`):
- File exists as markdown in commands/ directory
- Namespaced commands in subdirectories (e.g., `commands/code/cleanup.md`) are detected

**Step 3: Validate the docs routing catalog**

Every `docs/*.md` file (outside `archive/` and `images/`) carries frontmatter with `summary` and `read_when` — the on-demand load triggers for docs, matching what `skills/INDEX.json` gives skills.

```bash
python3 scripts/docs-catalog.py --check
```

Exit 1 means a doc is missing frontmatter; add `summary` and `read_when` to that file. `python3 scripts/docs-catalog.py` (no flags) prints the catalog table; `--json` emits it machine-readable.

**Step 4: Count and verify**

```markdown
## Scan Results
Skills found: [N]
Agents found: [N]
Commands found: [N]
YAML errors: [N] (must be 0 to proceed)
```

**Gate**: All tools discovered, all YAML valid, counts >0 for each type, docs catalog check exits 0. Proceed only after the gate passes.

### Phase 2: CROSS-REFERENCE

**Goal**: Extract documented tools from each type's primary doc and compare with discovered tools. Targets live in `PRIMARY_DOCS` in `scripts/parse_docs.py`; `scripts/validate.py` fails if one is missing.

**Step 1: Run the documentation parser**

```bash
python3 skills/meta/docs-sync-checker/scripts/parse_docs.py --repo-root $HOME/vexjoy-agent --scan-results /tmp/scan_results.json --output /tmp/issues.json
```

**Step 2: Parse each primary doc**

These are the documentation files to check -- no others:

| File | Tool type | Maintained by | What to Extract |
|------|-----------|---------------|-----------------|
| `docs/skills.md` | Skills | `scripts/generate-skills-doc.py` | First cell of every table row: `` `skill-name` `` |
| `docs/routing-map.md` | Agents | `scripts/generate-routing-map.py` | First cell of each `## AGENTS` table row: `agent-name` |
| `docs/REFERENCE.md` | Commands | Hand-written | First cell of each `## Slash Commands` table row: `` `/command` `` |
| `README.md` | Mentions only | Hand-written | `/command` and `*-engineer` mentions; recorded, never flagged |

**Step 3: Build documented-tools registry**

For each primary doc, collect the set of tool names found. This creates a mapping of `{file -> [tool_names]}` that Phase 3 will compare against the filesystem scan.

**Step 4: Verify parse completeness**

- Every primary doc found and parsed; a missing one exits 2 and stops the run. Never create a placeholder doc to get past it: fix `PRIMARY_DOCS` and this table.
- Entry counts are non-zero for each type

**Gate**: All documentation files parsed without errors. Proceed only after the gate passes.

### Phase 3: DETECT

**Goal**: Compare discovered tools with documented tools to identify drift. This is a point-in-time snapshot -- it cannot tell you when drift occurred, only that it exists now.

**Step 1: Compute set differences**

For each tool type and its primary documentation file:
- `missing = filesystem_tools - documented_tools` (tools that exist but are not documented)
- `stale = documented_tools - filesystem_tools` (documented tools that no longer exist -- users waste time trying to invoke non-existent tools, so always flag these)

**Step 2: Categorize and assign severity**

Severity reflects user impact: missing entries mean tools are undiscoverable and stale entries waste time.

| Category | Condition | Severity |
|----------|-----------|----------|
| Missing Entry | Tool in filesystem, not in its primary doc | HIGH |
| Stale Entry | Tool in a primary doc, not in filesystem | MEDIUM |
| Incomplete Entry | Documentation missing required fields | LOW |

**Step 3: Record issue details**

For each issue, capture: tool type, tool name, tool path, affected documentation file(s), severity, and suggested fix action. `parse_docs.py` writes these, with `suggested_fix`, to its output JSON.

**Gate**: All issues categorized with severity. Proceed only after the gate passes.

### Phase 4: REPORT

**Goal**: Generate human-readable report with actionable fix suggestions. Report facts concisely -- show data, not self-congratulatory descriptions. Target 100% sync score; even one missing entry erodes trust in all documentation.

**Step 1: Run the report generator**

```bash
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --scan-results /tmp/scan_results.json --output /tmp/sync-report.md
```

**Step 2: Verify report structure**

Report must include these sections:

1. **Summary** -- Total tools, issue counts by severity, sync score
   ```
   sync_score = (total_tools - total_issues) / total_tools * 100
   ```

2. **HIGH Priority: Missing Entries** -- For each missing tool, the fix: a generator command, or the exact `docs/REFERENCE.md` row to add

3. **MEDIUM Priority: Stale Entries** -- For each stale tool, the fix: a generator command, or the `docs/REFERENCE.md` row to remove

4. **Files Checked** -- List each primary doc with count of tools parsed from it

**Step 3: Validate actionability**

Every issue in the report must have a concrete suggested fix. No issue should say "review manually" without specifying what to review and where. The fix should enable a single-commit resolution -- tool files and documentation entries should be added/removed together.

**Step 4: Fix format for missing entries**

`docs/skills.md` and `docs/routing-map.md` are generated. A missing skill or agent is fixed by rerunning the generator, never by hand-adding a row:
```bash
python3 scripts/generate-skills-doc.py     # skills
python3 scripts/generate-routing-map.py    # agents
```
If the tool still does not appear, its frontmatter is the cause (`name`, `description`, `promoted_to`).

For each missing command, give the row to add to a `## Slash Commands` table in `docs/REFERENCE.md`:
```markdown
| `/command-name` | Description from command frontmatter |
```

**Step 5: Cleanup**

Remove any helper scripts and debug outputs created during execution.

**Gate**: Report generated with actionable suggestions for every issue.

### Examples

#### Example 1: New Skill Missing from the Catalog
User created `skills/process/my-new-skill/SKILL.md` but did not regenerate `docs/skills.md`.
Actions:
1. SCAN discovers `my-new-skill` in filesystem
2. CROSS-REFERENCE parses docs/skills.md, does not find `my-new-skill`
3. DETECT flags as HIGH severity missing entry
4. REPORT suggests `python3 scripts/generate-skills-doc.py`

#### Example 2: Removed Command Still Documented
User deleted `commands/old-command.md` but `docs/REFERENCE.md` still lists `/old-command`.
Actions:
1. SCAN does not find `old-command` in filesystem
2. CROSS-REFERENCE finds `/old-command` in docs/REFERENCE.md
3. DETECT flags as MEDIUM severity stale entry
4. REPORT suggests removing the `/old-command` row from docs/REFERENCE.md

#### Example 3: Batch Changes After Refactor
User created 3 new skills and deleted 2 old ones in a refactoring PR.
Actions:
1. SCAN discovers 3 new skills in filesystem, does not find 2 removed skills
2. CROSS-REFERENCE finds 2 stale entries and 3 absent entries in docs/skills.md
3. DETECT flags 3 HIGH (missing) + 2 MEDIUM (stale) issues
4. REPORT suggests one regeneration of docs/skills.md, which fixes all 5

## Error Handling

### Error: "YAML Parse Error"
Cause: Invalid frontmatter -- missing `---` delimiters, tabs instead of spaces, or missing required fields
Solution:
1. Check file has opening `---` on line 1 and closing `---` after YAML block
2. Verify no tab characters in YAML (spaces only)
3. Confirm required fields present: `name`, `description`
4. Validate manually: `head -20 {file_path}` and check syntax

### Error: "primary doc(s) not found"
Cause: `parse_docs.py` exits 2 because a `PRIMARY_DOCS` target does not exist -- the docs layout moved, or --repo-root is wrong
Solution:
1. Verify --repo-root path is correct
2. Check that docs/skills.md, docs/routing-map.md, and docs/REFERENCE.md exist
3. If the layout moved, update `PRIMARY_DOCS` in `scripts/parse_docs.py`, the Phase 2 table, and `references/documentation-structure.md` together, then run `python3 skills/meta/docs-sync-checker/scripts/validate.py`
4. Never create a placeholder doc to make the check pass

### Error: "No Tools Discovered"
Cause: Wrong --repo-root path, empty directories, or no SKILL.md files
Solution:
1. Verify the repo root path points to the correct repository
2. Confirm skills/, agents/, commands/ directories exist and are not empty
3. Check that skill directories contain SKILL.md (not just other files)
4. Run with --debug flag for verbose discovery output

### Error: "Entry count is zero for a type"
Cause: The table moved out of the parsed section (`## AGENTS` in docs/routing-map.md, `## Slash Commands` in docs/REFERENCE.md) or the first-cell format changed. `parse_docs.py` exits 2 with this message rather than report every entry missing
Solution:
1. Check the section heading and the first-cell format in `references/documentation-structure.md`
2. Update `_SECTIONS` or `_NAME_CELL` in `scripts/parse_docs.py` to match, and run `scripts/validate.py`

---

## Deep References

Load when the task requires detailed guidance beyond the phases above.

| Signal | Reference |
|--------|-----------|
| Primary docs, parsed formats, who is expected where | `references/documentation-structure.md` |
| Sync score formula, severity rules, fixes, exceptions | `references/sync-rules.md` |
| Pipeline commands, exit codes, JSON output, CI coverage | `references/integration-guide.md` |
