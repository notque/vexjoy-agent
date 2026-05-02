---
name: workflow-help
description: "Interactive guide to workflow system: agents, skills, routing, execution patterns."
effort: low
user-invocable: true
argument-hint: "[<topic>]"
allowed-tools:
  - Read
  - Grep
  - Glob
routing:
  triggers:
    - "how does routing work"
    - "what skills exist"
    - "system help"
    - "explain workflow"
    - "I am stuck"
    - "toolkit help"
  category: meta-tooling
  pairs_with:
    - workflow
    - do
---

# Workflow Help Skill

## Overview

Educational guide for repository workflows. Answers questions about the agent/skill/routing architecture, available components, and when to use each workflow phase. Reads actual files rather than relying on memory.

---

## Instructions

### Phase 1: UNDERSTAND THE QUESTION

**Goal**: Determine what the user wants to know.

Parse topic and $ARGUMENTS. Common categories:
- `brainstorm` / `plan` / `execute` — Workflow phases
- `skills` / `agents` / `hooks` — Component types
- `routing` / `do` — How routing works
- `subagent` — Subagent-driven execution
- No argument — System overview

Answer only what was asked. Do not dump entire architecture for a single-skill question. Offer related concepts after.

**Gate**: Topic identified.

### Phase 2: GATHER ACCURATE INFORMATION

**Goal**: Read actual files before explaining anything. Never describe components from memory.

**Step 1: Read relevant files**

- Specific skill: `Read skills/{skill-name}/SKILL.md`
- Specific agent: `Read agents/{agent-name}.md`
- Routing overview: Check /do router configuration
- System overview: `Glob for skills/*/SKILL.md and agents/*.md` for current counts

**Step 2: Extract key information**
- Name, description, version
- What it CAN and CANNOT do
- How to invoke it
- Related skills or agents

If a component does not exist, say so. If recently deleted/merged, search with Glob for similar names and suggest closest match.

**Gate**: Information gathered from actual files.

### Phase 3: EXPLAIN CLEARLY

**Goal**: Present information in the most useful format.

**For system overview**:

```
Router (/do) -> Agent (domain expert) -> Skill (methodology) -> Script (execution)
```

Key workflow:
1. BRAINSTORM — Clarify requirements, explore approaches
2. WRITE-PLAN — Break into atomic, verifiable tasks
3. EXECUTE — Direct or subagent-driven execution
4. VERIFY — Run tests, validate changes

**For specific components**:

```markdown
## [Component Name]
**Type**: Skill / Agent / Hook
**Invoke**: /command or skill: name
**Purpose**: One-sentence description
**Key Phases/Capabilities**: Bulleted list
**Related**: Links to related components
```

**For "when to use what"**:

| You Want To... | Use This |
|----------------|----------|
| Start a new feature | `/do implement [feature]` |
| Debug a bug | `/do debug [issue]` |
| Review code | `/do review [code]` |
| Execute an existing plan | `skill: subagent-driven-development` |
| Create a PR | `/pr-workflow` |

Reference actual skill names, commands, and file paths. Include invocation syntax. Use tables for lists. Apply progressive disclosure: overview first, deepen on request. Cross-reference related components.

**After explaining**, ask if the user wants to:
- Learn about a related component
- Execute a workflow (route to appropriate skill)
- See more detail

If user wants execution, not explanation (e.g., "how do I debug X" meaning "debug X for me"), route to the correct skill instead of explaining.

**Gate**: Question answered from actual files.

---

## Error Handling

### Error: "Skill or Agent Not Found"
Cause: Component does not exist or was renamed.
Solution: Glob for similar names, check for recent deletion/merge, suggest closest match.

### Error: "User Wants Execution, Not Explanation"
Cause: "How do I debug X" means "debug X for me."
Solution: Route to appropriate skill (e.g., systematic-debugging). Do not explain; invoke.

### Error: "Stale Information"
Cause: Files may have changed since last read.
Solution: Always read fresh. Check modification dates if inconsistent. Report discrepancies.

---

## References

### Core Constraints

1. **CLAUDE.md Compliance**: Follow repository CLAUDE.md before answering
2. **Accuracy Over Speed**: Read actual files before explaining; never describe from memory
3. **Show Real Examples**: Reference actual names, commands, file paths
4. **No Fabrication**: If a component doesn't exist, say so
5. **Route When Appropriate**: If user wants execution, route to the skill

Optional modes (off by default):
- Full Architecture Dump: Entire Router -> Agent -> Skill -> Script pipeline
- Comparison Mode: Side-by-side skill/agent comparison
- Troubleshooting Guide: Diagnose why a skill or route isn't working
