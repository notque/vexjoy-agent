# Documentation Structure Reference

Where each tool type is documented, in what format, and how a drift gets fixed. `scripts/parse_docs.py` (`PRIMARY_DOCS`) is the source of truth for the targets; `scripts/validate.py` fails if any target is missing.

## Primary docs

| Tool type | Filesystem | Primary doc | Maintained by | Fix a drift |
|-----------|------------|-------------|---------------|-------------|
| Skill | `skills/<category>/<name>/SKILL.md` | `docs/skills.md` | `scripts/generate-skills-doc.py` | Rerun the generator |
| Agent | `agents/<name>.md` | `docs/routing-map.md` (`## AGENTS` table) | `scripts/generate-routing-map.py` | Rerun the generator |
| Command | `commands/<name>.md` | `docs/REFERENCE.md` (`## Slash Commands` tables) | Hand-written | Add or remove the row |

There is no `agents/README.md` or `commands/README.md`. Never create one to satisfy this check.

## Formats the parser reads

`docs/skills.md`: one table per category; the first cell is the backticked skill name.

```markdown
| Skill | Description | Invoke |
|-------|-------------|--------|
| `deploy` | Deploy and infrastructure: web deploy, cron, package install, shell configuration. | `/deploy` |
```

`docs/routing-map.md`, `## AGENTS (N)` section: the first cell is the bare agent name.

```markdown
| name | when to call (description) | triggers | FORCE | not_for | pairs_with |
|---|---|---|---|---|---|
| golang-general-engineer | Go development: features, debugging, code review, performance | go, golang | | ... | programming |
```

`docs/REFERENCE.md`, `## Slash Commands` section: the first cell is the backticked `/command`. Rows whose first cell is not a `/command` (for example the "Available via `/do` Routing" table) are ignored.

```markdown
| Command | Purpose |
|---------|---------|
| `/retro` | Routing and review telemetry from learning.db: route health, route stats, errors, evidence, review false positives |
```

## Who is expected in each doc

| Tool | Expected in primary doc | Why |
|------|-------------------------|-----|
| Skill with `promoted_to` | No | `generate-skill-index.py` drops it from the index, so the catalog omits it |
| Skill or agent reached through a symlink | No | Private component; the generators strip private names |
| Every other skill, agent, and command | Yes | Missing entry, HIGH |
| Doc entry with no file on disk | — | Stale entry, MEDIUM |

## Root README.md

Narrative, not a catalog. The parser records its `/command` and `*-engineer` mentions for the report but never flags them.

## Related CI checks

The generated catalogs are already gated in `.github/workflows/test.yml`:

- `python3 scripts/generate-skills-doc.py --check` — `docs/skills.md` matches a fresh render.
- `python3 scripts/generate-routing-map.py --check` — `docs/routing-map.md` matches a fresh render.
- `python3 scripts/validate-doc-links.py`, `validate-doc-counts.py`, `validate-doc-commands.py` — links, count claims, and script paths named in docs.
