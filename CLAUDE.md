# Claude Code Toolkit

## Priority Order

When goals conflict, prioritize in this order:

1. **Produce correct, verified output** - Wrong output wastes everyone's time
2. **Maintain authentic voice and quality** - Generic AI output serves no one
3. **Complete the full task** - Partial work creates more work
4. **Be efficient** - Only after the above are satisfied

---

## How This Toolkit Works

The toolkit uses **agents, skills, hooks, and scripts** to absorb complexity that would otherwise fall on the user. Behavioral enforcement lives in these mechanisms, not in this file. Route to agents for all work. Load only the context required for the current task. Use scripts for deterministic work; reserve LLM judgment for contextual decisions.

---

## CI Must Pass Before Merging

GitHub Actions (`Tests` workflow) must pass before any PR can be merged. Branch protection is enforced at the GitHub layer — the merge API physically fails if `Tests / lint` or `Tests / test` checks have not passed.

For Python changes: run `ruff check . --config pyproject.toml` AND `ruff format --check . --config pyproject.toml` locally before pushing. Running only `ruff check` misses formatting violations.

---

## Local-Only Directories

The `adr/` directory is gitignored — ADR files are local development artifacts that exist on disk but are excluded from git. Use `ls adr/` to find them, not `git diff`. These files drive architectural decisions but are never pushed to the remote.

---

## Agent Reference Files

When creating or modifying agents with `references/` directories, run validation before committing:
- `python3 scripts/validate-references.py --agent {name}` — structural checks
- `python3 -m pytest scripts/tests/test_reference_loading.py -k {name}` — progressive disclosure tests

Standards: reference files <= 500 lines, joy-checked framing, loading table in agent body. Full spec in `skills/do/references/repo-architecture.md`.

---

## Reference Documentation

Domain-specific reference content lives in skill reference files, loaded on demand:

> Repository architecture and frontmatter fields: `skills/do/references/repo-architecture.md`

> Execution architecture (Router → Agent → Skill → Script): `skills/do/references/execution-architecture.md`

> Pipeline architecture (phases, templates, principles): `skills/do/references/pipeline-guide.md`

> Planning system (task_plan.md template, rules): `skills/do/references/planning-guide.md`

> Voice system (components, validation commands): `skills/workflow/references/voice-writer.md`

> Routing system (triggers, force-routes, agent selection): `skills/do/references/routing-guide.md`

> Full routing tables (all agents and skills): `skills/do/references/routing-tables.md`

> Hooks system (event types, features, error learning): `skills/do/references/hooks-guide.md`

> Quality gates (evaluation criteria, pre-completion checklist): `skills/do/references/quality-gates.md`
