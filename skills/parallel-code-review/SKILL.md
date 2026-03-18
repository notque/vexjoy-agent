---
name: parallel-code-review
description: |
  Parallel 3-reviewer code review orchestration: launch Security, Business-Logic,
  and Architecture reviewers simultaneously, aggregate findings by severity, and
  produce a unified BLOCK/FIX/APPROVE verdict. Use when reviewing PRs with 5+
  files, security-sensitive changes, new features needing broad coverage, or when
  user requests "parallel review", "comprehensive review", or "full review".
  Do NOT use for single-file fixes, documentation-only changes, or when
  systematic-code-review (sequential) is sufficient.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Task
---

# Parallel Code Review Skill

## Operator Context

This skill operates as an orchestrator for parallel code review, configuring Claude's behavior to launch three specialized review agents simultaneously and aggregate their findings into a unified report. It implements the **Fan-Out/Fan-In** architectural pattern -- dispatch independent reviewers in parallel, collect results, merge by severity -- with **Domain Intelligence** embedded in each reviewer's focus area.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before dispatching reviewers
- **True Parallelism**: All 3 Task calls MUST be dispatched in a SINGLE message
- **No Skipping Reviewers**: All 3 reviewers run even for "simple" changes
- **READ-ONLY**: Reviewers never modify code; this is observation only
- **Severity Aggregation**: Combine findings by severity before reporting
- **Always Produce Verdict**: Every review ends with BLOCK, FIX, or APPROVE

### Default Behaviors (ON unless disabled)
- **Re-run on Critical**: If CRITICAL issues found, re-run all reviewers after fixes
- **Severity Summary Table**: Include reviewer-by-severity matrix in output
- **File-Line References**: All findings must include `file:line` references
- **Domain-Specific Agent Selection**: Use language-appropriate agent for architecture reviewer

### Optional Behaviors (OFF unless enabled)
- **Threat Model**: Enable with "include threat model" for security reviewer
- **Git Bisect**: Enable with "find breaking commit" for regression tracking
- **Performance Profiling**: Enable with "benchmark" for architecture reviewer

## What This Skill CAN Do
- Dispatch 3 specialized reviewers in true parallel (single message)
- Aggregate findings across reviewers into unified severity classification
- Select domain-appropriate agents for architecture review (Go, Python, TS)
- Produce a structured report with BLOCK/FIX/APPROVE verdict
- Re-run all reviewers after critical fixes to verify resolution

## What This Skill CANNOT Do
- Modify code or apply fixes (read-only review only)
- Run fewer than 3 reviewers to save time
- Skip aggregation and report individual reviewer results separately
- Replace systematic-code-review for simple sequential reviews
- Approve without all 3 reviewers completing

---

## Instructions

### Phase 1: IDENTIFY SCOPE

**Goal**: Determine changed files and select appropriate agents before dispatching.

**Step 1: List changed files**

```bash
# For recent commits:
git diff --name-only HEAD~1
# For PRs:
gh pr view --json files -q '.files[].path'
```

**Step 2: Select architecture reviewer agent**

| File Types | Agent |
|-----------|-------|
| `.go` files | `golang-general-engineer` |
| `.py` files | `python-general-engineer` |
| `.ts`/`.tsx` files | `typescript-frontend-engineer` |
| Mixed or other | `Explore` |

**Gate**: Changed files listed, architecture reviewer agent selected. Proceed only when gate passes.

### Phase 2: DISPATCH PARALLEL REVIEWERS

**Goal**: Launch all 3 reviewers in a single message for true concurrent execution.

**CRITICAL**: All three Task calls MUST appear in ONE response. Sequential messages defeat parallelism.

Dispatch exactly these 3 agents:

**Reviewer 1 -- Security**
- Focus: OWASP Top 10, authentication, authorization, input validation, secrets exposure
- Output: Severity-classified findings with `file:line` references

**Reviewer 2 -- Business Logic**
- Focus: Requirements coverage, edge cases, state transitions, data validation, failure modes
- Output: Severity-classified findings with `file:line` references

**Reviewer 3 -- Architecture** (using agent selected in Phase 1)
- Focus: Design patterns, naming, structure, performance, maintainability
- Output: Severity-classified findings with `file:line` references

**Gate**: All 3 Task calls dispatched in a single message. Proceed only when all 3 return results.

### Phase 3: AGGREGATE

**Goal**: Merge all findings into a unified severity-classified report.

**Step 1: Classify each finding by severity**

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Security vulnerability, data loss risk | BLOCK merge |
| HIGH | Significant bug, logic error | Fix before merge |
| MEDIUM | Code quality issue, potential problem | Should fix |
| LOW | Minor issue, style preference | Nice to have |

**Step 2: Deduplicate overlapping findings**

Multiple reviewers may flag the same issue. Merge duplicates, keep the highest severity.

**Step 3: Build reviewer summary matrix**

```
| Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
|----------------|----------|------|--------|-----|
| Security       | N        | N    | N      | N   |
| Business Logic | N        | N    | N      | N   |
| Architecture   | N        | N    | N      | N   |
| **Total**      | **N**    | **N**| **N**  | **N**|
```

**Gate**: All findings classified, deduplicated, and summarized. Proceed only when gate passes.

### Phase 4: VERDICT

**Goal**: Produce final report with clear recommendation.

**Step 1: Determine verdict**

| Condition | Verdict |
|-----------|---------|
| Any CRITICAL findings | **BLOCK** |
| HIGH findings, no CRITICAL | **FIX** (fix before merge) |
| Only MEDIUM/LOW findings | **APPROVE** (with suggestions) |

**Step 2: Output structured report**

```markdown
## Parallel Review Complete

### Combined Findings

#### CRITICAL (Block Merge)
1. [Reviewer] Issue description - file:line

#### HIGH (Fix Before Merge)
1. [Reviewer] Issue description - file:line

#### MEDIUM (Should Fix)
1. [Reviewer] Issue description - file:line

#### LOW (Nice to Have)
1. [Reviewer] Issue description - file:line

### Summary by Reviewer
[Matrix from Phase 3]

### Recommendation
**VERDICT** - [1-2 sentence rationale]
```

**Step 3: If BLOCK verdict, initiate re-review protocol**

After user addresses CRITICAL issues, re-run ALL 3 reviewers to verify:
1. Original CRITICAL issues resolved
2. No regressions introduced
3. No new CRITICAL/HIGH issues from fixes

**Gate**: Structured report delivered with verdict. Review is complete.

---

## Error Handling

### Error: "Reviewer Times Out"
Cause: One or more Task agents exceed execution time
Solution:
1. Report findings from completed reviewers immediately
2. Note which reviewer(s) timed out and on which files
3. Offer to re-run failed reviewer separately or proceed with partial results

### Error: "All Reviewers Fail"
Cause: Systemic issue (bad file paths, permission errors, context overflow)
Solution:
1. Verify changed file list is correct and files are readable
2. Reduce scope if file count is very large (split into batches)
3. Fall back to systematic-code-review (sequential) as last resort

### Error: "Conflicting Findings Across Reviewers"
Cause: Two reviewers disagree on severity or interpretation of same code
Solution:
1. Keep the higher severity classification (classify UP)
2. Include both perspectives in the finding description
3. Flag as "needs author input" if genuinely ambiguous

---

## Anti-Patterns

### Anti-Pattern 1: Sequential Dispatch
**What it looks like**: Sending one Task call, waiting for it, then sending the next.
**Why wrong**: Defeats the entire purpose of parallel review. Triples wall-clock time.
**Do instead**: All 3 Task calls in a SINGLE message. This is not optional.

### Anti-Pattern 2: Skipping a Reviewer for "Simple" Changes
**What it looks like**: "This is just a config change, no need for security review."
**Why wrong**: Config changes can expose secrets, break authorization, or introduce logic errors. Simple changes cause complex bugs.
**Do instead**: Run all 3 reviewers. Let them report "no findings" if truly clean.

### Anti-Pattern 3: Reporting Without Aggregation
**What it looks like**: Dumping each reviewer's raw output as three separate sections.
**Why wrong**: Reader must mentally merge findings. Duplicate issues appear multiple times. No unified severity picture.
**Do instead**: Complete Phase 3 aggregation. Deduplicate, classify, build matrix.

### Anti-Pattern 4: Approving With Partial Results
**What it looks like**: "2 of 3 reviewers passed, looks good to merge."
**Why wrong**: The failed reviewer may have found the only CRITICAL issue. Partial coverage gives false confidence.
**Do instead**: Wait for all 3 to complete, or explicitly re-run the failed reviewer before issuing verdict.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Anti-Rationalization (Review)](../shared-patterns/anti-rationalization-review.md) - Review-specific rationalizations
- [Severity Classification](../shared-patterns/severity-classification.md) - Issue severity definitions
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "One reviewer is enough" | Different perspectives catch different issues | Run all three |
| "Security reviewer covered logic" | Specialization matters; overlap is feature not bug | Don't skip business logic |
| "Small PR, skip parallel" | Small PRs can harbor big bugs | Consider scope, not size |
| "Reviewers will just duplicate" | Each has specific focus areas | Trust the specialization |
