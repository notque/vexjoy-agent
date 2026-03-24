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
---

# Systematic Refactoring Skill

## Purpose

Perform safe, verifiable refactoring through explicit phases. Each phase has gates that prevent common refactoring mistakes: breaking behavior, incomplete migrations, or orphaned code.

## Operator Context

This skill operates as an operator for safe code refactoring, configuring Claude's behavior for incremental, verifiable changes.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution
- **Over-Engineering Prevention**: Only refactor what's directly requested. Keep changes minimal and focused. No speculative improvements or "while we're here" changes without explicit request.
- **NEVER change behavior without tests**: Characterization tests required before changes
- **NEVER make multiple changes at once**: One atomic change per commit
- **NEVER skip validation**: Tests must pass after every change
- **ALWAYS preserve external API**: Unless explicitly requested

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- **Temporary File Cleanup**: Remove temporary test files, debug outputs, or backup files created during refactoring at task completion. Keep only files explicitly needed.
- **Write characterization tests first**: Capture current behavior before changing
- **Incremental commits**: Commit at each stable point
- **Update all callers**: Find and update every reference
- **Remove dead code**: Clean up orphaned code after migration

### Optional Behaviors (OFF unless enabled)
- **Performance benchmarks**: Compare before/after performance
- **Documentation updates**: Auto-update docs for API changes
- **Type migration**: Update type definitions across codebase

## What This Skill CAN Do
- Safely rename functions, variables, files across a codebase
- Extract code into new modules with caller migration
- Change function signatures with incremental migration
- Restructure directory layouts preserving all behavior
- Consolidate duplicate code with test verification

## What This Skill CANNOT Do
- Fix bugs (use systematic-debugging instead)
- Add new features (use workflow-orchestrator instead)
- Make multiple changes simultaneously without testing between each
- Skip characterization tests before modifying code
- Leave incomplete migrations (old code alongside new)

## Systematic Phases

### Phase 1: CHARACTERIZE (Do NOT proceed without test coverage)

**Gate**: Tests exist that verify current behavior.

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
2. Find all callers with Grep
3. Run existing tests, note coverage gaps
4. Write characterization tests for uncovered behavior
5. Verify all tests pass

### Phase 2: PLAN (Do NOT proceed without incremental steps defined)

**Gate**: Clear sequence of atomic changes with rollback points.

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

### Phase 3: EXECUTE (One step at a time, tests between each)

**Gate**: Tests pass after each atomic change.

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

### Phase 4: VALIDATE (Do NOT mark complete until verified)

**Gate**: All original tests pass, no dead code, all callers updated.

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

## Refactoring Patterns

### Pattern 1: Rename (Function, Variable, File)

```
Phase 1: Find all usages with Grep
Phase 2: Plan order (definition first, then callers)
Phase 3: Execute with replace_all where safe
Phase 4: Verify no old name references remain
```

### Pattern 2: Extract (Function, Module, Class)

```
Phase 1: Identify code to extract, write tests
Phase 2: Plan new location, interface design
Phase 3:
  - Step 1: Create new location with copy
  - Step 2: Update callers one by one
  - Step 3: Remove old code
Phase 4: Verify all callers use new location
```

### Pattern 3: Inline (Remove Abstraction)

```
Phase 1: Find all usages, understand all variations
Phase 2: Plan inline order (start with simplest callers)
Phase 3:
  - Step 1: Inline at first call site
  - Step 2: Repeat for each call site
  - Step 3: Remove now-unused function
Phase 4: Verify no remaining references
```

### Pattern 4: Change Signature

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

## Common Anti-Patterns

### Anti-Pattern 1: Big Bang Refactoring

**What it looks like:**
```
User: "Rename getUserData to fetchUserProfile across the entire codebase"
Claude: *Changes 47 files in one commit, updating function name, all callers, tests, and docs*
```

**Why it's wrong:**
- One test failure breaks everything
- Impossible to bisect which change caused issues
- No rollback points if problems discovered later
- Merge conflicts guaranteed in active codebases

**Do this instead:**
1. CHARACTERIZE: Write tests for current getUserData behavior
2. PLAN: Break into steps (add new function, migrate callers gradually, remove old)
3. EXECUTE: Commit after each atomic change (5-10 callers at a time)
4. VALIDATE: Tests pass after every step

### Anti-Pattern 2: Refactoring Without Tests First

**What it looks like:**
```
User: "Extract this logic into a new function"
Claude: *Immediately creates new function and updates callers without writing tests*
```

**Why it's wrong:**
- No verification that behavior is preserved
- Silent bugs introduced during extraction
- Can't prove refactoring was safe
- No baseline to compare against

**Do this instead:**
1. CHARACTERIZE: Write tests for current behavior BEFORE touching code
2. Run tests: Verify they pass with current implementation
3. Make change: Extract function
4. Run tests again: Verify same results
5. Tests are your proof of correctness

### Anti-Pattern 3: Incomplete Migration

**What it looks like:**
```
User: "Move getUser from utils.js to user-service.js"
Claude: *Creates new location, updates 80% of callers, leaves old function "for backward compatibility"*
```

**Why it's wrong:**
- Code exists in two places indefinitely
- Future changes need double updates
- Confusion about which to use
- Old code becomes stale and buggy

**Do this instead:**
1. PLAN: Identify ALL callers upfront (use Grep exhaustively)
2. EXECUTE: Update every single caller before removing old code
3. VALIDATE: Grep confirms ZERO references to old location
4. Clean up: Remove old code completely
5. No half-migrated state allowed

### Anti-Pattern 4: Mixing Refactoring with Feature Work

**What it looks like:**
```
User: "Rename calculateTotal and also fix the tax calculation bug"
Claude: *Renames function AND changes logic in same refactoring*
```

**Why it's wrong:**
- Can't tell if tests fail due to rename or logic change
- Violates "preserve behavior" principle
- Impossible to review as pure refactoring
- Rollback becomes unclear

**Do this instead:**
1. Separate concerns: "This is ONLY refactoring, behavior unchanged"
2. Complete refactoring first: Rename with tests proving no behavior change
3. Then fix bug: In separate phase with new tests for fixed behavior
4. Two commits: One refactor (safe), one fix (behavior change)

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This refactoring is safe, no tests needed" | Refactoring without tests is flying blind | Write characterization tests first |
| "I'll update the remaining callers later" | Incomplete migrations rot forever | Migrate ALL callers before removing old code |
| "Small rename, no need for full process" | Small renames break string refs and configs | Grep for all references including strings |
| "I can fix this bug while refactoring" | Mixed concerns make failures undiagnosable | Separate commits: refactor then fix |
