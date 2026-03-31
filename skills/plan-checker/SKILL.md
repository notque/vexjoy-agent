---
name: plan-checker
description: "Validate plans against 10 dimensions: PASS/BLOCK verdict before execution."
version: 1.0.0
user-invocable: false
command: /plan-checker
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  triggers:
    - check plan
    - validate plan
    - plan checker
    - review plan
    - is this plan ready
    - plan-checker
    - pre-execution check
  pairs_with:
    - feature-lifecycle
    - workflow
    - plan-manager
  complexity: Medium
  category: process
---

# Plan Checker Skill

## Overview

Validate plans before execution using goal-backward analysis. Start from the stated goal and verify every requirement has a complete path through the plan to completion. This catches plan-level defects before they waste an entire execution cycle.

**Key principle**: Plan completeness does not equal goal achievement. A plan can have all tasks filled in, each well-specified, and still miss the goal entirely. The checker validates by working backward from the goal through every requirement to verify complete coverage -- not just that each task looks reasonable in isolation.

The skill operates as a gate between planning and execution, validating across 10 dimensions and issuing a PASS/BLOCK verdict. If issues are found, a bounded revision loop allows up to 3 iterations before proceeding with documented risks (because the cost of continued planning is not zero -- it consumes context, delays execution, and each revision may introduce new issues).

## Instructions

### Phase 1: LOAD

Load the plan and its context. The checker needs three things: the plan itself, the goal it serves, and the repository rules it must comply with.

**Step 1: Identify the plan**

Accept the plan from one of these sources (in priority order):
1. **Explicit path**: User provides a file path to the plan
2. **Feature state**: Check `.feature/state/plan/` for the active feature plan
3. **Active plans**: Check `plan/active/` for workflow-orchestrator plans
4. **Inline plan**: User pastes plan content directly

If no plan is found:
```
BLOCK: No plan found. Provide a plan file path, or run /feature-lifecycle (plan phase) or
workflow-orchestrator to create one first.
```

**Step 2: Extract the goal**

The goal is the anchor for goal-backward analysis (because analysis requires knowing what success looks like). Find it in:
- The plan's own `## Goal` or `## Success Criteria` section
- The parent design document (for feature plans: `.feature/state/design/`)
- The user's original request (for workflow-orchestrator plans)

If no goal is found:
```
BLOCK: No stated goal found in plan or design document. Goal-backward
analysis requires a goal. Add a ## Goal section to the plan.
```

**Step 3: Load repository context**

Read the target repository's CLAUDE.md (if it exists) for dimension 9 validation (because repository rules inform which constraints the plan must comply with):
```bash
find . -maxdepth 2 -name "CLAUDE.md" -type f 2>/dev/null | head -5
```

Read any found CLAUDE.md files to extract rules the plan must comply with.

**Step 4: Extract requirements**

From the goal and design document, extract a numbered list of requirements. Each requirement becomes a row in the coverage matrix. If the plan includes success criteria, those count as requirements too.

**GATE**: Plan loaded. Goal identified. Requirements extracted. Proceed to CHECK.

---

### Phase 2: CHECK

Run goal-backward analysis across all 10 verification dimensions. For each dimension, produce structured findings or mark as PASS.

#### Dimension 1: Requirement Coverage
**Severity**: Blocker
**Check**: Every extracted requirement appears in at least one task.

Trace backward from each requirement (because missing requirements directly predict execution failure):
- Which task(s) address this requirement?
- Is the coverage complete (full path to implementation) or partial?

Produce a coverage matrix:

```
## Requirements Coverage Matrix

| # | Requirement | Covered By | Status |
|---|-------------|------------|--------|
| R1 | [requirement] | T1, T3 | COVERED |
| R2 | [requirement] | T2 | COVERED |
| R3 | [requirement] | -- | UNCOVERED |
```

Any UNCOVERED requirement is a blocker finding.

#### Dimension 2: Task Completeness
**Severity**: Warning
**Check**: Each task has concrete actions, not vague descriptions.

Scan every task for vague verbs that signal incomplete thinking (because vague tasks fail at execution time when the executor realizes "implement feature" has dozens of possible interpretations):

| Vague (reject) | Concrete (accept) |
|-----------------|-------------------|
| "implement feature" | "add handler to router with X signature" |
| "ensure error handling" | "wrap fetchUser in try/catch, return 404 for NotFound" |
| "handle edge cases" | "add nil-check for user.Profile before accessing Avatar" |
| "improve performance" | "add index on orders.user_id, batch N+1 into JOIN" |
| "align the API" | "add created_at field to response struct" |
| "clean up" | "extract validation into validateInput() function" |

A task that uses vague verbs without specifying the concrete action is a warning finding.

#### Dimension 3: Dependency Correctness
**Severity**: Blocker
**Check**: Tasks reference the right files and imports, verified against the actual codebase.

For each task that references files, verify using the filesystem (because file paths and imports validated from memory are unreliable -- the codebase is the source of truth):
```bash
# Verify each referenced file exists
ls -la /path/to/referenced/file
```

For each task that references imports or packages:
- Verify the package/module exists in the codebase or dependency manifest
- Check that the import path is correct

A task referencing a nonexistent file or wrong import path is a blocker finding.

#### Dimension 4: Key Links Planned
**Severity**: Blocker
**Check**: Cross-component wiring is explicitly tasked.

For any plan that adds new components, verify that the wiring between components is an explicit task (because unwired components are the most common post-execution discovery -- the feature "works" in isolation but is never reachable):

| New Component | Required Wiring |
|---------------|----------------|
| New endpoint | Route registration |
| New handler | Router/mux hookup |
| New config option | Config loading code |
| New database table | Migration + ORM registration |
| New service | Dependency injection / initialization |
| New hook | Hook registration in settings |
| New agent | INDEX.json entry |
| New skill | INDEX.json entry, routing table |

If the plan adds a component but has no task for its wiring, that is a blocker finding.

#### Dimension 5: Scope Sanity
**Severity**: Warning at 4 tasks, Blocker at 5+
**Check**: Plan has right-sized scope for a single execution context.

Count the tasks in the plan:

| Task Count | Verdict | Rationale |
|------------|---------|-----------|
| 1-3 | Good | Right-sized for focused execution |
| 4 | Warning | Approaching limit; review if any tasks can merge |
| 5+ | Blocker | Split required -- context windows are finite, and each task adds execution state. Past 5 tasks, the executor loses track of earlier context, makes inconsistent decisions, or runs out of room for error recovery. |

For blocker: suggest how to split (by wave, by component, by dependency boundary).

#### Dimension 6: Verification Derivation
**Severity**: Warning
**Check**: How to verify the plan's goal is achieved must be explicit.

Look for a `## Verification` or `## Success Criteria` section. Check that it specifies (because "run tests" is not verification -- expected outcomes and observable behaviors are):
- Concrete commands to run (not just "run tests")
- Expected outcomes (not just "tests pass")
- Observable behaviors (not implementation tasks)

| Insufficient | Sufficient |
|--------------|-----------|
| "run tests" | "run `go test ./pkg/...` and verify TestNewHandler passes" |
| "check it works" | "curl localhost:8080/api/reset returns 200 with token field" |
| "verify deployment" | "kubectl get pods -n staging shows 3/3 Running within 60s" |

A plan with no verification section or only vague verification is a warning finding.

#### Dimension 7: Context Compliance
**Severity**: Blocker
**Check**: Plan respects decisions from prior phases.

If the plan is part of a feature lifecycle (design -> plan -> implement):
- Read the design document decisions
- Verify the plan doesn't contradict them (because contradictions with prior decisions create rework)
- Check that architectural choices from design are reflected in task details

If the plan is standalone (workflow-orchestrator):
- Check that the plan aligns with the user's stated requirements
- Verify no scope creep beyond what was requested

A plan that contradicts prior-phase decisions is a blocker finding.

#### Dimension 8: Cross-Plan Data Contracts
**Severity**: Blocker
**Check**: One plan's transformations don't conflict with another's.

This dimension only applies when multiple plans exist for the same feature. Check (because data contract conflicts cause silent failures -- code runs but produces wrong output):
- Do two plans modify the same files? If so, are the modifications compatible?
- Do two plans expect different shapes for shared data structures?
- Does Plan B depend on output from Plan A that Plan A doesn't actually produce?

If not applicable (single plan), mark as PASS with note "single plan -- no cross-plan conflicts possible."

#### Dimension 9: CLAUDE.md Compliance
**Severity**: Blocker
**Check**: Plan doesn't violate repository rules.

Cross-reference the plan against CLAUDE.md rules loaded in Phase 1 (because repository rules enforce architecture and safety patterns). Common violations:

| Rule Category | What to Check |
|---------------|--------------|
| Branch policy | Plan doesn't commit directly to main/master |
| Test requirements | Plan includes test tasks if CLAUDE.md requires them |
| Code style | Plan references correct formatters/linters |
| Forbidden patterns | Plan doesn't use patterns CLAUDE.md prohibits |
| Required tools | Plan uses repo-mandated tools (e.g., specific test runners) |

A plan that violates a CLAUDE.md rule is a blocker finding.

If no CLAUDE.md was found in Phase 1, mark as PASS with note "no CLAUDE.md found."

#### Dimension 10: Achievability
**Severity**: Warning
**Check**: Plan is completable within approximately 50% of a fresh context window.

Estimate the execution cost (because execution always takes more than planned):
- Number of tasks x average task complexity
- Number of files to read for context
- Number of verification commands to run
- Room needed for error recovery and iteration

If the plan looks like it would consume more than 50% of a context window:
- Warning finding with suggestion to split or simplify
- Rationale: A plan that fits in 50% leaves room for reality. Execution always has errors, context is needed for debugging, and verification adds overhead.

**GATE**: All 10 dimensions checked. Findings collected. Proceed to VERDICT.

---

### Phase 3: VERDICT

Compile findings and issue verdict.

**Step 1: Compile findings**

Collect all findings from Phase 2 into a structured report. Order by severity (blockers first), then by dimension number.

Each finding uses this format:

```
Plan: [plan identifier or filename]
Dimension: [N] [dimension name]
Severity: Blocker | Warning
Description: [what is wrong]
Fix hint: [specific suggestion for how to fix it]
```

**Step 2: Issue verdict**

| Condition | Verdict | Action |
|-----------|---------|--------|
| Zero findings | **PASS** | Proceed to execution |
| Warnings only, no blockers | **PASS with warnings** | Proceed, but address warnings if time allows |
| Any blocker findings | **BLOCK** | Plan must be revised before execution |

**Step 3: Format output**

```
================================================================
 PLAN CHECK: [plan identifier]
================================================================

 Verdict: PASS | PASS (with warnings) | BLOCK
 Blockers: [count]
 Warnings: [count]

 Requirements Coverage: [N/M] covered

================================================================
 FINDINGS
================================================================

 [structured findings, blockers first]

================================================================
 REQUIREMENTS COVERAGE MATRIX
================================================================

 [coverage matrix from dimension 1]

================================================================
```

If verdict is PASS or PASS with warnings, suggest:
```
Plan validated. Proceed to execution with /feature-lifecycle (implement phase) or
continue with workflow-orchestrator EXECUTE phase.
```

If verdict is BLOCK, proceed to Phase 4 (Revision Loop).

**GATE**: Verdict issued. If PASS, done. If BLOCK, proceed to revision loop.

---

### Phase 4: REVISION LOOP (only if BLOCK)

Bounded revision loop: fix blocker findings, re-check, max 3 iterations. After 3 good-faith attempts, remaining issues are either genuinely hard (and better discovered during execution with real code) or low-probability (and not worth further planning time).

**Iteration tracking**:
```
Revision iteration: [N] of 3
Remaining blockers: [count]
```

**Step 1: Revise plan**

For each blocker finding:
- Apply the fix_hint
- If auto-revise is OFF (default): present the suggested revision to the user for approval
- If auto-revise is ON: apply the revision directly

**Step 2: Re-check**

Run Phase 2 again on the revised plan. Only re-check dimensions that had findings (optimization -- dimensions that passed don't regress from plan edits).

**Step 3: Evaluate**

| Condition | Action |
|-----------|--------|
| All blockers resolved | Issue PASS verdict, done |
| Blockers remain, iterations < 3 | Next iteration |
| Blockers remain, iterations = 3 | Document remaining issues as known risks, issue **PASS (with known risks)** |

**On max iterations reached**:

```
================================================================
 PLAN CHECK: [plan identifier]
================================================================

 Verdict: PASS (with known risks)
 Revision iterations: 3 of 3 (limit reached)

 Known Risks (unresolved after 3 iterations):
   - [finding 1]
   - [finding 2]

 Proceeding to execution. These risks should be monitored during
 implementation. If any risk materializes, pause execution and
 revise the plan.
================================================================
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No plan found | No plan file at expected locations | Provide explicit path, or run /feature-lifecycle (plan phase) first |
| No goal found | Plan lacks ## Goal or ## Success Criteria | Add a goal section to the plan before checking |
| File verification fails | Referenced file doesn't exist in codebase | Fix the file path in the plan, or create the file first |
| CLAUDE.md not found | No CLAUDE.md in target repo | Dimension 9 passes automatically; note in findings |
| Revision loop exhausted | 3 iterations couldn't resolve all blockers | Proceed with known risks documented |
| Plan is inline text | User pasted plan instead of file path | Parse inline text; warn that revisions won't persist to file |

## References

- ADR-074: Plan Checker Pre-Execution Validation (historical reference -- file not present in current repo)
- [Feature Lifecycle](/skills/feature-lifecycle/SKILL.md) -- plan phase produces plans this skill validates; implement phase executes plans after validation
- [Workflow Orchestrator](skills/workflow/references/workflow-orchestrator.md) -- PLAN phase produces plans this skill can validate
- [Verification Before Completion](/skills/verification-before-completion/SKILL.md) -- post-execution counterpart (validates results, not plans)
