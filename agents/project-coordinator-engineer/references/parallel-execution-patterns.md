# Parallel Execution Patterns Reference

> **Scope**: Identifying safe parallel agent streams, detecting file domain conflicts, structuring concurrent workloads.
> **Version range**: All versions — Claude Code multi-agent coordination
> **Generated**: 2026-04-09 — verify against current agent capability roster

---

## Overview

Parallel execution is the primary throughput lever in multi-agent coordination. The constraint is file domain overlap — two agents touching the same file concurrently create merge conflicts. The coordinator's job is to identify the maximum safe parallelism while enforcing non-overlapping domains.

Common failure mode: sequential execution of work that could have been parallel, or parallel execution of work that shares a file domain (races).

---

## Pattern Table: Task Parallelism Categories

| Task Type | Safe to Parallelize? | Constraint |
|-----------|---------------------|------------|
| Different file domains (A edits `api/`, B edits `ui/`) | Yes | No shared files |
| Same file, different sections | No | Serialize via handoff |
| Read-only analysis (research, audit, review) | Always | No write conflicts |
| Test-only agents (no source modifications) | Yes | Read-only against source |
| Schema migration + application code | No | Migration must complete first |
| Lint + format on same file | No | Run sequentially post-compile |
| Documentation updates | Usually | Check for shared index files |

---

## Correct Patterns

### Fan-Out Parallel Dispatch

Dispatch independent agents simultaneously when file domains don't overlap.

```markdown
# In STATUS.md — parallel stream tracking
STREAM A: golang-general-engineer → src/api/ (RUNNING)
STREAM B: typescript-frontend-engineer → src/ui/ (RUNNING)
STREAM C: database-engineer → migrations/ (RUNNING)

All streams are read-only against each other's domains.
Fan-in: wait for A+B+C before integration phase.
```

**Why**: Sequential dispatch of independent work is the most common coordinator waste. A 3-stream parallel dispatch completes in 1x agent time vs 3x.

---

### File Domain Declaration (Pre-Dispatch)

Before dispatching any agent, declare its file domain explicitly.

```markdown
# TodoWrite task description — mandatory format
Task: Refactor authentication middleware
Agent: nodejs-api-engineer
Domain: src/middleware/auth.ts, src/middleware/session.ts
Excludes: src/routes/ (owned by STREAM B)
Success: `npm test -- auth` passes, no TypeScript errors
```

**Why**: Implicit domain assumptions cause conflicts discovered only at integration. Explicit declaration makes conflicts visible at planning time — before agents run.

**Detection** — find tasks missing domain declarations:
```
rg "Agent:.*\nDomain:" --multiline --files-without-matches STATUS.md
```

---

### Fan-In Gate Pattern

After parallel streams, hold integration until ALL streams complete.

```markdown
## Phase 2 Gate (Fan-In)

Wait conditions:
- [ ] STREAM A: golang-general-engineer — src/api/ complete
- [ ] STREAM B: typescript-frontend-engineer — src/ui/ complete  
- [ ] STREAM C: database-engineer — migrations/ complete

BLOCKED: Do not dispatch integration agent until all 3 boxes checked.
```

**Why**: Partial integration (2 of 3 streams done) creates inconsistent state that the integration agent will produce wrong output from.

---

### Sequential Dependency Chain

When output of one agent is input to the next, enforce sequential execution.

```markdown
# Correct dependency chain
Step 1: database-engineer → schema.sql (MUST COMPLETE FIRST)
Step 2: golang-general-engineer → generated models from schema
Step 3: nodejs-api-engineer → API handlers using models

# Anti-pattern — will fail:
[WRONG] Step 1 + Step 2 parallel → Step 2 reads schema before it exists
```

---

## Anti-Pattern Catalog

### ❌ Assumed Domain Isolation

**What it looks like**: Dispatching 3 agents without checking if any share `pkg/config/config.go`.

**Detection**:
```
grep -r "config/config" src/ | cut -d: -f1 | sort | uniq -d
```
Any file appearing in multiple agent domains signals a conflict.

**Fix**: Run domain conflict check before dispatch. Serialize agents that share any file.

---

### ❌ Optimistic Parallelism on Generated Files

**What it looks like**: Running `go generate` in STREAM A while STREAM B reads generated files.

**Why wrong**: Generated file content is undefined mid-generation. STREAM B reads partial state.

**Fix**: Generation is always sequential. Downstream consumers wait for generation fan-in.

---

### ❌ Lint/Format Before Compile in Parallel

**What it looks like**: Dispatching lint agent and compile agent simultaneously.

**Why wrong**: If compile fails, lint output is wasted work. If lint changes code, compile state is stale.

**Fix**: Compile → Test → Lint → Format (always sequential, never parallel within a domain).

---

## Parallel Capacity Heuristics

| Scenario | Max Safe Parallel Agents |
|----------|--------------------------|
| Large codebase, clean domain boundaries | 5-8 streams |
| Shared config/constants layer | 3-4 streams (config agent first) |
| Monorepo with cross-cutting concerns | 2-3 streams |
| Active schema migration in progress | 1 stream (schema owner) + blocked |
| Context at 70%+ | 1 stream only (preserve context budget) |

---

## Parallelism Decision Checklist

Before each dispatch wave, verify:
1. `[ ]` Domain overlap check complete — no shared files across streams
2. `[ ]` Dependencies resolved — prerequisites complete before dependents start
3. `[ ]` Generated files stabilized — no generation in progress
4. `[ ]` Context budget allows N agents — check against 70% threshold
5. `[ ]` Fan-in gate documented in STATUS.md — clear wait conditions
