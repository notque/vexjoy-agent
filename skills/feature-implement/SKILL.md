---
name: feature-implement
description: |
  Execute wave-ordered implementation plan by dispatching tasks to domain agents.
  Use after /feature-plan produces a plan. Use for "implement feature", "execute
  plan", "start building", or "/feature-implement". Do NOT use without a plan
  or for ad-hoc coding tasks.
version: 2.0.0
user-invocable: true
command: /feature-implement
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
routing:
  triggers:
    - feature implement
    - implement feature
    - execute plan
    - start building
    - feature-implement
  pairs_with:
    - feature-plan
    - feature-validate
    - subagent-driven-development
  complexity: Complex
  category: process
---

# Feature Implement Skill

## Purpose

Execute the implementation plan by dispatching tasks to domain agents wave by wave. Phase 3 of the feature lifecycle (design → plan → **implement** → validate → release).

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md
- **Plan Required**: CANNOT implement without a plan in `.feature/state/plan/`
- **State Management via Script**: All state operations through `python3 scripts/feature-state.py`
- **Domain Agent Dispatch**: Every task dispatched to its assigned domain agent via Task tool
- **Wave Order Enforcement**: Complete all tasks in Wave N before starting Wave N+1
- **Wave Checkpoint**: Run relevant tests after each wave completes
- **Deviation Handling**: Tier 1-2 auto-fix, Tier 3 stops for user

### Default Behaviors (ON unless disabled)
- **Context Loading**: Read L0, L1, plan artifact, and design artifact at prime
- **Fresh Agent Per Task**: Each task gets a clean agent dispatch (no context pollution)
- **Spec Compliance Check**: After each task, verify output matches plan specification
- **Progress Reporting**: Report after each task and wave completion

### Optional Behaviors (OFF unless enabled)
- **Parallel within wave**: Dispatch parallel-safe tasks simultaneously
- **Auto-fix Tier 2 deviations**: Handle missing dependencies automatically

## What This Skill CAN Do
- Dispatch tasks to domain agents (golang-general-engineer, typescript-frontend-engineer, etc.)
- Execute wave-ordered plans with dependency tracking
- Handle deviations with tiered escalation
- Run wave checkpoints (tests) between waves

## What This Skill CANNOT Do
- Implement without a plan
- Override domain agent selection from plan
- Skip wave ordering
- Handle Tier 3 (architectural) deviations without user input

## Instructions

### Phase 0: PRIME

1. Verify feature state:
   ```bash
   python3 scripts/feature-state.py status FEATURE
   ```
   Verify current phase is `implement` and `plan` is completed.

2. Load plan artifact from `.feature/state/plan/`.

3. Load design artifact from `.feature/state/design/` for reference.

4. Load L1 implement context:
   ```bash
   python3 scripts/feature-state.py context-read FEATURE L1 --phase implement
   ```

5. Capture BASE_SHA:
   ```bash
   git rev-parse HEAD
   ```

**Gate**: Plan loaded. Feature in implement phase. BASE_SHA captured. Proceed.

### Phase 1: EXECUTE (Wave Dispatch)

**For each wave in the plan:**

**Step 1: Dispatch Tasks**

For each task in the wave:

1. Check if task is parallel-safe and parallel mode is enabled
2. Dispatch to assigned domain agent via Task tool:

```
Agent(
  subagent_type="[agent-from-plan]",
  prompt="Implement the following task:\n\n[TASK DETAILS FROM PLAN]\n\nFiles: [FILES]\nOperations: [OPERATIONS]\nVerification: [VERIFICATION COMMAND]\n\nContext from design: [RELEVANT DESIGN CONTEXT]",
  description="Implement [task title]"
)
```

3. Verify task output matches plan specification

**Step 2: Handle Deviations**

| Tier | Examples | Action |
|------|----------|--------|
| Tier 1: Auto-Fix | Bug, type error, missing import | Auto-apply, record in retro |
| Tier 2: Blocking | Missing dependency, config issue | Auto-fix if possible, record |
| Tier 3: Architectural | Schema change, API change, scope expansion | **STOP**, present to user |

Check gate for Tier 3: `python3 scripts/feature-state.py gate FEATURE implement.architectural-deviation`

**Step 3: Wave Checkpoint**

After all tasks in a wave complete:
1. Run the project's test suite (or relevant subset)
2. If tests fail: identify which task caused the failure, route back to that agent
3. If tests pass: proceed to next wave

**Step 4: Progress Report**

After each wave:
```
Wave N complete: X/Y tasks passed
  T1: [agent] ✓
  T2: [agent] ✓
  T3: [agent] ✗ (deviation: [description])
```

**Gate**: All waves complete. All tasks verified. Proceed to Validate.

### Phase 2: VALIDATE (Implementation Review)

Quick validation before formal validation phase:
- [ ] All planned files were created/modified
- [ ] All verification commands pass
- [ ] No unplanned files were modified (check `git diff --name-only BASE_SHA..HEAD`)
- [ ] No Tier 3 deviations unresolved

**Gate**: Implementation complete. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

1. Save implementation artifact (summary of what was built):
   ```bash
   echo "IMPL_SUMMARY" | python3 scripts/feature-state.py checkpoint FEATURE implement
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
   Implementation complete. Run /feature-validate for quality gates.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No plan found | Plan phase not completed | Run /feature-plan first |
| Agent dispatch fails | Agent not available or task malformed | Retry with more context, escalate if 3 failures |
| Wave test failure | Task broke existing tests | Route back to responsible agent for fix |
| Tier 3 deviation | Architectural decision needed | Stop, present options to user |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Implement without dispatching to agents | Bypasses domain expertise | Use Task tool to dispatch |
| Skip wave checkpoints | Failures compound across waves | Test after every wave |
| Ignore deviations | Small deviations become big problems | Classify and handle per tier |
| Dispatch all tasks in parallel | File conflicts cause corruption | Respect wave ordering and parallel-safe flags |

## References

- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Retro Loop](../shared-patterns/retro-loop.md)
- [State Conventions](../_feature-shared/state-conventions.md)
- [Subagent-Driven Development](../subagent-driven-development/SKILL.md)
