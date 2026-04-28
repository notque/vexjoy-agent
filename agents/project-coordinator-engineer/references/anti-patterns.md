# Coordination Preferred Patterns
<!-- no-pair-required: file header, not an individual pattern -->

> **Scope**: Correct multi-agent coordination patterns — what to do, why it works, and how to detect violations.
> **Version range**: Claude Code multi-agent workflows (all versions)
> **Generated**: 2026-04-09

---

## Overview

Coordination failures fall into three categories: delegation failures (ambiguous task specs), workspace failures (file domain conflicts), and death loop enablers (retry without strategy change). The most expensive category is delegation failures — they produce plausible-looking output that fails during integration, requiring a second coordination round.

---

## Pattern Catalog
<!-- no-pair-required: section header, not an individual pattern -->

### Write Executable Success Criteria for Every Task

Every TASK block must answer three questions: which file, which agent, and what command proves it worked. Write specific commands that exit 0 on success, observable behavior changes, and explicit file domain boundaries. "Make sure it works" is unverifiable -- the agent cannot confirm success and the coordinator cannot confirm handoff completion.

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

**Why this matters**: Vague criteria ("make sure it works") create ambiguity about when to advance to the next phase. This causes coordination stalls (waiting for confirmation that never comes) or premature integration (declaring success without evidence).

**Detection**:
```bash
# TASK blocks without measurable success criteria
grep -A5 "TASK:" HANDOFF.md | grep -v "SUCCESS CRITERIA\|exits 0\|must pass\|verified"
```

---

### Assign Each File to Exactly One Agent

Before parallel dispatch, run the detection command to verify no file path appears in two agent domains. When a file must be touched by two agents, assign ownership to one and serialize the agents -- the dependent agent runs second.

```markdown
AGENT A: python-general-engineer
FILES: src/models.py, src/api.py

AGENT B: data-engineer
FILES: src/utils.py, src/pipeline.py, src/transformers.py

SEQUENCING NOTE: Agent A depends on Agent B's utils.py changes.
  Execute in order: B first, A second. No parallel execution.
```

**Why this matters**: Two agents editing the same file concurrently produce merge conflicts at integration. Neither agent's changes are complete in isolation, and the combined output is non-deterministic. The common outcome: Agent B's changes silently overwrite Agent A's without awareness.

**Detection**:
```bash
# Duplicate file paths across concurrent agent tasks
grep "FILE DOMAIN\|Assigned files" STATUS.md | sort | uniq -d
# Any duplicate = domain conflict. Resolve before dispatch.
```

---

### Require Root Cause Analysis Before Every Retry

Before writing a retry HANDOFF, identify the root cause from Attempt 1's error output and document a concrete strategy change. The HANDOFF must answer: "What is different this time?" If the answer is nothing, stop and escalate to the user rather than retry.

```markdown
HANDOFF (Attempt 2 — STRATEGY CHANGED):
  Attempt 1 failure root cause: `psycopg2.OperationalError` — migrations running before
  database connection is established in CI environment.

  NEW APPROACH: Add `SELECT 1` connection check before migration script.
  If connection fails, retry 3x with 2s backoff before raising error.

  File: migrations/001_add_user_preferences.py
  Change: Add connection health check at lines 12-18 (see BLOCKERS.md for detail)
```

**Why this matters**: Retrying with the same context, same constraints, and no new information produces the same failure. This is wasted budget disguised as coordination effort. The agent has no reason to succeed when nothing has changed.

**Detection**:
```bash
# Retry entries without documented strategy change
grep -A10 "RETRY\|ATTEMPT 2\|ATTEMPT 3" HANDOFF.md | grep -v "NEW STRATEGY\|Root cause\|Changed approach"
```

---

### Serialize Tasks That Depend on Each Other's Output

Map the dependency chain before dispatch. Any task whose input is another task's output must be in a later phase, not a parallel one. Gate each phase on a verifiable output artifact.

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

**Why this matters**: When dependent tasks run in parallel, the dependent agent starts without its input artifact. It generates speculative output that does not match the actual artifact produced by the upstream agent. Integration requires a complete rewrite of the downstream work.

**Detection**:
```bash
# Parallel tasks with dependency keywords (mis-scheduled as concurrent)
grep -B2 -A10 "PARALLEL\|concurrent" HANDOFF.md | grep "depends\|requires\|after\|output of"
```

---

### Write PROGRESS.md at 70% Context Capacity

Track context usage throughout the session. At 70% capacity, write PROGRESS.md covering completed phases, output artifacts, and modified files before spawning any new agent. A fresh agent with PROGRESS.md can resume accurately; one without it will either repeat work or invent a false prior state.

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

**Why this matters**: Agent context does not persist across spawns. "Continue from where we left off" is meaningless to a fresh agent -- it has no memory of prior phases, no record of completed work, and no list of modified files. Without PROGRESS.md, the new agent either repeats completed work or fabricates a prior state.

**Detection**:
```bash
# Check if PROGRESS.md exists (required for multi-phase projects)
ls -la PROGRESS.md 2>/dev/null || echo "MISSING: No PROGRESS.md found"
```

---

### Dispatch Specialists, Never Do Agent Work as Coordinator

Coordinators dispatch; specialists implement. When the coordinator identifies a specific fix, it writes that fix as a precise instruction in HANDOFF.md and dispatches the appropriate specialist. The coordinator's tools are Agent, Read, Glob, and Grep only -- never Edit, Write, or Bash for implementation.

**Why this matters**: The coordinator loses its orchestration perspective when it drops into implementation. It cannot simultaneously track project state and debug a specific file. It also bypasses the specialized agent's domain knowledge, producing lower-quality fixes that miss domain-specific edge cases.

**Detection**:
```bash
# Coordinator directly editing files instead of dispatching
grep -n "Edit\|Write\|Bash" coordinator-log.md 2>/dev/null
# Coordinator should only use Agent, Read, Glob, Grep
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Integration produces merge conflicts | Overlapping file domains in parallel phase | Audit file assignments before parallel dispatch; enforce non-overlapping |
| Agent B starts with wrong assumptions about Agent A's output | Parallel execution of sequential tasks | Map dependency chain; enforce gates between phases |
| Task marked complete but tests still failing | Vague success criteria | Add executable verification commands to every TASK block |
| Fresh agent repeats completed work | No PROGRESS.md before context handoff | Write PROGRESS.md at 70% context; include completed phases and modified files |
| Same error in 3 HANDOFF.md entries | Retry without strategy change | Require root cause analysis in BLOCKERS.md before any retry |
| Coordinator cannot verify which phase is current | No STATUS.md after agent completions | Update STATUS.md after every agent task completion |

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
