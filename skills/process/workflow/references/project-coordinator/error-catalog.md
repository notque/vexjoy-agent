# Coordination Error Catalog

> **Scope**: Runtime errors in multi-agent coordination — causes and resolutions.

Errors fall into three categories: agent spawn failures, task execution failures, and integration failures (most expensive — surface only after all agents have consumed budgets).

---

## Agent Spawn Failures

### Context Overflow on Spawn
**Symptom**: Agent produces incoherent output or can't process task.
**Detection**: `grep "CONTEXT USAGE" STATUS.md | grep -oP '\d+' | awk '{if ($1 > 90) print "OVERFLOW RISK"}'`
**Fix**: Write PROGRESS.md before dispatch when context > 70%.

### Missing Dependency in HANDOFF
**Symptom**: `undefined`, `not found`, `FileNotFoundError` immediately.
**Fix**: Verify all HANDOFF.md dependencies exist before dispatch. Cross-reference PROGRESS.md.

---

## Task Execution Failures

### File Domain Conflict
**Symptom**: Merge conflicts, unexpected file state, stale reads.
**Detection**: `grep -h "FILE DOMAIN\|FILES:" HANDOFF*.md | sort | uniq -d`
**Fix**: Serialize shared files. Each file to exactly one agent.

### Agent Exceeds 3-Attempt Limit
**Symptom**: STATUS.md shows `3/3 FAILED` with no BLOCKERS.md entry.
**Fix**: (1) STOP dispatches, (2) create BLOCKER entry with root cause, (3) escalate.

---

## Integration Failures

### Output Format Mismatch
**Symptom**: Phase N+1 agent reports type/schema errors on Phase N output.
**Fix**: Add format verification to Phase N success criteria:
```markdown
SUCCESS CRITERIA:
  4. Output matches schema: python3 -c "import json; d=json.load(open('output.json')); assert 'users' in d"
```

### PROGRESS.md Out of Sync
**Symptom**: Fresh agent repeats completed work or contradicts decisions.
**Fix**: Update PROGRESS.md after every task completion, not just at phase boundaries.

---

## Error-Fix Mappings

| Error Pattern | Fix |
|---------------|-----|
| Immediate `FileNotFoundError` | Verify HANDOFF.md dependencies exist |
| 3/3 FAILED without BLOCKERS.md | Create BLOCKER entry immediately |
| Schema/type mismatch at phase boundary | Add format verification to SUCCESS CRITERIA |
| Fresh agent repeats completed work | Write PROGRESS.md after every task |
| Conflicting writes to same file | Enforce non-overlapping domains before parallel dispatch |

---

## Detection Commands

```bash
# Context overflow risk
grep "CONTEXT USAGE" STATUS.md | grep -oP '\d+' | awk '{if ($1 > 70) print "WARNING: write PROGRESS.md"}'

# Missing dependencies
grep "DEPENDENCY:" HANDOFF*.md | grep -oP '[\w./]+\.(py|go|js|sql|md)' | while read f; do [ ! -f "$f" ] && echo "MISSING: $f"; done

# File domain conflicts
grep -h "FILES\|FILE DOMAIN" HANDOFF*.md | sort | uniq -d

# Exceeded retry without blocker
grep -l "ATTEMPTS: 3/3" STATUS.md 2>/dev/null && grep -c "BLOCKER-" BLOCKERS.md 2>/dev/null
```
