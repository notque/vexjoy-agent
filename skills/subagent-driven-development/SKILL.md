---
name: subagent-driven-development
description: |
  Fresh-subagent-per-task execution with two-stage review (ADR compliance +
  code quality). Use when an implementation plan exists with mostly independent
  tasks and you want quality gates between each. Use for "execute plan",
  "subagent", "dispatch tasks", or multi-task implementation runs. Do NOT use
  for single simple tasks, tightly coupled work needing shared context, or when
  the user wants manual review after each task.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
---

# Subagent-Driven Development Skill

## Operator Context

This skill operates as an operator for plan execution workflows, configuring Claude's behavior for disciplined task dispatch with mandatory quality gates. It implements the **Controller-Worker** architectural pattern -- controller extracts context, workers execute in isolation, reviewers verify -- with **Two-Stage Review** ensuring both ADR compliance and code quality.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before executing any task
- **Over-Engineering Prevention**: Implement only what the ADR requires. No speculative improvements, no "while I'm here" changes
- **ADR Compliance Before Quality**: NEVER run code quality review before ADR compliance passes
- **Full Context Injection**: NEVER make a subagent read the plan file; provide full task text in the dispatch
- **Review Gates Mandatory**: NEVER mark a task complete until both reviews pass
- **Sequential Tasks Only**: NEVER dispatch multiple implementation subagents in parallel (causes file conflicts)
- **BASE_SHA Capture**: Run `git rev-parse HEAD` BEFORE dispatching the first implementer

### Default Behaviors (ON unless disabled)
- **Fresh Subagent Per Task**: Each task gets a clean subagent with no cross-task context pollution
- **Scene-Setting Context**: Gather branch status, code patterns, and conventions before dispatch
- **Q&A Before Implementation**: Answer subagent questions before they start coding
- **Review Fix Loops**: When reviewer finds issues, implementer fixes and reviewer re-reviews
- **Max 3 Review Retries**: Escalate to user after 3 failed review cycles per stage
- **Final Integration Review**: After all tasks, dispatch a holistic reviewer for the full changeset
- **TodoWrite Tracking**: Create TodoWrite with all tasks upfront for progress visibility

### Optional Behaviors (OFF unless enabled)
- **Parallel Research**: Pre-gather codebase context for all tasks in parallel before execution
- **Auto PR Creation**: Run pr-sync automatically after final review passes
- **Custom Reviewer Prompts**: Override default reviewer prompt templates

## What This Skill CAN Do
- Execute multi-task plans with quality gates between each task
- Dispatch fresh subagents that implement, test, and commit independently
- Enforce ADR compliance before allowing code quality review
- Escalate to user when review loops exceed retry limits
- Track progress across tasks with TodoWrite

## What This Skill CANNOT Do
- Execute without an existing implementation plan (use workflow-orchestrator first)
- Run tasks in parallel (file conflicts make this unsafe)
- Skip either stage of the two-stage review
- Fix review issues itself (the implementer subagent must fix)
- Replace user judgment on ADR ambiguity (escalates instead)

---

## Instructions

### Phase 1: SETUP

**Goal**: Extract all tasks and establish project context before any implementation begins.

**Step 1: Read plan and extract tasks**

Read the plan file ONCE. Extract every task with full text:

```markdown
## Tasks Extracted from Plan

**Task 1: [Title]**
Full text: [Complete task description from plan]
Files: [List of files to create/modify]
Verification: [How to verify this task]

**Task 2: [Title]**
...
```

**Step 2: Create TodoWrite**

Create TodoWrite with ALL tasks:
```
1. [pending] Task 1: [Title]
2. [pending] Task 2: [Title]
3. [pending] Task 3: [Title]
```

**Step 3: Gather scene-setting context**
- Current branch status (`git status`)
- Capture BASE_SHA: `git rev-parse HEAD`
- Relevant existing code patterns
- Project conventions from CLAUDE.md
- Dependencies and setup requirements

This context gets passed to EVERY subagent.

**Gate**: All tasks extracted with full text. BASE_SHA captured. Scene-setting context gathered. Proceed only when gate passes.

### Phase 2: EXECUTE (Per-Task Loop)

**Goal**: Implement each task with a fresh subagent, then verify through two-stage review.

**Step 1: Mark task in_progress**

Update TodoWrite status for the current task.

**Step 2: Dispatch implementer subagent**

Use the Task tool with the prompt template from `./implementer-prompt.md`. Include:
- Full task text (NEVER say "see plan")
- Scene-setting context
- Clear deliverables
- Permission to ask questions

If the implementer asks questions: answer clearly and completely. Provide additional context. Re-dispatch with answers. Do NOT rush them into implementation.

The implementer MUST:
1. Understand the task fully
2. Ask questions if unclear (BEFORE implementing)
3. Implement following TDD where appropriate
4. Run tests
5. Self-review code
6. Commit changes

**Step 3: Dispatch ADR compliance reviewer subagent**

Use the prompt template from `./adr-reviewer-prompt.md`. The ADR compliance reviewer checks:
- Does implementation match the ADR EXACTLY?
- Is anything MISSING from requirements?
- Is anything EXTRA that was not requested?

If ADR compliance reviewer finds issues: dispatch new implementer subagent with fix instructions. ADR compliance reviewer reviews again. Repeat until ADR compliance passes.

**Max retries: 3** -- After 3 failed ADR compliance reviews, STOP and escalate:
> "ADR compliance failing after 3 attempts. Issues: [list]. Need human decision."

**Step 4: Dispatch code quality reviewer subagent**

Use the prompt template from `./code-quality-reviewer-prompt.md`. The code quality reviewer checks:
- Code is well-structured
- Tests are meaningful
- Error handling is appropriate
- No obvious bugs

If quality reviewer finds issues: implementer fixes Critical and Important issues (Minor issues are optional). Quality reviewer reviews again.

**Max retries: 3** -- After 3 failed quality reviews, STOP and escalate:
> "Quality review failing after 3 attempts. Issues: [list]. Need human decision."

**Step 5: Mark task complete**

Only when BOTH reviews pass:
```
Task [N]: [Title] -- COMPLETE
  ADR compliance: PASS
  Code quality: PASS
```

Return to Step 1 for the next task.

**Gate**: Both ADR compliance and code quality reviews pass. Task marked complete in TodoWrite. Proceed only when gate passes.

### Phase 3: FINALIZE

**Goal**: Verify the full implementation works together and complete the workflow.

**Step 1: Final integration review**

Dispatch a reviewer subagent for the entire changeset (diff from BASE_SHA to HEAD):
- All tests pass together
- No integration issues between tasks
- No conflicting patterns or redundant code

**Step 2: Complete development workflow**

Use the appropriate completion path:
- `/pr-sync` to create PR
- Manual merge
- Keep branch for further work

**Gate**: Final review passes. All tests pass. Integration verified. Proceed only when gate passes.

---

## Error Handling

### Error: "Subagent Asks Questions Mid-Implementation"
Cause: Insufficient context in the dispatch prompt
Solution:
1. Answer all questions clearly and completely
2. Add the missing context to the scene-setting for future tasks
3. Re-dispatch implementer with answers included

### Error: "Review Loop Exceeds 3 Retries"
Cause: ADR ambiguity, fundamental misunderstanding, or unreasonable review criteria
Solution:
1. STOP the loop immediately
2. Summarize all issues and attempted fixes for the user
3. Ask user to clarify ADR or adjust requirements
4. Resume only after user provides direction

### Error: "Subagent File Conflicts"
Cause: Multiple subagents modifying overlapping files (usually from parallel dispatch)
Solution:
1. Resolve conflicts manually
2. Re-run the affected review stage
3. Enforce sequential dispatch going forward -- NEVER parallelize implementers

---

## Anti-Patterns

### Anti-Pattern 1: Skipping ADR Compliance Review for "Obvious" Tasks
**What it looks like**: "This task is straightforward, code quality review is enough"
**Why wrong**: Even simple tasks can miss requirements or add unrequested scope
**Do instead**: Run both review stages for every task. No exceptions.

### Anti-Pattern 2: Controller Fixing Issues Directly
**What it looks like**: Controller edits code instead of dispatching a fix subagent
**Why wrong**: Pollutes controller context. Controller should orchestrate, not implement.
**Do instead**: Dispatch a new implementer subagent with specific fix instructions.

### Anti-Pattern 3: Bundling Multiple Tasks Into One Subagent
**What it looks like**: "Tasks 2 and 3 are related, I'll combine them"
**Why wrong**: Defeats isolation. Review becomes unclear. Rollback is impossible.
**Do instead**: One task per subagent. Always.

### Anti-Pattern 4: Proceeding With Unresolved Questions
**What it looks like**: "The subagent will figure it out from the code"
**Why wrong**: Subagent builds the wrong thing. Review catches it late. Wasted cycles.
**Do instead**: Answer every question before implementation begins.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This task is simple, skip ADR review" | Simple tasks still miss requirements | Run both review stages |
| "Subagent can read the plan itself" | File reading wastes tokens, context pollution | Provide full task text in dispatch |
| "Reviews passed, skip final integration check" | Per-task reviews miss cross-task issues | Run final integration review |
| "I'll fix this small issue myself instead of dispatching" | Controller context pollution breaks orchestration | Dispatch fix subagent |
| "Tasks 2 and 3 are related, combine them" | Combined tasks break isolation and review clarity | One task per subagent, always |

### Prompt Templates
- `implementer-prompt.md`: Dispatch template for implementation subagents
- `adr-reviewer-prompt.md`: Dispatch template for ADR compliance review
- `code-quality-reviewer-prompt.md`: Dispatch template for code quality review
