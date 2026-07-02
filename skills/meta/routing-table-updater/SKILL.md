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
    - "update routing tables"
    - "sync routing tables"
    - "routing maintenance"
    - "rebuild routing index"
    - "routing drift"
  not_for: "fleet-wide routing policy, trigger governance, or standards enforcement (use the toolkit-governance-engineer agent). This skill mechanically regenerates and repairs the INDEX files."
  category: meta-tooling
  pairs_with:
    - toolkit-evolution
    - generate-claudemd
---

# Routing Table Updater Skill

## Overview

This skill maintains the /do routing indices when skills or agents are added, modified, or removed. It implements a **Phase-Gated Pipeline** -- scan, extract, generate, update, verify -- with deterministic script execution at each phase.

The skill reads metadata from all skills and agents (never modifies them) and validates and repairs the generated routing indices `skills/INDEX.json` and `agents/INDEX.json`. PostToolUse hooks (`hooks/posttooluse-sync-skill-index.py`, `hooks/posttooluse-sync-agent-index.py`) regenerate the indices automatically on every SKILL.md or agent-file edit; this skill covers drift those hooks miss (bulk changes, deletes outside the harness, corrupted index files).

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| batch registration of many skills (invoked by pipeline-scaffolder) | `batch-mode.md` | Loads detailed guidance from `batch-mode.md`. |
| resolving trigger conflicts: priority rules and severity levels | `conflict-resolution.md` | Loads detailed guidance from `conflict-resolution.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| worked update scenarios: new skill, conflict, manual entry, complexity change | `examples.md` | Loads detailed guidance from `examples.md`. |
| extracting trigger phrases: 'use when' clauses, action verbs, domain keywords, complexity inference | `extraction-patterns.md` | Loads detailed guidance from `extraction-patterns.md`. |
| routing entry format: frontmatter routing block fields, INDEX.json entry shape, regeneration | `routing-format.md` | Loads detailed guidance from `routing-format.md`. |
| skill-entry examples for registering a newly created skill | `skill-examples.md` | Loads detailed guidance from `skill-examples.md`. |

## Instructions

### Phase 1: SCAN -- Discover All Skills and Agents

**Goal**: Find every skill and agent file in the repository.

**Constraints**: Repository must be at agents toolkit root (requires `commands/do.md`); only scan `skills/*/SKILL.md` and `agents/*.md` formats; file permissions must allow reading.

**Step 1: Run scan script**

```bash
python3 ~/.claude/skills/meta/routing-table-updater/scripts/scan.py --repo $HOME/vexjoy-agent
```

**Step 2: Validate scan output**

Expected output is JSON with `skills_found`, `agents_found`, `skills` (array of paths to skills/*/SKILL.md), `agents` (array of paths to agents/*.md).

**Step 3: Check for gaps**

Compare discovered count against expected. If missing, check directory naming, agent file naming, or file permissions.

**Gate**: All skill directories and agent files are discovered without permission errors. Proceed to Phase 2 only after the gate passes. See `references/error-handling.md` for gate failure recovery.

---

### Phase 2: EXTRACT -- Parse Metadata

**Goal**: Extract YAML frontmatter, trigger patterns, complexity, and routing table targets from every discovered file.

**Constraints**: YAML frontmatter must be valid; required fields (`name`, `description`) must be present; trigger patterns extracted from description text; complexity inference must follow `references/extraction-patterns.md`.

**Step 1: Run extraction script**

```bash
python3 ~/.claude/skills/meta/routing-table-updater/scripts/extract_metadata.py --input scan_results.json --output metadata.json
```

**Step 2: Verify extraction completeness**

For each capability, confirm extracted fields: `name`, `description`, `trigger_patterns` (skills), `domain_keywords` (agents), `complexity` (Simple, Medium, Complex), `routing_table` (Intent Detection, Task Type, Domain-Specific, or Combination).

**Step 3: Validate trigger pattern quality**

Review against `references/extraction-patterns.md`. Patterns must be specific enough to avoid false matches, broad enough to catch common phrasings, and free of generic terms.

**Description trimming**: skill descriptions trim safely to ≤40 router-line tokens when the frontmatter `routing.triggers` array stays untouched — triggers carry routing weight independently of the description. Verify trims with `scripts/skill-sprawl-audit.py` plus the routing-benchmark and trigger-ambiguity CI jobs (evidence: PR #801, 11 trims, routing-benchmark 68/68).

**Gate**: All YAML parsed successfully, required fields are present, trigger patterns are extracted for skills, and domain keywords are extracted for agents. Proceed to Phase 3 only after the gate passes. See `references/error-handling.md` for gate failure recovery.

---

### Phase 3: GENERATE -- Create Routing Table Entries

**Goal**: Map extracted metadata to routing entries and detect trigger conflicts before the indices are rebuilt.

**Constraints**: Deterministic generation (no randomness); pattern conflicts detected immediately; entries sorted alphabetically; duplicates within the same group block gate passage.

**Step 1: Run generation script**

```bash
python3 ~/.claude/skills/meta/routing-table-updater/scripts/generate_routes.py --input metadata.json --output routing_entries.json
```

**Step 2: Understand the generation process**

1. Group each capability by the routing classification extracted in Phase 2
2. Detect pattern conflicts (see `references/conflict-resolution.md`)
3. Sort entries alphabetically within groups

**Step 3: Review conflict detection output**

Low-severity conflicts: script applies specificity rules automatically. High-severity conflicts: script blocks gate passage and requires manual resolution.

**Gate**: All capabilities are mapped, conflicts are documented, and no duplicates remain within the same group. Proceed to Phase 4 only after the gate passes. See `references/error-handling.md` for gate failure recovery.

---

### Phase 4: UPDATE -- Repair INDEX.json

**Goal**: Bring `skills/INDEX.json` and `agents/INDEX.json` in line with filesystem state.

**Constraints**: Both indices are generated, gitignored artifacts — repair means regenerating from frontmatter via the repo scripts; hand-edits to index files are lost on the next regeneration; source SKILL.md and agent files stay untouched; run from the repo root.

**Step 1: Regenerate both indices**

```bash
cd $HOME/vexjoy-agent
python3 scripts/generate-skill-index.py
python3 scripts/generate-agent-index.py
```

**Step 2: Check for phantom entries**

Every entry's `file` path must exist on disk:

```bash
python3 - <<'EOF'
import json, os
for idx, key in (("skills/INDEX.json", "skills"), ("agents/INDEX.json", "agents")):
    entries = json.load(open(idx))[key]
    phantom = [n for n, e in entries.items() if not os.path.exists(e["file"])]
    print(idx, len(entries), "entries,", len(phantom), "phantom", phantom or "")
EOF
```

**Gate**: Both generators exit 0 and both indices contain zero phantom `file` paths. On generator failure, fix the offending frontmatter (the error names the file) and rerun. Proceed to Phase 5 only after the gate passes.

---

### Phase 5: VERIFY -- Validate Routing Correctness

**Goal**: Final validation of the skill package and the rebuilt indices.

**Constraints**: No duplicate trigger phrases within an index; every index entry's `file` path exists; complexity values must match Simple/Medium/Complex; overlapping patterns documented with priority rules.

**Step 1: Run validation script**

```bash
python3 ~/.claude/skills/meta/routing-table-updater/scripts/validate.py
```

Validates skill package structure, SKILL.md frontmatter, and script executability. Exit 0 = pass.

**Step 2: Understand verification checks**

1. **Structural**: Skill package complete (SKILL.md, scripts, references), frontmatter parses
2. **Content**: No duplicate triggers, every index entry's `file` path exists (Phase 4 Step 2 check)
3. **Conflicts**: Overlapping patterns documented, priority rules applied

**Gate**: All checks pass. Task complete ONLY if final gate passes. See `references/error-handling.md` for gate failure recovery.

---

## Examples

See `references/skill-examples.md` for worked examples (new skill created, agent description updated, conflict detection, manual entry preserved).

---

## Batch Mode

When invoked by `pipeline-scaffolder` Phase 4 (INTEGRATE), this skill operates in batch mode to register N skills and 0-1 agents in a single pass.

See `references/batch-mode.md` for batch input format, batch process, and the batch vs single mode comparison table.

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

The skill reads metadata from all skills and agents but never modifies them. Its only write targets are the generated indices `skills/INDEX.json` and `agents/INDEX.json`, always via the repo generator scripts.

---

## Error Handling

See `references/error-handling.md` for the full error matrix (YAML parse errors, routing conflicts, manual entry overwrites, markdown validation failures) and per-phase gate failure recovery.

---

## References

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/routing-format.md`: routing entry format specification (frontmatter routing block fields, INDEX.json entry shape, regeneration commands)
- `${CLAUDE_SKILL_DIR}/references/extraction-patterns.md`: Trigger phrase extraction patterns (regex, keyword maps, complexity inference)
- `${CLAUDE_SKILL_DIR}/references/conflict-resolution.md`: Conflict types, priority rules, severity levels, resolution process
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world examples of routing table updates (new skill, updated agent, conflict detection, manual preservation)
- `${CLAUDE_SKILL_DIR}/references/skill-examples.md`: Worked examples for the 5-phase pipeline (Phase 1-5 walkthroughs)
- `${CLAUDE_SKILL_DIR}/references/batch-mode.md`: Batch mode invocation by pipeline-scaffolder (input format, process, comparison)
- `${CLAUDE_SKILL_DIR}/references/error-handling.md`: Error matrix and per-phase gate failure recovery
