---
name: parallel-code-review
description: "Parallel 3-reviewer code review: Security, Business-Logic, Architecture."
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
  pairs_with:
    - systematic-code-review
    - verification-before-completion
---

# Parallel Code Review Skill

Orchestrate three specialized reviewers (Security, Business Logic, Architecture) in true parallel via Fan-Out/Fan-In. Each runs independently with domain-specific focus, then findings aggregate by severity into a unified BLOCK/FIX/APPROVE verdict.

---

## Instructions

### Phase 1: IDENTIFY SCOPE

**Step 1: Read repository CLAUDE.md** for project-specific conventions.

**Step 2: List changed files**

```bash
# Recent commits:
git diff --name-only HEAD~1
# PRs:
gh pr view --json files -q '.files[].path'
```

**Step 3: Select architecture reviewer agent** based on dominant language.

| File Types | Agent |
|-----------|-------|
| `.go` files | `golang-general-engineer` |
| `.py` files | `python-general-engineer` |
| `.ts`/`.tsx` files | `typescript-frontend-engineer` |
| Mixed or other | `Explore` |

**Optional enrichments** (only when user explicitly requests):
- "include threat model" -- adds threat modeling to Security scope
- "find breaking commit" -- adds git bisect regression tracking
- "benchmark" -- adds performance profiling to Architecture scope

**Gate**: Changed files listed, architecture reviewer selected.

### Phase 2: DISPATCH PARALLEL REVIEWERS

All three Task calls MUST appear in ONE response. Sequential dispatch triples wall-clock time.

Dispatch exactly 3 read-only reviewers:

**Reviewer 1 -- Security**
- Focus: OWASP Top 10, auth, input validation, secrets exposure
- Output: Severity-classified findings with `file:line` references

**Reviewer 2 -- Business Logic**
- Focus: Requirements coverage, edge cases, state transitions, data validation, failure modes
- Output: Severity-classified findings with `file:line` references

**Reviewer 3 -- Architecture** (agent from Phase 1)
- Focus: Design patterns, naming, structure, performance, maintainability
- Output: Severity-classified findings with `file:line` references

Always run all 3 regardless of perceived simplicity. Config changes can expose secrets; "trivial" fixes can break authorization. Let a reviewer report "no findings" rather than skip it.

**Gate**: All 3 dispatched in a single message. Wait for ALL 3 to return. Never verdict from partial results.

### Phase 3: AGGREGATE

Never dump raw reviewer outputs as separate sections. Synthesize, not summarize.

**Step 1: Classify by severity**

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Security vulnerability, data loss risk | BLOCK merge |
| HIGH | Significant bug, logic error | Fix before merge |
| MEDIUM | Code quality issue, potential problem | Should fix |
| LOW | Minor issue, style preference | Nice to have |

**Step 2: Deduplicate** -- merge overlapping findings, keep highest severity.

**Step 3: Build reviewer summary matrix**

```
| Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
|----------------|----------|------|--------|-----|
| Security       | N        | N    | N      | N   |
| Business Logic | N        | N    | N      | N   |
| Architecture   | N        | N    | N      | N   |
| **Total**      | **N**    | **N**| **N**  | **N**|
```

**Gate**: All findings classified, deduplicated, and summarized.

### Phase 4: VERDICT

Every review must end with an explicit verdict. Choose: BLOCK, FIX, or APPROVE.

**Step 1: Determine verdict**

| Condition | Verdict |
|-----------|---------|
| Any CRITICAL findings | **BLOCK** |
| HIGH findings, no CRITICAL | **FIX** (fix before merge) |
| Only MEDIUM/LOW findings | **APPROVE** (with suggestions) |

**Step 2: Output structured report**

```markdown
## Parallel Review Complete

### Severity Matrix

| Severity | Count | Summary |
|----------|-------|---------|
| Critical | N | One-line aggregated summary |
| High     | N | One-line aggregated summary |
| Medium   | N | One-line aggregated summary |
| Low      | N | One-line aggregated summary |

Details by reviewer below.

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

**Schema Validation (automatic):**
```bash
python3 scripts/validate-review-output.py --type parallel review-output.md
```

**Step 3: If BLOCK, initiate re-review**

After user addresses CRITICAL issues, re-run ALL 3 reviewers to verify:
1. Original CRITICAL issues resolved
2. No regressions introduced
3. No new CRITICAL/HIGH issues from fixes

**Gate**: Structured report delivered with verdict.

---

## Error Handling

### Error: "Reviewer Times Out"
1. Report findings from completed reviewers immediately.
2. Note which reviewer(s) timed out and on which files.
3. Offer to re-run failed reviewer or proceed with partial results (disclose incompleteness in verdict).

### Error: "All Reviewers Fail"
1. Verify changed file list is correct and files are readable.
2. Reduce scope if file count is large (split into batches).
3. Fall back to systematic-code-review (sequential) as last resort.

### Error: "Conflicting Findings Across Reviewers"
1. Keep higher severity classification (classify UP).
2. Include both perspectives in the finding description.
3. Flag as "needs author input" if genuinely ambiguous.

---

## References

- Severity: CRITICAL (blocks merge), HIGH (fix before), MEDIUM (should fix), LOW (nice to have)
- Verdict: Any CRITICAL -> BLOCK; HIGH without CRITICAL -> FIX; MEDIUM/LOW only -> APPROVE
- Re-review: Always re-run all 3 after BLOCK fixes
