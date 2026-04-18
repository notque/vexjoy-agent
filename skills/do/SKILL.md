---
name: do
description: "Route requests to agents with skills."
user-invocable: true
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  triggers:
    - "route task"
    - "classify request"
    - "which agent"
    - "delegate to skill"
    - "smart router"
  category: meta-tooling
---

# /do - Dispatch Router

/do classifies a request, asks a Haiku agent to pick the right agent + skill from the manifest, resolves file paths, and dispatches. It never reads skills, writes code, or does analysis itself.

---

## Instructions

### Phase 1: CLASSIFY

Determine complexity. Read the repository CLAUDE.md first.

| Complexity | What happens |
|------------|-------------|
| Trivial | Only: reading a file the user named by exact path. Handle directly. |
| Simple | Dispatch agent with skill. No phase composition. |
| Medium | Dispatch agent with skill + composed phases. |
| Complex | Dispatch 2+ agents with skills + composed phases. |

Everything except reading a named file is Simple+. When uncertain, classify UP. Simple+ MUST proceed to Phase 2. Do NOT skip Phase 2 by dispatching built-in agent types (Explore, general-purpose) directly.

**Creation requests** ("create", "scaffold", "build", "new [component]"): set `is_creation = true`. Phase 4 Step 0 writes ADR first.

**Gate**: Complexity determined. Proceed to Phase 2 for all Simple+ tasks.

---

### Phase 2: ROUTE (Haiku agent decides)

The main thread does NOT choose the agent or skill. A Haiku subagent reads the manifest and decides. This keeps routing knowledge out of the main thread's context.

**Step 1:** Generate the manifest and dispatch Haiku:

```bash
python3 scripts/routing-manifest.py
```

Dispatch Agent with `model: "haiku"`:

```
You are a routing agent. Given a user request and a manifest of available agents and skills, select the BEST agent+skill combination.

USER REQUEST: {user_request}

ROUTING MANIFEST:
{manifest_output}

Return JSON: {"agent": "name or null", "skill": "name or null", "reasoning": "one sentence", "confidence": "high/medium/low"}

Rules:
- Pick the most specific match. Agent handles domain, skill handles methodology.
- FORCE entries must be selected when intent clearly matches (semantic, not keyword).
- Git operations (push, commit, PR, merge) always get pr-workflow skill.
- If nothing matches, return nulls.
```

**Step 2:** Use the Haiku agent's response directly. If confidence is "low", read `references/routing-tables.md` to verify.

**Step 3:** Display the dispatch banner:

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Dispatching:
   -> Agent: [name from Haiku]
      carries skill: [name from Haiku]
      phases: [composed in Phase 3, or "none" for Simple]
 The agent will load its references and execute the skill.
===================================================================
```

---

### Phase 3: ENHANCE

For Medium+ tasks, load `references/phase-composition.md` and compose the phase sequence. Attach to dispatch.

For code modifications, attach anti-rationalization-core + verification-checklist via `--inject` flags.

Simple tasks skip this phase.

---

### Phase 4: EXECUTE

**Step 0:** Creation requests only: write ADR at `adr/{name}.md`, register via `adr-query.py register`.

**Step 1:** Resolve routing names to file paths and dispatch:

```bash
python3 ~/.claude/scripts/resolve-dispatch.py \
    --agent {agent_name} \
    --skill {skill_name} \
    --skill {enhancement_skill} \
    --inject {pattern_name} \
    --request "{user_request}"
```

Prepend the Dispatch Package output to the agent prompt. Pass the **Model** value from the Dispatch Package as the `model` parameter on the Agent tool call. If no model is specified, omit the parameter (session default applies).

For Medium+ tasks, also prepend:

```
## Task Specification
**Intent:** <what success looks like>
**Constraints:** <branch rules, operator profile>
**Acceptance criteria:** <what proves it works>
```

Append: "Deliver the finished product, not a plan. Search before building. Test before shipping. Ship the complete thing."

**Step 2:** For worktree-isolated agents, add: "Verify CWD contains .claude/worktrees/. Create feature branch before edits. Stage specific files only."

**Step 3:** Multi-part requests: sequential dependencies in order, independent items in parallel (max 10).

---

### Phase 5: LEARN

Record routing outcome:

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{agent}:{skill}" \
    "routing-decision: agent={agent} skill={skill} tool_errors: {0|1} user_rerouted: {0|1}" \
    --category effectiveness
```

---

## Error Handling

If the Haiku agent returns nulls or low confidence, read `references/routing-tables.md` to verify. If no agent/skill matches, route to the closest agent with verification-before-completion and record the gap.

---

## References

- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Skill routing verification (load when Haiku confidence is low)
- `${CLAUDE_SKILL_DIR}/references/phase-composition.md`: Phase composition (load for Medium+ tasks)
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Escalation protocol
