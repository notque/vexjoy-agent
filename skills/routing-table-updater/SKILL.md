---
name: routing-table-updater
description: "Maintain /do routing tables when skills or agents change."
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
    - "routing maintenance"
    - "rebuild routing index"
    - "routing drift"
  category: meta-tooling
  pairs_with:
    - toolkit-evolution
    - generate-claudemd
---

# Routing Table Updater Skill

Maintains /do routing tables and command references when skills or agents change. Phase-gated pipeline: scan, extract, generate, update, verify -- deterministic script execution at each phase.

Reads metadata from all skills/agents (never modifies them). Safely updates `skills/do/SKILL.md`, `skills/do/references/routing-tables.md`, `agents/INDEX.json`, and `commands/*.md`. All changes backed up before modification.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `batch-mode.md` | Loads detailed guidance from `batch-mode.md`. |
| tasks related to this reference | `conflict-resolution.md` | Loads detailed guidance from `conflict-resolution.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| implementation patterns | `extraction-patterns.md` | Loads detailed guidance from `extraction-patterns.md`. |
| tasks related to this reference | `routing-format.md` | Loads detailed guidance from `routing-format.md`. |
| example-driven tasks | `skill-examples.md` | Loads detailed guidance from `skill-examples.md`. |

## Instructions

### Phase 1: SCAN -- Discover All Skills and Agents

**Constraints**: Repo must be at toolkit root (requires `commands/do.md`); only scan `skills/*/SKILL.md` and `agents/*.md`; files must be readable.

**Step 1**: Run scan:

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/scan.py --repo $HOME/vexjoy-agent
```

**Step 2**: Validate output -- JSON with `skills_found`, `agents_found`, `skills` (paths), `agents` (paths).

**Step 3**: Compare discovered count against expected. If missing, check directory/file naming or permissions.

**Gate**: All skill directories and agent files discovered without errors. See `references/error-handling.md` for recovery.

---

### Phase 2: EXTRACT -- Parse Metadata

**Constraints**: Valid YAML frontmatter; required fields (`name`, `description`); complexity inference per `references/extraction-patterns.md`.

**Step 1**: Run extraction:

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/extract_metadata.py --input scan_results.json --output metadata.json
```

**Step 2**: Verify per capability: `name`, `description`, `trigger_patterns` (skills), `domain_keywords` (agents), `complexity`, `routing_table`.

**Step 3**: Validate trigger quality against `references/extraction-patterns.md` -- specific enough to avoid false matches, broad enough for common phrasings.

**Gate**: All YAML parsed, required fields present, triggers/keywords extracted. See `references/error-handling.md` for recovery.

---

### Phase 3: GENERATE -- Create Routing Table Entries

**Constraints**: Deterministic (no randomness); exact /do format per `references/routing-format.md`; conflicts detected; sorted alphabetically; no duplicates.

**Step 1**: Run generation:

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/generate_routes.py --input metadata.json --output routing_entries.json
```

**Step 2**: Process: load format spec, map to routing tables, format entries, detect conflicts (see `references/conflict-resolution.md`), sort alphabetically.

**Step 3**: Low-severity conflicts: auto-resolved via specificity rules. High-severity: blocks gate, requires manual resolution.

**Gate**: All mapped, /do format followed, conflicts documented, no duplicates. See `references/error-handling.md` for recovery.

---

### Phase 4A: UPDATE -- Modify commands/do.md

**Constraints**: Timestamped backup before modification; hand-written entries (without `[AUTO-GENERATED]`) never overwritten; markdown validated; atomic restore on failure.

**Step 1**: Run update:

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/update_routing.py --input routing_entries.json --target $HOME/vexjoy-agent/commands/do.md --backup
```

**Step 2**: Confirm backup at `commands/.do.md.backup.{timestamp}`.

**Step 3**: Review diff (new +, modified - old / + new, preserved unchanged).

**Step 4**: Correct => confirm. Unexpected => abort. With --auto-commit: skip confirmation.

**Step 5**: Post-update validation: pipe alignment, header separators, column counts, no orphaned rows. Failure => automatic restore.

**Gate**: Backup created, manual entries preserved, markdown validated, diff confirmed. Failure => RESTORE.

---

### Phase 4B: UPDATE -- Update Command Files

**Constraints**: Only update if referencing outdated/invalid skills; backups for all modified files; all referenced skills must exist; markdown validated.

**Step 1**: Run:

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/update_commands.py --commands-dir $HOME/vexjoy-agent/commands --metadata metadata.json --backup
```

**Step 2**: Process: scan command files for skill references, identify outdated/invalid, update, backup, validate.

**Gate**: Backups created, all referenced skills exist, markdown validated.

---

### Phase 5: VERIFY -- Final Validation

**Constraints**: All auto-generated entries marked `[AUTO-GENERATED]`; no duplicates; all referenced skills/agents exist; complexity matches Simple/Medium/Complex; overlapping patterns documented.

**Step 1**: Run:

```bash
python3 ~/.claude/skills/routing-table-updater/scripts/validate.py --target $HOME/vexjoy-agent/commands/do.md
```

**Step 2**: Checks: structural (tables present, headers, pipes), content (markers, no duplicates, references valid), conflicts (documented, priority applied), integration (sample pattern tests).

**Gate**: All checks pass. Task complete. See `references/error-handling.md` for recovery.

---

## Batch Mode

When invoked by `pipeline-scaffolder` Phase 4 (INTEGRATE), operates in batch to register N skills and 0-1 agents in a single pass.

See `references/batch-mode.md` for input format, process, and comparison table.

---

## Integration

Typically invoked after:
- **skill-creator**: New skill needs routing entry
- **skill/agent modification**: Description or trigger changes need refresh
- **Repository maintenance**: Periodic sync to catch drift
- **pipeline-scaffolder Phase 3**: N skills need routing (batch mode)

```
skill: routing-table-updater
```

Reads all skill/agent metadata but never modifies them. Writes only to `skills/do/SKILL.md`, `skills/do/references/routing-tables.md`, `agents/INDEX.json`, and `commands/*.md`.

---

## Error Handling

See `references/error-handling.md` for full error matrix and per-phase gate failure recovery.

---

## References

- `${CLAUDE_SKILL_DIR}/references/routing-format.md`: /do routing table format spec
- `${CLAUDE_SKILL_DIR}/references/extraction-patterns.md`: Trigger extraction patterns
- `${CLAUDE_SKILL_DIR}/references/conflict-resolution.md`: Conflict types, priority rules, resolution
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world routing table update examples
- `${CLAUDE_SKILL_DIR}/references/skill-examples.md`: Worked 5-phase pipeline examples
- `${CLAUDE_SKILL_DIR}/references/batch-mode.md`: Batch mode invocation
- `${CLAUDE_SKILL_DIR}/references/error-handling.md`: Error matrix and recovery
