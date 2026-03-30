---
name: routing-table-updater
description: |
  Maintain /do routing tables and command references when skills or agents
  are added, modified, or removed. Use when skill/agent metadata changes,
  after skill-creator runs, or when
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
routing:
  triggers:
    - "update routing"
    - "sync routing tables"
  category: meta-tooling
---

# Routing Table Updater Skill

## Overview

This skill maintains /do routing tables and command references when skills or agents are added, modified, or removed. It implements a **Phase-Gated Pipeline** -- scan, extract, generate, update, verify -- with deterministic script execution at each phase.

The skill reads metadata from all skills and agents (never modifies them) and safely updates `skills/do/SKILL.md`, `skills/do/references/routing-tables.md`, `agents/INDEX.json`, and `commands/*.md` files. All changes are backed up before modification, and markdown syntax is validated before commit.

---

## Instructions

### Phase 1: SCAN -- Discover All Skills and Agents

**Goal**: Find every skill and agent file in the repository.

**Constraints applied in this phase**:
- Repository must be at agents toolkit root (requires `commands/do.md`)
- Only scan skills/ directories matching `skills/*/SKILL.md` format
- Only scan agent files matching `agents/*.md` format
- File permissions must allow reading all discovered files

**Step 1: Run scan script**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/scan.py --repo $HOME/claude-code-toolkit
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

---

### Phase 2: EXTRACT -- Parse Metadata

**Goal**: Extract YAML frontmatter, trigger patterns, complexity, and routing table targets from every discovered file.

**Constraints applied in this phase**:
- YAML frontmatter must be valid (no syntax errors; malformed YAML blocks extraction)
- Required fields (`name`, `description`, `version`) must be present
- Trigger patterns for skills extracted from description text (specify patterns, don't infer from vague text)
- Domain keywords for agents extracted from description text (explicit phrases required)
- Complexity inference must follow established rules (`references/extraction-patterns.md`)

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

Review extracted patterns against `references/extraction-patterns.md`. Patterns must be:
- Specific enough to avoid false matches (too broad = user confusion)
- Broad enough to catch common phrasings (too narrow = missed activations)
- Free of generic terms that match too many routes (prevents routing ambiguity)

**Gate**: All YAML parsed successfully, required fields present (name, description, version), trigger patterns extracted for skills, domain keywords extracted for agents. Do NOT proceed to Phase 3 until gate passes.

If gate fails:
- "Invalid YAML in {file}": Fix YAML frontmatter in the skill/agent file
- "Missing description field": Add description to YAML frontmatter
- "No trigger patterns found": Update description to include clear trigger phrases

---

### Phase 3: GENERATE -- Create Routing Table Entries

**Goal**: Map extracted metadata to routing entries and detect conflicts.

**Constraints applied in this phase**:
- Same skill/agent metadata always produces the same routing entry (deterministic generation, no randomness)
- Entries follow exact /do format specification (`references/routing-format.md`)
- Pattern conflicts detected immediately (same trigger maps to multiple incompatible routes)
- Entries sorted alphabetically within tables
- Duplicate entries within same table prevent gate passage

**Step 1: Run generation script**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/generate_routes.py --input metadata.json --output routing_entries.json
```

**Step 2: Understand the generation process**

1. Load routing format specification from `references/routing-format.md`
2. Map each capability to appropriate routing table
3. Format entries according to /do table structure
4. Detect pattern conflicts (see `references/conflict-resolution.md`)
5. Sort entries alphabetically within tables

**Step 3: Review conflict detection output**

The script logs all conflicts with severity levels. For low-severity conflicts (both routes reasonable), the script applies specificity rules automatically. For high-severity conflicts (incompatible routes), the script blocks gate passage and requires manual resolution.

**Gate**: All capabilities mapped to entries, entries follow /do format, conflicts detected and documented, no duplicates within same table. Do NOT proceed to Phase 4 until gate passes.

If gate fails:
- "Unknown routing table target": Update routing table mapping logic
- "High-severity conflict": Review conflicting patterns manually before proceeding

---

### Phase 4A: UPDATE -- Safely Modify commands/do.md

**Goal**: Apply generated routing entries to do.md with backup and validation.

**Constraints applied in this phase**:
- Always create timestamped backup before any modification (mandatory backup gate)
- Detect and preserve all hand-written entries (entries without `[AUTO-GENERATED]` marker are never overwritten)
- Manual entries are intentional curation — overwriting them causes data loss
- Markdown table syntax must validate after updates (pipe alignment, header rows, column consistency)
- Atomic backup/restore: if validation fails, automatic restore from backup

**Step 1: Run update script with backup**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/update_routing.py --input routing_entries.json --target $HOME/claude-code-toolkit/commands/do.md --backup
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

---

### Phase 4B: UPDATE -- Update Command Files

**Goal**: Update command files with current skill/agent references.

**Constraints applied in this phase**:
- Command files updated only if they reference outdated or invalid skills
- Backups created for all modified files before any changes
- All referenced skills must exist (missing skills cause gate failure)
- Markdown syntax validated after updates (prevents publishing broken tables)

**Step 1: Run update script with backup**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/update_commands.py --commands-dir $HOME/claude-code-toolkit/commands --metadata metadata.json --backup
```

**Step 2: Understand the update process**

1. Scan command files for skill invocations and references
2. Identify outdated or invalid references (renamed/removed skills)
3. Update references to match current metadata
4. Create backups for all modified command files
5. Validate updated markdown syntax

**Gate**: Backups created for all modified files, all referenced skills exist, markdown validated.

---

### Phase 5: VERIFY -- Validate Routing Correctness

**Goal**: Final validation of all routing tables.

**Constraints applied in this phase**:
- All auto-generated entries must have `[AUTO-GENERATED]` markers (validation gate checks this)
- No duplicate patterns within the same routing table
- All referenced skills/agents must exist as actual files
- Complexity values must match defined levels (Simple, Medium, Complex)
- Overlapping patterns documented with priority rules applied

**Step 1: Run validation script**

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/validate.py --target $HOME/claude-code-toolkit/commands/do.md
```

**Step 2: Understand verification checks**

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

User creates `skills/api-integration-helper/SKILL.md` via skill-creator:

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

---

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

---

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

---

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
| Invoked by | skill-creator | pipeline-scaffolder Phase 4 |

---

## Integration

This skill is typically invoked after other creation skills complete:

- **After skill-creator**: New skill created, routing tables need updated entry
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

## References

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/routing-format.md`: /do routing table format specification (table structure, entry formats, ordering rules)
- `${CLAUDE_SKILL_DIR}/references/extraction-patterns.md`: Trigger phrase extraction patterns (regex, keyword maps, complexity inference)
- `${CLAUDE_SKILL_DIR}/references/conflict-resolution.md`: Conflict types, priority rules, severity levels, resolution process
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world examples of routing table updates (new skill, updated agent, conflict detection, manual preservation)
