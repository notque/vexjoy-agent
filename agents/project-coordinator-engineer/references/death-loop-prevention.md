# Death Loop Prevention Reference

> **Scope**: Patterns for detecting, stopping, and recovering from agent death loops in multi-agent coordination.
> **Version range**: Claude Code multi-agent workflows (all versions)
> **Generated**: 2026-04-09

---

## Overview

A death loop occurs when an agent repeatedly fails at the same task using the same strategy, consuming context and budget without progress. The 3-attempt maximum is a hard limit — not a guideline. The most common trigger is assigning linting/formatting before confirming compilation, which creates a fix-break-fix cycle that never converges.

---

## Pattern Table

| Situation | Signal | Required Action |
|-----------|--------|-----------------|
| Same error 3+ consecutive attempts | Identical error message or stack trace | STOP, document in BLOCKERS.md, require root cause analysis |
| Agent modifying same lines repeatedly | STATUS.md shows identical file/line targets | Trigger intervention, change strategy |
| Compilation + lint cycling | Build fails after lint fix; lint breaks after build fix | Enforce compilation-first protocol |
| Context at 70%+ | Agent spawning cost growing | Summarize to PROGRESS.md, compress context |

---

## Correct Patterns

### 3-Attempt Tracking in STATUS.md

Track every attempt explicitly so the coordinator can detect the loop before it runs deep.

```markdown
# STATUS.md — Agent Attempt Log

AGENT: golang-general-engineer
TASK: Fix channel direction linting errors

ATTEMPT 1 — 2026-04-09 14:01
  Action: Ran `go vet ./...`
  Result: FAILED — 3 channel direction errors in consumer.go:44,87,112
  Error: `receive from send-only channel`

ATTEMPT 2 — 2026-04-09 14:08
  Action: Changed chan directions in consumer.go
  Result: FAILED — compilation broken, new errors in producer.go:22
  Error: `cannot use chan<- int as type <-chan int`

ATTEMPT 3 — 2026-04-09 14:15
  Action: Reverted consumer.go, changed producer.go
  Result: FAILED — original linting errors returned
  Error: `receive from send-only channel` (same as Attempt 1)

ATTEMPTS: 3/3 FAILED — LOOP DETECTED
PATTERN: Fix in consumer.go breaks producer.go; fix in producer.go reverts consumer.go
ACTION: Manual intervention required — design issue, not a lint fix issue
```

**Why**: Explicit attempt logs prevent coordinators from losing count during long sessions, especially when context summarization has occurred.

---

### Compilation-First Protocol

Always verify compilation before assigning linting or formatting tasks.

```markdown
# Correct agent assignment sequence:

1. ASSIGN: code-modification-agent
   TASK: Implement feature X
   SUCCESS CRITERIA: `go build ./...` exits 0

2. VERIFY: Run `go build ./...` — must pass before step 3
   If fails → return to step 1 with specific build errors

3. ASSIGN: code-modification-agent
   TASK: Fix linting (ruff/golangci-lint)
   DEPENDENCY: Step 2 verified compilation passes
   SUCCESS CRITERIA: lint exits 0 AND `go build ./...` still exits 0
```

**Why**: Linting auto-fixes (gofmt, ruff --fix) can introduce syntax changes that break compilation. Assigning lint before compile verification creates a build-break cycle.

---

### Root Cause Analysis Template

When 3 attempts fail, document the root cause before any retry.

```markdown
# BLOCKERS.md — Root Cause Analysis

## Blocker: Channel Direction Death Loop

DATE: 2026-04-09
AGENT: golang-general-engineer
TASK: Resolve channel direction lint errors
ATTEMPTS: 3/3 FAILED

ROOT CAUSE (not symptoms):
  - consumer.go and producer.go share a channel defined in types.go
  - Lint requires send-only in producer, receive-only in consumer
  - Bidirectional chan in types.go is the source — neither file can be fixed independently
  - This is a design issue: types.go must change first

FAILED STRATEGIES:
  1. Fix consumer.go only → breaks producer.go
  2. Fix producer.go only → reverts consumer.go errors
  3. Fix both simultaneously → compilation breaks on types.go

REQUIRED STRATEGY:
  1. Modify types.go channel type first
  2. Verify compilation after types.go change
  3. Then fix consumer.go and producer.go together

ESCALATION: User approval needed to modify types.go (shared interface)
```

---

## Anti-Pattern Catalog

### ❌ Silent Retry Without Strategy Change

**Detection**:
```bash
# In STATUS.md files — look for identical error messages across attempts
grep -A2 "ATTEMPT" STATUS.md | grep "Error:" | sort | uniq -d
# If uniq -d returns lines, identical errors are repeating
```

**What it looks like**:
```markdown
ATTEMPT 1 — Error: `undefined: UserRepository`
ATTEMPT 2 — Error: `undefined: UserRepository`
ATTEMPT 3 — Error: `undefined: UserRepository`
```

**Why wrong**: Retrying without strategy change is guaranteed to fail. The 3-attempt limit exists specifically to prevent this. Each retry burns context budget with zero probability of success.

**Fix**: Before any retry, the coordinator must answer: "What is different about this attempt?" If the answer is "nothing", do not retry — escalate.

---

### ❌ Lint-Before-Compile Assignment

**Detection**:
```bash
# In HANDOFF.md or coordination notes — look for lint tasks assigned before build verification
grep -B5 "lint\|ruff\|golangci" HANDOFF.md | grep -i "success criteria"
# Success criteria should reference compilation, not just lint exit code
```

**What it looks like**:
```markdown
TASK: Fix all linting errors in src/
SUCCESS CRITERIA: `ruff check . --fix` exits 0
```

**Why wrong**: `ruff --fix` can change syntax that breaks Python's AST. `gofmt` can reformat imports that expose missing packages. Assigning lint-only success criteria hides compilation regression.

**Fix**:
```markdown
TASK: Fix all linting errors in src/
SUCCESS CRITERIA:
  1. `python3 -c "import ast; ast.parse(open('src/main.py').read())"` exits 0
  2. `ruff check . --fix` exits 0
  3. Re-verify step 1 after lint fix (compilation must still pass)
```

---

### ❌ Ambiguous "Fix It" Re-Dispatch

**Detection**:
```bash
# Look for HANDOFF.md re-dispatches without explicit strategy change
grep -c "RETRY\|Re-assign\|Try again" HANDOFF.md
# Any count > 0 warrants review of whether strategy changed
```

**What it looks like**:
```markdown
HANDOFF to golang-general-engineer:
  Previous attempt failed with compilation errors.
  Please try again and fix the compilation errors.
```

**Why wrong**: "Try again" without specifying what to do differently is identical retry disguised as new instruction. The agent has no new information, so it will repeat the same approach.

**Fix**:
```markdown
HANDOFF to golang-general-engineer:
  Previous attempt failed: `undefined: Logger` in server.go:44
  Root cause identified: Logger is defined in logger.go but not imported in server.go
  NEW STRATEGY: Add `"myapp/internal/logger"` import to server.go imports block
  Do NOT touch any other file — scope is server.go imports only
```

---

## Error-Fix Mappings

| Pattern | Root Cause | Fix |
|---------|------------|-----|
| Same error message in 3 consecutive STATUS.md entries | Strategy not changing between attempts | STOP, perform root cause analysis, change approach |
| Build passes, lint fails, agent re-runs linting, build fails | Lint mutated compilation-valid code | Enforce compilation-first: verify build after every lint fix |
| `ATTEMPTS: 3/3` in STATUS.md without BLOCKERS.md entry | Death loop completed without documentation | Create BLOCKERS.md root cause entry before any further coordination |
| Agent assigned file already in another agent's domain | Non-overlapping file domain violated | Check STATUS.md current file assignments before dispatching |
| Context summarization triggered mid-task | Context grew past 70% without PROGRESS.md update | Write PROGRESS.md at 70% threshold; start new agent context with summary |

---

## Detection Commands Reference

```bash
# Detect repeated identical errors across attempts
grep -A2 "ATTEMPT" STATUS.md | grep "Error:" | sort | uniq -d

# Count retry directives in HANDOFF.md (should be 0 without strategy note)
grep -c "RETRY\|Re-assign\|Try again" HANDOFF.md

# Check if lint was assigned before compilation in task sequence
grep -B5 "lint\|ruff\|golangci" HANDOFF.md | grep -i "success criteria"

# Find STATUS.md files with 3/3 attempt entries (completed loops)
grep -rn "ATTEMPTS: 3/3" . --include="STATUS.md"
```

---

## See Also

- `anti-patterns.md` — Full coordination anti-pattern catalog
- `communication-protocols.md` — STATUS.md, HANDOFF.md, BLOCKERS.md templates
