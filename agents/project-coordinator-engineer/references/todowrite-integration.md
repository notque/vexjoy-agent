# TodoWrite Integration Reference

> **Scope**: TodoWrite patterns for multi-agent coordination — task structure, dependencies, and completion verification.
> **Version range**: Claude Code TodoWrite system (all versions)
> **Generated**: 2026-04-09

---

## Overview

TodoWrite tracks agent task ownership, dependencies, and completion. Keep TodoWrite synchronized with STATUS.md and PROGRESS.md — a task marked `completed` in TodoWrite but not in STATUS.md creates phantom progress.

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

---

### Completion Verification Before Status Update

Never mark `completed` based on agent claim alone — verify with success criteria first.

```markdown
Verification sequence:
1. Agent reports: "Phase 1 complete, schema.sql created"
2. VERIFY: ls -la schema.sql  (file must exist)
3. VERIFY: python3 -c "import json; open('schema.sql')"
4. VERIFY: SUCCESS CRITERIA from HANDOFF.md all pass
5. ONLY THEN: Update TodoWrite to completed
6. THEN: Update STATUS.md
7. THEN: Update PROGRESS.md if context >70%
```

---

### Parallel Task Structure

For parallel tasks, assign non-overlapping file domains.

```markdown
Task: "Phase 4: Integration tests (parallel)"
  id: phase-4-tests
  status: in_progress
  blockedBy: phase-3-api
  parallel_agents:
    - agent: nodejs-api-engineer
      files: tests/integration/api/*.test.js
      id: phase-4a-api-tests
    - agent: python-general-engineer
      files: tests/integration/models/*.test.py
      id: phase-4b-model-tests
```

File domains MUST NOT overlap. If they do, serialize instead.

---

## Pattern Catalog
<!-- no-pair-required: section header, not an individual anti-pattern -->

### Verify Before Marking Complete

**Detection**:
```bash
grep -B5 "completed" todo*.md 2>/dev/null | grep -v "VERIFY\|exits 0\|tests pass"
```

**Preferred action**: Run success criteria from HANDOFF.md before updating status. Every `completed` transition must include verification evidence:
```markdown
Task: "Implement user endpoint"
  status: completed
  verified: npm test src/routes/users.test.js → exit 0, 12 tests passed
```

---

### Declare blockedBy on Every Dependent Task

**Detection**:
```bash
grep -B2 "Phase [2-9]\|depends on\|requires" todo*.md 2>/dev/null | grep -v "blockedBy"
```

**Preferred action**: Add `blockedBy: {prior-task-id}` to every task that reads output from a prior task.

---

### Split Multi-Agent Work into Per-Agent Tasks

**Detection**:
```bash
grep -A5 "assigned:" todo*.md 2>/dev/null | grep -E "assigned:.*,.*,"
```

**Preferred action**: Split into `parallel_agents` subtasks with own file domain, id, and success criteria. Each agent's retry count tracks independently.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Phase N+1 dispatched before Phase N output | Missing `blockedBy` | Add `blockedBy: phase-N-id` |
| Task `completed` but next agent reports missing files | Premature completion | Require verification before `completed` |
| Two agents edit conflicting files | Multi-agent single task | Split into parallel_agents with non-overlapping domains |
| Can't determine which tasks are ready | No dependency chain | Rebuild TodoWrite with explicit `blockedBy` |
| Fresh agent re-does completed tasks | TodoWrite not synced with PROGRESS.md | Update PROGRESS.md with TodoWrite completed list |

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
- `preferred-patterns.md` — Parallel execution and file domain conflict patterns
