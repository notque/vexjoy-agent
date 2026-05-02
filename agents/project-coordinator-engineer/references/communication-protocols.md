# Communication Protocols Reference

> **Scope**: Templates for STATUS.md, HANDOFF.md, PROGRESS.md, BLOCKERS.md in multi-agent coordination.

---

## STATUS.md — Live Project Heartbeat

Update after every agent task completion.

```markdown
# STATUS.md

UPDATED: 2026-04-09 15:42 UTC
PHASE: 3 of 5 — API Endpoint Implementation
OVERALL: IN PROGRESS

## Active Agents
| Agent | Task | Status | File Domain | Attempts |
|-------|------|--------|-------------|----------|
| nodejs-api-engineer | /api/users endpoint | IN PROGRESS | src/routes/users.js | 1/3 |

## Completed Phases
- [x] Phase 1: Database schema — database-engineer — DONE

## Context Health
CONTEXT USAGE: ~45% (safe)
NEXT CHECKPOINT: At Phase 4 start
```

**Rules**: Update after every task (not just phase). File domains list specific files. Attempt count (X/3) must be accurate.

---

## HANDOFF.md — Task Assignment

One per agent dispatch.

```markdown
# HANDOFF — nodejs-api-engineer

ATTEMPT: 1 of 3

## Task
Implement `/api/users` GET endpoint with pagination.

## File Domain (ONLY these files)
- `src/routes/users.js`, `src/routes/users.test.js`
DO NOT TOUCH: src/models/, src/middleware/, schema.sql

## Dependencies (Already Complete)
- schema.sql (Phase 1, DONE)
- src/models/user.js (Phase 2, DONE)

## Success Criteria (All Must Pass)
1. `npm test src/routes/users.test.js` exits 0
2. GET /api/users returns `{ data: [...], page: N, total: N }`
3. Missing page defaults to page=1, limit=20
4. Invalid page returns HTTP 400
5. `npm run build` exits 0

## Escalation
If blocked after attempting, write BLOCKERS.md and stop. Do NOT attempt a 4th time.
```

**Rules**: File domains must be explicit and mutually exclusive. Success criteria must be executable commands. Escalation instructions prevent exceeding 3-attempt limit.

---

## PROGRESS.md — Context Reload Summary

Write at 70% context AND at project completion.

```markdown
# PROGRESS.md

WRITTEN: 2026-04-09 16:15 UTC
REASON: Context approaching 70%

## Project Phases
| Phase | Status | Agent | Notes |
|-------|--------|-------|-------|
| 1 | DONE | database-engineer | 4 tables |
| 2 | DONE | python-general-engineer | User, Preferences models |
| 3 | DONE | nodejs-api-engineer | /users, /users/:id, /users/me |
| 4 | NOT STARTED | — | |

## Modified Files
### Created
- schema.sql, src/models/user.py, src/routes/users.js

### Modified
- package.json (added express-validator), src/app.js (registered router at line 34)

## Key Decisions Made
1. Pagination: page+limit (not cursor), defaults page=1 limit=20
2. Auth: JWT at router level

## Next Phase Instructions
Dispatch nodejs-api-engineer AND python-general-engineer in PARALLEL for Phase 4.
File domains do NOT overlap — safe for parallel execution.
```

**Rules**: Write at 70%, not 100% (too late). List every modified file. Decisions must be explicit. Next-phase instructions complete enough for a fresh coordinator.

---

## BLOCKERS.md — Escalation Log

Append-only. Unique IDs for cross-reference.

```markdown
## BLOCKER-001

AGENT: nodejs-api-engineer
ATTEMPTS: 3/3 FAILED
STATUS: OPEN

### Failure Pattern
All 3: OperationalError: database connection refused (port 5432)

### Root Cause
Dev database not running. Not a code issue.

### Resolution Options
A) Start postgres: `sudo systemctl start postgresql`
B) Use SQLite for dev (requires model changes)
C) Skip tests, mock DB (reduces coverage)

USER ACTION REQUIRED: Choose A, B, or C
```

**Rules**: Root cause must distinguish infrastructure from code failures. Resolution options must be concrete actions. User action label triggers escalation.

---

## Error-Fix Mappings

| Symptom | Fix |
|---------|-----|
| Agent continues past 3 attempts | Add explicit "stop at 3, write BLOCKERS.md" to every HANDOFF |
| Fresh agent repeats completed work | Write PROGRESS.md at 70% context |
| Two agents conflict on same file | Audit all active HANDOFF.md file domains before parallel dispatch |
| Cannot determine current phase | Enforce STATUS.md update after every agent completion |
| Blocker stalls indefinitely | Each option must be executable, not directional |

---

## Detection Commands

```bash
ls -la STATUS.md 2>/dev/null || echo "MISSING STATUS.md"
grep -L "SUCCESS CRITERIA" HANDOFF*.md 2>/dev/null
grep -c "STATUS: OPEN" BLOCKERS.md 2>/dev/null
# Verify non-overlapping file domains
grep "File Domain\|FILE DOMAIN" HANDOFF*.md | grep -oP '(?<=\s)\S+\.(js|py|go|ts|sql)' | sort | uniq -d
```
