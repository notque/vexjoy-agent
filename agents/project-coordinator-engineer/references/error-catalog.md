# Coordination Error Catalog

> **Scope**: Common runtime errors encountered during multi-agent coordination — causes and resolutions.
> **Version range**: Claude Code multi-agent workflows (all versions)
> **Generated**: 2026-04-09

---

## Overview

Coordination errors fall into three categories: agent spawn failures (the agent cannot start or load context), task execution failures (the agent starts but cannot complete its work), and integration failures (agents complete individually but produce incompatible output). Integration failures are the most expensive — they surface only at the end of a phase after all agents have consumed their budgets.

---

## Agent Spawn Failures

### Context Overflow on Spawn

**Symptom**: Agent starts but immediately reports it cannot process the task, or produces incoherent output.

**Detection**:
```bash
# Check if STATUS.md context tracking shows > 90% before dispatch
grep "CONTEXT USAGE" STATUS.md | grep -oP '\d+' | awk '{if ($1 > 90) print "OVERFLOW RISK: " $1 "%"}'
```

**Root cause**: The coordinator dispatched a new agent while the current context was already near capacity. The agent receives a truncated or corrupted context.

**Fix**: Write PROGRESS.md summary before any dispatch when context exceeds 70%. Start fresh context with PROGRESS.md as the only source of prior state.

---

### Missing Dependency in HANDOFF

**Symptom**: Agent reports `undefined`, `not found`, or `FileNotFoundError` immediately — before making any code changes.

**Detection**:
```bash
# Check if HANDOFF.md declares dependencies that don't exist yet
grep "DEPENDENCY:" HANDOFF*.md | while read dep; do
  file=$(echo "$dep" | grep -oP '[\w./]+\.(py|go|js|sql|md)')
  [ -n "$file" ] && [ ! -f "$file" ] && echo "MISSING DEPENDENCY: $file"
done
```

**Root cause**: A previous phase's output was listed as a dependency but that phase has not completed, or completed with a different output filename.

**Fix**: Verify all declared dependencies exist before dispatch. Cross-reference PROGRESS.md completed phases with HANDOFF.md dependency list.

---

## Task Execution Failures

### File Domain Conflict During Execution

**Symptom**: Agent reports merge conflicts, unexpected file state, or reads stale content mid-task.

**Detection**:
```bash
# Look for concurrent STATUS.md entries for the same file
grep -h "FILE DOMAIN\|FILES:" HANDOFF*.md | sort | uniq -d
```

**Root cause**: Two agents assigned to the same file in a parallel phase. One agent's write invalidates the other's assumptions.

**Fix**: Serialize all modifications to shared files. Rebuild the HANDOFF.md to give each file to exactly one agent. See `anti-patterns.md` — "Overlapping File Domains."

---

### Agent Exceeds 3-Attempt Limit

**Symptom**: STATUS.md shows `ATTEMPTS: 3/3 FAILED` with no corresponding BLOCKERS.md entry.

**Detection**:
```bash
grep -rn "ATTEMPTS: 3/3" . --include="STATUS.md"
grep -rn "BLOCKER-" BLOCKERS.md 2>/dev/null || echo "BLOCKERS.md missing or empty"
```

**Root cause**: Coordinator dispatched a 4th attempt without stopping to analyze root cause, OR coordinator marked 3 failures without creating a BLOCKERS.md entry.

**Fix**: After 3/3 FAILED: (1) STOP all further dispatches for this task, (2) create BLOCKER-N entry in BLOCKERS.md with root cause analysis, (3) escalate to user.

---

## Integration Failures

### Output Format Mismatch

**Symptom**: Phase N+1 agent reports type errors, schema errors, or key-not-found when consuming Phase N output.

**Detection**:
```bash
# Check if SUCCESS CRITERIA included output format verification
grep -A10 "SUCCESS CRITERIA" HANDOFF*.md | grep -i "format\|schema\|structure\|shape"
# If no format verification in SUCCESS CRITERIA, this failure was predictable
```

**Root cause**: Phase N success criteria only verified that the agent completed (exit code 0), not that its output matches the interface Phase N+1 expects.

**Fix**: Add output format verification to Phase N's SUCCESS CRITERIA before Phase N closes:
```markdown
SUCCESS CRITERIA:
  4. Output JSON matches schema: python3 -c "import json; d=json.load(open('output.json')); assert 'users' in d and isinstance(d['users'], list)"
```

---

### PROGRESS.md Out of Sync

**Symptom**: Freshly-spawned agent repeats work already documented as complete, or contradicts prior decisions.

**Detection**:
```bash
# Compare PROGRESS.md completed list against actual file modification times
while IFS= read -r line; do
  file=$(echo "$line" | grep -oP '[\w./]+\.(py|go|js|ts|sql)')
  [ -n "$file" ] && [ -f "$file" ] && echo "$(stat -c %Y "$file") $file"
done < PROGRESS.md | sort -rn | head -10
```

**Root cause**: PROGRESS.md was not updated when a phase completed, or was written before context summarization occurred (capturing stale state).

**Fix**: PROGRESS.md must be updated immediately after each agent task completes — not at the end of a phase, not at 70% context, but after every task. See `communication-protocols.md` — PROGRESS.md template.

---

## Error-Fix Mappings

| Error Pattern | Root Cause | Fix |
|---------------|------------|-----|
| Agent immediately errors with `FileNotFoundError` or `undefined` | Missing dependency — prior phase not complete | Verify all HANDOFF.md dependencies exist before dispatch |
| STATUS.md shows 3/3 FAILED with no BLOCKERS.md entry | Retry limit reached without escalation | Create BLOCKER entry immediately; do not dispatch again |
| Phase N+1 agent reports schema/type mismatch | Phase N SUCCESS CRITERIA lacked output format check | Add format verification to SUCCESS CRITERIA for all phases with consumers |
| Fresh agent repeats completed work | PROGRESS.md stale or not written after phase completion | Write PROGRESS.md after every task, not just at phase boundaries |
| Two agents write conflicting content to same file | Overlapping file domains in parallel phase | Audit HANDOFF.md file assignments; enforce non-overlapping before parallel dispatch |

---

## Detection Commands Reference

```bash
# Check context usage before dispatch (prevent overflow)
grep "CONTEXT USAGE" STATUS.md | grep -oP '\d+' | awk '{if ($1 > 70) print "WARNING: " $1 "% context — write PROGRESS.md first"}'

# Find missing dependencies declared in HANDOFF files
grep "DEPENDENCY:" HANDOFF*.md | grep -oP '[\w./]+\.(py|go|js|sql|md)' | while read f; do [ ! -f "$f" ] && echo "MISSING: $f"; done

# Detect file domain conflicts across active HANDOFF files
grep -h "FILES\|FILE DOMAIN" HANDOFF*.md | sort | uniq -d

# Find tasks that exceeded retry limit without BLOCKERS entry
grep -l "ATTEMPTS: 3/3" STATUS.md 2>/dev/null && grep -c "BLOCKER-" BLOCKERS.md 2>/dev/null
```

---

## See Also

- `death-loop-prevention.md` — Retry loop patterns and intervention protocols
- `anti-patterns.md` — Coordination mistakes that produce these errors
- `communication-protocols.md` — STATUS.md, HANDOFF.md, PROGRESS.md, BLOCKERS.md templates
