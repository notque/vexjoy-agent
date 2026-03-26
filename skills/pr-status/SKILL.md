---
name: pr-status
description: |
  Quick status check for current branch and PR state showing local changes,
  CI results, reviews, and merge readiness. Use when user wants branch status,
  PR state, CI check results, review status, or merge readiness. Use for
  "pr status", "what's the status", "is my PR ready", "check CI". Do NOT use
  for creating PRs, pushing changes, or fixing review comments.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Bash
  - Read
routing:
  force_route: true
  triggers:
    - "PR status"
    - "branch status"
    - "merge readiness"
  category: git-workflow
---

# PR Status Skill

## Operator Context

This skill operates as an operator for PR status checks, configuring Claude's behavior for fast, accurate branch and PR state reporting. It implements a **Sequential Gather** pattern -- collect git state, PR metadata, CI status, reviews, and merge readiness in ordered steps, then present a unified status report.

### Hardcoded Behaviors (Always Apply)
- **Read-Only**: Never modify files, branches, or PR state during status checks
- **Fetch Before Report**: Always `git fetch` before comparing local/remote state
- **gh CLI Required**: Verify `gh` is installed and authenticated before PR queries
- **Complete Report**: Show all available sections; never skip sections silently
- **Current Branch Context**: Always report which branch is being checked

### Default Behaviors (ON unless disabled)
- **CI Detail**: Show individual check names with pass/fail status
- **Review Summary**: Show reviewer names with their review state
- **Merge Readiness**: Report conflicts, required approvals, and blocking checks
- **Behind-Main Count**: Show how many commits behind the base branch
- **Claude Review Detection**: Check for Claude Code review comments on the PR

### Optional Behaviors (OFF unless enabled)
- **Recent PRs on Main**: When on main branch, list recent PRs
- **Verbose CI Output**: Show full CI log URLs for failed checks
- **Cross-Repository Status**: Check PRs across multiple remotes

## What This Skill CAN Do
- Report current branch name and its relationship to base branch
- Show local working tree state (clean, modified files, ahead/behind)
- Display PR metadata (number, title, state, URL)
- List CI check results with pass/fail per check
- Summarize review states per reviewer
- Report merge readiness (conflicts, approvals needed)
- Detect Claude Code review activity

## What This Skill CANNOT Do
- Create or update pull requests (use pr-sync instead)
- Fix review comments or CI failures (use pr-fix instead)
- Push commits or modify git state
- Perform code review (use /pr-review instead)

---

## Instructions

### Step 0: Check Prerequisites

Verify `gh` CLI is available and authenticated. If not, report the missing prerequisite and stop.

```bash
command -v gh &> /dev/null || { echo "GitHub CLI (gh) not installed. Install: https://cli.github.com/"; exit 1; }
gh auth status &> /dev/null || { echo "GitHub CLI not authenticated. Run: gh auth login"; exit 1; }
```

### Step 1: Get Branch Info

```bash
CURRENT_BRANCH=$(git branch --show-current)
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")
```

If on the main branch, report that and optionally list recent PRs. No further steps needed.

### Step 2: Check Local State

```bash
# Working tree status
DIRTY=$(git status --porcelain)
if [[ -z "$DIRTY" ]]; then
    echo "Clean working tree"
else
    FILE_COUNT=$(echo "$DIRTY" | wc -l)
    echo "$FILE_COUNT files modified"
fi

# Fetch and compare
git fetch origin --quiet
AHEAD=$(git rev-list origin/$CURRENT_BRANCH..$CURRENT_BRANCH --count 2>/dev/null || echo "0")
BEHIND=$(git rev-list $CURRENT_BRANCH..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
BEHIND_MAIN=$(git rev-list $CURRENT_BRANCH..origin/$MAIN_BRANCH --count 2>/dev/null || echo "0")
```

### Step 3: Check PR Status

```bash
PR_JSON=$(gh pr view --json number,title,state,url,reviewDecision,statusCheckRollup,mergeable,reviews 2>/dev/null)

if [[ -z "$PR_JSON" ]]; then
    echo "No PR exists for this branch"
else
    PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number')
    PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')
    PR_STATE=$(echo "$PR_JSON" | jq -r '.state')
    PR_URL=$(echo "$PR_JSON" | jq -r '.url')
fi
```

If no PR exists, report the branch state and suggest creating one. Skip Steps 4-7.

### Step 4: Check CI Status

```bash
gh pr checks --json name,state,conclusion 2>/dev/null | jq -r '.[] | "\(.conclusion // .state) \(.name)"'
```

### Step 5: Check Claude Review

```bash
CLAUDE_COMMENTS=$(gh pr view --json comments --jq '[.comments[] | select(
  (.author.login == "claude") or
  ((.author.login == "github-actions[bot]") and (.body | test("PR Review:|Claude|claude-code-action"; "i")))
)] | length')

if [[ "$CLAUDE_COMMENTS" -gt 0 ]]; then
    echo "Claude review completed ($CLAUDE_COMMENTS comments)"
else
    CLAUDE_WORKFLOW=$(gh run list --workflow=claude.yml --limit 1 --json conclusion,status --jq '.[0]' 2>/dev/null)
    if [[ -n "$CLAUDE_WORKFLOW" ]]; then
        STATUS=$(echo "$CLAUDE_WORKFLOW" | jq -r '.status // .conclusion')
        echo "Claude review status: $STATUS"
    else
        echo "No Claude review configured"
    fi
fi
```

### Step 6: Check Reviews

```bash
gh pr view --json reviews --jq '.reviews[] | "\(.author.login): \(.state)"'
gh pr view --json reviewDecision --jq '.reviewDecision'
```

### Step 7: Check Merge Status

```bash
gh pr view --json mergeable --jq '.mergeable'
```

### Step 8: Present Status Report

Format the collected information into a structured report:

```
PR STATUS
=========

Branch: [current] -> [base] ([N commits behind])

Local State:
  [clean/modified] working tree
  [ahead/behind] remote

PR #[N]: "[title]"
  State: [Open/Closed/Merged]
  URL: [url]

  CI Status:
    [pass/fail] [check-name] (per check)

  Claude Review:
    [status]

  Reviews:
    [reviewer]: [state] (per reviewer)

  Merge Status:
    [mergeable/conflicts/approvals needed]
```

---

## Examples

### Example 1: Feature Branch with Open PR
User says: "/pr-status"
Actions:
1. Verify gh CLI available, fetch latest
2. Report branch `feature/auth` is 2 behind main
3. Show PR #45 is open, CI passing, 1 approval, no conflicts
4. Report ready to merge
Result: Complete status showing merge-ready PR

### Example 2: No PR Exists
User says: "/pr-status"
Actions:
1. Verify gh CLI, identify branch `fix/typo`
2. Report 3 modified files, 1 commit not pushed
3. Report no PR exists for this branch
Result: Branch state shown, suggest creating PR

### Example 3: On Main Branch
User says: "/pr-status"
Actions:
1. Detect current branch is main
2. List recent PRs if optional behavior enabled
3. Suggest switching to a feature branch
Result: Brief report noting user is on main

---

## Error Handling

### Error: "gh CLI Not Installed or Not Authenticated"
Cause: GitHub CLI missing or `gh auth login` not completed
Solution:
1. Report the specific missing prerequisite
2. Provide installation/auth URL
3. Stop -- do not attempt partial status without gh

### Error: "No Remote Tracking Branch"
Cause: Branch exists locally but has never been pushed
Solution:
1. Report local branch state (modified files, commits)
2. Note that no remote tracking branch exists
3. Suggest pushing with `git push -u origin [branch]`

### Error: "gh pr view Fails with Non-Zero Exit"
Cause: No PR exists for the branch, or network/auth issue
Solution:
1. Check if error is "no pull requests found" vs network error
2. For no PR: report branch state, suggest creating one
3. For network/auth: report the error, suggest `gh auth status`

---

## Anti-Patterns

### Anti-Pattern 1: Modifying State During Status Check
**What it looks like**: Pushing commits, creating PRs, or fixing issues during a status check
**Why wrong**: Status is read-only. Modifications belong to other skills.
**Do instead**: Report status only. Suggest appropriate skills for actions.

### Anti-Pattern 2: Skipping Fetch Before Reporting
**What it looks like**: Reporting ahead/behind counts from stale local refs
**Why wrong**: Produces inaccurate status that misleads the user
**Do instead**: Always `git fetch origin --quiet` before comparing

### Anti-Pattern 3: Partial Report Without Explanation
**What it looks like**: Showing only CI status, omitting reviews and merge state
**Why wrong**: User expects complete picture. Missing sections hide problems.
**Do instead**: Show all sections. If a section fails to load, say so explicitly.

### Anti-Pattern 4: Inventing Status When Commands Fail
**What it looks like**: Reporting "CI passing" when `gh pr checks` returned an error
**Why wrong**: False status is worse than no status
**Do instead**: Report the command failure and what information is unavailable

---

## References

This skill uses these shared patterns:
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
