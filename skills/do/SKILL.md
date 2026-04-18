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

/do routes requests to agents with skills. It dispatches a single Haiku call to classify and route, then orchestrates the dispatch. It never reads skills, writes code, or does analysis itself.

---

## Instructions

### Phase 1: GATE

If the request is reading a file the user named by exact path, handle it directly. Everything else proceeds to Phase 2.

Do NOT skip Phase 2 by dispatching built-in agent types (Explore, general-purpose) directly.

---

### Phase 2: ROUTE (single Haiku call)

One Haiku call handles all classification and routing. The main thread does not classify complexity or pick agents. Haiku does both.

**Step 1:** Generate the manifest:

```bash
python3 scripts/routing-manifest.py
```

**Step 2:** Dispatch Agent with `model: "haiku"`:

```
You are a routing agent. Given a user request and a manifest of available agents and skills, classify the request and select the best agent+skill combination.

USER REQUEST: {user_request}

ROUTING MANIFEST:
{manifest_output}

Return JSON:
{
  "complexity": "Simple | Medium | Complex",
  "agent": "name or null",
  "skill": "name or null",
  "is_creation": false,
  "is_code_modification": false,
  "reasoning": "one sentence",
  "confidence": "high/medium/low"
}

Complexity rules:
- Simple: single agent, single skill, no phase composition needed.
- Medium: single agent with skill, benefits from structured phases (plan/test/review).
- Complex: requires 2+ agents or multi-part coordination.
- When uncertain, classify UP.

Routing rules:
- Pick the most specific match. Agent handles domain, skill handles methodology.
- FORCE entries must be selected when intent clearly matches (semantic, not keyword).
- Git operations (push, commit, PR, merge) always get pr-workflow skill.
- Creation requests ("create", "scaffold", "build", "new [component]"): set is_creation to true.
- Code modifications (features, bug fixes, refactoring): set is_code_modification to true.
- If nothing matches, return nulls.
```

**Step 3:** If confidence is "low", read `references/routing-tables.md` to verify. If Haiku returns nulls, route to the closest agent with verification-before-completion and record the gap.

---

### Phase 3: DISPATCH

The main thread orchestrates dispatch using Haiku's routing decision. It does not re-classify or make judgment calls. It enforces policy from the table below, then dispatches.

#### Forced Injections

These are mechanical. When a flag is set, the injection happens. No discretion.

| Flag | Injection | What it does |
|------|-----------|-------------|
| `is_code_modification` | `--inject anti-rationalization-core` | Prevents rationalization of skipped steps |
| `is_code_modification` | `--inject verification-checklist` | Pre-completion verification gate |
| `is_code_modification` | `--skill pr-workflow` | Branch, commit, push, PR after implementation |
| `is_creation` | ADR at `adr/{name}.md` via `adr-query.py register` | Write ADR before dispatching |
| `complexity >= Medium` | Load `references/phase-composition.md` | Compose structured phase sequence |

The agent receives these injections in its dispatch package. It does not decide whether to follow them.

#### Dispatch Steps

**Step 1:** Resolve routing names to file paths, applying all forced injections:

```bash
python3 ~/.claude/scripts/resolve-dispatch.py \
    --agent {agent_name} \
    --skill {skill_name} \
    --skill pr-workflow \
    --inject anti-rationalization-core \
    --inject verification-checklist \
    --request "{user_request}"
```

Only include `--skill pr-workflow` and `--inject` flags when their corresponding forced injection flag is set.

**Step 2:** Display the dispatch banner and dispatch the agent:

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Dispatching:
   -> Agent: [name]
      carries skill: [name]
      complexity: [Simple/Medium/Complex]
      phases: [composed sequence, or "none" for Simple]
      injections: [list of forced injections applied]
===================================================================
```

Prepend the Dispatch Package output to the agent prompt. For Medium+ tasks, also prepend:

```
## Task Specification
**Intent:** <what success looks like>
**Constraints:** <branch rules, operator profile>
**Acceptance criteria:** <what proves it works>
```

Append: "Deliver the finished product, not a plan. Search before building. Test before shipping. Ship the complete thing."

For worktree-isolated agents, add: "Verify CWD contains .claude/worktrees/. Create feature branch before edits. Stage specific files only."

Multi-part requests: sequential dependencies in order, independent items in parallel (max 10).

---

### Phase 4: LEARN

Record routing outcome:

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{agent}:{skill}" \
    "routing-decision: agent={agent} skill={skill} complexity={complexity} tool_errors: {0|1} user_rerouted: {0|1}" \
    --category effectiveness
```

---

## References

- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Skill routing verification (load when Haiku confidence is low)
- `${CLAUDE_SKILL_DIR}/references/phase-composition.md`: Phase composition (load for Medium+ tasks)
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Escalation protocol
