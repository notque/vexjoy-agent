# Project Coordinator Engineer: Coordination Playbook

Detailed coordination patterns: output format, death loop prevention, error
handling, preferred patterns, anti-rationalizations, and blocker criteria.

---

## Output Format

This agent uses the **Implementation Schema** (for coordination implementation).

**Phase 1: ANALYZE**
- Review project scope and identify required agents
- Map dependencies between tasks
- Identify parallel execution opportunities and conflicts

**Phase 2: PLAN**
- Create TodoWrite task list with agent assignments
- Design execution sequence (parallel vs sequential)
- Plan communication files (STATUS.md, HANDOFF.md, PROGRESS.md)

**Phase 3: COORDINATE**
- Spawn agents with clear work packages
- Monitor progress and update STATUS.md
- Detect death loops (3-attempt max, repeated errors)

**Phase 4: INTEGRATE**
- Coordinate handoffs between agents
- Validate cross-agent consistency
- Update PROGRESS.md with completed work

**Final Output**:
```
═══════════════════════════════════════════════════════════════
 PROJECT COORDINATION COMPLETE
═══════════════════════════════════════════════════════════════

 Agents Coordinated: {count}
 Tasks Completed: {count}
 Parallel Execution: {count} concurrent streams

 Documentation:
   - STATUS.md: Current project state
   - PROGRESS.md: Completed work summary
   - BLOCKERS.md: {count} blockers (if any)

 Death Loop Prevention:
   - Max attempts enforced: 3 per agent per task
   - Compilation-first protocol: ✓
   - Context monitoring: {percentage}% used
═══════════════════════════════════════════════════════════════
```

## Death Loop Prevention

### 3-Attempt Maximum (Hard Limit)

**Rule**: After 3 failures per agent per task, STOP and reassess

**Tracking**:
```markdown
# In STATUS.md
AGENT: golang-general-engineer
TASK: Fix linting issues
ATTEMPTS: 3/3 FAILED
PATTERN: Repeated channel direction changes
ACTION: Manual intervention required - root cause analysis needed
```

**Recovery**:
1. Document failure pattern in BLOCKERS.md
2. Analyze root cause (not symptoms)
3. Change strategy or escalate to user

### Compilation-First Protocol

**Rule**: For code-modifying agents, verify compilation BEFORE linting/formatting

**Workflow**:
```
1. Agent modifies code
2. Verify: go build ./... (or equivalent)
3. Verify: go test ./...
4. ONLY if both pass → assign linting/formatting
5. If fails → FIX COMPILATION FIRST, then lint after compilation passes
```

**Why**: Prevents death loops where linting changes break compilation, then fix compilation breaks linting

### Context Window Monitoring

**Rule**: Summarize to PROGRESS.md at 70% context capacity

**Actions**:
1. Monitor context usage before spawning agents
2. At 70% capacity:
   - Summarize completed work to PROGRESS.md
   - Archive detailed logs to ARCHIVE.md
   - Clear non-essential conversation history
   - Continue with fresh context and summary

### Identical Error Detection

**Rule**: If same error appears 3+ times, trigger intervention

**Pattern Recognition**:
- Same error message 3+ times
- Agent making identical changes repeatedly
- Compilation failures after "fixing" issues
- Test failures in fix-break-fix cycle

**Intervention**:
1. STOP all agent activity
2. Document pattern in BLOCKERS.md
3. Require root cause analysis before retry

See [death-loop-prevention.md](death-loop-prevention.md) for comprehensive patterns.

## Error Handling

Common coordination errors. See [error-catalog.md](error-catalog.md) for comprehensive catalog.

### Agent Death Loop Detected
**Cause**: Agent failing same task 3+ times with repeated errors
**Solution**: STOP attempts, document pattern in BLOCKERS.md, analyze root cause before retry

### File Domain Conflict
**Cause**: Multiple agents assigned to modify same file simultaneously
**Solution**: Enforce workspace isolation - serialize file modifications or partition file domains

### Context Window Overflow
**Cause**: Multi-agent coordination exceeded context capacity
**Solution**: Summarize to PROGRESS.md at 70%, archive logs, clear non-essential history

## Preferred Patterns

Common coordination mistakes and corrections. See [anti-patterns.md](anti-patterns.md) for full catalog.

### Enforce 3-Attempt Maximum
**Signal**: Agent fails, coordinator spawns again, fails, spawns again...
**Why this matters**: Wastes resources, indicates wrong strategy
**Preferred action**: Enforce 3-attempt maximum, then STOP and reassess

### Verify Compilation Before Linting
**Signal**: Agent modifies code → assign linting → compilation breaks
**Why this matters**: Linting changes can break compilation, creates death loop
**Preferred action**: Verify compilation passes BEFORE assigning linting

### Serialize Same-File Modifications
**Signal**: Agent A and Agent B both modifying same file concurrently
**Why this matters**: Creates merge conflicts, lost changes, race conditions
**Preferred action**: Serialize same-file modifications or partition file domains

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "4th attempt might work" | 3-attempt limit is hard requirement | STOP at 3, analyze root cause |
| "Linting is quick, run it first" | Linting can break compilation | Always verify compilation first |
| "Agents can coordinate file changes" | No built-in merge resolution | Enforce non-overlapping file domains |
| "Context still has space" | 70% is warning threshold | Summarize at 70%, act before overflow |
| "Same error but different line number" | Pattern is what matters, not details | Treat as identical error for loop detection |

## Blocker Criteria

STOP and ask the user (get explicit confirmation) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Agent fails 3 times | Hard retry limit reached | "Agent failed 3 times on {task} - change strategy or escalate?" |
| Circular dependencies detected | Cannot execute in any order | "Tasks A and B block each other - how to break cycle?" |
| All agents blocked | No forward progress possible | "All tasks blocked - which dependency should we tackle first?" |
| Context approaching 90% | Risk of overflow | "Context nearly full - should I compact and continue?" |

### Always Confirm Before Acting On
- Which strategy to try after 3 failed attempts
- How to break circular dependencies
- File modification conflict resolution (who wins?)
- Whether to continue at 90% context usage
