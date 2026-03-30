---
name: feature-lifecycle
description: |
  Feature lifecycle: design, plan, implement, validate, release. Phase-gated workflow.
version: 3.0.0
user-invocable: false
command: /feature-lifecycle
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
  - Task
routing:
  force_route: true
  triggers:
    - feature design
    - design feature
    - think through
    - explore approaches
    - design first
    - feature plan
    - plan feature
    - break down design
    - create tasks
    - feature implement
    - implement feature
    - execute plan
    - start building
    - feature validate
    - validate feature
    - run quality gates
    - check feature
    - feature release
    - release feature
    - merge feature
    - ship it
    - build feature end to end
    - full feature lifecycle
    - feature from scratch
    - design to release
    - complete feature pipeline
    - feature pipeline
  pairs_with:
    - workflow-orchestrator
    - subagent-driven-development
    - pr-pipeline
    - git-commit-flow
    - verification-before-completion
    - universal-quality-gate
    - adr-consultation
    - spec-writer
  complexity: Complex
  category: process
---

# Feature Lifecycle Skill

Phase-gated feature workflow: DESIGN > PLAN > IMPLEMENT > VALIDATE > RELEASE. Each phase must pass its gate before the next begins.

## Phase Routing

Determine which phase to execute based on feature state:

1. **If `.feature/` exists**, check current phase:
   ```bash
   python3 ~/.claude/scripts/feature-state.py status
   ```
   Route to the phase indicated by the state machine.

2. **If no feature state exists**, determine entry point from user intent:
   - "design", "think through", "explore approaches" -> DESIGN
   - "plan", "break down", "create tasks" -> PLAN (requires completed design)
   - "implement", "execute plan", "start building" -> IMPLEMENT (requires completed plan)
   - "validate", "quality gates", "check feature" -> VALIDATE (requires completed implementation)
   - "release", "merge", "ship it" -> RELEASE (requires passed validation)
   - "end to end", "full lifecycle", "from scratch" -> DESIGN (start from beginning)

3. **Load the phase reference** for the current phase:
   - DESIGN: Read `references/design.md`
   - PLAN: Read `references/plan.md`
   - IMPLEMENT: Read `references/implement.md`
   - VALIDATE: Read `references/validate.md`
   - RELEASE: Read `references/release.md`
   - END-TO-END: Read `references/pipeline.md`

4. **Follow the loaded reference** exactly. Each reference contains the full phase instructions, gates, and checkpoints.

## State Conventions

Read `references/shared.md` for directory structure, state management commands, context loading rules, and naming conventions. All state operations go through `python3 ~/.claude/scripts/feature-state.py` -- never manipulate state files directly.

## Phase Ordering

```
DESIGN -> PLAN -> IMPLEMENT -> VALIDATE -> RELEASE
  |         |         |           |          |
  v         v         v           v          v
design.md plan.md  impl.md   report.md  PR merged
```

Each phase produces an artifact consumed by the next. Skipping phases is not supported because downstream phases depend on artifacts from earlier phases.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Phase mismatch | User requests phase N but state is at phase M | Report current state, suggest correct next phase |
| Missing artifact | Previous phase did not produce expected output | Route back to previous phase |
| Gate failure | Phase requirements not met | Report what failed, suggest fixes |

## References

- `references/design.md` -- Design phase: explore requirements, discuss trade-offs
- `references/plan.md` -- Plan phase: break design into wave-ordered tasks
- `references/implement.md` -- Implement phase: dispatch tasks to domain agents
- `references/validate.md` -- Validate phase: run quality gates
- `references/release.md` -- Release phase: merge, tag, cleanup
- `references/pipeline.md` -- End-to-end orchestration across all phases
- `references/shared.md` -- State conventions shared across all phases
