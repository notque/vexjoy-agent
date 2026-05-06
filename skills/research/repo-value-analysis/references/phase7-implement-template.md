# Phase 7: IMPLEMENT — Agent Dispatch Template

> **Scope**: Template for dispatching implementation agents during Phase 7 of the repo-value-analysis pipeline. Each HIGH recommendation with MISSING or PARTIAL coverage gets one agent dispatched using this template.

---

## Agent Prompt Template

Use this template when dispatching each implementation agent in Phase 7. Replace `{placeholders}` with actual values from the Phase 6 report.

```
You are implementing a capability for the vexjoy-agent toolkit based on a recommendation from an external repo analysis.

## Your Assignment

**Recommendation**: {recommendation_title}
**Gap type**: {MISSING | PARTIAL}
**What the external repo does**: {their_approach_summary}
**What we currently have**: {our_current_state}
**What to build**: {specific_deliverable}

## Mandatory First Step: Read PHILOSOPHY.md

Before writing any code or creating any files, read `docs/PHILOSOPHY.md` in full. The principles there govern every decision you make. Key constraints for this task:

1. **External Components Are Research Inputs, Not Imports**: The external repo's approach is reference material. Do not copy their code, their naming, their file structure, or their conventions. Study what they did, understand why it works, then rebuild it inside our architecture.

2. **One Domain, One Component**: Before creating anything new, search for existing components that already cover this domain:
   - `ls agents/*.md` — check for an agent that already handles this area
   - `ls skills/*/SKILL.md` — check for a skill that already covers this workflow
   - `ls scripts/*.py` — check for scripts that already do this work
   If overlap exists, extend the existing component (add a reference file, extend a phase) rather than creating a new one.

3. **Progressive Disclosure**: Keep runtime files thin. If you create an agent, the main `.md` file stays under 10k words. Deep content (pattern catalogs, detection commands, error-fix mappings) goes in `references/` subdirectories, loaded on demand.

4. **Deterministic Execution**: If the work can be expressed as a script (file searching, validation, counting, formatting), write a Python script in `scripts/` or the skill's `scripts/` directory. Reserve LLM judgment for design decisions and contextual analysis.

5. **Our Naming, Our Structure, Our Routing**: Use our naming conventions. Register new components in the routing system. Follow our file layout (`agents/*.md`, `skills/*/SKILL.md`, `skills/*/references/`).

## Implementation Steps

1. **Search existing components** — verify nothing already covers this gap
2. **Design the solution** — decide: new reference file on existing component? New script? Extension to existing skill phase?
3. **Build it** — create files following our conventions
4. **Register it** — if you created a new agent or skill, TWO registrations are required:
   - **Routing table**: add an entry to `skills/meta/do/references/routing-tables.md` — this is the canonical routing table. Every skill and agent must have an entry there (not in skill-local files, not in agent frontmatter alone). Run `python3 scripts/check-routing-drift.py` after adding the entry to verify it was added correctly — CI enforces this check.
   - **INDEX.json**: regenerate with `python3 scripts/generate-skill-index.py` (for skills) or `python3 scripts/generate-agent-index.py` (for agents)
5. **Validate it** — run the applicable quality gates:
   - Python files: `ruff check . --config pyproject.toml && ruff format --check . --config pyproject.toml`
   - New agent/skill reference files: `python3 scripts/validate-references.py`
   - New components: verify they appear in INDEX files
6. **Branch it** — create a feature branch for this implementation: `feat/{recommendation-slug}`

## What NOT To Do

- Do not copy files from the external repo into our tree
- Do not use external naming conventions or directory structures
- Do not create a new agent or skill when a reference file on an existing component would suffice
- Do not skip quality gates — a passing build is part of the deliverable
- Do not commit to main — create a feature branch

## Output Format

When done, report:

| Field | Value |
|-------|-------|
| **Status** | DONE / DEFERRED (with reason) |
| **Branch** | feat/{branch-name} |
| **Files created** | list of new files |
| **Files modified** | list of changed files |
| **Quality gates** | which gates ran, pass/fail |
| **Existing component extended** | name, or "N/A — new component created" |
| **PHILOSOPHY.md alignment** | which principles were applied and how |

## Citation Reporting

Your output is used by the orchestrator to build a citation entry in `docs/CITATIONS.md`. Report implementation details clearly enough to populate that entry:

- **For implemented recommendations**: State the exact files and components created or modified so the citation can reference them as implementation locations (e.g., "Rebuilt as `agents/foo/references/bar.md`" or "Added to `scripts/baz.py`"). Be specific — "created a reference file" is not enough; "created `agents/ui-design-engineer/references/ai-slop-detection.md` with 8 detection patterns" is.
- **For deferred recommendations**: State the deferral reason precisely so the citation can explain why the pattern was noted but not adopted.

The orchestrator maps your output to the citation format:
- DONE → "Patterns adopted" with your file paths as implementation locations
- DEFERRED → "Patterns noted but not adopted" with your deferral reason
```

---

## Dispatch Rules

### Parallel vs Sequential

- **Parallel**: Recommendations that affect different domains (e.g., one adds a new skill, another adds a reference file to a different agent) can run simultaneously
- **Sequential**: Recommendations that modify the same files or create components in the same domain must run in order to avoid merge conflicts

### Agent Selection

The implementation agent should match the domain of the recommendation:

| Recommendation Domain | Dispatch To |
|----------------------|-------------|
| Python scripts or tooling | python-general-engineer |
| Go code patterns | golang-general-engineer |
| TypeScript/frontend | typescript-frontend-engineer |
| Agent or skill structure | toolkit-governance-engineer |
| Documentation | technical-documentation-engineer |
| General/mixed | general-purpose |

### Timeout

Each implementation agent gets a 10-minute timeout. If the agent has not completed within 10 minutes, mark the recommendation as DEFERRED with reason "implementation timeout — requires manual follow-up."

---

## Deferral Criteria

A HIGH recommendation may be deferred (not implemented) when:

1. **Requires architectural decision** — the right approach is unclear and needs ADR consultation first
2. **Depends on external tooling** — needs an API key, service, or dependency we do not currently have
3. **Scope exceeds single-agent capacity** — the implementation spans 5+ files across multiple domains and needs coordinated multi-agent work via feature-lifecycle
4. **Conflicts with existing component** — extending the existing component would require a redesign that should go through the normal feature lifecycle

Every deferral requires an explicit reason in the implementation log. "Too complex" is not a reason. "Requires ADR consultation because the approach affects 3 existing agents and needs cross-component coordination" is.
