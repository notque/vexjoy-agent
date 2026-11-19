# Repository Architecture

This repository contains skills, pipelines, hooks, and scripts for Claude Code. The repo ships no specialist agents (retired in plans/009): the dispatch worker is the built-in `general-purpose` agent and the skill carries the domain. Private overlay agents (`agents/INDEX.local.json`) still install and validate when named.

## Component Types

| Component | Location | Purpose | Format |
|-----------|----------|---------|--------|
| **Skill** | `skills/*/SKILL.md` | Domain (e.g., Go, Python, K8s) or methodology (e.g., TDD, debugging) | Markdown with YAML frontmatter |
| **Pipeline** | `skills/process/workflow/references/*.md` | Multi-phase structured workflow (same format as skills) | Markdown with YAML frontmatter |
| **Hook** | `hooks/*.py` | Event-driven automation | Python script |
| **Script** | `scripts/*.py`, `scripts/*.sh` | Deterministic operations | Python or shell script |

> **Note**: Pipelines are skills with explicit numbered phases and gates. They live in `skills/process/workflow/references/` for organizational clarity but are synced to `~/.claude/skills/` at install time, so Claude Code discovers them as regular skills.

## Key Frontmatter Fields

```yaml
---
name: skill-name
description: Brief purpose description
user-invocable: false    # Hide from slash menu (internal skills)
context: fork            # Run in isolated sub-agent context
model: opus              # Optional; omit to inherit. opus | fable | inherit; haiku only with a read-only `tools:` list; never sonnet (`/do` SKILL.md, Model choice)
allowed-tools:           # YAML list format
  - Read
  - Write
  - Bash
hooks:                   # Skill-specific lifecycle hooks
  PostToolUse:
    - type: command
      command: python3 -c "..."
      timeout: 3000
routing:                 # Routing metadata
  triggers: [keyword1, keyword2]
  pairs_with: [skill1, skill2]  # skills or pipelines only
  complexity: Simple | Medium | Complex
  category: domain | devops | meta
---
```

## Skill Reference Files

Skills use progressive disclosure. Domain knowledge lives in `references/`, loaded on demand based on task context. A retired agent's body lives at `<skill>/references/<slug>.md` and its references at `<skill>/references/<slug>/`.

### Structure

```
skills/frontend/frontend/
├── SKILL.md                              # Skill body with the Reference Loading Table
└── references/
    ├── react-native.md                   # Former agent body, loaded for React Native tasks
    └── react-native/
        ├── list-performance.md           # Loaded for list/scroll tasks
        └── navigation-patterns.md        # Loaded for navigation tasks
```

### Reference Loading Table (mandatory for skills with references)

Every skill with a `references/` directory MUST have a reference loading table in its SKILL.md. `build-dispatch.py` tells every worker to consult it. The table maps task keywords to specific reference files so the model knows WHICH file to load for the current task — not all of them.

```markdown
| Task involves | Load reference |
|---|---|
| Lists, FlatList, scrolling | `list-performance.md` |
| Animation, gestures, transitions | `animation-patterns.md` |
| Navigation, screens, routing | `navigation-patterns.md` |
```

Without this table, the worker either loads nothing (missing context) or everything (wasted tokens). Both defeat progressive disclosure.

### Reference File Standards

| Rule | Requirement |
|---|---|
| **Size** | <= 500 lines per file. Split at ~400 if growing. |
| **Framing** | Joy-checked: lead with what patterns ENABLE, not what they PREVENT. Use "Instead of:" / "Use:" not "Bad:" / "Good:" or "Incorrect:" / "Correct:". |
| **Structure** | Each section: `## Title` + `**Impact:** LEVEL` + explanation + code examples |
| **Isolation** | Reference only files in the same skill's directory. No cross-skill references. |
| **Comment header** | First line after title: `<!-- Loaded by {skill-name} when task involves {domain} -->` |

### Validation

Run `scripts/validate-references.py --all` to check:
- Every declared reference file exists on disk
- Every file on disk is declared in the SKILL.md body
- Structural compliance (headings, content, code examples)

Run `scripts/validate-references.py --check-size` to check reference size limits (500 lines) against the dated debt register and flag empty `references/` dirs.

Run `python3 -m pytest scripts/tests/test_reference_loading.py` to verify:
- Reference loading tables are complete
- Keyword→reference mapping selects the right files

### When Adding Domain Knowledge

Add it to the skill that owns the domain; do not create a repo agent.

1. Add reference files under `skills/<group>/<skill>/references/` (one per domain concern, <= 500 lines each)
2. Add rows to the skill's reference loading table mapping keywords → files
3. Regenerate `skills/INDEX.json` via `scripts/generate-skill-index.py` when frontmatter changes
4. Run `scripts/validate-references.py --all` to verify
