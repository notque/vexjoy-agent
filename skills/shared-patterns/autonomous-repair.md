# Autonomous Repair Pattern

Bounded self-repair for task execution failures. When a task fails verification, select a repair strategy and retry within a strict budget — then escalate to the user if repair doesn't resolve it.

## When to Use

- A task within a pipeline or orchestrated workflow fails its verification step
- The failure has a specific error message or output to act on
- You have remaining repair budget (default: 2 attempts per task)

## When NOT to Use

- The failure is architectural or strategic (wrong approach entirely) — ESCALATE immediately
- The user explicitly asked you to stop on failure
- You're outside an orchestrated workflow (ad-hoc single edits don't need formal repair)

## The Four Strategies

### 1. RETRY

Try again with a targeted fix that addresses the specific error.

**When to use:** Error is specific and actionable — typo, missing import, wrong function signature, dependency not installed, syntax error.

**Rules:**
- The retry MUST include error context from the failed attempt. A retry without error context repeats the same mistake.
- Each RETRY consumes 1 repair attempt from the budget.
- If the same error recurs after retry, do NOT retry again with the same fix. Move to DECOMPOSE or ESCALATE.

**Example:**
```
Task: Add validation to user input handler
Verification: `python3 -m pytest tests/test_validation.py` exits 0
Failure: ImportError: No module named 'pydantic'
Strategy: RETRY — install missing dependency, re-run
```

### 2. DECOMPOSE

Break the failed task into smaller sub-tasks and execute them individually.

**When to use:** Task was too large or had hidden dependencies that surfaced during execution. A RETRY already failed, and the task has independently separable parts.

**Rules:**
- Decomposed sub-tasks are **in-memory only**. NEVER modify the original plan file on disk. The plan file represents user-approved scope; decomposition is an execution-level adaptation.
- DECOMPOSE consumes 1 repair attempt for the decomposition itself.
- Each sub-task gets its own budget of 1 attempt. If a sub-task fails, it escalates — no recursive decomposition.
- Log every decomposition as a deviation in the execution summary.

**Example:**
```
Task: Refactor auth module with new token format
RETRY failed: Multiple intertwined issues (token generation + validation + storage)
Strategy: DECOMPOSE into:
  - Sub-task A: Update token generation (budget: 1)
  - Sub-task B: Update token validation (budget: 1)
  - Sub-task C: Update token storage (budget: 1)
```

### 3. PRUNE

Skip the task entirely with documented justification.

**When to use:** Task is genuinely unnecessary (solved by a prior task), blocked by external factors (service is down), or optional given the overall goal.

**Rules:**
- PRUNE consumes 0 repair attempts (it's a resolution, not a retry).
- Requires explicit justification recorded in the execution summary.
- "Couldn't figure it out" is NOT a valid prune justification — that's an ESCALATE.
- The justification must explain why the task's goal is already met or why skipping it doesn't compromise the workflow.

**Example:**
```
Task: Add index on users.email column
Justification: T2 already created a unique constraint on users.email, which implicitly creates an index.
Strategy: PRUNE — objective already satisfied by T2
```

### 4. ESCALATE

Ask the user. This is the mandatory terminal strategy.

**When to use:** Architectural mismatch, ambiguous requirements, budget exhausted, or DECOMPOSE sub-tasks also failed.

**Rules:**
- ESCALATE consumes 0 repair attempts (it's a termination, not a retry).
- ESCALATE is **mandatory** when repair budget is exhausted. No exceptions, no rationalization.
- Present the user with: what failed, what was tried, and specific options for how to proceed.

**Example:**
```
Task: Migrate database schema to support multi-tenancy
Budget: Exhausted (2/2 attempts used)
Tried: RETRY (wrong column type), DECOMPOSE (sub-tasks had circular dependencies)
Strategy: ESCALATE — present failure summary and ask user for direction
```

## Strategy Selection Decision Tree

```
Task fails verification
  |
  +-- Error is specific and actionable? (typo, missing import, wrong arg)
  |     \-- YES --> RETRY with targeted fix
  |         \-- Retry also fails?
  |             +-- Task is decomposable? (multiple independent parts)
  |             |     \-- YES --> DECOMPOSE into sub-tasks
  |             |         \-- Sub-tasks also fail? --> ESCALATE
  |             +-- Task is genuinely optional or already satisfied?
  |             |     \-- YES --> PRUNE with justification
  |             \-- Otherwise --> ESCALATE
  |
  +-- Error is vague or systemic? (architectural mismatch, wrong approach)
  |     \-- ESCALATE immediately (don't waste budget on strategic errors)
  |
  \-- Budget exhausted?
        \-- ESCALATE (mandatory, no exceptions)
```

## Repair Budget

**Default: 2 repair attempts per task.**

| Strategy | Budget Cost | Notes |
|----------|-----------|-------|
| RETRY | 1 attempt | Must include error context |
| DECOMPOSE | 1 attempt | Sub-tasks get 1 attempt each |
| PRUNE | 0 attempts | Resolution, not retry |
| ESCALATE | 0 attempts | Termination, not retry |

After budget exhaustion, ESCALATE is mandatory. No strategy selection, no exceptions.

**Why 2?** Most fixable errors resolve in 1-2 attempts. Higher budgets waste context on unrecoverable failures. Lower budgets escalate too aggressively, defeating the purpose of autonomous repair.

## Deviation Logging

Every repair action MUST be logged in the execution summary. This creates an audit trail of autonomous decisions made without user input.

**Log format:**

```markdown
## Repair Deviations

| Task | Strategy | Error | Outcome | Attempts Used |
|------|----------|-------|---------|---------------|
| T3: Add input validation | RETRY | ImportError: pydantic | Resolved — installed dep | 1 |
| T5: Refactor auth module | DECOMPOSE | Multiple intertwined failures | Resolved — 3 sub-tasks | 1 (+3 sub-task attempts) |
| T7: Add email index | PRUNE | N/A — already satisfied by T2 | Skipped | 0 |
| T9: Multi-tenant migration | ESCALATE | Schema conflict | User decision needed | 2 (budget exhausted) |
```

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "One more retry should fix it" | Budget exists to prevent infinite loops | ESCALATE when budget is exhausted |
| "I'll just skip this, it's probably fine" | PRUNE requires justification that the goal is met | Provide explicit justification or ESCALATE |
| "The error is vague but I'll try anyway" | Vague/systemic errors don't respond to targeted fixes | ESCALATE immediately on architectural mismatches |
| "I'll modify the plan to remove this task" | Plan file is user-approved scope | PRUNE in-memory only, never edit the plan file |
| "Sub-tasks need more attempts" | Recursive retry loops waste context exponentially | Sub-tasks get 1 attempt each, then ESCALATE |
| "This decomposition needs decomposition" | Recursive decomposition is unbounded | ESCALATE if sub-tasks fail — no nested decomposition |

## Related Patterns

- [Gate Enforcement](./gate-enforcement.md) — repair happens within the IMPLEMENT-to-VERIFY gate loop
- [Blocker Criteria](./blocker-criteria.md) — ESCALATE aligns with blocker handling (stop and ask)
- [Anti-Rationalization Core](./anti-rationalization-core.md) — prevents rationalizing past budget limits
- [Analysis Paralysis Guard](./analysis-paralysis-guard.md) — prevents unbounded exploration during RETRY/DECOMPOSE
