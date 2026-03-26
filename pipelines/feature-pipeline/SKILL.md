---
name: feature-pipeline
description: |
  End-to-end feature lifecycle pipeline coordinating design through release:
  DESIGN, PLAN, IMPLEMENT, VALIDATE, RELEASE, RECORD. Wraps the existing
  feature-design, feature-plan, feature-implement, feature-validate, and
  feature-release skills into a single phase-gated pipeline. Use for "build
  feature end to end", "full feature lifecycle", "feature from scratch", or
  "design to release". Do NOT use for single-phase feature work (use the
  individual feature-* skills instead).
version: 1.0.0
user-invocable: false
context: fork
agent: general-purpose
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

## Operator Context

This pipeline orchestrates the full feature lifecycle. Each phase invokes the corresponding feature-* skill and enforces gates before transitions.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before starting
- **Sequential Phases**: Phases execute in order. No skipping.
- **Phase Gates Enforced**: Each phase must pass its gate before the next begins
- **Artifact Persistence**: Each phase produces artifacts that subsequent phases depend on
- **Branch Isolation**: All work happens on a feature branch, never on main

### Default Behaviors (ON unless disabled)
- **Design-First**: Always start with design, even for "obvious" features
- **Plan Before Code**: Never write implementation code without an approved plan
- **Test Before Ship**: Validation must pass before release
- **Record Learnings**: Always complete the RECORD phase

### Optional Behaviors (OFF unless enabled)
- **--skip-design**: Skip Phase 1 if design document already exists
- **--skip-release**: Stop after validation (useful for draft features)
- **--parallel-implement**: Dispatch implementation tasks in parallel via agents

## What This Pipeline CAN Do
- Coordinate an entire feature from initial design through release
- Ensure proper sequencing of design, planning, implementation, validation, and release
- Prevent common lifecycle mistakes (coding before design, shipping before tests)
- Record patterns for future feature development

## What This Pipeline CANNOT Do
- Replace individual feature-* skills for single-phase work
- Debug bugs (use systematic-debugging instead)
- Refactor existing code (use systematic-refactoring instead)
- Skip phases without explicit opt-in flags

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
Solution: Time-box design to 2 iterations. If no convergence, document open questions and proceed with best-available design, flagging assumptions.

### Error: "Implementation Diverges from Plan"
Cause: Discovered complexity not anticipated in design/plan
Solution: Return to Phase 2 (PLAN). Update plan with new understanding. Do NOT continue implementing against an outdated plan.

### Error: "Validation Fails"
Cause: Implementation bugs or missing requirements
Solution: Return to Phase 3 (IMPLEMENT) to fix. Do NOT proceed to RELEASE with failing validation. Re-run full validation after fixes.

### Error: "Release Blocked"
Cause: Merge conflicts, CI failures, or review feedback
Solution: Address each blocker. Return to Phase 4 (VALIDATE) if code changes were needed.

---

## Anti-Patterns

### Anti-Pattern 1: Skipping Design
**What it looks like**: "This feature is simple, let me just code it"
**Why wrong**: Simple features become complex. Without design, scope creeps and rework follows.
**Do instead**: Complete Phase 1 even if brief. A one-paragraph design doc is still a design doc.

### Anti-Pattern 2: Implementing Without a Plan
**What it looks like**: Starting to code after design, without breaking into tasks
**Why wrong**: Leads to unordered work, missed dependencies, and integration pain.
**Do instead**: Complete Phase 2. Even 3 ordered tasks is better than ad-hoc coding.

### Anti-Pattern 3: Shipping Without Validation
**What it looks like**: "Tests pass locally, let's merge"
**Why wrong**: Local passes != CI passes. Regressions hide in untested paths.
**Do instead**: Complete Phase 4 with full quality gates before Phase 5.

### Anti-Pattern 4: Not Recording Learnings
**What it looks like**: Shipping and moving on without retrospective
**Why wrong**: Same mistakes repeat. Process never improves.
**Do instead**: Complete Phase 6. Five minutes of recording saves hours on the next feature.
