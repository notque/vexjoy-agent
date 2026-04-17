# Plan Checker Verdict & Revision Loop Templates

Verbatim output formats for Phase 3 (VERDICT) and Phase 4 (REVISION LOOP).

## Phase 3 Step 1: Compile findings

Collect all findings from Phase 2 into a structured report. Order by severity (blockers first), then by dimension number.

Each finding uses this format:

```
Plan: [plan identifier or filename]
Dimension: [N] [dimension name]
Severity: Blocker | Warning
Description: [what is wrong]
Fix hint: [specific suggestion for how to fix it]
```

## Phase 3 Step 2: Issue verdict

| Condition | Verdict | Action |
|-----------|---------|--------|
| Zero findings | **PASS** | Proceed to execution |
| Warnings only, no blockers | **PASS with warnings** | Proceed, but address warnings if time allows |
| Any blocker findings | **BLOCK** | Plan must be revised before execution |

## Phase 3 Step 3: Format output

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

## Phase 4: Revision Loop iteration tracking

```
Revision iteration: [N] of 3
Remaining blockers: [count]
```

### Step 1: Revise plan

For each blocker finding:
- Apply the fix_hint
- If auto-revise is OFF (default): present the suggested revision to the user for approval
- If auto-revise is ON: apply the revision directly

### Step 2: Re-check

Run Phase 2 again on the revised plan. Only re-check dimensions that had findings (optimization -- dimensions that passed don't regress from plan edits).

### Step 3: Evaluate

| Condition | Action |
|-----------|--------|
| All blockers resolved | Issue PASS verdict, done |
| Blockers remain, iterations < 3 | Next iteration |
| Blockers remain, iterations = 3 | Document remaining issues as known risks, issue **PASS (with known risks)** |

### On max iterations reached

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
