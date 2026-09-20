---
name: toolkit
description: "Maintain this repository's skills, agents, routing indexes, evaluations, compositions, and toolkit evolution workflows."
user-invocable: true
agent: toolkit-governance-engineer
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, Task, Skill]
routing:
  force_route: true
  not_for: "application code (use workflow), code review (use review)"
  triggers: [create skill, create agent, scaffold skill, scaffold agent, new skill, new agent, skill template, agent template, eval skill, evaluate agent, benchmark skill, benchmark agents, compare agents, A/B test agents, optimize description, evolve toolkit, toolkit evolution, self-improve, update routing tables, routing maintenance, generate claude.md, create claude.md, compose skills, bake-off, skill quality]
  category: meta-tooling
  pairs_with: [review, workflow]
---

# Toolkit

Select one mode. Read only its listed reference and use its bundled scripts;
those files hold repository-specific schemas and command contracts.

| Request | Load | Executables |
|---|---|---|
| Create or improve a skill | `references/skill-creator.md` | `scripts/skill-creator/` |
| Create an agent | `references/agent-creator.md` | repository index/validation scripts |
| Evaluate a skill | `references/skill-eval.md` | `scripts/skill-creator/run_eval.py`, `eval_compare.py` |
| Compare/optimize agents | `references/agent-comparison.md` | `scripts/agent-comparison/` |
| Evaluate an agent | `references/agent-evaluation.md` | scorer named by the reference |
| Compose skills | `references/skill-composer.md` | `scripts/skill-composer/` |
| Repair routing indexes | `references/routing-table-updater.md` | `scripts/routing-table-updater/` |
| Evolve the toolkit | `references/toolkit-evolution.md` | scripts named by that reference |
| Generate repository guidance | `references/generate-claudemd.md` | commands named by that reference |

## Repository invariants

- Frontmatter is routing source-of-truth; generated indexes and routing maps
  must be regenerated and checked after metadata changes.
- Preserve manual routing entries and surface conflicts; never resolve a
  same-trigger conflict by silent overwrite.
- `name` must match its directory/file identity. Validate every `pairs_with`
  target and every referenced path.
- New components need realistic positive, negative, and near-miss activation
  cases. Structural checks do not substitute for behavior evaluation.
- Comparisons use identical frozen tasks, isolated outputs, deterministic
  checks first, and blind grading. Promote only improvements that hold on a
  separate test split.
- Existing scripts define artifact schemas. Inspect their CLI help and source
  before constructing inputs; do not copy stale schema examples from prose.
- Creation or promotion that changes repository state remains subject to the
  user's authorization and normal review workflow.

Keep reports evidence-linked: commands, artifact paths, deterministic failures,
scores, and unresolved risks. Do not expand a narrow maintenance request into
the full toolkit lifecycle.
