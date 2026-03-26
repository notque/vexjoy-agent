---
name: systematic-refactoring
description: |
  Safe 5-phase refactoring pipeline with test characterization, incremental
  changes, and learning gates: CHARACTERIZE, PLAN, REFACTOR, VERIFY, RECORD.
  Use when renaming functions/variables, extracting modules, changing signatures,
  restructuring directories, or consolidating duplicate code. Use for "refactor",
  "rename", "extract", "restructure", or "migrate pattern". Do NOT use for bug
  fixes or new feature implementation.
version: 2.0.0
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Grep
  - Glob
success-criteria:
  - "Characterization tests pass before and after changes"
  - "Zero references to old names remaining in codebase"
  - "Full test suite passes after each incremental step"
  - "No behavioral changes (only structural improvements)"
  - "All import paths and cross-references updated"
  - "Refactoring pattern recorded to learning.db"
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

# Systematic Refactoring Pipeline

> **Promoted from**: `skills/systematic-refactoring/SKILL.md` (original 4-phase skill)

Safe, verifiable refactoring through 5 explicit phases with mandatory gates. Each phase has gates that prevent common refactoring mistakes: breaking behavior, incomplete migrations, or orphaned code.

## Operator Context

This pipeline operates as an operator for safe code refactoring, configuring Claude's behavior for incremental, verifiable changes.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution
- **Over-Engineering Prevention**: Only refactor what's directly requested. Keep changes minimal and focused. No speculative improvements or "while we're here" changes without explicit request.
- **NEVER change behavior without tests**: Characterization tests required before changes
- **NEVER make multiple changes at once**: One atomic change per commit
- **NEVER skip validation**: Tests must pass after every change
- **ALWAYS preserve external API**: Unless explicitly requested
- **Phase Gates Enforced**: Each phase must pass its gate before the next begins

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

## What This Pipeline CAN Do
- Safely rename functions, variables, files across a codebase
- Extract code into new modules with caller migration
- Change function signatures with incremental migration
- Restructure directory layouts preserving all behavior
- Consolidate duplicate code with test verification
- Record refactoring patterns for future sessions

## What This Pipeline CANNOT Do
- Fix bugs (use systematic-debugging instead)
- Add new features (use workflow-orchestrator instead)
- Make multiple changes simultaneously without testing between each
- Skip characterization tests before modifying code
- Leave incomplete migrations (old code alongside new)

---

## Instructions

### Phase 1: CHARACTERIZE

**Goal**: Document current behavior with tests before touching any code.

**Artifact**: Characterization test suite (green).

```
===============================================================
 PHASE 1: CHARACTERIZE
===============================================================

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
===============================================================
```

**Actions in this phase:**
1. Read the code to be refactored completely
2. Find all callers with Grep
3. Run existing tests, note coverage gaps
4. Write characterization tests for uncovered behavior
5. Verify all tests pass

**GATE**: Test suite exists that verifies current behavior. ALL tests GREEN. Proceed only when gate passes.

---

### Phase 2: PLAN

**Goal**: Identify refactoring targets, define incremental steps with rollback points.

**Artifact**: `refactor-plan.md`

```
===============================================================
 PHASE 2: PLAN
===============================================================

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

 PLAN complete. Proceeding to REFACTOR...
===============================================================
```

**Actions in this phase:**
1. Define the exact end state
2. Break into smallest possible atomic changes
3. Identify dependencies between steps
4. Define rollback procedure for each step
5. Estimate risk level for each step
6. Write `refactor-plan.md` to project root

**GATE**: `refactor-plan.md` exists with clear sequence of atomic changes and rollback points for each step. Proceed only when gate passes.

---

### Phase 3: REFACTOR

**Goal**: Apply changes incrementally, run tests after each step. Tests must stay green throughout.

```
===============================================================
 PHASE 3: REFACTOR - Step [N] of [Total]
===============================================================

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

===============================================================
```

**Actions in this phase:**
1. Make ONE atomic change
2. Run ALL tests
3. If pass: commit, move to next step
4. If fail: rollback, investigate, fix, retry
5. Repeat until all steps complete

**Error Recovery:**
- **Test Failure During Execute**: Stop immediately, rollback current step, investigate root cause, fix and retry OR revise plan
- **Incomplete Caller Migration**: Do not remove old code until ALL callers migrated. Use Grep to verify zero remaining references. Check for dynamic references (strings, reflection).
- **Unexpected Dependencies**: Stop and return to PLAN phase. Add new dependencies to plan. May need to add intermediate steps.

**GATE**: ALL planned steps executed. Tests GREEN after every step. No step skipped or combined. Proceed only when gate passes.

---

### Phase 4: VERIFY

**Goal**: Full test suite, diff summary, confirm no behavior change.

```
===============================================================
 PHASE 4: VERIFY
===============================================================

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

===============================================================
```

**GATE**: Full test suite passes. Zero references to old names. No orphaned code. No behavior changes detected. Proceed only when gate passes.

---

### Phase 5: RECORD

**Goal**: Log refactoring patterns to learning database for future sessions.

**Step 1: Record refactoring pattern**

```markdown
## [Date] [Refactoring Type]: [Brief Description]
**Pattern**: [rename | extract | inline | restructure | migrate]
**Scope**: [N files, M callers]
**Steps**: [N atomic steps]
**Key Decision**: [Most important choice made and why]
**Gotcha**: [What almost went wrong or required extra care]
```

**Step 2: Update learning.db**

Record the refactoring pattern and outcome to the learning database for automated future lookup.

**Step 3: Clean up**

- Remove `refactor-plan.md` (plan executed)
- Remove temporary test files or debug outputs
- Keep characterization tests (they add permanent value)

**Output**: `[learning] Refactoring pattern recorded.`

**GATE**: Learning database entry exists with pattern type, scope, key decision, and gotcha. Temporary files cleaned up. Characterization tests retained.

---

## Refactoring Patterns

### Pattern 1: Rename (Function, Variable, File)

```
Phase 1: Find all usages with Grep
Phase 2: Plan order (definition first, then callers)
Phase 3: Execute with replace_all where safe
Phase 4: Verify no old name references remain
Phase 5: Record pattern and any gotchas
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
Phase 5: Record extraction pattern
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
Phase 5: Record inline pattern
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
Phase 5: Record migration pattern
```

---

## Anti-Patterns

### Anti-Pattern 1: Big Bang Refactoring

**What it looks like:** Changing 47 files in one commit, updating function name, all callers, tests, and docs simultaneously.

**Why it's wrong:**
- One test failure breaks everything
- Impossible to bisect which change caused issues
- No rollback points if problems discovered later
- Merge conflicts guaranteed in active codebases

**Do this instead:**
1. CHARACTERIZE: Write tests for current behavior
2. PLAN: Break into steps (add new function, migrate callers gradually, remove old)
3. REFACTOR: Commit after each atomic change (5-10 callers at a time)
4. VERIFY: Tests pass after every step

### Anti-Pattern 2: Refactoring Without Tests First

**What it looks like:** Immediately creating new function and updating callers without writing tests.

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

**What it looks like:** Creating new location, updating 80% of callers, leaving old function "for backward compatibility".

**Why it's wrong:**
- Code exists in two places indefinitely
- Future changes need double updates
- Confusion about which to use
- Old code becomes stale and buggy

**Do this instead:**
1. PLAN: Identify ALL callers upfront (use Grep exhaustively)
2. REFACTOR: Update every single caller before removing old code
3. VERIFY: Grep confirms ZERO references to old location
4. Clean up: Remove old code completely

### Anti-Pattern 4: Mixing Refactoring with Feature Work

**What it looks like:** Renaming function AND changing logic in same refactoring.

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

---

## Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This refactoring is safe, no tests needed" | Refactoring without tests is flying blind | Write characterization tests first |
| "I'll update the remaining callers later" | Incomplete migrations rot forever | Migrate ALL callers before removing old code |
| "Small rename, no need for full process" | Small renames break string refs and configs | Grep for all references including strings |
| "I can fix this bug while refactoring" | Mixed concerns make failures undiagnosable | Separate commits: refactor then fix |
| "No need to record, it was straightforward" | Future refactors benefit from past patterns | Complete Phase 5 |

---

## References

This pipeline uses these shared patterns:
- [Anti-Rationalization](../../skills/shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../../skills/shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../../skills/shared-patterns/gate-enforcement.md) - Phase transition rules
