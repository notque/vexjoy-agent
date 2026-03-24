---
name: pr-review-address-feedback
description: |
  Fetch PR feedback from all GitHub sources and validate every comment before
  acting. Use when user needs to process PR review comments, address reviewer
  feedback, or triage pull request discussions. Use for "review comments",
  "PR feedback", "address reviews", "address feedback", or "what did reviewers
  say". Do NOT use for creating new PRs, code review of local changes, or
  general code analysis without an existing PR.
version: 2.0.0
user-invocable: true
argument-hint: "[<PR-number>]"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Edit
  - Write
---

# PR Review Address Feedback Skill

## Operator Context

This skill operates as an operator for PR feedback processing, configuring Claude's behavior for rigorous validation of reviewer comments before acting on them. It implements a **Validate-Then-Act** pattern -- fetch all feedback, verify each claim independently, summarize findings, then fix only validated issues.

### Hardcoded Behaviors (Always Apply)
- **Fetch All Sources**: Always query reviews, inline comments, AND issue comments -- never rely on a single endpoint
- **Validate Before Acting**: NEVER start fixing code until every comment has been independently verified
- **Evidence Over Trust**: Reviewer claims are treated as hypotheses, not facts -- verify with code, tests, or HTTP requests
- **Summary Table Required**: Always present a validation summary table before making any changes
- **Phase Gates Enforced**: Each phase must complete before the next begins -- no skipping

### Default Behaviors (ON unless disabled)
- **Auto-Detect PR Context**: Infer owner/repo/PR number from current git branch and remote when not provided
- **Structured Validation Output**: Use the validation entry format for each comment
- **Classify Verdicts**: Every comment gets VALID, INVALID, or NEEDS-DISCUSSION
- **Show Verification Work**: Display evidence for each verdict, not just the conclusion
- **Fix Only VALID Issues**: Skip INVALID comments, escalate NEEDS-DISCUSSION to user

### Optional Behaviors (OFF unless enabled)
- **Post Reply Comments**: Reply to individual review comments on GitHub with findings
- **Request Re-Review**: Automatically request re-review after pushing fixes
- **Commit Per Finding**: Create separate commits for each validated fix
- **Diff Verification**: Run `git diff` after fixes to confirm only intended changes

## What This Skill CAN Do
- Fetch and consolidate PR feedback from all three GitHub comment sources
- Independently verify each reviewer claim against the actual codebase
- Classify comments as VALID, INVALID, or NEEDS-DISCUSSION with evidence
- Fix validated issues after presenting the summary table
- Detect reviewer claims that lack supporting evidence

## What This Skill CANNOT Do
- Fix issues without completing the validation phase first
- Trust reviewer claims without independent verification
- Skip the summary table and proceed directly to fixes
- Perform general code review (use systematic-code-review instead)
- Create or submit new pull requests (use pr-pipeline instead)

---

## Instructions

### Usage

```
/pr-review-address-feedback [owner] [repo] [pr_number]
```

If no arguments provided, auto-detect from current git branch and remote.

### Phase 1: FETCH

**Goal**: Retrieve all feedback from every GitHub comment source.

Use `gh` CLI (handles auth automatically):

```bash
# Get PR details
gh api repos/{owner}/{repo}/pulls/{pr_number}

# Get formal reviews (submitted via "Review changes")
gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews

# Get inline code comments (added directly to specific lines)
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments

# Get issue/PR comments (general conversation - where Claude typically comments)
gh api repos/{owner}/{repo}/issues/{pr_number}/comments
```

All three comment sources must be fetched and combined. Treat all feedback identically regardless of submission method:
- **Formal reviews** -- submitted via GitHub's "Review changes" button
- **Inline code comments** -- added directly to specific code lines
- **Issue/PR comments** -- general comments on the PR conversation

**Gate**: All three endpoints queried successfully, feedback consolidated into a single list. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Independently verify every reviewer comment before acting.

**Step 1: Create a validation entry for each comment**

```
VALIDATING: [file:line] - [brief description]

Claim: [What the reviewer claims]

Verification:
  [ ] Read actual file/line: [YES/NO]
  [ ] Tested claim: [describe test performed]
  [ ] Result: [what you found]

Verdict: [VALID | INVALID | NEEDS-DISCUSSION]
Reason: [one sentence explanation]
```

**Step 2: Apply verification tests by comment type**

| Comment Type | Required Verification |
|---|---|
| "Unused import/variable" | Grep for usage in file, check if actually unused |
| "Security issue" | Analyze attack vector, test if exploitable |
| "Bug in logic" | Write test case or trace execution path |
| "URL is wrong/outdated" | `curl -sI [URL]` to check HTTP status |
| "Date is wrong" | Verify actual date, check if format matters |
| "Regex doesn't work" | Test regex with actual inputs |
| "Missing null check" | Trace where value comes from, check if can be null |
| "Performance issue" | Only valid if measurable; otherwise NEEDS-DISCUSSION |
| "Style/formatting" | Check if matches project conventions |
| "Off-by-one error" | Write boundary test cases |

**Step 3: Flag automatic INVALID patterns**

Flag as likely INVALID if reviewer:
- Claims code behavior without showing evidence
- Says "future date" without checking if URL works
- Claims unused without searching codebase
- Suggests "safer" approach without demonstrating risk

**Gate**: Every comment has a validation entry with verdict and evidence. Proceed only when gate passes.

### Phase 3: SUMMARIZE

**Goal**: Present all findings in a summary table before any fixes.

```
VALIDATION SUMMARY

Total Comments: [N] (from reviews + inline + issue comments)

| # | File:Line | Claim | Verdict | Action |
|---|-----------|-------|---------|--------|
| 1 | foo.py:42 | Unused import | VALID | Fix |
| 2 | bar.js:15 | Future date | INVALID | Skip |
| 3 | baz.go:99 | Race condition | NEEDS-DISCUSSION | Ask user |

VALID: [count] - Will fix
INVALID: [count] - Will skip with reason
NEEDS-DISCUSSION: [count] - Requires user input
```

**Gate**: Summary table displayed. User has acknowledged NEEDS-DISCUSSION items (if any). Proceed only when gate passes.

### Phase 4: EXECUTE

**Goal**: Fix only VALID issues, verify each fix works.

For each validated fix:

1. State which validated comment is being addressed
2. Make the change
3. Verify the fix works (run tests, grep for correctness, inspect result)
4. Confirm no regressions from the change

Do NOT fix INVALID comments. Escalate NEEDS-DISCUSSION items to the user.

**Gate**: All VALID issues fixed and verified. No regressions introduced.

### Phase 5: LEARN

**Goal**: Extract reusable review patterns into the retro knowledge store.

After fixes are applied, reflect on what was learned:

**Step 1: Identify reusable patterns**

Ask:
- Did we find a recurring reviewer concern that applies broadly?
- Did we discover a pattern (valid or invalid) that would help in future reviews?
- Did we learn something about this codebase's conventions from the reviewer feedback?
- Were there common false positives that should be documented?

If nothing reusable was learned, skip recording.

**Step 2: Record via retro-record-adhoc**

```bash
python3 ~/.claude/scripts/feature-state.py retro-record-adhoc TOPIC KEY "VALUE"
```

Where:
- **TOPIC**: Match the domain of the reviewed code (e.g., `go-patterns`, `python-patterns`, `code-review-patterns`)
- **KEY**: Short kebab-case identifier (e.g., `reviewer-false-positive-unused-reexport`)
- **VALUE**: 1-2 sentence specific, actionable finding

**Step 3: Report**

```
LEARNED: [key] → [topic]
  [one-line value]
```

**Quality gate**: Only record specific, actionable findings. "Reviewers are sometimes wrong" is NOT worth recording. "Reviewers flag fmt.Errorf wrapping but the org convention is errors.New" IS worth recording.

**Gate**: Learning recorded (or skipped if nothing reusable). Review complete.

---

## Trust Hierarchy

Verification sources in order of trust:

1. **Running code/tests** -- highest trust
2. **HTTP requests** -- verify URLs, APIs
3. **Grep/search results** -- verify usage claims
4. **Reading source** -- understand context
5. **Reviewer's word** -- lowest trust (always verify)

---

## Examples

### Example 1: Mixed Valid and Invalid Comments

User says: "/pr-review-address-feedback your-org your-repo 42"
Actions:
1. Fetch all comments from reviews, inline, and issue endpoints (FETCH)
2. Validate each: find that "unused import" is valid, but "future date URL" works fine (VALIDATE)
3. Present table showing 1 VALID, 1 INVALID (SUMMARIZE)
4. Fix the unused import, skip the URL comment (EXECUTE)
Result: Only verified issues fixed, invalid feedback documented with evidence

### Example 2: Auto-Detected PR with Discussion Items

User says: "/pr-review-address-feedback" (no arguments, on feature branch)
Actions:
1. Detect owner/repo/PR from git remote and branch, fetch all comments (FETCH)
2. Validate each: "race condition" claim needs reproduction attempt (VALIDATE)
3. Present table with NEEDS-DISCUSSION item, ask user for guidance (SUMMARIZE)
4. Fix validated items, skip discussion items pending user input (EXECUTE)
Result: User decides on ambiguous feedback, only confirmed issues addressed

---

## Error Handling

### Error: "gh CLI Not Authenticated"
Cause: GitHub CLI not logged in or token expired
Solution:
1. Run `gh auth status` to check authentication state
2. If not authenticated, prompt user to run `gh auth login`
3. Verify with `gh api user` before retrying

### Error: "PR Not Found or No Access"
Cause: Wrong owner/repo/PR number, or repository is private without access
Solution:
1. Verify PR exists: `gh api repos/{owner}/{repo}/pulls/{pr_number}`
2. Check repo visibility and token scopes
3. If auto-detecting, verify remote URL and current branch has an open PR

### Error: "No Comments Found on PR"
Cause: PR has no review feedback yet, or all comments are from bots
Solution:
1. Confirm PR exists and is open
2. Check if reviews are pending (requested but not submitted)
3. Report "No reviewer feedback found" and exit cleanly -- do not fabricate findings

---

## Anti-Patterns

### Anti-Pattern 1: Fixing Before Validating
**What it looks like**: Reading reviewer comments and immediately editing code
**Why wrong**: Reviewer may be wrong. Fixing unverified claims wastes time and can introduce bugs.
**Do instead**: Complete Phase 2 validation for every comment before touching any code.

### Anti-Pattern 2: Trusting Claims Without Evidence
**What it looks like**: Accepting "this import is unused" without grepping for usage
**Why wrong**: Reviewers often miss indirect usage, re-exports, or dynamic references.
**Do instead**: Independently verify each claim using the verification tests table.

### Anti-Pattern 3: Skipping the Summary Table
**What it looks like**: Validating comments one at a time and fixing each immediately
**Why wrong**: User loses the big picture. NEEDS-DISCUSSION items may change the approach to VALID ones.
**Do instead**: Complete all validations, present the full summary table, then proceed to fixes.

### Anti-Pattern 4: Fetching Only One Comment Source
**What it looks like**: Checking only `/pulls/{pr}/reviews` and missing inline or issue comments
**Why wrong**: Claude and other tools often comment via `/issues/{pr}/comments`, which is a separate endpoint. Missing any source means missing feedback.
**Do instead**: Always fetch from all three endpoints: reviews, pull comments, and issue comments.

### Anti-Pattern 5: Downgrading NEEDS-DISCUSSION to VALID
**What it looks like**: Marking ambiguous feedback as VALID to avoid asking the user
**Why wrong**: Acting on ambiguous feedback without user input may fix the wrong thing or introduce unintended behavior.
**Do instead**: Classify honestly. Present NEEDS-DISCUSSION items to the user for their decision.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization: Code Review](../shared-patterns/anti-rationalization-review.md) - Review-specific rationalization prevention
- [Anti-Rationalization Core](../shared-patterns/anti-rationalization-core.md) - Universal anti-rationalization patterns
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|---|---|---|
| "Reviewer is probably right" | Probably is not verified | Test the claim independently |
| "Small comment, just fix it" | Small fixes can break things | Validate first, even for trivial claims |
| "Already validated similar comment" | Each comment has unique context | Validate each comment individually |
| "No time for the summary table" | Summary prevents premature action | Always present the table before fixes |
