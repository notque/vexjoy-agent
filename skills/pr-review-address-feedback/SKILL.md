---
name: pr-review-address-feedback
description: "Fetch PR feedback from GitHub and validate comments before acting."
version: 2.0.0
user-invocable: false
argument-hint: "[<PR-number>]"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Edit
  - Write
routing:
  triggers:
    - "process PR feedback"
    - "address review comments"
  category: git-workflow
---

# PR Review Address Feedback Skill

## Overview

This skill processes PR feedback by implementing a **Validate-Then-Act** pattern: fetch all comments from every GitHub source, independently verify each claim, present findings in a summary table, then fix only validated issues. The pattern is mandatory because:
- Reviewer claims are hypotheses, not facts (verify with code/tests/HTTP requests)
- Single comment sources miss feedback (reviews, inline comments, and issue comments are separate endpoints)
- Unverified fixes waste time and introduce bugs (validation phase gates code changes)

### Key Principles

**Fetch Comprehensively**: Always query all three endpoints — reviews, inline comments, AND issue comments. Claude and other tools comment via `/issues/{pr}/comments`, which is a separate endpoint. Missing any source means missing feedback.

**Verify Independently**: Reviewer claims must be tested using the verification tests table. Reviewers often miss indirect usage, re-exports, or dynamic references. Trust hierarchy (highest to lowest): running code/tests → HTTP requests → grep/search → reading source → reviewer's word.

**Classify Honestly**: Classify comments as VALID, INVALID, or NEEDS-DISCUSSION based on evidence. Never downgrade NEEDS-DISCUSSION to VALID to avoid asking the user — acting on ambiguous feedback without user input may fix the wrong thing.

**Present Summary Before Fixes**: Complete all validations and present the full summary table before making any code changes. User loses the big picture if you validate and fix incrementally, and NEEDS-DISCUSSION items may change approach to VALID ones.

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

All three comment sources must be fetched and combined because feedback arrives through different endpoints. Treat all feedback identically regardless of submission method:
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

Flag as likely INVALID because evidence is required for all claims:
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

Only record specific, actionable findings because "Reviewers are sometimes wrong" provides no guidance. "Reviewers flag fmt.Errorf wrapping but the org convention is errors.New" IS worth recording as a real org standard.

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

## References

Trust hierarchy, validation checklist patterns, and phase-gate enforcement are derived from:
- Anti-Rationalization principles (verify claims independently, never skip phases for time)
- Code review rigor standards (validate before touching code, classify honestly)
- Evidence-based troubleshooting (highest-trust sources first, lowest-trust sources last)
