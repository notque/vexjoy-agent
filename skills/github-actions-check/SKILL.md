---
name: github-actions-check
description: |
  Check GitHub Actions workflow status after git push using gh CLI. Reports
  CI status, identifies failing jobs, and suggests local reproduction
  commands. Use after "git push", when user asks about CI status, workflow
  failures, or build results. Use for "check CI", "workflow status",
  "actions failing", or "build broken". Do NOT use for local linting
  (use code-linting), debugging test failures locally (use
  systematic-debugging), or setting up new workflows.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
routing:
  force_route: true
  triggers:
    - "check CI"
    - "CI status"
    - "actions status"
    - "did CI pass"
  category: git-workflow
---

# GitHub Actions Check Skill

## Operator Context

This skill operates as an operator for GitHub Actions monitoring workflows, configuring Claude's behavior for automated CI/CD status checking after git operations. It implements the **Observe and Report** pattern -- wait for workflow registration, check status, identify failures, suggest remediation.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution
- **Over-Engineering Prevention**: Only check what's directly relevant. No speculative monitoring, no custom API scripts when gh CLI works, no workflow file modifications
- **Wait Before Check**: Always wait 5-10 seconds after push for GitHub to register the workflow
- **Complete Output Display**: Show full `gh` command output, never summarize as "build passed" or "tests failed"
- **Branch-Aware Checking**: Always check workflows for the branch that was actually pushed, not default branch
- **Prefer gh CLI**: Always use `gh` CLI over raw API calls -- it handles auth, pagination, and formatting

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- **Temporary File Cleanup**: Remove any temporary scripts or cache files created during workflow status checking at task completion.
- **Failure Investigation**: When failures detected, identify specific failing jobs and suggest local reproduction commands
- **Auto-fix Suggestions**: For common failures (linting, formatting), provide exact fix commands without executing them

### Optional Behaviors (OFF unless enabled)
- **Automatic Fix Application**: Only fix and re-push if user explicitly requests it
- **Watch Mode**: Only use `gh run watch` for interactive monitoring if user asks
- **Detailed Job Logs**: Only fetch full job logs (`gh run view --log-failed`) if user needs debugging details

## What This Skill CAN Do
- Check workflow run status for a specific branch after push
- Identify which jobs failed and show their output
- Suggest local reproduction commands for common CI failures
- Report on multiple workflow runs for comparison
- Show complete gh CLI output for user review

## What This Skill CANNOT Do
- Auto-fix and re-push without explicit user permission
- Modify workflow YAML files or CI configuration
- Replace local debugging (use systematic-debugging for root cause analysis)
- Replace local linting (use code-linting for pre-push checks)
- Summarize or abbreviate gh CLI output

---

## Instructions

### Step 1: Identify Repository and Branch

**Goal**: Determine which repository and branch to check.

```bash
# Get repository from git remote
git remote get-url origin

# Get the branch that was pushed
git branch --show-current
```

**Gate**: Repository and branch identified. Proceed only when gate passes.

### Step 2: Wait and Check Workflow Status

**Goal**: Allow GitHub to register the workflow, then retrieve status.

```bash
# Wait for GitHub to register the workflow run
sleep 10

# Check workflow runs for the pushed branch
BRANCH=$(git branch --show-current)
gh run list --branch "$BRANCH" --limit 5
```

Show the complete output. Do not summarize.

**Gate**: Workflow status retrieved and displayed. Proceed only when gate passes.

### Step 3: Investigate Failures

**Goal**: If any workflow failed, identify the specific failing jobs.

Only execute this step if Step 2 shows a failed or failing run.

```bash
# Get details of the failed run
gh run view <run-id>

# For deeper investigation (only if user requests)
gh run view <run-id> --log-failed
```

For each failing job, identify:
1. Which job failed (build, test, lint, deploy)
2. The specific error message
3. A local reproduction command

```markdown
## Failure Report
Job: [job name]
Error: [specific error from logs]
Local reproduction: [command to reproduce locally]
Suggested fix: [exact commands to fix, if applicable]
```

**Gate**: All failures identified with reproduction commands. Proceed only when gate passes.

### Step 4: Report and Suggest

**Goal**: Present findings and suggest next steps without auto-fixing.

If all checks passed:
- Show the complete `gh run list` output
- Confirm which workflows ran and their status

If checks failed:
- Show the failure report from Step 3
- Suggest local reproduction commands
- Suggest fix commands (but do NOT execute without permission)
- Ask the user if they want you to apply fixes

**Gate**: Complete status report delivered to user.

---

## Error Handling

### Error: "gh CLI not found"
**Cause**: GitHub CLI not installed on the system
**Solution**:
1. Check if `gh` is available: `which gh`
2. If missing, suggest installation: `brew install gh` or `sudo apt install gh`
3. As last resort, use `curl` with GitHub API (but prefer installing gh)

### Error: "gh auth required"
**Cause**: GitHub CLI not authenticated
**Solution**:
1. Run `gh auth status` to check current auth
2. If not authenticated, suggest `gh auth login`
3. Check if GITHUB_TOKEN environment variable is set as alternative

### Error: "No workflow runs found"
**Cause**: Workflow not triggered, branch has no workflows, or checked too early
**Solution**:
1. Wait longer (up to 30 seconds) and retry
2. Verify `.github/workflows/` directory exists in the repository
3. Check if workflow is configured to trigger on the pushed branch
4. Verify push event matches workflow trigger conditions

---

## Anti-Patterns

### Anti-Pattern 1: Checking Immediately After Push
**What it looks like**: `git push && gh run list --limit 1`
**Why wrong**: GitHub needs 5-10 seconds to register the workflow. Immediate checks show stale results from previous runs.
**Do instead**: Always `sleep 10` between push and status check.

### Anti-Pattern 2: Summarizing Workflow Results
**What it looks like**: "The build passed successfully."
**Why wrong**: Hides which jobs ran, timing, warnings. User cannot verify results. Violates Complete Output Display behavior.
**Do instead**: Show the complete `gh run list` or `gh run view` output verbatim.

### Anti-Pattern 3: Auto-Fixing Without Permission
**What it looks like**: Detecting lint failure, then running `ruff check --fix . && git push` automatically.
**Why wrong**: Makes code changes and git commits without user review. May introduce unintended changes. Violates optional behavior default.
**Do instead**: Suggest fix commands and wait for explicit user confirmation before executing.

### Anti-Pattern 4: Checking Wrong Branch
**What it looks like**: `gh run list --limit 1` without specifying `--branch`.
**Why wrong**: May show workflow runs from other branches (main, other feature branches). Gives misleading status for the user's actual push.
**Do instead**: Always use `--branch "$BRANCH"` with the branch that was actually pushed.

### Anti-Pattern 5: Using Raw API When gh CLI Is Available
**What it looks like**: Writing 50 lines of Python with `requests` to hit the GitHub API.
**Why wrong**: `gh` handles auth, pagination, and formatting automatically. Custom code adds unnecessary complexity and maintenance burden.
**Do instead**: Use `gh run list`, `gh run view`, and `gh run watch`. Only fall back to API if `gh` is truly unavailable.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Build passed" (without showing output) | Claim without evidence is unverifiable | Show complete gh output |
| "Checked right after push" | Too early shows stale results | Wait 10 seconds minimum |
| "Those failures are pre-existing" | Assumption without evidence | Compare with previous runs |
| "I'll just fix and re-push" | Auto-fixing without permission | Ask user before applying fixes |
