---
name: planning-with-files
description: |
  Persistent markdown files as working memory for complex tasks: plan,
  track progress, store findings. Use when tasks have 3+ phases, require
  research, span many tool calls, or risk context drift. Use for "plan",
  "break down", "track progress", "multi-step", or complex tasks. Do NOT
  use for simple lookups, single-file edits, or questions answerable in
  one response.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Planning with Files Skill

## Operator Context

This skill operates as an operator for file-based planning workflows, configuring Claude's behavior for persistent, structured task execution. It implements the **External Memory** architectural pattern — store on disk, re-read to maintain focus, update after each action — with **Context Engineering** principles from Manus-style agent design.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before starting any planned work
- **Over-Engineering Prevention**: Plan only the phases needed. No speculative phases, no "future-proofing" empty sections
- **Plan Before Execute**: NEVER start complex work without creating `task_plan.md` first
- **Re-Read Before Decide**: Read plan file before every major decision to combat context drift
- **Update After Act**: Mark phases complete and update status immediately after each phase
- **Store, Don't Stuff**: Large outputs go to files, not context. Keep only file paths in working memory

### Default Behaviors (ON unless disabled)
- **3-File Pattern**: Create `task_plan.md`, `notes.md`, and deliverable file for non-trivial tasks
- **Error Logging**: Record all errors in the "Errors Encountered" section of plan file
- **Phase Checkboxes**: Use `- [ ]` / `- [x]` for phase tracking
- **Status Line**: Maintain a "Currently in Phase X" status at bottom of plan
- **Findings Synthesis**: Consolidate research notes into categorized findings before generating deliverables
- **Cleanup at Completion**: Remove temporary scratch files, keep plan and deliverable

### Optional Behaviors (OFF unless enabled)
- **Timestamp Entries**: Add `[YYYY-MM-DD]` timestamps to errors and decisions
- **Git Integration**: Create commits at phase boundaries
- **Parallel Research**: Launch multiple search queries simultaneously in research phase

## What This Skill CAN Do
- Structure complex tasks into trackable phases with file-based persistence
- Maintain focus across long sessions by re-reading goals into attention window
- Store and synthesize research findings across multiple sources
- Recover from context drift by grounding decisions in written plans
- Preserve failure traces for error recovery and institutional knowledge

## What This Skill CANNOT Do
- Replace domain-specific skills (use systematic-debugging for bugs, systematic-refactoring for refactoring)
- Execute without a written plan for complex tasks
- Store sensitive data (credentials, tokens) in plan files
- Skip the re-read step before major decisions

---

## Instructions

### Phase 1: CREATE PLAN

**Goal**: Establish written plan before any execution begins.

**Step 1: Assess complexity**

Determine if planning is needed:
- 3+ steps or phases required → Plan needed
- Research or information gathering involved → Plan needed
- Task spans multiple files or systems → Plan needed
- Simple lookup or single edit → Skip planning

**Step 2: Create `task_plan.md`**

```markdown
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Phases
- [ ] Phase 1: [First phase]
- [ ] Phase 2: [Second phase]
- [ ] Phase 3: [Third phase]
- [ ] Phase 4: [Review and deliver]

## Key Questions
1. [Question to answer before proceeding]

## Decisions Made
- [Decision]: [Rationale]

## Errors Encountered
- [Error]: [Resolution]

## Status
**Currently in Phase 1** - Creating plan
```

**Gate**: `task_plan.md` exists with goal, phases, and key questions defined. Proceed only when gate passes.

### Phase 2: RESEARCH AND GATHER

**Goal**: Collect all information needed before execution.

**Step 1: Re-read plan**

Read `task_plan.md` to refresh goals in attention window. This is mandatory, not optional.

**Step 2: Gather information**

Search, read, explore. Store findings in `notes.md`:

```markdown
# Notes: [Topic]

## Sources
### Source 1: [Name]
- Key points:
  - [Finding]
  - [Finding]

## Synthesized Findings
### [Category]
- [Finding with context]
```

**Step 3: Update plan**

Mark Phase 2 complete. Log any decisions made. Update status line.

**Gate**: All key questions from Phase 1 answered. Findings stored in `notes.md`. Proceed only when gate passes.

### Phase 3: EXECUTE

**Goal**: Build the deliverable using gathered information.

**Step 1: Re-read plan and notes**

Read `task_plan.md` then `notes.md`. Both reads are mandatory before generating output.

**Step 2: Create deliverable**

Build the output artifact. Reference notes for accuracy. Write to the deliverable file.

**Step 3: Update plan**

Mark Phase 3 complete. Log any errors encountered during execution.

**Gate**: Deliverable file exists and addresses the goal stated in the plan. Proceed only when gate passes.

### Phase 4: VERIFY AND DELIVER

**Goal**: Confirm deliverable meets the plan's stated goal.

**Step 1: Re-read plan one final time**

Compare deliverable against original goal and key questions. Every question should be addressed.

**Step 2: Verify completeness**

- All phases marked `[x]`
- All key questions answered
- Deliverable matches stated goal
- Errors section documents any issues encountered

**Step 3: Deliver and clean up**

Present the deliverable. Remove temporary scratch files. Keep `task_plan.md` and deliverable as artifacts.

**Gate**: All verification checks pass. Deliverable is complete.

---

## Examples

### Example 1: Research Task
User says: "Research morning exercise benefits and write a summary"
Actions:
1. Create `task_plan.md` with goal and 4 phases (CREATE PLAN)
2. Search sources, store findings in `notes.md` (RESEARCH)
3. Re-read notes, write `morning_exercise_summary.md` (EXECUTE)
4. Verify summary covers all key questions, deliver (VERIFY)
Result: Structured summary grounded in documented research

### Example 2: Multi-File Refactoring Plan
User says: "Plan the migration from REST to GraphQL"
Actions:
1. Create `task_plan.md` with migration phases (CREATE PLAN)
2. Inventory endpoints, dependencies, store in `notes.md` (RESEARCH)
3. Write `migration_plan.md` with ordered steps (EXECUTE)
4. Verify all endpoints covered, deliver plan (VERIFY)
Result: Actionable migration plan with nothing missed

---

## Error Handling

### Error: "Context Drift — Forgot Original Goal"
Cause: Too many tool calls without re-reading the plan
Solution:
1. Immediately read `task_plan.md`
2. Compare current work against stated goal
3. Correct course if diverged
4. Increase re-read frequency for remainder of task

### Error: "Plan Becomes Stale or Inaccurate"
Cause: New information invalidates original phases or decisions
Solution:
1. Update plan with new information and revised phases
2. Log the change in Decisions Made with rationale
3. Continue from updated plan

### Error: "Notes File Too Large for Context"
Cause: Research phase produced more content than fits in attention window
Solution:
1. Add a "Summary" section at top of `notes.md` with key takeaways
2. Reference specific sections by heading when needed
3. Read only relevant sections, not entire file

---

## Anti-Patterns

### Anti-Pattern 1: Executing Without a Plan
**What it looks like**: Jumping straight into code or content without creating `task_plan.md`
**Why wrong**: No way to track progress, detect drift, or verify completeness
**Do instead**: Create plan first. Always. Even if it takes 30 seconds.

### Anti-Pattern 2: Writing Plan but Never Re-Reading
**What it looks like**: Creating `task_plan.md` then never opening it again
**Why wrong**: Plan exists to combat context drift. Unread plans provide zero value.
**Do instead**: Re-read before every major decision and phase transition.

### Anti-Pattern 3: Stuffing Context Instead of Storing
**What it looks like**: Keeping all research findings in working memory instead of `notes.md`
**Why wrong**: Context window fills up, earlier information gets pushed out
**Do instead**: Write to files immediately. Read back only what you need.

### Anti-Pattern 4: Over-Planning Simple Tasks
**What it looks like**: Creating 3 files and 8 phases for a single-file edit
**Why wrong**: Planning overhead exceeds task complexity. Wastes time.
**Do instead**: Use complexity check in Phase 1. Skip planning for simple tasks.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition enforcement

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I remember the goal, no need to re-read" | Memory degrades after ~50 tool calls | Read `task_plan.md` before deciding |
| "Quick task, no plan needed" | Quick tasks become multi-step tasks | Assess complexity first |
| "Notes are in my context already" | Context is ephemeral, files are persistent | Write to `notes.md` |
| "Plan is mostly done, close enough" | Mostly ≠ Complete | Mark all phases [x] or explain why not |
