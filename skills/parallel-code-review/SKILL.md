---
name: parallel-code-review
description: "Parallel 3-reviewer code review: Security, Business-Logic, Architecture."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Task
routing:
  triggers:
    - "parallel review"
    - "3-reviewer review"
    - "security review"
    - "multi-reviewer"
    - "concurrent review"
  category: code-review
---

# Parallel Code Review Skill

Orchestrate three specialized code reviewers (Security, Business Logic, Architecture) in true parallel using the Fan-Out/Fan-In pattern. Each reviewer runs independently with domain-specific focus, then findings are aggregated by severity into a unified BLOCK/FIX/APPROVE verdict.

---

## Instructions

### Phase 1: IDENTIFY SCOPE

**Goal**: Determine changed files and select appropriate agents before dispatching.

**Step 1: Read repository CLAUDE.md** to load project-specific conventions that reviewers must respect.

**Step 2: List changed files**

```bash
# For recent commits:
git diff --name-only HEAD~1
# For PRs:
gh pr view --json files -q '.files[].path'
```

**Step 3: Select architecture reviewer agent** based on the dominant language. This ensures the architecture reviewer applies idiomatic standards rather than generic advice, because different languages have fundamentally different design patterns and conventions.

| File Types | Agent |
|-----------|-------|
| `.go` files | `golang-general-engineer` |
| `.py` files | `python-general-engineer` |
| `.ts`/`.tsx` files | `typescript-frontend-engineer` |
| Mixed or other | `Explore` |

**Optional enrichments** (only when user explicitly requests):
- "include threat model" -- adds threat modeling to Security reviewer scope
- "find breaking commit" -- adds git bisect regression tracking
- "benchmark" -- adds performance profiling to Architecture reviewer scope

**Gate**: Changed files listed, architecture reviewer agent selected. Proceed only when gate passes.

### Phase 2: DISPATCH PARALLEL REVIEWERS

**Goal**: Launch all 3 reviewers in a single message for true concurrent execution.

**Critical constraint**: All three Task calls MUST appear in ONE response. Sending them sequentially triples wall-clock time and defeats the purpose of parallel review. This is not optional—parallelism is the entire value proposition of this skill.

Dispatch exactly these 3 agents. This is a read-only review—reviewers observe and report but never modify code.

**Reviewer 1 -- Security**
- Focus: OWASP Top 10, authentication, authorization, input validation, secrets exposure
- Output: Severity-classified findings with `file:line` references

**Reviewer 2 -- Business Logic**
- Focus: Requirements coverage, edge cases, state transitions, data validation, failure modes
- Output: Severity-classified findings with `file:line` references

**Reviewer 3 -- Architecture** (using agent selected in Phase 1)
- Focus: Design patterns, naming, structure, performance, maintainability
- Output: Severity-classified findings with `file:line` references

**Critical constraint**: Always run all 3 reviewers regardless of perceived change simplicity. Config changes can expose secrets, "trivial" fixes can break authorization, and each reviewer's specialization catches issues the others miss. Let a reviewer report "no findings" rather than skip it—because silence is information too.

**Gate**: All 3 Task calls dispatched in a single message. Proceed only when ALL 3 return results—never issue a verdict from partial results, because the missing reviewer may hold the only CRITICAL finding. Partial results are worse than no review.

### Phase 3: AGGREGATE

**Goal**: Merge all findings into a unified severity-classified report.

**Critical constraint**: Never dump raw reviewer outputs as three separate sections—the reader should not have to mentally merge findings across reviewers. Your job is to synthesize, not summarize.

**Step 1: Classify each finding by severity**

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Security vulnerability, data loss risk | BLOCK merge |
| HIGH | Significant bug, logic error | Fix before merge |
| MEDIUM | Code quality issue, potential problem | Should fix |
| LOW | Minor issue, style preference | Nice to have |

**Step 2: Deduplicate overlapping findings**

Multiple reviewers may flag the same issue. Merge duplicates, keeping the highest severity. Overlap between reviewers is a feature (independent confirmation), but the report should consolidate it so readers see a unified issue once, not three times.

**Step 3: Build reviewer summary matrix**

Include this matrix in every report so stakeholders see the severity distribution at a glance:

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

**Critical constraint**: Every review must end with an explicit verdict. Ambiguity is a decision to merge untested code. Choose: BLOCK, FIX, or APPROVE.

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

After user addresses CRITICAL issues, re-run ALL 3 reviewers (not just the one that found the issue) to verify:
1. Original CRITICAL issues resolved
2. No regressions introduced
3. No new CRITICAL/HIGH issues from fixes

Re-run all three because fixes often introduce new issues in adjacent code, and you need confirmation across all three domains that the solution is safe.

**Gate**: Structured report delivered with verdict. Review is complete.

---

## Error Handling

### Error: "Reviewer Times Out"

**Cause**: One or more Task agents exceed execution time.

**Solution**:
1. Report findings from completed reviewers immediately—a partial review is better than no review, because you'll know at least some classes of issues are present.
2. Note which reviewer(s) timed out and on which files, so the user understands the blind spots.
3. Offer to re-run failed reviewer separately or proceed with partial results (but disclose the incompleteness in the verdict).

### Error: "All Reviewers Fail"

**Cause**: Systemic issue (bad file paths, permission errors, context overflow).

**Solution**:
1. Verify changed file list is correct and files are readable—start with the basics.
2. Reduce scope if file count is very large (split into batches), because each reviewer needs enough context tokens to reason properly.
3. Fall back to systematic-code-review (sequential) as last resort, because at least one reviewer completing sequentially is better than zero reviewers failing.

### Error: "Conflicting Findings Across Reviewers"

**Cause**: Two reviewers disagree on severity or interpretation of same code.

**Solution**:
1. Keep the higher severity classification (classify UP), because you want to err on the side of caution—false positives are correctable, false negatives ship bugs.
2. Include both perspectives in the finding description, so the code author understands the disagreement and can make an informed decision.
3. Flag as "needs author input" if genuinely ambiguous, and include both interpretations verbatim so they can choose.

---

## References

- Severity classification: CRITICAL (blocks merge), HIGH (fix before), MEDIUM (should fix), LOW (nice to have)
- Verdict decision tree: Any CRITICAL → BLOCK; HIGH without CRITICAL → FIX; MEDIUM/LOW only → APPROVE
- Re-review trigger: Always re-run all 3 reviewers after BLOCK fixes to catch regressions
