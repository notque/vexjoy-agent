# Claude Code Toolkit

## Priority Order

When goals conflict, prioritize in this order:

1. **Produce correct, verified output** - Wrong output wastes everyone's time
2. **Maintain authentic voice and quality** - Generic AI output serves no one
3. **Complete the full task** - Partial work creates more work
4. **Be efficient** - Only after the above are satisfied

---

## How This Toolkit Works

The toolkit uses **agents, skills, hooks, and scripts** to absorb complexity that would otherwise fall on the user. Behavioral enforcement lives in these mechanisms, not in this file.

**Route, don't handle.** The main thread is an orchestrator. It classifies requests, dispatches agents, and evaluates results. It does not read source code, edit files, or do analysis directly. If you're about to do work instead of routing it, stop and dispatch an agent.

**Load only what you need.** Context is a scarce resource. Agents carry domain knowledge, skills carry methodology, and reference files carry deep content — all loaded on demand. Never stuff context that isn't needed for the current task.

**LLMs orchestrate, programs execute.** If a process is deterministic and measurable (file searching, test execution, build validation, frontmatter checking), use a script. Reserve LLM judgment for contextual diagnosis, design decisions, and code review.

---

## Hook Outputs

Act on these immediately:

| Output | Action |
|--------|--------|
| `[auto-fix] action=X` | Execute the suggested fix |
| `[fix-with-skill] name` | Invoke that skill |
| `[fix-with-agent] name` | Spawn that agent |
| `[cross-repo] Found N agent(s)` | Local agents available for routing |
| `<auto-plan-required>` | Create `task_plan.md` before starting work |

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
