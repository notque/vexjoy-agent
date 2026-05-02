---
name: subagent-driven-development
description: "Fresh-subagent-per-task execution with two-stage review gates."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "subagent per task"
    - "fresh context execution"
    - "plan execution"
    - "execute plan with agents"
    - "fresh context per task"
  category: process
  pairs_with:
    - pair-programming
    - testing-agents-with-subagents
---

# Subagent-Driven Development Skill

## Instructions

### Phase 1: SETUP

**Goal**: Extract all tasks and establish project context before implementation.

**Step 1: Read plan and extract tasks**

Read plan ONCE. Extract every task with full text:

```markdown
## Tasks Extracted from Plan

**Task 1: [Title]**
Full text: [Complete task description]
Files: [Files to create/modify]
Verification: [How to verify]
```

Provide complete task text inline -- prevents subagents from burning tokens reading files and polluting context.

**Step 2: Create TodoWrite**

```
1. [pending] Task 1: [Title]
2. [pending] Task 2: [Title]
3. [pending] Task 3: [Title]
```

**Step 3: Gather scene-setting context**

Before dispatching any implementer:
- `git status` and `git rev-parse HEAD` (capture BASE_SHA -- required for final integration review, must be captured BEFORE first implementer moves HEAD)
- Existing code patterns (naming, error handling style)
- Project conventions from CLAUDE.md
- Dependencies and setup requirements

Pass to EVERY subagent to prevent repeated discovery.

**Gate**: All tasks extracted with full text. BASE_SHA captured. Scene-setting gathered.

### Phase 2: EXECUTE (Per-Task Loop)

**Goal**: Implement each task with fresh subagent, verify through two-stage review.

**Step 1: Mark task in_progress** in TodoWrite.

**Step 2: Dispatch implementer subagent**

Use `./implementer-prompt.md` template. Include full task text, scene-setting context, clear deliverables, permission to ask questions.

- Implementer must understand task fully before coding. If questions arise: answer, provide context, re-dispatch.
- Tasks run sequentially -- overlapping file edits cause expensive conflicts.
- Implementer steps: understand -> ask questions if unclear -> implement (TDD where appropriate) -> run tests -> self-review -> commit.

**Step 3: ADR compliance review**

Use `./adr-reviewer-prompt.md`. Checks: implementation matches ADR exactly, nothing missing, nothing extra.

ADR compliance gates code quality -- wrong requirements make code quality review pointless.

If issues found: dispatch new implementer with fix instructions. Re-review. Repeat until pass.

**Max retries: 3.** After 3 failures: "ADR compliance failing after 3 attempts. Issues: [list]. Need human decision."

**Step 4: Code quality review**

Use `./code-quality-reviewer-prompt.md`. Only dispatch AFTER ADR compliance passes. Checks: structure, meaningful tests, error handling, no obvious bugs.

If issues: implementer fixes Critical and Important (Minor optional). Re-review.

**Max retries: 3.** After 3 failures: escalate to user.

**Step 5: Mark task complete**

Only when BOTH reviews pass:
```
Task [N]: [Title] -- COMPLETE
  ADR compliance: PASS
  Code quality: PASS
```

Return to Step 1 for next task.

**Gate**: Both reviews pass. Task marked complete.

### Phase 3: FINALIZE

**Goal**: Verify full implementation works together.

**Step 1: Final integration review**

Dispatch reviewer for entire changeset (diff from BASE_SHA to HEAD):
- All tests pass together
- No cross-task integration issues
- No conflicting patterns or redundant code

Per-task reviews ensure isolated correctness. Integration review catches cross-task problems: duplicate utilities, tests conflicting when run together, breaking changes not accounted for.

**Step 2: Complete workflow**

- `/pr-workflow` to create PR, or
- Manual merge, or
- Keep branch for further work

**Gate**: Final review passes. All tests pass. Integration verified.

---

## Error Handling

### Subagent Asks Questions Mid-Implementation
Cause: Insufficient context in dispatch prompt.
Solution: Answer all questions. Add missing context to scene-setting for future tasks. Re-dispatch with answers.

### Review Loop Exceeds 3 Retries
Cause: ADR ambiguity, fundamental misunderstanding, or unreasonable criteria.
Solution: Stop immediately. Summarize issues and attempts. Ask user to clarify ADR or adjust requirements. Resume only after direction.

### Subagent File Conflicts
Cause: Parallel dispatch (sequential constraint violated).
Solution: Resolve conflicts. Re-run affected review. Enforce sequential dispatch.

---

## References

### Prompt Templates
- `implementer-prompt.md`: Implementation subagent dispatch
- `adr-reviewer-prompt.md`: ADR compliance review dispatch
- `code-quality-reviewer-prompt.md`: Code quality review dispatch
