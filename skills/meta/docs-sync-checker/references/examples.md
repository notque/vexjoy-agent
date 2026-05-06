# Documentation Update Examples

This file shows before/after examples of documentation updates for common scenarios.

## Example 1: Adding New Skill Documentation

### Scenario
You created a new skill called `docs-sync-checker` in `skills/meta/docs-sync-checker/SKILL.md`

### YAML Frontmatter
```yaml
---
name: docs-sync-checker
description: Verify all skills, agents, and commands are documented in repository READMEs
---
```

### Before: skills/README.md

```markdown
# Skills

| Name | Description | Command | Hook |
|------|-------------|---------|------|
| code-linting | Combined Python (ruff) and JavaScript (Biome) linting | `skill: code-linting` | - |
| test-driven-development | RED-GREEN-REFACTOR cycle for all code changes | `skill: test-driven-development` | - |
```

### After: skills/README.md

```markdown
# Skills

| Name | Description | Command | Hook |
|------|-------------|---------|------|
| code-linting | Combined Python (ruff) and JavaScript (Biome) linting | `skill: code-linting` | - |
| docs-sync-checker | Verify all skills, agents, and commands are documented in repository READMEs | `skill: docs-sync-checker` | - |
| test-driven-development | RED-GREEN-REFACTOR cycle for all code changes | `skill: test-driven-development` | - |
```

**Note**: Insert in alphabetical order for easy navigation.

### Before: docs/REFERENCE.md

```markdown
## Skills Reference

### code-linting

Combined Python (ruff) and JavaScript (Biome) linting skill.

**Usage**: `skill: code-linting`
**Version**: 1.2.0
```

### After: docs/REFERENCE.md

```markdown
## Skills Reference

### code-linting

Combined Python (ruff) and JavaScript (Biome) linting skill.

**Usage**: `skill: code-linting`
**Version**: 1.2.0

### docs-sync-checker

Verify all skills, agents, and commands are documented in repository READMEs. Automatically detect documentation drift by comparing filesystem tools with documented tools.

**Usage**: `skill: docs-sync-checker`
**Version**: 1.0.0
```

---

## Example 2: Removing Deprecated Agent Documentation

### Scenario
You removed the deprecated agent `old-agent.md` from `agents/` directory

### Before: agents/README.md

```markdown
# Agents

| Name | Description |
|------|-------------|
| golang-general-engineer | Deep expertise in Go development, architecture, debugging, concurrency |
| old-agent | [DEPRECATED] Use new-agent instead. Removal: 2025-01-15 |
| research-coordinator-engineer | Orchestrate research operations that extract and synthesize information |
```

### After: agents/README.md

```markdown
# Agents

| Name | Description |
|------|-------------|
| golang-general-engineer | Deep expertise in Go development, architecture, debugging, concurrency |
| research-coordinator-engineer | Orchestrate research operations that extract and synthesize information |
```

**Note**: Remove the entire row for the deprecated agent.

### Before: docs/REFERENCE.md

```markdown
## Agents Reference

### golang-general-engineer

Deep expertise in Go development, architecture, debugging, concurrency.

### old-agent

[DEPRECATED] Use new-agent instead. This agent has been replaced.

### research-coordinator-engineer

Orchestrate research operations.
```

### After: docs/REFERENCE.md

```markdown
## Agents Reference

### golang-general-engineer

Deep expertise in Go development, architecture, debugging, concurrency.

### research-coordinator-engineer

Orchestrate research operations.
```

**Note**: Remove the entire section for the deprecated agent.

---

## Example 3: Updating Command Documentation

### Scenario
You created a new namespaced command `commands/code/cleanup.md`

### Before: commands/README.md

```markdown
# Available Commands

- `/do` - Smart router that automatically selects the right agents, skills, and commands
- `/agents` - List all specialized agents
- `/skills` - List all skills with triggers
```

### After: commands/README.md

```markdown
# Available Commands

- `/agents` - List all specialized agents
- `/code cleanup` - Find and fix small neglected improvements (stale TODOs, unused imports, etc.)
- `/do` - Smart router that automatically selects the right agents, skills, and commands
- `/skills` - List all skills with triggers
```

**Note**:
- Insert in alphabetical order
- Use `/code cleanup` format (with slash and space) for namespaced commands
- Extract description from command file

---

## Example 4: Fixing Version Mismatch

### Scenario
You updated `code-linting` skill from version 1.1.0 to 1.2.0 in YAML, but forgot to update README

### YAML Frontmatter (Updated)
```yaml
---
name: code-linting
---
```

### Before: docs/REFERENCE.md

```markdown
### code-linting

Combined Python (ruff) and JavaScript (Biome) linting skill.

**Usage**: `skill: code-linting`
**Version**: 1.1.0
```

### After: docs/REFERENCE.md

```markdown
### code-linting

Combined Python (ruff) and JavaScript (Biome) linting skill.

**Usage**: `skill: code-linting`
**Version**: 1.2.0
```

**Note**: Only update version number, keep description and usage unchanged.

---

## Example 5: Adding Skill with Hook

### Scenario
You created `github-actions-check` skill with associated hook `UserToolUse`

### YAML Frontmatter
```yaml
---
name: github-actions-check
description: Proactively checks GitHub Actions workflow status after git push
---
```

### Before: skills/README.md

```markdown
| Name | Description | Command | Hook |
|------|-------------|---------|------|
| code-linting | Combined Python and JavaScript linting | `skill: code-linting` | - |
```

### After: skills/README.md

```markdown
| Name | Description | Command | Hook |
|------|-------------|---------|------|
| code-linting | Combined Python and JavaScript linting | `skill: code-linting` | - |
| github-actions-check | Proactively checks GitHub Actions workflow status after git push | `skill: github-actions-check` | UserToolUse |
```

**Note**: Specify hook name in Hook column (not `-`)

---

## Example 6: Handling Experimental Tools

### Scenario
You created `auto-fix-mode` skill that's still experimental

### YAML Frontmatter
```yaml
---
name: auto-fix-mode
description: [EXPERIMENTAL] Automatically fix missing documentation entries
---
```

### Documentation: skills/README.md

```markdown
| Name | Description | Command | Hook |
|------|-------------|---------|------|
| auto-fix-mode | [EXPERIMENTAL] Automatically fix missing documentation entries | `skill: auto-fix-mode` | - |
| code-linting | Combined Python and JavaScript linting | `skill: code-linting` | - |
```

**Note**:
- Include `[EXPERIMENTAL]` prefix in description
- Use version 0.x.x to indicate experimental status
- Still document in README (prevents "missing entry" reports)

---

## Example 7: Updating Description Across Multiple Locations

### Scenario
You improved the description of `test-driven-development` skill and want consistency everywhere

### New YAML Description
```yaml
---
name: test-driven-development
description: RED-GREEN-REFACTOR cycle for all code changes. Write failing test first, implement minimum code to pass, then refactor.
---
```

### Update 1: skills/README.md

**Before**:
```markdown
| test-driven-development | TDD workflow for code changes | `skill: test-driven-development` | - |
```

**After**:
```markdown
| test-driven-development | RED-GREEN-REFACTOR cycle for all code changes. Write failing test first, implement minimum code to pass, then refactor. | `skill: test-driven-development` | - |
```

### Update 2: docs/REFERENCE.md

**Before**:
```markdown
### test-driven-development

Test-driven development workflow.

**Usage**: `skill: test-driven-development`
```

**After**:
```markdown
### test-driven-development

RED-GREEN-REFACTOR cycle for all code changes. Write failing test first, implement minimum code to pass, then refactor. Never skip the red phase.

**Usage**: `skill: test-driven-development`
**Version**: 2.1.0
```

**Note**: Expand description in REFERENCE.md (more detail than README table)

---

## Example 8: Batch Update After Multiple Changes

### Scenario
You created 3 new skills and removed 1 old skill. Update all at once.

### Changes
- Created: `skill-a`, `skill-b`, `skill-c`
- Removed: `old-skill`

### Before: skills/README.md

```markdown
| Name | Description | Command | Hook |
|------|-------------|---------|------|
| code-linting | Combined Python and JavaScript linting | `skill: code-linting` | - |
| old-skill | Old skill no longer maintained | `skill: old-skill` | - |
| test-driven-development | TDD workflow | `skill: test-driven-development` | - |
```

### After: skills/README.md

```markdown
| Name | Description | Command | Hook |
|------|-------------|---------|------|
| code-linting | Combined Python and JavaScript linting | `skill: code-linting` | - |
| skill-a | Description of skill A | `skill: skill-a` | - |
| skill-b | Description of skill B | `skill: skill-b` | - |
| skill-c | Description of skill C | `skill: skill-c` | - |
| test-driven-development | TDD workflow | `skill: test-driven-development` | - |
```

**Note**:
- Add all new skills in alphabetical order
- Remove old-skill row
- Maintain consistent formatting

---

## Example 9: Documenting Command in Root README

### Scenario
You want to highlight `/do` command in root README overview

### Before: README.md

```markdown
# Agents Repository

This repository contains Claude Code agents and skills.

## Getting Started

Clone the repository and explore the skills/ and agents/ directories.
```

### After: README.md

```markdown
# Agents Repository

This repository contains Claude Code agents and skills.

## Getting Started

Clone the repository and explore the skills/ and agents/ directories.

For complex requests, use the `/do` command - it automatically routes to the right agents and skills.

Example: `Use /do to analyze this codebase and suggest improvements`
```

**Note**: This is narrative reference, not catalog entry. Sync checker will detect `/do` reference.

---

## Example 10: Complex Multi-Location Update

### Scenario
You created a major new agent `kubernetes-helm-engineer` and want comprehensive documentation

### YAML Frontmatter
```yaml
---
name: kubernetes-helm-engineer
description: Complete Kubernetes operations, troubleshooting, best practices, and cloud infrastructure expertise
---
```

### Update 1: agents/README.md

```markdown
| Name | Description |
|------|-------------|
| golang-general-engineer | Deep expertise in Go development |
| kubernetes-helm-engineer | Complete Kubernetes operations, troubleshooting, best practices, and cloud infrastructure expertise |
| research-coordinator-engineer | Orchestrate research operations |
```

### Update 2: docs/REFERENCE.md

```markdown
### kubernetes-helm-engineer

Complete Kubernetes operations, troubleshooting, best practices, and cloud infrastructure expertise.

This agent provides deep knowledge of:
- Kubernetes cluster operations and management
- Helm chart development and deployment
- Cloud infrastructure (AWS, GCP, Azure)
- Container orchestration best practices
- Troubleshooting and debugging K8s deployments

**Version**: 1.0.0
**Complexity**: High - for Kubernetes and cloud infrastructure tasks
```

### Update 3: README.md (Optional)

```markdown
## Specialized Agents

For Kubernetes and cloud infrastructure tasks, use `kubernetes-helm-engineer` agent.
```

**Note**: Major agents often documented in all three locations for visibility.

---

## Verification Workflow

After making any documentation updates:

```bash
# 1. Run docs-sync-checker to verify changes
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root . --output /tmp/scan.json
python3 skills/meta/docs-sync-checker/scripts/parse_docs.py --repo-root . --scan-results /tmp/scan.json --output /tmp/parse.json
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/parse.json --scan-results /tmp/scan.json

# 2. Expected output: "Status: ✅ ALL IN SYNC"

# 3. If issues remain, review report and fix

# 4. Commit tool and documentation together
git add skills/ agents/ commands/ README.md docs/REFERENCE.md
git commit -m "Add/update [tool-name] with documentation"
```

---

## Quick Reference: Common Patterns

### Add Skill
1. Create `skills/skill-name/SKILL.md` with YAML frontmatter
2. Add row to `skills/README.md` table
3. Add section to `docs/REFERENCE.md` (if significant skill)

### Remove Skill
1. Delete `skills/skill-name/` directory
2. Remove row from `skills/README.md` table
3. Remove section from `docs/REFERENCE.md` (if documented)
4. Remove references from `README.md` (if any)

### Update Skill Version
1. Update `version:` in `skills/skill-name/SKILL.md` YAML
2. Update version in `docs/REFERENCE.md` (if documented there)

### Add Agent
1. Create `agents/agent-name.md` with YAML frontmatter
2. Add row to `agents/README.md` table/list
3. Add section to `docs/REFERENCE.md` (if major agent)

### Add Command
1. Create `commands/command-name.md` or `commands/namespace/command-name.md`
2. Add item to `commands/README.md` list (use `/command-name` or `/namespace command-name` format)
3. Add section to `docs/REFERENCE.md` (if significant command)
