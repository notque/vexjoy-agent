---
name: verification-before-completion
description: "Defense-in-depth verification before declaring any task complete."
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
  pairs_with:
    - systematic-code-review
    - with-anti-rationalization
---

# Verification Before Completion Skill

Enforce adversarial verification before declaring any task complete. Defense-in-depth validation with multiple independent checks. Core principle: verify what ACTUALLY exists through testing, inspection, and data-flow tracing -- do not trust executor claims.

Prevents premature completion: claiming success without running tests, summarizing instead of showing evidence, trusting code that "looks right."

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `adversarial-methodology.md` | Loads detailed guidance from `adversarial-methodology.md`. |
| checklist-driven work | `checklist.md` | Loads detailed guidance from `checklist.md`. |
| example-driven tasks | `verification-examples.md` | Loads detailed guidance from `verification-examples.md`. |

## Instructions

> **Opus 4.7 override:** Run the command. Do not reason about whether it would pass. Execute the check, paste the exit code and relevant output. A verification without an observed tool result is a guess.

### Step 1: Identify What Changed

```bash
git diff --name-only
```

Use `git status --short` (not just `git diff`) to capture both modified AND untracked files. Limit verification to what was actually changed.

For each changed file:
- Read with Read tool to validate actual contents
- Summarize what changed
- Identify affected systems/modules and dependencies

Report separately:
- **New files**: [`??` or `A` status]
- **Modified files**: [`M` status]

### Step 2: Run Domain-Specific Tests

Run appropriate suite, show **complete** output (not summaries):

| Language | Test Command | Build Command | Lint Command |
|----------|-------------|---------------|-------------|
| Python | `pytest -v` | `python -m py_compile {files}` | `ruff check {files}` |
| Go | `go test ./... -v -race` | `go build ./...` | `golangci-lint run ./...` |
| JavaScript | `npm test` | `npm run build` | `npm run lint` |
| TypeScript | `npm test` | `npx tsc --noEmit` | `npm run lint` |
| Rust | `cargo test` | `cargo build` | `cargo clippy` |

ALWAYS run full test suite. The agent that writes code has inherent bias toward believing its own output. Full suite catches regressions that focused testing misses.

**Output requirements**: Show COMPLETE test output, all test names, warnings, execution time. Summary claims document what was SAID, not what IS.

### Step 3: Verify Build/Compilation

Run build command, show full output. Confirm: no errors, no new warnings, output artifacts created (if applicable).

**Critical gate**: Build failure is a blocker. Fix before proceeding. Re-run from Step 1 after fixing.

### Step 4: Validate Changed Files

Read each changed file with Read tool. Verify:
1. Syntax correct (no unterminated strings, mismatched brackets)
2. Logic sound (no inverted conditions, off-by-one errors)
3. Formatting consistent with surrounding code
4. Imports/dependencies present and correct
5. No leftover artifacts (commented-out code, placeholders, TODO markers)

### Step 5: Check for Unintended Changes

```bash
git diff

# Debug code
grep -r "console.log\|print(\|fmt.Println\|debugger\|pdb.set_trace" {changed_files}

# Unresolved stubs
grep -r "TODO\|FIXME\|HACK\|XXX" {changed_files}

# Sensitive data
grep -r "password\|secret\|api_key\|token" {changed_files}
```

If `git diff` shows changes to unintended files, investigate before proceeding. No stub patterns should remain in new code.

### Step 6: Review Verification Checklist

**Core (Required):**
- [ ] Tests pass (actual output shown)
- [ ] Build succeeds (actual output shown)
- [ ] Changed files reviewed (Read tool used)
- [ ] No unintended changes (diff checked)
- [ ] No debug/console statements left
- [ ] No sensitive data exposed

**Extended (Recommended):**
- [ ] Documentation updated if needed
- [ ] No new warnings introduced
- [ ] Error handling adequate
- [ ] Backwards compatibility maintained

> See `references/checklist.md` for domain-specific checklists (Python, Go, JavaScript, Database, Infrastructure).

### Step 7: Final Verification Statement

ONLY after all checks pass:

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

Show complete output, not summaries. No self-congratulation. Use Read tool on changed files, not memory.

ALWAYS say: "Test if this addresses the issue" or "Please verify the changes work for your use case."

---

## 4-Level Adversarial Artifact Verification

> See `references/adversarial-methodology.md` for complete methodology: goal-backward framing, all four levels, stub detection with automated scan, verification report format, and "when to apply each level" table.

Apply after Steps 1-7 pass. Focuses on artifacts that are part of the stated goal.

- **L1 EXISTS**: File present on disk (catches forgotten writes)
- **L2 SUBSTANTIVE**: Contains real logic, not stubs (catches placeholders)
- **L3 WIRED**: Imported and used by other code (catches orphaned files)
- **L4 DATA FLOWS**: Real data reaches artifact and real results come out (catches dead integration)

## Error Handling

**"Tests failed after changes"** -- Show full failure output. Analyze. Fix and re-run full verification.

**"Build failed"** -- Stop immediately. Show error output. Fix. Re-run from Step 1.

**"No tests exist for changed code"** -- Acknowledge. Recommend writing tests (only if user requests). Perform extra manual validation. Document that changes are untested.

**"Cannot run tests (missing dependencies)"** -- Document what's missing. Attempt alternative verification (syntax checks, manual review). Be explicit about limitations.

**"Stub patterns detected"** -- Review each match. Confirmed stubs: flag as blocker. Intentional patterns (e.g., `return []` as correct result): document with rationale. If unsure: treat as stub.

**"Artifact exists but not wired (L3 failure)"** -- Identify what should import it. Check if wiring was planned but not executed. Flag: "File X exists but is not imported by Y."

**"Data flow gap (L4 failure)"** -- Trace call chain to find where real data stops flowing. Common: function called with hardcoded `[]`/`{}` instead of computed values. Flag: "Function X called but receives empty data at Y."

## References

**Core Principles**
- **Adversarial distrust**: Verify independently. Code authors have inherent bias.
- **Evidence over claims**: Show actual test output, build logs, file contents.
- **Goal-backward framing**: Derive verification from what must be true for the goal, not from executor task lists.
- **4-level verification**: EXISTS, SUBSTANTIVE, WIRED, DATA FLOWS.

**Reference Files**
- `references/adversarial-methodology.md` -- 4-level verification, stub detection, goal-backward framing
- `references/checklist.md` -- Domain-specific checklists (Python, Go, JS, Database, Infrastructure)
- `references/verification-examples.md` -- Good vs bad verification examples per language
