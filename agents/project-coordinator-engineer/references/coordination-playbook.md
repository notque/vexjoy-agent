# Project Coordinator Engineer: Coordination Playbook

Output format, death loop prevention, error handling, preferred patterns, anti-rationalizations, blocker criteria.

---

## Output Format — Implementation Schema

**Phase 1: ANALYZE** — Review scope, identify agents, map dependencies, find parallel opportunities.
**Phase 2: PLAN** — TodoWrite with assignments, execution sequence, communication file plan.
**Phase 3: COORDINATE** — Spawn agents, monitor progress, update STATUS.md, detect death loops.
**Phase 4: INTEGRATE** — Coordinate handoffs, validate cross-agent consistency, update PROGRESS.md.

**Final Output**:
```
═══════════════════════════════════════════════════════════════
 PROJECT COORDINATION COMPLETE
 Agents Coordinated: {count}
 Tasks Completed: {count}
 Parallel Execution: {count} concurrent streams
 Documentation: STATUS.md, PROGRESS.md, BLOCKERS.md ({count})
 Death Loop Prevention: 3 max enforced, compilation-first ✓, context {%}%
═══════════════════════════════════════════════════════════════
```

## Death Loop Prevention

### 3-Attempt Maximum (Hard Limit)
After 3 failures per agent per task: STOP, document in BLOCKERS.md, analyze root cause, change strategy or escalate.

### Compilation-First Protocol
For code-modifying agents: (1) modify code, (2) verify build, (3) verify tests, (4) ONLY then lint/format. Prevents build-lint-break cycles.

### Context Window Monitoring
At 70%: summarize to PROGRESS.md, archive logs, clear non-essential history, continue with summary.

### Identical Error Detection
Same error 3+ times → STOP all agents, document in BLOCKERS.md, require root cause before retry.

See [death-loop-prevention.md](death-loop-prevention.md) for comprehensive patterns.

## Error Handling

| Error | Fix |
|-------|-----|
| Death loop (3+ same failures) | STOP, BLOCKERS.md, root cause before retry |
| File domain conflict | Serialize or partition file domains |
| Context overflow | PROGRESS.md at 70%, archive, clear |

See [error-catalog.md](error-catalog.md) for full catalog.

## Preferred Patterns

| Signal | Fix |
|--------|-----|
| Agent fails repeatedly, coordinator re-spawns | Enforce 3-attempt max, then reassess |
| Code → lint → compilation breaks | Verify compilation BEFORE linting |
| Two agents modifying same file | Serialize same-file modifications |

See [preferred-patterns.md](preferred-patterns.md) for full catalog.

## Anti-Rationalization

| Rationalization | Required Action |
|----------------|-----------------|
| "4th attempt might work" | STOP at 3, analyze root cause |
| "Linting is quick, run it first" | Verify compilation first |
| "Agents can coordinate file changes" | Enforce non-overlapping domains |
| "Context still has space" | Summarize at 70% |
| "Same error but different line number" | Treat as identical for loop detection |

## Blocker Criteria

| Situation | Ask This |
|-----------|----------|
| Agent fails 3 times | "Change strategy or escalate?" |
| Circular dependencies | "How to break cycle?" |
| All agents blocked | "Which dependency first?" |
| Context approaching 90% | "Compact and continue?" |

### Always Confirm Before Acting On
- Strategy after 3 failed attempts
- Breaking circular dependencies
- File modification conflict resolution
- Continuing at 90% context
