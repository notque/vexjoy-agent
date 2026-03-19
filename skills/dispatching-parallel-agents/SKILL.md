---
name: dispatching-parallel-agents
description: |
  Dispatch independent subagents in parallel for unrelated problems spanning
  different subsystems. Use when 2+ failures have independent root causes,
  multiple subsystems are broken independently, or user requests concurrent
  investigation. Use for "parallel", "multiple failures", "independent bugs",
  "fix these concurrently". Do NOT use for related failures, shared-state
  problems, or exploratory debugging where root cause is unknown.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
  - Task
  - Bash
triggers:
  - multiple failures
  - independent problems
  - parallel
  - concurrent
  - 3+ tasks
---

# Dispatching Parallel Agents

## Operator Context

This skill operates as an operator for parallel dispatch workflows, configuring Claude's behavior for concurrent investigation of independent problems. It implements the **Fan-Out / Fan-In** architectural pattern -- dispatch isolated agents, collect results, integrate -- with **Domain Separation** ensuring agents never interfere with each other.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before dispatching agents
- **Over-Engineering Prevention**: Fix only what is broken. No speculative improvements across domains
- **Independence Verification**: MUST confirm problems are independent before parallel dispatch
- **Single Message Dispatch**: MUST launch all parallel agents in ONE message for true concurrency
- **Scoped Prompts**: Each agent MUST receive explicit scope, constraints, and expected output
- **Post-Integration Verification**: MUST run full test suite after all agents return

### Default Behaviors (ON unless disabled)
- **Conflict Detection**: Check if agents modified overlapping files after completion
- **Prompt Template**: Use structured prompt with scope, goal, constraints, and output format
- **Summary Collection**: Require each agent to return root cause and files modified
- **Maximum Parallelism**: Cap at 10 concurrent agents to avoid coordination overhead
- **Result Spot-Check**: Verify at least one agent's fix manually before declaring done
- **Sequential Fallback**: If agents report same root cause, stop and investigate holistically

### Optional Behaviors (OFF unless enabled)
- **Dependency Graph**: Map subsystem dependencies before dispatching
- **Resource Isolation**: Assign exclusive file/port ranges to each agent
- **Retry on Failure**: Re-dispatch failed agents with additional context

## What This Skill CAN Do
- Dispatch multiple agents to work on independent problems concurrently
- Reduce total investigation time proportional to number of independent problems
- Detect conflicts between agent fixes during integration
- Provide structured prompts that keep agents focused on their domain
- Integrate results and verify the combined fix

## What This Skill CANNOT Do
- Parallelize problems that share state or root cause
- Guarantee agents will not edit overlapping files
- Replace systematic debugging for single complex bugs (use systematic-debugging instead)
- Plan implementation work (use workflow-orchestrator instead)
- Execute sequential dependent tasks (use subagent-driven-development instead)

---

## Instructions

### Phase 1: CLASSIFY

**Goal**: Determine whether problems are independent and suitable for parallel dispatch.

**Step 1: List all problems**

```markdown
## Problems Identified
1. [Problem A] - [Subsystem] - [Error summary]
2. [Problem B] - [Subsystem] - [Error summary]
3. [Problem C] - [Subsystem] - [Error summary]
```

**Step 2: Test independence**

For each pair of problems, ask: "If I fix problem A, does it affect problem B?"
- If NO for all pairs --> Independent, proceed to parallel dispatch
- If YES or MAYBE for any pair --> Investigate those together first, parallelize the rest

**Step 3: Verify no shared state**

Check that agents will not compete for:
- Same source files
- Same database tables or ports
- Same configuration files
- Same external services

**Gate**: All dispatched problems confirmed independent with no shared state. Proceed only when gate passes.

### Phase 2: DISPATCH

**Goal**: Launch focused agents with clear scope in a single message.

**Step 1: Create agent prompts**

Each agent prompt MUST include:

```markdown
Fix [N] failing tests in [FILE/SUBSYSTEM]:

1. "[Specific failure]" - [error summary]
2. "[Specific failure]" - [error summary]

Context: [What this subsystem does]

Your task:
1. Read the relevant code and understand what it does
2. Identify root cause - is this a code issue or test issue?
3. Fix the issue (prefer fixing implementation over changing test expectations)
4. Run tests to verify fix

Constraints:
- Only modify files in [SCOPE]
- Do NOT change [OUT OF SCOPE FILES]

Return:
- Root cause (1-2 sentences)
- Files modified
- How to verify the fix
```

**Step 2: Dispatch all agents in ONE message**

Use multiple Task tool calls in a single response. All agents run concurrently.

**Gate**: All agents dispatched with scoped prompts and constraints. Proceed only when all agents return.

### Phase 3: INTEGRATE

**Goal**: Combine agent results, detect conflicts, verify combined fix.

**Step 1: Read each agent summary**
- What was the root cause?
- What files were modified?
- Did the agent's local tests pass?

**Step 2: Check for conflicts**
- Did any two agents modify the same file?
- Did any agent report the same root cause as another?
- Did any agent report inability to reproduce?

If conflicts detected: Do NOT auto-merge. Understand which fix is correct. May need sequential re-investigation.

**Step 3: Run full test suite**

Execute the complete test suite to verify all fixes work together without regressions.

**Step 4: Spot-check at least one fix**

Read the actual code change from one agent and verify it makes sense.

**Gate**: Full suite passes, no conflicts, fixes verified. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Document what was fixed and how.

```markdown
## Parallel Dispatch Summary
Agents dispatched: [N]
Problems resolved: [N]

### Agent 1: [Subsystem]
- Root cause: [description]
- Files: [list]

### Agent 2: [Subsystem]
- Root cause: [description]
- Files: [list]

Integration: [No conflicts / Conflicts resolved by...]
Verification: Full test suite passes
```

**Gate**: Summary documented. Task complete.

---

## Error Handling

### Error: "Agents Report Same Root Cause"
Cause: Problems were not actually independent; shared underlying issue
Solution: Stop parallel execution. Consolidate into single investigation using systematic-debugging skill. The shared root cause must be fixed once, not independently.

### Error: "Agent Fixes Break Other Agent's Tests"
Cause: Hidden dependency between subsystems; agents modified shared code paths
Solution: Revert conflicting changes. Re-investigate the conflicting pair sequentially. Apply the combined fix, then re-run remaining agents if needed.

### Error: "Agent Cannot Reproduce Problem"
Cause: Problem depends on state from another subsystem, or environment mismatch
Solution: Provide additional context. If still cannot reproduce, the problem may not be independent -- move it to a sequential investigation.

### Error: "Worktree Agent Commits to Wrong Branch"
Cause: When multiple worktrees exist, agents may operate on an unexpected branch because the worktree's branch and push target can diverge.
Solution:
1. In each agent's dispatch prompt, explicitly state the target branch name
2. Include `git branch --show-current` as the first verification step in each agent
3. After all agents return, verify each commit landed on the intended branch
4. If a commit landed on the wrong branch, cherry-pick to the correct branch and reset
*Graduated from learning.db — multi-agent-coordination/worktree-branch-confusion*

---

## Anti-Patterns

### Anti-Pattern 1: Parallelizing Related Problems
**What it looks like**: Dispatching agents for failures that share a root cause
**Why wrong**: Multiple agents fix the same thing differently, creating conflicts
**Do instead**: Test independence first. If unsure, investigate sequentially.

### Anti-Pattern 2: Vague Agent Prompts
**What it looks like**: "Fix the failing tests" with no scope or constraints
**Why wrong**: Agent wanders, modifies out-of-scope files, takes too long
**Do instead**: Use the structured prompt template with explicit scope and constraints.

### Anti-Pattern 3: Skipping Integration Verification
**What it looks like**: "All agents reported success, we're done!"
**Why wrong**: Individual fixes may conflict or introduce cross-subsystem regressions
**Do instead**: Run full test suite after all agents return. Spot-check at least one fix.

### Anti-Pattern 4: Dispatching Before Understanding
**What it looks like**: Immediately parallelizing without confirming independence
**Why wrong**: Wastes agent effort; conflicting fixes require rework
**Do instead**: Complete Phase 1 classification. Independence verification is not optional.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "These problems look independent" | Looking ≠ verified independence | Test each pair explicitly |
| "Agent said it's fixed" | Agent report ≠ integrated verification | Run full test suite |
| "No conflicts in file list" | File-level ≠ logic-level conflict | Spot-check actual changes |
| "Too many problems to classify" | Skipping classification causes rework | Classify all before dispatch |
