---
name: feature-pipeline
description: "End-to-end feature lifecycle: design through release."
version: 1.0.0
user-invocable: false
context: fork
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
  triggers:
    - "build feature end to end"
    - "full feature lifecycle"
    - "feature from scratch"
    - "design to release"
    - "complete feature pipeline"
    - "feature pipeline"
  category: process
---

# Feature Pipeline

End-to-end feature lifecycle pipeline that coordinates the five existing feature skills (feature-design, feature-plan, feature-implement, feature-validate, feature-release) into a single phase-gated workflow with a final RECORD phase for learning.

## Overview

This pipeline orchestrates the full feature lifecycle by invoking feature-* skills in sequence: DESIGN, PLAN, IMPLEMENT, VALIDATE, RELEASE, RECORD. Each phase must pass its gate before the next begins (enforced because skipping design or plan steps causes rework, and testing without validation creates merged bugs).

**Before starting**: Read and follow your repository's CLAUDE.md because it contains essential context and conventions.

**Scope**: Use for end-to-end feature work only. For single-phase work (e.g., "just validate this feature"), use the individual feature-* skills instead.

**Optional flags** (OFF by default):
- `--skip-design` — Skip Phase 1 if design document already exists
- `--skip-release` — Stop after validation (useful for draft features)
- `--parallel-implement` — Dispatch implementation tasks in parallel via agents

---

## Instructions

### Phase 1: DESIGN

**Goal**: Invoke the `feature-design` skill to explore requirements, discuss trade-offs, and produce a design document.

**Skill**: `/feature-design`

**Actions:**
1. Invoke feature-design with the feature description
2. Explore requirements and constraints collaboratively
3. Discuss trade-offs between approaches
4. Produce a design document with chosen approach, rationale, and scope

**Artifact**: Design document (e.g., `feature-design-[name].md`)

**GATE**: Design document exists with requirements, chosen approach, trade-offs discussed, and scope defined. Proceed only when gate passes.

---

### Phase 2: PLAN

**Goal**: Invoke the `feature-plan` skill to break the design into wave-ordered implementation tasks with domain agent assignments.

**Skill**: `/feature-plan`

**Actions:**
1. Read the design document from Phase 1
2. Break design into wave-ordered implementation tasks
3. Assign domain agents to each task
4. Define dependencies between tasks
5. Produce an implementation plan

**Artifact**: Implementation plan (e.g., `feature-plan-[name].md`)

**GATE**: Implementation plan exists with ordered tasks, agent assignments, and dependencies. Design document referenced. Proceed only when gate passes.

---

### Phase 3: IMPLEMENT

**Goal**: Invoke the `feature-implement` skill to execute the wave-ordered plan by dispatching tasks to domain agents.

**Skill**: `/feature-implement`

**Actions:**
1. Read the implementation plan from Phase 2
2. Execute tasks in wave order
3. Dispatch tasks to assigned domain agents
4. Track progress and handle failures
5. Verify each task completes before starting dependent tasks

**Artifact**: Implemented feature code, tests.

**GATE**: All planned tasks completed. Implementation plan exists (from Phase 2). All dispatched tasks report success. Code compiles/runs without errors. Proceed only when gate passes.

---

### Phase 4: VALIDATE

**Goal**: Invoke the `feature-validate` skill to run quality gates on the implemented feature.

**Skill**: `/feature-validate`

**Actions:**
1. Run test suite (unit, integration, e2e as applicable)
2. Run linter and type checks
3. Run custom validation rules
4. Verify feature meets design requirements from Phase 1
5. Check for regressions in existing functionality

**Artifact**: Validation report.

**GATE**: All quality gates pass -- tests, lint, type checks, custom validation. Implementation complete (from Phase 3). No regressions. Feature meets design requirements. Proceed only when gate passes.

---

### Phase 5: RELEASE

**Goal**: Invoke the `feature-release` skill to merge the validated feature via PR, tag release, and clean up.

**Skill**: `/feature-release`

**Actions:**
1. Create pull request with feature summary
2. Link to design document and validation report
3. Merge to main branch (after review)
4. Tag release if applicable
5. Clean up feature branch and worktree

**Artifact**: Merged PR, release tag (if applicable).

**GATE**: Validation passes (from Phase 4). PR created and merged. Feature branch cleaned up. Proceed only when gate passes.

---

### Phase 6: RECORD

**Goal**: Log feature lifecycle pattern to learning database for future features.

**Step 1: Record feature pattern**

```markdown
## [Date] Feature: [Brief Description]
**Phases Completed**: [DESIGN, PLAN, IMPLEMENT, VALIDATE, RELEASE]
**Duration**: [time from design to release]
**Design Decisions**: [key trade-offs and choices]
**Plan Accuracy**: [how well the plan matched actual implementation]
**Validation Issues**: [what quality gates caught]
**Gotcha**: [what almost went wrong or required extra care]
```

**Step 2: Update learning.db**

Record the feature lifecycle pattern and outcome to the learning database.

**Step 3: Retrospective notes**

Document what went well, what could improve, and any process adjustments for next time.

**Output**: `[learning] Feature pattern recorded.`

**GATE**: Learning database entry exists with phase outcomes, key decisions, and gotchas. Retrospective notes captured.

---

## Error Handling

### Error: "Design Phase Stalls"
Cause: Requirements unclear or stakeholder alignment missing
Solution: Time-box design to 2 iterations because unbounded design exploration delays implementation without creating clarity. If no convergence, document open questions and proceed with best-available design, flagging assumptions. Re-validate during Phase 4 if assumptions prove incorrect.

### Error: "Implementation Diverges from Plan"
Cause: Discovered complexity not anticipated in design/plan
Solution: Return to Phase 2 (PLAN) to update the plan with new understanding because continuing with an outdated plan causes wasted implementation effort and integration rework. Do NOT continue implementing against an outdated plan.

### Error: "Validation Fails"
Cause: Implementation bugs or missing requirements
Solution: Return to Phase 3 (IMPLEMENT) to fix because proceeding to release with failing tests ships defects to end users. Do NOT proceed to RELEASE with failing validation. Re-run full validation after fixes to catch any regressions.

### Error: "Release Blocked"
Cause: Merge conflicts, CI failures, or review feedback
Solution: Address each blocker. Return to Phase 4 (VALIDATE) if code changes were needed because changes risk introducing new failures.

---

## References

This pipeline coordinates:
- `/feature-design` — Explore requirements, discuss trade-offs, produce design document
- `/feature-plan` — Break design into wave-ordered tasks with domain agent assignments
- `/feature-implement` — Execute plan by dispatching tasks to domain agents
- `/feature-validate` — Run quality gates (tests, lint, type checks, custom validation)
- `/feature-release` — Merge via PR, tag release, clean up branch
