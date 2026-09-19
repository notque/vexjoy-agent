# Routing Entry Format Specification

Routing metadata lives in two layers:

1. **Source of truth**: the YAML frontmatter `routing:` block in each `skills/*/SKILL.md` and `agents/*.md` file. Hand-authored, tracked in git.
2. **Generated artifact**: `skills/INDEX.json` and `agents/INDEX.json` (schema v2.0). Built from frontmatter by the repo generator scripts. Gitignored — regenerate to repair; the generators own ordering and formatting.

## Skill Frontmatter Routing Block

```yaml
---
name: routing-table-updater
description: "Maintain /do routing tables when skills or agents change."
user-invocable: false
routing:
  triggers:
    - "update routing tables"
    - "routing drift"
  category: meta-tooling
  pairs_with:
    - toolkit-evolution
---
```

| Field | Required | Purpose |
|-------|----------|---------|
| `name` | yes | Skill identifier; index key |
| `description` | yes | Intent text the router reads |
| `routing.triggers` | yes | Phrases that route to this skill |
| `routing.category` | yes | Coverage grouping |
| `routing.pairs_with` | no | Components commonly co-dispatched |
| `routing.not_for` | no | Negative routing examples |
| `routing.force_route` | no | High-confidence route on a single trigger match |
| `user-invocable` | no | `false` hides the skill from direct user invocation |

## Agent Frontmatter Routing Block

Same shape; agents add `complexity` (e.g., `Medium`, `Complex`, `Medium-Complex`) and use `description` as the router's short description.

## skills/INDEX.json Entry Shape

```json
{
  "version": "2.0",
  "generated": "2026-07-01T23:44:02Z",
  "generated_by": "scripts/generate-skill-index.py",
  "skills": {
    "routing-table-updater": {
      "file": "skills/meta/routing-table-updater/SKILL.md",
      "description": "Maintain /do routing tables when skills or agents change.",
      "triggers": ["update routing tables", "routing drift"],
      "category": "meta-tooling",
      "user_invocable": false,
      "pairs_with": ["toolkit-evolution", "generate-claudemd"]
    }
  }
}
```

Optional per-entry fields when present in frontmatter: `not_for`, `force_route`, `agent`, `version`.

## agents/INDEX.json Entry Shape

```json
{
  "agents": {
    "ansible-automation-engineer": {
      "file": "agents/ansible-automation-engineer.md",
      "short_description": "Ansible automation: playbooks, roles, collections, Molecule testing, Vault security",
      "triggers": ["ansible", "playbook"],
      "pairs_with": ["verification-before-completion"],
      "complexity": "Medium-Complex",
      "category": "infrastructure"
    }
  }
}
```

## Regeneration

```bash
cd $HOME/vexjoy-agent
python3 scripts/generate-skill-index.py    # rebuilds skills/INDEX.json
python3 scripts/generate-agent-index.py    # rebuilds agents/INDEX.json
```

PostToolUse hooks (`hooks/posttooluse-sync-skill-index.py`, `hooks/posttooluse-sync-agent-index.py`) run these automatically when a SKILL.md or agent file is written or edited. Manual regeneration covers bulk changes, deletes outside the harness, and corrupted index files.

## Validity Rules

- Every entry's `file` path exists on disk (zero phantom entries).
- Every on-disk skill/agent with valid frontmatter appears in its index.
- Triggers are specific phrases, unique across components where practical; resolve overlaps per `conflict-resolution.md`.
- Edit routing metadata in the source frontmatter, then regenerate — the index rebuild discards direct index edits.
