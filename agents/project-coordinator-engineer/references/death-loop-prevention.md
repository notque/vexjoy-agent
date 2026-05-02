# Death Loop Prevention Reference

> **Scope**: Detecting, stopping, and recovering from agent death loops.

---

## Pattern Table

| Situation | Signal | Action |
|-----------|--------|--------|
| Same error 3+ consecutive | Identical error message/stack | STOP, BLOCKERS.md, root cause analysis |
| Agent modifying same lines | STATUS.md shows identical targets | Trigger intervention, change strategy |
| Compilation + lint cycling | Build fails after lint; lint breaks after build | Enforce compilation-first |
| Context at 70%+ | Spawning cost growing | PROGRESS.md, compress context |

---

## 3-Attempt Tracking in STATUS.md

```markdown
AGENT: golang-general-engineer
TASK: Fix channel direction linting errors

ATTEMPT 1 — Result: FAILED — 3 channel direction errors in consumer.go
ATTEMPT 2 — Changed directions → FAILED — compilation broken in producer.go
ATTEMPT 3 — Reverted, changed producer.go → FAILED — original errors returned

ATTEMPTS: 3/3 FAILED — LOOP DETECTED
PATTERN: Fix in consumer breaks producer; fix in producer reverts consumer
ACTION: Manual intervention — design issue, not lint fix
```

---

## Compilation-First Protocol

```markdown
1. ASSIGN: code-modification-agent — SUCCESS: `go build ./...` exits 0
2. VERIFY: `go build ./...` — must pass before step 3
3. ASSIGN: lint task — SUCCESS: lint exits 0 AND `go build ./...` still exits 0
```

---

## Root Cause Analysis Template

```markdown
## Blocker: Channel Direction Death Loop

AGENT: golang-general-engineer — 3/3 FAILED

ROOT CAUSE: consumer.go and producer.go share a channel in types.go.
types.go must change first — neither file fixable independently.

REQUIRED STRATEGY:
  1. Modify types.go channel type
  2. Verify compilation
  3. Fix consumer.go and producer.go together

ESCALATION: User approval needed to modify types.go (shared interface)
```

---

## Pattern Catalog

### Change Strategy Before Each Retry
**Detection**: `grep -A2 "ATTEMPT" STATUS.md | grep "Error:" | sort | uniq -d`
**Fix**: Before retry, identify what changed. If answer is "nothing", stop and document in BLOCKERS.md.

### Verify Compilation Before and After Lint
**Detection**: `grep -B5 "lint\|ruff\|golangci" HANDOFF.md | grep -i "success criteria"`
**Fix**: Compilation verification as first AND last step of every lint task:
```markdown
SUCCESS CRITERIA:
  1. Compilation passes
  2. Lint passes
  3. Compilation still passes after lint
```

### Include Root Cause and New Strategy in Re-Dispatch
**Detection**: `grep -c "RETRY\|Re-assign\|Try again" HANDOFF.md`
**Fix**: Re-dispatch requires: (1) specific error from prior attempt, (2) root cause identified, (3) new strategy with file/line scope.

---

## Error-Fix Mappings

| Pattern | Fix |
|---------|-----|
| Same error 3 consecutive entries | STOP, root cause analysis, change approach |
| Build passes → lint → build fails | Enforce compilation-first: verify build after lint |
| 3/3 without BLOCKERS.md | Create BLOCKERS.md entry before further coordination |
| Agent assigned file in another domain | Check STATUS.md assignments before dispatching |
| Context summarization mid-task | Write PROGRESS.md at 70% threshold |

---

## Detection Commands

```bash
# Repeated identical errors
grep -A2 "ATTEMPT" STATUS.md | grep "Error:" | sort | uniq -d

# Retry directives without strategy (should be 0)
grep -c "RETRY\|Re-assign\|Try again" HANDOFF.md

# Lint before compilation in task sequence
grep -B5 "lint\|ruff\|golangci" HANDOFF.md | grep -i "success criteria"

# Completed loops
grep -rn "ATTEMPTS: 3/3" . --include="STATUS.md"
```
