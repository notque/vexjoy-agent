# Parallel Execution Patterns Reference

> **Scope**: Safe parallel agent streams, file domain conflict detection, concurrent workloads.

---

## Task Parallelism Categories

| Task Type | Safe? | Constraint |
|-----------|-------|------------|
| Different file domains | Yes | No shared files |
| Same file, different sections | No | Serialize via handoff |
| Read-only analysis/audit/review | Always | No write conflicts |
| Test-only agents | Yes | Read-only against source |
| Schema migration + app code | No | Migration first |
| Lint + format on same file | No | Sequential post-compile |
| Documentation updates | Usually | Check shared index files |

---

## Fan-Out Parallel Dispatch

```markdown
STREAM A: golang-general-engineer → src/api/ (RUNNING)
STREAM B: typescript-frontend-engineer → src/ui/ (RUNNING)
STREAM C: database-engineer → migrations/ (RUNNING)

Fan-in: wait for A+B+C before integration.
```

---

## File Domain Declaration (Pre-Dispatch)

```markdown
Task: Refactor authentication middleware
Agent: nodejs-api-engineer
Domain: src/middleware/auth.ts, src/middleware/session.ts
Excludes: src/routes/ (owned by STREAM B)
Success: `npm test -- auth` passes
```

Explicit declaration makes conflicts visible at planning time.

---

## Fan-In Gate

```markdown
Wait conditions:
- [ ] STREAM A complete
- [ ] STREAM B complete
- [ ] STREAM C complete

BLOCKED: Do not dispatch integration until all checked.
```

Partial integration creates inconsistent state.

---

## Pattern Catalog

### Verify Domain Isolation Before Dispatch
**Signal**: Dispatching 3 agents without checking shared files.
**Detection**: `grep -r "config/config" src/ | cut -d: -f1 | sort | uniq -d`
**Fix**: Run domain conflict check before every parallel wave. Serialize agents sharing any file.

### Treat Code Generation as Sequential Gate
**Signal**: Running `go generate` while another stream reads generated files.
**Fix**: Generation completes fully, fan-in confirms output exists, then downstream starts.

### Enforce Compile-Test-Lint-Format Sequence
**Signal**: Lint and compile agents dispatched simultaneously.
**Fix**: Within any domain: Compile → Test → Lint → Format. Only proceed after previous exits 0.

---

## Parallel Capacity Heuristics

| Scenario | Max Parallel |
|----------|-------------|
| Clean domain boundaries | 5-8 |
| Shared config layer | 3-4 (config agent first) |
| Monorepo cross-cutting | 2-3 |
| Active schema migration | 1 + blocked |
| Context at 70%+ | 1 only |

---

## Parallelism Decision Checklist

1. `[ ]` Domain overlap check — no shared files
2. `[ ]` Dependencies resolved — prerequisites complete
3. `[ ]` Generated files stabilized
4. `[ ]` Context budget allows N agents
5. `[ ]` Fan-in gate documented in STATUS.md
