# Communication Protocols Reference

> **Scope**: Structural templates for STATUS.md, HANDOFF.md, PROGRESS.md, and BLOCKERS.md in multi-agent coordination.
> **Version range**: Claude Code multi-agent workflows (all versions)
> **Generated**: 2026-04-09

---

## Overview

Structured coordination files are how agents communicate state across context boundaries. Each file has a specific role: STATUS.md is the live heartbeat, HANDOFF.md is the task assignment, PROGRESS.md is the durable summary for context reloads, and BLOCKERS.md is the escalation log. Writing them inconsistently creates coordination ambiguity — the next agent cannot reliably determine project state.

---

## STATUS.md — Live Project Heartbeat

Update after every agent task completion. This is the coordinator's source of truth during active execution.

```markdown
# STATUS.md

UPDATED: 2026-04-09 15:42 UTC
PHASE: 3 of 5 — API Endpoint Implementation
OVERALL: IN PROGRESS

## Active Agents

| Agent | Task | Status | File Domain | Attempts |
|-------|------|--------|-------------|----------|
| nodejs-api-engineer | Implement /api/users endpoint | IN PROGRESS | src/routes/users.js | 1/3 |
| database-engineer | Optimize user query index | COMPLETE | migrations/002_*.sql | 1/3 |

## Blocked Agents

| Agent | Blocker | Blocking Since | See |
|-------|---------|----------------|-----|
| (none) | — | — | — |

## Completed Phases

- [x] Phase 1: Database schema — schema.sql — database-engineer — DONE
- [x] Phase 2: ORM models — src/models/ — python-general-engineer — DONE

## Pending Phases

- [ ] Phase 4: Integration tests — nodejs-api-engineer + python-general-engineer
- [ ] Phase 5: Documentation — technical-documentation-engineer

## Context Health

CONTEXT USAGE: ~45% (safe)
NEXT CHECKPOINT: At Phase 4 start — write PROGRESS.md before dispatching
```

**Rules for STATUS.md**:
- Must be updated after every agent task completion (not just phase completion)
- File domains must list specific files, not directories
- Attempt count (X/3) must be accurate — this is the death loop detector's input
- Context usage estimate prevents surprise compression events

---

## HANDOFF.md — Task Assignment

Write one HANDOFF.md per agent dispatch. Overwrite or version with HANDOFF-{agent}-{attempt}.md for retry tracking.

```markdown
# HANDOFF — nodejs-api-engineer

CREATED: 2026-04-09 15:40 UTC
ATTEMPT: 1 of 3
COORDINATOR: project-coordinator-engineer

## Task

Implement the `/api/users` GET endpoint with pagination.

## File Domain (ONLY these files)

- `src/routes/users.js` — endpoint implementation
- `src/routes/users.test.js` — unit tests

DO NOT TOUCH: src/models/, src/middleware/, schema.sql

## Dependencies (Already Complete)

- Database schema: schema.sql (Phase 1, DONE)
- ORM models: src/models/user.js (Phase 2, DONE)
- Import: `const User = require('../models/user')`

## Success Criteria (All Must Pass)

1. `npm test src/routes/users.test.js` exits 0
2. GET /api/users returns `{ data: [...], page: N, total: N }` structure
3. Missing page parameter defaults to page=1, limit=20
4. Invalid page parameter returns HTTP 400
5. `npm run build` exits 0 (compilation must still pass)

## Output Format

Return:
- Modified src/routes/users.js
- Modified src/routes/users.test.js
- Brief summary: what was implemented, any assumptions made

## Escalation

If blocked after attempting, write to BLOCKERS.md and stop. Do NOT attempt a 4th time.
```

**Rules for HANDOFF.md**:
- File domain must list every file the agent may touch and explicitly exclude shared files
- Success criteria must be executable commands — not prose descriptions
- Dependencies must reference the completed phase that produced them
- Escalation instructions prevent the agent from exceeding the 3-attempt limit unilaterally

---

## PROGRESS.md — Context Reload Summary

Write at 70% context capacity AND at project completion. This file is the only reliable state transfer mechanism when context must be summarized.

```markdown
# PROGRESS.md

WRITTEN: 2026-04-09 16:15 UTC
REASON: Context approaching 70% — saving state before Phase 4 dispatch
PROJECT: User API implementation

## Project Phases

| Phase | Description | Status | Agent | Notes |
|-------|-------------|--------|-------|-------|
| 1 | Database schema | DONE | database-engineer | schema.sql created, 4 tables |
| 2 | ORM models | DONE | python-general-engineer | User, Preferences models |
| 3 | API endpoints | DONE | nodejs-api-engineer | /users, /users/:id, /users/me |
| 4 | Integration tests | NOT STARTED | — | Blocked on: none |
| 5 | Documentation | NOT STARTED | — | Blocked on: Phase 4 |

## Modified Files

### Created
- schema.sql
- src/models/user.py
- src/models/preferences.py
- src/routes/users.js
- src/routes/users.test.js

### Modified
- package.json (added express-validator dependency)
- src/app.js (registered /api/users router at line 34)

## Key Decisions Made

1. Pagination: page+limit params (not cursor), defaults page=1 limit=20
2. Auth: JWT middleware applied at router level, not endpoint level
3. Error format: `{ error: "...", code: "...", field: "..." }` for all 4xx responses

## Pending Decisions (Need User Input)

- Rate limiting strategy for /api/users (none implemented yet)
- Whether /api/users/me should be a separate route or query param

## Next Phase Instructions

Dispatch: `nodejs-api-engineer` AND `python-general-engineer` in PARALLEL for Phase 4
  - nodejs-api-engineer: Write integration tests (tests/integration/users.test.js)
  - python-general-engineer: Write integration tests (tests/integration/models.test.py)
  File domains do NOT overlap — safe for parallel execution
```

**Rules for PROGRESS.md**:
- Write at 70% context, not at 100% (too late by then)
- Every modified file must be listed — fresh agent context cannot reconstruct git diff
- Decisions made must be explicit — prevents agents from re-debating resolved questions
- Next phase instructions must be complete enough for a fresh coordinator to continue

---

## BLOCKERS.md — Escalation Log

Append-only. Never delete entries. Each blocker gets a unique ID for cross-reference.

```markdown
# BLOCKERS.md

## BLOCKER-001

DATE: 2026-04-09 15:55 UTC
AGENT: nodejs-api-engineer
TASK: Implement /api/users endpoint
ATTEMPTS: 3/3 FAILED
STATUS: OPEN — requires user decision

### Failure Pattern

ATTEMPT 1: OperationalError: database connection refused (port 5432)
ATTEMPT 2: OperationalError: database connection refused (port 5432)
ATTEMPT 3: OperationalError: database connection refused (port 5432)

### Root Cause

The development database is not running. All three attempts hit the same infrastructure
failure — this is not a code issue. No code change can fix this.

Error confirms: postgres is not listening on localhost:5432.
Check: `pg_isready -h localhost -p 5432` returns "no response"

### Attempted Fixes

1. Connection retry with backoff (Attempt 2) — same error
2. Changed connection string format (Attempt 3) — same error

### Resolution Options

A) Start postgres: `sudo systemctl start postgresql`
B) Use SQLite for local dev (requires model changes)
C) Skip endpoint tests, implement with mocked DB (reduces test coverage)

### Blocking

- Phase 3: API endpoints (BLOCKED — cannot test without DB)
- Phase 4: Integration tests (BLOCKED — depends on Phase 3)

USER ACTION REQUIRED: Choose option A, B, or C
```

**Rules for BLOCKERS.md**:
- Numbered IDs allow STATUS.md to cross-reference (`See BLOCKER-001`)
- Root cause must distinguish infrastructure failures from code failures
- Resolution options must be concrete — "fix the code" is not an option
- User action required label triggers actual escalation to the user

---

## Error-Fix Mappings

| Symptom | Protocol Violation | Fix |
|---------|-------------------|-----|
| Agent continues past 3 attempts | HANDOFF.md missing escalation instruction | Add explicit "stop at 3 attempts, write BLOCKERS.md" to every HANDOFF |
| Fresh agent repeats completed work | PROGRESS.md not written before context summary | Write PROGRESS.md at 70% context, include completed phase list |
| Two agents conflict on same file | HANDOFF.md file domains not mutually exclusive | Audit all active HANDOFF.md files before parallel dispatch |
| Coordinator cannot determine current phase | STATUS.md not updated after agent completion | Enforce STATUS.md update as mandatory post-agent step |
| Blocker resolution stalls indefinitely | BLOCKERS.md options not concrete | Each option must be an executable action, not a direction |

---

## Detection Commands Reference

```bash
# Check STATUS.md exists and was recently updated
ls -la STATUS.md 2>/dev/null || echo "MISSING STATUS.md"
stat STATUS.md | grep Modify

# Find HANDOFF.md files missing SUCCESS CRITERIA
grep -L "SUCCESS CRITERIA" HANDOFF*.md 2>/dev/null

# Check PROGRESS.md written before last context-heavy dispatch
ls -la PROGRESS.md 2>/dev/null || echo "MISSING PROGRESS.md"

# Find open blockers (OPEN status in BLOCKERS.md)
grep -c "STATUS: OPEN" BLOCKERS.md 2>/dev/null

# Verify all agent file domains are non-overlapping
grep "File Domain\|FILE DOMAIN" HANDOFF*.md | grep -oP '(?<=\s)\S+\.(js|py|go|ts|sql)' | sort | uniq -d
```

---

## See Also

- `death-loop-prevention.md` — Attempt tracking and retry patterns
- `anti-patterns.md` — What goes wrong when protocols are skipped
