---
name: plan-checker
description: "Validate plans against 10 dimensions: PASS/BLOCK verdict before execution."
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

If no plan is found, BLOCK with a message telling the user to provide a plan path or run `/feature-lifecycle` first.

**Step 2: Extract the goal**

The goal is the anchor for goal-backward analysis. Find it in the plan's own `## Goal` or `## Success Criteria` section, the parent design document (for feature plans: `.feature/state/design/`), or the user's original request (for workflow-orchestrator plans).

If no goal is found, BLOCK: goal-backward analysis requires a goal. Direct the user to add a `## Goal` section.

**Step 3: Load repository context**

Read the target repository's CLAUDE.md (if present) for dimension 9 validation:
```bash
find . -maxdepth 2 -name "CLAUDE.md" -type f 2>/dev/null | head -5
```

**Step 4: Extract requirements**

From the goal and design document, extract a numbered list of requirements. Each becomes a row in the coverage matrix. Success criteria in the plan count as requirements.

**GATE**: Plan loaded. Goal identified. Requirements extracted. Proceed to CHECK.

---

### Phase 2: CHECK

Run goal-backward analysis across all 10 verification dimensions. For each, produce structured findings or mark as PASS.

Full dimension specifications (severity, checks, tables, examples) for all 10 dimensions — Requirement Coverage, Task Completeness, Dependency Correctness, Key Links Planned, Scope Sanity, Verification Derivation, Context Compliance, Cross-Plan Data Contracts, CLAUDE.md Compliance, Achievability — live in `references/dimensions.md`.

**Dimension severity summary**:

| # | Dimension | Severity |
|---|-----------|----------|
| 1 | Requirement Coverage | Blocker |
| 2 | Task Completeness | Warning |
| 3 | Dependency Correctness | Blocker |
| 4 | Key Links Planned | Blocker |
| 5 | Scope Sanity | Warning at 4, Blocker at 5+ |
| 6 | Verification Derivation | Warning |
| 7 | Context Compliance | Blocker |
| 8 | Cross-Plan Data Contracts | Blocker |
| 9 | CLAUDE.md Compliance | Blocker |
| 10 | Achievability | Warning |

**GATE**: All 10 dimensions checked. Findings collected. Proceed to VERDICT.

---

### Phase 3: VERDICT

Compile findings and issue verdict.

**Step 1: Compile findings** — Order by severity (blockers first), then by dimension number. Each finding uses the structured format (Plan, Dimension, Severity, Description, Fix hint) — see `references/verdict-format.md`.

**Step 2: Issue verdict**

| Condition | Verdict | Action |
|-----------|---------|--------|
| Zero findings | **PASS** | Proceed to execution |
| Warnings only, no blockers | **PASS with warnings** | Proceed, but address warnings if time allows |
| Any blocker findings | **BLOCK** | Plan must be revised before execution |

**Step 3: Format output** — Full verdict output template (headers, findings block, coverage matrix block) lives in `references/verdict-format.md`.

If verdict is PASS or PASS with warnings, direct the user to proceed with `/feature-lifecycle` (implement phase) or workflow-orchestrator EXECUTE.

If verdict is BLOCK, proceed to Phase 4 (Revision Loop).

**GATE**: Verdict issued. If PASS, done. If BLOCK, proceed to revision loop.

---

### Phase 4: REVISION LOOP (only if BLOCK)

Bounded revision loop: fix blocker findings, re-check, max 3 iterations. After 3 good-faith attempts, remaining issues are either genuinely hard (better discovered during execution with real code) or low-probability (not worth further planning time).

**Step 1: Revise plan** — For each blocker, apply the fix_hint. If auto-revise is OFF (default), present to the user for approval; if ON, apply directly.

**Step 2: Re-check** — Run Phase 2 again on the revised plan. Only re-check dimensions that had findings (dimensions that passed don't regress from plan edits).

**Step 3: Evaluate**

| Condition | Action |
|-----------|--------|
| All blockers resolved | Issue PASS verdict, done |
| Blockers remain, iterations < 3 | Next iteration |
| Blockers remain, iterations = 3 | Document remaining as known risks, issue **PASS (with known risks)** |

Revision loop output template (iteration tracking, max-iterations banner, known-risks section): `references/verdict-format.md`.

---

## Error Handling

Common errors (no plan found, no goal found, file verification fails, CLAUDE.md not found, revision loop exhausted, plan is inline text) and solutions: `references/errors.md`.

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/dimensions.md` | Phase 2 CHECK | All 10 dimensions verbatim: severity, check, tables, examples |
| `references/verdict-format.md` | Phase 3 VERDICT, Phase 4 | Verdict output templates, finding format, revision loop tracking, max-iterations banner |
| `references/errors.md` | Error Handling | Error matrix with causes and solutions |

- ADR-074: Plan Checker Pre-Execution Validation (historical reference -- file not present in current repo)
- [Feature Lifecycle](/skills/feature-lifecycle/SKILL.md) -- plan phase produces plans this skill validates; implement phase executes plans after validation
- [Workflow Orchestrator](skills/workflow/references/workflow-orchestrator.md) -- PLAN phase produces plans this skill can validate
- [Verification Before Completion](/skills/verification-before-completion/SKILL.md) -- post-execution counterpart (validates results, not plans)
