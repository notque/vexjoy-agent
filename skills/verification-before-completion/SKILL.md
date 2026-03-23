---
name: verification-before-completion
description: |
  Defense-in-depth verification before declaring any task complete. Run tests,
  check build, validate changed files, verify no regressions. Applies 4-level
  adversarial artifact verification (EXISTS > SUBSTANTIVE > WIRED > DATA FLOWS)
  with goal-backward framing. Use before saying "done", "fixed", or "complete"
  on any code change. Use for "verify", "make sure it works", "check before
  committing", or "validate changes". Do NOT use for debugging
  (use systematic-debugging) or code review (use systematic-code-review).
version: 3.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
---

# Verification Before Completion Skill

## Purpose

Enforce rigorous verification before declaring any task complete. Implements defense-in-depth validation with multiple independent checks to catch errors before they reach users. Never say "done", "fixed", or "complete" without running actual verification steps.

## Operator Context

This skill operates as an operator for code quality assurance workflows, configuring Claude's behavior for defensive verification and thorough validation before task completion.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before verification
- **Over-Engineering Prevention**: Only verify what was actually changed. Don't add verification steps that weren't requested. Keep validation focused on the specific changes made.
- **Never declare completion without tests**: ALWAYS run relevant tests before saying "done"
- **Show complete verification output**: Display full test results, build output, validation messages
- **Check all changed files**: Review every file modification with Read tool
- **Validate assumptions**: Verify that what you think happened actually happened
- **No summarization**: Never say "tests pass" - show the actual test output
- **Adversarial Distrust**: Never trust executor claims. Summary claims document what was SAID, not what IS. Verify what ACTUALLY exists in the codebase by inspecting files, running commands, and tracing data flow. WHY: The same agent that writes code has inherent bias toward believing its own output is correct. Structural distrust counteracts this bias.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report verification results concisely without self-congratulation. Show command output rather than describing it. Be factual and direct.
- **Temporary File Cleanup**: Remove any temporary files, test artifacts, or debug outputs created during verification at task completion.
- **Run full test suite**: Execute complete test suite for the affected domain
- **Verify build succeeds**: Run build commands to ensure compilation/bundling works
- **Check for regressions**: Test that existing functionality still works

### Optional Behaviors (OFF unless enabled)
- **Run integration tests**: Execute full integration test suite (slow)
- **Performance testing**: Run benchmarks to check for performance regressions
- **Security scanning**: Run security analysis tools

## What This Skill CAN Do
- Run domain-specific test suites (Python, Go, JavaScript)
- Verify build/compilation succeeds
- Check for unintended changes via git diff
- Validate changed files by reading them
- Detect debug statements and sensitive data left in code
- Perform 4-level artifact verification (EXISTS, SUBSTANTIVE, WIRED, DATA FLOWS)
- Apply goal-backward framing to decompose completion into verifiable conditions
- Run automated stub detection and anti-pattern scans against changed files

## What This Skill CANNOT Do
- Declare task complete without running tests
- Summarize test output (must show full output)
- Skip verification for "simple" changes
- Ignore test failures as "pre-existing"
- Mark complete when any verification step fails

## Instructions

### Step 1: Identify What Changed

Before verification, understand the scope of changes:

```bash
# For git repositories
git diff --name-only
```

Use `git status --short` (not just `git diff`) to capture both modified AND untracked (new) files. New files created during the session are easy to miss in status summaries.

For each changed file:
- Read the file with the Read tool
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

**Output Requirements:**
- Show COMPLETE test output (not "X tests passed")
- Display all test names that ran
- Show any warnings or deprecation notices
- Include execution time

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

If the build fails, stop immediately. Fix build issues before proceeding to any other verification step. Re-run from Step 1 after fixing.

### Step 4: Validate Changed Files

For each changed file, use the Read tool to inspect the actual file contents. Do not rely on memory of what you wrote -- re-read the file to confirm.

For each file verify:
1. **Syntax** is correct (no unterminated strings, mismatched brackets)
2. **Logic** makes sense (no inverted conditions, off-by-one errors)
3. **Formatting** is consistent with surrounding code
4. **Imports/dependencies** are present and correct
5. **No leftover artifacts** (commented-out code, placeholder values, TODO markers)

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

If `git diff` shows changes to files you didn't intend to modify, investigate before proceeding. Unintended changes are a red flag for accidental side effects.

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

**NEVER say:**
- "Should be fixed now"
- "This is working"
- "All done"
- "Tests pass" (without showing output)

**ALWAYS say:**
- "Test if this addresses the issue"
- "Please verify the changes work for your use case"

---

## Adversarial Verification Methodology

> **Core Principle**: Never trust executor claims. The verification question is not "did the executor say it's done?" but "does the codebase prove it's done?"

Steps 1-7 above verify that tests pass, builds succeed, and files contain what you expect. The adversarial methodology below goes deeper: it verifies that artifacts are real implementations (not stubs), actually integrated (not orphaned), and processing real data (not hardcoded empties). Apply this methodology after Steps 1-7 pass, focusing on artifacts that are part of the stated goal.

### Goal-Backward Framing

**Do NOT ask**: "Were all tasks completed?"
**Instead ask**: "What must be TRUE for the goal to be achieved?"

This framing matters because task-forward verification invites the executor to confirm its own narrative. Goal-backward verification derives conditions independently from the goal itself, then checks whether the codebase satisfies them.

**Procedure:**

1. **State the goal as a testable condition**: Express what the user asked for as a concrete, verifiable outcome.
   - Example: "Users can create a PR with quality scoring that blocks merges below threshold"

2. **Decompose into must-be-true conditions**: Break the goal into independent conditions that must ALL hold.
   - "A scoring function exists" (L1)
   - "It contains real scoring logic, not stubs" (L2)
   - "It is called by the PR pipeline" (L3)
   - "It receives actual PR data and its score affects the merge gate" (L4)

3. **Verify each condition independently** at the appropriate level using the 4-Level system below.

4. **Report unverified conditions** as blockers -- not "you missed a task" but "this condition is not yet true in the codebase."

### 4-Level Artifact Verification

Each artifact produced during the task is verified at four progressively deeper levels. Higher levels subsume lower ones -- an artifact at Level 4 has passed Levels 1-3 by definition.

**WHY four levels**: Existence checks (L1) catch forgotten writes. Substance checks (L2) catch stubs. Wiring checks (L3) catch orphaned files. Data flow checks (L4) catch integration that exists structurally but passes no real data. Each level catches a distinct class of premature-completion failure.

#### Level 1: EXISTS

The file is present on disk.

**Check**: Use Glob or Bash (`ls`, `test -f`) to confirm the file exists.

**What this catches**: Claims about files that were never created (forgotten Write calls, planned-but-not-executed steps).

**What this misses**: Everything else. Existence is necessary but nowhere near sufficient.

#### Level 2: SUBSTANTIVE

The file contains real logic, not placeholder implementations.

**Check**: Scan for stub indicators using Grep against changed files. See the **Stub Detection Patterns** table below.

**What this catches**: Files that exist but contain no real implementation -- the most common form of premature completion claim.

**What this misses**: Code that has logic but wrong logic, or logic that handles only the happy path.

#### Level 3: WIRED

The artifact is imported AND used by other code in the codebase.

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

**What this catches**: Orphaned files that were created but never integrated.

**What this misses**: Circular or dead-end wiring where the integration exists but the code path is never reached at runtime.

#### Level 4: DATA FLOWS

Real data reaches the artifact and real results come out.

**Check**:
1. Trace the call chain from entry point to the artifact
2. Verify inputs are not hardcoded empty values (`[]`, `{}`, `""`, `0`)
3. Verify outputs are consumed by downstream code (not discarded)
4. If tests exist, verify test inputs exercise meaningful cases (not just empty-input tests)

**What this catches**: Integration that exists structurally but passes no real data -- functions wired in but fed empty arrays, handlers registered but never triggered.

**What this misses**: Semantic correctness (the data flows but produces wrong results). That is the domain of testing, not verification.

### Stub Detection Patterns

Scan changed files for these patterns. A match does not automatically mean failure -- `return []` is sometimes correct -- but each match requires investigation to confirm the empty return or placeholder is intentional.

| Pattern | Language | Indicates |
|---------|----------|-----------|
| `return []` | Python, JS/TS | Empty list return -- may be stub if function should compute results |
| `return {}` | Python, JS/TS | Empty dict/object return -- may be stub if function should build a structure |
| `return None` | Python | Sole return in non-optional function -- likely stub |
| `return nil, nil` | Go | Returning no value and no error -- likely stub |
| `return nil` | Go | Single nil return in a function expected to produce a value |
| `pass` (as sole body) | Python | Empty function body -- definite stub |
| `...` (Ellipsis as body) | Python | Protocol/abstract stub -- should not appear in concrete implementations |
| `() => {}` | JS/TS | Empty arrow function -- no-op handler |
| `onClick={() => {}}` | JSX/TSX | Empty click handler -- UI wired but non-functional |
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

Review each match. If the pattern is intentional (e.g., a function that genuinely returns an empty list), note it in the verification report. If it is a stub, flag it as a blocker.

### Anti-Pattern Scan

Beyond stub detection, scan for patterns that correlate with premature completion claims:

**Log-only functions** -- functions whose entire body is a log/print statement with no real logic:
```bash
# Python: functions that only log
grep -A2 "def " $changed_files | grep -B1 "logging\.\|print(" | grep "def "
```

**Empty handlers** -- event handlers that prevent default but do nothing else:
```bash
grep -n "onSubmit.*preventDefault" $changed_files
grep -n "handler.*{\\s*}" $changed_files
```

**Placeholder text** in non-test files:
```bash
grep -n -i "(placeholder|example data|test data|lorem ipsum)" $changed_files
```

**Dead imports** -- modules imported but never used:
```bash
# Python: imported but not referenced later in the file
# (manual check -- read the file and verify each import is used)
```

### Verification Report Format

After completing 4-level verification, produce a structured report. This replaces the simpler verification statement in Step 7 when adversarial verification applies.

```markdown
## Verification Report

### Goal
[Stated goal as a testable condition]

### Conditions

| Condition | L1 | L2 | L3 | L4 | Status |
|-----------|----|----|----|----|--------|
| [condition 1] | Y/N | Y/N | Y/N | Y/N/- | VERIFIED / INCOMPLETE -- [reason] |
| [condition 2] | Y/N | Y/N | Y/N | Y/N/- | VERIFIED / INCOMPLETE -- [reason] |

### Blockers
- [Any condition not verified at the required level]

### Stub Scan Results
- [N matches found, M confirmed intentional, K flagged as blockers]

### Verdict
**COMPLETE** / **NOT COMPLETE** -- [summary]
```

Use `-` in a level column when that level does not apply (e.g., a configuration file does not need L3 wiring checks).

### When to Apply Each Level

Not every artifact needs Level 4 verification. Applying deep verification to trivial changes wastes resources.

| Artifact Type | Minimum Level | Rationale |
|---------------|---------------|-----------|
| Core feature code (new modules, handlers, logic) | Level 4 | Must prove data flows end-to-end |
| Configuration files, YAML, env | Level 1 | Existence is sufficient -- content verified by build/tests |
| Test files | Level 2 | Must be substantive (not empty test stubs), but wiring is implicit |
| Documentation, README, comments | Level 1 | Existence check only |
| Integration glue (imports, routing, wiring) | Level 3 | Must be wired, but data flow verified through the module it connects |
| Bug fixes to existing code | Level 2 + tests | Substance verified, plus tests must cover the fix |

## Error Handling

**Error: "Tests failed after changes"**
- DO NOT declare task complete
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
- Recommend writing tests (but don't require unless user requests)
- Perform extra manual validation
- Document that changes are untested

**Error: "Cannot run tests (missing dependencies)"**
- Document what's missing
- Attempt alternative verification (syntax checks, manual review)
- Be explicit about verification limitations

**Error: "Stub patterns detected in changed files"**
- Review each match individually -- some stubs are intentional (e.g., `return []` when empty list is the correct result)
- For confirmed stubs: flag as blocker, DO NOT declare task complete
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

## Common Anti-Patterns

### Anti-Pattern 1: Claiming Success Without Running Tests

**Bad:**
```
User: Did you fix the bug?
Assistant: Yes, I've fixed the authentication issue. The code looks good now.
```

No actual verification performed. Assumptions about correctness without evidence. The user will discover the issue wasn't actually fixed.

**Good:**
```
User: Did you fix the bug?
Assistant: I've made changes to address the authentication issue. Let me verify:

$ pytest tests/test_auth.py -v
============================= test session starts ==============================
collected 12 items

tests/test_auth.py::test_login_success PASSED                            [  8%]
tests/test_auth.py::test_login_failure PASSED                            [ 16%]
[... complete output ...]
============================= 12 passed in 2.43s ===============================

Verification Complete - all authentication tests pass.
Test if this addresses the issue.
```

### Anti-Pattern 2: Summarizing Test Results

**Bad:**
```
I ran the tests and they all passed! Everything is working now.
```

No evidence provided. Can't verify which tests actually ran. Hides important warnings or partial failures. The user cannot validate the verification.

**Good:** Show the complete, unabbreviated test output:
```
$ go test ./... -v
=== RUN   TestUserCreate
--- PASS: TestUserCreate (0.01s)
=== RUN   TestUserUpdate
--- PASS: TestUserUpdate (0.02s)
=== RUN   TestUserDelete
--- PASS: TestUserDelete (0.01s)
PASS
ok      github.com/example/users    0.123s
```

### Anti-Pattern 3: Ignoring Failed Tests

**Bad:**
```
The tests mostly passed, with just 2 failures in unrelated tests.
Those were probably already failing, so the changes are good to go.
```

Assumes failures are pre-existing without verification. Could be introducing new failures. Degrades test suite quality over time.

**Good:** Investigate ALL failures before claiming completion:
```
$ pytest -v
...
tests/test_api.py::test_create_user FAILED
tests/test_api.py::test_update_user FAILED
[10 passed, 2 failed]

Verification FAILED - 2 tests are failing.

Let me check if these are pre-existing:
$ git stash
$ pytest tests/test_api.py::test_create_user -v
PASSED

These failures were introduced by my changes. Fixing before completion.
```

### Anti-Pattern 4: Not Reading Changed Files

**Bad:**
```
I've updated the authentication module. Tests pass. Done!
```

Didn't verify what was actually written to the file. Could have syntax errors tests don't catch, debug statements, or incomplete changes.

**Good:** Always read modified files to confirm changes:
```
I've updated the authentication module. Let me verify what was changed:

$ Read /home/project/auth.py
[Shows file contents - verify changes are correct]

Changes confirmed:
- Added password hashing with bcrypt
- Implemented token expiration check

Now running tests:
$ pytest tests/test_auth.py -v
[... complete test output ...]

Verification Complete
- Changed files reviewed: auth.py (syntax valid, logic correct)
- Tests: 15 passed in 1.23s

Test if this addresses the issue.
```

### Anti-Pattern 5: Trusting Executor Summary Claims

**Bad:**
```
Executor: "I implemented the scoring module, added tests, and wired it into the pipeline."
Verifier: Great, scoring module is done. Moving on.
```

Accepted the claim at face value. Never checked whether the file exists, contains real logic, is imported, or processes real data. Summary claims document what was SAID, not what IS.

**Good:** Independently verify every claim at the appropriate level:
```
Executor: "I implemented the scoring module, added tests, and wired it into the pipeline."
Verifier: Let me verify each claim independently.

L1 EXISTS: ls scoring/calculator.py -- file exists, confirmed.
L2 SUBSTANTIVE: Reading file... contains calculate_score() with real logic (weighted average across metrics). No stubs detected.
L3 WIRED: grep -r "from scoring" . -- imported in pipeline/pr_check.py. Checking usage... calculate_score() called on line 47. Confirmed.
L4 DATA FLOWS: Tracing call site... calculate_score(pr_data.files, pr_data.comments) -- receives real PR data, not empty values. Return value used in gate check on line 52. Confirmed.

All 4 levels verified for scoring module.
```

### Anti-Pattern 6: Existence-Only Verification

**Bad:**
```
Verifier: Let me check -- scoring.py exists, tests exist, pipeline file exists. All artifacts present. Verified!
```

Checked Level 1 (EXISTS) only. Files can exist but be stubs, orphaned, or processing no real data. Existence is necessary but nowhere near sufficient.

**Good:** Verify at the appropriate depth per artifact type:
```
Verifier: scoring.py exists (L1). Checking substance...
- Reading file: contains calculate_score() with weighted scoring logic (L2 pass)
- grep for imports: imported in pr_pipeline.py line 12 (L3 pass)
- Tracing data flow: called with pr.changed_files on line 45 (L4 pass)
```

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Adversarial Verification](../shared-patterns/adversarial-verification.md) - 4-level artifact verification methodology (reusable)

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Tests pass" (without showing output) | Claim without evidence is unverifiable | Show complete test output |
| "Simple change, no need to verify" | Simple changes cause complex bugs | Run full verification regardless |
| "Those failures were pre-existing" | Assumption without verification | Check with git stash to confirm |
| "Code looks correct" | Looking correct ≠ being correct | Run tests and read changed files |
| "I implemented X" (executor claim) | Summary claims document what was SAID, not what IS | Verify independently at L1-L4 |
| "File exists, so it's done" | Existence (L1) is necessary but not sufficient | Check substance (L2), wiring (L3), data flow (L4) |
| "It's imported, so it works" | Import without invocation is dead code | Verify the symbol is called with real arguments |
| "Stubs are fine for now" | Stubs in goal-critical artifacts mean the goal is not achieved | Flag as blocker unless explicitly scoped out |
