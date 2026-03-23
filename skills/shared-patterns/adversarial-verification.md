# Adversarial Verification Pattern

Reusable 4-level artifact verification methodology for any agent or skill that needs to verify task completion. Implements structural distrust of executor claims with goal-backward framing.

**Source**: ADR-071 (Adversarial Verification Agent)
**Primary consumer**: `verification-before-completion` skill
**Also useful for**: Code review agents, PR pipeline verification phases, any agent that validates another agent's output

## Core Principle: Never Trust Summary Claims

The verifier NEVER accepts statements like "implemented the scoring module" or "all tests pass" at face value. Every claim is independently verified by examining what actually exists in the codebase.

**WHY**: The same agent (or a cooperating agent) that wrote the code has inherent bias toward believing its output is correct. Even with good intentions, executors report what they *intended* to do, not necessarily what the codebase *actually* contains. Structural distrust counteracts this by requiring evidence at every level.

The verification question is not "did the executor say it's done?" but "does the codebase prove it's done?"

## Goal-Backward Framing

**Instead of**: "Were all tasks completed?" (task-forward, invites executor confirmation)
**Ask**: "What must be TRUE for the goal to be achieved?" (goal-backward, derives conditions independently)

### Procedure

1. **State the goal as a testable condition**: Express the user's request as a concrete, verifiable outcome.
2. **Decompose into must-be-true conditions**: Break the goal into independent conditions that must ALL hold.
3. **Verify each condition independently** at the appropriate level using the 4-Level system.
4. **Report unverified conditions** as blockers -- not "you missed a task" but "this condition is not yet true in the codebase."

### Example

**Goal**: "Users can create a PR with quality scoring that blocks merges below threshold"

**Conditions**:
| Condition | Required Level |
|-----------|---------------|
| A scoring function exists | L1 |
| It contains real scoring logic, not stubs | L2 |
| It is called by the PR pipeline | L3 |
| It receives actual PR data and its score affects the merge gate | L4 |

## 4-Level Artifact Verification

Each artifact is verified at four progressively deeper levels. Higher levels subsume lower ones.

### Level 1: EXISTS

The file is present on disk.

**How to check**: `ls`, `test -f`, Glob tool

**Catches**: Files never created (forgotten writes, planned-but-not-executed steps).

### Level 2: SUBSTANTIVE

The file contains real logic, not placeholder implementations.

**How to check**: Grep for stub indicators (see Stub Detection Patterns below).

**Catches**: Files that exist but contain no real implementation.

### Level 3: WIRED

The artifact is imported AND used by other code in the codebase.

**How to check**:
1. Search for import/require statements referencing the artifact
2. Verify imported symbols are actually called (not just imported)
3. Check that call sites pass real arguments (not empty objects or nil)

**Catches**: Orphaned files created but never integrated.

### Level 4: DATA FLOWS

Real data reaches the artifact and real results come out.

**How to check**:
1. Trace the call chain from entry point to the artifact
2. Verify inputs are not hardcoded empty values (`[]`, `{}`, `""`, `0`)
3. Verify outputs are consumed by downstream code (not discarded)
4. If tests exist, verify test inputs exercise meaningful cases

**Catches**: Integration that exists structurally but passes no real data.

## Stub Detection Patterns

| Pattern | Language | Indicates |
|---------|----------|-----------|
| `return []` | Python, JS/TS | Empty list return -- may be stub |
| `return {}` | Python, JS/TS | Empty dict/object return -- may be stub |
| `return None` | Python | Sole return in non-optional function |
| `return nil, nil` | Go | No value and no error -- likely stub |
| `return nil` | Go | Single nil return where value expected |
| `pass` (as sole body) | Python | Empty function body -- definite stub |
| `...` (Ellipsis as body) | Python | Protocol/abstract stub in concrete code |
| `() => {}` | JS/TS | Empty arrow function -- no-op handler |
| `onClick={() => {}}` | JSX/TSX | Empty click handler -- UI wired but non-functional |
| `throw new Error("not implemented")` | JS/TS | Explicit "not done" marker |
| `panic("not implemented")` | Go | Explicit "not done" marker |
| `raise NotImplementedError` | Python | Explicit "not done" marker |
| `TODO`, `FIXME`, `HACK`, `XXX` | Any | Markers for incomplete work |
| `PLACEHOLDER`, `stub`, `mock` | Any | Self-described placeholder code (in non-test files) |
| `"coming soon"`, `"not yet implemented"` | Any | Placeholder UI/API text |

**Important**: A match does not automatically mean failure. `return []` is sometimes the correct result. Each match requires investigation to confirm whether the pattern is intentional or a stub.

## Verification Depth Guide

Not every artifact needs Level 4. Match depth to artifact type.

| Artifact Type | Minimum Level | Rationale |
|---------------|---------------|-----------|
| Core feature code | Level 4 | Must prove data flows end-to-end |
| Configuration files | Level 1 | Content verified by build/tests |
| Test files | Level 2 | Must be substantive, wiring is implicit |
| Documentation | Level 1 | Existence check only |
| Integration glue (imports, routing) | Level 3 | Wiring is the purpose |
| Bug fixes to existing code | Level 2 + tests | Substance verified, tests cover the fix |

## Report Template

```markdown
## Verification Report

### Goal
[Stated goal as a testable condition]

### Conditions

| Condition | L1 | L2 | L3 | L4 | Status |
|-----------|----|----|----|----|--------|
| [condition] | Y/N | Y/N | Y/N | Y/N/- | VERIFIED / INCOMPLETE -- [reason] |

### Blockers
- [Conditions not verified at required level]

### Stub Scan Results
- [N matches found, M confirmed intentional, K flagged as blockers]

### Verdict
**COMPLETE** / **NOT COMPLETE** -- [summary]
```

Use `-` in a level column when that level does not apply.

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I implemented X" (executor claim) | Claims document what was SAID, not what IS | Verify independently at L1-L4 |
| "File exists, so it's done" | Existence (L1) is not sufficient | Check L2, L3, L4 as needed |
| "It's imported, so it works" | Import without invocation is dead code | Verify the symbol is called with real arguments |
| "Stubs are fine for now" | Stubs in goal-critical artifacts mean the goal is not achieved | Flag as blocker |
| "This is a simple change, deep verification is overkill" | Simple changes with stubs are still incomplete | Apply level appropriate to artifact type |
| "Tests pass so it must be wired correctly" | Tests can pass on stubs if they test the stub behavior | Verify independently of test results |
