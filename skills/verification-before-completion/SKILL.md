---
name: verification-before-completion
description: |
  Defense-in-depth verification before declaring any task complete. Run tests,
  check build, validate changed files, verify no regressions. Use before
  saying "done", "fixed", or "complete" on any code change. Use for "verify",
  "make sure it works", "check before committing", or "validate changes".
  Do NOT use for debugging (use systematic-debugging) or code review
  (use systematic-code-review).
version: 2.0.0
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

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Tests pass" (without showing output) | Claim without evidence is unverifiable | Show complete test output |
| "Simple change, no need to verify" | Simple changes cause complex bugs | Run full verification regardless |
| "Those failures were pre-existing" | Assumption without verification | Check with git stash to confirm |
| "Code looks correct" | Looking correct ≠ being correct | Run tests and read changed files |
