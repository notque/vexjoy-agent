# TodoWrite Integration Reference

> **Scope**: Patterns for using TodoWrite with multi-agent coordination — task structure, agent assignments, dependency tracking, and completion verification.
> **Version range**: Claude Code TodoWrite system (all versions)
> **Generated**: 2026-04-09

---

## Overview

TodoWrite is the coordinator's task registry — it tracks which agents own which tasks, what dependencies exist between tasks, and which tasks are complete. The critical discipline is keeping the TodoWrite list synchronized with STATUS.md and PROGRESS.md. A task marked `completed` in TodoWrite but not reflected in STATUS.md creates phantom progress that misleads fresh agents.

---

## Pattern Table

| State | TodoWrite Status | STATUS.md Entry | Trigger |
|-------|-----------------|-----------------|---------|
| Task not started | `pending` | Not listed | Initial setup |
| Agent assigned | `in_progress` | Active with attempt count | On dispatch |
| Agent completed | `completed` | Phase marked done | On verified success |
| Agent blocked | `in_progress` | Blocked section | After 3/3 FAILED + BLOCKERS.md |
| Task cancelled | Remove from list | Update phase status | After root cause changes strategy |

---

## Correct Patterns

### Agent Assignment with Dependencies

Structure each task with explicit `blockedBy` when it depends on prior output.

```markdown
TodoWrite tasks for a 3-phase project:

Task: "Phase 1: Generate database schema"
  id: phase-1-schema
  status: in_progress
  assigned: database-engineer
  output: schema.sql

Task: "Phase 2: ORM models"
  id: phase-2-models
  status: pending
  blockedBy: phase-1-schema
  assigned: python-general-engineer
  output: src/models/*.py

Task: "Phase 3: API endpoints"
  id: phase-3-api
  status: pending
  blockedBy: phase-2-models
  assigned: nodejs-api-engineer
  output: src/routes/*.js

Task: "Phase 4: Integration tests"
  id: phase-4-tests
  status: pending
  blockedBy: phase-3-api
  assigned: nodejs-api-engineer, python-general-engineer (parallel)
  output: tests/integration/*
```

**Why**: The `blockedBy` chain makes the execution order explicit. The coordinator can read the TodoWrite list to determine which tasks are ready to dispatch — any task whose blockedBy tasks are all `completed` is ready.

---

### Completion Verification Before Status Update

Never mark a task `completed` based on agent claim alone — verify with the success criteria before updating TodoWrite.

```markdown
Verification sequence before marking completed:

1. Agent reports: "Phase 1 complete, schema.sql created"
2. VERIFY: ls -la schema.sql  (file must exist)
3. VERIFY: python3 -c "import json; open('schema.sql')"  (or language-specific check)
4. VERIFY: SUCCESS CRITERIA from HANDOFF.md all pass
5. ONLY THEN: Update TodoWrite task phase-1-schema to completed
6. THEN: Update STATUS.md completed phases list
7. THEN: Update PROGRESS.md if context >70%
```

**Why**: Agents sometimes report completion when they have only partially completed work. Premature `completed` status causes Phase 2 to start before its dependency is actually ready, producing "file not found" errors that cost another retry cycle.

---

### Parallel Task Structure

For tasks that can safely run in parallel, assign multiple agents with non-overlapping file domains.

```markdown
Task: "Phase 4: Integration tests (parallel)"
  id: phase-4-tests
  status: in_progress
  blockedBy: phase-3-api  (must be completed before this starts)
  parallel_agents:
    - agent: nodejs-api-engineer
      files: tests/integration/api/*.test.js
      id: phase-4a-api-tests
    - agent: python-general-engineer
      files: tests/integration/models/*.test.py
      id: phase-4b-model-tests
```

File domains MUST NOT overlap. If they do, serialize instead of parallelizing.

---

## Anti-Pattern Catalog

### ❌ Marking Complete Before Verification

**Detection**:
```bash
# Look for completed status updates without a verification step in notes
grep -B5 "completed" todo*.md 2>/dev/null | grep -v "VERIFY\|exits 0\|tests pass"
# Any completed entry without verification evidence is premature
```

**What it looks like**:
```markdown
Task: "Implement user endpoint"
  status: completed  ← marked complete based on agent message alone
  note: "Agent said it was done"
```

**Why wrong**: Agent self-report is not evidence of completion. The agent may have hit a timeout, written partial output, or misread a test result. Premature `completed` causes the next dependent task to start with missing inputs.

**Fix**: Every `completed` transition must include a verification command result:
```markdown
Task: "Implement user endpoint"
  status: completed
  verified: npm test src/routes/users.test.js → exit 0, 12 tests passed
```

---

### ❌ Missing blockedBy on Dependent Tasks

**Detection**:
```bash
# Find tasks that reference prior phases in their description but have no blockedBy
grep -B2 "Phase [2-9]\|depends on\|requires" todo*.md 2>/dev/null | grep -v "blockedBy"
```

**What it looks like**:
```markdown
Task: "Phase 2: Write ORM models using the schema"
  status: pending
  # No blockedBy — can be accidentally dispatched before Phase 1 completes
```

**Why wrong**: Without `blockedBy`, the coordinator has no automated signal to wait. In multi-session or parallel scenarios, a fresh coordinator agent may dispatch Phase 2 before Phase 1's output exists.

**Fix**: Every task that consumes prior output must declare `blockedBy: {prior-task-id}`.

---

### ❌ Single Task Spanning Multiple Agents

**Detection**:
```bash
# Find tasks with multiple agents assigned without parallel structure
grep -A5 "assigned:" todo*.md 2>/dev/null | grep -E "assigned:.*,.*,"
# Multiple agent assignments to one task without parallel_agents structure = ambiguous ownership
```

**What it looks like**:
```markdown
Task: "Implement and test the API"
  assigned: nodejs-api-engineer, python-general-engineer, database-engineer
  # Who owns what? What happens if one fails?
```

**Why wrong**: Single-task multi-agent assignment has no file domain boundaries, no independent completion criteria, and no retry tracking per agent. If one agent fails, the entire task fails with no clear path to recovery.

**Fix**: Split into per-agent tasks with explicit file domains and independent completion criteria.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Phase N+1 dispatched before Phase N output exists | Missing `blockedBy` on Phase N+1 task | Add `blockedBy: phase-N-id` to all dependent tasks |
| Task marked `completed` but next agent reports missing files | Premature completion without verification | Require verification command result before any `completed` status change |
| Two agents edit conflicting files | Multi-agent assignment to single task without parallel structure | Split into parallel_agents subtasks with non-overlapping file domains |
| Coordinator cannot determine which tasks are ready | No clear dependency chain | Rebuild TodoWrite with explicit `blockedBy` for every inter-phase dependency |
| Fresh agent re-does completed tasks | TodoWrite not synced with PROGRESS.md | Update PROGRESS.md to include TodoWrite `completed` task list |

---

## Detection Commands Reference

```bash
# Find tasks without blockedBy that reference prior phases
grep -B2 "Phase [2-9]\|depends on\|requires" todo*.md 2>/dev/null | grep -v "blockedBy"

# Find completed tasks without verification evidence
grep -B5 "completed" todo*.md 2>/dev/null | grep -v "VERIFY\|exits 0\|tests pass\|verified:"

# Check for multi-agent single-task assignments (ambiguous ownership)
grep -A5 "assigned:" todo*.md 2>/dev/null | grep -E "assigned:.*,.*,"

# Verify TodoWrite completed count matches PROGRESS.md completed phases
echo "TodoWrite completed tasks:" && grep -c "status: completed" todo*.md 2>/dev/null
echo "PROGRESS.md completed phases:" && grep -c "\[x\]" PROGRESS.md 2>/dev/null
```

---

## See Also

- `communication-protocols.md` — PROGRESS.md and STATUS.md sync patterns
- `anti-patterns.md` — Parallel execution and file domain conflict patterns
