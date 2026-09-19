# Adversarial Artifact Verification Methodology

> **Core Principle**: Verify what ACTUALLY exists in the codebase. The verification question is not "did the executor say it's done?" but "does the codebase prove it's done?"

This methodology goes deeper than test/build/lint checks: it verifies that artifacts are real implementations (not stubs), actually integrated (not orphaned), and processing real data (not hardcoded empties). Apply after Steps 1-7 pass, focusing on artifacts that are part of the stated goal.

**Why four levels**: Existence checks (L1) catch forgotten writes. Substance checks (L2) catch stubs. Wiring checks (L3) catch orphaned files. Data flow checks (L4) catch integration that exists structurally but passes no real data. Each level catches a distinct class of premature-completion failure.

## Goal-Backward Framing

**Replace this question**: "Were all tasks completed?"
**Instead ask**: "What must be TRUE for the goal to be achieved?"

This framing prevents task-forward verification that invites executors to confirm their own narrative. Goal-backward verification derives conditions independently from the goal itself, then checks whether the codebase satisfies them. This structural approach counteracts confirmation bias.

**Procedure:**

1. **State the goal as a testable condition**: Express what the user asked for as a concrete, verifiable outcome.
   - Example: "Users can create a PR with quality scoring that blocks merges below threshold"

2. **Decompose into must-be-true conditions**: Break the goal into independent conditions that must ALL hold.
   - "A scoring function exists" (L1)
   - "It contains real scoring logic, not stubs" (L2)
   - "It is called by the PR pipeline" (L3)
   - "It receives actual PR data and its score affects the merge gate" (L4)

3. **Verify each condition independently** at the appropriate level using the 4-Level system below.

4. **Report unverified conditions** as blockers — not "you missed a task" but "this condition is not yet true in the codebase."

## The Four Levels of Artifact Verification

Each artifact produced during the task is verified at four progressively deeper levels. Higher levels subsume lower ones — an artifact at Level 4 has passed Levels 1-3 by definition.

### Level 1: EXISTS — File is present on disk

**Check**: Use Glob or Bash (`ls`, `test -f`) to confirm the file exists.

**What this catches**: Claims about files that were planned but not written to disk (forgotten Write calls, planned-but-not-executed steps).

**What this misses**: Everything else. Existence is necessary but nowhere near sufficient.

---

### Level 2: SUBSTANTIVE — File contains real logic, not placeholder implementations

**Check**: Scan for stub indicators using Grep against changed files. See the **Stub Detection Patterns** table below. A match does not automatically mean failure — `return []` is sometimes correct — but each match requires investigation to confirm the empty return or placeholder is intentional.

**What this catches**: Files that exist but contain no real implementation — the most common form of premature completion claim. This catches stubs disguised as code.

**What this misses**: Code that has logic but wrong logic, or logic that handles only the happy path.

---

### Level 3: WIRED — The artifact is imported AND used by other code in the codebase

**Check**:
1. Search for import/require statements referencing the artifact
2. Verify the imported symbols are actually called (not just imported)
3. Check that the call sites pass real arguments (not empty objects or nil)

```bash
# Example: Check if scoring.py is imported anywhere
grep -r "from.*scoring import\|import.*scoring" --include="*.py" .

# Example: Check if the imported function is actually called
grep -r "calculate_score\|score_package" --include="*.py" .
```

**What this catches**: Orphaned files that were created but left unintegrated. Wiring gaps indicate the component exists structurally but is not active in the system.

**What this misses**: Circular or dead-end wiring where the integration exists but the code path is unreachable at runtime.

---

### Level 4: DATA FLOWS — Real data reaches the artifact and real results come out

**Check**:
1. Trace the call chain from entry point to the artifact
2. Verify inputs are not hardcoded empty values (`[]`, `{}`, `""`, `0`)
3. Verify outputs are consumed by downstream code (not discarded)
4. If tests exist, verify test inputs exercise meaningful cases (not just empty-input tests)

**What this catches**: Integration that exists structurally but passes no real data — functions wired in but fed empty arrays, handlers registered but inactive. Data flow verification confirms the entire chain is active end-to-end.

**What this misses**: Semantic correctness (the data flows but produces wrong results). That is the domain of testing, not verification.

## Stub Detection Patterns for Level 2 (SUBSTANTIVE)

Scan changed files for these patterns to verify they contain real logic, not placeholder implementations:

| Pattern | Language | Indicates |
|---------|----------|-----------|
| `return []` | Python, JS/TS | Empty list return — may be stub if function should compute results |
| `return {}` | Python, JS/TS | Empty dict/object return — may be stub if function should build a structure |
| `return None` | Python | Sole return in non-optional function — likely stub |
| `return nil, nil` | Go | Returning no value and no error — likely stub |
| `return nil` | Go | Single nil return in a function expected to produce a value |
| `pass` (as sole body) | Python | Empty function body — definite stub |
| `...` (Ellipsis as body) | Python | Protocol/abstract stub — should not appear in concrete implementations |
| `() => {}` | JS/TS | Empty arrow function — no-op handler |
| `onClick={() => {}}` | JSX/TSX | Empty click handler — UI wired but non-functional |
| `throw new Error("not implemented")` | JS/TS | Explicit "not done" marker |
| `panic("not implemented")` | Go | Explicit "not done" marker |
| `raise NotImplementedError` | Python | Explicit "not done" marker |
| `TODO`, `FIXME`, `HACK`, `XXX` | Any | Markers for incomplete work (in non-test files) |
| `PLACEHOLDER`, `stub`, `mock` | Any | Self-described placeholder code (in non-test files) |
| `"coming soon"`, `"not yet implemented"` | Any | Placeholder UI/API text |

**Automated scan command** (run against files changed in the current task):

```bash
# Get changed files relative to base branch
changed_files=$(git diff --name-only main...HEAD)

# Scan for stub patterns (adjust base branch as needed)
grep -n -E "(return \[\]|return \{\}|return None|return nil|pass$|raise NotImplementedError|panic\(\"not implemented\"\)|throw new Error\(\"not implemented\"\)|TODO|FIXME|HACK|XXX|PLACEHOLDER)" $changed_files
```

**Review methodology**: Each match requires investigation. If the pattern is intentional (e.g., a function that genuinely returns an empty list), note it in the verification report with rationale. If it is a stub, flag it as a blocker — resolve stubs before declaring task complete.

## Completion Shortcut Scan (Level 2 Supplement)

Beyond stub detection, scan for patterns that indicate premature completion claims:

**Log-only functions** — functions whose entire body is a log/print statement with no real logic:
```bash
# Python: functions that only log
grep -A2 "def " $changed_files | grep -B1 "logging\.\|print(" | grep "def "
```

**Empty handlers** — event handlers that prevent default but do nothing else:
```bash
grep -n "onSubmit.*preventDefault" $changed_files
grep -n "handler.*{\\s*}" $changed_files
```

**Placeholder text** in non-test files:
```bash
grep -n -i "(placeholder|example data|test data|lorem ipsum)" $changed_files
```

**Dead imports** — modules imported but unused:
```bash
# Python: imported but not referenced later in the file
# (manual check — read the file and verify each import is used)
```

---

## Verification Report Format

After completing 4-level verification, produce a structured report. This replaces the simpler verification statement in Step 7 when adversarial verification applies:

```markdown
## Verification Report

### Goal
[Stated goal as a testable condition]

### Conditions

| Condition | L1 | L2 | L3 | L4 | Status |
|-----------|----|----|----|----|--------|
| [condition 1] | Y/N | Y/N | Y/N | Y/N/- | VERIFIED / INCOMPLETE — [reason] |
| [condition 2] | Y/N | Y/N | Y/N | Y/N/- | VERIFIED / INCOMPLETE — [reason] |

### Blockers
- [Any condition not verified at the required level]

### Stub Scan Results
- [N matches found, M confirmed intentional, K flagged as blockers]

### Verdict
**COMPLETE** / **NOT COMPLETE** — [summary]
```

Use `-` in a level column when that level does not apply (e.g., a configuration file does not need L3 wiring checks).

---

## When to Apply Each Level

Not every artifact needs Level 4 verification. Apply only the minimum level required, avoiding unnecessary overhead on trivial changes:

| Artifact Type | Minimum Level | Rationale |
|---------------|---------------|-----------|
| Core feature code (new modules, handlers, logic) | Level 4 | Must prove data flows end-to-end |
| Configuration files, YAML, env | Level 1 | Existence is sufficient — content verified by build/tests |
| Test files | Level 2 | Must be substantive (not empty test stubs), but wiring is implicit |
| Documentation, README, comments | Level 1 | Existence check only |
| Integration glue (imports, routing, wiring) | Level 3 | Must be wired, but data flow verified through the module it connects |
| Bug fixes to existing code | Level 2 + tests | Substance verified, plus tests must cover the fix |
