---
name: pr-fix
description: |
  Validate-then-fix workflow for PR review comments: Fetch, Validate, Plan,
  Fix, Commit. Use when user wants to address PR feedback, fix review comments,
  or resolve reviewer requests. Use for "fix PR comments", "address review",
  "pr-fix", or "resolve feedback". Do NOT use for creating PRs, reviewing code
  without fixing, or general debugging unrelated to PR comments.
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

## Operator Context

This skill operates as an operator for PR comment resolution workflows, configuring Claude's behavior for validated, evidence-based fixes. It implements the **Validate-Before-Fix** architectural pattern -- verify each comment's claim against actual code, then apply targeted fixes with a single clean commit.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before making any changes
- **Validate Every Comment**: NEVER blindly fix a comment without verifying its claim against actual code
- **Show Plan First**: NEVER apply fixes without presenting the fix plan and getting confirmation
- **Single Commit**: All fixes go into one commit with descriptive message referencing the PR
- **No Scope Creep**: Fix only what reviewers asked for. No "while I'm here" improvements
- **Branch Safety**: Never commit directly to main/master; work on the PR's branch

### Default Behaviors (ON unless disabled)
- **Comment Classification**: Categorize each comment as VALID, INVALID, or NEEDS-DISCUSSION
- **Before/After Display**: Show code diff for each fix before committing
- **Skip Invalid Comments**: Report invalid comments with explanation instead of fixing
- **Push After Commit**: Push changes to update the PR after committing
- **Final Report**: Display summary of fixed, skipped, and pending items

### Optional Behaviors (OFF unless enabled)
- **Reply to Comments**: Post resolution replies on fixed comment threads via `gh api`
- **Resolve Threads**: Mark fixed comment threads as resolved
- **NEEDS-DISCUSSION Auto-Reply**: Draft reply templates for ambiguous comments

## What This Skill CAN Do
- Fetch and validate PR review comments against actual code
- Distinguish valid feedback from incorrect claims
- Apply targeted fixes for validated comments only
- Commit and push all fixes in a single clean commit
- Report what was fixed, skipped, or needs discussion

## What This Skill CANNOT Do
- Fix comments without first validating them against the codebase
- Apply fixes without showing the plan and getting confirmation
- Create PRs (use pr-pipeline instead)
- Review code for new issues (use /pr-review instead)
- Make unrelated improvements beyond what reviewers requested

---

## Instructions

### Phase 1: IDENTIFY PR

**Goal**: Determine which PR to work on.

If no PR number is provided as argument:

```bash
gh pr view --json number,title,headRefName --jq '{number, title, headRefName}'
```

If no PR is found for the current branch, inform the user and stop.

Verify the current branch matches the PR's head branch. If not, ask the user before proceeding.

**Gate**: PR identified with number, title, and correct branch checked out.

### Phase 2: FETCH & VALIDATE

**Goal**: Retrieve all review comments and validate each claim against actual code.

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

**Gate**: Every comment classified with evidence. Proceed only when gate passes.

### Phase 3: SHOW FIX PLAN

**Goal**: Present the plan and get user confirmation before making changes.

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

For each VALID comment:
1. Read the file at the referenced location
2. Apply the minimal fix that addresses the comment
3. Show the before/after diff
4. Verify the fix compiles or passes basic checks

For NEEDS-DISCUSSION items the user chose to address, apply the same process.

**Gate**: All approved fixes applied. Code still compiles/passes basic checks.

### Phase 5: COMMIT & PUSH

**Goal**: Create a single clean commit and push to update the PR.

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

## Examples

### Example 1: Mixed Valid and Invalid Comments
User says: "/pr-fix 42"
Actions:
1. Fetch 5 review comments on PR #42 (IDENTIFY, FETCH)
2. Validate: 3 VALID, 1 INVALID (import IS used on line 45), 1 NEEDS-DISCUSSION (VALIDATE)
3. Show plan, user confirms 3 fixes (PLAN)
4. Apply fixes, show before/after for each (FIX)
5. Single commit, push (COMMIT)
Result: 3 fixes committed, 1 invalid explained, 1 pending discussion

### Example 2: All Comments Invalid
User says: "/pr-fix"
Actions:
1. Detect PR for current branch, fetch 3 comments (IDENTIFY, FETCH)
2. Validate all 3: each claim does not match current code state (VALIDATE)
3. Report: no changes needed, explain why each is invalid (REPORT)
Result: No changes made, user informed with evidence

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

## Anti-Patterns

### Anti-Pattern 1: Blindly Applying All Comments
**What it looks like**: Fixing every comment without checking if claims are accurate
**Why wrong**: Reviewers make mistakes. Invalid fixes introduce bugs.
**Do instead**: Validate every claim against actual code before fixing.

### Anti-Pattern 2: Fixing Beyond What Was Asked
**What it looks like**: "While fixing this nil check, I also refactored the whole function"
**Why wrong**: Scope creep makes the PR harder to review again and may introduce new issues.
**Do instead**: Fix exactly what the reviewer requested. Nothing more.

### Anti-Pattern 3: Separate Commits Per Comment
**What it looks like**: Creating 5 commits for 5 review comments
**Why wrong**: Clutters git history. Makes it harder for reviewer to see what changed.
**Do instead**: Single commit with all fixes, descriptive message listing each change.

### Anti-Pattern 4: Skipping the Plan Step
**What it looks like**: Immediately applying fixes without showing what will change
**Why wrong**: User loses control. May fix things they disagree with.
**Do instead**: Always show the fix plan and wait for confirmation.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Reviewer must be right, just fix it" | Reviewers make mistakes too | Validate claim against code |
| "Small comment, no need to verify" | Small mistakes cause real bugs | Validate every comment |
| "I'll fix extra things while I'm here" | Scope creep derails PR reviews | Fix only what was requested |
| "One commit per fix is cleaner" | Multiple small commits clutter history | Single commit for all fixes |
