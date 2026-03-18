---
name: routing-table-updater
description: |
  Maintain /do routing tables and command references when skills or agents
  are added, modified, or removed. Use when skill/agent metadata changes,
  after skill-creator-engineer or agent-creator-engineer runs, or when
  routing tables need synchronization. Use for "update routes", "sync
  routing", "routing table", or "refresh /do". Do NOT use for creating
  new skills/agents, modifying skill logic, or manual /do table edits.
version: 2.1.0
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
---

# Routing Table Updater Skill

## Operator Context

This skill operates as an operator for routing table maintenance workflows, configuring Claude's behavior for automated /do command routing configuration. It implements a **Phase-Gated Pipeline** -- scan, extract, generate, update, verify -- with deterministic script execution at each phase.

### Hardcoded Behaviors (Always Apply)

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution. Project instructions override default skill behaviors.
- **Over-Engineering Prevention**: Only update routing tables that need changes. Keep routing entries concise and pattern-focused. No speculative patterns or flexibility that was not requested. Generate exactly what /do needs -- no additional features.
- **Preserve Manual Entries**: Detect and skip hand-written routing entries in do.md. Never overwrite entries without `[AUTO-GENERATED]` markers.
- **Backup Before Modification**: Always create timestamped backup of commands/do.md before any changes. Rollback on validation failure.
- **Markdown Syntax Validation**: Verify table syntax after updates. Ensure pipe alignment and proper header separation.
- **Deterministic Generation**: Same skill/agent metadata always produces same routing entry. No randomness in pattern extraction or table formatting.

### Default Behaviors (ON unless disabled)

- **Communication Style**: Report facts without self-congratulation. Show diff of routing changes rather than describing them.
- **Temporary File Cleanup**: Remove temporary metadata JSON files and diff files at completion. Keep only backups and updated do.md.
- **Interactive Confirmation**: Show diff and ask for confirmation before updating do.md (unless --auto-commit flag provided).
- **Progress Reporting**: Stream updates as scanning, extracting, generating, and updating phases execute.
- **Conflict Detection**: Warn when multiple routes match the same pattern with suggestions for resolution.
- **Alphabetical Ordering**: Maintain alphabetical order within routing tables.

### Optional Behaviors (OFF unless enabled)

- **Auto-Commit Mode**: `--auto-commit` flag to skip confirmation and automatically commit changes.
- **Dry-Run Mode**: `--dry-run` to show changes without modifying do.md.
- **Verbose Debug**: `--verbose` for detailed parsing and generation logs.

## What This Skill CAN Do

- Scan all skills (skills/*/SKILL.md) and agents (agents/*.md) for metadata
- Extract YAML frontmatter (name, description, version) and trigger patterns
- Generate routing table entries following /do format specification
- Detect routing conflicts (same trigger mapped to multiple routes)
- Safely update commands/do.md with atomic backup/restore
- Update command files (commands/*.md) with skill/agent references
- Preserve all hand-written manual routing entries
- Validate markdown table syntax after updates
- **Batch mode**: Process N skills at once from a Pipeline Spec or component list (used by pipeline-scaffolder Phase 4)
- **INDEX.json updates**: Add/update agent entries in `agents/INDEX.json` alongside routing tables

## What This Skill CANNOT Do

- Infer trigger patterns from vague descriptions (requires explicit phrases)
- Create new routing table sections (only updates existing tables)
- Resolve high-severity conflicts automatically (requires manual priority decisions)
- Modify skill/agent metadata (read-only access to capabilities)
- Handle non-standard markdown table formats

---

## Prerequisites

- Must be in agents repository root (has commands/do.md)
- Skills must have valid YAML frontmatter in SKILL.md files
- Agents must have valid YAML frontmatter in agents/*.md files
- commands/do.md must have routing table sections with standard headers

---

## Instructions

### Phase 1: SCAN -- Discover All Skills and Agents

**Goal**: Find every skill and agent file in the repository.

**Step 1: Run scan script**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/scan.py --repo $HOME/ai-overkill
```

**Step 2: Validate scan output**

Expected output is JSON with:
- `skills_found`: count of discovered skill files
- `agents_found`: count of discovered agent files
- `skills`: array of paths to skills/*/SKILL.md
- `agents`: array of paths to agents/*.md

**Step 3: Check for gaps**

Compare discovered count against expected. If skills or agents are missing, check:
- Directory naming (must be skills/*/SKILL.md format)
- Agent file naming (must be agents/*.md format)
- File permissions

**Gate**: All skill directories and agent files discovered with no permission errors. Do NOT proceed to Phase 2 until gate passes.

If gate fails:
- "Repository not found": Verify --repo path points to agents directory
- "No skills found": Check skills/ directory exists and has subdirectories
- "Permission denied": Verify file read permissions

### Phase 2: EXTRACT -- Parse Metadata

**Goal**: Extract YAML frontmatter, trigger patterns, complexity, and routing table targets from every discovered file.

**Step 1: Run extraction script**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/extract_metadata.py --input scan_results.json --output metadata.json
```

**Step 2: Verify extraction completeness**

For each capability, confirm these fields were extracted:
- `name`: Matches YAML frontmatter name field
- `description`: Full description text
- `version`: Semantic version string
- `trigger_patterns` (skills): Array of quoted phrases from description
- `domain_keywords` (agents): Array of technology/domain terms
- `complexity`: Inferred level (Simple, Medium, Complex)
- `routing_table`: Target table (Intent Detection, Task Type, Domain-Specific, or Combination)

**Step 3: Validate trigger pattern quality**

Review extracted patterns against `references/extraction-patterns.md`. Patterns should be:
- Specific enough to avoid false matches
- Broad enough to catch common phrasings
- Free of generic terms that match too many routes

**Gate**: All YAML parsed successfully, required fields present (name, description, version), trigger patterns extracted for skills, domain keywords extracted for agents. Do NOT proceed to Phase 3 until gate passes.

If gate fails:
- "Invalid YAML in {file}": Fix YAML frontmatter in the skill/agent file
- "Missing description field": Add description to YAML frontmatter
- "No trigger patterns found": Update description to include clear trigger phrases

### Phase 3: GENERATE -- Create Routing Table Entries

**Goal**: Map extracted metadata to routing entries and detect conflicts.

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/generate_routes.py --input metadata.json --output routing_entries.json
```

Generation process:
1. Load routing format specification from `references/routing-format.md`
2. Map each capability to appropriate routing table
3. Format entries according to /do table structure
4. Detect pattern conflicts (see `references/conflict-resolution.md`)
5. Sort entries alphabetically within tables

**Gate**: All capabilities mapped to entries, entries follow /do format, conflicts detected and documented, no duplicates within same table. Do NOT proceed to Phase 4 until gate passes.

If gate fails:
- "Unknown routing table target": Update routing table mapping logic
- "High-severity conflict": Review conflicting patterns manually before proceeding

### Phase 4A: UPDATE -- Safely Modify commands/do.md

**Goal**: Apply generated routing entries to do.md with backup and validation.

**Step 1: Run update script with backup**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/update_routing.py --input routing_entries.json --target $HOME/ai-overkill/commands/do.md --backup
```

**Step 2: Verify backup exists**

Confirm backup file at `commands/.do.md.backup.{timestamp}` before any modifications proceed.

**Step 3: Review the diff**

The script outputs a diff showing:
- New entries being added (prefixed with +)
- Modified entries being updated (old with -, new with +)
- Manual entries being preserved (unchanged)

Review the diff for correctness. Count of preserved manual entries should match expectations.

**Step 4: Confirm or abort**

- If diff looks correct: confirm to apply
- If diff shows unexpected changes: abort and investigate
- If using --auto-commit: confirmation is skipped

**Step 5: Post-update validation**

After writing, the script validates:
- Pipe alignment in all tables
- Header separator rows present
- Consistent column counts per table
- No orphaned rows

On validation failure: automatic restore from backup. Report error details.

**Gate**: Backup created, all manual entries preserved, markdown validated, diff confirmed. If gate fails, RESTORE from backup.

### Phase 4B: UPDATE -- Update Command Files

**Goal**: Update command files with current skill/agent references.

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/update_commands.py --commands-dir $HOME/ai-overkill/commands --metadata metadata.json --backup
```

Update process:
1. Scan command files for skill invocations and references
2. Identify outdated or invalid references (renamed/removed skills)
3. Update references to match current metadata
4. Create backups for all modified command files
5. Validate updated markdown syntax

**Gate**: Backups created for all modified files, all referenced skills exist, markdown validated.

### Phase 5: VERIFY -- Validate Routing Correctness

**Goal**: Final validation of all routing tables.

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/validate.py --target $HOME/ai-overkill/commands/do.md
```

Verification checks:
1. **Structural**: All routing tables present, headers formatted, pipes aligned
2. **Content**: All auto-generated entries marked, no duplicates, all referenced skills/agents exist
3. **Conflicts**: Overlapping patterns documented, priority rules applied
4. **Integration**: Sample pattern matching tests pass

**Gate**: All checks pass. Task complete ONLY if final gate passes.

If gate fails:
- "Duplicate pattern detected": Remove duplicate from do.md
- "Missing skill/agent file": Remove routing entry or create missing capability
- "Invalid complexity level": Fix complexity value in routing entry

---

## Examples

### Example 1: New Skill Created

User creates `skills/api-integration-helper/SKILL.md` via skill-creator-engineer:

```yaml
---
name: api-integration-helper
description: Test API integrations with mock responses and validation. Use when "test API", "API integration", or "mock API".
version: 1.0.0
---
```

Actions:
1. SCAN: Detect new file in skills/ directory
2. EXTRACT: Parse frontmatter, extract trigger patterns ["test API", "API integration", "mock API"], complexity Medium
3. GENERATE: Create entry for Intent Detection Patterns table
4. UPDATE: Backup do.md, insert entry alphabetically, validate markdown
5. VERIFY: Run validate.py, confirm no conflicts, all tables intact

Generated routing entry:
```
| "test API", "API integration", "mock API" | api-integration-helper skill | Medium | [AUTO-GENERATED]
```

Result: New skill is discoverable via /do command

### Example 2: Agent Description Updated

User updates golang-general-engineer description to add "concurrency" keyword.

Actions:
1. SCAN: Find modified agents/golang-general-engineer.md
2. EXTRACT: Parse updated domain keywords ["Go", "Golang", "gofmt", "Go concurrency"]
3. GENERATE: Update Domain-Specific routing entry with new keywords
4. UPDATE: Backup, replace existing auto-generated entry, preserve manual entries
5. VERIFY: Confirm no new conflicts, all references valid

Updated routing entry:
```diff
-| Go, Golang, gofmt | golang-general-engineer | Medium-Complex | [AUTO-GENERATED]
+| Go, Golang, gofmt, Go concurrency | golang-general-engineer | Medium-Complex | [AUTO-GENERATED]
```

Result: Domain routing expanded to cover new keyword

### Example 3: Conflict Detection

Two skills both match "test API" pattern.

Actions:
1. GENERATE phase detects overlap between api-testing-skill and integration-testing-skill
2. Conflict logged with severity assessment (low: both routes reasonable)
3. Resolution: longer pattern "test API integration" takes precedence for integration skill
4. Document conflict in output, apply specificity rule

Resolution applied:
```
| "test API integration" | integration-testing-skill | Medium | [AUTO-GENERATED]
| "test API" | api-testing-skill | Medium | [AUTO-GENERATED]
```

Result: Unambiguous routing with longest-match precedence

### Example 4: Manual Entry Preserved

Existing do.md has a hand-curated combination entry (no AUTO-GENERATED marker):
```
| "review Python", "Python quality" | python-general-engineer + python-quality-gate | Medium |
```

Auto-generation produces a simpler entry for "review Python". Because the existing entry lacks the `[AUTO-GENERATED]` marker, it is preserved as-is. The auto-generated entry is skipped for this pattern.

Result: Manual curation respected, no data loss

---

## Batch Mode

When invoked by `pipeline-scaffolder` Phase 4 (INTEGRATE), this skill operates in batch mode to register N skills and 0-1 agents in a single pass.

### Batch Input

The scaffolder provides a component list (from the Pipeline Spec):
```json
{
  "domain": "prometheus",
  "agent": { "name": "prometheus-grafana-engineer", "is_new": false },
  "skills": [
    { "name": "prometheus-metrics", "triggers": ["prometheus metrics", "PromQL", "recording rules"], "agent": "prometheus-grafana-engineer" },
    { "name": "prometheus-alerting", "triggers": ["prometheus alerting", "alert rules", "alertmanager"], "agent": "prometheus-grafana-engineer" },
    { "name": "prometheus-operations", "triggers": ["prometheus operations", "prometheus troubleshooting"], "agent": "prometheus-grafana-engineer" }
  ]
}
```

### Batch Process

1. **SCAN**: Skip full repo scan — use the provided component list directly
2. **EXTRACT**: Read YAML frontmatter from each listed skill file (verify they exist)
3. **GENERATE**: Create routing entries for ALL N skills in one pass. Check for inter-batch conflicts (skills within the same batch that share triggers).
4. **UPDATE**:
   - Add all N routing entries to `skills/do/references/routing-tables.md` in one write
   - If agent is new (`is_new: true`), add to `agents/INDEX.json`
   - Update `skills/do/SKILL.md` if force-route triggers are needed
   - Create `commands/{domain}-pipeline.md` manifest
5. **VERIFY**: Validate all N entries are present and correctly formatted

### Batch vs Single Mode

| Aspect | Single Mode | Batch Mode |
|--------|-------------|------------|
| Input | Full repo scan | Component list from Pipeline Spec |
| Scan | All skills/* and agents/* | Only listed components |
| Conflict check | Against existing entries | Against existing AND within batch |
| OUTPUT | One entry at a time | N entries in one pass |
| Invoked by | skill-creator-engineer, agent-creator-engineer | pipeline-scaffolder Phase 4 |

---

## Integration

This skill is typically invoked after other creation skills complete:

- **After skill-creator-engineer**: New skill created, routing tables need updated entry
- **After agent-creator-engineer**: New agent created, domain routing needs expansion
- **After skill/agent modification**: Description or trigger changes require routing refresh
- **During repository maintenance**: Periodic sync to catch manual drift
- **After pipeline-scaffolder Phase 3**: N skills created for a domain, all need routing (batch mode)

Invocation by other skills:
```
skill: routing-table-updater
```

The skill reads metadata from all skills and agents but never modifies them. It only writes to `skills/do/SKILL.md`, `skills/do/references/routing-tables.md`, `agents/INDEX.json`, and `commands/*.md` files.

---

## Error Handling

### Error: "YAML Parse Error in {file}"
Cause: Malformed YAML frontmatter in skill/agent file
Solution: Fix YAML syntax (missing colons, bad indentation, unquoted special characters), re-run extraction

### Error: "Routing Conflict -- High Severity"
Cause: Same trigger phrase maps to incompatible routes (e.g., "deploy" to both Docker and Kubernetes)
Solution: Add domain context to patterns ("deploy Docker" vs "deploy K8s"), update skill descriptions, document resolution in `references/conflict-resolution.md`

### Error: "Manual Entry Overwrite Detected"
Cause: Bug in manual entry detection logic
Solution: CRITICAL -- DO NOT PROCEED. Restore from backup immediately. Report detection regex issue.

### Error: "Markdown Table Validation Failed"
Cause: Generated table has misaligned pipes, missing headers, or inconsistent column counts
Solution: Restore from backup, fix table generation logic, re-run. Do not commit broken markdown.

---

## Anti-Patterns

### Anti-Pattern 1: Fixing Without Backup
**What it looks like**: Running update_routing.py with --no-backup
**Why wrong**: No recovery path if manual entries are lost or markdown is corrupted
**Do instead**: Always use --backup flag. Verify backup exists before proceeding.

### Anti-Pattern 2: Skipping Phase Gates
**What it looks like**: Running UPDATE before EXTRACT completes
**Why wrong**: Missing metadata produces empty or incorrect routing tables. Phase gates prevent incomplete data from corrupting do.md.
**Do instead**: Verify each gate passes before proceeding. Follow SCAN -> EXTRACT -> GENERATE -> UPDATE -> VERIFY sequence.

### Anti-Pattern 3: Ignoring Conflict Warnings
**What it looks like**: Proceeding with high-severity conflicts unresolved
**Why wrong**: Ambiguous routing confuses /do command. Users get wrong tool for their context.
**Do instead**: Review severity. High-severity conflicts MUST be resolved. Add domain context to make patterns specific.

### Anti-Pattern 4: Overwriting Manual Entries
**What it looks like**: Replacing all matching rows without checking for AUTO-GENERATED marker
**Why wrong**: Manual entries contain curated routing decisions and hand-tuned combinations
**Do instead**: Only update rows with `[AUTO-GENERATED]` marker. Preserve everything else.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Routes look correct, no need to validate" | Visual inspection misses duplicate patterns and conflicts | Run validate.py against updated do.md |
| "Small routing change, skip backup" | One corrupt table makes /do unusable | Always create backup before modification |
| "Manual entries are outdated, replace them" | Manual entries contain intentional curation | Preserve all non-AUTO-GENERATED entries |
| "Conflict is low severity, ignore it" | Low severity today becomes user confusion tomorrow | Document all conflicts with resolution strategy |

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/routing-format.md`: /do routing table format specification (table structure, entry formats, ordering rules)
- `${CLAUDE_SKILL_DIR}/references/extraction-patterns.md`: Trigger phrase extraction patterns (regex, keyword maps, complexity inference)
- `${CLAUDE_SKILL_DIR}/references/conflict-resolution.md`: Conflict types, priority rules, severity levels, resolution process
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world examples of routing table updates (new skill, updated agent, conflict detection, manual preservation)
