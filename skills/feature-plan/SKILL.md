---
name: feature-plan
description: |
  Break a design document into wave-ordered implementation tasks with domain
  agent assignments. Use after /feature-design produces a design doc. Use for
  "plan feature", "break down design", "create tasks", or "/feature-plan".
  Do NOT use without a design doc or for simple single-task work.
version: 2.0.0
user-invocable: true
command: /feature-plan
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - feature plan
    - plan feature
    - break down design
    - create tasks
    - feature-plan
  pairs_with:
    - feature-design
    - feature-implement
    - workflow-orchestrator
  complexity: Medium
  category: process
---

# Feature Plan Skill

## Purpose

Transform a design document into a wave-ordered implementation plan with tasks assigned to domain agents. Phase 2 of the feature lifecycle (design → **plan** → implement → validate → release).

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md
- **Design Doc Required**: CANNOT plan without a design document in `.feature/state/design/`
- **State Management via Script**: All state operations through `python3 scripts/feature-state.py`
- **Wave Ordering**: Tasks grouped by dependency wave; Wave N must complete before Wave N+1
- **Domain Agent Assignment**: Every implementation task MUST specify which domain agent handles it
- **Parallel Safety Analysis**: Flag which tasks in the same wave can run in parallel

### Default Behaviors (ON unless disabled)
- **Context Loading**: Read L0, L1, and design artifact at prime
- **Task Duration Targeting**: Each task scoped to 2-5 minutes of agent work
- **File Conflict Detection**: Detect tasks that modify the same files and sequence them

### Optional Behaviors (OFF unless enabled)
- **Auto-approve plan**: Skip human approval gate

## What This Skill CAN Do
- Read design documents and decompose into tasks
- Assign domain agents from our system to each task
- Detect file conflicts and resequence waves
- Produce structured plan artifacts

## What This Skill CANNOT Do
- Create plans without a design document
- Implement code (that's feature-implement)
- Skip plan approval gate without configuration
- Override domain agent routing

## Instructions

### Phase 0: PRIME

1. Check feature state:
   ```bash
   python3 scripts/feature-state.py status FEATURE
   ```
   Verify current phase is `plan` and `design` is in completed phases.

2. Load design artifact:
   ```bash
   ls .feature/state/design/*-FEATURE.md
   ```
   Read the design document.

3. Load L1 plan context:
   ```bash
   python3 scripts/feature-state.py context-read FEATURE L1 --phase plan
   ```

**Gate**: Design doc loaded. Feature in plan phase. Proceed.

### Phase 1: EXECUTE (Task Decomposition)

**Step 1: Identify Components**

From the design document, extract:
- Components to build/modify
- Dependencies between components
- Domain agents assigned in design

**Step 2: Create Wave-Ordered Tasks**

Group tasks by dependency wave:

```markdown
# Implementation Plan: [Feature Name]

## Wave 1 (no dependencies)
### T1: [Task title]
- **Agent**: golang-general-engineer
- **Duration**: 3 min
- **Files**: /absolute/path/to/file.go
- **Operations**: [specific changes]
- **Verification**: `go build ./...` exits 0
- **Parallel-safe**: true (no file conflicts with T2)

### T2: [Task title]
- **Agent**: typescript-frontend-engineer
- **Duration**: 4 min
- **Files**: /absolute/path/to/component.tsx
- **Operations**: [specific changes]
- **Verification**: `npm run typecheck` exits 0
- **Parallel-safe**: true

## Wave 2 (depends on Wave 1)
### T3: [Task title]
- **Agent**: golang-general-engineer
- **Dependencies**: T1
- **Duration**: 5 min
- **Files**: /absolute/path/to/handler.go
- **Operations**: [specific changes]
- **Verification**: `go test ./...` exits 0
- **Parallel-safe**: false (shares files with T4)
```

**Step 3: File Conflict Analysis**

For each wave, check if any two tasks modify the same files:
- If yes: mark `Parallel-safe: false` and add ordering constraint
- If no: mark `Parallel-safe: true`

**Step 4: Agent Routing Verification**

For each task, verify the assigned agent exists in our system:
- Check against known agent triggers
- If uncertain, default to the closest domain agent
- Log routing decisions

**Gate**: Tasks decomposed with waves, agents, and parallel safety flags.

### Phase 2: VALIDATE

Check gate: `python3 scripts/feature-state.py gate FEATURE plan.plan-approval`

Validation checklist:
- [ ] Every task has an assigned domain agent
- [ ] Every task has absolute file paths
- [ ] Every task has a verification command
- [ ] Every task is scoped to 2-5 minutes
- [ ] Wave ordering respects dependencies
- [ ] File conflicts are sequenced correctly
- [ ] Design components are fully covered by tasks

If gate is `human`: present plan to user for approval.
If gate is `auto`: verify checklist passes.

**Gate**: Plan approved. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

1. Save plan artifact:
   ```bash
   echo "PLAN_CONTENT" | python3 scripts/feature-state.py checkpoint FEATURE plan
   ```

2. **Record learnings** — if this phase produced non-obvious insights, record them:
   ```bash
   python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category design
   ```

3. Advance:
   ```bash
   python3 scripts/feature-state.py advance FEATURE
   ```

4. Suggest next step:
   ```
   Plan complete. Run /feature-implement to begin execution.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No design doc found | Design phase not completed | Run /feature-design first |
| Feature not in plan phase | Phase mismatch | Check status, advance if needed |
| Agent not found | Invalid agent assignment | Check agents/INDEX.json, use closest match |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Plan without design | No requirements to decompose | Complete /feature-design first |
| Vague task descriptions | Can't be executed by subagent | Specify exact files, operations, verification |
| All tasks in one wave | Loses parallelization opportunity | Group by actual dependencies |
| Skip file conflict analysis | Parallel execution causes corruption | Analyze every wave for conflicts |

## References

- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Retro Loop](../shared-patterns/retro-loop.md)
- [State Conventions](../_feature-shared/state-conventions.md)
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md)
