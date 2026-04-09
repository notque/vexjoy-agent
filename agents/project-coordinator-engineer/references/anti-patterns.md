# Coordination Anti-Patterns Reference

> **Scope**: Common multi-agent coordination mistakes — what they look like, why they fail, and the corrected pattern.
> **Version range**: Claude Code multi-agent workflows (all versions)
> **Generated**: 2026-04-09

---

## Overview

Coordination anti-patterns fall into three categories: delegation failures (ambiguous task specs), workspace failures (file domain conflicts), and death loop enablers (retry without strategy change). The most expensive category is delegation failures — they produce plausible-looking output that fails during integration, requiring a second coordination round.

---

## Anti-Pattern Catalog

### ❌ Vague Success Criteria

**Detection**:
```bash
# In HANDOFF.md files — look for tasks without measurable success criteria
grep -A5 "TASK:" HANDOFF.md | grep -v "SUCCESS CRITERIA\|exits 0\|must pass\|verified"
# Any TASK: block without a SUCCESS CRITERIA: line is at risk
```

**What it looks like**:
```markdown
TASK: Fix the authentication module
AGENT: nodejs-api-engineer
SUCCESS: Make sure it works
```

**Why wrong**: "Make sure it works" is unverifiable. The agent cannot confirm it succeeded; the coordinator cannot confirm the handoff is complete. This creates ambiguity about when to move to the next phase, causing coordination stalls or premature integration.

**Fix**:
```markdown
TASK: Fix JWT token expiry handling in src/auth/middleware.js
AGENT: nodejs-api-engineer
FILE DOMAIN: src/auth/middleware.js ONLY
SUCCESS CRITERIA:
  1. `npm test src/auth/middleware.test.js` exits 0
  2. Expired tokens return HTTP 401 (not 500)
  3. Valid tokens pass through without error
OUTPUT FORMAT: Modified middleware.js + test run output
```

---

### ❌ Overlapping File Domains

**Detection**:
```bash
# Compare file assignments across concurrent agent tasks in STATUS.md
grep "FILE DOMAIN\|Assigned files" STATUS.md | sort | uniq -d
# Duplicate file paths mean two agents share a domain — conflict waiting to happen
```

**What it looks like**:
```markdown
AGENT A: python-general-engineer
FILES: src/models.py, src/utils.py, src/api.py

AGENT B: data-engineer
FILES: src/utils.py, src/pipeline.py, src/transformers.py
# src/utils.py is in BOTH domains — conflict
```

**Why wrong**: Two agents editing the same file concurrently produce merge conflicts at integration. Neither agent's changes are complete in isolation, and combined output is non-deterministic. Common outcome: Agent B's changes overwrite Agent A's without awareness.

**Fix**:
```markdown
AGENT A: python-general-engineer
FILES: src/models.py, src/api.py  ← utils.py REMOVED

AGENT B: data-engineer
FILES: src/utils.py, src/pipeline.py, src/transformers.py  ← owns utils.py

SEQUENCING NOTE: Agent A depends on Agent B's utils.py changes.
  Execute in order: B first, A second. No parallel execution.
```

---

### ❌ Retry Without Root Cause (Retry Theater)

**Detection**:
```bash
# Look for HANDOFF entries that repeat task description without new strategy
grep -A10 "RETRY\|ATTEMPT 2\|ATTEMPT 3" HANDOFF.md | grep -v "NEW STRATEGY\|Root cause\|Changed approach"
# Retry entries without strategy change documentation are retry theater
```

**What it looks like**:
```markdown
HANDOFF (Attempt 2):
  Previous attempt failed. Please try again to implement the database migration.
  The migration should add the user_preferences column.
```

**Why wrong**: The agent has the same context, the same constraints, and no new information. The expected outcome is identical to Attempt 1. This is wasted budget disguised as coordination effort.

**Fix**:
```markdown
HANDOFF (Attempt 2 — STRATEGY CHANGED):
  Attempt 1 failure root cause: `psycopg2.OperationalError` — migrations running before
  database connection is established in CI environment.

  NEW APPROACH: Add `SELECT 1` connection check before migration script.
  If connection fails, retry 3x with 2s backoff before raising error.

  File: migrations/001_add_user_preferences.py
  Change: Add connection health check at lines 12-18 (see BLOCKERS.md for detail)
```

---

### ❌ Parallel Execution of Dependent Tasks

**Detection**:
```bash
# Look for tasks marked PARALLEL that reference each other's output
grep -B2 -A10 "PARALLEL\|concurrent" HANDOFF.md | grep "depends\|requires\|after\|output of"
# Any parallel task that depends on another parallel task's output is mis-scheduled
```

**What it looks like**:
```markdown
PHASE 2 (parallel execution):
  Agent A: Generate database schema → schema.sql
  Agent B: Write ORM models (requires schema.sql from Agent A)
  Agent C: Write API endpoints (requires ORM models from Agent B)
  # All three marked as parallel — B and C will fail
```

**Why wrong**: Agent B and C will start before Agent A completes. Without schema.sql, Agent B generates speculative models. Agent C's endpoints reference models that don't match the final schema. Integration requires a complete rewrite of B and C.

**Fix**:
```markdown
PHASE 2A (Agent A only):
  Agent A: Generate database schema → schema.sql
  GATE: Proceed to 2B only when schema.sql exists and validates

PHASE 2B (Agent B only):
  Agent B: Write ORM models using schema.sql
  DEPENDENCY: Phase 2A complete
  GATE: Proceed to 2C only when models pass `python3 -m pytest tests/models/`

PHASE 2C (Agent C only):
  Agent C: Write API endpoints using ORM models
  DEPENDENCY: Phase 2B complete
```

---

### ❌ Context Compression Without PROGRESS.md

**Detection**:
```bash
# Verify PROGRESS.md exists and was updated before any context summary event
ls -la PROGRESS.md 2>/dev/null || echo "MISSING: No PROGRESS.md found"
# If missing and coordination is multi-phase, context loss has already occurred
```

**What it looks like**:
```markdown
[No PROGRESS.md exists]
[Coordinator is at 75% context capacity]
[Coordinator spawns new agent with "continue from where we left off"]
# New agent has no record of what phases completed, what files were changed
```

**Why wrong**: Agent context does not persist across spawns. "Continue from where we left off" is meaningless to a fresh agent — it has no memory of prior phases, no record of completed work, and no list of modified files. It will either repeat completed work or invent a fabricated prior state.

**Fix**:
```markdown
# At 70% context capacity, write PROGRESS.md BEFORE spawning any new agent:

# PROGRESS.md template:
## Project State — 2026-04-09 14:30

### Completed Phases
- [x] Phase 1: Database schema (schema.sql) — golang-general-engineer — DONE
- [x] Phase 2: ORM models (src/models/) — python-general-engineer — DONE

### Modified Files
- schema.sql (created)
- src/models/user.py (created)
- src/models/preferences.py (created)

### In Progress
- Phase 3: API endpoints — not started

### Pending Decisions
- Pagination strategy for /api/users endpoint (ask user)
```

---

### ❌ Coordinator Doing Agent Work

**Detection**:
```bash
# Look for the coordinator directly editing files instead of dispatching
grep -n "Edit\|Write\|Bash" coordinator-log.md 2>/dev/null
# Coordinator should only use Agent, Read, Glob, Grep — not file-modifying tools
```

**What it looks like**:
```markdown
[Coordinator reads a failing test]
[Coordinator directly edits src/auth.py to fix the test]
[Coordinator marks task complete without verification by the assigned agent]
```

**Why wrong**: The coordinator loses its orchestration perspective when it drops into implementation. It cannot simultaneously track project state and debug a specific file. It also bypasses the specialized agent's domain knowledge, producing lower-quality fixes.

**Fix**: Coordinators dispatch. Specialists implement. If the coordinator identifies a specific fix, it writes the fix as a precise instruction in HANDOFF.md and dispatches the appropriate specialist to execute it.

---

## Error-Fix Mappings

| Symptom | Root Cause Anti-Pattern | Fix |
|---------|------------------------|-----|
| Integration phase produces merge conflicts | Overlapping file domains in parallel phase | Audit file assignments before parallel dispatch; enforce non-overlapping |
| Agent B starts with wrong assumptions about Agent A's output | Parallel execution of sequential tasks | Map dependency chain; enforce gates between phases |
| Task marked complete but tests still failing | Vague success criteria | Add executable verification commands to every TASK: block |
| Fresh agent repeats completed work | No PROGRESS.md before context summary | Write PROGRESS.md at 70% context; include completed phases and modified files |
| Same error in 3 HANDOFF.md entries | Retry theater (no strategy change) | Require root cause analysis in BLOCKERS.md before any retry |
| Coordinator cannot verify which phase is current | No STATUS.md after agent completions | Update STATUS.md after every agent task completion — mandatory |

---

## Detection Commands Reference

```bash
# Find TASK blocks without SUCCESS CRITERIA
grep -A5 "TASK:" HANDOFF.md | grep -v "SUCCESS CRITERIA\|exits 0\|must pass"

# Detect overlapping file domains across agents
grep "FILE DOMAIN\|Assigned files" STATUS.md | sort | uniq -d

# Detect retry entries without strategy change
grep -A10 "RETRY\|ATTEMPT [23]" HANDOFF.md | grep -v "NEW STRATEGY\|Root cause"

# Check if PROGRESS.md exists (required for multi-phase projects)
ls -la PROGRESS.md 2>/dev/null || echo "MISSING"

# Find parallel tasks with dependency keywords (sequential tasks mis-labeled as parallel)
grep -B2 -A10 "PARALLEL\|concurrent" HANDOFF.md | grep "depends\|requires\|after\|output of"
```

---

## See Also

- `death-loop-prevention.md` — Retry loop detection and recovery patterns
- `communication-protocols.md` — STATUS.md, HANDOFF.md, BLOCKERS.md templates
