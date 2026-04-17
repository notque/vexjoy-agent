# Plan Checker Dimensions

Verbatim detail for the 10 verification dimensions used in Phase 2 (CHECK). For each dimension, produce structured findings or mark as PASS.

## Dimension 1: Requirement Coverage
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

## Dimension 2: Task Completeness
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

## Dimension 3: Dependency Correctness
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

## Dimension 4: Key Links Planned
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

## Dimension 5: Scope Sanity
**Severity**: Warning at 4 tasks, Blocker at 5+
**Check**: Plan has right-sized scope for a single execution context.

Count the tasks in the plan:

| Task Count | Verdict | Rationale |
|------------|---------|-----------|
| 1-3 | Good | Right-sized for focused execution |
| 4 | Warning | Approaching limit; review if any tasks can merge |
| 5+ | Blocker | Split required -- context windows are finite, and each task adds execution state. Past 5 tasks, the executor loses track of earlier context, makes inconsistent decisions, or runs out of room for error recovery. |

For blocker: suggest how to split (by wave, by component, by dependency boundary).

## Dimension 6: Verification Derivation
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

## Dimension 7: Context Compliance
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

## Dimension 8: Cross-Plan Data Contracts
**Severity**: Blocker
**Check**: One plan's transformations don't conflict with another's.

This dimension only applies when multiple plans exist for the same feature. Check (because data contract conflicts cause silent failures -- code runs but produces wrong output):
- Do two plans modify the same files? If so, are the modifications compatible?
- Do two plans expect different shapes for shared data structures?
- Does Plan B depend on output from Plan A that Plan A doesn't actually produce?

If not applicable (single plan), mark as PASS with note "single plan -- no cross-plan conflicts possible."

## Dimension 9: CLAUDE.md Compliance
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

## Dimension 10: Achievability
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
