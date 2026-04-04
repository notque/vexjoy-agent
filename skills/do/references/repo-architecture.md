# Repository Architecture

This repository contains agents, skills, and hooks for Claude Code.

## Component Types

| Component | Location | Purpose | Format |
|-----------|----------|---------|--------|
| **Agent** | `agents/*.md` or `agents/<name>/` | Domain expert (e.g., Go, Python, K8s) | Markdown with YAML frontmatter |
| **Skill** | `skills/*/SKILL.md` | Workflow methodology (e.g., TDD, debugging) | Markdown with YAML frontmatter |
| **Pipeline** | `skills/workflow/references/*.md` | Multi-phase structured workflow (same format as skills) | Markdown with YAML frontmatter |
| **Hook** | `hooks/*.py` | Event-driven automation | Python script |
| **Script** | `scripts/*.py`, `scripts/*.sh` | Deterministic operations | Python or shell script |

> **Note**: Pipelines are skills with explicit numbered phases and gates. They live in `skills/workflow/references/` for organizational clarity but are synced to `~/.claude/skills/` at install time, so Claude Code discovers them as regular skills.

## Key Frontmatter Fields

```yaml
---
name: skill-name
description: Brief purpose description
version: 1.0.0
user-invocable: false    # Hide from slash menu (internal skills)
context: fork            # Run in isolated sub-agent context
agent: golang-general-engineer  # Declare executor agent
model: opus              # Model preference: opus | sonnet | haiku
allowed-tools:           # YAML list format
  - Read
  - Write
  - Bash
hooks:                   # Agent-specific lifecycle hooks
  PostToolUse:
    - type: command
      command: python3 -c "..."
      timeout: 3000
routing:                 # Agent routing metadata (agents only)
  triggers: [keyword1, keyword2]
  pairs_with: [skill1, skill2]
  complexity: Simple | Medium | Complex
  category: domain | devops | meta
---
```

## Agent Reference Files

Agents use the same progressive disclosure pattern as skills. Domain knowledge lives in `references/` subdirectories, loaded on demand based on task context.

### Structure

```
agents/
├── react-native-engineer.md              # Agent body (< 300 lines)
└── react-native-engineer/
    └── references/
        ├── list-performance.md           # Loaded for list/scroll tasks
        ├── animation-patterns.md         # Loaded for animation tasks
        └── navigation-patterns.md        # Loaded for navigation tasks
```

### Reference Loading Table (mandatory for agents with references)

Every agent with a `references/` directory MUST have a reference loading table in its body. The table maps task keywords to specific reference files so the model knows WHICH file to load for the current task — not all of them.

```markdown
| Task involves | Load reference |
|---|---|
| Lists, FlatList, scrolling | `list-performance.md` |
| Animation, gestures, transitions | `animation-patterns.md` |
| Navigation, screens, routing | `navigation-patterns.md` |
```

Without this table, the agent either loads nothing (missing context) or everything (wasted tokens). Both defeat progressive disclosure.

### Reference File Standards

| Rule | Requirement |
|---|---|
| **Size** | <= 500 lines per file. Split at ~400 if growing. |
| **Framing** | Joy-checked: lead with what patterns ENABLE, not what they PREVENT. Use "Instead of:" / "Use:" not "Bad:" / "Good:" or "Incorrect:" / "Correct:". |
| **Structure** | Each section: `## Title` + `**Impact:** LEVEL` + explanation + code examples |
| **Isolation** | Reference only files in the same agent's directory. No cross-agent references. |
| **Comment header** | First line after title: `<!-- Loaded by {agent-name} when task involves {domain} -->` |

### Validation

Run `scripts/validate-references.py --all` to check:
- Every declared reference file exists on disk
- Every file on disk is declared in the agent body
- Structural compliance (headings, content, code examples)
- Size limits

Run `python3 -m pytest scripts/tests/test_reference_loading.py` to verify:
- Reference loading tables are complete
- Keyword→reference mapping selects the right files
- Joy-check compliance on headings

### When Creating a New Agent

1. Create the agent `.md` file with frontmatter and workflow phases
2. Create `agents/{name}/references/` directory
3. Add reference files (one per domain concern, <= 500 lines each)
4. Add a reference loading table to the agent body mapping keywords → files
5. Register in `agents/INDEX.json` via `scripts/generate-agent-index.py`
6. Run `scripts/validate-references.py --agent {name}` to verify
7. Add test cases to `scripts/tests/test_reference_loading.py`
