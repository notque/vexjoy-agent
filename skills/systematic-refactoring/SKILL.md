---
name: systematic-refactoring
description: |
  Safe, phase-gated refactoring: CHARACTERIZE with tests, PLAN incremental
  steps, EXECUTE one change at a time, VALIDATE no regressions. Use when
  renaming functions/variables, extracting modules, changing signatures,
  restructuring directories, or consolidating duplicate code. Use for
  "refactor", "rename", "extract", "restructure", or "migrate pattern".
  Do NOT use for bug fixes or new feature implementation.
version: 2.0.0
user-invocable: false
promoted_to: pipelines/systematic-refactoring
success-criteria:
  - "Characterization tests pass before and after changes"
  - "Zero references to old names remaining in codebase"
  - "Full test suite passes after each incremental step"
  - "No behavioral changes (only structural improvements)"
  - "All import paths and cross-references updated"
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "refactor safely"
    - "rename symbol"
    - "extract function"
    - "refactor"
    - "simplify this"
    - "restructure code"
    - "reduce complexity"
    - "split this file"
    - "restructure"
    - "move to separate file"
  category: process
---

> **Note**: This skill has been promoted to a pipeline. See `pipelines/systematic-refactoring/SKILL.md` for the phase-gated version.

# Systematic Refactoring Skill

Perform safe, verifiable refactoring through explicit phases. Each phase has gates that prevent common refactoring mistakes: breaking behavior, incomplete migrations, or orphaned code.

## Instructions

Before starting any refactoring work, read and follow the repository's CLAUDE.md because it may contain project-specific conventions that affect how refactoring should be done (e.g., import ordering, naming conventions, test commands).

Only refactor what is directly requested. Do not add speculative improvements or "while we're here" changes because scope creep during refactoring makes failures harder to diagnose and rollbacks harder to execute. If a bug is discovered during refactoring, finish the refactoring first and address the bug in a separate commit because mixing structural changes with behavioral changes makes it impossible to tell which caused a test failure.

### Phase 1: CHARACTERIZE

**Goal**: Establish a test safety net that proves current behavior before any code is touched.

**Gate**: Tests exist that verify current behavior. Do not proceed to Phase 2 until all characterization tests pass.

Write characterization tests before making any changes because refactoring without tests is flying blind -- you have no proof that behavior was preserved. Even for a "small rename," grep for all references including string literals, config files, and dynamic lookups because small renames break string refs and configs that static analysis misses.

```
═══════════════════════════════════════════════════════════════
 PHASE 1: CHARACTERIZE
═══════════════════════════════════════════════════════════════

 Target Code:
   - File: [path/to/file.ext]
   - Element: [function/class/module being refactored]
   - Lines: [start-end]

 Current Behavior:
   - Purpose: [what it does]
   - Inputs: [parameters/dependencies]
   - Outputs: [return values/side effects]
   - Callers: [N files/functions use this]

 Existing Tests:
   - Coverage: [X% of target code]
   - Test files: [list of relevant test files]

 Characterization Tests Written:
   - [ ] Happy path covered
   - [ ] Edge cases covered
   - [ ] Error cases covered
   - [ ] Integration points covered

 Test Execution:
   $ [test command]
   Result: ALL PASS (required to proceed)

 CHARACTERIZE complete. Proceeding to PLAN...
═══════════════════════════════════════════════════════════════
```

**Actions in this phase:**
1. Read the code to be refactored completely
2. Find all callers with Grep -- check string literals, config files, and reflection-based references in addition to direct code references
3. Run existing tests, note coverage gaps
4. Write characterization tests for uncovered behavior
5. Verify all tests pass

### Phase 2: PLAN

**Goal**: Define a sequence of atomic changes, each independently testable, with rollback points.

**Gate**: Clear sequence of atomic changes with rollback points defined. Do not proceed to Phase 3 until every step is small enough to be a single commit.

Break the work into the smallest possible atomic changes because one large commit touching many files makes it impossible to bisect which change caused an issue and guarantees merge conflicts in active codebases. Every step must preserve the external API unless the user explicitly requested an API change, because callers outside the codebase may depend on the current interface.

```
═══════════════════════════════════════════════════════════════
 PHASE 2: PLAN
═══════════════════════════════════════════════════════════════

 Refactoring Type: [rename | extract | restructure | migrate]

 Target State:
   - [Description of end state]

 Incremental Steps:
   1. [First atomic change]
      - Files affected: [list]
      - Risk: LOW/MEDIUM/HIGH
      - Rollback: [how to undo]

   2. [Second atomic change]
      - Files affected: [list]
      - Risk: LOW/MEDIUM/HIGH
      - Rollback: [how to undo]

   ... [continue for all steps]

 Dependencies:
   Step 2 depends on: Step 1
   Step 3 depends on: Step 2
   ...

 Risks:
   - [Potential issue 1]: [mitigation]
   - [Potential issue 2]: [mitigation]

 PLAN complete. Proceeding to EXECUTE...
═══════════════════════════════════════════════════════════════
```

**Actions in this phase:**
1. Define the exact end state
2. Break into smallest possible atomic changes
3. Identify dependencies between steps
4. Define rollback procedure for each step
5. Estimate risk level for each step

### Phase 3: EXECUTE

**Goal**: Apply each planned change one at a time, running the full test suite after every step.

**Gate**: Tests pass after each atomic change. If any test fails, stop, rollback, and investigate before proceeding.

Make exactly one atomic change per step because multiple simultaneous changes make it impossible to isolate which change broke a test. Run the full test suite after each step, not just the tests you think are relevant, because refactoring should never change behavior and the full suite is your proof. Commit at each stable point so that every commit represents a working state and you can bisect or rollback to any intermediate point.

When updating callers, migrate every single reference before removing old code because leaving old code alongside new "for backward compatibility" means code exists in two places indefinitely, future changes require double updates, and the old code becomes stale and buggy. Use Grep exhaustively to confirm zero remaining references at each migration step.

```
═══════════════════════════════════════════════════════════════
 PHASE 3: EXECUTE - Step [N] of [Total]
═══════════════════════════════════════════════════════════════

 Step [N]: [description]

 Changes Made:
   - [file1.ext]: [specific change]
   - [file2.ext]: [specific change]

 Test Execution:
   $ [test command]
   Result: PASS / FAIL

 If PASS:
   Step [N] complete
   Commit: [commit message if applicable]
   Proceeding to Step [N+1]...

 If FAIL:
   Step [N] failed
   Rolling back...
   Investigating failure before retry

═══════════════════════════════════════════════════════════════
```

**Actions in this phase:**
1. Make ONE atomic change
2. Run ALL tests
3. If pass: commit, move to next step
4. If fail: rollback, investigate, fix, retry
5. Repeat until all steps complete

### Phase 4: VALIDATE

**Goal**: Confirm the entire refactoring preserved behavior, left no dead code, and updated all references.

**Gate**: All original tests pass, no dead code remains, all callers are updated. Do not mark complete until every check passes.

Show command output directly rather than describing results because evidence is more trustworthy than summary. Grep for old names across the entire codebase including strings, comments, and config files to confirm zero remaining references. Check for dynamic references such as reflection and string-based lookups that static analysis may miss.

Remove any temporary test files, debug outputs, or backup files created during refactoring because they are noise that obscures the actual changes.

```
═══════════════════════════════════════════════════════════════
 PHASE 4: VALIDATE
═══════════════════════════════════════════════════════════════

 Full Test Suite:
   $ [comprehensive test command]
   Result: [PASS/FAIL]

 Behavior Verification:
   - [ ] Original functionality preserved
   - [ ] No new failures introduced
   - [ ] Performance acceptable

 Cleanup Verification:
   - [ ] No orphaned code
   - [ ] No unused imports
   - [ ] No dead references
   - [ ] Old names completely removed
   - [ ] Temporary files removed

 Caller Verification:
   $ grep -r "[old_name]" --include="*.ext"
   Result: [No matches / N remaining references]

 Documentation:
   - [ ] Comments updated
   - [ ] README updated (if applicable)
   - [ ] API docs updated (if applicable)

 Final Status: COMPLETE / INCOMPLETE

 Summary:
   - Files changed: [N]
   - Lines changed: [+X/-Y]
   - Steps completed: [N/Total]
   - Tests: [X passed, Y total]

═══════════════════════════════════════════════════════════════
```

## Reference Material

### Pattern: Rename (Function, Variable, File)

```
Phase 1: Find all usages with Grep
Phase 2: Plan order (definition first, then callers)
Phase 3: Execute with replace_all where safe
Phase 4: Verify no old name references remain
```

### Pattern: Extract (Function, Module, Class)

```
Phase 1: Identify code to extract, write tests
Phase 2: Plan new location, interface design
Phase 3:
  - Step 1: Create new location with copy
  - Step 2: Update callers one by one
  - Step 3: Remove old code
Phase 4: Verify all callers use new location
```

### Pattern: Inline (Remove Abstraction)

```
Phase 1: Find all usages, understand all variations
Phase 2: Plan inline order (start with simplest callers)
Phase 3:
  - Step 1: Inline at first call site
  - Step 2: Repeat for each call site
  - Step 3: Remove now-unused function
Phase 4: Verify no remaining references
```

### Pattern: Change Signature

```
Phase 1: Find all callers, understand usage patterns
Phase 2: Plan migration (add new, migrate, remove old)
Phase 3:
  - Step 1: Add new signature alongside old
  - Step 2: Migrate callers one by one
  - Step 3: Remove old signature
Phase 4: Verify all callers use new signature
```

## Error Handling

**Test Failure During Execute**:
- Stop immediately
- Rollback current step
- Investigate root cause
- Fix and retry OR revise plan

**Incomplete Caller Migration**:
- Do not remove old code until ALL callers migrated
- Use Grep to verify zero remaining references
- Check for dynamic references (strings, reflection)

**Unexpected Dependencies**:
- Stop and return to PLAN phase
- Add new dependencies to plan
- May need to add intermediate steps

## References

- `pipelines/systematic-refactoring/SKILL.md` - Phase-gated pipeline version
