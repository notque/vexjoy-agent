---
name: pr-fix
description: "Validate-then-fix workflow for PR review comments."
version: 2.0.0
user-invocable: false
argument-hint: "[<PR-number>]"
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "fix PR comments"
    - "resolve PR feedback"
    - "pr-fix"
  category: git-workflow
---

# PR Fix Skill

## Overview

This skill implements a **Validate-Before-Fix** workflow for addressing PR review comments. Each comment is verified against actual code before any fix is applied, ensuring only valid feedback gets implemented. The workflow produces a single clean commit referencing the PR, with optional replies and thread resolution.

This skill is designed for targeted comment resolution only — not for new PRs, code reviews, or unrelated debugging.

---

## Instructions

### Phase 1: IDENTIFY PR

**Goal**: Determine which PR to work on.

If no PR number is provided as argument:

```bash
gh pr view --json number,title,headRefName --jq '{number, title, headRefName}'
```

If no PR is found for the current branch, inform the user and stop. (This prevents fixing comments on wrong PRs, which is the most common integration mistake.)

Verify the current branch matches the PR's head branch. If not, ask the user before proceeding. (Branch safety constraint: Work on the PR's branch — this check enforces working on the PR's branch.)

**Gate**: PR identified with number, title, and correct branch checked out.

### Phase 2: FETCH & VALIDATE

**Goal**: Retrieve all review comments and validate each claim against actual code.

**Why validation is critical**: Reviewers make mistakes. Without verification, you risk applying invalid fixes that introduce bugs.

**Step 1: Fetch comments**

```bash
# Get review comments (inline comments on code)
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --jq '.[] | {id, path, line: .original_line, body, user: .user.login}'

# Get review-level comments
gh api repos/{owner}/{repo}/pulls/{number}/reviews \
  --jq '.[] | select(.body != "") | {id, body, state, user: .user.login}'
```

**Step 2: Validate each comment**

For EACH comment:
1. Read the actual file and line referenced
2. Test the reviewer's claim (does the issue actually exist?)
3. Classify:
   - **VALID**: Claim verified, fix needed
   - **INVALID**: Claim does not match actual code state
   - **NEEDS-DISCUSSION**: Subjective or design-level feedback

This validation step is **mandatory** — there are no exceptions. Small comments deserve the same scrutiny as large ones, because small mistakes cause real bugs.

**Gate**: Every comment classified with evidence. Proceed only when gate passes.

### Phase 3: SHOW FIX PLAN

**Goal**: Present the plan and get user confirmation before making changes.

User control over fix scope is essential. Always show the plan first. This prevents fixing things the user disagrees with and catches validation errors before commits.

Display a structured plan:

```
PR #{number}: "{title}"

Comments to address: {N} VALID, {N} INVALID, {N} NEEDS-DISCUSSION

Will fix:
  1. [VALID] src/auth.go:42 - "Add nil check for user"
  2. [VALID] src/utils.go:15 - "Remove unused import"

Will skip:
  3. [INVALID] src/api.go:99 - "URL is outdated" (verified: URL returns 200)

Needs discussion:
  4. [DISCUSS] src/db.go:55 - "Consider using transaction"

Proceed with fixes?
```

**Gate**: User confirms the plan. Proceed only when gate passes.

### Phase 4: APPLY FIXES

**Goal**: Apply each validated fix, showing before/after for each change.

Scope constraint: Fix exactly what was requested. "While I'm here" improvements derail PR reviews and may introduce unrelated issues. Stay focused.

For each VALID comment:
1. Read the file at the referenced location
2. Apply the **minimal** fix that addresses the comment (no refactoring, no enhancements)
3. Show the before/after diff
4. Verify the fix compiles or passes basic checks

For NEEDS-DISCUSSION items the user chose to address, apply the same process.

**Gate**: All approved fixes applied. Code still compiles/passes basic checks.

### Phase 5: COMMIT & PUSH

**Goal**: Create a single clean commit and push to update the PR.

Commit discipline matters: Multiple small commits clutter git history and make it harder for reviewers to see what changed. Always combine all fixes into a single descriptive commit. This follows the workflow principle: single commit per logical change set.

```bash
# Stage changed files (list specific files, not -A)
git add {file1} {file2} ...

# Commit with descriptive message
git commit -m "Address PR review comments

- {fix description 1}
- {fix description 2}
- {fix description 3}

Resolves review comments on PR #{number}"

# Push to update PR
git push
```

### Phase 6: FINAL REPORT

**Goal**: Summarize what was done.

```
PR FIX COMPLETE

Fixed: {N} issues
Skipped: {N} (invalid)
Pending: {N} (needs discussion)

Commit: {hash} "Address PR review comments"
Pushed to: origin/{branch}

PR: https://github.com/{owner}/{repo}/pull/{number}

Remaining:
  - Discuss {topic} in {file}:{line} with reviewer
```

---

## Examples and Constraints in Practice

### Example 1: Mixed Valid and Invalid Comments

User says: "/pr-fix 42"

**How the constraints apply:**

1. Fetch 5 review comments on PR #42 (IDENTIFY, FETCH)
2. **Validate each claim** (core constraint: always validate each claim before fixing): 3 VALID, 1 INVALID (import IS used on line 45), 1 NEEDS-DISCUSSION
   - Invalid comment detected because actual code shows import is used. This prevents an accidental break.
3. **Show plan, get confirmation** (core constraint: show the plan and get confirmation before applying fixes): User reviews and confirms 3 fixes
4. **Apply minimal fixes only**: No extra improvements despite obvious refactoring opportunities
5. **Single commit** (not 3): Combines all changes with references PR
6. Result: 3 fixes committed, 1 invalid explained, 1 pending discussion

### Example 2: All Comments Invalid

User says: "/pr-fix"

**How the constraints apply:**

1. Detect PR for current branch, fetch 3 comments (IDENTIFY, FETCH)
2. **Validate all claims**: Each claim does not match current code state (the validation step catches this)
3. **Report with evidence**: No changes made, user informed with specific reasons (URL actually returns 200, variable is already declared, etc.)
4. Result: No commits created, user learns why comments were invalid

---

## Error Handling

### Error: "No PR Found for Current Branch"
Cause: Branch has no open PR, or `gh` not authenticated
Solution:
1. Verify `gh auth status` succeeds
2. Check if a PR exists: `gh pr list --head {branch}`
3. If no PR, suggest creating one first

### Error: "Comment References Deleted or Moved Code"
Cause: Code was refactored since the review, line numbers no longer match
Solution:
1. Search for the referenced code pattern in the current file
2. If found at a different location, apply fix there
3. If code was removed entirely, mark comment as stale and skip

### Error: "Fix Causes Test Failures"
Cause: Reviewer's suggestion introduces a regression, or other tests depend on old behavior
Solution:
1. Run tests to identify which fail
2. Evaluate whether tests need updating or fix needs adjustment
3. If reviewer's suggestion is wrong, classify as NEEDS-DISCUSSION
4. Document the test failure evidence

---

## References

### Related Skills
- `pr-pipeline` — For creating PRs from scratch
- `pr-review` — For reviewing code without fixing
- `systematic-debugging` — For general debugging unrelated to PR comments

### PR Comment Best Practices
- Always validate before fixing (this prevents introducing bugs that reviewers caught)
- Classify comments as VALID, INVALID, or NEEDS-DISCUSSION (ensures evidence-based decisions)
- Show the plan before committing (maintains user control and catches errors early)
- Single commit per fix cycle (clean git history for reviewers)
