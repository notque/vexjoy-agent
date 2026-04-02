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
