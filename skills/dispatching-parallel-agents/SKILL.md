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
routing:
  triggers:
    - "parallel agents"
    - "independent failures"
    - "fan-out dispatch"
    - "do these simultaneously"
    - "handle all at once"
    - "run in parallel"
    - "split into tasks"
  category: process
---

# Dispatching Parallel Agents

Fan-Out / Fan-In pattern for concurrent investigation of independent problems. Dispatch isolated agents with domain separation so they never interfere with each other, collect results, integrate, verify.

## Instructions

### Phase 1: CLASSIFY

**Goal**: Determine whether problems are independent and suitable for parallel dispatch.

**Step 1: List all problems**

Read and follow the repository CLAUDE.md before proceeding. Then enumerate every problem:

```markdown
## Problems Identified
1. [Problem A] - [Subsystem] - [Error summary]
2. [Problem B] - [Subsystem] - [Error summary]
3. [Problem C] - [Subsystem] - [Error summary]
```

Fix only what is broken -- do not add speculative improvements across domains.

**Step 2: Test independence**

For each pair of problems, ask: "If I fix problem A, does it affect problem B?"
- If NO for all pairs --> Independent, proceed to parallel dispatch
- If YES or MAYBE for any pair --> Investigate those together first, parallelize the rest

Do not skip this step regardless of how obvious independence appears. "These problems look independent" is an assumption, not a verification -- test each pair explicitly. If there are many problems, classify all of them before dispatching any.

**Step 3: Check scope overlap (deterministic)**

Before dispatching, infer file scopes from each task description, then run the overlap checker:

```bash
python3 scripts/check-scope-overlap.py --tasks '[
  {"id": "task-1", "scope": ["handlers/auth.go", "middleware/"], "readonly": false},
  {"id": "task-2", "scope": ["handlers/payment.go", "models/"], "readonly": false}
]' --json
```

Scope inference rules:
- Extract file paths and directories mentioned in the task description
- If a task only reads files (investigation, analysis), set `"readonly": true`
- If scope cannot be inferred, use the subsystem directory as a broad scope
- When in doubt, over-scope -- false positives (unnecessary serialization) are safe

Interpret the output:
- `"conflicts": []` --> All tasks can run in parallel. Proceed to Phase 2.
- `"conflicts": [...]` --> Use `"parallel_groups"` to determine wave ordering. Tasks in the same group run together; groups run sequentially.
- Display the grouping decision in the dispatch summary.

**Step 4: Verify no shared state beyond files**

Check that agents will not compete for:
- Same database tables or ports
- Same configuration files
- Same external services

These are NOT caught by the scope overlap script and require manual verification.

**Gate**: All dispatched problems confirmed independent via scope overlap check and shared state review. Proceed only when gate passes.

### Phase 2: DISPATCH

**Goal**: Launch focused agents with clear scope on a single shared branch.

**Step 0: Create target branch (ADR-093 -- Branch Convergence)**

Before dispatching any agents, the orchestrator creates and checks out the target branch:

```bash
git checkout -b feat/{descriptive-name}
```

This branch is the single convergence point for all parallel agents. Individual agents MUST NOT create their own branches. Without this step, N agents create N branches (the "scattered branches" problem) -- cherry-picking and branch discovery after the fact is fragile and error-prone. Creating the branch before dispatch is simple and deterministic.

**Step 1: Create agent prompts**

Each agent receives an explicit prompt with scope, goal, constraints, and expected output format. Vague prompts like "Fix the failing tests" cause agents to wander, modify out-of-scope files, and take too long. Use this template:

```markdown
Fix [N] failing tests in [FILE/SUBSYSTEM]:

1. "[Specific failure]" - [error summary]
2. "[Specific failure]" - [error summary]

Context: [What this subsystem does]

Branch: Work on branch `{branch_name}`. Do NOT create a new branch.
Do NOT checkout other branches. Commit your changes to this branch.
Run `git branch --show-current` first to verify you are on the correct branch.

Your task:
1. Verify you are on branch `{branch_name}`
2. Read the relevant code and understand what it does
3. Identify root cause - is this a code issue or test issue?
4. Fix the issue (prefer fixing implementation over changing test expectations)
5. Run tests to verify fix

Constraints:
- Only modify files in [SCOPE]
- Do NOT change [OUT OF SCOPE FILES]
- Do NOT create a new branch or checkout other branches

Return:
- Root cause (1-2 sentences)
- Files modified
- Branch confirmed: [branch name from git branch --show-current]
- How to verify the fix
```

The branch name must appear in every agent prompt -- agents will not "figure out the branch" on their own, and merging scattered branches after the fact creates conflicts and pollutes history.

**Step 2: Dispatch agents using scope overlap grouping**

All agents in a wave MUST be dispatched in a single message for true concurrency. Dispatching them one at a time serializes the work and defeats the purpose.

- If Phase 1 scope check returned a single parallel group: dispatch all agents in ONE message. All run concurrently.
- If Phase 1 scope check returned multiple groups: dispatch each group as a sequential wave. All agents within a wave run concurrently, but waves run sequentially. Wait for wave N to complete before dispatching wave N+1.

Cap at 10 concurrent agents per wave to avoid coordination overhead.

```markdown
## Dispatch Plan
Wave 1 (parallel): [task-1, task-2] -- no file overlap
Wave 2 (after wave 1): [task-3] -- overlaps with task-1 on handlers/auth.go
```

**Gate**: All agents dispatched with scoped prompts and constraints. Proceed only when all agents return.

### Phase 3: INTEGRATE

**Goal**: Combine agent results, detect conflicts, verify combined fix.

**Step 1: Verify branch convergence (ADR-093)**

Before reading results, verify all agent work landed on the target branch:

```bash
git branch --show-current   # Must show the target branch
git log --oneline -10       # All recent commits should be on this branch
```

If an agent created a rogue branch:
1. Identify the rogue branch: `git branch --list 'feat/*'`
2. Cherry-pick its commits to the target branch: `git cherry-pick <commit-hash>`
3. Delete the rogue branch: `git branch -d <rogue-branch>`

If an agent used a worktree, its commits are on a separate branch by design -- cherry-pick them to the target branch.

**Step 2: Read each agent summary**
- What was the root cause?
- What files were modified?
- Did the agent's local tests pass?
- Did the agent confirm the correct branch?

If agents report the same root cause, stop integration immediately. The problems were not actually independent -- consolidate into a single investigation.

**Step 3: Check for conflicts**
- Did any agent modify files outside its declared scope? (Compare actual files modified vs Phase 1 scope declarations)
- Did any two agents modify the same file? (Should not happen if scope overlap check was clean, but verify)
- Did any agent report inability to reproduce?

"No conflicts in the file list" does not mean no conflicts in logic -- spot-check actual code changes, not just file names.

If conflicts detected: Do NOT auto-merge. Understand which fix is correct. May need sequential re-investigation.

**Step 4: Run full test suite**

Execute the complete test suite to verify all fixes work together without regressions. An agent reporting "it's fixed" is not the same as integrated verification -- the full suite catches cross-subsystem regressions that individual agents cannot see.

**Step 5: Spot-check at least one fix**

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

### Error: "Agent Commits to Wrong Branch"
Cause: Agent creates its own branch (ignoring convergence protocol) or worktree diverges from target.
Solution (ADR-093 -- Branch Convergence):
1. Orchestrator creates the target branch BEFORE dispatching agents (Phase 2, Step 0)
2. Each agent prompt explicitly states `Work on branch: {name}. Do NOT create a new branch.`
3. Each agent runs `git branch --show-current` as first step to verify correct branch
4. After all agents return, Phase 3 Step 1 verifies convergence
5. If a commit landed on the wrong branch, cherry-pick to the target and delete the rogue branch
*Graduated from learning.db -- multi-agent-coordination/worktree-branch-confusion. Superseded by ADR-093.*

---

## References

- `skills/_shared-patterns/fan-out-dispatch.md` -- Canonical fan-out/fan-in dispatch pattern (shared across parallel skills)
- `scripts/check-scope-overlap.py` -- Deterministic scope overlap checker for parallel task dispatch
- `pipelines/systematic-debugging/SKILL.md` -- Use instead for single complex bugs or related failures
- `skills/workflow-orchestrator/SKILL.md` -- Use instead for planning implementation work
- `skills/subagent-driven-development/SKILL.md` -- Use instead for sequential dependent tasks
