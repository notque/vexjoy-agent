---
name: planning-with-files
description: "Persistent markdown files as working memory for complex multi-phase tasks."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
routing:
  triggers:
    - "create plan"
    - "task plan"
    - "working memory"
  category: process
---

# Planning with Files Skill

## Overview

This skill uses persistent markdown files as external memory to execute complex, multi-phase tasks without context drift. Files serve as the single source of truth for goals, progress, and decisions. Re-read files before major decisions to ground work in written commitments rather than fallible working memory.

The workflow consists of four phases:
1. **CREATE PLAN** — Write goals and phases before executing
2. **RESEARCH AND GATHER** — Collect information, store findings, update plan
3. **EXECUTE** — Build deliverable using gathered information
4. **VERIFY AND DELIVER** — Confirm completeness, clean up temporary files

This skill is mandatory for tasks with 3+ phases, research requirements, or risk of context drift after many tool calls.

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

**Why this matters**: Creating a plan takes 30 seconds but saves hours in rework. Plans prevent mid-task goal drift by anchoring decisions to written commitment. Skip this step only for single-file edits or lookups answerable in one response.

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

Open `task_plan.md` and read it completely. This is mandatory, not optional.

**Why this matters**: After ~50 tool calls, memory degrades. Re-reading restores focus and prevents drift. Claims like "I remember the goal, no need to re-read" are the primary cause of failed complex tasks.

**Step 2: Gather information**

Search, read, explore. Store all findings in `notes.md`:

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

**Why separate files**: Context window is ephemeral. Files are persistent. Writing findings to `notes.md` immediately ensures they survive context compression. Reference the file by section header when needed rather than keeping all content in working memory.

**Step 3: Update plan**

Mark Phase 2 complete. Log any decisions made. Update status line.

**Gate**: All key questions from Phase 1 answered. Findings stored in `notes.md`. Proceed only when gate passes.

### Phase 3: EXECUTE

**Goal**: Build the deliverable using gathered information.

**Step 1: Re-read plan and notes**

Read `task_plan.md` first, then `notes.md`. Both reads are mandatory before generating output.

**Why this matters**: Phase transitions are high-risk points for context drift. Two reads ground execution in both original goals and current findings, preventing divergence from the stated intent.

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

Check all verification criteria:
- All phases marked `[x]`
- All key questions answered
- Deliverable matches stated goal
- Errors section documents any issues encountered

**Why this matters**: "Done" is often an assumption, not a fact. This checklist is a defense-in-depth verification gate. Marks complete only when all criteria pass, not when work "feels done" or "should be done."

**Step 3: Deliver and clean up**

Present the deliverable. Remove temporary scratch files. Keep `task_plan.md` and deliverable as artifacts.

**Gate**: All verification checks pass. Deliverable is complete.

---

## Examples

### Example 1: Research Task
User says: "Research morning exercise benefits and write a summary"

**Phase 1**: Create `task_plan.md` with goal and 4 phases
- Goal: Produce a summary of morning exercise benefits backed by research

**Phase 2**: Search sources, store findings in `notes.md`
- Create notes.md with "Sources" section (studies, articles)
- Create "Synthesized Findings" with categories: mental health, physical health, productivity

**Phase 3**: Re-read notes, write `morning_exercise_summary.md`
- Reference findings for accuracy

**Phase 4**: Verify summary covers all key questions, deliver
- Result: Structured summary grounded in documented research

### Example 2: Multi-File Refactoring Plan
User says: "Plan the migration from REST to GraphQL"

**Phase 1**: Create `task_plan.md` with migration phases
- Phase 1: Inventory endpoints and dependencies
- Phase 2: Design GraphQL schema
- Phase 3: Implement resolvers
- Phase 4: Migrate clients
- Phase 5: Decommission REST endpoints

**Phase 2**: Inventory endpoints, dependencies, store in `notes.md`
- Document endpoint mapping to GraphQL queries/mutations
- Identify clients and their endpoint usage

**Phase 3**: Write `migration_plan.md` with ordered steps
- Step 1: Build GraphQL service alongside REST
- Step 2: Migrate internal clients first

**Phase 4**: Verify all endpoints covered, deliver plan
- Result: Actionable migration plan with nothing missed

---

## Error Handling

### Error: "Context Drift — Forgot Original Goal"
**Cause**: Too many tool calls without re-reading the plan

**Solution**:
1. Immediately read `task_plan.md`
2. Compare current work against stated goal
3. Correct course if diverged
4. Increase re-read frequency for remainder of task

### Error: "Plan Becomes Stale or Inaccurate"
**Cause**: New information invalidates original phases or decisions

**Solution**:
1. Update plan with new information and revised phases
2. Log the change in Decisions Made with rationale
3. Continue from updated plan

### Error: "Notes File Too Large for Context"
**Cause**: Research phase produced more content than fits in attention window

**Solution**:
1. Add a "Summary" section at top of `notes.md` with key takeaways
2. Reference specific sections by heading when needed
3. Read only relevant sections, not entire file

### Error: "Task Becomes Unstuck Midway"
**Cause**: Required information is missing or deliverable is off-track

**Solution**:
1. Stop forward execution
2. Re-read plan to clarify original goal
3. Update plan with new discovery
4. Decide: continue with modified goal, or gather more information
5. Log decision and rationale in plan

---

## References

**Standard File Names**: Plans use `task_plan.md`, research notes use `notes.md`, deliverables use domain-specific names (e.g., `migration_plan.md`, `research_summary.md`)

**Required Elements**: Every plan must contain Goal (one sentence), Phases (with [ ] checkboxes), Key Questions, and Status line. Without these, the plan provides zero value.

**Phase Gate Enforcement**: Never advance to next phase until current phase gate passes. Gates are designed to catch problems early. "Mostly done" phases cause downstream errors. Enforce gates strictly.
