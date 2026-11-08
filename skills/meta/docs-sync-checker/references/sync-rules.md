# Documentation Sync Rules

Rules for which doc must list which tool, how issues are scored, and how they are fixed. Targets and formats: `documentation-structure.md`.

## Primary documentation rules

| Tool | Rule | Severity when absent |
|------|------|----------------------|
| Skill | Every public, non-promoted `skills/*/*/SKILL.md` appears in `docs/skills.md` | HIGH |
| Agent | Every public `agents/*.md` with frontmatter `name` appears in the `## AGENTS` table of `docs/routing-map.md` | HIGH |
| Command | Every `commands/*.md` appears in a `## Slash Commands` table of `docs/REFERENCE.md` | HIGH |
| Any | A doc entry whose file is gone | MEDIUM (stale) |

A missing primary doc is an error (exit 2), not an empty list. It means this skill's target list has drifted; fix `PRIMARY_DOCS` in `scripts/parse_docs.py` and the tables in this skill.

## Fixing issues

- Generated catalogs (`docs/skills.md`, `docs/routing-map.md`): rerun the generator. A hand edit is overwritten and fails the CI `--check`.
- If a skill or agent still does not appear after regenerating, its frontmatter is the cause: check `name`, `description`, and `promoted_to`.
- `docs/REFERENCE.md`: add or remove the `/command` row, using the command's frontmatter `description`.
- Commit the tool change and its doc change together.

## Description source

The YAML `description` field is authoritative. The generators copy it; for `docs/REFERENCE.md`, use it as the Purpose cell.

## Sync score

```
sync_score = (total_tools - total_issues) / total_tools * 100
```

`total_tools` counts every discovered skill, agent, and command; `total_issues` counts missing plus stale entries. Target 100%; one missing entry hides a tool from users.

## Exceptions

- `promoted_to` skills and symlinked (private) skills or agents are never expected in a catalog.
- `agents/*.md` files without frontmatter (for example `agents/base-instructions.md`, a shared prompt) are not agents.
- There is no ignore file. To hide a tool, promote or remove it.
