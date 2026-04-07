---
name: verification-before-completion
description: "Defense-in-depth verification before declaring any task complete."
version: 3.0.0
user-invocable: false
success-criteria:
  - "All tests pass (full suite, not just changed files)"
  - "Build succeeds without errors or warnings"
  - "Changed files validated against task requirements"
  - "No stub patterns (TODO, FIXME, pass, not implemented) in new code"
  - "Artifacts exist at expected paths (4-level verification)"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "verify completion"
    - "run tests"
    - "check build"
    - "defense in depth"
    - "final verification"
  category: process
---

# Verification Before Completion Skill

## Overview

Enforce rigorous, adversarial verification before declaring any task complete. Implements defense-in-depth validation with multiple independent checks to catch errors before they reach users. The core principle: verify independently rather than trusting executor claims (what was SAID) — verify what ACTUALLY exists in the codebase through testing, inspection, and data-flow tracing.

This skill prevents the most common form of premature completion: claiming success without running tests, summarizing results instead of showing evidence, or trusting code that "looks right" without verification.

## Instructions

### Step 1: Identify What Changed

Before verification, understand the scope of changes:

```bash
# For git repositories
git diff --name-only
```

**Why:** Use `git status --short` (not just `git diff`) to capture both modified AND untracked (new) files. New files created during the session are easy to miss in status summaries. Over-engineering prevention requires limiting scope to what was actually changed — limit verification to what was actually changed. Focus only on the specific changes made.

For each changed file:
- Read the file with the Read tool to validate the actual contents
- Summarize what changed
- Identify affected systems/modules and dependencies

Report separately:
- **New files**: [files with `??` or `A` status in git]
- **Modified files**: [files with `M` status]

### Step 2: Run Domain-Specific Tests

Run the appropriate test suite and show **complete** output (not summaries):

| Language | Test Command | Build Command | Lint Command |
|----------|-------------|---------------|-------------|
| Python | `pytest -v` | `python -m py_compile {files}` | `ruff check {files}` |
| Go | `go test ./... -v -race` | `go build ./...` | `golangci-lint run ./...` |
| JavaScript | `npm test` | `npm run build` | `npm run lint` |
| TypeScript | `npm test` | `npx tsc --noEmit` | `npm run lint` |
| Rust | `cargo test` | `cargo build` | `cargo clippy` |

**Why full test suite, not just changed files**: ALWAYS run relevant tests before saying "done". The same agent that writes code has inherent bias toward believing its own output is correct. Running the full suite catches regressions and unintended side effects that focused testing misses.

**Output Requirements:**
- Show COMPLETE test output (not "X tests passed")
- Display all test names that ran
- Show any warnings or deprecation notices
- Include execution time

**Critical constraint**: Show test output when reporting test results. Summary claims document what was SAID, not what IS. Evidence-based reporting is required.

### Step 3: Verify Build/Compilation

Run the build command from the table above and show the full output. Confirm:
- Build completes without errors
- No new warnings introduced
- Output artifacts are created (if applicable)

```bash
# Example: Go project
go build ./...

# Example: Python - check syntax of changed files
python -m py_compile path/to/changed_file.py

# Example: JavaScript/TypeScript
npm run build
```

**Critical gate**: If the build fails, stop immediately. Fix build issues before proceeding to any other verification step. A failed build is a blocker that supersedes all other checks. Re-run from Step 1 after fixing. This prevents declaring "done" when the code doesn't compile.

### Step 4: Validate Changed Files

For each changed file, use the Read tool to inspect the actual file contents. **Validate assumptions**: Re-read the file to confirm the actual contents — re-read the file to confirm. Verify that what you think happened actually happened.

For each file verify:
1. **Syntax** is correct (no unterminated strings, mismatched brackets)
2. **Logic** makes sense (no inverted conditions, off-by-one errors)
3. **Formatting** is consistent with surrounding code
4. **Imports/dependencies** are present and correct
5. **No leftover artifacts** (commented-out code, placeholder values, TODO markers)

This step counteracts confirmation bias where executors believe their own edits are correct without evidence.

### Step 5: Check for Unintended Changes

```bash
# Check git diff for unexpected changes
git diff

# Look for debug code that should be removed
grep -r "console.log\|print(\|fmt.Println\|debugger\|pdb.set_trace" {changed_files}

# Check for TODO/FIXME comments that should be resolved
grep -r "TODO\|FIXME\|HACK\|XXX" {changed_files}

# Verify no sensitive data
grep -r "password\|secret\|api_key\|token" {changed_files}
```

**Why this matters**: If `git diff` shows changes to files you didn't intend to modify, investigate before proceeding. Unintended changes are a red flag for accidental side effects. Detecting this early prevents silent regressions that reach users.

**Constraint**: No stub patterns (TODO, FIXME, pass, not implemented) should remain in new code created by the task.

### Step 6: Review Verification Checklist

**Core Verification (Required):**
- [ ] Tests pass (actual output shown)
- [ ] Build succeeds (actual output shown)
- [ ] Changed files reviewed (Read tool used)
- [ ] No unintended changes (diff checked)
- [ ] No debug/console statements left
- [ ] No sensitive data exposed

**Extended Verification (Recommended):**
- [ ] Documentation updated if needed
- [ ] No new warnings introduced
- [ ] Error handling adequate
- [ ] Backwards compatibility maintained

### Step 7: Final Verification Statement

**ONLY AFTER all checks pass, provide verification statement:**

```
Verification Complete

**Tests Run:**
{paste actual test output}

**Build Status:**
{paste actual build output}

**Files Verified:**
- {file1}: Reviewed, syntax valid, logic correct
- {file2}: Reviewed, syntax valid, logic correct

**Checklist Status:** X/X core checks passed

Test if this addresses the issue.
```

**Critical constraints on communication:**
- Show test output when reporting test results. Show complete verification output, not summaries.
- Report verification results concisely without self-congratulation. Show command output rather than describing it.
- Verify that what you think happened actually happened. Use Read tool on changed files, not memory.

**Replace with:**
- "Should be fixed now"
- "This is working"
- "All done"
- "Tests pass" (without showing output)

**ALWAYS say:**
- "Test if this addresses the issue"
- "Please verify the changes work for your use case"

---

## 4-Level Adversarial Artifact Verification Methodology

> **Core Principle**: Verify what ACTUALLY exists in the codebase. The verification question is not "did the executor say it's done?" but "does the codebase prove it's done?"

Steps 1-7 above verify that tests pass, builds succeed, and files contain what you expect. The adversarial methodology below goes deeper: it verifies that artifacts are real implementations (not stubs), actually integrated (not orphaned), and processing real data (not hardcoded empties). Apply this methodology after Steps 1-7 pass, focusing on artifacts that are part of the stated goal.

**Why four levels**: Existence checks (L1) catch forgotten writes. Substance checks (L2) catch stubs. Wiring checks (L3) catch orphaned files. Data flow checks (L4) catch integration that exists structurally but passes no real data. Each level catches a distinct class of premature-completion failure.

### Goal-Backward Framing

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

### The Four Levels of Artifact Verification

Each artifact produced during the task is verified at four progressively deeper levels. Higher levels subsume lower ones — an artifact at Level 4 has passed Levels 1-3 by definition.

#### Level 1: EXISTS — File is present on disk

**Check**: Use Glob or Bash (`ls`, `test -f`) to confirm the file exists.

**What this catches**: Claims about files that were planned but not written to disk (forgotten Write calls, planned-but-not-executed steps).

**What this misses**: Everything else. Existence is necessary but nowhere near sufficient.

---

#### Level 2: SUBSTANTIVE — File contains real logic, not placeholder implementations

**Check**: Scan for stub indicators using Grep against changed files. See the **Stub Detection Patterns** table below. A match does not automatically mean failure — `return []` is sometimes correct — but each match requires investigation to confirm the empty return or placeholder is intentional.

**What this catches**: Files that exist but contain no real implementation — the most common form of premature completion claim. This catches stubs disguised as code.

**What this misses**: Code that has logic but wrong logic, or logic that handles only the happy path.

---

#### Level 3: WIRED — The artifact is imported AND used by other code in the codebase

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

#### Level 4: DATA FLOWS — Real data reaches the artifact and real results come out

**Check**:
1. Trace the call chain from entry point to the artifact
2. Verify inputs are not hardcoded empty values (`[]`, `{}`, `""`, `0`)
3. Verify outputs are consumed by downstream code (not discarded)
4. If tests exist, verify test inputs exercise meaningful cases (not just empty-input tests)

**What this catches**: Integration that exists structurally but passes no real data — functions wired in but fed empty arrays, handlers registered but inactive. Data flow verification confirms the entire chain is active end-to-end.

**What this misses**: Semantic correctness (the data flows but produces wrong results). That is the domain of testing, not verification.

### Stub Detection Patterns for Level 2 (SUBSTANTIVE)

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

### Completion Shortcut Scan (Level 2 Supplement)

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

### Verification Report Format

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

### When to Apply Each Level

Not every artifact needs Level 4 verification. Apply only the minimum level required, avoiding unnecessary overhead on trivial changes:

| Artifact Type | Minimum Level | Rationale |
|---------------|---------------|-----------|
| Core feature code (new modules, handlers, logic) | Level 4 | Must prove data flows end-to-end |
| Configuration files, YAML, env | Level 1 | Existence is sufficient — content verified by build/tests |
| Test files | Level 2 | Must be substantive (not empty test stubs), but wiring is implicit |
| Documentation, README, comments | Level 1 | Existence check only |
| Integration glue (imports, routing, wiring) | Level 3 | Must be wired, but data flow verified through the module it connects |
| Bug fixes to existing code | Level 2 + tests | Substance verified, plus tests must cover the fix |

## Error Handling

**Error: "Tests failed after changes"**
- Resolve stubs before declaring task complete
- Show full test failure output
- Analyze what went wrong
- Fix issues and re-run full verification

**Error: "Build failed"**
- Stop immediately
- Show complete build error output
- Fix build issues before proceeding
- Re-run verification from Step 1

**Error: "No tests exist for changed code"**
- Acknowledge lack of test coverage
- Recommend writing tests (but include only if user requests)
- Perform extra manual validation
- Document that changes are untested

**Error: "Cannot run tests (missing dependencies)"**
- Document what's missing
- Attempt alternative verification (syntax checks, manual review)
- Be explicit about verification limitations

**Error: "Stub patterns detected in changed files"**
- Review each match individually -- some stubs are intentional (e.g., `return []` when empty list is the correct result)
- For confirmed stubs: flag as blocker, Resolve stubs before declaring task complete
- For intentional patterns: document in verification report with rationale
- If unsure: treat as stub (false positive is safer than false negative)

**Error: "Artifact exists but is not wired (Level 3 failure)"**
- Identify what should import/reference the artifact
- Check if the wiring was planned but not executed (common in multi-step tasks)
- Flag as blocker with specific guidance: "File X exists but is not imported by Y"

**Error: "Data flow gap detected (Level 4 failure)"**
- Trace the call chain to identify where real data stops flowing
- Common cause: function called with hardcoded `[]` or `{}` instead of computed values
- Flag as blocker: "Function X is called but receives empty data at call site Y"

The error handling section above integrates constraints inline: "Stop immediately" for build failures reinforces the critical gate, "flag as blocker, Resolve stubs before declaring task complete" for confirmed stubs enforces the no-stubs constraint, and detailed guidance on each error prevents rationalization.

## References

**Core Principles**
- **Adversarial distrust**: Verify independently. The same agent that writes code has inherent bias toward believing its own output is correct. Structural distrust in the verification process counteracts this bias.
- **Evidence over claims**: Summary claims document what was SAID, not what IS. Always show actual test output, build logs, and file contents. Verification without evidence is unverifiable.
- **Goal-backward framing**: Derive verification conditions from what must be true for the goal, not from executor task lists. This prevents executors from confirming their own narrative.
- **4-level artifact verification**: EXISTS → SUBSTANTIVE → WIRED → DATA FLOWS. Each level catches distinct classes of premature-completion failures.

**Key Constraints (Integrated Above)**
- Run tests before declaring completion
- Show complete verification output (not summaries or "X tests passed")
- Check all changed files using Read tool (not memory)
- Show actual test output when reporting test results
- Run full test suite for affected domain (not just changed files)
- Flag any stub patterns as blockers — mark complete only after full verification
- Build failures are gates that stop all other verification
- Over-engineering prevention: only verify what was actually changed
