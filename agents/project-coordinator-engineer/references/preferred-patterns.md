# Coordination Preferred Patterns
<!-- no-pair-required: file header, not an individual pattern -->

> **Scope**: Multi-agent coordination patterns — delegation, workspace, and death loop prevention.
> **Version range**: Claude Code multi-agent workflows (all versions)
> **Generated**: 2026-04-09

---

## Pattern Catalog
<!-- no-pair-required: section header, not an individual pattern -->

### Write Executable Success Criteria for Every Task

Every TASK block must specify: which file, which agent, and what command proves success. "Make sure it works" is unverifiable.

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

**Detection**:
```bash
grep -A5 "TASK:" HANDOFF.md | grep -v "SUCCESS CRITERIA\|exits 0\|must pass\|verified"
```

---

### Assign Each File to Exactly One Agent

Before parallel dispatch, verify no file path appears in two agent domains. When a file must be touched by two agents, serialize them.

```markdown
AGENT A: python-general-engineer
FILES: src/models.py, src/api.py

AGENT B: data-engineer
FILES: src/utils.py, src/pipeline.py, src/transformers.py

SEQUENCING NOTE: Agent A depends on Agent B's utils.py changes.
  Execute in order: B first, A second. No parallel execution.
```

**Detection**:
```bash
grep "FILE DOMAIN\|Assigned files" STATUS.md | sort | uniq -d
```

---

### Require Root Cause Analysis Before Every Retry

Before writing a retry HANDOFF, identify the root cause and document a concrete strategy change. If nothing changed, escalate to the user.

```markdown
HANDOFF (Attempt 2 — STRATEGY CHANGED):
  Attempt 1 failure root cause: `psycopg2.OperationalError` — migrations running before
  database connection is established in CI environment.

  NEW APPROACH: Add `SELECT 1` connection check before migration script.
  If connection fails, retry 3x with 2s backoff before raising error.

  File: migrations/001_add_user_preferences.py
  Change: Add connection health check at lines 12-18 (see BLOCKERS.md for detail)
```

**Detection**:
```bash
grep -A10 "RETRY\|ATTEMPT 2\|ATTEMPT 3" HANDOFF.md | grep -v "NEW STRATEGY\|Root cause\|Changed approach"
```

---

### Serialize Tasks That Depend on Each Other's Output

Map the dependency chain before dispatch. Gate each phase on a verifiable output artifact.

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

**Detection**:
```bash
grep -B2 -A10 "PARALLEL\|concurrent" HANDOFF.md | grep "depends\|requires\|after\|output of"
```

---

### Write PROGRESS.md at 70% Context Capacity

At 70% capacity, write PROGRESS.md covering completed phases, output artifacts, and modified files before spawning any new agent.

```markdown
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

**Detection**:
```bash
ls -la PROGRESS.md 2>/dev/null || echo "MISSING: No PROGRESS.md found"
```

---

### Dispatch Specialists, Never Do Agent Work as Coordinator

Coordinators dispatch; specialists implement. Coordinator tools: Agent, Read, Glob, Grep only — never Edit, Write, or Bash for implementation.

**Detection**:
```bash
grep -n "Edit\|Write\|Bash" coordinator-log.md 2>/dev/null
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Merge conflicts at integration | Overlapping file domains | Audit file assignments before parallel dispatch |
| Agent B starts with wrong assumptions | Parallel execution of sequential tasks | Map dependency chain; enforce gates between phases |
| Task marked complete but tests failing | Vague success criteria | Add executable verification commands to every TASK block |
| Fresh agent repeats completed work | No PROGRESS.md | Write PROGRESS.md at 70% context |
| Same error in 3 HANDOFF entries | Retry without strategy change | Require root cause analysis before retry |
| Coordinator can't verify current phase | No STATUS.md updates | Update STATUS.md after every agent task completion |

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
