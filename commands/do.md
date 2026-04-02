---
description: "Smart router: classify requests and route to the correct agent + skill"
argument-hint: "[request]"
allowed-tools: ["Read", "Bash", "Grep", "Glob", "Skill", "Task"]
---

# /do - Smart Router

Route user requests to the correct agent + skill combination.

## Instructions

Read and follow the full skill file at `skills/do/SKILL.md` in this repository.

```
Base directory: $CLAUDE_PROJECT_DIR or the current working directory
Skill file: skills/do/SKILL.md
```

**Phase 1: CLASSIFY** — Assess complexity, check parallel patterns
**Phase 2: ROUTE** — Select agent + skill, display routing banner
**Phase 3: ENHANCE** — Stack retro knowledge, anti-rationalization, parallel reviewers
**Phase 4: EXECUTE** — Create plan, invoke agent with skill
**Phase 5: LEARN** — Extract reusable patterns, record via retro-record-adhoc

The routing banner MUST be the first visible output:
```
===================================================================
 ROUTING: [brief summary]
===================================================================

 Selected:
   -> Agent: [name]
   -> Skill: [name]

 Invoking...
===================================================================
```

For complete routing tables, force-route triggers, and domain agent mappings, read `skills/do/SKILL.md` and `skills/do/references/routing-tables.md`.

ARGUMENTS: $ARGUMENTS
